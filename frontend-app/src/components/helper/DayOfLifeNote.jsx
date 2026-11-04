import React from "react";
import { calendarDateForNicuDay, NICU_DAY_GRACE_HOUR } from "../../utils/datetime";
import { birthMoment, dayOfLifeSpan, describeDayOfLife } from "../../utils/dayOfLife";

const pad = (n) => String(n).padStart(2, "0");

/** Helper 2 / 4 / 5 day header (PI 2026-11-03): the baby's day of life over
 *  this Helper day, which runs 08:00 to 08:00 (Day 1 from birth). Display
 *  only; the Helper day number is unchanged. */
export default function DayOfLifeNote({ dob, tob, day }) {
  if (!dob || !day) return null;
  const birth = birthMoment(dob, tob);
  if (!birth) return <p className="rcn-dol-note">Day of life: time of birth not entered in Form B.</p>;
  const date = calendarDateForNicuDay(dob, day);
  if (!date) return null;
  const at = (ymd) => new Date(`${ymd}T${pad(NICU_DAY_GRACE_HOUR)}:00:00`);
  const from = day === 1 ? null : at(date);
  const to = new Date(at(date).getTime() + 86400000);
  const span = dayOfLifeSpan(birth, from, to);
  if (!span) return null;
  return <p className="rcn-dol-note">Age: {describeDayOfLife(span, { withDate: true })}</p>;
}
