// Form I asks cause, date and time of death at up to seven places. They are
// one death, so what is entered once carries to every place answered Yes
// (PI 2026-10-31). A place whose text was changed by hand keeps it.
const SECTIONS = [
  ["mortality_7_days", "mortality_7d"],
  ["mortality_28_days", "mortality_28d"],
  ["death36", "death36"],
  ["death40", "death40"],
  ["death44", "death44"],
  ["mortality_in_hospital", "mortality_hospital"],
  ["mortality_after_discharge", "mortality_after_discharge"],
];
const DETAILS = ["cause", "date", "time"];

const text = (v) => (v === null || v === undefined ? "" : v);

/** The fields to change after prev -> next, or {} if none. */
export function deathDetailUpdates(prev, next) {
  const yes = SECTIONS.filter(([answer]) => next[answer] === "Yes").map(([, prefix]) => prefix);
  const updates = {};
  DETAILS.forEach((detail) => {
    const keys = yes.map((prefix) => `${prefix}_${detail}`);
    const changed = keys.find((k) => text(next[k]) !== text(prev[k]));
    if (changed) {
      const was = text(prev[changed]);
      const now = text(next[changed]);
      keys.forEach((k) => {
        const v = text(next[k]);
        if (k !== changed && ((v === "" && now !== "") || (was !== "" && v === was))) updates[k] = now;
      });
      return;
    }
    const source = keys.map((k) => text(next[k])).find((v) => v !== "");
    if (source) keys.forEach((k) => { if (text(next[k]) === "") updates[k] = source; });
  });
  return updates;
}

const AGE_FIELDS = [
  ["mortality_7d", "age_hrs"],
  ["mortality_28d", "age_days"],
  ["death36", "age_days"],
  ["death40", "age_days"],
  ["death44", "age_days"],
  ["mortality_hospital", "age_days"],
  ["mortality_after_discharge", "age_days"],
];

/** Age at death. Uses both times when both are known, otherwise the dates alone. */
export function ageAtDeath(dob, tob, date, time, unit) {
  if (!dob || !date) return "";
  const useTimes = !!(tob && time);
  const birth = new Date(`${String(dob).slice(0, 10)}T${useTimes ? String(tob).slice(0, 5) : "00:00"}:00`);
  const death = new Date(`${String(date).slice(0, 10)}T${useTimes ? String(time).slice(0, 5) : "00:00"}:00`);
  if (isNaN(birth) || isNaN(death)) return "";
  const hours = (death - birth) / 3600000;
  if (hours < 0) return "";
  return unit === "age_hrs" ? Math.round(hours) : Math.floor(hours / 24);
}

/** The age fields that differ from what their dates and times give. */
export function ageUpdates(form) {
  const updates = {};
  AGE_FIELDS.forEach(([prefix, unit]) => {
    if (!form.dob || !form[`${prefix}_date`]) return;
    const age = ageAtDeath(form.dob, form.tob, form[`${prefix}_date`], form[`${prefix}_time`], unit);
    if (String(age) !== String(text(form[`${prefix}_${unit}`]))) updates[`${prefix}_${unit}`] = age;
  });
  return updates;
}
