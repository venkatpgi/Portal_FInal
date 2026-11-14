// Form F surveillance window is open today and this baby has no scan in it.
// Shown on every form (FormLayout), same slot as SAE / data queries. Not a data query.
import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import api from "../api/axios";

const ENROLLMENT = /^\d{2}-[A-Za-z0-9-]+$/;

export default function CranialUsgDueBanner() {
  const location = useLocation();
  const [due, setDue] = useState([]);
  const last = location.pathname.split("/").filter(Boolean).pop() || "";
  const eid = ENROLLMENT.test(last) ? last : "";

  useEffect(() => {
    if (!eid) {
      setDue([]);
      return undefined;
    }
    let cancelled = false;
    const load = () => api.get(`/enrollment/${encodeURIComponent(eid)}/cranial-usg-due`)
      .then((r) => { if (!cancelled) setDue(r.data?.due || []); })
      .catch(() => { if (!cancelled) setDue([]); });
    load();
    window.addEventListener("portal:form-f-saved", load);
    return () => {
      cancelled = true;
      window.removeEventListener("portal:form-f-saved", load);
    };
  }, [eid, location.pathname]);

  if (!due.length) return null;
  const onFormF = location.pathname.includes("/form-f/");
  return (
    <div
      role="status"
      style={{
        margin: "0 0 12px", padding: "8px 12px", borderRadius: 8, fontSize: 13,
        background: "#e9f4f3", border: "1px solid #087e8b", color: "#0b5c63",
      }}
    >
      {due.map((d) => (
        <div key={d.key || d.label}>
          <strong>Cranial USG due: {d.label}</strong>
          {d.window ? ` — ${d.window}.` : "."}
        </div>
      ))}
      {!onFormF && <Link to={`/form-f/${eid}`}>Open Form F</Link>}
    </div>
  );
}
