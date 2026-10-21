// Form A · A6 Pregnancy follow-up (PI 2026-10-20).
// For a consented woman not yet delivered: discharges home undelivered and
// readmissions, the final pregnancy outcome, and consent withdrawn by the
// woman herself. Consent otherwise stands for every admission of this
// pregnancy, so a readmitted woman keeps her one Form A. Saved on its own
// (PATCH /screenings/{id}/pregnancy-follow-up), so Form A does not need to
// be unlocked. Rules: backend/pregnancy_followup.py.
import React, { useEffect, useState } from "react";
import { CalendarClock } from "lucide-react";
import api from "../api/axios";
import { useAuth } from "../context/AuthContext";
import { isReadOnlyUser } from "../utils/roles";

const OUTCOMES = ["Delivered here", "Delivered elsewhere", "Lost to follow-up"];

const ymd = (v) => (v ? String(v).slice(0, 10) : "");
const todayYmd = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export default function PregnancyFollowUp({ screeningId }) {
  const { user } = useAuth();
  const readOnly = isReadOnlyUser(user);
  const [episodes, setEpisodes] = useState([]);
  const [outcome, setOutcome] = useState("");
  const [outcomeDate, setOutcomeDate] = useState("");
  const [withdrawn, setWithdrawn] = useState(false);
  const [withdrawnDate, setWithdrawnDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const load = (d) => {
    setEpisodes((d.pregnancy_episodes || []).map(e => ({ discharged: ymd(e.discharged), readmitted: ymd(e.readmitted) })));
    setOutcome(d.pregnancy_outcome || "");
    setOutcomeDate(ymd(d.pregnancy_outcome_date));
    setWithdrawn(!!d.consent_withdrawn);
    setWithdrawnDate(ymd(d.consent_withdrawn_date));
  };

  useEffect(() => {
    if (!screeningId) return;
    api.get(`/screenings/${screeningId}`).then(r => load(r.data || {})).catch(() => {});
  }, [screeningId]);

  const setEp = (i, key, value) =>
    setEpisodes(prev => prev.map((e, j) => (j === i ? { ...e, [key]: value } : e)));

  const save = async () => {
    setSaving(true);
    setMessage("");
    try {
      const r = await api.patch(`/screenings/${screeningId}/pregnancy-follow-up`, {
        pregnancy_episodes: episodes
          .filter(e => e.discharged || e.readmitted)
          .map(e => ({ discharged: e.discharged || null, readmitted: e.readmitted || null })),
        pregnancy_outcome: outcome || null,
        pregnancy_outcome_date: outcome ? outcomeDate || null : null,
        consent_withdrawn: withdrawn,
        consent_withdrawn_date: withdrawn ? withdrawnDate || null : null,
      });
      load(r.data || {});
      setMessage("✅ Pregnancy follow-up saved");
    } catch (err) {
      const d = err.response?.data?.detail;
      setMessage(`❌ ${typeof d === "string" ? d : "Could not save. Check the dates and try again."}`);
    } finally {
      setSaving(false);
    }
  };

  const max = todayYmd();
  const last = episodes[episodes.length - 1];
  const canAddEpisode = !last || !!last.readmitted;

  return (
    <div className="form-section card-section">
      <div className="form-section-header">
        <div className="section-title-left">
          <CalendarClock size={15} className="section-header-icon" />
          <h3>A6 · Pregnancy follow-up (until delivery)</h3>
        </div>
      </div>
      <div className="form-section-body">
        <p style={{ margin: "0 0 12px", fontSize: 13, color: "#64748b" }}>
          Her consent stands for every admission of this pregnancy. If she is sent home undelivered and
          readmitted, record it here; do not fill a new Form A. In the Gestation Log, add her again with
          "New contact of the same woman". This section can be saved without unlocking Form A.
        </p>

        <label className="followup-label">Sent home undelivered / readmitted</label>
        {episodes.length === 0 && (
          <p style={{ margin: "4px 0 8px", fontSize: 13 }}>Not sent home undelivered so far.</p>
        )}
        {episodes.map((e, i) => (
          <div className="form-grid-2" key={i}>
            <div className="form-group">
              <label>Discharged home undelivered on</label>
              <input type="date" value={e.discharged} max={max} disabled={readOnly}
                onChange={ev => setEp(i, "discharged", ev.target.value)} />
            </div>
            <div className="form-group">
              <label>Readmitted on (blank if not yet)</label>
              <div style={{ display: "flex", gap: 8 }}>
                <input type="date" value={e.readmitted} min={e.discharged || undefined} max={max} disabled={readOnly}
                  onChange={ev => setEp(i, "readmitted", ev.target.value)} />
                {!readOnly && (
                  <button type="button" className="btn btn-secondary"
                    onClick={() => setEpisodes(prev => prev.filter((_, j) => j !== i))}>Remove</button>
                )}
              </div>
            </div>
          </div>
        ))}
        {!readOnly && canAddEpisode && (
          <button type="button" className="btn btn-secondary" style={{ marginBottom: 16 }}
            onClick={() => setEpisodes(prev => [...prev, { discharged: "", readmitted: "" }])}>
            + Sent home undelivered
          </button>
        )}

        <div className="form-grid-2">
          <div className="form-group">
            <label>Pregnancy outcome</label>
            <select value={outcome} disabled={readOnly} onChange={ev => setOutcome(ev.target.value)}>
              <option value="">Still pregnant / not known yet</option>
              {OUTCOMES.map(o => <option key={o} value={o}>{o}</option>)}
            </select>
            <small style={{ color: "#64748b" }}>
              "Delivered here" is set by filling Form B; use it here only if Form B is not yet entered.
            </small>
          </div>
          {outcome && (
            <div className="form-group">
              <label>Date of outcome<span className="required">*</span></label>
              <input type="date" value={outcomeDate} max={max} disabled={readOnly}
                onChange={ev => setOutcomeDate(ev.target.value)} />
            </div>
          )}
        </div>

        <div className="form-grid-2">
          <div className="form-group">
            <label>
              <input type="checkbox" checked={withdrawn} disabled={readOnly}
                onChange={ev => setWithdrawn(ev.target.checked)} style={{ marginRight: 8 }} />
              She withdrew her consent herself
            </label>
            <small style={{ color: "#64748b" }}>
              Only when the woman (or her family) asks to withdraw. Form B is then not filled.
            </small>
          </div>
          {withdrawn && (
            <div className="form-group">
              <label>Date withdrawn<span className="required">*</span></label>
              <input type="date" value={withdrawnDate} max={max} disabled={readOnly}
                onChange={ev => setWithdrawnDate(ev.target.value)} />
            </div>
          )}
        </div>

        {!readOnly && (
          <button type="button" className="btn btn-save" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save pregnancy follow-up"}
          </button>
        )}
        {message && (
          <div className={`form-message${message.startsWith("✅") ? " msg-success" : " msg-error"}`}>{message}</div>
        )}
      </div>
    </div>
  );
}
