/** Mirror backend/deps.py role sets for UI gating (not authoritative; the
 * server enforces). Access hierarchy SOP 1 Oct 2026 + PI 2026-10-15. */
const GLOBAL_ROLES = new Set(["superadmin", "project_scientist", "global_scientist", "tech_support"]);
const READ_ONLY_ROLES = new Set(["project_scientist", "global_scientist", "tech_support"]);
const CENTRAL_ANALYTICS_ROLES = new Set(["superadmin", "project_scientist", "global_scientist"]);

const CENTRAL_REVIEWER_ROLES = new Set(["superadmin", "project_scientist", "global_scientist"]);
const SITE_QUERY_ROLES = new Set(["site_pi", "site_scientist"]);

/** Data queries inbox: Global PI, Overall Project Scientist, Site PI, Site Scientist. */
export function canSeeDataQueries(user) {
  const r = (user?.role || "").toLowerCase();
  return CENTRAL_REVIEWER_ROLES.has(r) || SITE_QUERY_ROLES.has(r);
}

/** All-site query reviewer who gives the second sign-off. */
export function isCentralReviewer(user) {
  return CENTRAL_REVIEWER_ROLES.has((user?.role || "").toLowerCase());
}

/** View-only account: cannot create, change or delete entries. */
export function isReadOnlyUser(user) {
  return READ_ONLY_ROLES.has((user?.role || "").toLowerCase());
}

/** Manage Staff: Global PI and PTS-3 (tech_support). */
export function canManageUsers(user) {
  const r = (user?.role || "").toLowerCase();
  return r === "superadmin" || r === "tech_support";
}

/** Trial Monitoring, AI Insights, CSV export: Global PI + Overall Project Scientist. */
export function canSeeAnalytics(user) {
  return CENTRAL_ANALYTICS_ROLES.has((user?.role || "").toLowerCase());
}

export function isGlobalUser(user) {
  return GLOBAL_ROLES.has((user?.role || "").toLowerCase());
}

export function canViewAudit(user) {
  const r = (user?.role || "").toLowerCase();
  return isGlobalUser(user) || r === "site_pi";
}

export function roleDisplayLabel(role) {
  const r = (role || "").toLowerCase();
  const map = {
    superadmin: "Global PI (Superadmin)",
    global_scientist: "Global Scientist",
    project_scientist: "Overall Project Scientist",
    tech_support: "Technical Support (PTS3)",
    site_pi: "Site PI",
    site_scientist: "Site Scientist",
    nurse: "Project Nurse",
    pii_officer: "PII Officer",
    admin: "Admin",
    pi: "Principal Investigator",
    scientist: "Scientist",
    deo: "Data Entry Operator",
    monitor: "Trial Monitor",
  };
  return map[r] || role || "User";
}
