"""
Participant PII — separate store for identifiers (DPDP / ICMR pseudonymisation).

Clinical tables keep only enrollment_id / screening_id; names and contacts live here.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from models import BirthResuscitation, ParticipantPII, Screening

# Who may see participant identity (explicit list: access hierarchy SOP 1 Oct
# 2026, PI 2026-10-15). All sites: Global PI, Overall Project Scientist
# (view only; writes are refused centrally), PII officer. Own site only:
# the site roles. Technical support (PTS3) and any other role: none.
PII_VIEW_ROLES = frozenset({"superadmin", "pii_officer", "project_scientist", "global_scientist"})
PII_SITE_ROLES = frozenset({"site_pi", "site_scientist", "nurse"})

SCREENING_PII_FIELDS = (
    "mother_first_name",
    "mother_surname",
    "husband_first_name",
    "husband_surname",
    "maternal_uid",
    "hospital_admission_number",
    "mother_contact",
    "husband_contact",
)

BIRTH_PII_FIELDS = (
    "mother_name_first",
    "mother_name_surname",
    "maternal_uid",
    "contact_mother",
    "contact_husband",
)

MATERNAL_PII_FIELDS = (
    "mother_name",
    "maternal_uid",
    "contact_mother",
    "contact_husband",
    "address",
    "email_address",
    "house",
    "city",
    "district",
    "state",
    "pincode",
    "landmark",
)

POSTNATAL_PII_FIELDS = ("baby_name",)
NICU_PII_FIELDS = ("baby_name",)
LOG_PII_FIELDS = ("mother_name", "maternal_uid")
AE_PII_FIELDS = ("mother_name", "maternal_uid")


def utc_now():
    return datetime.now(timezone.utc)


def can_view_pii(user) -> bool:
    role = (user.role or "").lower()
    return role in PII_VIEW_ROLES or (role in PII_SITE_ROLES and bool(user.site_name))


def can_view_pii_for_site(user, site_name: str | None) -> bool:
    if not can_view_pii(user):
        return False
    role = (user.role or "").lower()
    if role in PII_VIEW_ROLES:
        return True
    # Site roles: their own site only.
    return bool(user.site_name and site_name and user.site_name == site_name)


def _merge(existing: ParticipantPII | None, **fields: Any) -> dict[str, Any]:
    """Merge incoming PII fields onto an existing row.

    Empty string means "clear this field" (so a wrongly saved value can be
    corrected). ``None`` means "leave whatever is already stored".
    """
    out = {}
    for key, value in fields.items():
        if value is not None and value != "":
            out[key] = value
        elif value == "":
            out[key] = None
        elif existing is not None:
            current = getattr(existing, key, None)
            if current is not None:
                out[key] = current
    return out


def _collapse_pii_duplicates(
    db: Session,
    keep: ParticipantPII,
    drop: ParticipantPII,
    *,
    enrollment_id: str | None = None,
    screening_id: str | None = None,
) -> ParticipantPII:
    """Merge two PII rows that represent the same participant.

    Form A typically creates a row keyed only by screening_id. Form B/C may
    later create a second row keyed only by enrollment_id. Stamping
    screening_id onto the enrollment row then hits
    ix_participant_pii_screening_id. Collapse into one row instead.
    """
    if keep.id == drop.id:
        return keep

    drop_eid = drop.enrollment_id
    drop_sid = drop.screening_id
    drop.enrollment_id = None
    drop.screening_id = None
    db.flush()

    skip = {"id", "created_at", "updated_at", "enrollment_id", "screening_id"}
    for col in ParticipantPII.__table__.columns:
        name = col.name
        if name in skip:
            continue
        if getattr(keep, name) is None:
            drop_val = getattr(drop, name)
            if drop_val is not None:
                setattr(keep, name, drop_val)

    preferred_eid = enrollment_id or keep.enrollment_id or drop_eid
    preferred_sid = screening_id or keep.screening_id or drop_sid
    keep.enrollment_id = preferred_eid
    keep.screening_id = preferred_sid

    db.delete(drop)
    db.flush()
    keep.updated_at = utc_now()
    return keep


def _later_baby(db: Session, enrollment_id: str) -> bool:
    n = (db.query(BirthResuscitation.baby_number)
         .filter(BirthResuscitation.enrollment_id == enrollment_id).scalar())
    return n is not None and n > 1


def upsert_participant_pii(
    db: Session,
    *,
    enrollment_id: str | None = None,
    screening_id: str | None = None,
    site_name: str | None = None,
    **fields: Any,
) -> ParticipantPII:
    if enrollment_id and screening_id and _later_baby(db, enrollment_id):
        screening_id = None  # twin 2+: never merge into the mother's (baby 1's) row
    by_enrollment = None
    by_screening = None
    if enrollment_id:
        by_enrollment = (
            db.query(ParticipantPII)
            .filter(ParticipantPII.enrollment_id == enrollment_id)
            .first()
        )
    if screening_id:
        by_screening = (
            db.query(ParticipantPII)
            .filter(ParticipantPII.screening_id == screening_id)
            .first()
        )

    record = None
    if by_enrollment and by_screening and by_enrollment.id != by_screening.id:
        # Prefer the screening-keyed row (Form A identity) and fold the
        # enrollment-only row into it.
        record = _collapse_pii_duplicates(
            db,
            by_screening,
            by_enrollment,
            enrollment_id=enrollment_id,
            screening_id=screening_id,
        )
    elif by_enrollment:
        record = by_enrollment
    elif by_screening:
        record = by_screening

    merged = _merge(record, **fields)

    if record is None:
        record = ParticipantPII(
            enrollment_id=enrollment_id,
            screening_id=screening_id,
            site_name=site_name,
            created_at=utc_now(),
        )
        db.add(record)
    else:
        if enrollment_id and record.enrollment_id != enrollment_id:
            other = (
                db.query(ParticipantPII)
                .filter(
                    ParticipantPII.enrollment_id == enrollment_id,
                    ParticipantPII.id != record.id,
                )
                .first()
            )
            if other:
                record = _collapse_pii_duplicates(
                    db, record, other,
                    enrollment_id=enrollment_id,
                    screening_id=screening_id or record.screening_id,
                )
            else:
                record.enrollment_id = enrollment_id
        elif enrollment_id and not record.enrollment_id:
            record.enrollment_id = enrollment_id

        if screening_id and record.screening_id != screening_id:
            other = (
                db.query(ParticipantPII)
                .filter(
                    ParticipantPII.screening_id == screening_id,
                    ParticipantPII.id != record.id,
                )
                .first()
            )
            if other:
                record = _collapse_pii_duplicates(
                    db, other, record,
                    enrollment_id=enrollment_id or record.enrollment_id,
                    screening_id=screening_id,
                )
            elif not record.screening_id:
                record.screening_id = screening_id
        elif screening_id and not record.screening_id:
            record.screening_id = screening_id

        if site_name:
            record.site_name = site_name

    for key, value in merged.items():
        setattr(record, key, value)
    record.updated_at = utc_now()
    return record


def extract_screening_pii(data: dict) -> dict:
    """Pull Form A identity fields out of a screening payload.

    Empty strings are kept so optional fields (e.g. mother_surname) can be
    explicitly cleared on update. ``None`` is omitted so partial updates
    don't wipe unrelated PII columns.
    """
    out = {}
    for k in SCREENING_PII_FIELDS:
        if k not in data:
            continue
        val = data[k]
        if val is None:
            continue
        out[k] = val
    return out


def clear_screening_pii_columns(screening: Screening) -> None:
    for field in SCREENING_PII_FIELDS:
        setattr(screening, field, None)


def strip_keys(data: dict, keys: tuple) -> dict:
    return {k: v for k, v in data.items() if k not in keys}


def pii_to_dict(record: ParticipantPII | None) -> dict | None:
    if record is None:
        return None
    return {
        "enrollment_id": record.enrollment_id,
        "screening_id": record.screening_id,
        "site_name": record.site_name,
        "mother_first_name": record.mother_first_name,
        "mother_surname": record.mother_surname,
        "husband_first_name": record.husband_first_name,
        "husband_surname": record.husband_surname,
        "maternal_uid": record.maternal_uid,
        "hospital_admission_number": record.hospital_admission_number,
        "mother_contact": record.mother_contact,
        "husband_contact": record.husband_contact,
        "address": record.address,
        "baby_name": record.baby_name,
        "contact_mother": record.contact_mother,
        "contact_husband": record.contact_husband,
        "updated_at": record.updated_at,
    }


_SIBLING_SKIP = {"id", "enrollment_id", "screening_id", "baby_name", "created_at", "updated_at"}


def seed_sibling_pii(db: Session, screening_id: str, enrollment_id: str) -> ParticipantPII | None:
    """Twin / triplet baby 2+ (babies.py): its own identity row, keyed by its
    enrollment id only (screening_id is unique and belongs to the mother's
    row), with the mother's details copied once so pages that look a baby up
    by enrollment id still show the mother. The baby name is never copied."""
    row = db.query(ParticipantPII).filter(ParticipantPII.enrollment_id == enrollment_id).first()
    if row is not None:
        return row
    mother = db.query(ParticipantPII).filter(ParticipantPII.screening_id == screening_id).first()
    row = ParticipantPII(enrollment_id=enrollment_id, created_at=utc_now(), updated_at=utc_now())
    if mother is not None:
        for col in ParticipantPII.__table__.columns:
            if col.name not in _SIBLING_SKIP:
                setattr(row, col.name, getattr(mother, col.name))
    db.add(row)
    return row


def get_pii_for_participant(
    db: Session,
    *,
    enrollment_id: str | None = None,
    screening_id: str | None = None,
) -> ParticipantPII | None:
    by_enrollment = None
    by_screening = None
    if enrollment_id:
        by_enrollment = (
            db.query(ParticipantPII)
            .filter(ParticipantPII.enrollment_id == enrollment_id)
            .first()
        )
    if screening_id:
        by_screening = (
            db.query(ParticipantPII)
            .filter(ParticipantPII.screening_id == screening_id)
            .first()
        )
    # Twin / triplet baby 2+: the mother's row belongs to baby 1, so this
    # baby's own row wins (its baby name is its own).
    if by_enrollment and by_screening and by_screening.enrollment_id not in (None, enrollment_id):
        return by_enrollment
    # Prefer Form A (screening-keyed) identity when two rows still exist;
    # Form B save will collapse them. Do not return the enrollment-only stub
    # and hide the mother's Form A name / UID.
    if by_screening:
        return by_screening
    return by_enrollment


def migrate_legacy_pii(db: Session) -> int:
    """Copy PII from clinical tables into participant_pii; clear screening columns."""
    count = 0
    screenings = db.query(Screening).all()
    for s in screenings:
        has_pii = any(getattr(s, f) for f in SCREENING_PII_FIELDS)
        if not has_pii:
            continue
        upsert_participant_pii(
            db,
            enrollment_id=s.enrollment_id,
            screening_id=s.screening_id,
            site_name=s.site_name,
            mother_first_name=s.mother_first_name,
            mother_surname=s.mother_surname,
            husband_first_name=s.husband_first_name,
            husband_surname=s.husband_surname,
            maternal_uid=s.maternal_uid,
            hospital_admission_number=s.hospital_admission_number,
            mother_contact=s.mother_contact,
            husband_contact=s.husband_contact,
        )
        clear_screening_pii_columns(s)
        count += 1
    if count:
        db.commit()
    return count


def _require_valid_identity_for(db, mapped, enrollment_id, screening_id, site_name) -> None:
    """CR / name rules (identity_rules.py) for a form save; values equal to
    the ones already stored are not re-checked."""
    from identity_rules import CR_FIELDS, NAME_FIELD_LABELS, require_valid_identity, stored_values
    existing = None
    if screening_id:
        existing = db.query(ParticipantPII).filter(ParticipantPII.screening_id == screening_id).first()
    if existing is None and enrollment_id:
        existing = db.query(ParticipantPII).filter(ParticipantPII.enrollment_id == enrollment_id).first()
    keys = tuple(CR_FIELDS) + tuple(NAME_FIELD_LABELS)
    require_valid_identity(site_name or (existing.site_name if existing else None),
                           mapped, stored_values(existing, keys))


def split_and_store_pii(
    db: Session,
    payload: dict,
    pii_keys: tuple,
    *,
    enrollment_id: str | None = None,
    screening_id: str | None = None,
    site_name: str | None = None,
) -> dict:
    """Move PII fields into participant_pii; remove them from the clinical payload."""
    pii_values = {}
    for key in pii_keys:
        if key in payload:
            if payload[key] not in (None, ""):
                pii_values[key] = payload[key]
            del payload[key]  # Remove entirely — don't pass to model constructor

    if pii_values:
        mapped = dict(pii_values)
        if "mother_name_first" in mapped:
            mapped.setdefault("mother_first_name", mapped.pop("mother_name_first", None))
        if "mother_name_surname" in mapped:
            mapped.setdefault("mother_surname", mapped.pop("mother_name_surname", None))
        if "mother_name" in mapped and "mother_first_name" not in mapped:
            parts = (mapped.pop("mother_name") or "").split(None, 1)
            mapped["mother_first_name"] = parts[0] if parts else None
            mapped["mother_surname"] = parts[1] if len(parts) > 1 else None
        if "contact_mother" in mapped:
            mapped.setdefault("mother_contact", mapped.get("contact_mother"))
        if "contact_husband" in mapped:
            mapped.setdefault("husband_contact", mapped.get("contact_husband"))
        valid_cols = {c.name for c in ParticipantPII.__table__.columns}
        _require_valid_identity_for(db, mapped, enrollment_id, screening_id, site_name)
        upsert_participant_pii(
            db,
            enrollment_id=enrollment_id,
            screening_id=screening_id,
            site_name=site_name,
            **{k: v for k, v in mapped.items() if k in valid_cols},
        )
    return payload


def screening_to_clinical_dict(screening: Screening) -> dict:
    """Build API dict for screening without PII fields."""
    data = {
        c.name: getattr(screening, c.name)
        for c in screening.__table__.columns
    }
    for field in SCREENING_PII_FIELDS:
        data.pop(field, None)
    return data
