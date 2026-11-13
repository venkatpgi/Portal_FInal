// Plausible ranges approved by the Global PI 2026-11-12. Same table as
// backend/range_rules.py RULES: keep the two in step.
//   confirm range: outside it the value saves with a warning (data query)
//   refuse limits: outside them the server refuses the save
// `names` are the input name attributes that carry the field; inputs without
// a name use data-range="<key>" (helpers, DMS).

const R = (key, label, unit, confirmLo, confirmHi, refuseLo, refuseHi, names = []) =>
  ({ key, label, unit, confirmLo, confirmHi, refuseLo, refuseHi, names });

export const RANGE_RULES = [
  // Form B
  R("birth_weight", "Birth weight", "g", 400, 3000, 300, 4000, ["birth_weight"]),
  R("spo2_5min", "SpO₂ at 5 min", "%", 40, null, 0, 100, ["spo2_5min"]),
  R("cord_ph", "Cord pH", "", 6.8, 7.5, 6.5, 7.8, ["cord_ph"]),
  R("cord_pco2", "Cord pCO₂", "mmHg", 25, 90, 10, 150, ["cord_pco2"]),
  R("cord_sbe", "Cord base excess", "mmol/L", -20, 5, -30, 10, ["cord_sbe"]),
  R("tpiece_pip", "T-piece PIP", "cmH₂O", 12, 30, 5, 40, ["tpiece_pip"]),
  R("tpiece_peep", "T-piece PEEP", "cmH₂O", 4, 8, 3, 15, ["tpiece_peep"]),
  R("tpiece_flow", "T-piece gas flow", "L/min", 4, 12, 1, 15, ["tpiece_flow"]),
  // Form C
  R("mother_age", "Mother's age", "years", 16, 45, 12, 60, ["mother_age"]),
  // Form D
  R("d_fio2", "FiO₂", "%", null, null, 21, 100, ["fio2_percent", "max_fio2_1hr"]),
  R("d_cpap", "CPAP pressure", "cmH₂O", 4, 10, 0, 15, ["cpap_cm"]),
  R("d_surfactant", "Surfactant dose", "mg/kg", 100, 200, 50, 300, ["surfactant_dose"]),
  // Form E
  R("e_temp", "Temperature", "°C", 35, 38, 25, 42, ["temp_dr", "temp_skin", "temp_axillary"]),
  R("e_fio2", "FiO₂", "%", null, null, 21, 100, ["transport_fio2", "nicu_fio2"]),
  R("e_cpap", "CPAP", "cmH₂O", 4, 10, 0, 15, ["transport_cpap", "nicu_cpap"]),
  R("e_peep", "PEEP", "cmH₂O", 4, 10, 0, 15, ["transport_peep", "nicu_peep"]),
  R("e_pip", "PIP", "cmH₂O", 12, 30, 5, 40, ["transport_pip", "nicu_pip"]),
  R("e_map", "MAP (HFO)", "cmH₂O", 6, 18, 0, 30, ["transport_map", "nicu_map"]),
  // DMS
  R("dms_weight", "Weight", "g", null, null, 300, 6000),
  R("dms_temp", "Axillary temperature", "°C", 35, 37.8, 24, 42),
  R("dms_sbp", "Systolic BP", "mmHg", 30, 110, 15, 140),
  R("dms_dbp", "Diastolic BP", "mmHg", 10, 75, 5, 100),
  R("dms_map", "Mean BP", "mmHg", 15, 85, 10, 100),
  R("dms_glucose", "Glucose", "mg/dL", 20, 200, 5, 600),
  R("dms_ph", "pH", "", 6.8, 7.6, 6.5, 7.9),
  R("dms_paco2", "PaCO₂", "mmHg", 20, 100, 10, 150),
  R("dms_pao2", "PaO₂", "mmHg", 25, 200, 10, 600),
  // Helper 2
  R("h2_max_fio2", "Max FiO₂", "%", null, null, 21, 100),
  R("h2_max_flow", "Max gas flow", "L/min", null, 20, 0, 30),
  // Helper 4
  R("h4_feed", "Feed volume", "ml/kg/day", null, 200, 0, 300),
  R("h4_hb", "Haemoglobin", "g/dL", 7, 22, 3, 28),
  R("h4_tsb", "Peak TSB", "mg/dL", null, 25, 0, 40),
  // Helper 5
  R("h5_creatinine", "Serum creatinine", "mg/dL", 0.2, 2.0, 0.1, 6.0),
  R("h5_sodium", "Sodium", "mmol/L", 125, 155, 100, 190),
  R("h5_potassium", "Potassium", "mmol/L", 2.5, 7.5, 1.5, 10),
  R("h5_calcium", "Ionised calcium", "mmol/L", 0.6, 1.5, 0.4, 2.5),
  // Form H
  R("h_discharge_weight", "Discharge weight", "g", 1000, 4000, 800, 8000, ["discharge_weight"]),
];

export const RANGE_BY_KEY = Object.fromEntries(RANGE_RULES.map((r) => [r.key, r]));
export const RANGE_BY_NAME = Object.fromEntries(
  RANGE_RULES.flatMap((r) => r.names.map((n) => [n, r])),
);

const fmt = (n) => (Number.isInteger(n) ? String(n) : String(Math.round(n * 100) / 100));

function span(lo, hi) {
  if (lo != null && hi != null) return `${fmt(lo)}–${fmt(hi)}`;
  if (hi != null) return `up to ${fmt(hi)}`;
  if (lo != null) return `${fmt(lo)} or more`;
  return "";
}

/** { level: "impossible" | "high" | "low", text } or null. */
export function rangeCheck(rule, value) {
  if (!rule || value === null || value === undefined || String(value).trim() === "") return null;
  const v = Number(value);
  if (!Number.isFinite(v)) return null;
  const unit = rule.unit ? ` ${rule.unit}` : "";
  if ((rule.refuseLo != null && v < rule.refuseLo) || (rule.refuseHi != null && v > rule.refuseHi)) {
    return {
      level: "impossible",
      text: `${rule.label} ${fmt(v)}${unit} is not possible (allowed ${span(rule.refuseLo, rule.refuseHi)}${unit}). It will not save: check the value and its unit.`,
    };
  }
  const hi = rule.confirmHi != null && v > rule.confirmHi;
  const lo = rule.confirmLo != null && v < rule.confirmLo;
  if (hi || lo) {
    return {
      level: hi ? "high" : "low",
      text: `${rule.label} ${fmt(v)}${unit} is ${hi ? "high" : "low"} (expected ${span(rule.confirmLo, rule.confirmHi)}${unit}). Check the chart; if it is right, it will be confirmed in Data queries.`,
    };
  }
  return null;
}

/** Numbers in a typed text box ("45-60" is a range, not 45 and -60). */
export function textNumbers(value) {
  if (value === null || value === undefined) return [];
  const s = String(value).replace(/[–—]/g, " ");
  const out = [];
  const re = /-?\d+(?:\.\d+)?/g;
  let m;
  while ((m = re.exec(s))) {
    let tok = m[0];
    if (tok.startsWith("-") && m.index > 0 && /\d/.test(s[m.index - 1])) tok = tok.slice(1);
    out.push(Number(tok));
  }
  return out;
}

/** Worst result across the numbers in one input. */
export function rangeCheckText(rule, value) {
  const order = { impossible: 0, high: 1, low: 1 };
  return textNumbers(value)
    .map((n) => rangeCheck(rule, n))
    .filter(Boolean)
    .sort((a, b) => order[a.level] - order[b.level])[0] || null;
}
