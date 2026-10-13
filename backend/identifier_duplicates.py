"""Duplicate CR / hospital-number check for Form A (all sites).

Both values live in participant_pii as encrypted columns, so they cannot be
matched in SQL. The endpoint loads one site's live rows and compares them
here, the same way cr_duplicates.py does for the birth and gestation logs.

Scope is one site: the same number at two hospitals is not a duplicate.
Blank values never clash. The message names the screening, never the number.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

from fastapi import HTTPException


def normalize_identifier(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return re.sub(r"[\s\-]+", "", text.upper())


def find_identifier_conflict(
    rows: Iterable,
    maternal_uid: Optional[str],
    hospital_admission_number: Optional[str],
    *,
    exclude_screening_id: Optional[str] = None,
):
    """(label, row) of the first clash, or None.

    Labels are "CR number" and "Hospital number". A blank incoming value
    never clashes. When exclude_screening_id is set, that row is skipped,
    and an identifier is not checked at all when its normalised value is
    the one that screening already stores. Re-saving unchanged data — even
    an existing duplicate pair — therefore does not block.
    """
    rows = list(rows)
    cr = normalize_identifier(maternal_uid)
    hospital = normalize_identifier(hospital_admission_number)
    check_cr = bool(cr)
    check_hospital = bool(hospital)
    if exclude_screening_id is not None:
        for row in rows:
            if getattr(row, "screening_id", None) != exclude_screening_id:
                continue
            if cr == normalize_identifier(getattr(row, "maternal_uid", None)):
                check_cr = False
            if hospital == normalize_identifier(
                getattr(row, "hospital_admission_number", None)
            ):
                check_hospital = False
            break
    if not check_cr and not check_hospital:
        return None
    for row in rows:
        if (
            exclude_screening_id is not None
            and getattr(row, "screening_id", None) == exclude_screening_id
        ):
            continue
        if check_cr and normalize_identifier(getattr(row, "maternal_uid", None)) == cr:
            return ("CR number", row)
        if (
            check_hospital
            and normalize_identifier(getattr(row, "hospital_admission_number", None))
            == hospital
        ):
            return ("Hospital number", row)
    return None


def load_site_identifier_rows(db, site_name):
    """Live Form A identity rows for one site. Soft-deleted screenings are omitted."""
    from models import ParticipantPII, Screening

    return (
        db.query(
            ParticipantPII.screening_id,
            ParticipantPII.maternal_uid,
            ParticipantPII.hospital_admission_number,
        )
        .join(Screening, Screening.screening_id == ParticipantPII.screening_id)
        .filter(ParticipantPII.site_name == site_name)
        .filter(Screening.is_deleted.isnot(True))
        .all()
    )


def refuse_duplicate_identifiers(
    db,
    site_name: Optional[str],
    maternal_uid: Optional[str],
    hospital_admission_number: Optional[str],
    *,
    exclude_screening_id: Optional[str] = None,
) -> None:
    if not (site_name or "").strip():
        return
    if not normalize_identifier(maternal_uid) and not normalize_identifier(
        hospital_admission_number
    ):
        return
    found = find_identifier_conflict(
        load_site_identifier_rows(db, site_name),
        maternal_uid,
        hospital_admission_number,
        exclude_screening_id=exclude_screening_id,
    )
    if not found:
        return
    label, row = found
    raise HTTPException(
        status_code=409,
        detail=(
            f"Duplicate: this {label} is already entered at {site_name} "
            f"on screening {row.screening_id}. Open and edit that screening "
            f"instead of creating a new one."
        ),
    )
