import {
  calendarDateError,
  isBirthDateTimeInFuture,
  isCalendarDateAfterToday,
  isCalendarDateBefore,
  isDateTimeBeforeBirth,
  maxBirthClockHms,
  randomisationDateError,
  randomisationDateMaxYmd,
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

test("randomisation date is only DOB or the next calendar day, never future", () => {
  const now = new Date(2026, 10, 14, 10, 0, 0);
  expect(randomisationDateMaxYmd("2026-11-14", now)).toBe("2026-11-14");
  expect(randomisationDateMaxYmd("2026-11-13", now)).toBe("2026-11-14");
  expect(randomisationDateMaxYmd("2026-11-01", now)).toBe("2026-11-02");
  expect(randomisationDateError("2026-11-14", "2026-11-14", now)).toBe(null);
  expect(randomisationDateError("2026-11-13", "2026-11-13", now)).toBe(null);
  expect(randomisationDateError("2026-11-14", "2026-11-13", now)).toBe(null);
  expect(randomisationDateError("2026-11-15", "2026-11-14", now)).toBe(
    "Future date not allowed",
  );
  expect(randomisationDateError("2026-11-03", "2026-11-01", now)).toBe(
    "Must be date of birth or the next day",
  );
  expect(randomisationDateError("2026-10-31", "2026-11-01", now)).toBe(
    "Cannot be before date of birth",
  );
});

test("time of birth cannot be later than now on the same calendar day", () => {
  const now = new Date(2026, 10, 14, 13, 40, 0);
  expect(maxBirthClockHms("2026-11-14", now)).toEqual({ hour: 13, minute: 40, second: 0 });
  expect(maxBirthClockHms("2026-11-13", now)).toEqual({ hour: 23, minute: 59, second: 59 });
  expect(isBirthDateTimeInFuture("2026-11-14", "13:40:00", now)).toBe(false);
  expect(isBirthDateTimeInFuture("2026-11-14", "14:00:00", now)).toBe(true);
  expect(isBirthDateTimeInFuture("2026-11-13", "23:59:00", now)).toBe(false);
});

test("DMS times before birth on day 1 are rejected", () => {
  const birth = birthMoment("2026-11-12", "15:00");
  expect(isDateTimeBeforeBirth("2026-11-12", "08:00", birth)).toBe(true);
  expect(isDateTimeBeforeBirth("2026-11-12", "15:00", birth)).toBe(false);
  expect(isDateTimeBeforeBirth("2026-11-12", "16:00", birth)).toBe(false);
});
