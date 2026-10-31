// Twice-daily report (PI 2026-10-31): any site staff member generates it and
// shares the PDF to the site's WhatsApp group. Enrolment ID, area admitted,
// morbidities till date; randomised babies only, IDs only, nothing by arm
// (backend/shift_report.py). Global PI and central scientists pick a site.
import React, { useState } from "react";
import { ClipboardCheck, Download, Share2 } from "lucide-react";
import api from "./api/axios";
import { useAuth } from "./context/AuthContext";
import DashboardWorkspaceLayout from "./components/dashboard/DashboardWorkspaceLayout";
import { canUseShiftReport, isGlobalUser } from "./utils/roles";
import { SITE_ORDER } from "./utils/siteNames";
import { formatSiteName } from "./components/dashboard/siteLabels";
import "./SiteSummary.css";

function saveFile(file) {
  const url = window.URL.createObjectURL(file);
  const a = document.createElement("a");
  a.href = url;
  a.download = file.name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export default function ShiftReport() {
  const { user } = useAuth();
  const allowed = canUseShiftReport(user);
  const global = isGlobalUser(user);
  const [site, setSite] = useState("");
  const [report, setReport] = useState(null);
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const params = global ? { site } : {};
      const [json, pdf] = await Promise.all([
        api.get("/shift-report", { params }),
        api.get("/shift-report/pdf", { params, responseType: "blob" }),
      ]);
      const m = (pdf.headers?.["content-disposition"] || "").match(/filename="?([^"]+)"?/);
      setReport(json.data);
      setFile(new File([pdf.data], (m && m[1]) || "PORTAL_report.pdf", { type: "application/pdf" }));
    } catch (err) {
      const d = err?.response?.data?.detail;
      setError(typeof d === "string" ? d : "Could not generate the report. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const share = async () => {
    setNotice("");
    // Tablets and phones open the share sheet (WhatsApp is on it). Desktop
    // browsers cannot hand a file to WhatsApp, so the PDF is saved instead.
    if (navigator.canShare?.({ files: [file] })) {
      try {
        await navigator.share({ files: [file], title: "PORTAL twice-daily report" });
      } catch (err) {
        if (err?.name !== "AbortError") setError("Could not open sharing. Use Download.");
      }
      return;
    }
    saveFile(file);
    setNotice("Saved. Attach this PDF in the site's WhatsApp group.");
  };

  if (!allowed) {
    return (
      <DashboardWorkspaceLayout pageTitle="Twice-daily report">
        <div className="ss-root ss-none">The twice-daily report is for site staff.</div>
      </DashboardWorkspaceLayout>
    );
  }

  return (
    <DashboardWorkspaceLayout pageTitle="Twice-daily report">
      <div className="ss-root">
        <div className="ss-hero">
          <div className="ss-hero-icon" aria-hidden="true"><ClipboardCheck size={20} /></div>
          <div>
            <h1>Twice-daily report</h1>
            <p>
              Generate this in the morning and evening and share it to the site's WhatsApp group. Randomised babies
              still admitted or whose stay ended in the last 7 days. Enrolment IDs only: no names, and nothing by
              study arm.
            </p>
          </div>
        </div>

        <div className="ss-bar">
          {global ? (
            <label className="ss-field">
              <span>Site</span>
              <select value={site} onChange={e => { setSite(e.target.value); setReport(null); setFile(null); }}>
                <option value="">Pick a site</option>
                {SITE_ORDER.map(s => <option key={s} value={s}>{formatSiteName(s)}</option>)}
              </select>
            </label>
          ) : (
            <span className="ss-note">Site: {formatSiteName(user?.site_name)}</span>
          )}
          <button type="button" className="ss-btn" onClick={generate} disabled={loading || (global && !site)}>
            <ClipboardCheck size={14} aria-hidden="true" /> {loading ? "Generating…" : "Generate report"}
          </button>
          {file && (
            <>
              <button type="button" className="ss-btn" onClick={share}>
                <Share2 size={14} aria-hidden="true" /> Share on WhatsApp
              </button>
              <button type="button" className="ss-btn" onClick={() => saveFile(file)}>
                <Download size={14} aria-hidden="true" /> Download PDF
              </button>
            </>
          )}
        </div>

        {error && <div className="ss-error" role="alert">{error}</div>}
        {notice && <span className="ss-note" role="status">{notice}</span>}

        {report && (
          <section className="ss-card">
            <h2>{report.site_name}: {report.babies.length} {report.babies.length === 1 ? "baby" : "babies"}</h2>
            {report.babies.length ? (
              <div className="ss-table-wrap">
                <table className="ss-table">
                  <thead><tr><th>Enrollment ID</th><th>Area admitted</th><th>Morbidities till date</th></tr></thead>
                  <tbody>
                    {report.babies.map(b => (
                      <tr key={b.enrollment_id}>
                        <td><span className="ss-id">{b.enrollment_id}</span></td>
                        <td>{b.area}{b.area_day ? ` (Day ${b.area_day})` : ""}</td>
                        <td>{b.morbidity_text}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <p className="ss-none">Nil to report.</p>}
          </section>
        )}
      </div>
    </DashboardWorkspaceLayout>
  );
}
