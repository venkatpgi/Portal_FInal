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

/* ── This tab's patient (two-tab fix, PI 2026-11-03) ──
   current_enrollment_id / current_screening_id in localStorage are shared by
   every tab of the site. A page whose address names a baby (/vs6-1/01-D-901)
   is about that baby whatever another tab stored; reacting to another tab's
   write by writing back made two tabs on different babies flip the stored id
   without end (~600 requests a minute, 2026-11-03). */

/** Baby named in this tab's address, or null. */
export function urlEnrollmentId() {
  if (typeof window === "undefined") return null;
  let seg = "";
  try { seg = decodeURIComponent(window.location.pathname.split("/")[2] || "").trim(); } catch (_) { return null; }
  return isUsableEnrollmentId(seg) ? seg : null;
}

/** This tab's baby: the address first, else the stored id. */
export function pageEnrollmentId() {
  const fromUrl = urlEnrollmentId();
  if (fromUrl) return fromUrl;
  const stored = localStorage.getItem("current_enrollment_id");
  return isUsableEnrollmentId(stored) ? String(stored).trim() : null;
}

/** Stored screening id, unless it belongs to another tab's baby. */
export function pageScreeningId() {
  const sid = localStorage.getItem("current_screening_id");
  if (!sid || sid === "undefined" || sid === "null") return null;
  const fromUrl = urlEnrollmentId();
  const stored = localStorage.getItem("current_enrollment_id");
  if (fromUrl && isUsableEnrollmentId(stored) && String(stored).trim() !== fromUrl) return null;
  return sid;
}

/** Short label for one baby in twin lists: its ID, "not randomised" for an
 *  NR- placeholder, or "<ID> (in error)" for a baby randomised in error
 *  (backend randomised_in_error.py: blender activated, PPV not needed). */
export const babyIdLabel = (b) => {
  if (!b) return "no Form B";
  if (b.randomised_in_error) return `${b.enrollment_id} (in error)`;
  return isNrEnrollmentId(b.enrollment_id) ? "not randomised" : b.enrollment_id;
};
