/** Location / area of the baby (PI 2026-11-04): Helper 5 4.6 Location, Form E
 *  area of admission, Form D transferred out on day 1.
 *
 *  Every site stores the same generic area, so sites compare like with like.
 *  A site that has sent its ward names sees them on the buttons (PGIMER:
 *  AMCC wards); the stored value is still the generic area. Form D has no
 *  DR (a transfer out of the delivery room cannot go to the delivery room).
 */

export const LOCATION_AREAS = [
  "DR",
  "NICU",
  "HDU",
  "Nursery",
  "Transitional nursery",
  "KMC nursery",
];

/** Ward names per site, by enrolment-ID site prefix. Other sites: none yet. */
const SITE_WARDS = {
  "01": {   // PGIMER, PI 2026-11-04
    DR: "AMCC 1A",
    NICU: "AMCC 4A / 4B",
    Nursery: "AMCC 5A / 5B",
    "Transitional nursery": "AMCC 1C, LR nursery",
    "KMC nursery": "AMCC 5C",
  },
};

/** Earlier labels → generic area (old generic chips; AMCC labels saved on training). */
const LEGACY_AREA = {
  "Step-down/Nursery": "Nursery",
  NURSERY: "Nursery",
  "KMC-N": "KMC nursery",
  "AMCC-1A (DR)": "DR",
  "AMCC-1A(DR)": "DR",
  "AMCC-1C (NURSERY)": "Transitional nursery",
  "AMCC-1C(NURSERY)": "Transitional nursery",
  "AMCC-4A (NICU)": "NICU",
  "AMCC-4A(NICU)": "NICU",
  "AMCC-5B (NNN)": "Nursery",
  "AMCC-5B(NNN)": "Nursery",
};

function sitePrefix({ site, enrollmentId } = {}) {
  const m = String(enrollmentId || "").trim().match(/^(\d{2})-/);
  if (m) return m[1];
  const s = String(site || "").trim().toUpperCase();
  return s === "PGIMER" || s === "01" ? "01" : null;
}

export function isPgimerBaby(ctx = {}) {
  return sitePrefix(ctx) === "01";
}

export function normalizeHelperLocations(values) {
  const list = Array.isArray(values) ? values : [];
  return list.map((v) => LEGACY_AREA[v] || v).filter(Boolean);
}

export function normalizeHelperLocation(value) {
  return normalizeHelperLocations(value ? [value] : [])[0] || "";
}

/** Values to offer. noDR for Form D. A saved value not in the list is kept. */
export function helperLocationOptions({ selected, noDR = false } = {}) {
  const base = noDR ? LOCATION_AREAS.filter((a) => a !== "DR") : LOCATION_AREAS;
  const extras = (selected || []).filter((v) => v && !base.includes(v));
  return [...base, ...extras];
}

/** Button text: "NICU (AMCC 4A / 4B)" where the site has a ward name. */
export function locationLabel(value, ctx = {}) {
  const ward = (SITE_WARDS[sitePrefix(ctx)] || {})[value];
  return ward ? `${value} (${ward})` : value;
}
