"""Seed login accounts for site staff (nurses + site scientists) into the
`users` table so they can log into both the web portal and the mobile app
with the same username/password.

Idempotent: existing usernames are left untouched. Newly created accounts
get a random temp password (must_change_password=True) written to a
credentials file on local disk — NOT logged, NOT committed — for the
superadmin to hand out securely and delete afterwards.
"""
import os
import secrets
import string
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from auth import hash_password
from models import User
from user_seed import (
    DEFAULT_LOGIN_USERS,
    EXISTING_STAFF_DISPLAY_NAMES,
    KNOWN_STAFF_EMAILS,
    SCIENTIST_ROLES,
    designation_for_account,
    display_name_for_role,
    name_without_dr,
)

CREDENTIALS_DIR = os.path.join(os.path.dirname(__file__), "credentials")


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length - 2))
        pwd += secrets.choice(string.digits) + secrets.choice("!@#$%&*")
        if any(c.islower() for c in pwd) and any(c.isupper() for c in pwd):
            return pwd


def seed_login_users(db: Session) -> int:
    created_rows = []

    for username, full_name, role, site_name in DEFAULT_LOGIN_USERS:
        exists = db.query(User).filter(User.username == username).first()
        if exists:
            continue

        temp_password = _generate_temp_password()
        db.add(User(
            username=username,
            email=None,
            hashed_password=hash_password(temp_password),
            role=role,
            site_name=site_name,
            full_name=display_name_for_role(full_name, role),
            designation=designation_for_account(full_name, role, site_name),
            must_change_password=True,
            is_active=True,
        ))
        created_rows.append((username, full_name, role, site_name, temp_password))

    if not created_rows:
        return 0

    db.commit()

    os.makedirs(CREDENTIALS_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = os.path.join(CREDENTIALS_DIR, f"new_accounts_{ts}.csv")
    with open(out_path, "w") as f:
        f.write("username,full_name,role,site_name,temp_password\n")
        for row in created_rows:
            f.write(",".join(field if field is not None else "" for field in row) + "\n")

    return len(created_rows)


def backfill_scientist_names(db: Session) -> int:
    """Strip a leading Dr. from scientist full_name rows already in users.

    Seed skips existing usernames, so live accounts keep the old title
    until this runs. Idempotent; does not touch nurses, PIs, or admins.
    """
    updated = 0
    rows = (
        db.query(User)
        .filter(User.role.in_(tuple(SCIENTIST_ROLES)))
        .all()
    )
    for row in rows:
        wanted = display_name_for_role(row.full_name, row.role)
        if not wanted or wanted == (row.full_name or "").strip():
            continue
        row.full_name = wanted
        updated += 1
    if updated:
        db.commit()
    return updated


def backfill_pilot_designations(db: Session) -> int:
    """Fill users.designation when still blank so Completion Details autofill
    works at every site, not only the PGIMER named list.

    Named PGIMER titles stay as-is. Other-site scientists get Project
    Research Scientist II (Medical); nurses get Project Nurse III (same as
    Tanvi Saini / Yashvi Jolly). Does not overwrite a designation already
    saved in Manage Staff.
    """
    updated = 0
    rows = (
        db.query(User)
        .filter(
            User.is_active.is_(True),
            User.full_name.isnot(None),
            User.full_name != "",
        )
        .all()
    )
    for row in rows:
        current = (row.designation or "").strip()
        wanted = designation_for_account(row.full_name, row.role, row.site_name)
        if not wanted:
            continue
        if current:
            continue
        row.designation = wanted
        updated += 1
    if updated:
        db.commit()
    return updated


def _matches_existing_staff(row: User, full_name: str, username_hints: tuple[str, ...]) -> bool:
    uname = (row.username or "").strip().lower()
    current = name_without_dr(row.full_name).strip().lower()
    wanted = name_without_dr(full_name).strip().lower()
    if uname in {h.lower() for h in username_hints}:
        return True
    if wanted and current == wanted:
        return True
    tokens = [t for t in wanted.split() if t]
    if tokens and all(t in uname or t in current for t in tokens):
        return True
    first = tokens[0] if tokens else ""
    return bool(first) and (first in uname or first in current)


def backfill_existing_staff_names(db: Session) -> int:
    """Set display name / designation on logins that already exist.

    Used when someone was created in Manage Staff (so they can log in)
    but is missing from Completed-by because `full_name` is blank or is
    the username. Does not insert users.
    """
    updated = 0
    for site_name, full_name, username_hints in EXISTING_STAFF_DISPLAY_NAMES:
        rows = (
            db.query(User)
            .filter(User.site_name == site_name, User.is_active.is_(True))
            .all()
        )
        match = next(
            (row for row in rows if _matches_existing_staff(row, full_name, username_hints)),
            None,
        )
        if not match:
            continue
        changed = False
        wanted_name = display_name_for_role(full_name, match.role)
        if (match.full_name or "").strip() != wanted_name:
            match.full_name = wanted_name
            changed = True
        wanted_des = designation_for_account(wanted_name, match.role, site_name)
        if wanted_des and not (match.designation or "").strip():
            match.designation = wanted_des
            changed = True
        if changed:
            updated += 1
    if updated:
        db.commit()
    return updated


def backfill_staff_emails(db: Session) -> int:
    """Set known contact emails when users.email is still empty.

    Idempotent and will not overwrite an address already saved via
    Manage Staff / PUT /users/{id}. Skips if another account already
    holds that address (unique constraint).
    """
    updated = 0
    for username, email in KNOWN_STAFF_EMAILS.items():
        row = db.query(User).filter(User.username == username).first()
        if not row or row.email:
            continue
        dupe = (
            db.query(User)
            .filter(User.email == email, User.id != row.id)
            .first()
        )
        if dupe:
            continue
        row.email = email
        updated += 1
    if updated:
        db.commit()
    return updated
