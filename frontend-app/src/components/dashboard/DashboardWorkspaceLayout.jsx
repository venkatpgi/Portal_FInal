import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import DashboardShell from "./DashboardShell";

const RL_MAP = {
  superadmin: "Super Admin",
  admin: "Administrator",
  pi: "Principal Investigator",
  scientist: "Scientist",
  nurse: "Research Nurse",
  deo: "Data Entry Operator",
  monitor: "Trial Monitor",
};

const RL_COL = {
  superadmin: "#7c3aed",
  global_scientist: "#006398",
  admin: "#7c3aed",
  pi: "#0E7C7B",
  scientist: "#006398",
  nurse: "#059669",
  deo: "#d97706",
  monitor: "#ea580c",
};

/** Shared layout for /entries, /manage-staff, /trial-monitoring, /audit-trail, /data-queries */
export default function DashboardWorkspaceLayout({
  pageTitle,
  search = "",
  onSearchChange = () => {},
  onRefresh = () => {},
  children,
}) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(t);
  }, []);

  const goDashboardTab = useCallback(
    (id) => navigate("/dashboard", { state: { dashboardTab: id } }),
    [navigate],
  );

  return (
    <DashboardShell
      tab=""
      pageTitle={pageTitle}
      onTabChange={goDashboardTab}
      sidebarOpen={sidebarOpen}
      onSidebarOpen={() => setSidebarOpen(true)}
      onSidebarClose={() => setSidebarOpen(false)}
      isSuperadmin={user?.role === "superadmin"}
      headerProps={{
        search,
        onSearchChange,
        now,
        notifications: [],
        notifOpen: false,
        onNotifToggle: () => {},
        onNotifClose: () => {},
        roleLabel: RL_MAP[user?.role] || user?.role || "User",
        roleColor: RL_COL[user?.role] || "#006398",
        onAskAi: () => navigate("/dashboard", { state: { dashboardTab: "ai-insights" } }),
        onRefresh,
      }}
    >
      {children}
    </DashboardShell>
  );
}
