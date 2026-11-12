/** Caffeine citrate: loading is a single mg/kg dose; maintenance is mg/kg/day. */

export function caffeineMgPerKg(absMg, birthWeightG) {
  const n = Number(absMg);
  const kg = Number(birthWeightG) / 1000;
  if (!Number.isFinite(n) || !Number.isFinite(kg) || kg <= 0) return null;
  return n / kg;
}

export function typicalCaffeineLoadingMg(birthWeightG, mgPerKg = 20) {
  const kg = Number(birthWeightG) / 1000;
  if (!Number.isFinite(kg) || kg <= 0) return null;
  return mgPerKg * kg;
}

export function formatCaffeineMgPerKg(absMg, birthWeightG, digits = 2) {
  const mpk = caffeineMgPerKg(absMg, birthWeightG);
  return mpk == null ? "" : mpk.toFixed(digits);
}
