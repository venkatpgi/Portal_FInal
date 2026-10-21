/** Mother's / husband's names may not contain numbers (PI 2026-10-18):
 * twins are recorded with Birth type / Birth order, not "T1" / "T2" in the
 * name. The server applies the same rule (backend/identity_rules.py). */
export const PERSON_NAME_FIELDS = ["mother_first_name", "mother_surname", "husband_first_name", "husband_surname"];

export function stripDigits(value) {
  return String(value ?? "").replace(/[0-9]/g, "");
}

/** First letter of each word capital, remaining letters small.
 *  "RAJNSJ" → "Rajnsj", "B/o asdasdasd" → "B/o Asdasdasd". */
export function toPersonNameCase(value) {
  const s = String(value ?? "");
  if (!s) return s;
  return s.replace(/[^\s]+/g, (word) => {
    const lower = word.toLocaleLowerCase();
    if (lower === "b/o") return "B/o";
    return lower.replace(/(^|[-'.])(\p{L})/gu, (_, sep, ch) => sep + ch.toLocaleUpperCase());
  });
}
