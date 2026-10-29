/** Full randomised enrollment: site-letter-serial e.g. 01-A-452 */
export const COMPLETE_ENROLLMENT_RE = /^\d{2}-[A-D]-\d{3}$/;

/** Non-randomised / no-PPV placeholder tied to a screening. */
export const isNrEnrollmentId = (value) =>
  /^NR-.+/i.test(String(value || "").trim());

/** NR- placeholder of baby n of one mother (twins: baby 1 = NR-<sid>,
 *  baby 2 = NR-<sid>-2; backend babies.nr_enrollment_id). */
export const nrEnrollmentId = (screeningId, babyNumber = 1) =>
  Number(babyNumber) > 1 ? `NR-${screeningId}-${Number(babyNumber)}` : `NR-${screeningId}`;

/** Safe to persist, route on, and use as Form C/D/E key. */
export const isUsableEnrollmentId = (value) => {
  const v = String(value || "").trim();
  if (!v || v === "undefined" || v === "null") return false;
  return COMPLETE_ENROLLMENT_RE.test(v) || isNrEnrollmentId(v);
};

/** Site-prefix stub shown while typing (e.g. 01- or 01-A-). */
export const isIncompleteEnrollmentId = (value) => {
  const v = String(value || "").trim();
  if (!v || isUsableEnrollmentId(v)) return false;
  return /^\d{2}-([A-D]-?)?$/.test(v) || /^\d{2}-[A-D]-\d{1,2}$/.test(v);
};
