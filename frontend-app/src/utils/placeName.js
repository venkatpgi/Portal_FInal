/** Village / city / tehsil: letters only (no digits). */

const PLACE_CHARS = /^[A-Za-z .'\-/]*$/;

export function placeNameError(value, { required = false, label = "This field" } = {}) {
  const v = String(value ?? "").trim();
  if (!v) return required ? `${label} required` : "";
  if (/\d/.test(v)) return "Letters only — numbers are not allowed";
  if (!PLACE_CHARS.test(v)) return "Letters, spaces and hyphens only";
  return "";
}

export function isPlaceNameInput(value) {
  return PLACE_CHARS.test(String(value ?? ""));
}
