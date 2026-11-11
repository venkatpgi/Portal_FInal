/** Shared MML → helper mirror sync (set + clear when MML data removed). */

/** Helper 4 GI / Helper 5 renal: latest DMS 5.7.A kg only once ≥ birth kg. */
export function effectiveFeedWeightKg({ dmsWeightKg, birthWeightGrams } = {}) {
  const birthKg =
    birthWeightGrams != null && Number(birthWeightGrams) > 0
      ? Number(birthWeightGrams) / 1000
      : null;
  const dms =
    dmsWeightKg != null && Number.isFinite(Number(dmsWeightKg))
      ? Number(dmsWeightKg)
      : null;
  if (dms != null && birthKg != null) {
    return dms >= birthKg ? dms : birthKg;
  }
  return birthKg ?? dms;
}

export const URINE_WINDOW_HOURS_8AM_2PM = 6;
export const URINE_WINDOW_HOURS_2PM_8PM = 6;
export const URINE_WINDOW_HOURS_8PM_8AM = 12;

/** ml/kg/hr = volume_ml ÷ (effective kg × window hours), 2 decimals. */
export function urineMlPerKgHr(volumeMl, effectiveWeightKg, hours) {
  const ml = volumeMl === null || volumeMl === undefined || volumeMl === ""
    ? NaN
    : Number(volumeMl);
  const kg = Number(effectiveWeightKg);
  const h = Number(hours);
  if (!Number.isFinite(ml) || !Number.isFinite(kg) || !(kg > 0) || !Number.isFinite(h) || !(h > 0)) {
    return null;
  }
  return Math.round((ml / (kg * h)) * 100) / 100;
}

/** Daily urine rate over recorded windows only (skips blank / Not Recorded). */
export function urineTotalMlPerKgHr(amMl, pmMl, nightMl, effectiveWeightKg) {
  let ml = 0;
  let hours = 0;
  const add = (v, h) => {
    if (v === null || v === undefined || v === "") return;
    const n = Number(v);
    if (!Number.isFinite(n)) return;
    ml += n;
    hours += h;
  };
  add(amMl, URINE_WINDOW_HOURS_8AM_2PM);
  add(pmMl, URINE_WINDOW_HOURS_2PM_8PM);
  add(nightMl, URINE_WINDOW_HOURS_8PM_8AM);
  if (!(hours > 0)) return null;
  return urineMlPerKgHr(ml, effectiveWeightKg, hours);
}

// Plausible range, same as backend/value_ranges.py (PI 2026-11-11).
export const URINE_REFUSE_ABOVE = 15;
export const URINE_HIGH_ABOVE = 6;
export const URINE_LOW_BELOW = 0.5;

/** Warning text for one window's ml/kg/hr, or null when in range. */
export function urineRateWarning(rate) {
  if (rate === null || rate === undefined || rate === "") return null;
  const r = Number(rate);
  if (!Number.isFinite(r)) return null;
  if (r > URINE_REFUSE_ABOVE) {
    return { level: "impossible", text: `More than ${URINE_REFUSE_ABOVE} ml/kg/hr is not possible: enter the ml passed in this window. This value will not save.` };
  }
  if (r > URINE_HIGH_ABOVE) {
    return { level: "high", text: `High (over ${URINE_HIGH_ABOVE} ml/kg/hr): check the bedside chart. If it is right, it will be confirmed in Data queries.` };
  }
  if (r < URINE_LOW_BELOW) {
    return { level: "low", text: `Low (under ${URINE_LOW_BELOW} ml/kg/hr): check the bedside chart. If it is right, it will be confirmed in Data queries.` };
  }
  return null;
}

export function formatUrineMlPerKgHr(v) {
  if (v == null || !Number.isFinite(Number(v))) return null;
  const hundredths = Math.round(Number(v) * 100);
  if (hundredths % 100 === 0) return String(hundredths / 100);
  if (hundredths % 10 === 0) return (hundredths / 100).toFixed(1);
  return (hundredths / 100).toFixed(2);
}

export function mmlIsEmptyField(v) {
  return v === null || v === undefined || v === "";
}

/** Mirror 5.6.A / 5.1.B Y/N onto helper fields.
 *  DMS may set Yes when the sheet has a value, and may clear only a Yes it
 *  wrote itself. A Yes or No the nurse chose on the helper form stays. */
export function mmlSyncTransfusionYnFromMml(current, mmlHas, wasAutofilled) {
  if (current === false) {
    return { next: current, autofilled: false, changed: false };
  }
  if (mmlHas) {
    if (current == null || wasAutofilled) {
      const changed = current !== true;
      return { next: true, autofilled: true, changed };
    }
    return { next: current, autofilled: false, changed: false };
  }
  if (current === true && wasAutofilled) {
    return { next: null, autofilled: false, changed: true };
  }
  return { next: current, autofilled: false, changed: false };
}

/**
 * @param {object} opts
 * @param {string|null|undefined} opts.current
 * @param {boolean} [opts.blockedByNotDone]
 * @param {boolean} [opts.wasAutofilled]
 * @param {boolean} [opts.stillMatchesLastAuto]
 * @param {(current: *, entries: *) => boolean} [opts.looksSourced]
 * @param {*} [opts.entryValuesForSourced]
 * @param {string|null|undefined} opts.mmlValue — null/"" = no MML aggregate → clear when allowed
 * @param {boolean} [opts.force] — refresh from MML even when prior partial sync left stale values
 */
export function mmlSyncAggregateFieldFromMml({
  current,
  blockedByNotDone = false,
  wasAutofilled = false,
  stillMatchesLastAuto = false,
  looksSourced = () => false,
  entryValuesForSourced = null,
  mmlValue = null,
  force = false,
}) {
  if (blockedByNotDone) {
    return {
      nextValue: current == null ? "" : String(current),
      autofilled: wasAutofilled,
      changed: false,
    };
  }
  const cur = current == null ? "" : String(current).trim();
  const isEmpty = cur === "";
  const canTouch =
    force ||
    isEmpty ||
    stillMatchesLastAuto ||
    wasAutofilled ||
    looksSourced(current, entryValuesForSourced);

  const mml = mmlValue == null ? "" : String(mmlValue).trim();
  const hasMml = mml !== "";

  if (hasMml) {
    if (!canTouch) {
      return { nextValue: cur, autofilled: wasAutofilled, changed: false };
    }
    if (cur === mml) {
      return {
        nextValue: mml,
        autofilled: true,
        changed: !wasAutofilled,
      };
    }
    return { nextValue: mml, autofilled: true, changed: true };
  }

  if (isEmpty) {
    if (wasAutofilled) {
      return { nextValue: "", autofilled: false, changed: true };
    }
    return { nextValue: "", autofilled: false, changed: false };
  }
  if (!canTouch) {
    return { nextValue: cur, autofilled: wasAutofilled, changed: false };
  }
  return { nextValue: "", autofilled: false, changed: true };
}

const GLUCOSE_SENTINELS = new Set(["Not Tested", "Not Low", "Not High", "0"]);

export function mmlGlucoseStaleWhenNoReadings(current, fieldKey, readings) {
  if (readings.length) return false;
  const t = current == null ? "" : String(current).trim();
  if (!t) return false;
  if (GLUCOSE_SENTINELS.has(t)) return false;
  if (fieldKey === "hypoglycemia_episodes" && t === "0") return false;
  return true;
}

export function mmlSyncGlucoseFieldFromMml({
  current,
  wasAutofilled = false,
  stillMatchesLastAuto = false,
  force = false,
  fieldKey,
  readings,
  computedValue,
  looksSourced,
}) {
  const cur = current == null ? "" : String(current).trim();
  const next = computedValue == null ? "" : String(computedValue).trim();
  const canTouch =
    force ||
    mmlIsEmptyField(current) ||
    stillMatchesLastAuto ||
    wasAutofilled ||
    looksSourced(current, fieldKey, readings) ||
    mmlGlucoseStaleWhenNoReadings(current, fieldKey, readings);

  if (!canTouch) {
    return { nextValue: cur, autofilled: wasAutofilled, changed: false };
  }
  if (cur === next) {
    return { nextValue: next, autofilled: true, changed: !wasAutofilled };
  }
  return { nextValue: next, autofilled: true, changed: true };
}
