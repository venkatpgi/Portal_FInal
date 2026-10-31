import { ageAtDeath, ageUpdates, deathDetailUpdates as up } from "./deathDetails";

const yes = { mortality_7_days: "Yes", mortality_28_days: "Yes", death36: "Yes", mortality_in_hospital: "Yes" };

test("typing carries every keystroke, so no half-typed text is left behind", () => {
  const a = { ...yes, mortality_7d_cause: "S" };
  expect(up(yes, a)).toEqual({ mortality_28d_cause: "S", death36_cause: "S", mortality_hospital_cause: "S" });
  const b = { ...a, mortality_28d_cause: "S", death36_cause: "S", mortality_hospital_cause: "S" };
  const c = { ...b, mortality_7d_cause: "Sh" };
  expect(up(b, c)).toEqual({ mortality_28d_cause: "Sh", death36_cause: "Sh", mortality_hospital_cause: "Sh" });
});

test("a place edited differently keeps its own text", () => {
  const b = { ...yes, mortality_7d_cause: "Shock", death36_cause: "Shock", mortality_28d_cause: "Own" };
  const c = { ...b, mortality_7d_cause: "Septic shock" };
  expect(up(b, c)).toEqual({ death36_cause: "Septic shock", mortality_hospital_cause: "Septic shock" });
});

test("a place answered No or left blank gets nothing", () => {
  const p = { mortality_7_days: "Yes", death40: "No" };
  expect(up(p, { ...p, mortality_7d_time: "10:00" })).toEqual({});
});

test("a place answered Yes later picks up what is already there", () => {
  const p = { mortality_7_days: "Yes", mortality_7d_date: "2026-10-30" };
  const n = { ...p, death36: "Yes" };
  expect(up(p, n)).toEqual({ death36_date: "2026-10-30" });
});

test("clearing clears the matching places and does not refill", () => {
  const b = { ...yes, mortality_7d_time: "10:00", mortality_28d_time: "10:00" };
  const c = { ...b, mortality_7d_time: "" };
  expect(up(b, c)).toEqual({ mortality_28d_time: "" });
});

test("age uses date and time of birth and of death", () => {
  expect(ageAtDeath("2026-10-28", "22:30:00", "2026-10-30", "14:00", "age_hrs")).toBe(40);
  expect(ageAtDeath("2026-10-28", "22:30:00", "2026-10-30", "14:00", "age_days")).toBe(1);
  expect(ageAtDeath("2026-10-28", "06:00:00", "2026-10-30", "14:00", "age_hrs")).toBe(56);
  expect(ageAtDeath("2026-10-28", "06:00:00", "2026-10-30", "14:00", "age_days")).toBe(2);
});

test("a missing time falls back to the dates, and death before birth gives blank", () => {
  expect(ageAtDeath("2026-10-28", "", "2026-10-30", "14:00", "age_hrs")).toBe(48);
  expect(ageAtDeath("2026-10-28", "06:00", "2026-10-30", "", "age_hrs")).toBe(48);
  expect(ageAtDeath("2026-10-30", "14:00", "2026-10-30", "06:00", "age_hrs")).toBe("");
});

test("ageUpdates settles: a form already right needs no change", () => {
  const f = { dob: "2026-10-28", tob: "06:00:00", mortality_7d_date: "2026-10-30", mortality_7d_time: "14:00", mortality_7d_age_hrs: 48 };
  expect(ageUpdates(f)).toEqual({ mortality_7d_age_hrs: 56 });
  expect(ageUpdates({ ...f, mortality_7d_age_hrs: 56 })).toEqual({});
});
