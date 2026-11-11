/** Compare audit old/new snapshots so reviewers can see what actually changed. */

import { formatAuditDateTime, parseApiUtcDate } from "./datetime";

export const AUDIT_NOISE_KEYS = new Set([
  "id",
  "created_at",
  "updated_at",
  "created_by",
  "updated_by",
  "deleted_at",
  "deleted_by",
  "enrollment_id",
  "saved_by",
  "submitted_by",
  "override_by",
  "override_unlocked_until",
  "form",
  "explicitly_saved",
]);

/** Extra keys the helper-day History modal already shows in the header. */
export const AUDIT_HELPER_HIDE_KEYS = [
  "reason",
  "nicu_day",
  "saved_at",
  "submitted_at",
  "submission_status",
];

export const AUDIT_ACTION_LABELS = {
  INSERT: "Created",
  UPDATE: "Updated",
  SAVE: "Saved",
  SOFT_DELETE: "Deleted",
  OVERRIDE_UNLOCK: "Override unlock",
};

const ACRONYMS = {
  ga: "GA",
  nbs: "NBS",
  fio2: "FiO₂",
  cpap: "CPAP",
  pii: "PII",
  dob: "DOB",
  uid: "UID",
  et: "ET",
  kmc: "KMC",
  lisa: "LISA",
  sae: "SAE",
  usg: "USG",
  lmp: "LMP",
  sga: "SGA",
  aga: "AGA",
  lga: "LGA",
  pma: "PMA",
  nicu: "NICU",
  hr: "HR",
  spo2: "SpO₂",
  bpd: "BPD",
  ivh: "IVH",
  pvl: "PVL",
  rop: "ROP",
};

const FIELD_LABELS = {
  gestation_weeks: "Gestation (weeks)",
  gestation_days: "Gestation (days)",
  gestation_rand_weeks: "Gestation at randomization (weeks)",
  gestation_rand_days: "Gestation at randomization (days)",
  ga_method: "GA method",
  screening_datetime: "Screening date & time",
  date_of_birth: "Date of birth",
  time_of_birth: "Time of birth",
  birth_weight: "Birth weight",
  expected_delivery_date: "Expected delivery date",
  is_complete: "Form marked complete",
  consent_given: "Consent given",
  consent_datetime: "Consent date & time",
  consent_obtained_by_signature: "Consent obtained by signature",
  consent_signature_image: "Consent signature image",
  consent_signature_captured_at: "Consent signature captured at",
  pi_signature_image: "PI signature image",
  pi_signature_captured_at: "PI signature captured at",
  consent_taken_by: "Consent taken by",
  consent_form_version: "Consent form version",
  consent_language: "Consent language",
  video_pis_shown: "Video PIS shown",
  gestation_known: "Gestation known",
  screened_by: "Screened by",
  enrollment_id: "Enrollment ID",
  screening_id: "Screening ID",
  screening_status: "Screening status",
  mother_name_first: "Mother first name",
  mother_name_surname: "Mother surname",
  reason: "Reason",
  hours: "Unlock hours",
  nicu_day: "NICU day",
  urine_output_8am_2pm: "Urine 8am–2pm (ml)",
  urine_output_2pm_8pm: "Urine 2pm–8pm (ml)",
  urine_output_8pm_8am: "Urine 8pm–8am (ml)",
  urine_output_total: "Urine output total (ml/kg/hr)",
  urine_output_8am_2pm_status: "Urine 8am–2pm status",
  urine_output_2pm_8pm_status: "Urine 2pm–8pm status",
  urine_output_8pm_8am_status: "Urine 8pm–8am status",
  cumulative_feed_volume: "Cumulative feed volume (ml)",
  feed_volume: "Feed volume (ml/kg/d)",
  ph_readings_json: "pH readings",
  sodium_readings_json: "Sodium readings",
  potassium_readings_json: "Potassium readings",
  calcium_readings_json: "Calcium readings",
  sepsis_screens_json: "Sepsis screens",
  entries_json: "Daily monitoring entries",
  saved_at: "Saved at",
  submitted_at: "Submitted at",
  submission_status: "Submission status",
};

export function auditActionLabel(action) {
  if (!action) return "—";
  const key = String(action).toUpperCase();
  return AUDIT_ACTION_LABELS[key] || String(action).replace(/_/g, " ");
}

export function humanizeField(key) {
  if (!key) return "";
  if (FIELD_LABELS[key]) return FIELD_LABELS[key];
  return String(key)
    .split("_")
    .map((part) => {
      const lower = part.toLowerCase();
      if (ACRONYMS[lower]) return ACRONYMS[lower];
      if (/^\d+$/.test(part)) return part;
      return part.charAt(0).toUpperCase() + part.slice(1).toLowerCase();
    })
    .join(" ");
}

function isEmpty(value) {
  if (value === null || value === undefined || value === "") return true;
  if (Array.isArray(value) && value.length === 0) return true;
  return false;
}

function tryParseJson(value) {
  if (typeof value !== "string") return null;
  const t = value.trim();
  if (!(t.startsWith("{") || t.startsWith("["))) return null;
  try {
    return JSON.parse(t);
  } catch {
    return null;
  }
}

function looksLikeIsoDateTime(str) {
  return /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(str);
}

function formatReadingRow(row) {
  if (row == null) return "";
  if (typeof row !== "object" || Array.isArray(row)) return formatAuditValue(row);
  const date = row.date ? String(row.date).slice(0, 10) : "";
  const time = (row.time || row.slot_time || "").toString().trim();
  const when = [date, time].filter(Boolean).join(" ");
  const bits = [];
  if (row.type) bits.push(String(row.type));
  const val = row.ph ?? row.value ?? row.volume_ml ?? row.result ?? row.glucose
    ?? row.weight_g ?? row.max_fio2;
  if (val != null && val !== "") bits.push(String(val));
  if (row.unit) bits.push(String(row.unit));
  if (row.status) bits.push(String(row.status));
  const body = bits.join(" ");
  if (when && body) return `${when} · ${body}`;
  return when || body || "empty";
}

function formatEntriesMap(obj) {
  const parts = [];
  for (const [block, rows] of Object.entries(obj)) {
    if (!Array.isArray(rows)) continue;
    const filled = rows.filter((r) => {
      if (!r || typeof r !== "object") return false;
      return Object.entries(r).some(([k, v]) => {
        if (k === "id" || k === "date" || k === "time" || k === "slot_time") return false;
        return !isEmpty(v) && v !== false;
      });
    }).length;
    if (!filled) continue;
    parts.push(`${humanizeField(block)}: ${filled} reading${filled === 1 ? "" : "s"}`);
  }
  return parts.length ? parts.join("; ") : "sheet updated";
}

function formatStructured(value) {
  if (Array.isArray(value)) {
    if (value.length === 0) return "—";
    if (value.every((r) => r && typeof r === "object" && !Array.isArray(r))) {
      const lines = value.map(formatReadingRow).filter(Boolean);
      return lines.length ? lines.join("\n") : "—";
    }
    return value.map((v) => formatAuditValue(v)).filter((s) => s && s !== "—").join(", ") || "—";
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value);
    if (keys.length && keys.every((k) => Array.isArray(value[k]) || value[k] == null)) {
      return formatEntriesMap(value);
    }
    const parts = keys
      .filter((k) => k !== "id" && !isEmpty(value[k]))
      .map((k) => `${humanizeField(k)}: ${formatAuditValue(value[k])}`);
    return parts.length ? parts.join("; ") : "—";
  }
  return String(value);
}

const HIDDEN_VALUES = new Set(["[redacted]", "[previous]", "[updated]", "[hidden]"]);

function isHiddenValue(value) {
  if (typeof value !== "string") return false;
  return HIDDEN_VALUES.has(value.trim().toLowerCase());
}

export function formatAuditValue(value) {
  if (isEmpty(value)) return "empty";
  if (isHiddenValue(value)) return "hidden";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  const parsed = tryParseJson(value);
  if (parsed !== null) return formatAuditValue(parsed);
  if (typeof value === "object") return formatStructured(value);
  const str = String(value);
  if (looksLikeIsoDateTime(str)) {
    const formatted = formatAuditDateTime(str);
    if (formatted) return formatted;
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(str)) {
    const [y, m, d] = str.split("-").map(Number);
    const local = new Date(y, m - 1, d);
    if (!Number.isNaN(local.getTime())) {
      return local.toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
    }
  }
  return str;
}

function stripRowIds(value) {
  if (Array.isArray(value)) return value.map(stripRowIds);
  if (value && typeof value === "object") {
    const out = {};
    for (const k of Object.keys(value).sort()) {
      if (k === "id") continue;
      out[k] = stripRowIds(value[k]);
    }
    return out;
  }
  return value;
}

function canonical(value) {
  const parsed = tryParseJson(value);
  const v = parsed !== null ? parsed : value;
  if (isEmpty(v)) return "";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "object") {
    try {
      return JSON.stringify(stripRowIds(v));
    } catch {
      return String(v);
    }
  }
  return String(v).trim();
}

export function valuesEqual(a, b) {
  return canonical(a) === canonical(b);
}

function collectKeys(oldValues, newValues) {
  return [...new Set([
    ...Object.keys(oldValues || {}),
    ...Object.keys(newValues || {}),
  ])].sort();
}

/**
 * @returns {{
 *   changes: Array<{key: string, label: string, from: any, to: any, kind: string}>,
 *   unchanged: Array<{key: string, label: string, from: any, to: any, kind: string}>,
 * }}
 */
export function diffAuditValues(oldValues, newValues, { hideKeys = [] } = {}) {
  const hide = new Set([...AUDIT_NOISE_KEYS, ...hideKeys]);
  const oldV = oldValues && typeof oldValues === "object" ? oldValues : {};
  const newV = newValues && typeof newValues === "object" ? newValues : {};
  const changes = [];
  const unchanged = [];

  for (const key of collectKeys(oldV, newV)) {
    if (hide.has(key)) continue;
    const from = Object.prototype.hasOwnProperty.call(oldV, key) ? oldV[key] : undefined;
    const to = Object.prototype.hasOwnProperty.call(newV, key) ? newV[key] : undefined;
    const row = {
      key,
      label: humanizeField(key),
      from,
      to,
      kind: "unchanged",
    };
    if (valuesEqual(from, to)) {
      unchanged.push(row);
      continue;
    }
    if (isHiddenValue(from) && isHiddenValue(to)) row.kind = "hidden";
    else if (isEmpty(from) && !isEmpty(to)) row.kind = "added";
    else if (!isEmpty(from) && isEmpty(to)) row.kind = "removed";
    else row.kind = "changed";
    changes.push(row);
  }

  return { changes, unchanged };
}

export function describeAuditChange(row) {
  if (row?.kind === "hidden" || (isHiddenValue(row?.from) && isHiddenValue(row?.to))) {
    return { was: "hidden", now: "changed (details not shown)" };
  }
  const from = formatAuditValue(row?.from);
  const to = formatAuditValue(row?.to);
  if (row?.kind === "added") return { was: "empty (not filled)", now: to };
  if (row?.kind === "removed") return { was: from, now: "cleared" };
  return { was: from, now: to };
}

function sameAuditRecord(a, b) {
  if (!a || !b) return false;
  if ((a.table_name || "") !== (b.table_name || "")) return false;
  if (a.record_id && b.record_id) return String(a.record_id) === String(b.record_id);
  if (a.screening_id && b.screening_id) return a.screening_id === b.screening_id;
  if (a.enrollment_id && b.enrollment_id) return a.enrollment_id === b.enrollment_id;
  return false;
}

function findPairedSnapshot(rows, save, usedIds) {
  const saveTs = parseApiUtcDate(save.created_at)?.getTime() ?? 0;
  let best = null;
  let bestRank = Infinity;
  for (const other of rows) {
    if (!other || other.id === save.id || usedIds.has(other.id)) continue;
    const act = String(other.action || "").toUpperCase();
    if (act !== "UPDATE" && act !== "INSERT") continue;
    if (!sameAuditRecord(save, other)) continue;
    const otherTs = parseApiUtcDate(other.created_at)?.getTime() ?? 0;
    const dt = Math.abs(otherTs - saveTs);
    if (dt > 30_000) continue;
    const { changes } = diffAuditValues(other.old_values, other.new_values);
    const bucket = changes.length === 0 ? 2 : act === "INSERT" ? 1 : 0;
    const rank = bucket * 1_000_000 + dt;
    if (rank < bestRank) {
      bestRank = rank;
      best = other;
    }
  }
  return best;
}

/** Dummy Form A SAVE rows only stored {form, explicitly_saved}. Attach the real UPDATE/INSERT diffs. */
export function pairSaveRows(rows) {
  if (!Array.isArray(rows) || rows.length === 0) return rows || [];
  const usedIds = new Set();
  const patched = new Map();
  for (const row of rows) {
    if (String(row?.action || "").toUpperCase() !== "SAVE") continue;
    const { changes } = diffAuditValues(row.old_values, row.new_values);
    if (changes.length > 0) continue;
    const paired = findPairedSnapshot(rows, row, usedIds);
    if (!paired) continue;
    usedIds.add(paired.id);
    patched.set(row.id, {
      ...row,
      old_values: paired.old_values,
      new_values: paired.new_values,
    });
  }
  return rows
    .filter((row) => !usedIds.has(row.id))
    .map((row) => patched.get(row.id) || row);
}

export function summarizeAuditChanges(changes, { action, limit = 3 } = {}) {
  const act = String(action || "").toUpperCase();
  if (act === "SOFT_DELETE") return "Record deleted";
  if (act === "OVERRIDE_UNLOCK" && (!changes || changes.length === 0)) {
    return "Day unlocked for correction";
  }
  if (!changes || changes.length === 0) {
    if (act === "INSERT") return "Form created";
    if (act === "SAVE") return "Saved — no answers changed";
    return "No answers changed";
  }
  if (act === "SAVE") {
    const names = changes.map((c) => c.label);
    if (names.length <= limit) return names.join(", ");
    return `${names.slice(0, limit).join(", ")} +${names.length - limit} more`;
  }
  if (act === "INSERT") {
    return `Created · ${changes.length} field${changes.length === 1 ? "" : "s"} set`;
  }
  const names = changes.map((c) => c.label);
  if (names.length <= limit) return names.join(", ");
  return `${names.slice(0, limit).join(", ")} +${names.length - limit} more`;
}
