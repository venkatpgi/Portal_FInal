"""Read-only report of Form A screenings that share a CR or hospital number.

Groups live (not soft-deleted) screenings by site, identifier type and
normalised value, and prints only groups with more than one screening.

Prints screening_id, enrollment_id and created_at. Never prints the numbers.

    python report_duplicate_identifiers.py
    python report_duplicate_identifiers.py PGIMER
"""
from __future__ import annotations

import logging
import sys
from collections import defaultdict

logging.disable(logging.CRITICAL)

from db import SessionLocal  # noqa: E402
from identifier_duplicates import normalize_identifier  # noqa: E402
from models import ParticipantPII, Screening  # noqa: E402


def main() -> int:
    site = sys.argv[1].strip() if len(sys.argv) > 1 else None
    db = SessionLocal()
    try:
        query = (
            db.query(
                ParticipantPII.site_name,
                ParticipantPII.screening_id,
                ParticipantPII.maternal_uid,
                ParticipantPII.hospital_admission_number,
                Screening.enrollment_id,
                Screening.created_at,
            )
            .join(Screening, Screening.screening_id == ParticipantPII.screening_id)
            .filter(Screening.is_deleted.isnot(True))
        )
        if site:
            query = query.filter(ParticipantPII.site_name == site)
        rows = query.all()
        db.rollback()
    finally:
        db.close()

    groups = defaultdict(list)
    for row in rows:
        for label, raw in (
            ("CR number", row.maternal_uid),
            ("Hospital number", row.hospital_admission_number),
        ):
            if not normalize_identifier(raw):
                continue
            groups[(row.site_name or "", label, normalize_identifier(raw))].append(row)

    found = 0
    for (site_name, label, _value), members in sorted(groups.items()):
        if len(members) < 2:
            continue
        found += 1
        print(f"{site_name} — {label}: {len(members)} screenings")
        for member in members:
            created = ""
            if member.created_at is not None:
                created = member.created_at.isoformat(sep=" ", timespec="seconds")
            print(
                f"  screening_id={member.screening_id} "
                f"enrollment_id={member.enrollment_id} created_at={created}"
            )
    if not found:
        print("No duplicate CR or hospital numbers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
