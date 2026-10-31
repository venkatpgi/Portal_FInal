// A baby who died needs an SAE report within 24 hours (PI 2026-10-31,
// backend/death_alert.py). Shown on every form, wherever the death was
// recorded, until a fatal Form Y is saved.
import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import api from "../api/axios";

const ENROLLMENT = /^\d{2}-[A-Za-z0-9-]+$/;

export default function DeathReportBanner() {
  const location = useLocation();
  const [status, setStatus] = useState(null);
  const last = location.pathname.split("/").filter(Boolean).pop() || "";
  const eid = ENROLLMENT.test(last) ? last : "";

  useEffect(() => {
    if (!eid) {
      setStatus(null);
      return undefined;
    }
    let cancelled = false;
    const load = () => api.get(`/enrollment/${encodeURIComponent(eid)}/death-status`)
      .then((r) => { if (!cancelled) setStatus(r.data); })
      .catch(() => { if (!cancelled) setStatus(null); });
    load();
    window.addEventListener("portal:death-recorded", load);
    return () => {
      cancelled = true;
      window.removeEventListener("portal:death-recorded", load);
    };
  }, [eid, location.pathname]);

  if (!status?.needs_report) return null;
  const onFormY = location.pathname.includes("/form-y-sae");
  return (
    <div className="field-hint field-hint-warning" role="alert" style={{ margin: "0 0 12px" }}>
      <strong>SAE report due{status.due ? ` by ${status.due.replace("T", " ")}` : " within 24 hours"}.</strong>{" "}
      This baby died{status.date ? ` on ${status.date}` : ""}{status.time ? ` at ${status.time}` : ""}.{" "}
      {!onFormY && <Link to={`/form-y-sae/${eid}`}>Open Form Y</Link>}
    </div>
  );
}
