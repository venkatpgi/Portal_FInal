import {
  calendarDateError,
  isCalendarDateAfterToday,
  isCalendarDateBefore,
  isDateTimeBeforeBirth,
} from "./clinicalDateBounds";
import { birthMoment } from "./dayOfLife";

test("future calendar dates are rejected using local days, not UTC midnight", () => {
  const now = new Date(2026, 10, 12, 10, 30, 0);
  expect(isCalendarDateAfterToday("2026-11-12", now)).toBe(false);
  expect(isCalendarDateAfterToday("2026-11-22", now)).toBe(true);
  expect(calendarDateError("2026-11-22", { now })).toBe("Future date not allowed");
});

test("dates before birth are rejected", () => {
  expect(isCalendarDateBefore("2026-11-02", "2026-11-12")).toBe(true);
  expect(calendarDateError("2026-11-02", { minYmd: "2026-11-12" }))
    .toBe("Cannot be before date of birth");
  expect(calendarDateError("2026-11-12", { minYmd: "2026-11-12" })).toBe(null);
});

test("DMS times before birth on day 1 are rejected", () => {
  const birth = birthMoment("2026-11-12", "15:00");
  expect(isDateTimeBeforeBirth("2026-11-12", "08:00", birth)).toBe(true);
  expect(isDateTimeBeforeBirth("2026-11-12", "15:00", birth)).toBe(false);
  expect(isDateTimeBeforeBirth("2026-11-12", "16:00", birth)).toBe(false);
});
