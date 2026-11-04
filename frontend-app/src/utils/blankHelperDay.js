/** Mirrors backend stay_end.is_blank_helper_day. An explicit No is an answer. */
const META = new Set([
  "enrollment_id",
  "nicu_day",
  "submission_status",
  "saved_at",
  "saved_by",
  "submitted_at",
  "submitted_by",
]);

const ENTRY_META = new Set(["id", "date", "time", "slot_time"]);

function isEmptyHelperValue(v) {
  return v == null || v === "" || (Array.isArray(v) && v.length === 0);
}

function jsonRowHasValue(entry) {
  if (!entry || typeof entry !== "object" || Array.isArray(entry)) return false;
  return Object.entries(entry).some(([k, v]) => {
    if (ENTRY_META.has(k)) return false;
    if (v == null || v === "" || v === false || (Array.isArray(v) && v.length === 0)) return false;
    return true;
  });
}

export function isBlankHelperDay(values) {
  if (!values || typeof values !== "object") return true;
  for (const [k, v] of Object.entries(values)) {
    if (META.has(k) || isEmptyHelperValue(v)) continue;
    if (k.endsWith("_json") && typeof v === "string") {
      try {
        const rows = JSON.parse(v);
        if (Array.isArray(rows) && !rows.some(jsonRowHasValue)) continue;
      } catch {
        return false;
      }
    }
    return false;
  }
  return true;
}

export const BLANK_HELPER_DAY_CLIENT_MESSAGE =
  "⚠️ Nothing entered for this day yet — add data before saving.";

/** Backend refuse_blank_helper_day 422. Not a scary failure when browsing days. */
export function isBlankHelperDayRefusal(err) {
  if (err?.response?.status !== 422) return false;
  const d = err?.response?.data?.detail;
  if (typeof d !== "string") return false;
  return d.toLowerCase().includes("nothing entered for this day");
}
