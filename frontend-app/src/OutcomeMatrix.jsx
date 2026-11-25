// Outcome matrix (PI 2026-11-26): one row per randomised baby, one column per
// protocol outcome (backend/outcome_matrix.py, GET /outcome-matrix). Colour =
// state (occurred with date / No / due / overdue / not applicable); a dashed
// outline = found in the daily logs, Form H, Form F or Form J but not yet on
// Form I. Pooled, never by arm. Global PI, Project Scientist, Site PIs and
// Site Scientists (own site), like Reports.
import React, { useEffect, useMemo, useState } from "react";
import { Grid3X3 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import api from "./api/axios";
import { useAuth } from "./context/AuthContext";
import DashboardWorkspaceLayout from "./components/dashboard/DashboardWorkspaceLayout";
import { canUseReports, isGlobalUser } from "./utils/roles";
import { SITE_ORDER } from "./utils/siteNames";
import { formatSiteName } from "./components/dashboard/siteLabels";
import "./SiteSummary.css";

const STATE_LABEL = { yes: "Occurred / done", no: "No", pending: "Due", overdue: "Overdue", na: "Not applicable" };
const FORM_OF = { mri: "form-k" };   // everything else is recorded on Form I

export default function OutcomeMatrix() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const allowed = canUseReports(user);
  const global = isGlobalUser(user);
  const [site, setSite] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [only, setOnly] = useState("all");

  useEffect(() => {
    if (!allowed) return;
    setData(null);
    setError("");
    api.get("/outcome-matrix", { params: global && site ? { site } : {} })
      .then((res) => setData(res.data))
      .catch((e) => setError(e?.response?.data?.detail || "Could not load the outcome matrix."));
  }, [allowed, global, site]);

  const rows = useMemo(() => {
    const all = data?.rows || [];
    if (only === "overdue") return all.filter((r) => Object.values(r.cells).some((c) => c.state === "overdue"));
    if (only === "detected") return all.filter((r) => Object.values(r.cells).some((c) => c.source === "detected"));
    if (only === "pending") return all.filter((r) => Object.values(r.cells).some((c) => c.state === "pending"));
    return all;
  }, [data, only]);

  if (!allowed) {
    return (
      <DashboardWorkspaceLayout pageTitle="Outcome matrix">
        <div className="ss-root ss-none">The outcome matrix is for the Global PI, Project Scientist, Site PIs and Site Scientists.</div>
      </DashboardWorkspaceLayout>
    );
  }

  const cols = data?.columns || [];
  const showSite = global && !site;
  return (
    <DashboardWorkspaceLayout pageTitle="Outcome matrix">
      <div className="ss-root">
        <div className="ss-hero">
          <div className="ss-hero-icon" aria-hidden="true"><Grid3X3 size={20} /></div>
          <div>
            <h1>Outcome matrix</h1>
            <p>
              Every randomised baby against every protocol outcome. Form I first; where Form I is blank, what the
              daily logs, Form H, Form F or Form J show (dashed outline: not yet on Form I). Due = the checkpoint
              date; overdue = 2 days after it with nothing known. All arms together, never by arm. Tap a cell to
              open the form. PDF / CSV: Reports → Outcome matrix.
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
            <span>Show</span>
            <select value={only} onChange={(e) => setOnly(e.target.value)}>
              <option value="all">All babies</option>
              <option value="overdue">Babies with something overdue</option>
              <option value="pending">Babies with something still due</option>
              <option value="detected">Babies with an outcome not yet on Form I</option>
            </select>
          </label>
        </div>

        <div className="omx-legend">
          {Object.entries(STATE_LABEL).map(([k, label]) => (
            <span key={k} className={`omx-cell omx-${k}`}>{label}</span>
          ))}
          <span className="omx-cell omx-yes omx-detected">Dashed: not yet on Form I</span>
        </div>

        {error && <p className="ss-none">{error}</p>}
        {!data && !error && <p className="ss-none">Loading… (works out every outcome for every baby)</p>}
        {data && (
          <div className="omx-wrap">
            <table className="omx-table">
              <thead>
                <tr>
                  <th className="omx-sticky">Baby</th>
                  {showSite && <th>Site</th>}
                  <th>GA</th><th>Now</th>
                  {cols.map((c) => <th key={c.key}>{c.label}</th>)}
                </tr>
                <tr className="omx-totals">
                  <th className="omx-sticky">Totals ({data.rows.length})</th>
                  {showSite && <th />}
                  <th /><th />
                  {cols.map((c) => {
                    const t = data.totals[c.key] || {};
                    return (
                      <th key={c.key}>
                        <span className="omx-n omx-yes">{t.yes}</span>
                        <span className="omx-n omx-no">{t.no}</span>
                        <span className="omx-n omx-pending">{t.pending}</span>
                        {t.overdue ? <span className="omx-n omx-overdue">{t.overdue}</span> : null}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.enrollment_id}>
                    <td className="omx-sticky">
                      <span className="ss-id">{r.enrollment_id}</span>
                      {r.name ? <div className="ss-name">{r.name}</div> : null}
                    </td>
                    {showSite && <td>{formatSiteName(r.site)}</td>}
                    <td>{r.ga}</td>
                    <td>{r.status}</td>
                    {cols.map((c) => {
                      const cell = r.cells[c.key] || {};
                      return (
                        <td key={c.key}>
                          <button type="button"
                            className={`omx-cell omx-${cell.state}${cell.source === "detected" ? " omx-detected" : ""}`}
                            title={[cell.note, cell.source === "detected" ? "Not yet on Form I" : ""]
                              .filter(Boolean).join(" · ")}
                            onClick={() => navigate(`/${FORM_OF[c.key] || "form-i"}/${r.enrollment_id}`)}>
                            {cell.text}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <p className="ss-none">No babies in this view.</p>}
          </div>
        )}
      </div>
    </DashboardWorkspaceLayout>
  );
}
