import { birthMoment, dayOfLife, dayOfLifeSpan, describeDayOfLife, dayOfLifeSwitchOn } from "./dayOfLife";

const birth = birthMoment("2026-11-01", "22:15:00");

test("day 1 of life is birth to under 24 h", () => {
  expect(dayOfLife(birth, new Date("2026-11-02T22:14:00"))).toBe(1);
  expect(dayOfLife(birth, new Date("2026-11-02T22:15:00"))).toBe(2);
  expect(dayOfLife(birth, new Date("2026-11-01T21:00:00"))).toBeNull();
});

test("needs both date and time of birth", () => {
  expect(birthMoment("2026-11-01", "")).toBeNull();
  expect(birthMoment("", "10:00")).toBeNull();
});

test("helper day window 08:00 to 08:00 shows the switch", () => {
  const span = dayOfLifeSpan(birth, new Date("2026-11-02T08:00:00"), new Date("2026-11-03T08:00:00"));
  expect(span.startDay).toBe(1);
  expect(span.switches.map(s => s.day)).toEqual([2]);
  expect(describeDayOfLife(span)).toBe("Day 1 of life → Day 2 from 10:15 PM");
});

test("helper day 1 starts at birth", () => {
  const span = dayOfLifeSpan(birth, null, new Date("2026-11-02T08:00:00"));
  expect(describeDayOfLife(span, { withDate: true })).toBe("Born 01-11-2026 10:15 PM · Day 1 of life");
});

test("DMS sheet switch time", () => {
  expect(dayOfLifeSwitchOn(birth, "2026-11-03")).toEqual({ time: "22:15", day: 3 });
  expect(dayOfLifeSwitchOn(birth, "2026-11-01")).toBeNull();
});
