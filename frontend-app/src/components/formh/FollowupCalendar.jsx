// Follow-up calendar (Form H H12.6, PI 2026-11-19). When the baby leaves
// alive, book a date with the family for each Form I checkpoint still to
// come (36 / 40 / 44 wk PMA, window ± 2 days), or record why no date could
// be fixed. Server rules: backend/followup_booking.py. The calendar is built
// from the SAVED Form H, so an unsaved outcome / discharge date is saved
// first. Submit of Form H waits until every checkpoint is booked
// (onStatus(false)).
import React, { useCallback, useEffect, useState } from "react";
import api from "../../api/axios";
import { useAuth } from "../../context/AuthContext";
import { CollapsibleCard } from "./FormHFields";

export const ALIVE_OUTCOMES = [
  "Discharged",
  "Back referred",
  "Discharged home on request",
  "Left Against Medical Advice",
];

const fmt = (iso) => {
  if (!iso) return "";
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00`);
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
};

const STATE_TEXT = {
  done: "Done on Form I",
  ended: "Follow-up ended (death or consent withdrawn)",
  in_nicu: "Due while in the NICU: assess before leaving and record on Form I",
  no_discharge_date: "Enter the discharge date first",
};

const toItem = (r) => ({
  checkpoint: r.checkpoint,
  booked_date: r.booked_date ? String(r.booked_date).slice(0, 10) : "",
  mode: r.mode || "",
  not_booked_reason: r.not_booked_reason || "",
  not_booked_other: r.not_booked_other || "",
});

export default function FollowupCalendar({ enrollmentId, outcome, dischargeDate, saveFormH, onStatus }) {
  const { user } = useAuth() || {};
  const [cal, setCal] = useState(null);
  const [items, setItems] = useState({});
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(true);
  const [clinicEdit, setClinicEdit] = useState(null);

  const role = (user?.role || "").toLowerCase();
  const canSetClinic = ["superadmin", "site_pi", "site_scientist"].includes(role);
  const alive = ALIVE_OUTCOMES.includes(outcome);

  const load = useCallback(async () => {
    if (!enrollmentId) return;
    try {
      const res = await api.get(`/followup-bookings/${enrollmentId}`);
      setCal(res.data);
      setItems(Object.fromEntries((res.data.rows || []).map((r) => [r.checkpoint, toItem(r)])));
    } catch (err) {
      setCal(null);
    }
  }, [enrollmentId]);

  useEffect(() => { load(); }, [load]);

  // Saved Form H differs from what is on screen: the calendar is stale.
  const stale = alive && cal && (cal.outcome !== outcome
    || String(cal.left_on || "").slice(0, 10) !== String(dischargeDate || "").slice(0, 10));

  const bookable = (cal?.rows || []).filter((r) => r.state === "bookable");
  const filled = (it) => !!(it && (it.booked_date ? it.mode : it.not_booked_reason
    && (it.not_booked_reason !== "Other" || it.not_booked_other.trim())));
  const savedComplete = !!(cal && cal.applies && cal.complete);

  useEffect(() => {
    if (!onStatus) return;
    if (!alive) onStatus(true);
    else onStatus(!!(cal && cal.applies && !stale && savedComplete));
  }, [alive, cal, stale, savedComplete, onStatus]);

  if (!alive) return null;

  const set = (wk, patch) => setItems((prev) => ({ ...prev, [wk]: { ...prev[wk], ...patch } }));

  const syncFormH = async () => {
    setBusy(true);
    setMsg("");
    const ok = await saveFormH();
    if (ok !== false) await load();
    setBusy(false);
  };

  const save = async () => {
    setBusy(true);
    setMsg("");
    try {
      const res = await api.put(`/followup-bookings/${enrollmentId}`, {
        items: bookable.map((r) => items[r.checkpoint] || { checkpoint: r.checkpoint }),
      });
      setCal(res.data);
      setItems(Object.fromEntries((res.data.rows || []).map((r) => [r.checkpoint, toItem(r)])));
      setMsg(res.data.complete
        ? "✅ Follow-up saved. The Site PI and Site Scientists are emailed."
        : "✅ Saved. Some checkpoints still need a date or a reason.");
    } catch (err) {
      setMsg(`❌ ${err?.response?.data?.detail || "Could not save the follow-up dates."}`);
    } finally {
      setBusy(false);
    }
  };

  const slip = async () => {
    try {
      const res = await api.get(`/followup-bookings/${enrollmentId}/slip.pdf`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      setMsg("❌ Could not make the parent slip.");
    }
  };

  const saveClinic = async () => {
    try {
      const res = await api.put(`/followup-bookings/clinic/${encodeURIComponent(cal.site)}`, clinicEdit);
      setCal((prev) => ({ ...prev, clinic: res.data }));
      setClinicEdit(null);
    } catch (err) {
      setMsg(`❌ ${err?.response?.data?.detail || "Could not save the clinic details."}`);
    }
  };

  const summary = !cal ? "Loading" : stale ? "Save Form H" : !cal.applies ? "—"
    : bookable.length === 0 ? "Nothing to book" : savedComplete ? "Booked" : "To book";
  const statusClass = savedComplete && !stale ? "yes" : "empty";
  const clinic = cal?.clinic || {};

  return (
    <CollapsibleCard
      code="H12.6"
      title="Follow-up calendar (Form I visits)"
      icon="📅"
      accentColor="bg-emerald-500"
      summary={summary}
      statusClass={statusClass}
      open={open}
      onToggle={() => setOpen(!open)}
    >
      <div className="fu-cal">
        <p className="field-note">
          Book each follow-up with the family before the baby leaves. Pick a date inside the window
          (checkpoint date ± {cal?.window_days ?? 2} days). If no date can be fixed, choose why.
          Form H cannot be submitted until every checkpoint is booked.
        </p>

        {stale && (
          <div className="fu-cal-warn">
            The outcome or discharge date on screen is not saved yet; the dates below depend on it.
            <button type="button" className="fu-cal-btn" disabled={busy} onClick={syncFormH}>
              Save Form H and update
            </button>
          </div>
        )}

        {cal && !cal.applies && !stale && <p className="field-note">{cal.why}</p>}

        {cal && cal.applies && !stale && (
          <>
            <div className="fu-cal-table" role="table">
              <div className="fu-cal-row fu-cal-head" role="row">
                <span>Checkpoint</span><span>Date (window)</span><span>Booked date</span><span>How / why not</span>
              </div>
              {cal.rows.map((r) => {
                const it = items[r.checkpoint] || toItem(r);
                const isBookable = r.state === "bookable";
                return (
                  <div className={`fu-cal-row${isBookable && !filled(it) ? " fu-cal-missing" : ""}`}
                    role="row" key={r.checkpoint}>
                    <span className="fu-cal-wk">{r.checkpoint} wk PMA</span>
                    <span>
                      {fmt(r.due)}
                      <small> ({fmt(r.window_from)} – {fmt(r.window_to)})</small>
                    </span>
                    {isBookable ? (
                      <>
                        <span>
                          <input
                            type="date"
                            aria-label={`${r.checkpoint} wk booked date`}
                            value={it.booked_date}
                            min={String(r.earliest).slice(0, 10)}
                            max={String(r.latest).slice(0, 10)}
                            onChange={(e) => set(r.checkpoint, { booked_date: e.target.value })}
                          />
                          {r.problem && r.problem !== "not booked" && (
                            <div className="error-text">{r.problem}</div>
                          )}
                        </span>
                        <span>
                          {it.booked_date ? (
                            <span className="fu-cal-pills">
                              {cal.modes.map((m) => (
                                <button type="button" key={m}
                                  className={`fu-cal-pill${it.mode === m ? " is-on" : ""}`}
                                  onClick={() => set(r.checkpoint, { mode: m })}>{m}</button>
                              ))}
                            </span>
                          ) : (
                            <>
                              <select
                                aria-label={`${r.checkpoint} wk reason not booked`}
                                value={it.not_booked_reason}
                                onChange={(e) => set(r.checkpoint, { not_booked_reason: e.target.value })}
                              >
                                <option value="">-- No date: why? --</option>
                                {cal.reasons.map((x) => <option key={x} value={x}>{x}</option>)}
                              </select>
                              {it.not_booked_reason === "Other" && (
                                <input
                                  placeholder="Reason"
                                  value={it.not_booked_other}
                                  onChange={(e) => set(r.checkpoint, { not_booked_other: e.target.value })}
                                />
                              )}
                            </>
                          )}
                        </span>
                      </>
                    ) : (
                      <span className="fu-cal-state">{STATE_TEXT[r.state] || r.state}</span>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="fu-cal-actions">
              {bookable.length > 0 && (
                <button type="button" className="fu-cal-btn" disabled={busy} onClick={save}>
                  Save follow-up dates
                </button>
              )}
              {bookable.length > 0 && savedComplete && (
                <button type="button" className="fu-cal-btn fu-cal-btn--light" onClick={slip}>
                  Print parent slip
                </button>
              )}
            </div>

            <div className="fu-cal-clinic">
              <strong>On the parent slip:</strong>{" "}
              {clinic.place || clinic.phone
                ? `${clinic.place || "place not set"}${clinic.days_times ? `, ${clinic.days_times}` : ""}; phone ${clinic.phone || "not set"}`
                : "clinic place and phone not set yet (blank lines are printed)."}
              {canSetClinic && !clinicEdit && (
                <button type="button" className="fu-cal-link"
                  onClick={() => setClinicEdit({ place: clinic.place || "", days_times: clinic.days_times || "",
                    phone: clinic.phone || "" })}>
                  Edit for the site
                </button>
              )}
              {clinicEdit && (
                <div className="fu-cal-clinic-edit">
                  <input placeholder="Where (clinic name, block, floor)" value={clinicEdit.place}
                    onChange={(e) => setClinicEdit({ ...clinicEdit, place: e.target.value })} />
                  <input placeholder="Days and times" value={clinicEdit.days_times}
                    onChange={(e) => setClinicEdit({ ...clinicEdit, days_times: e.target.value })} />
                  <input placeholder="Phone for families" value={clinicEdit.phone}
                    onChange={(e) => setClinicEdit({ ...clinicEdit, phone: e.target.value })} />
                  <button type="button" className="fu-cal-btn" onClick={saveClinic}>Save</button>
                  <button type="button" className="fu-cal-link" onClick={() => setClinicEdit(null)}>Cancel</button>
                </div>
              )}
            </div>
          </>
        )}

        {msg && <div className={`form-message${msg.startsWith("✅") ? " msg-success" : " msg-error"}`}>{msg}</div>}
      </div>
    </CollapsibleCard>
  );
}
