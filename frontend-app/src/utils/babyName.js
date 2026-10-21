import { toPersonNameCase } from "./personName";

/**
 * NICU shorthand for the baby, e.g. "B/o Seema".
 * Prefers an explicit baby_name; otherwise uses the mother's first name.
 */

function usableName(value) {
  const s = String(value || "").trim();
  if (!s) return "";
  const upper = s.toUpperCase();
  if (upper === "DRAFT" || upper === "NAME PENDING") return "";
  return toPersonNameCase(s);
}

export function formatBabyOfLabel(pii) {
  if (!pii) return "";
  const baby = usableName(pii.baby_name);
  if (baby) {
    const m = baby.match(/^(?:baby\s+of|b\/o)\s+(.+)$/i);
    if (m) {
      const rest = usableName(m[1]);
      return rest ? `B/o ${rest}` : "";
    }
    return baby;
  }
  const mother = formatMotherFullName(pii);
  if (mother) return `B/o ${mother}`;
  return "";
}

/** Mother's first name only (no B/o). */
export function formatMotherFirstName(pii) {
  return usableName(pii?.mother_first_name);
}

function formatMotherFullName(pii) {
  return [formatMotherFirstName(pii), usableName(pii?.mother_surname)]
    .filter(Boolean)
    .join(" ");
}

/**
 * View Entries name column:
 * Form A only → mother's name (each word capitalised, e.g. Shobha Devi)
 * Form B started (draft or saved) → "B/o {mother name}"
 */
export function formatParticipantListName(pii, { formBStarted } = {}) {
  const mother = formatMotherFullName(pii);
  if (!mother) return "";
  if (formBStarted) return `B/o ${mother}`;
  return mother;
}
