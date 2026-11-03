// Day of life from Form B date + time of birth (PI 2026-11-03): birth to
// under 24 h = Day 1 of life, 24 h to under 48 h = Day 2, and so on. Display
// only: Helper day numbers (Day 1 = date of birth, 08:00 boundary) and DMS
// sheet dates are unchanged.
import { formatTimeAmPm, formatDateToDDMMYYYY, toDateOnlyValue } from "./datetime";

const DAY_MS = 86400000;

/** Local Date of birth, or null without both date and time. */
export function birthMoment(dobYmd, tobHm) {
  const d = String(dobYmd || "").slice(0, 10);
  const t = String(tobHm || "").match(/^(\d{1,2}):(\d{2})/);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d) || !t) return null;
  const at = new Date(`${d}T${t[1].padStart(2, "0")}:${t[2]}:00`);
  return Number.isNaN(at.getTime()) ? null : at;
}

export function dayOfLife(birth, at) {
  if (!birth || !at || at < birth) return null;
  return Math.floor((at - birth) / DAY_MS) + 1;
}

/** Day of life over [from, to): { startDay, born, switches: [{ day, at }] }.
 *  from null = from birth. null if the window ends before birth. */
export function dayOfLifeSpan(birth, from, to) {
  if (!birth || !to || to <= birth) return null;
  const start = !from || from < birth ? birth : from;
  const switches = [];
  for (let k = Math.ceil((start - birth) / DAY_MS) || 1; ; k += 1) {
    const at = new Date(birth.getTime() + k * DAY_MS);
    if (at >= to) break;
    if (at > start) switches.push({ day: k + 1, at });
  }
  return { startDay: dayOfLife(birth, start), born: start === birth ? birth : null, switches };
}

const hm = (d) => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

/** "Day 2 of life → Day 3 from 10:15 PM"; withDate adds the date to each time. */
export function describeDayOfLife(span, { withDate = false } = {}) {
  if (!span) return "";
  const when = (d) => `${withDate ? `${formatDateToDDMMYYYY(toDateOnlyValue(d))} ` : ""}${formatTimeAmPm(hm(d))}`;
  const parts = [`${span.born ? `Born ${when(span.born)} · ` : ""}Day ${span.startDay} of life`];
  span.switches.forEach(s => parts.push(`Day ${s.day} from ${when(s.at)}`));
  return parts.join(" → ");
}

/** "HH:MM" at which the day of life changes on a calendar date, with the new day. */
export function dayOfLifeSwitchOn(birth, ymd) {
  if (!birth || !ymd) return null;
  const from = new Date(`${ymd}T00:00:00`);
  const span = dayOfLifeSpan(birth, from, new Date(from.getTime() + DAY_MS));
  const s = span && span.switches[0];
  return s ? { time: hm(s.at), day: s.day } : null;
}
