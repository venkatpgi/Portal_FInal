// Suggested AEs not yet in the Adverse Events table (PI 2026-11-25). The portal
// suggests AEs from data already entered (daily-log values over a grade
// threshold, transfusions, Form D / Form H diagnoses); each one stays on the
// site summary "AE review" until a row with that term is added here, or the
// Site PI / a Site Scientist marks it "Not an AE" with a reason (audit-logged,
// can be undone). Backend: GET/POST /adverse-events/suggestions/{id}.
import React, { useCallback, useEffect, useState } from "react";
import api from "../api/axios";
import { useAuth } from "../context/AuthContext";

export default function AeSuggestions({ enrollmentId }) {
  const { user } = useAuth() || {};
  const role = (user?.role || "").toLowerCase();
  const canDecide = ["superadmin", "site_pi", "site_scientist", "project_scientist", "global_scientist"].includes(role);
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(null);       // term being dismissed
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    if (!enrollmentId) return;
    api.get(`/adverse-events/suggestions/${encodeURIComponent(enrollmentId)}`)
      .then((res) => setData(res.data))
      .catch(() => setData(null));
  }, [enrollmentId]);
  useEffect(() => { load(); }, [load]);

  const send = async (body) => {
    setMsg("");
    try {
      await api.post(`/adverse-events/suggestions/${encodeURIComponent(enrollmentId)}/dismiss`, body);
      setOpen(null);
      setReason("");
      load();
    } catch (err) {
      setMsg(err?.response?.data?.detail || "Could not save.");
    }
  };

  if (!data || (!data.pending.length && !data.dismissed.length)) return null;
  return (
    <div className="ae-sugg">
      <div className="ae-sugg-head">
        <strong>Suggested AEs not yet in the table below ({data.pending.length})</strong>
        <button type="button" className="ae-sugg-link" onClick={load}>Refresh</button>
      </div>
      <p className="ae-sugg-note">
        Found in data already entered for this baby. Add each one to the table (Scan daily logs adds it for
        you), or{canDecide ? "" : " ask the Site PI or a Site Scientist to"} mark it “Not an AE” with a reason.
        Until then it shows in the site summary under AE review.
      </p>
      {data.pending.map((p) => (
        <div className="ae-sugg-row" key={p.term}>
          <div>
            <strong>{p.description}</strong>{p.grade ? ` · grade ${p.grade}` : ""}
            {p.evidence && <div className="ae-sugg-ev">From: {p.evidence}</div>}
          </div>
          {canDecide && (open === p.term ? (
            <div className="ae-sugg-act">
              <input placeholder="Why it is not an AE" value={reason} onChange={(e) => setReason(e.target.value)} />
              <button type="button" className="ae-scan-btn" disabled={reason.trim().length < 5}
                onClick={() => send({ term: p.term, description: p.description, reason: reason.trim() })}>
                Save
              </button>
              <button type="button" className="ae-sugg-link" onClick={() => setOpen(null)}>Cancel</button>
            </div>
          ) : (
            <button type="button" className="ae-sugg-link" onClick={() => { setOpen(p.term); setReason(""); }}>
              Not an AE
            </button>
          ))}
        </div>
      ))}
      {data.dismissed.length > 0 && (
        <details className="ae-sugg-done">
          <summary>Marked “Not an AE” ({data.dismissed.length})</summary>
          {data.dismissed.map((d) => (
            <div className="ae-sugg-row" key={d.term}>
              <div>
                <strong>{d.description || d.term}</strong>: {d.reason}
                <div className="ae-sugg-ev">{d.by}{d.at ? `, ${String(d.at).slice(0, 10)}` : ""}</div>
              </div>
              {canDecide && (
                <button type="button" className="ae-sugg-link" onClick={() => send({ term: d.term, undo: true })}>
                  Undo
                </button>
              )}
            </div>
          ))}
        </details>
      )}
      {msg && <p className="ae-scan-msg">{msg}</p>}
    </div>
  );
}
