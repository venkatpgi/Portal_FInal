// Site summary (PI 2026-10-26): the Monday / Thursday email, live. Randomised
// babies by enrolment ID, with the name when the server sends one (viewer may
// see that site's PII; the email stays IDs only) -- safety watch list (close
// to an SAE), advisory notes, active morbidities, missed data collection.
// Each count tile jumps to its list; the emails link to #watch etc. and
// ?site= (PI 2026-11-04). Rules are fixed in
// backend/site_summary.py; their W / M codes are not shown. Nothing here is
// shown or grouped by arm.
// Global PI + Project Scientist: any or all sites; Site PI / Site Scientist:
// own site.
import React, { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { HeartPulse, RefreshCw } from "lucide-react";
import api from "./api/axios";
import { useAuth } from "./context/AuthContext";
import DashboardWorkspaceLayout from "./components/dashboard/DashboardWorkspaceLayout";
import { canUseReports, isGlobalUser } from "./utils/roles";
import { SITE_ORDER } from "./utils/siteNames";
import { formatSiteName } from "./components/dashboard/siteLabels";
import "./SiteSummary.css";

function apiError(err, fallback) {
  const d = err?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
}

function Baby({ id, name }) {
  return (
    <>
      <span className="ss-id">{id}</span>
      {name && <div className="ss-name">{name}</div>}
    </>
  );
}

function RuleTable({ items, showSite }) {
  if (!items.length) return <p className="ss-none">None.</p>;
  return (
    <div className="ss-table-wrap">
      <table className="ss-table">
        <thead>
          <tr>
            {showSite && <th>Site</th>}
            <th>Baby</th>
            <th>Concern</th>
            <th>Detail</th>
          </tr>
        </thead>
        <tbody>
          {items.map((x, i) => (
            <tr key={i}>
              {showSite && <td>{formatSiteName(x.site)}</td>}
              <td><Baby id={x.enrollment_id || `Form A ${x.screening_id}`} name={x.name} /></td>
              <td><strong>{x.title}</strong></td>
              <td>{x.detail}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SiteSummary() {
  const { user } = useAuth();
  const allowed = canUseReports(user);
  const global = isGlobalUser(user);
  const [params] = useSearchParams();
  const { hash } = useLocation();
  const navigate = useNavigate();
  const [site, setSite] = useState(params.get("site") || "");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    setError("");
    api.get("/site-summary", { params: global && site ? { site } : {} })
      .then(res => setData(res.data))
      .catch(err => setError(apiError(err, "Could not load the site summary.")))
      .finally(() => setLoading(false));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (allowed) load(); }, [allowed, site]);

  const showSite = data?.scope === "ALL";
  const babies = useMemo(() => data?.babies || [], [data]);
  const watch = useMemo(() => babies.flatMap(b => b.watch.map(w => ({ ...w, site: b.site, enrollment_id: b.enrollment_id, name: b.name }))), [babies]);
  const advisory = useMemo(() => babies.flatMap(b => (b.advisory || []).map(a => ({ ...a, site: b.site, enrollment_id: b.enrollment_id, name: b.name }))), [babies]);
  const missed = useMemo(() => [
    ...babies.flatMap(b => b.missed.map(m => ({ ...m, site: b.site, enrollment_id: b.enrollment_id, name: b.name }))),
    ...(data?.mothers || []),
  ], [babies, data]);
  const active = babies.filter(b => b.status === "In NICU" && b.active.length);
  const census = babies.filter(b => b.status === "In NICU" || b.ended_since_last);
  const c = data?.counts || {};

  // An email link (#watch, #missed ...) opens at that list once it is drawn.
  useEffect(() => {
    if (!data || !hash) return;
    const el = document.getElementById(`ss-${hash.slice(1)}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [data, hash]);
  const jump = (to) => {
    if (to.startsWith("/")) { navigate(to); return; }
    document.getElementById(`ss-${to}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  if (!allowed) {
    return (
      <DashboardWorkspaceLayout pageTitle="Site summary">
        <div className="ss-root ss-none">The site summary is for the Global PI, Project Scientist, Site PIs and Site Scientists.</div>
      </DashboardWorkspaceLayout>
    );
  }

  const tiles = [
    ["In NICU", c.in_nicu, "ss-t-dark", "census"], ["Stays ended since last", c.ended_since_last, "ss-t-grey", "census"],
    ["Babies on safety watch list", c.watch_babies, "ss-t-red", "watch"],
    ["With active morbidity", c.active_babies, "ss-t-amber", "active"],
    ["Missed data items", c.missed, "ss-t-violet", "missed"], ["Advisory notes", c.advisory, "ss-t-teal", "advisory"],
    ["Overdue queries", c.red_queries, "ss-t-blue", "/data-queries?show=red"],
  ];

  return (
    <DashboardWorkspaceLayout pageTitle="Site summary">
      <div className="ss-root">
        <div className="ss-hero">
          <div className="ss-hero-icon" aria-hidden="true"><HeartPulse size={20} /></div>
          <div>
            <h1>Site summary</h1>
            <p>
              Randomised babies born since the trial start. Every item comes from a fixed rule on the data in the
              portal; check the baby's forms before acting. Emailed Monday and Thursday at 08:00 IST (enrolment IDs
              only, no names); the urgent items of the safety watch list (serious AE not reviewed for SAE, severe
              brain scan not in Form H, death without an SAE report, SAE reporting deadline, converted to SAE with no
              report) also go in the daily 8 am email. Tap a number to go to its list.
              {data?.since && <> "Since last" means since {data.since}.</>}
            </p>
          </div>
        </div>

        <div className="ss-bar">
          {global ? (
            <label className="ss-field">
              <span>Site</span>
              <select value={site} onChange={e => setSite(e.target.value)}>
                <option value="">All sites</option>
                {SITE_ORDER.map(s => <option key={s} value={s}>{formatSiteName(s)}</option>)}
              </select>
            </label>
          ) : (
            <span className="ss-note">Site: {formatSiteName(user?.site_name)}</span>
          )}
          <button type="button" className="ss-btn" onClick={load} disabled={loading}>
            <RefreshCw size={14} aria-hidden="true" /> {loading ? "Loading…" : "Refresh"}
          </button>
        </div>

        {error && <div className="ss-error" role="alert">{error}</div>}

        {data && (
          <>
            <div className="ss-tiles">
              {tiles.map(([label, n, cls, to]) => (
                <button type="button" key={label} className={`ss-tile ${cls}`} onClick={() => jump(to)}
                  title={to.startsWith("/") ? "Open the data queries" : "Go to the list"}>
                  <div className="ss-tile-n">{n ?? 0}</div>
                  <div className="ss-tile-label">{label}</div>
                </button>
              ))}
            </div>

            {showSite && (
              <section className="ss-card">
                <h2>By site</h2>
                <div className="ss-table-wrap">
                  <table className="ss-table">
                    <thead><tr><th>Site</th><th>In NICU</th><th>Watch-list items</th><th>Missed items</th><th>Overdue queries</th></tr></thead>
                    <tbody>
                      {Object.entries(data.per_site || {}).map(([s, p]) => (
                        <tr key={s}><td>{formatSiteName(s)}</td><td>{p.in_nicu}</td><td>{p.watch}</td><td>{p.missed}</td><td>{p.red_queries}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            <section className="ss-card ss-card-red" id="ss-watch">
              <h2>Safety watch list: close to an SAE ({watch.length})</h2>
              <RuleTable items={watch} showSite={showSite} />
            </section>

            <section className="ss-card" id="ss-advisory">
              <h2>Advisory: AE grades to review ({advisory.length})</h2>
              <RuleTable items={advisory} showSite={showSite} />
            </section>

            <section className="ss-card" id="ss-active">
              <h2>Active morbidities, babies in the NICU ({active.length})</h2>
              {active.length ? (
                <div className="ss-table-wrap">
                  <table className="ss-table">
                    <thead><tr>{showSite && <th>Site</th>}<th>Baby</th><th>Age</th><th>Active</th></tr></thead>
                    <tbody>
                      {active.map(b => (
                        <tr key={b.enrollment_id}>
                          {showSite && <td>{formatSiteName(b.site)}</td>}
                          <td><Baby id={b.enrollment_id} name={b.name} /></td>
                          <td>DOL {b.dol} · {b.pma}</td>
                          <td>{b.active.join("; ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <p className="ss-none">None.</p>}
            </section>

            <section className="ss-card" id="ss-missed">
              <h2>Missed data collection ({missed.length})</h2>
              <RuleTable items={missed} showSite={showSite} />
            </section>

            <section className="ss-card" id="ss-census">
              <h2>Census: in the NICU or stay ended since last ({census.length})</h2>
              {census.length ? (
                <div className="ss-table-wrap">
                  <table className="ss-table">
                    <thead><tr>{showSite && <th>Site</th>}<th>Baby</th><th>Age</th><th>Status</th></tr></thead>
                    <tbody>
                      {census.map(b => (
                        <tr key={b.enrollment_id}>
                          {showSite && <td>{formatSiteName(b.site)}</td>}
                          <td><Baby id={b.enrollment_id} name={b.name} /></td>
                          <td>DOL {b.dol} · {b.pma}</td>
                          <td>{b.status}{b.ended_on ? ` (${b.ended_on})` : ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <p className="ss-none">None.</p>}
            </section>
          </>
        )}
      </div>
    </DashboardWorkspaceLayout>
  );
}
