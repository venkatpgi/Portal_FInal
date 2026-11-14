"""Seed site staff roster into database, and keep it in lockstep with
Manage Users (create / edit / deactivate)."""

from sqlalchemy.orm import Session

from models import SiteStaff, User
from staff_seed import DEFAULT_SITE_STAFF
from user_seed import display_name_for_role, name_without_dr

# Roles that belong on Screened-by / Completed-by. Superadmin, PTS3,
# PII officer, and global_scientist are logins only — not form names.
DROPDOWN_ROLES = frozenset({
    "nurse",
    "site_scientist",
    "site_pi",
    "project_scientist",
})

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


def _name_key(name: str | None) -> str:
    return name_without_dr(name).strip().lower()


def dropdown_display_name(user: User) -> str:
    return display_name_for_role(user.full_name or user.username, user.role).strip()


def dropdown_site_for_user(user: User) -> str | None:
    site = (user.site_name or "").strip()
    if site:
        return site
    if (user.role or "").strip().lower() == "project_scientist":
        return "PGIMER"
    return None


def user_belongs_on_dropdowns(user: User) -> bool:
    if not user or not bool(user.is_active):
        return False
    if (user.role or "").strip().lower() not in DROPDOWN_ROLES:
        return False
    return bool(dropdown_display_name(user) and dropdown_site_for_user(user))


def _staff_row(db: Session, site_name: str, name: str) -> SiteStaff | None:
    key = _name_key(name)
    if not site_name or not key:
        return None
    rows = db.query(SiteStaff).filter(SiteStaff.site_name == site_name).all()
    for row in rows:
        if _name_key(row.name) == key:
            return row
    return None


def _another_active_user_has_name(
    db: Session,
    site_name: str,
    name: str,
    exclude_user_id: int | None = None,
) -> bool:
    key = _name_key(name)
    if not key:
        return False
    query = db.query(User).filter(User.is_active.is_(True))
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    for row in query.all():
        if (row.role or "").strip().lower() not in DROPDOWN_ROLES:
            continue
        if dropdown_site_for_user(row) != site_name:
            continue
        if _name_key(dropdown_display_name(row)) == key:
            return True
    return False


def _upsert_staff(db: Session, site_name: str, name: str) -> None:
    row = _staff_row(db, site_name, name)
    if row:
        row.is_active = True
        if row.name != name:
            row.name = name
        return
    db.add(SiteStaff(site_name=site_name, name=name, role="screener", is_active=True))


def _deactivate_staff_if_unused(
    db: Session,
    site_name: str | None,
    name: str | None,
    exclude_user_id: int | None = None,
) -> None:
    if not site_name or not name:
        return
    if _another_active_user_has_name(db, site_name, name, exclude_user_id):
        return
    row = _staff_row(db, site_name, name)
    if row and row.is_active:
        row.is_active = False


def sync_dropdowns_for_user(
    db: Session,
    user: User,
    *,
    previous_name: str | None = None,
    previous_site: str | None = None,
) -> None:
    """Add or drop this login on Screened-by / Completed-by. Does not commit."""
    new_name = dropdown_display_name(user)
    new_site = dropdown_site_for_user(user)
    old_name = (previous_name or "").strip() or None
    old_site = (previous_site or "").strip() or None

    if user_belongs_on_dropdowns(user):
        moved = bool(old_name and old_site) and (
            _name_key(old_name) != _name_key(new_name) or old_site != new_site
        )
        if moved:
            _deactivate_staff_if_unused(db, old_site, old_name, exclude_user_id=user.id)
        _upsert_staff(db, new_site, new_name)
        return

    _deactivate_staff_if_unused(
        db,
        old_site or new_site,
        old_name or new_name,
        exclude_user_id=user.id,
    )


def deactivate_dropdowns_for_user(db: Session, user: User) -> None:
    """Drop this login from dropdowns after Manage Users deactivate/delete."""
    _deactivate_staff_if_unused(
        db,
        dropdown_site_for_user(user),
        dropdown_display_name(user),
        exclude_user_id=user.id,
    )


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