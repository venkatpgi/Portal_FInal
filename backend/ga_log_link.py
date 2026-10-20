"""Link Gestation Log entries and Form A records that belong to the same woman.

The "Continue to Form A" button on the Gestation Log links the two
explicitly (PATCH /ga-check/{id}/link). A Form A opened from "New screening",
or a log entry added after the Form A, used to stay unlinked (PGIMER
01-0104 / entry #374, 2026-10-20), so the log showed her as never continued
and CONSORT Box 1 counted her twice. Now both saves link automatically:

- Saving a Form A links the most recent unlinked Gestation Log entry at the
  same site with the same CR number.
- Saving a Gestation Log entry links the most recent live Form A at the same
  site with the same CR number that no log entry is linked to yet.

A Form A that already has a linked log entry is never linked again, and a
linked log entry is never moved to another Form A. CR numbers are compared
with ga_log_status.norm_cr (spaces/hyphens ignored, case-insensitive).
"""
from datetime import date

from ga_log_status import norm_cr


def _sort_key(when, rid):
    return (when or date.min, rid or 0)


def pick_log_entry(entries, site_name, cr):
    """entries: dicts with id, site_name, mother_uid, screening_id, check_date.
    Returns the id of the unlinked same-site same-CR entry to link, or None."""
    key = norm_cr(cr)
    if not key:
        return None
    hits = [e for e in entries
            if e["site_name"] == site_name and not e.get("screening_id")
            and norm_cr(e.get("mother_uid")) == key]
    if not hits:
        return None
    return max(hits, key=lambda e: _sort_key(e.get("check_date"), e["id"]))["id"]


def pick_screening(screenings, site_name, cr, linked_sids):
    """screenings: live Form A dicts with screening_id, site_name, maternal_uid,
    created_at. Returns the screening_id to link, or None."""
    key = norm_cr(cr)
    if not key:
        return None
    hits = [s for s in screenings
            if s["site_name"] == site_name and s["screening_id"] not in linked_sids
            and norm_cr(s.get("maternal_uid")) == key]
    if not hits:
        return None
    return max(hits, key=lambda s: (s.get("created_at") or "", s["screening_id"]))["screening_id"]


def orphan_counts(screenings, entries):
    """CONSORT Box 1 orphans: live Form A with no in-period Gestation Log entry.

    screenings: dicts with screening_id, site_name, maternal_uid.
    entries: in-period log dicts with id, site_name, mother_uid, screening_id.
    A Form A is covered by a log entry linked to it, or else by an in-period
    same-site same-CR entry not linked to another live Form A. Each entry
    covers at most one Form A, so Box 1 (entries + orphans) >= Box 3.
    Returns {site_name: n_orphans}."""
    live = {s["screening_id"] for s in screenings}
    linked = {e["screening_id"] for e in entries if e.get("screening_id") in live}
    free = [e for e in entries if e.get("screening_id") not in live]
    used = set()
    out = {}
    for s in sorted(screenings, key=lambda s: s["screening_id"]):
        if s["screening_id"] in linked:
            continue
        key = norm_cr(s.get("maternal_uid"))
        match = next((e for e in free if e["id"] not in used and key
                      and e["site_name"] == s["site_name"] and norm_cr(e.get("mother_uid")) == key), None)
        if match:
            used.add(match["id"])
            continue
        out[s["site_name"]] = out.get(s["site_name"], 0) + 1
    return out


MISSED = "Missed - identified retrospectively"


def ga_box_counts(entries):
    """CONSORT Box 1 log part + Box 2 sub-reasons, counting WOMEN, not log
    entries (PI 2026-10-20): an undelivered woman sent home and readmitted
    is logged again ("New contact of the same woman") but approached once.
    Entries with the same site + normalised CR are one woman; an entry
    without a CR is its own woman. Each woman is represented by an entry
    that continued to Form A if any did, else her latest entry.

    entries: in-period dicts with id, site_name, mother_uid, check_date,
    continued_to_screening, screening_id, identification_type, found_iufd,
    eligible. Returns {site: {box1, box2_missed, box2_iufd,
    box2_eligible_gap, box2_not_candidate_older,
    box2_not_candidate_unreliable}}."""
    groups = {}
    for e in entries:
        key = norm_cr(e.get("mother_uid"))
        gk = (e["site_name"], key) if key else ("id", e["id"])
        groups.setdefault(gk, []).append(e)
    out = {}
    for members in groups.values():
        cont = [e for e in members if e.get("continued_to_screening") or e.get("screening_id")]
        rep = max(cont or members, key=lambda e: _sort_key(e.get("check_date"), e["id"]))
        c = out.setdefault(rep["site_name"], {k: 0 for k in (
            "box1", "box2_missed", "box2_iufd", "box2_eligible_gap",
            "box2_not_candidate_older", "box2_not_candidate_unreliable")})
        c["box1"] += 1
        if rep.get("continued_to_screening") is not False or cont:
            continue
        if rep.get("identification_type") == MISSED:
            c["box2_missed"] += 1
        elif rep.get("found_iufd") is True:
            c["box2_iufd"] += 1
        elif rep.get("eligible") is True:
            c["box2_eligible_gap"] += 1
        elif rep.get("eligible") is False:
            c["box2_not_candidate_older"] += 1
        elif rep.get("eligible") is None:
            c["box2_not_candidate_unreliable"] += 1
    return out


# ------------------------------------------------------------------ database
def _screening_rows(db, site_name):
    from models import ParticipantPII, Screening
    rows = (db.query(Screening.screening_id, Screening.site_name, Screening.created_at)
            .filter(Screening.is_deleted == False, Screening.site_name == site_name)  # noqa: E712
            .all())
    sids = [r.screening_id for r in rows]
    cr = {p.screening_id: p.maternal_uid
          for p in db.query(ParticipantPII).filter(ParticipantPII.screening_id.in_(sids)).all()} if sids else {}
    return [{"screening_id": r.screening_id, "site_name": r.site_name,
             "created_at": r.created_at.isoformat() if r.created_at else "",
             "maternal_uid": cr.get(r.screening_id)} for r in rows]


def link_screening_to_log(db, screening_id, site_name):
    """After a Form A save. Returns the linked GACheckEntry or None. No commit."""
    from models import GACheckEntry, ParticipantPII
    if not screening_id or not site_name:
        return None
    if db.query(GACheckEntry.id).filter(GACheckEntry.screening_id == screening_id).first():
        return None
    pii = db.query(ParticipantPII).filter(ParticipantPII.screening_id == screening_id).first()
    cr = pii.maternal_uid if pii else None
    if not norm_cr(cr):
        return None
    rows = db.query(GACheckEntry).filter(GACheckEntry.site_name == site_name,
                                         GACheckEntry.screening_id.is_(None)).all()
    pick = pick_log_entry([{"id": r.id, "site_name": r.site_name, "mother_uid": r.mother_uid,
                            "screening_id": r.screening_id, "check_date": r.check_date} for r in rows],
                          site_name, cr)
    if pick is None:
        return None
    entry = next(r for r in rows if r.id == pick)
    entry.screening_id = screening_id
    entry.continued_to_screening = True
    return entry


def link_log_to_screening(db, entry):
    """After a Gestation Log save. Returns the linked screening_id or None. No commit."""
    from models import GACheckEntry
    if entry.screening_id or not norm_cr(entry.mother_uid):
        return None
    linked = {sid for (sid,) in db.query(GACheckEntry.screening_id)
              .filter(GACheckEntry.screening_id.isnot(None)).all()}
    sid = pick_screening(_screening_rows(db, entry.site_name), entry.site_name, entry.mother_uid, linked)
    if sid is None:
        return None
    entry.screening_id = sid
    entry.continued_to_screening = True
    return sid
