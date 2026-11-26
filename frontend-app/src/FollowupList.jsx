// Follow-up list, baby by baby (PI 2026-11-26): for every randomised baby, its
// time points worked out from date of birth, gestation and PMA (day 3, day 7,
// day 28, DOL 30 ROP, 36 / 40 / 44 wk PMA, discharge), what to document at each,
// the date or window and whether it is done (backend/followup_timeline.py,
// GET /followup-list/timeline). All staff: own site; central team any site.
// Names only with PII rights.
// PI 2026-11-26 (2): the Babies filter filters lines, not only babies ("Something
// overdue" shows only overdue lines; "at discharge" and done lines are left
// out), and a Calendar view: tasks under their date, grouped by baby.
import React, { useEffect, useMemo, useState } from "react";
import { CalendarClock, ChevronLeft, ChevronRight } from "lucide-react";
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
const OPEN = new Set(["overdue", "due_now", "due", "booked"]);
const RANK = { overdue: 0, due_now: 1, booked: 2, due: 3 };
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
  "October", "November", "December"];

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parseIso = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
const dayText = (s) => { const d = parseIso(s); return `${WEEKDAYS[(d.getDay() + 6) % 7]} ${d.getDate()} ${MONTHS[d.getMonth()].slice(0, 3)}`; };

/** Lines of a card that the Babies filter keeps. */
function visibleItems(items, show, hideDone) {
  if (show === "overdue") return items.filter((i) => i.status === "overdue");
  if (show === "soon") return items.filter((i) => i.soon);
  return hideDone ? items.filter((i) => i.status !== "done" && i.status !== "na") : items;
}

function BabyLine({ c, global, site }) {
  return (
    <>
      <span className="ss-id">{c.enrollment_id}</span>
      {c.name && <span className="flist-name"> · {c.name}</span>}
      {global && !site ? <span className="flist-meta"> · {formatSiteName(c.site)}</span> : null}
    </>
  );
}

/** Tasks grouped by baby: [{card, items: [{...item, rowLabel}]}]. */
function TaskGroups({ groups, global, site, showDate }) {
  return groups.map(({ card, items }) => (
    <div key={card.enrollment_id} className="fcal-group">
      <div className="fcal-group-head"><BabyLine c={card} global={global} site={site} />
        <span className="flist-meta"> · {card.status}</span></div>
      <ul className="fcal-items">
        {items.map((it, i) => (
          <li key={i}>
            <Link to={it.route}><strong>{it.form}:</strong> {it.text}</Link>
            <span className="flist-meta"> · {it.rowLabel}{showDate && it.date ? ` · ${dayText(it.date)}` : ""}</span>{" "}
            <span className={`flist-badge ${BADGE[it.status] || ""}`}>{it.status_text}</span>
          </li>
        ))}
      </ul>
    </div>
  ));
}

function groupByBaby(entries) {
  const m = new Map();
  for (const e of entries) {
    if (!m.has(e.card.enrollment_id)) m.set(e.card.enrollment_id, { card: e.card, items: [] });
    m.get(e.card.enrollment_id).items.push(e.item);
  }
  return [...m.values()];
}

function CalendarView({ cards, today, global, site }) {
  // Panels start closed so the month grid is in view; "Due now" lists windows
  // already open on or before today (a deadline later on, e.g. the DOL 30 ROP
  // screen, stays on the grid on its date).
  const [month, setMonth] = useState(() => { const t = parseIso(today); return new Date(t.getFullYear(), t.getMonth(), 1); });
  const [picked, setPicked] = useState(today);

  const { byDate, overdue, dueNow } = useMemo(() => {
    const byDate = new Map(); const overdue = []; const dueNow = [];
    for (const card of cards) {
      for (const r of card.rows) {
        for (const it of r.items) {
          if (!OPEN.has(it.status)) continue;
          const e = { card, item: { ...it, rowLabel: r.label } };
          if (it.status === "overdue") overdue.push(e);
          if (it.status === "due_now" && it.date && it.date <= today) dueNow.push(e);
          if (!it.date) continue;
          if (!byDate.has(it.date)) byDate.set(it.date, []);
          byDate.get(it.date).push(e);
        }
      }
    }
    return { byDate, overdue, dueNow };
  }, [cards, today]);

  const cells = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    const start = new Date(first); start.setDate(1 - ((first.getDay() + 6) % 7));
    const out = [];
    for (let i = 0; i < 42; i++) {
      const d = new Date(start); d.setDate(start.getDate() + i);
      if (i >= 35 && d.getMonth() !== month.getMonth()) break;
      out.push(d);
    }
    return out;
  }, [month]);

  const pickedGroups = groupByBaby(byDate.get(picked) || []);
  const shift = (n) => setMonth(new Date(month.getFullYear(), month.getMonth() + n, 1));

  return (
    <div>
      {overdue.length > 0 && (
        <details className="fcal-panel fcal-panel-red">
          <summary>Overdue: {overdue.length} task{overdue.length !== 1 ? "s" : ""} ({groupByBaby(overdue).length} babies), tap to open</summary>
          <TaskGroups groups={groupByBaby(overdue)} global={global} site={site} showDate />
        </details>
      )}
      {dueNow.length > 0 && (
        <details className="fcal-panel fcal-panel-amber">
          <summary>Due now (window open): {dueNow.length} task{dueNow.length !== 1 ? "s" : ""} ({groupByBaby(dueNow).length} babies), tap to open</summary>
          <TaskGroups groups={groupByBaby(dueNow)} global={global} site={site} showDate />
        </details>
      )}

      <div className="fcal-head">
        <button type="button" className="fcal-nav" onClick={() => shift(-1)} aria-label="Previous month"><ChevronLeft size={16} /></button>
        <strong>{MONTHS[month.getMonth()]} {month.getFullYear()}</strong>
        <button type="button" className="fcal-nav" onClick={() => shift(1)} aria-label="Next month"><ChevronRight size={16} /></button>
        <button type="button" className="fcal-today" onClick={() => { const t = parseIso(today); setMonth(new Date(t.getFullYear(), t.getMonth(), 1)); setPicked(today); }}>Today</button>
      </div>
      <div className="fcal-grid" role="grid">
        {WEEKDAYS.map((w) => <div key={w} className="fcal-wd">{w}</div>)}
        {cells.map((d) => {
          const k = iso(d);
          const groups = groupByBaby(byDate.get(k) || []);
          const n = groups.reduce((a, g) => a + g.items.length, 0);
          const cls = ["fcal-day", d.getMonth() !== month.getMonth() ? "is-out" : "", k === today ? "is-today" : "",
            k === picked ? "is-picked" : "", n ? "has-tasks" : ""].join(" ");
          return (
            <button type="button" key={k} className={cls} onClick={() => setPicked(k)}
              aria-label={`${dayText(k)}: ${n} task${n !== 1 ? "s" : ""}`}>
              <span className="fcal-num">{d.getDate()}</span>
              {n > 0 && <span className="fcal-count">{n}</span>}
              <span className="fcal-chips">
                {groups.slice(0, 3).map((g) => {
                  const worst = g.items.reduce((a, it) => (RANK[it.status] < RANK[a] ? it.status : a), "due");
                  return <span key={g.card.enrollment_id} className={`fcal-chip ${BADGE[worst] || ""}`}>
                    {g.card.enrollment_id}{g.items.length > 1 ? ` ×${g.items.length}` : ""}</span>;
                })}
                {groups.length > 3 && <span className="fcal-more">+{groups.length - 3} more</span>}
              </span>
            </button>
          );
        })}
      </div>

      <h2 className="fcal-day-title">{dayText(picked)}{picked === today ? " (today)" : ""}</h2>
      {pickedGroups.length === 0
        ? <p className="ss-none">Nothing due on this date.</p>
        : <TaskGroups groups={pickedGroups} global={global} site={site} />}
      <p className="flist-count">Tasks sit on their due date (a scan window on its first day, a booked visit on its
        booked date). Lines to be filled at discharge are in the Baby-by-baby view.</p>
    </div>
  );
}

export default function FollowupList() {
  const { user } = useAuth();
  const allowed = canUseShiftReport(user);
  const global = isGlobalUser(user);
  const [site, setSite] = useState("");
  const [view, setView] = useState("babies");
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

  const found = useMemo(() => {
    const s = q.trim().toLowerCase();
    const all = data?.cards || [];
    return s ? all.filter((c) => c.enrollment_id.toLowerCase().includes(s) || (c.name || "").toLowerCase().includes(s)) : all;
  }, [data, q]);

  // Baby-by-baby: keep only the lines the filter asks for, and babies with any left
  const cards = useMemo(() => found
    .map((c) => ({ ...c, rows: c.rows.map((r) => ({ ...r, items: visibleItems(r.items, show, hideDone) })) }))
    .filter((c) => show === "all" || c.rows.some((r) => r.items.length)), [found, show, hideDone]);

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
              PMA: the baby's ID numbers on Form B by day 7, day 3, day 7 and day 28 (cranial USG, early outcomes),
              the first ROP screen by DOL 30, Form I at 36, 40 and 44 weeks PMA, MRI at term (subset) and discharge.
              Each line clears itself when the form is filled. Tap a line to open the form. The Calendar shows the
              same tasks under their dates.
            </p>
          </div>
        </div>
        <div className="flist-views" role="tablist" aria-label="View">
          <button type="button" role="tab" aria-selected={view === "babies"} className={`flist-view${view === "babies" ? " is-on" : ""}`}
            onClick={() => setView("babies")}>Baby by baby</button>
          <button type="button" role="tab" aria-selected={view === "calendar"} className={`flist-view${view === "calendar" ? " is-on" : ""}`}
            onClick={() => setView("calendar")}>Calendar</button>
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
          {view === "babies" && (
            <label className="ss-field">
              <span>Show</span>
              <select value={show} onChange={(e) => setShow(e.target.value)}>
                <option value="soon">Due in 14 days or overdue</option>
                <option value="overdue">Overdue only</option>
                <option value="all">Everything, all randomised babies</option>
              </select>
            </label>
          )}
          <label className="ss-field">
            <span>Find</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ID or name" />
          </label>
          {view === "babies" && show === "all" && (
            <label className="flist-check">
              <input type="checkbox" checked={hideDone} onChange={(e) => setHideDone(e.target.checked)} /> Hide done lines
            </label>
          )}
        </div>

        {error && <p className="ss-none">{error}</p>}
        {!data && !error && <p className="ss-none">Loading…</p>}

        {data && view === "calendar" && <CalendarView cards={found} today={data.today} global={global} site={site} />}

        {data && view === "babies" && (
          <>
            <p className="flist-count">{cards.length} of {total} babies shown
              {show !== "all" ? " · only the lines in this view (done and at-discharge lines are left out)" : ""}</p>
            {cards.length === 0 && <p className="ss-none">No baby in this view.</p>}
            {cards.map((c) => (
              <section key={c.enrollment_id} className="flist-card">
                <header className="flist-card-head">
                  <div>
                    <BabyLine c={c} global={global} site={site} />
                    <span className="flist-meta"> · GA {c.ga} · born {c.dob_text}</span>
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
                      if (!r.items.length) return null;
                      return r.items.map((it, i) => (
                        <tr key={`${r.key}-${i}`} className={i === 0 ? "flist-tp-first" : ""}>
                          {i === 0 && <td rowSpan={r.items.length} className="flist-tp">{r.label}</td>}
                          {i === 0 && (
                            <td rowSpan={r.items.length} className="flist-date">
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
          </>
        )}
      </div>
    </DashboardWorkspaceLayout>
  );
}
