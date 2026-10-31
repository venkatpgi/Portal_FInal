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
