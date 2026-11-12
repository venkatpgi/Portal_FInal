/** Calendar-day and birth-clock bounds shared by Forms B/D/E and DMS. */

import { combineDateAndTime, parseDateOnly } from "./datetime";

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

export function calendarDateError(ymd, { minYmd, now = new Date() } = {}) {
  if (!ymd) return null;
  if (isCalendarDateAfterToday(ymd, now)) return "Future date not allowed";
  if (minYmd && isCalendarDateBefore(ymd, minYmd)) {
    return "Cannot be before date of birth";
  }
  return null;
}

export function isDateTimeBeforeBirth(dateYmd, timeHm, birth) {
  const dt = combineDateAndTime(dateYmd, timeHm);
  if (!dt || !birth) return false;
  return dt.getTime() < birth.getTime();
}
