// Follow-up list (PI 2026-11-25): every outcome assessment per randomised baby,
// Form I 36 / 40 / 44 wk PMA (window ± 2 days) and the outpatient ROP screen
// for babies who left before one (backend/followup_list.py). All staff: own
// site; Global PI and central scientists pick a site. Names only with PII rights.
import React, { useEffect, useMemo, useState } from "react";
import { CalendarClock } from "lucide-react";
import { Link } from "react-router-dom";
import api from "./api/axios";
import { useAuth } from "./context/AuthContext";
import DashboardWorkspaceLayout from "./components/dashboard/DashboardWorkspaceLayout";
import { canUseShiftReport, isGlobalUser } from "./utils/roles";
import { SITE_ORDER } from "./utils/siteNames";
import { formatSiteName } from "./components/dashboard/siteLabels";
import "./SiteSummary.css";

const VIEWS = [
  ["due", "Due or overdue (next 14 days)"],
  ["overdue", "Overdue"],
  ["upcoming", "All still to do"],
  ["done", "Done"],
  ["all", "Everything"],
];

const STATUS_LABEL = {
  overdue: "Overdue", window: "Window open", booked: "Booked", upcoming: "Coming up",
  in_nicu: "Admitted", done: "Done", ended: "Ended",
};

const fmt = (iso) => (iso
  ? new Date(`${String(iso).slice(0, 10)}T00:00:00`).toLocaleDateString("en-GB",
    { day: "2-digit", month: "short", year: "numeric" })
  : "");

const TODO = new Set(["overdue", "window", "booked", "upcoming", "in_nicu"]);

export default function FollowupList() {
  const { user } = useAuth();
  const allowed = canUseShiftReport(user);
  const global = isGlobalUser(user);
  const [site, setSite] = useState("");
  const [view, setView] = useState("due");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!allowed) return;
    setError("");
    api.get("/followup-list", { params: global && site ? { site } : {} })
      .then((res) => setData(res.data))
      .catch((e) => setError(e?.response?.data?.detail || "Could not load the follow-up list."));
  }, [allowed, global, site]);

  const rows = useMemo(() => {
    const all = data?.rows || [];
    if (view === "all") return all;
    if (view === "done") return all.filter((r) => r.status === "done");
    if (view === "overdue") return all.filter((r) => r.status === "overdue");
    if (view === "upcoming") return all.filter((r) => TODO.has(r.status));
    return all.filter((r) => r.status === "overdue" || (TODO.has(r.status) && r.days_to_due <= 14));
  }, [data, view]);

  const counts = useMemo(() => {
    const all = data?.rows || [];
    return {
      overdue: all.filter((r) => r.status === "overdue").length,
      soon: all.filter((r) => TODO.has(r.status) && r.status !== "overdue" && r.days_to_due <= 14).length,
      booked: all.filter((r) => r.status === "booked").length,
    };
  }, [data]);

  if (!allowed) {
    return (
      <DashboardWorkspaceLayout pageTitle="Follow-up list">
        <div className="ss-root ss-none">The follow-up list is for site staff and the central team.</div>
      </DashboardWorkspaceLayout>
    );
  }

  const showSite = global && !site;
  return (
    <DashboardWorkspaceLayout pageTitle="Follow-up list">
      <div className="ss-root">
        <div className="ss-hero">
          <div className="ss-hero-icon" aria-hidden="true"><CalendarClock size={20} /></div>
          <div>
            <h1>Follow-up list</h1>
            <p>
              Outcome assessments for every randomised baby: Form I at 36, 40 and 44 weeks PMA (window
              ± 2 days), and the outpatient ROP screen for babies who left before one. Booked dates come
              from the Form H follow-up calendar. A row clears itself when Form I or Form G is filled.
            </p>
          </div>
        </div>
        <div className="ss-bar">
          {global ? (
            <label className="ss-field">
              <span>Site</span>
              <select value={site} onChange={(e) => setSite(e.target.value)}>
                <option value="">All sites</option>
                {SITE_ORDER.map((s) => <option key={s} value={s}>{formatSiteName(s)}</option>)}
              </select>
            </label>
          ) : (
            <span className="ss-note">Site: {formatSiteName(user?.site_name)}</span>
          )}
        </div>

        <div className="fl-tiles">
          <button type="button" className="fl-tile fl-red" onClick={() => setView("overdue")}>
            <strong>{counts.overdue}</strong> overdue</button>
          <button type="button" className="fl-tile fl-amber" onClick={() => setView("due")}>
            <strong>{counts.soon}</strong> due in 14 days</button>
          <button type="button" className="fl-tile fl-blue" onClick={() => setView("upcoming")}>
            <strong>{counts.booked}</strong> booked</button>
        </div>

        <div className="fl-views">
          {VIEWS.map(([k, label]) => (
            <button type="button" key={k} className={`fl-view${view === k ? " is-on" : ""}`}
              onClick={() => setView(k)}>{label}</button>
          ))}
        </div>

        {error && <p className="ss-none">{error}</p>}
        {!data && !error && <p className="ss-none">Loading…</p>}
        {data && (rows.length ? (
          <div className="ss-table-wrap">
            <table className="ss-table">
              <thead><tr>
                {showSite && <th>Site</th>}<th>Baby</th><th>Assessment</th><th>Date</th><th>Window</th>
                <th>Status</th><th>Now</th><th />
              </tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={`${r.enrollment_id}-${r.assessment}`} className={`fl-row fl-${r.status}`}>
                    {showSite && <td>{formatSiteName(r.site)}</td>}
                    <td><span className="ss-id">{r.enrollment_id}</span>{r.name ? <div className="ss-name">{r.name}</div> : null}</td>
                    <td>{r.assessment}</td>
                    <td>{fmt(r.due)}</td>
                    <td>{r.window_from ? `${fmt(r.window_from)} – ${fmt(r.window_to)}` : `by ${fmt(r.window_to)}`}</td>
                    <td><span className={`fl-badge fl-b-${r.status}`}>{STATUS_LABEL[r.status] || r.status}</span>
                      <div className="fl-text">{r.text}</div></td>
                    <td>{r.where}</td>
                    <td>
                      <Link to={r.kind === "rop" ? `/form-g/${r.enrollment_id}` : `/form-i/${r.enrollment_id}`}>
                        {r.kind === "rop" ? "Form G" : "Form I"}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="ss-none">Nothing in this view.</p>)}
      </div>
    </DashboardWorkspaceLayout>
  );
}
