// Data queries inbox (Phase 1 of real-time data-quality monitoring, PI
// 2026-10-15). Problems found by the server's fixed checks
// (backend/data_checks.py); this page only shows them and records what the
// scientist did. Queries close by themselves once the data is corrected.
// Site PI / Site Scientist: own site. Global PI + Overall Project Scientist:
// all sites, and the second sign-off.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
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

function recordLink(q) {
  if (q.record_type === "ga_check") return "/ga-check";
  if (q.record_type === "birth_log") return "/log-of-all-births";
  return null;
}

export default function DataQueries() {
  const { user } = useAuth();
  const central = isCentralReviewer(user);
  const [status, setStatus] = useState("open");
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
    rows.forEach((q) => { (g[q.area || "Other"] = g[q.area || "Other"] || []).push(q); });
    return Object.entries(g);
  }, [rows]);

  if (!canSeeDataQueries(user)) {
    return (
      <DashboardWorkspaceLayout pageTitle="Data Queries">
        <div className="dqy-root dqy-empty">Data queries are for Site PIs, scientists and the Global PI.</div>
      </DashboardWorkspaceLayout>
    );
  }

  return (
    <DashboardWorkspaceLayout pageTitle="Data Queries">
      <div className="dqy-root">
        <p className="dqy-lead">
          Problems found automatically in the data. A query closes by itself once the record is corrected;
          if the data is right, confirm it with a reason.
        </p>

        {summary && (
          <div className="dqy-tiles">
            <div className="dqy-tile"><b>{summary.total}</b><span>Open</span></div>
            <div className="dqy-tile dqy-tile--amber"><b>{summary.amber || 0}</b><span>Over 72 h</span></div>
            <div className="dqy-tile dqy-tile--red"><b>{summary.red || 0}</b><span>Over 7 days</span></div>
            <div className="dqy-tile"><b>{summary.awaiting_signoff || 0}</b><span>Awaiting sign-off</span></div>
          </div>
        )}

        <div className="dqy-toolbar">
          <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Show">
            <option value="open">Open</option>
            <option value="closed">Closed</option>
            <option value="all">All</option>
          </select>
          <button type="button" onClick={load} disabled={loading}>Refresh</button>
        </div>

        {error && <div className="dqy-error">{error}</div>}
        {!loading && rows.length === 0 && <div className="dqy-empty">No {status === "open" ? "open " : ""}queries.</div>}

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
                        {link && <Link className="dqy-link" to={link}>Open the log</Link>}
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
                      <td className="dqy-nowrap">{STATUS_LABEL[q.status] || q.status}</td>
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
