// "Go to another baby" box in the forms sidebar (PI 2026-11-26): type an
// enrolment / screening number or the mother's name and open that record on
// the same form, without going back through View Entries. Same lists as View
// Entries (/screenings/ + /pii/batch, names only with PII rights). Forms keyed
// by enrolment number open the same form; otherwise Form A. The current form
// is saved first (`go` = the sidebar's guarded navigate).
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Search } from "lucide-react";
import api from "../api/axios";
import { formatMotherFirstName } from "../utils/babyName";

// form path prefix -> needs an enrolment number (true) or a screening id (false)
const BY_ENROLLMENT = new Set(["form-c", "form-d", "form-e", "form-f", "form-g", "form-h", "form-i", "form-j",
  "form-k", "form-l", "fio2-auc", "vs6-1", "infect-gi-hema-log", "metab-renal-vasc-eye-log",
  "minimal-monitoring", "form-y-sae", "adverse-events", "sae-list"]);
const BY_SCREENING = new Set(["form-a", "form-b"]);

let cache = null;   // { at, rows } for this page load

export default function QuickSwitch({ go }) {
  const location = useLocation();
  const [text, setText] = useState("");
  const [rows, setRows] = useState(cache?.rows || null);
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  const load = async () => {
    if (cache && Date.now() - cache.at < 5 * 60 * 1000) { setRows(cache.rows); return; }
    try {
      const res = await api.get("/screenings/?limit=500");
      const list = (Array.isArray(res.data) ? res.data : []).filter((s) => s.screening_id);
      let pii = {};
      try {
        const sids = list.map((s) => s.screening_id);
        if (sids.length) pii = (await api.post("/pii/batch", { screening_ids: sids })).data?.items || {};
      } catch { pii = {}; }
      let stages = {};
      try { stages = (await api.get("/screenings/stages")).data || {}; } catch { stages = {}; }
      // twins / triplets: one item per baby, so twin 2 opens twin 2 (PI 2026-11-26)
      const out = list.flatMap((s) => {
        const mother = formatMotherFirstName(pii[s.screening_id]) || "";
        const babies = stages[s.screening_id]?.babies || [];
        if (babies.length > 1) {
          return babies.map((b) => ({ sid: s.screening_id, eid: b.enrollment_id || "", n: b.baby_number,
            total: babies.length, mother }));
        }
        return [{ sid: s.screening_id, eid: s.enrollment_id || "", n: 1, total: 1, mother }];
      });
      cache = { at: Date.now(), rows: out };
      setRows(out);
    } catch { setRows([]); }
  };

  useEffect(() => {
    const close = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const hits = useMemo(() => {
    const q = text.trim().toLowerCase();
    if (!rows || q.length < 2) return [];
    return rows.filter((r) => r.eid.toLowerCase().includes(q) || r.sid.toLowerCase().includes(q)
      || r.mother.toLowerCase().includes(q)).slice(0, 8);
  }, [rows, text]);

  const target = (r) => {
    const parts = location.pathname.split("/").filter(Boolean);
    const form = parts[0] || "";
    if (BY_ENROLLMENT.has(form) && r.eid) return `/${form}/${r.eid}`;
    if (form === "form-b") return r.n > 1 ? `/form-b/${r.sid}/${r.n}` : `/form-b/${r.sid}`;
    if (BY_SCREENING.has(form)) return `/${form}/${r.sid}`;
    if (r.n > 1) return `/form-b/${r.sid}/${r.n}`;   // twin 2+ with no enrolment yet: its own Form B
    return `/form-a/${r.sid}`;
  };

  const pick = (r) => {
    if (r.sid) localStorage.setItem("current_screening_id", r.sid);
    if (r.eid) localStorage.setItem("current_enrollment_id", r.eid);
    else localStorage.removeItem("current_enrollment_id");
    window.dispatchEvent(new Event("storage"));
    setOpen(false);
    setText("");
    go(target(r));
  };

  return (
    <div className="qs-box" ref={box}>
      <label className="qs-input">
        <Search size={13} strokeWidth={2} aria-hidden="true" />
        <input
          value={text}
          placeholder="Go to another baby: ID or name"
          aria-label="Go to another baby"
          onFocus={() => { setOpen(true); load(); }}
          onChange={(e) => { setText(e.target.value); setOpen(true); }}
          onKeyDown={(e) => { if (e.key === "Enter" && hits[0]) pick(hits[0]); if (e.key === "Escape") setOpen(false); }}
        />
      </label>
      {open && text.trim().length >= 2 && (
        <div className="qs-list" role="listbox">
          {rows === null && <div className="qs-empty">Loading…</div>}
          {rows !== null && hits.length === 0 && <div className="qs-empty">No match</div>}
          {hits.map((r) => (
            <button type="button" key={`${r.sid}/${r.n}`} className="qs-item" onClick={() => pick(r)}>
              <strong>{r.eid || r.sid}{r.total > 1 ? ` · baby ${r.n} of ${r.total}` : ""}</strong>
              <span>{[r.eid ? r.sid : "", r.mother].filter(Boolean).join(" · ")}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
