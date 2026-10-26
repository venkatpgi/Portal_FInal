// Site summary (PI 2026-10-26): the Monday / Thursday email, live. Randomised
// babies by enrolment ID, with the name when the server sends one (viewer may
// see that site's PII; the email stays IDs only) -- watch list (close to an
// SAE), active morbidities, missed data collection. Rules are fixed in
// backend/site_summary.py; their W / M codes are not shown. Nothing here is
// shown or grouped by arm.
// Global PI + Project Scientist: any or all sites; Site PI / Site Scientist:
// own site.
import React, { useEffect, useMemo, useState } from "react";
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
  const [site, setSite] = useState("");
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
  const babies = data?.babies || [];
  const watch = useMemo(() => babies.flatMap(b => b.watch.map(w => ({ ...w, site: b.site, enrollment_id: b.enrollment_id, name: b.name }))), [babies]);
  const missed = useMemo(() => [
    ...babies.flatMap(b => b.missed.map(m => ({ ...m, site: b.site, enrollment_id: b.enrollment_id, name: b.name }))),
    ...(data?.mothers || []),
  ], [babies, data]);
  const active = babies.filter(b => b.status === "In NICU" && b.active.length);
  const census = babies.filter(b => b.status === "In NICU" || b.ended_since_last);
  const c = data?.counts || {};

  if (!allowed) {
    return (
      <DashboardWorkspaceLayout pageTitle="Site summary">
        <div className="ss-root ss-none">The site summary is for the Global PI, Project Scientist, Site PIs and Site Scientists.</div>
      </DashboardWorkspaceLayout>
    );
  }

  const tiles = [
    ["In NICU", c.in_nicu, "ss-t-dark"], ["Stays ended since last", c.ended_since_last, "ss-t-grey"],
    ["Babies on watch list", c.watch_babies, "ss-t-red"], ["With active morbidity", c.active_babies, "ss-t-amber"],
    ["Missed data items", c.missed, "ss-t-violet"], ["Overdue queries", c.red_queries, "ss-t-blue"],
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
              only, no names); the urgent items (serious AE not reviewed for SAE, severe brain scan not in Form H,
              death without an SAE report, SAE reporting deadline) also go in the daily 8 am email.
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
              {tiles.map(([label, n, cls]) => (
                <div key={label} className={`ss-tile ${cls}`}>
                  <div className="ss-tile-n">{n ?? 0}</div>
                  <div className="ss-tile-label">{label}</div>
                </div>
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

            <section className="ss-card ss-card-red">
              <h2>Watch list: close to an SAE ({watch.length})</h2>
              <RuleTable items={watch} showSite={showSite} />
            </section>

            <section className="ss-card">
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

            <section className="ss-card">
              <h2>Missed data collection ({missed.length})</h2>
              <RuleTable items={missed} showSite={showSite} />
            </section>

            <section className="ss-card">
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
