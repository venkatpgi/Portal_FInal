"""Twins, triplets and more: several babies under one mother's Form A
(PI 2026-10-29).

Form A is the mother (one screening id); each baby has its own Form B with
`baby_number` (1, 2, 3 ...) and `number_of_babies`. Each baby is randomised
independently with its own envelope (PI), so a randomised twin types its own
enrollment id; a baby not randomised gets NR-<screening id> as baby 1 and
NR-<screening id>-<n> from baby 2 on. NULL baby_number = baby 1 (every record
saved before this change).

`screenings.enrollment_id` keeps pointing at baby 1 (the mobile app and older
pages read it). To find the mother of ANY baby, use `screening_for_enrollment`,
which goes through the baby's own Form B.
"""
from __future__ import annotations

import re

from models import BirthResuscitation, Screening

MAX_BABIES = 6
_NR_BABY_RE = re.compile(r"^(\d{2}-\d{4})-([2-9])$")


def baby_no(row_or_value) -> int:
    v = getattr(row_or_value, "baby_number", row_or_value)
    try:
        return int(v) if v not in (None, "") else 1
    except (TypeError, ValueError):
        return 1


def nr_enrollment_id(screening_id: str, baby_number=None) -> str:
    n = baby_no(baby_number)
    return f"NR-{screening_id}" if n == 1 else f"NR-{screening_id}-{n}"


def parse_nr(enrollment_id: str | None):
    """(screening_id, baby_number) for an NR- id, else None."""
    eid = (enrollment_id or "").strip()
    if not eid.upper().startswith("NR-"):
        return None
    rest = eid[3:]
    m = _NR_BABY_RE.match(rest)
    if m:
        return m.group(1), int(m.group(2))
    return rest, 1


def babies_of(db, screening_id: str | None) -> list:
    """Form B rows of one mother, baby 1 first."""
    if not screening_id:
        return []
    rows = (db.query(BirthResuscitation)
            .filter(BirthResuscitation.screening_id == screening_id).all())
    return sorted(rows, key=lambda b: (baby_no(b), b.id))


def screening_for_enrollment(db, enrollment_id: str | None):
    """The mother's Form A for any baby's enrollment id (or None)."""
    eid = (enrollment_id or "").strip()
    if not eid:
        return None
    nr = parse_nr(eid)
    if nr:
        s = db.query(Screening).filter(Screening.screening_id == nr[0]).first()
        if s or nr[1] == 1:
            return s
    sid = (db.query(BirthResuscitation.screening_id)
           .filter(BirthResuscitation.enrollment_id == eid).scalar())
    if sid:
        s = db.query(Screening).filter(Screening.screening_id == sid).first()
        if s:
            return s
    return db.query(Screening).filter(Screening.enrollment_id == eid).first()


def enrollments_by_screening(db, screenings) -> dict:
    """{enrollment id: screening} for every baby of the given Form A rows
    (Form B ids plus the id stored on Form A)."""
    by_sid = {s.screening_id: s for s in screenings if s.screening_id}
    out = {s.enrollment_id: s for s in screenings if s.enrollment_id}
    if by_sid:
        for eid, sid in (db.query(BirthResuscitation.enrollment_id, BirthResuscitation.screening_id)
                         .filter(BirthResuscitation.screening_id.in_(list(by_sid))).all()):
            if eid:
                out.setdefault(eid, by_sid[sid])
    return out


def baby_label(baby_number, number_of_babies) -> str:
    """'Twin 2 of 2' / 'Triplet 1 of 3' / '' for a singleton."""
    total = baby_no(number_of_babies) if number_of_babies not in (None, "") else 1
    if total < 2:
        return ""
    word = {2: "Twin", 3: "Triplet", 4: "Quadruplet"}.get(total, "Baby")
    return f"{word} {baby_no(baby_number)} of {total}"
