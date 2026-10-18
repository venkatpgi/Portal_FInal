// Open data queries on the baby / screening this form is showing (Phase 1,
// PI 2026-10-15). Read-only notice; nurses see it too (their site). Queries
// close by themselves once the data is corrected.
import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import api from "../api/axios";
import { useAuth } from "../context/AuthContext";
import { canSeeDataQueries } from "../utils/roles";

function storedId(key) {
  try {
    const v = localStorage.getItem(key);
    return v && v !== "undefined" && v !== "null" ? v : "";
  } catch {
    return "";
  }
}

export default function DataQueryBanner() {
  const { user } = useAuth();
  const location = useLocation();
  const [items, setItems] = useState([]);

  useEffect(() => {
    let cancelled = false;
    const keys = [storedId("current_screening_id"), storedId("current_enrollment_id")].filter(Boolean);
    if (!keys.length) {
      setItems([]);
      return undefined;
    }
    const params = new URLSearchParams();
    keys.forEach((k) => params.append("keys", k));
    api.get(`/data-queries/for-record?${params.toString()}`)
      .then((r) => { if (!cancelled) setItems(r.data || []); })
      .catch(() => { if (!cancelled) setItems([]); });
    return () => { cancelled = true; };
  }, [location.pathname]);

  if (!items.length) return null;
  const urgent = items.some((q) => q.colour === "red");
  return (
    <div
      role="status"
      style={{
        margin: "0 0 12px", padding: "8px 12px", borderRadius: 8, fontSize: 13,
        background: urgent ? "#fef2f2" : "#fffbeb",
        border: `1px solid ${urgent ? "#fecaca" : "#fcd34d"}`,
        color: urgent ? "#991b1b" : "#92400e",
      }}
    >
      <strong>{items.length === 1 ? "1 open data query" : `${items.length} open data queries`} on this record</strong>
      <ul style={{ margin: "4px 0 0 18px", padding: 0 }}>
        {items.map((q) => (
          <li key={q.id}>
            <span style={{ fontWeight: 600 }}>{q.title}</span>
            {q.detail ? ` — ${q.detail}` : ""}
          </li>
        ))}
      </ul>
      {canSeeDataQueries(user) && (
        <div style={{ marginTop: 4 }}><Link to="/data-queries">Open Data Queries</Link></div>
      )}
    </div>
  );
}
