// Data queries inbox (Phase 1 of real-time data-quality monitoring, PI
// 2026-10-15). Problems found by the server's fixed checks
// (backend/data_checks.py); this page only shows them and records what the
// scientist did. Queries close by themselves once the data is corrected.
// Site PI / Site Scientist: own site. Global PI + Overall Project Scientist:
// all sites, and the second sign-off.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  AlertTriangle, Clock, ListChecks, RefreshCw, ShieldAlert,
} from "lucide-react";
import api from "./api/axios";
import { useAuth } from "./context/AuthContext";
import DashboardWorkspaceLayout from "./components/dashboard/DashboardWorkspaceLayout";
import { canSeeDataQueries, isCentralReviewer } from "./utils/roles";
import { siteShortCode } from "./utils/siteNames";
import "./DataQueries.css";

const STATUS_LABEL = {
  open: "Open",
  acknowledged: "Acknowledged",
  awaiting_signoff: "Awaiting sign-off",
  resolved: "Resolved",
  confirmed_correct: "Confirmed correct",
};

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
}

// ?show= (PI 2026-11-04): the count tiles here and in the daily email link
// to the list they count. status = what the server is asked for; keep = the
// rows of that list to show.
const DAY_MS = 86400000;
const since24 = (iso) => !!iso && Date.now() - new Date(iso.endsWith("Z") ? iso : `${iso}Z`).getTime() < DAY_MS;
const SHOW = {
  open: { label: "Open", status: "open", keep: () => true },
  amber: { label: "Over 72 h", status: "open", keep: (q) => q.colour === "amber" },
  red: { label: "Over 7 days", status: "open", keep: (q) => q.colour === "red" },
  awaiting: { label: "Awaiting sign-off", status: "open", keep: (q) => q.status === "awaiting_signoff" },
  new: { label: "New (24 h)", status: "open", keep: (q) => since24(q.first_seen_at) },
  closed24: { label: "Closed (24 h)", status: "closed", keep: (q) => since24(q.confirmed_at) || since24(q.resolved_at) },
  closed: { label: "Closed", status: "closed", keep: () => true },
  all: { label: "All", status: "all", keep: () => true },
};

function recordLink(q) {
  // ?entry= opens the log at that entry (hooks/useEntryFocus.js).
  const entry = encodeURIComponent(q.record_key);
  if (q.record_type === "ga_check") return `/ga-check?entry=${entry}`;
  if (q.record_type === "birth_log") return `/log-of-all-births?entry=${entry}`;
  return null;
}

export default function DataQueries() {
  const { user } = useAuth();
  const central = isCentralReviewer(user);
  const [params, setParams] = useSearchParams();
  const show = SHOW[params.get("show")] ? params.get("show") : "open";
  const status = SHOW[show].status;
  const setShow = (v) => setParams(v === "open" ? {} : { show: v }, { replace: true });
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(null); // query id
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [list, sum] = await Promise.all([
        api.get("/data-queries/", { params: { status } }),
        api.get("/data-queries/summary"),
      ]);
      setRows(list.data || []);
      setSummary(sum.data || null);
    } catch (e) {
      setError(e?.response?.data?.detail || "Could not load data queries.");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => { load(); }, [load]);

  const act = async (q, path, body) => {
    setBusy(q.id);
    setError("");
    try {
      await api.post(`/data-queries/${q.id}/${path}`, body || {});
      setConfirming(null);
      setReason("");
      await load();
    } catch (e) {
      setError(e?.response?.data?.detail || "Action failed.");
    } finally {
      setBusy(null);
    }
  };

  const groups = useMemo(() => {
    const g = {};
    rows.filter(SHOW[show].keep).forEach((q) => { (g[q.area || "Other"] = g[q.area || "Other"] || []).push(q); });
    return Object.entries(g);
  }, [rows, show]);
  const shown = groups.reduce((n, [, qs]) => n + qs.length, 0);

  const Tile = ({ to, className, label, icon: Icon, n }) => (
    <button type="button" className={`dqy-tile ${className || ""} ${show === to ? "dqy-tile--on" : ""}`}
      onClick={() => setShow(to)} title={`Show: ${SHOW[to].label}`}>
      <span className="dqy-tile-label">{label}</span>
      <Icon size={16} aria-hidden="true" />
      <b>{n}</b>
    </button>
  );

  if (!canSeeDataQueries(user)) {
    return (
      <DashboardWorkspaceLayout pageTitle="Data Queries">
        <div className="dqy-root dqy-empty">Data queries are for Site PIs, scientists and the Global PI.</div>
      </DashboardWorkspaceLayout>
    );
  }

  return (
    <DashboardWorkspaceLayout pageTitle="Data Queries" onRefresh={load}>
      <div className="dqy-root">
        <div className="dqy-hero">
          <div className="dqy-hero-icon" aria-hidden="true">
            <ListChecks size={20} />
          </div>
          <div>
            <h1>Data Queries</h1>
            <p>
              Problems found automatically in the data. A query closes by itself once the record is corrected;
              if the data is right, confirm it with a reason.
            </p>
          </div>
        </div>

        {summary && (
          <div className="dqy-tiles">
            <Tile to="open" label="Open" icon={ListChecks} n={summary.total} />
            <Tile to="amber" className="dqy-tile--amber" label="Over 72 h" icon={Clock} n={summary.amber || 0} />
            <Tile to="red" className="dqy-tile--red" label="Over 7 days" icon={AlertTriangle} n={summary.red || 0} />
            <Tile to="awaiting" className="dqy-tile--violet" label="Awaiting sign-off" icon={ShieldAlert}
              n={summary.awaiting_signoff || 0} />
          </div>
        )}

        <div className="dqy-toolbar">
          <select value={show} onChange={(e) => setShow(e.target.value)} aria-label="Show">
            {Object.entries(SHOW).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
          <button type="button" className="dqy-refresh" onClick={load} disabled={loading}>
            <RefreshCw size={14} aria-hidden="true" />
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>

        {error && <div className="dqy-error">{error}</div>}
        {!loading && shown === 0 && (
          <div className="dqy-empty">No queries{show === "all" ? "" : `: ${SHOW[show].label.toLowerCase()}`}.</div>
        )}

        {groups.map(([area, qs]) => (
          <section key={area} className="dqy-group">
            <h3>{area} <span>({qs.length})</span></h3>
            <table className="dqy-table">
              <thead>
                <tr>
                  <th aria-label="Age" />
                  {central && <th>Site</th>}
                  <th>Problem</th>
                  <th>Due</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {qs.map((q) => {
                  const link = recordLink(q);
                  return (
                    <tr key={q.id}>
                      <td><span className={`dqy-dot dqy-dot--${q.colour || "none"}`} title={q.colour === "red" ? "Over 7 days" : q.colour === "amber" ? "Over 72 hours" : ""} /></td>
                      {central && <td>{siteShortCode(q.site_name) || "—"}</td>}
                      <td>
                        <div className="dqy-title">
                          {q.title}
                          {q.needs_second_signoff && <span className="dqy-tag">2nd sign-off</span>}
                        </div>
                        <div className="dqy-detail">{q.detail}</div>
                        {link && <Link className="dqy-link" to={link}>Open entry #{q.record_key}</Link>}
                        {q.confirmed_reason && (
                          <div className="dqy-reason">Confirmed by {q.confirmed_by}: {q.confirmed_reason}</div>
                        )}
                        {confirming === q.id && (
                          <div className="dqy-confirm">
                            <textarea
                              value={reason}
                              onChange={(e) => setReason(e.target.value)}
                              placeholder="Why the data is correct (required)"
                              rows={2}
                            />
                            <div>
                              <button type="button" disabled={busy === q.id || reason.trim().length < 5}
                                onClick={() => act(q, "confirm-correct", { reason })}>Confirm correct</button>
                              <button type="button" className="dqy-ghost" onClick={() => { setConfirming(null); setReason(""); }}>Cancel</button>
                            </div>
                          </div>
                        )}
                      </td>
                      <td className="dqy-nowrap">{fmtDate(q.due_at)}</td>
                      <td className="dqy-nowrap">
                        <span className={`dqy-status dqy-status--${q.status || "open"}`}>
                          {STATUS_LABEL[q.status] || q.status}
                        </span>
                      </td>
                      <td className="dqy-actions">
                        {q.status === "open" && (
                          <button type="button" disabled={busy === q.id} onClick={() => act(q, "acknowledge")}>Acknowledge</button>
                        )}
                        {["open", "acknowledged"].includes(q.status) && confirming !== q.id && (
                          <button type="button" className="dqy-ghost" onClick={() => { setConfirming(q.id); setReason(""); }}>Data is correct…</button>
                        )}
                        {q.status === "awaiting_signoff" && central && (
                          <>
                            <button type="button" disabled={busy === q.id} onClick={() => act(q, "signoff")}>Sign off</button>
                            <button type="button" className="dqy-ghost" disabled={busy === q.id} onClick={() => act(q, "reject-confirmation")}>Reopen</button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        ))}
      </div>
    </DashboardWorkspaceLayout>
  );
}
