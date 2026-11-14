"""Seed site staff roster into database."""

from sqlalchemy.orm import Session

from models import SiteStaff
from staff_seed import DEFAULT_SITE_STAFF
from user_seed import name_without_dr

# Known-wrong (site_name, name) pairs from before the 2026-07-31 roster
# correction — deactivated rather than deleted, so any historical link
# (e.g. a screening record's screened_by referencing the old string) is
# preserved. The /sites/{site}/screeners endpoint already filters on
# is_active, so deactivated rows silently drop out of the dropdown.
STALE_SITE_STAFF: list[tuple[str, str]] = [
    ("GMCH", "Arushu"),              # typo — corrected to "Arushi"
    ("IOG", "Yashvi Jolly"),         # wrong site — she's PGIMER staff
    ("GMCH-A", "Nurse A"),           # placeholder, replaced with real roster
    ("GMCH-A", "Nurse B"),           # placeholder, replaced with real roster
    ("AMC", "Nurse A"),              # placeholder, replaced with real roster
    ("AMC", "Nurse B"),              # placeholder, replaced with real roster
    ("AFMC", "Mannat Guliani"),      # PGIMER-only; AFMC had no PDF roster
    # Pre-2026-11 scientist names carried a "Dr." prefix; renamed in place
    # by strip_dr_from_site_staff, and deactivated here if a clash remains.
    ("PGIMER", "Dr. Mannat Guliani"),
    ("PGIMER", "Dr. Shalini Dhiman"),
    ("GMCH", "Dr. Manpreet Kaur"),
    ("IOG", "Dr. Sobhana"),
    ("GMCH-A", "Dr. Kirti Vishnu Rathod"),
]


def strip_dr_from_site_staff(db: Session) -> int:
    """Drop the Dr. title from scientist names on the screened-by roster.

    Renames in place when the stripped name is free; otherwise deactivates
    the Dr. row so the seed can keep a single active name per person.
    """
    changed = 0
    rows = db.query(SiteStaff).filter(SiteStaff.is_active.is_(True)).all()
    for row in rows:
        stripped = name_without_dr(row.name)
        if not stripped or stripped == row.name:
            continue
        clash = (
            db.query(SiteStaff)
            .filter(
                SiteStaff.site_name == row.site_name,
                SiteStaff.name == stripped,
            )
            .first()
        )
        if clash and clash.id != row.id:
            row.is_active = False
        else:
            row.name = stripped
        changed += 1
    if changed:
        db.commit()
    return changed


def seed_site_staff(db: Session) -> int:
    added = 0
    for site_name, names in DEFAULT_SITE_STAFF.items():
        for name in names:
            exists = (
                db.query(SiteStaff)
                .filter(SiteStaff.site_name == site_name, SiteStaff.name == name)
                .first()
            )
            if exists:
                continue
            db.add(
                SiteStaff(
                    site_name=site_name,
                    name=name,
                    role="screener",
                    is_active=True,
                )
            )
            added += 1
    if added:
        db.commit()
    return added


def deactivate_stale_site_staff(db: Session) -> int:
    deactivated = 0
    for site_name, name in STALE_SITE_STAFF:
        row = (
            db.query(SiteStaff)
            .filter(
                SiteStaff.site_name == site_name,
                SiteStaff.name == name,
                SiteStaff.is_active.is_(True),
            )
            .first()
        )
        if not row:
            continue
        row.is_active = False
        deactivated += 1
    if deactivated:
        db.commit()
    return deactivated