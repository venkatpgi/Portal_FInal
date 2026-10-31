// SAE items still owed on this baby (PI 2026-10-31, backend/sae_rules.py): the
// 14-day report from 3 days before it is due, and an AE marked Converted to
// SAE with no report.
import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import api from "../api/axios";

const ENROLLMENT = /^\d{2}-[A-Za-z0-9-]+$/;

export default function SaeDeadlineBanner() {
  const location = useLocation();
  const [alerts, setAlerts] = useState(null);
  const last = location.pathname.split("/").filter(Boolean).pop() || "";
  const eid = ENROLLMENT.test(last) ? last : "";

  useEffect(() => {
    if (!eid) {
      setAlerts(null);
      return undefined;
    }
    let cancelled = false;
    api.get(`/enrollment/${encodeURIComponent(eid)}/sae-alerts`)
      .then((r) => { if (!cancelled) setAlerts(r.data); })
      .catch(() => { if (!cancelled) setAlerts(null); });
    return () => { cancelled = true; };
  }, [eid, location.pathname]);

  const due = alerts?.fourteen_day || [];
  const unreported = alerts?.unreported || [];
  if (!due.length && !unreported.length) return null;
  return (
    <div
      role="alert"
      style={{
        margin: "0 0 12px", padding: "8px 12px", borderRadius: 8, fontSize: 13,
        background: "#fef2f2", border: "1px solid #fecaca", color: "#991b1b",
      }}
    >
      {due.map((d) => (
        <div key={`${d.sae}-${d.due}`}>
          <strong>14-day report {d.overdue ? "overdue" : "due"}: {d.sae}</strong>, {d.overdue ? "was due" : "by"} {d.due}.
        </div>
      ))}
      {unreported.map((name) => (
        <div key={name}><strong>No SAE report:</strong> {name} is marked Converted to SAE.</div>
      ))}
      {!location.pathname.includes("/form-y-sae") && <Link to={`/form-y-sae/${eid}`}>Open Form Y</Link>}
    </div>
  );
}
