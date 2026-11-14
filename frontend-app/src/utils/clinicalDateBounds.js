/** Calendar-day and birth-clock bounds shared by Forms B/D/E and DMS. */

import { combineDateAndTime, parseDateOnly, toDateOnlyValue } from "./datetime";

/** Form B randomisation: date of birth or the next calendar day only. */
export const RANDOMISATION_MAX_DAYS_AFTER_DOB = 1;

function startOfLocalDay(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function todayStart(now = new Date()) {
  return startOfLocalDay(now);
}

export function isCalendarDateAfterToday(ymd, now = new Date()) {
  const d = parseDateOnly(ymd);
  if (!d) return false;
  return startOfLocalDay(d).getTime() > todayStart(now).getTime();
}

export function isCalendarDateBefore(ymd, minYmd) {
  const d = parseDateOnly(ymd);
  const m = parseDateOnly(minYmd);
  if (!d || !m) return false;
  return startOfLocalDay(d).getTime() < startOfLocalDay(m).getTime();
}

export function isCalendarDateAfter(ymd, maxYmd) {
  const d = parseDateOnly(ymd);
  const m = parseDateOnly(maxYmd);
  if (!d || !m) return false;
  return startOfLocalDay(d).getTime() > startOfLocalDay(m).getTime();
}

export function addCalendarDaysYmd(ymd, days) {
  const d = parseDateOnly(ymd);
  if (!d) return null;
  return toDateOnlyValue(
    new Date(d.getFullYear(), d.getMonth(), d.getDate() + Number(days)),
  );
}

/** Latest selectable randomisation date: min(DOB + 1 day, today). */
export function randomisationDateMaxYmd(dobYmd, now = new Date()) {
  const dob = parseDateOnly(dobYmd);
  if (!dob) return null;
  const next = new Date(
    dob.getFullYear(),
    dob.getMonth(),
    dob.getDate() + RANDOMISATION_MAX_DAYS_AFTER_DOB,
  );
  const today = todayStart(now);
  const cap = next.getTime() < today.getTime() ? next : today;
  if (cap.getTime() < dob.getTime()) return toDateOnlyValue(dob);
  return toDateOnlyValue(cap);
}

export function calendarDateError(ymd, { minYmd, maxYmd, now = new Date() } = {}) {
  if (!ymd) return null;
  if (isCalendarDateAfterToday(ymd, now)) return "Future date not allowed";
  if (minYmd && isCalendarDateBefore(ymd, minYmd)) {
    return "Cannot be before date of birth";
  }
  if (maxYmd && isCalendarDateAfter(ymd, maxYmd)) {
    return "Outside the allowed date range";
  }
  return null;
}

/** Date of administration / completion: any calendar day from DOB through today. */
export function dobOnwardMinDate(dobYmd) {
  return parseDateOnly(dobYmd) || undefined;
}

export function dobOnwardMaxDate(now = new Date()) {
  return todayStart(now);
}

export function randomisationDateError(ymd, dobYmd, now = new Date()) {
  if (!ymd) return null;
  if (!dobYmd) return "Select date of birth first";
  const maxYmd = randomisationDateMaxYmd(dobYmd, now);
  const err = calendarDateError(ymd, { minYmd: dobYmd, maxYmd, now });
  if (!err) return null;
  if (err === "Future date not allowed" || err === "Cannot be before date of birth") {
    return err;
  }
  return "Must be date of birth or the next day";
}

/** Latest HH:MM:SS allowed for a birth on [dobYmd]. Past days: 23:59:59. Today: now. */
export function maxBirthClockHms(dobYmd, now = new Date()) {
  const dob = parseDateOnly(dobYmd);
  if (!dob) return { hour: 23, minute: 59, second: 59 };
  const dobDay = startOfLocalDay(dob).getTime();
  const today = todayStart(now).getTime();
  if (dobDay < today) return { hour: 23, minute: 59, second: 59 };
  if (dobDay > today) return { hour: 0, minute: 0, second: 0 };
  return { hour: now.getHours(), minute: now.getMinutes(), second: now.getSeconds() };
}

export function birthDateTime(dobYmd, timeHms) {
  const d = parseDateOnly(dobYmd);
  if (!d || !timeHms) return null;
  const m = String(timeHms).trim().match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?/);
  if (!m) return null;
  d.setHours(Number(m[1]), Number(m[2]), Number(m[3] || 0), 0);
  return d;
}

export function isBirthDateTimeInFuture(dobYmd, timeHms, now = new Date()) {
  const dt = birthDateTime(dobYmd, timeHms);
  if (!dt) return false;
  return dt.getTime() > now.getTime();
}

export function isDateTimeBeforeBirth(dateYmd, timeHm, birth) {
  const dt = combineDateAndTime(dateYmd, timeHm);
  if (!dt || !birth) return false;
  return dt.getTime() < birth.getTime();
}
