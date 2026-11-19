/** Completed-by designation autofill (Form D/E/H and later CRF footers).

PGIMER named titles stay as they were. Other-site scientists are
Project Research Scientist II (Medical). Nurses match Tanvi Saini /
Yashvi Jolly: Project Nurse III.
*/

export const DESIGNATION_NURSE = "Project Nurse III";
export const DESIGNATION_SITE_SCIENTIST =
  "Project Research Scientist II (Medical)";
export const DESIGNATION_PROJECT_SCIENTIST =
  "Project Research Scientist III (Medical)";
export const DESIGNATION_SHALINI =
  "Project Research Scientist III (Non-Medical)";

/** Site scientists — names are stored without a Dr. prefix. */
const SITE_SCIENTISTS = new Set([
  "Nafifa Tasmeen Rahman",
  "Kirti Vishnu Rathod",
  "Manpreet Kaur",
  "Sobhana",
]);

/** Drop a leading Dr. / Dr prefix. "Drake" is left as-is. */
export function nameWithoutDr(name) {
  return String(name || "")
    .replace(/^(?:Dr\.\s*|Dr\s+|Dr\.)/i, "")
    .trim();
}

function nameKey(name) {
  return nameWithoutDr(name);
}

export function isMannatGuliani(name) {
  return nameKey(name).toLowerCase() === "mannat guliani";
}

/** Keep existing order, but pin Mannat Guliani (with or without Dr.) last. */
export function withMannatLast(items, nameOf = (item) => item) {
  const rest = [];
  const mannat = [];
  for (const item of items || []) {
    const name = typeof nameOf === "function" ? nameOf(item) : item;
    if (isMannatGuliani(name)) mannat.push(item);
    else rest.push(item);
  }
  return [...rest, ...mannat];
}

export function completedByNameList(names = [], current = "") {
  const seen = new Set();
  const out = [];
  for (const raw of [...(names || []), current]) {
    const n = nameWithoutDr(raw);
    if (!n) continue;
    const key = n.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(n);
  }
  return withMannatLast(out);
}

export function completedByNameOptions(roster = [], current = "") {
  return completedByNameList(
    (roster || []).map((r) => r && r.full_name).filter(Boolean),
    current,
  );
}

export function fallbackCompletedByDesignation(name) {
  if (!name) return "";
  const n = nameKey(name);
  if (n === "Mannat Guliani") return DESIGNATION_PROJECT_SCIENTIST;
  if (n === "Shalini Dhiman") return DESIGNATION_SHALINI;
  if (/^Dr\.?\s+/i.test(String(name).trim()) || /^Dr\./i.test(String(name).trim())) {
    return DESIGNATION_SITE_SCIENTIST;
  }
  if (SITE_SCIENTISTS.has(n)) return DESIGNATION_SITE_SCIENTIST;
  return DESIGNATION_NURSE;
}

export function designationForCompletedBy(name, roster = []) {
  if (!name) return "";
  const key = nameKey(name);
  const hit = (roster || []).find((r) => r && nameKey(r.full_name) === key);
  if (hit?.designation) return hit.designation;
  return fallbackCompletedByDesignation(name);
}
