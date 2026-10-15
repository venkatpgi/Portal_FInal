// Top-bar link to the Data Queries inbox with the open-query count (red when
// any query is over 7 days). Refreshes on navigation and every 5 minutes.
import React, { useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { ClipboardList } from "lucide-react";
import api from "../api/axios";

export default function DataQueriesNavLink() {
  const location = useLocation();
  const [sum, setSum] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => api.get("/data-queries/summary")
      .then((r) => { if (!cancelled) setSum(r.data || null); })
      .catch(() => { if (!cancelled) setSum(null); });
    load();
    const t = setInterval(load, 5 * 60 * 1000);
    return () => { cancelled = true; clearInterval(t); };
  }, [location.pathname]);

  const total = sum?.total || 0;
  return (
    <NavLink to="/data-queries" className={({ isActive }) => `nav-btn ${isActive ? "active" : ""}`}>
      <ClipboardList size={16} /> <span>Data Queries</span>
      {total > 0 && (
        <span
          title={sum?.red ? `${sum.red} over 7 days` : `${total} open`}
          style={{
            marginLeft: 6, minWidth: 18, padding: "0 6px", borderRadius: 9, fontSize: 11, fontWeight: 700,
            lineHeight: "18px", textAlign: "center", color: "#fff", background: sum?.red ? "#dc2626" : "#d97706",
          }}
        >
          {total}
        </span>
      )}
    </NavLink>
  );
}
