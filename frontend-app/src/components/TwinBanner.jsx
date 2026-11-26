// Which twin / triplet this form is for (PI 2026-11-26: entries for twin 2
// were typed into twin 1's forms). Shown at the top of every baby form when the
// mother has more than one baby: "Twin 2 of 2 · 01-B-012". Each baby has its
// own colour. Form A (the mother's) shows nothing.
import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import api from "../api/axios";

const COLOURS = ["#1d4ed8", "#7c3aed", "#0f766e", "#b45309"];
const WORD = { 2: "Twin", 3: "Triplet", 4: "Quadruplet" };

export default function TwinBanner() {
  const { pathname } = useLocation();
  const [info, setInfo] = useState(null);

  useEffect(() => {
    let active = true;
    const parts = pathname.split("/").filter(Boolean);
    const form = parts[0] || "";
    const id = parts[1] ? decodeURIComponent(parts[1]) : "";
    setInfo(null);
    if (!id || form === "form-a" || form === "edit") return undefined;
    (async () => {
      try {
        let sid = null;
        let number = null;
        let eid = null;
        if (form === "form-b") {
          sid = id;
          number = parts[2] ? Number(parts[2]) : 1;
        } else {
          eid = id;
          sid = (await api.get(`/screenings/by-enrollment/${encodeURIComponent(id)}`)).data?.screening_id || null;
        }
        if (!sid) return;
        const r = (await api.get(`/screenings/${encodeURIComponent(sid)}/babies`)).data || {};
        const total = r.number_of_babies || 1;
        if (total < 2) return;
        const babies = r.babies || [];
        const me = eid ? babies.find((b) => b.enrollment_id === eid) : babies.find((b) => b.baby_number === number);
        const n = me?.baby_number || number;
        if (active && n) setInfo({ n, total, eid: me?.enrollment_id || eid || "" });
      } catch (_) { /* nothing to show */ }
    })();
    return () => { active = false; };
  }, [pathname]);

  if (!info) return null;
  const colour = COLOURS[(info.n - 1) % COLOURS.length];
  return (
    <div className="twin-banner" style={{ borderColor: colour, color: colour }}>
      <strong>{WORD[info.total] || "Baby"} {info.n} of {info.total}</strong>
      {info.eid ? ` · ${info.eid}` : ""} — everything on this page is for baby {info.n}.
      Switch baby with the buttons in the sidebar.
    </div>
  );
}
