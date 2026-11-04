/** Helper 4.6 Location chips — site-specific (PGIMER AMCC wards). */

export const DEFAULT_HELPER_LOCATIONS = [
  "DR",
  "NICU",
  "Step-down/Nursery",
  "KMC-N",
  "Other",
];

export const PGIMER_HELPER_LOCATIONS = [
  "AMCC-1A (DR)",
  "AMCC-1C (NURSERY)",
  "AMCC-2A (SLR)",
  "AMCC-3D (ANTENATAL)",
  "AMCC-4A (NICU)",
  "AMCC-5B (NNN)",
];

/** Old generic chips / no-space AMCC labels → current PGIMER labels. */
const PGIMER_LEGACY_LOCATION = {
  DR: "AMCC-1A (DR)",
  NICU: "AMCC-4A (NICU)",
  "Step-down/Nursery": "AMCC-1C (NURSERY)",
  NURSERY: "AMCC-1C (NURSERY)",
  "AMCC-1A(DR)": "AMCC-1A (DR)",
  "AMCC-1C(NURSERY)": "AMCC-1C (NURSERY)",
  "AMCC-2A(SLR)": "AMCC-2A (SLR)",
  "AMCC-3D(ANTENATAL)": "AMCC-3D (ANTENATAL)",
  "AMCC-4A(NICU)": "AMCC-4A (NICU)",
  "AMCC-5B(NNN)": "AMCC-5B (NNN)",
};

export function isPgimerBaby({ site, enrollmentId } = {}) {
  const id = String(enrollmentId || "").trim();
  const prefix = id.match(/^(\d{2})-/);
  if (prefix) return prefix[1] === "01";
  const s = String(site || "").trim().toUpperCase();
  return s === "PGIMER" || s === "01";
}

export function normalizeHelperLocations(values, { site, enrollmentId } = {}) {
  const list = Array.isArray(values) ? values : [];
  if (!isPgimerBaby({ site, enrollmentId })) {
    return list.filter(Boolean);
  }
  return list
    .map((v) => PGIMER_LEGACY_LOCATION[v] || v)
    .filter(Boolean);
}

export function helperLocationOptions({ site, enrollmentId, selected } = {}) {
  const base = isPgimerBaby({ site, enrollmentId })
    ? PGIMER_HELPER_LOCATIONS
    : DEFAULT_HELPER_LOCATIONS;
  const extras = (selected || []).filter((v) => v && !base.includes(v));
  return extras.length ? [...base, ...extras] : [...base];
}

export function normalizeHelperLocation(value, ctx = {}) {
  return normalizeHelperLocations(value ? [value] : [], ctx)[0] || "";
}
