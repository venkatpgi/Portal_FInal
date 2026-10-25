// Report builder (PI 2026-10-24): pick columns from any form, filter, preview,
// download CSV. The server (backend/routers/reports.py) decides which columns
// exist -- never names, CR / UID numbers, phone, address or signatures, and
// nothing that could unblind. Global PI + Overall Project Scientist: all
// sites; Site PI / Site Scientist: own site. Downloads go to the audit trail.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Check, Download, Eye, FileSpreadsheet, Save, Search, Trash2, X } from "lucide-react";
import api from "./api/axios";
import { useAuth } from "./context/AuthContext";
import DashboardWorkspaceLayout from "./components/dashboard/DashboardWorkspaceLayout";
import { canUseReports, isGlobalUser } from "./utils/roles";
import { PARTICIPANT_TILES } from "./utils/participantCounts";
import { SITE_ORDER } from "./utils/siteNames";
import { formatSiteName } from "./components/dashboard/siteLabels";
import "./ReportBuilder.css";

const SAVED_KEY = "portal_saved_reports_v1";

function loadSaved() {
  try {
    const v = JSON.parse(localStorage.getItem(SAVED_KEY) || "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

function storeSaved(list) {
  try { localStorage.setItem(SAVED_KEY, JSON.stringify(list)); } catch { /* private window */ }
}

// Column search matches the English name or the variable name.
function fieldMatches(x, q) {
  return !q || x.label.toLowerCase().includes(q) || x.column.toLowerCase().includes(q);
}

function apiError(err, fallback) {
  const d = err?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
}

export default function ReportBuilder() {
  const { user } = useAuth();
  const allowed = canUseReports(user);
  const global = isGlobalUser(user);

  const [forms, setForms] = useState([]);
  const [trialStart, setTrialStart] = useState("");
  const [selected, setSelected] = useState([]);
  const [openForm, setOpenForm] = useState("A");
  const [fieldSearch, setFieldSearch] = useState("");
  const [filters, setFilters] = useState({
    site: "", group: "", screened_from: "", screened_to: "", trial_only: true, include_stage: true,
    headings: "both",
  });
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(loadSaved);

  useEffect(() => {
    if (!allowed) return;
    api.get("/reports/fields")
      .then(res => {
        setForms(res.data?.forms || []);
        setTrialStart(res.data?.trial_start_date || "");
      })
      .catch(err => setError(apiError(err, "Could not load the list of columns.")));
  }, [allowed]);

  const fieldById = useMemo(() => {
    const m = {};
    forms.forEach(f => f.fields.forEach(x => { m[x.id] = x; }));
    return m;
  }, [forms]);

  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const q = fieldSearch.trim().toLowerCase();

  const toggle = id => {
    setSelected(prev => (prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]));
    setPreview(null);
  };
  const setForm = (form, on) => {
    const ids = form.fields.filter(x => fieldMatches(x, q)).map(x => x.id);
    setSelected(prev => (on ? [...prev, ...ids.filter(id => !prev.includes(id))] : prev.filter(id => !ids.includes(id))));
    setPreview(null);
  };
  const setFilter = (k, v) => {
    setFilters(prev => ({ ...prev, [k]: v }));
    setPreview(null);
  };

  const body = useCallback(() => ({
    columns: selected,
    site: global ? (filters.site || null) : null,
    group: filters.group || null,
    screened_from: filters.screened_from || null,
    screened_to: filters.screened_to || null,
    trial_only: filters.trial_only,
    include_stage: filters.include_stage,
    headings: filters.headings || "both",
  }), [selected, filters, global]);

  const runPreview = async () => {
    setBusy("preview");
    setError("");
    try {
      const res = await api.post("/reports/preview", body());
      setPreview(res.data);
    } catch (err) {
      setError(apiError(err, "Preview failed."));
    } finally {
      setBusy("");
    }
  };

  const download = async () => {
    setBusy("csv");
    setError("");
    try {
      const res = await api.post("/reports/csv", body(), { responseType: "blob" });
      const cd = res.headers?.["content-disposition"] || "";
      const name = (cd.match(/filename="([^"]+)"/) || [])[1] || "portal_report.csv";
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      let msg = "Download failed.";
      try { msg = JSON.parse(await err.response.data.text()).detail || msg; } catch { /* not JSON */ }
      setError(msg);
    } finally {
      setBusy("");
    }
  };

  const saveCurrent = () => {
    const name = (window.prompt("Name for this report (saved in this browser only):") || "").trim();
    if (!name) return;
    const next = [...saved.filter(s => s.name !== name), { name, columns: selected, filters }];
    setSaved(next);
    storeSaved(next);
  };
  const applySaved = s => {
    setSelected((s.columns || []).filter(id => fieldById[id]));
    setFilters(prev => ({ ...prev, ...(s.filters || {}) }));
    setPreview(null);
  };
  const removeSaved = name => {
    const next = saved.filter(s => s.name !== name);
    setSaved(next);
    storeSaved(next);
  };

  if (!allowed) {
    return (
      <DashboardWorkspaceLayout pageTitle="Reports">
        <div className="rb-root rb-empty">Reports are for the Global PI, Project Scientist, Site PIs and Site Scientists.</div>
      </DashboardWorkspaceLayout>
    );
  }

  return (
    <DashboardWorkspaceLayout pageTitle="Reports">
      <div className="rb-root">
        <div className="rb-hero">
          <div className="rb-hero-icon" aria-hidden="true"><FileSpreadsheet size={20} /></div>
          <div>
            <h1>Report builder</h1>
            <p>
              One row per screened woman and her baby. Pick the columns you need from any form, filter, preview,
              then download a CSV (opens in Excel). Reports carry IDs only: no names, CR / UID numbers, phone
              numbers, addresses or signatures. Day-by-day logs are not included. Every download is recorded in
              the audit trail.
            </p>
          </div>
        </div>

        {error && <div className="rb-error" role="alert">{error}</div>}

        <div className="rb-grid">
          <section className="rb-card" aria-label="Rows">
            <h2>Rows</h2>
            {global ? (
              <label className="rb-field">
                <span>Site</span>
                <select value={filters.site} onChange={e => setFilter("site", e.target.value)}>
                  <option value="">All sites</option>
                  {SITE_ORDER.map(s => <option key={s} value={s}>{formatSiteName(s)}</option>)}
                </select>
              </label>
            ) : (
              <p className="rb-note">Site: {formatSiteName(user?.site_name)}</p>
            )}
            <label className="rb-field">
              <span>Who</span>
              <select value={filters.group} onChange={e => setFilter("group", e.target.value)}>
                <option value="">Everyone screened</option>
                {PARTICIPANT_TILES.filter(t => t.key !== "screened").map(t => (
                  <option key={t.key} value={t.key}>{t.label}</option>
                ))}
              </select>
            </label>
            <div className="rb-dates">
              <label className="rb-field">
                <span>Screened from</span>
                <input type="date" value={filters.screened_from} onChange={e => setFilter("screened_from", e.target.value)} />
              </label>
              <label className="rb-field">
                <span>to</span>
                <input type="date" value={filters.screened_to} onChange={e => setFilter("screened_to", e.target.value)} />
              </label>
            </div>
            <label className="rb-check">
              <input type="checkbox" checked={filters.trial_only} onChange={e => setFilter("trial_only", e.target.checked)} />
              Trial period only{trialStart ? ` (screened from ${trialStart})` : ""}
            </label>
            <label className="rb-check">
              <input type="checkbox" checked={filters.include_stage} onChange={e => setFilter("include_stage", e.target.checked)} />
              Add a Stage column
            </label>
            <label className="rb-field rb-field-gap">
              <span>CSV column headings</span>
              <select value={filters.headings} onChange={e => setFilter("headings", e.target.value)}>
                <option value="both">English (variable name)</option>
                <option value="english">English only</option>
                <option value="variable">Variable names only (for Stata / R / SPSS)</option>
              </select>
            </label>

            <h2 className="rb-h2-gap">Saved reports</h2>
            {saved.length === 0 ? (
              <p className="rb-note">None yet. Pick columns, then “Save”. Saved in this browser only.</p>
            ) : (
              <ul className="rb-saved">
                {saved.map(s => (
                  <li key={s.name}>
                    <button type="button" className="rb-link" onClick={() => applySaved(s)}>{s.name}</button>
                    <span className="rb-muted">{(s.columns || []).length} cols</span>
                    <button type="button" className="rb-icon" onClick={() => removeSaved(s.name)} aria-label={`Delete saved report ${s.name}`}>
                      <Trash2 size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="rb-card" aria-label="Columns">
            <div className="rb-cols-head">
              <h2>Columns <span className="rb-muted">({selected.length} picked)</span></h2>
              <div className="rb-search">
                <Search size={14} aria-hidden="true" />
                <input
                  placeholder="Find a column, e.g. birth weight"
                  value={fieldSearch}
                  onChange={e => setFieldSearch(e.target.value)}
                  aria-label="Find a column"
                />
              </div>
            </div>
            <p className="rb-note">
              Every report starts with site, screening ID and enrollment (randomisation) number. Click a column to
              pick it; click again to remove it. The variable name is shown in brackets.
            </p>
            {selected.length > 0 && (
              <div className="rb-picked" aria-label="Picked columns">
                {selected.map(id => fieldById[id] && (
                  <button key={id} type="button" className="rb-chip" onClick={() => toggle(id)} title={`Remove ${fieldById[id].label}`}>
                    <span className="rb-chip-form">{id.split(".")[0]}</span>
                    {fieldById[id].label}
                    <X size={12} aria-hidden="true" />
                  </button>
                ))}
              </div>
            )}
            <div className="rb-forms">
              {forms.map(form => {
                const shown = form.fields.filter(x => fieldMatches(x, q));
                const picked = form.fields.filter(x => selectedSet.has(x.id)).length;
                const open = q ? shown.length > 0 : openForm === form.form;
                if (q && shown.length === 0) return null;
                return (
                  <div key={form.form} className={`rb-form${open ? " rb-form--open" : ""}`}>
                    <button type="button" className="rb-form-head" onClick={() => setOpenForm(open && !q ? "" : form.form)} aria-expanded={open}>
                      <span>{form.label}</span>
                      <span className="rb-muted">{picked ? `${picked} / ` : ""}{form.fields.length}</span>
                    </button>
                    {open && (
                      <div className="rb-form-body">
                        <div className="rb-form-actions">
                          <button type="button" className="rb-link" onClick={() => setForm(form, true)}>Select {q ? "matching" : "all"}</button>
                          <button type="button" className="rb-link" onClick={() => setForm(form, false)}>Clear</button>
                        </div>
                        <div className="rb-fields">
                          {shown.map(x => {
                            const on = selectedSet.has(x.id);
                            return (
                              <button
                                key={x.id}
                                type="button"
                                className={`rb-fieldbtn${on ? " rb-fieldbtn--on" : ""}`}
                                aria-pressed={on}
                                onClick={() => toggle(x.id)}
                                title={`${x.label} (${x.header}, ${x.kind})`}
                              >
                                <span className="rb-tick" aria-hidden="true">{on && <Check size={12} strokeWidth={3} />}</span>
                                <span className="rb-fieldtext">
                                  <span className="rb-fieldlabel">{x.label}</span>
                                  <span className="rb-fieldcode">({x.column})</span>
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        </div>

        <div className="rb-actions">
          <button type="button" className="rb-btn" onClick={runPreview} disabled={!selected.length || !!busy}>
            <Eye size={15} /> {busy === "preview" ? "Loading…" : "Preview"}
          </button>
          <button type="button" className="rb-btn rb-btn--primary" onClick={download} disabled={!selected.length || !!busy}>
            <Download size={15} /> {busy === "csv" ? "Preparing…" : "Download CSV"}
          </button>
          <button type="button" className="rb-btn" onClick={saveCurrent} disabled={!selected.length}>
            <Save size={15} /> Save
          </button>
          {selected.length > 0 && (
            <button type="button" className="rb-link" onClick={() => { setSelected([]); setPreview(null); }}>Clear all columns</button>
          )}
        </div>

        {preview && (
          <section className="rb-card" aria-label="Preview">
            <h2>Preview <span className="rb-muted">— {preview.total} row{preview.total === 1 ? "" : "s"}{preview.total > preview.rows.length ? `, first ${preview.rows.length} shown` : ""}</span></h2>
            <div className="rb-table-wrap">
              <table className="rb-table">
                <thead>
                  <tr>
                    {preview.headers.map((h, i) => (
                      <th key={h}>
                        {(preview.labels || [])[i] || h}
                        <span className="rb-th-code">{h}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.length === 0 ? (
                    <tr><td colSpan={preview.headers.length} className="rb-muted">No one matches these filters.</td></tr>
                  ) : preview.rows.map((r, i) => (
                    <tr key={i}>{r.map((c, j) => <td key={j}>{String(c)}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </DashboardWorkspaceLayout>
  );
}
