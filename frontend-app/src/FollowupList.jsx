// Follow-up list, baby by baby (PI 2026-11-26): for every randomised baby, its
// time points worked out from date of birth, gestation and PMA (day 3, day 7,
// day 28, DOL 30 ROP, 36 / 40 / 44 wk PMA, discharge), what to document at each,
// the date or window and whether it is done (backend/followup_timeline.py,
// GET /followup-list/timeline). All staff: own site; central team any site.
// Names only with PII rights.
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

const BADGE = {
  done: "flist-b-done", booked: "flist-b-booked", due_now: "flist-b-window", overdue: "flist-b-overdue",
  due: "flist-b-due", at_discharge: "flist-b-in_nicu", na: "flist-b-na",
};

export default function FollowupList() {
  const { user } = useAuth();
  const allowed = canUseShiftReport(user);
  const global = isGlobalUser(user);
  const [site, setSite] = useState("");
  const [show, setShow] = useState("soon");
  const [q, setQ] = useState("");
  const [hideDone, setHideDone] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!allowed) return;
    setData(null);
    setError("");
    api.get("/followup-list/timeline", { params: global && site ? { site } : {} })
      .then((res) => setData(res.data))
      .catch((e) => setError(e?.response?.data?.detail || "Could not load the follow-up list."));
  }, [allowed, global, site]);

  const cards = useMemo(() => {
    let all = data?.cards || [];
    if (show === "soon") all = all.filter((c) => c.counts.overdue || c.counts.soon);
    if (show === "overdue") all = all.filter((c) => c.counts.overdue);
    const s = q.trim().toLowerCase();
    if (s) all = all.filter((c) => c.enrollment_id.toLowerCase().includes(s) || (c.name || "").toLowerCase().includes(s));
    return all;
  }, [data, show, q]);

  if (!allowed) {
    return (
      <DashboardWorkspaceLayout pageTitle="Follow-up list">
        <div className="ss-root ss-none">The follow-up list is for site staff and the central team.</div>
      </DashboardWorkspaceLayout>
    );
  }

  const total = data?.cards?.length || 0;
  return (
    <DashboardWorkspaceLayout pageTitle="Follow-up list">
      <div className="ss-root">
        <div className="ss-hero">
          <div className="ss-hero-icon" aria-hidden="true"><CalendarClock size={20} /></div>
          <div>
            <h1>Follow-up list</h1>
            <p>
              Baby by baby: what has to be documented and when, worked out from the date of birth, gestation and
              PMA: day 3, day 7 and day 28 (cranial USG, early outcomes), the first ROP screen by DOL 30, Form I at
              36, 40 and 44 weeks PMA, MRI at term (subset) and discharge. Each line clears itself when the form is
              filled. Tap a line to open the form.
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
          <label className="ss-field">
            <span>Babies</span>
            <select value={show} onChange={(e) => setShow(e.target.value)}>
              <option value="soon">Something due in 14 days or overdue</option>
              <option value="overdue">Something overdue</option>
              <option value="all">All randomised babies</option>
            </select>
          </label>
          <label className="ss-field">
            <span>Find</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ID or name" />
          </label>
          <label className="flist-check">
            <input type="checkbox" checked={hideDone} onChange={(e) => setHideDone(e.target.checked)} /> Hide done lines
          </label>
        </div>

        {error && <p className="ss-none">{error}</p>}
        {!data && !error && <p className="ss-none">Loading…</p>}
        {data && <p className="flist-count">{cards.length} of {total} babies shown</p>}
        {data && cards.length === 0 && <p className="ss-none">No baby in this view.</p>}

        {cards.map((c) => (
          <section key={c.enrollment_id} className="flist-card">
            <header className="flist-card-head">
              <div>
                <span className="ss-id">{c.enrollment_id}</span>
                {c.name && <span className="flist-name"> · {c.name}</span>}
                <span className="flist-meta"> · GA {c.ga} · born {c.dob_text}{global && !site ? ` · ${formatSiteName(c.site)}` : ""}</span>
              </div>
              <div className="flist-meta">Now: {c.now} · {c.status}</div>
              <div className="flist-next">
                {c.counts.overdue > 0 && <span className="flist-badge flist-b-overdue">{c.counts.overdue} overdue</span>}
                {c.next ? <span>Next: <strong>{c.next.text}</strong></span> : <span>Nothing left to schedule</span>}
              </div>
            </header>
            <table className="flist-tl">
              <thead><tr><th>Time point</th><th>Date / window</th><th>To document</th><th>Status</th></tr></thead>
              <tbody>
                {c.rows.map((r) => {
                  const items = hideDone ? r.items.filter((i) => i.status !== "done" && i.status !== "na") : r.items;
                  if (!items.length) return null;
                  return items.map((it, i) => (
                    <tr key={`${r.key}-${i}`} className={i === 0 ? "flist-tp-first" : ""}>
                      {i === 0 && <td rowSpan={items.length} className="flist-tp">{r.label}</td>}
                      {i === 0 && (
                        <td rowSpan={items.length} className="flist-date">
                          {r.date_text || r.window}
                          {r.date_text && r.window ? <div className="flist-window">{r.window}</div> : null}
                        </td>
                      )}
                      <td><Link to={it.route}><strong>{it.form}:</strong> {it.text}</Link></td>
                      <td><span className={`flist-badge ${BADGE[it.status] || ""}`}>{it.status_text}</span></td>
                    </tr>
                  ));
                })}
              </tbody>
            </table>
          </section>
        ))}
      </div>
    </DashboardWorkspaceLayout>
  );
}
