import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { isGlobalUser } from "../../utils/roles";
import {
  Bell,
  Menu,
  RefreshCw,
  Sparkles,
  LogOut,
  MapPin,
} from "lucide-react";
import { formatSiteName, formatSiteShort } from "./siteLabels";

const NOTIF_COL = {
  warn: "#E8A020",
  info: "#006398",
  error: "#ba1a1a",
  ok: "#059669",
};

export default function DashboardHeader({
  now,
  notifications,
  notifOpen,
  onNotifToggle,
  onNotifClose,
  roleLabel,
  roleColor,
  onAskAi,
  onRefresh,
  onMenu,
  tabLabel,
}) {
  const { user, logout } = useAuth();
  const [confirmOut, setConfirmOut] = useState(false);
  const siteChip = user?.site
    ? formatSiteShort(user.site)
    : isGlobalUser(user)
      ? "All sites"
      : "";
  const siteChipTitle = user?.site
    ? formatSiteName(user.site)
    : isGlobalUser(user)
      ? "All trial sites"
      : "";

  const handleLogout = () => {
    logout();
    window.location.href = "/login";
  };

  const clock = `${now.toLocaleDateString("en-IN", { day: "2-digit", month: "short" })} · ${now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}`;

  return (
    <header className="relative z-40 shrink-0">
      <div
        className="flex h-[72px] items-center gap-3 px-3 sm:px-5"
        style={{
          background:
            "radial-gradient(circle at 12% 0%, rgba(56,189,248,0.34), transparent 34%), radial-gradient(circle at 88% 120%, rgba(45,212,191,0.16), transparent 32%), linear-gradient(135deg, #082f49 0%, #0d3d6e 48%, #123c69 100%)",
        }}
      >
        <button
          type="button"
          className="ds-focus flex h-10 w-10 items-center justify-center rounded-xl border-0 bg-white/10 text-white shadow-none hover:bg-white/15 lg:hidden"
          aria-label="Open navigation"
          onClick={onMenu}
        >
          <Menu size={18} />
        </button>

        <div className="hidden min-w-0 shrink-0 items-center gap-3 lg:flex">
          <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-xl bg-white shadow-[0_8px_20px_rgba(2,6,23,0.28)]">
            <img src="/logo.png" alt="" className="h-9 w-9 object-contain" />
          </div>
          <div className="flex min-w-0 flex-col justify-center">
            <p className="m-0 font-display text-[17px] font-bold leading-none tracking-[-0.03em] text-white">
              PORTAL Trial
            </p>
            <p className="m-0 mt-1 text-[10px] font-semibold uppercase leading-none tracking-[0.14em] text-sky-200/80">
              ICMR · Multi-site RCT
            </p>
          </div>
        </div>

        {tabLabel ? (
          <div className="hidden min-w-0 flex-1 items-center justify-center xl:flex">
            <span className="max-w-[280px] truncate rounded-full border border-cyan-200/25 bg-white/10 px-4 py-1.5 font-display text-[13px] font-semibold tracking-[-0.01em] text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]">
              {tabLabel}
            </span>
          </div>
        ) : (
          <div className="hidden flex-1 xl:block" />
        )}

        <p className="min-w-0 flex-1 truncate font-display text-[15px] font-semibold tracking-[-0.01em] text-white xl:hidden">
          {tabLabel || "PORTAL Trial"}
        </p>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <div className="hidden items-center gap-0 overflow-hidden rounded-full border border-white/15 bg-white/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.1)] lg:flex">
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5" title="Live telemetry">
              <span className="h-1.5 w-1.5 rounded-full bg-portal-live animate-ds-pulse" aria-hidden="true" />
              <span className="text-[11px] font-semibold tracking-wide text-emerald-200">Live</span>
            </span>
            <span className="h-4 w-px bg-white/15" aria-hidden="true" />
            <time
              className="px-3 py-1.5 font-data-mono text-[11px] font-medium text-sky-50"
              dateTime={now.toISOString()}
            >
              {clock}
            </time>
            {siteChip && (
              <>
                <span className="h-4 w-px bg-white/15" aria-hidden="true" />
                <span
                  className="inline-flex items-center gap-1 px-3 py-1.5 text-[11px] font-semibold text-white"
                  title={siteChipTitle}
                >
                  <MapPin size={11} className="text-sky-200" aria-hidden="true" />
                  {siteChip}
                </span>
              </>
            )}
          </div>

          <button
            type="button"
            onClick={onAskAi}
            className="ds-focus hidden h-9 items-center gap-1.5 rounded-full border-0 bg-gradient-to-r from-sky-500 to-cyan-400 px-3.5 text-[12px] font-semibold tracking-wide text-white shadow-[0_6px_16px_rgba(14,165,233,0.35)] hover:brightness-110 sm:inline-flex"
          >
            <Sparkles size={13} aria-hidden="true" />
            Ask AI
          </button>

          <div className="flex items-center gap-1 rounded-full border border-white/12 bg-black/15 p-1">
            <button
              type="button"
              onClick={onRefresh}
              className="ds-focus flex h-8 w-8 items-center justify-center rounded-full border-0 bg-transparent text-white shadow-none hover:bg-white/15"
              aria-label="Refresh dashboard"
            >
              <RefreshCw size={15} />
            </button>

            <div className="relative">
              <button
                type="button"
                className="ds-focus relative flex h-8 w-8 items-center justify-center rounded-full border-0 bg-transparent text-white shadow-none hover:bg-white/15"
                aria-label="Notifications"
                aria-expanded={notifOpen}
                onClick={onNotifToggle}
              >
                <Bell size={15} />
                {notifications.length > 0 && (
                  <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-portal-accent ring-2 ring-[#0d3d6e]" />
                )}
              </button>
              {notifOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40 cursor-default bg-transparent"
                    aria-hidden="true"
                    onClick={onNotifClose}
                  />
                  <div
                    className="absolute right-0 top-[calc(100%+10px)] z-50 w-[min(320px,calc(100vw-24px))] overflow-hidden rounded-xl border border-portal-line/80 bg-white shadow-portal-elevated"
                    role="dialog"
                    aria-label="Notifications"
                  >
                    <div className="flex items-center justify-between border-b border-portal-line/80 bg-portal-surface-low px-3.5 py-2.5">
                      <span className="text-[12px] font-semibold text-portal-ink">Notifications</span>
                      <span className="font-data-mono text-[10px] text-portal-secondary">
                        {notifications.length} recent
                      </span>
                    </div>
                    <div className="max-h-72 overflow-y-auto">
                      {notifications.length === 0 ? (
                        <p className="px-4 py-8 text-center text-[12px] font-medium text-portal-muted">
                          No recent live updates
                        </p>
                      ) : (
                        notifications.map((n, i) => (
                          <div key={i} className="flex gap-2.5 border-b border-portal-line/60 px-3.5 py-3 last:border-0">
                            <span
                              className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                              style={{ background: NOTIF_COL[n.type] || "#74777e" }}
                              aria-hidden="true"
                            />
                            <div>
                              <p className="text-[12px] font-medium leading-snug text-portal-ink">{n.msg}</p>
                              <p className="mt-0.5 font-data-mono text-[10px] text-portal-outline">{n.time}</p>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          <div className="hidden items-center gap-2 rounded-full border border-white/12 bg-white/10 py-1 pl-1 pr-2 sm:flex">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-full text-[12px] font-bold text-white shadow-[inset_0_0_0_2px_rgba(255,255,255,0.18)]"
              style={{ background: roleColor || "#0ea5e9" }}
              aria-hidden="true"
            >
              {(user?.full_name || user?.name || "U")[0].toUpperCase()}
            </div>
            <div className="flex min-w-0 max-w-[168px] flex-col justify-center">
              <p className="m-0 truncate text-[12px] font-semibold leading-none tracking-[-0.01em] text-white">
                {user?.full_name || user?.name || "User"}
              </p>
              <p className="m-0 mt-1 truncate text-[10px] font-medium leading-none tracking-wide text-sky-200/85">
                {roleLabel}
              </p>
            </div>
          </div>

          <div className="relative">
            <button
              type="button"
              onClick={() => setConfirmOut((open) => !open)}
              className="ds-focus flex h-9 w-9 items-center justify-center rounded-full border border-white/12 bg-white/10 text-white shadow-none hover:bg-white/20"
              aria-label="Log out"
              aria-expanded={confirmOut}
            >
              <LogOut size={15} />
            </button>
            {confirmOut && (
              <>
                <div
                  className="fixed inset-0 z-40 cursor-default bg-transparent"
                  aria-hidden="true"
                  onClick={() => setConfirmOut(false)}
                />
                <div
                  className="absolute right-0 top-[calc(100%+10px)] z-50 w-56 rounded-xl border border-white/10 bg-white p-3.5 shadow-[0_16px_40px_rgba(0,19,44,0.22)]"
                  role="dialog"
                  aria-label="Confirm log out"
                >
                  <p className="m-0 text-[13px] font-semibold leading-none text-portal-ink">Log out?</p>
                  <p className="m-0 mt-1.5 text-[12px] leading-snug text-portal-muted">
                    You will need to sign in again to continue.
                  </p>
                  <div className="mt-3 flex gap-2">
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="ds-focus h-8 flex-1 rounded-lg border-0 bg-portal-accent text-[12px] font-semibold text-white hover:opacity-90"
                    >
                      Log out
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmOut(false)}
                      className="ds-focus h-8 flex-1 rounded-lg border border-portal-line bg-white text-[12px] font-semibold text-portal-ink hover:bg-portal-surface-low"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
      <div
        className="h-[3px] w-full"
        style={{
          background: "linear-gradient(90deg, #22c55e 0%, #38bdf8 35%, #2563eb 70%, #22c55e 100%)",
        }}
        aria-hidden="true"
      />
    </header>
  );
}
