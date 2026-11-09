// Ready-made reports (PI 2026-11-06): one click, preview on the page or
// download as PDF / CSV. Built by backend/ready_reports.py; the page only
// draws what the server sends (tables, and bar charts as plain CSS bars).
import React, { useEffect, useState } from "react";
import { Download, Eye, FileText } from "lucide-react";
import api from "../api/axios";
import { SITE_ORDER } from "../utils/siteNames";
import { formatSiteName } from "./dashboard/siteLabels";

const COLOURS = ["#1d4ed8", "#0f766e", "#b45309", "#7c3aed", "#be123c", "#15803d"];

function apiError(err, fallback) {
  const d = err?.response?.data?.detail;
  return typeof d === "string" ? d : fallback;
}

function Bars({ chart }) {
  const top = Math.max(1, ...chart.series.flatMap(s => s.values));
  const max = chart.unit === "%" && top <= 100 ? 100 : top;
  return (
    <figure className="rr-chart">
      <figcaption>{chart.title}</figcaption>
      {chart.series.length > 1 && (
        <div className="rr-legend">
          {chart.series.map((s, i) => (
            <span key={s.name}><i style={{ background: COLOURS[i % COLOURS.length] }} />{s.name}</span>
          ))}
        </div>
      )}
      {chart.labels.map((label, li) => (
        <div key={label} className="rr-bar-row">
          <span className="rr-bar-label" title={label}>{label}</span>
          <span className="rr-bar-set">
            {chart.series.map((s, si) => {
              const v = s.values[li] || 0;
              return (
                <span key={s.name} className="rr-bar-line">
                  <span className="rr-bar" style={{ width: `${(100 * v) / max}%`, background: COLOURS[si % COLOURS.length] }} />
                  <span className="rr-bar-value">{chart.unit === "%" ? `${v}%` : v}</span>
                </span>
              );
            })}
          </span>
        </div>
      ))}
    </figure>
  );
}

export default function ReadyReports({ global, userSite }) {
  const [list, setList] = useState([]);
  const [site, setSite] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [shown, setShown] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/reports/ready").then(res => setList(res.data || [])).catch(() => setList([]));
  }, []);

  // PI 2026-11-09: the IEC / DSMB summary goes monthly; one click sets the last calendar month.
  const lastMonth = () => {
    const now = new Date();
    const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const last = new Date(now.getFullYear(), now.getMonth(), 0);
    const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    setFrom(iso(first));
    setTo(iso(last));
    setShown(null);
  };

  const params = () => ({
    ...(global && site ? { site } : {}),
    ...(from ? { date_from: from } : {}),
    ...(to ? { date_to: to } : {}),
  });

  const preview = async key => {
    setBusy(`${key}:view`);
    setError("");
    try {
      const res = await api.get(`/reports/ready/${key}`, { params: params() });
      setShown(res.data);
    } catch (err) {
      setError(apiError(err, "Could not build the report."));
    } finally {
      setBusy("");
    }
  };

  const download = async (key, format) => {
    setBusy(`${key}:${format}`);
    setError("");
    try {
      const res = await api.get(`/reports/ready/${key}/download`, { params: { ...params(), format }, responseType: "blob" });
      const cd = res.headers?.["content-disposition"] || "";
      const name = (cd.match(/filename="([^"]+)"/) || [])[1] || `portal_${key}.${format}`;
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

  return (
    <section className="rb-card rr-root" aria-label="Ready-made reports">
      <h2>Ready-made reports</h2>
      <p className="rb-note">
        One click: preview here, or download a PDF (tables and charts) or CSV (opens in Excel). IDs only, nothing by
        study arm. Every download is recorded in the audit trail.
      </p>
      <div className="rr-filters">
        {global ? (
          <label className="rb-field">
            <span>Site</span>
            <select value={site} onChange={e => { setSite(e.target.value); setShown(null); }}>
              <option value="">All sites (with comparison)</option>
              {SITE_ORDER.map(s => <option key={s} value={s}>{formatSiteName(s)}</option>)}
            </select>
          </label>
        ) : <p className="rb-note">Site: {formatSiteName(userSite)}</p>}
        <label className="rb-field">
          <span>From</span>
          <input type="date" value={from} onChange={e => { setFrom(e.target.value); setShown(null); }} />
        </label>
        <label className="rb-field">
          <span>to</span>
          <input type="date" value={to} onChange={e => { setTo(e.target.value); setShown(null); }} />
        </label>
        <button type="button" className="rb-btn" onClick={lastMonth}>Last month</button>
      </div>
      <p className="rb-note">
        Dates are the screening date, except the AE summary, where they are the AE start date (it also shows
        everything up to the end date).
      </p>
      {error && <div className="rb-error" role="alert">{error}</div>}
      <div className="rr-cards">
        {list.map(r => (
          <div key={r.key} className={`rr-card${shown?.key === r.key ? " rr-card--on" : ""}`}>
            <strong><FileText size={14} aria-hidden="true" /> {r.title}</strong>
            <span className="rb-note">{r.description}</span>
            <div className="rr-card-actions">
              <button type="button" className="rb-btn" onClick={() => preview(r.key)} disabled={!!busy}>
                <Eye size={14} /> {busy === `${r.key}:view` ? "Building…" : "Preview"}
              </button>
              <button type="button" className="rb-btn rb-btn--primary" onClick={() => download(r.key, "pdf")} disabled={!!busy}>
                <Download size={14} /> {busy === `${r.key}:pdf` ? "Preparing…" : "PDF"}
              </button>
              <button type="button" className="rb-btn" onClick={() => download(r.key, "csv")} disabled={!!busy}>
                <Download size={14} /> {busy === `${r.key}:csv` ? "Preparing…" : "CSV"}
              </button>
            </div>
          </div>
        ))}
      </div>
      {shown && (
        <div className="rr-report" aria-label={shown.title}>
          <h3>{shown.title} <span className="rb-muted">— {shown.scope} · {shown.generated_at}</span></h3>
          {shown.sections.map(sec => (
            <div key={sec.title} className="rr-section">
              <h4>{sec.title}</h4>
              {sec.note && <p className="rb-note">{sec.note}</p>}
              {sec.chart && sec.chart.labels.length > 0 && <Bars chart={sec.chart} />}
              <div className="rb-table-wrap">
                <table className="rb-table">
                  <thead><tr>{sec.columns.map(c => <th key={c}>{c}</th>)}</tr></thead>
                  <tbody>
                    {sec.rows.length === 0
                      ? <tr><td colSpan={sec.columns.length} className="rb-muted">None.</td></tr>
                      : sec.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{String(c)}</td>)}</tr>)}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
