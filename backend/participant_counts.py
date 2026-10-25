"""Participant counts shared by View Entries and the Dashboard (PI 2026-10-24).

The two pages used to count separately (View Entries in the browser from the
screenings list, the Dashboard in SQL) and showed different tiles: View
Entries had no randomised count and the Dashboard had no delivered count, and
neither showed Not Eligible. Both now take their tiles from counts() below.

Who is counted: every non-deleted Form A at one of the sites in scope
(DRAFT / blank-site autosave shells are left out). Screening tiles use
compute_screening_status, as the screenings list does. Delivery and
randomisation tiles come straight from Form B (birth_resuscitation), so a
baby is counted whatever the mother's Form A says; "Randomised" is the same
br.randomised = TRUE count the Dashboard has always called Enrolled.
No arm is shown anywhere: allocation is not in this database (blinded).
"""
from collections import defaultdict

from models import BirthResuscitation, Screening
from patient_stage import followup_stage, patient_stage
from screening_status import compute_screening_status

# Stages that mean "consented, still pregnant, delivery expected here".
AWAITING_STAGES = frozenset({"awaiting_delivery", "readmitted_awaiting", "discharged_undelivered"})

COUNT_KEYS = (
    # Screening (Form A)
    "screened", "eligible", "not_eligible", "screen_failures", "pending", "consented",
    # Delivery and randomisation (Form B)
    "awaiting_delivery", "delivered", "needed_ppv", "randomised", "not_randomised", "no_ppv",
)


def scoped_screenings(db, sites):
    """Non-deleted Form A rows at the given sites."""
    if not sites:
        return []
    return (db.query(Screening)
            .filter(Screening.is_deleted.isnot(True))
            .filter(Screening.site_name.in_(list(sites)))
            .all())


def stage_items(db, rows):
    """[(screening row, status, stage key, Form B row or None)] for Form A rows."""
    sids = [r.screening_id for r in rows if r.screening_id]
    form_b = {}
    if sids:
        for b in (db.query(BirthResuscitation.screening_id, BirthResuscitation.required_resuscitation,
                           BirthResuscitation.randomised)
                  .filter(BirthResuscitation.screening_id.in_(sids)).all()):
            form_b[b.screening_id] = b
    out = []
    for r in rows:
        b = form_b.get(r.screening_id)
        status = compute_screening_status(r)
        key = patient_stage(status, r.consent_given, r.gestation_weeks, r.gestation_days,
                            b is not None, b.required_resuscitation if b else None,
                            b.randomised if b else None)
        if key == "awaiting_delivery":
            key = followup_stage(r.pregnancy_episodes, r.pregnancy_outcome, r.consent_withdrawn) or key
        out.append((r, status, key, b))
    return out


def tile_keys(status, consent_given, stage, b):
    """Which COUNT_KEYS tiles one Form A (+ its Form B) is counted in."""
    keys = ["screened", {
        "Eligible": "eligible",
        "Not Eligible": "not_eligible",
        "Screen Failure": "screen_failures",
    }.get(status, "pending")]
    if consent_given == "Yes":
        keys.append("consented")
    if stage in AWAITING_STAGES:
        keys.append("awaiting_delivery")
    if b is None:
        return keys
    keys.append("delivered")
    if b.randomised is True:
        keys.append("randomised")
    if b.required_resuscitation is True or b.randomised is True:
        keys.append("needed_ppv")
        if b.randomised is False:
            keys.append("not_randomised")
    elif b.required_resuscitation is False:
        keys.append("no_ppv")
    return keys


def members(items):
    """{tile key: [screening_id, ...]} -- the records behind each count."""
    m = {k: [] for k in COUNT_KEYS}
    for r, status, stage, b in items:
        for k in tile_keys(status, r.consent_given, stage, b):
            m[k].append(r.screening_id)
    return m


def counts(items):
    return {k: len(v) for k, v in members(items).items()}


def counts_by_site(items):
    by_site = defaultdict(list)
    for it in items:
        by_site[it[0].site_name].append(it)
    return {site: counts(its) for site, its in by_site.items()}
