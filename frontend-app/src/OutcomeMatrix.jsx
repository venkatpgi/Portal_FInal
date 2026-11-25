// Outcome matrix (PI 2026-11-26): one row per randomised baby; every Form I
// outcome as a column in the order it happens (at birth -> first week -> 28
// days / stay -> 36 -> 40 -> 44 wk PMA -> overall and composites), plus a
// short "Key outcomes" view (backend/outcome_matrix.py, GET /outcome-matrix).
// Cells say the answer in words; colour only backs it up. Dashed = found in the
// data but not yet saved on Form I. Pooled, never by arm. PI and scientists.
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

const LEGEND = [
  ["yes", "Yes / done (date)"], ["no", "No"], ["val", "Number (days / seconds)"], ["pending", "Due later"],
  ["overdue", "Overdue / not entered"], ["na", "— not applicable"],
];
const FORM_OF = { k_mri: "form-k" };   // everything else is on Form I

export default function OutcomeMatrix() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const allowed = canUseReports(user);
  const global = isGlobalUser(user);
  const [site, setSite] = useState("");
  const [section, setSection] = useState("all");
  const [only, setOnly] = useState("all");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!allowed) return;
    setData(null);
    setError("");
    api.get("/outcome-matrix", { params: global && site ? { site } : {} })
      .then((res) => setData(res.data))
      .catch((e) => setError(e?.response?.data?.detail || "Could not load the outcome matrix."));
  }, [allowed, global, site]);

  // "all" = every Form I section in time order (the key summary is its own view)
  const cols = useMemo(() => {
    const all = data?.columns || [];
    return section === "all" ? all.filter((c) => c.section !== "key") : all.filter((c) => c.section === section);
  }, [data, section]);

  const groups = useMemo(() => {
    const out = [];
    cols.forEach((c) => {
      const last = out[out.length - 1];
      if (last && last.key === c.section) last.span += 1;
      else out.push({ key: c.section, span: 1, label: (data?.sections || []).find((s) => s.key === c.section)?.label });
    });
    return out;
  }, [cols, data]);

  const rows = useMemo(() => {
    const all = data?.rows || [];
    const keys = new Set(cols.map((c) => c.key));
    const has = (r, test) => Object.entries(r.cells).some(([k, c]) => keys.has(k) && test(c));
    if (only === "overdue") return all.filter((r) => has(r, (c) => c.state === "overdue"));
    if (only === "detected") return all.filter((r) => has(r, (c) => c.source === "detected"));
    if (only === "pending") return all.filter((r) => has(r, (c) => c.state === "pending"));
    return all;
  }, [data, only, cols]);

  if (!allowed) {
    return (
      <DashboardWorkspaceLayout pageTitle="Outcome matrix">
        <div className="ss-root ss-none">The outcome matrix is for the Global PI, Project Scientist, Site PIs and Site Scientists.</div>
      </DashboardWorkspaceLayout>
    );
  }

  const showSite = global && !site;
  return (
    <DashboardWorkspaceLayout pageTitle="Outcome matrix">
      <div className="ss-root">
        <div className="ss-hero">
          <div className="ss-hero-icon" aria-hidden="true"><Grid3X3 size={20} /></div>
          <div>
            <h1>Outcome matrix</h1>
            <p>
              Every randomised baby against every Form I outcome, in the order they happen: at birth, first week,
              up to 28 days, 36, 40 and 44 weeks PMA, then overall and the composites. Form I first; where Form I
              is blank, what the forms and daily logs show (dashed: not yet saved on Form I). All arms together,
              never by arm. Tap a cell to open the form. PDF / CSV: Reports → Outcome matrix.
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
            <span>Outcomes</span>
            <select value={section} onChange={(e) => setSection(e.target.value)}>
              <option value="all">All Form I outcomes, in time order</option>
              {(data?.sections || []).map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </label>
          <label className="ss-field">
            <span>Babies</span>
            <select value={only} onChange={(e) => setOnly(e.target.value)}>
              <option value="all">All babies</option>
              <option value="overdue">With something overdue / not entered</option>
              <option value="pending">With something still due</option>
              <option value="detected">With an answer not yet saved on Form I</option>
            </select>
          </label>
        </div>

        <div className="omx-legend">
          {LEGEND.map(([k, label]) => <span key={k} className={`omx-cell omx-${k}`}>{label}</span>)}
          <span className="omx-cell omx-yes omx-detected">Dashed = not yet saved on Form I</span>
        </div>

        {error && <p className="ss-none">{error}</p>}
        {!data && !error && <p className="ss-none">Loading… (works out every outcome for every baby; may take a minute)</p>}
        {data && (
          <div className="omx-wrap">
            <table className="omx-table">
              <thead>
                {groups.length > 1 && (
                  <tr className="omx-groups">
                    <th className="omx-sticky" />
                    {showSite && <th />}
                    <th /><th />
                    {groups.map((g, i) => <th key={`${g.key}-${i}`} colSpan={g.span}>{g.label}</th>)}
                  </tr>
                )}
                <tr>
                  <th className="omx-sticky">Baby</th>
                  {showSite && <th>Site</th>}
                  <th>GA</th><th>Now</th>
                  {cols.map((c) => <th key={c.key}>{c.label}</th>)}
                </tr>
                <tr className="omx-totals">
                  <th className="omx-sticky">All {data.rows.length} babies</th>
                  {showSite && <th />}
                  <th /><th />
                  {cols.map((c) => <th key={c.key}>{data.totals_text?.[c.key] || ""}</th>)}
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
                            title={[cell.note, cell.source === "detected" ? "Not yet saved on Form I" : ""]
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
