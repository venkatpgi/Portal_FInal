"""Unit tests for backend/staff_service.py (site-staff seeding).

Uses an in-memory SQLite database to verify seeding is idempotent and adds the
full default roster.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from db import Base
from staff_seed import DEFAULT_SITE_STAFF
from staff_service import (
    deactivate_dropdowns_for_user,
    seed_site_staff,
    strip_dr_from_site_staff,
    sync_dropdowns_for_user,
)
from user_seed import is_mannat_guliani


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[models.SiteStaff.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _expected_count():
    return sum(len(names) for names in DEFAULT_SITE_STAFF.values())


def test_seed_site_staff_adds_full_roster(db):
    added = seed_site_staff(db)
    assert added == _expected_count()
    assert db.query(models.SiteStaff).count() == _expected_count()


def test_seed_site_staff_sets_expected_defaults(db):
    seed_site_staff(db)
    row = (
        db.query(models.SiteStaff)
        .filter_by(site_name="PGIMER", name="Geetika")
        .first()
    )
    assert row is not None
    assert row.role == "screener"
    assert row.is_active is True


def test_seed_site_staff_is_idempotent(db):
    first = seed_site_staff(db)
    second = seed_site_staff(db)
    assert first == _expected_count()
    assert second == 0
    assert db.query(models.SiteStaff).count() == _expected_count()


def test_seed_site_staff_only_adds_missing_entries(db):
    # Pre-seed a single existing staff member
    db.add(
        models.SiteStaff(
            site_name="PGIMER", name="Geetika", role="screener", is_active=True
        )
    )
    db.commit()

    added = seed_site_staff(db)
    # everything except the one that already existed
    assert added == _expected_count() - 1
    assert db.query(models.SiteStaff).count() == _expected_count()


def test_seed_site_staff_has_no_dr_prefix():
    for names in DEFAULT_SITE_STAFF.values():
        for name in names:
            assert not name.lower().startswith("dr.")
            assert not name.lower().startswith("dr ")


def test_amc_site_staff_includes_debika_kurmi():
    assert "Debika Kurmi" in DEFAULT_SITE_STAFF["AMC"]


def test_pgimer_site_staff_lists_mannat_last():
    names = DEFAULT_SITE_STAFF["PGIMER"]
    mannat = [n for n in names if is_mannat_guliani(n)]
    assert mannat == ["Mannat Guliani"]
    assert names[-1] == "Mannat Guliani"


def test_strip_dr_from_site_staff_renames_in_place(db):
    db.add(
        models.SiteStaff(
            site_name="PGIMER",
            name="Dr. Shalini Dhiman",
            role="screener",
            is_active=True,
        )
    )
    db.commit()
    assert strip_dr_from_site_staff(db) == 1
    row = (
        db.query(models.SiteStaff)
        .filter_by(site_name="PGIMER")
        .one()
    )
    assert row.name == "Shalini Dhiman"
    assert row.is_active is True
    assert strip_dr_from_site_staff(db) == 0


def test_strip_dr_from_site_staff_deactivates_clash(db):
    db.add(
        models.SiteStaff(
            site_name="GMCH",
            name="Dr. Manpreet Kaur",
            role="screener",
            is_active=True,
        )
    )
    db.add(
        models.SiteStaff(
            site_name="GMCH",
            name="Manpreet Kaur",
            role="screener",
            is_active=True,
        )
    )
    db.commit()
    assert strip_dr_from_site_staff(db) == 1
    dr_row = (
        db.query(models.SiteStaff)
        .filter_by(site_name="GMCH", name="Dr. Manpreet Kaur")
        .one()
    )
    assert dr_row.is_active is False


@pytest.fixture
def users_staff_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine, tables=[models.SiteStaff.__table__, models.User.__table__]
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _nurse(username, full_name, site="AMC", active=True):
    return models.User(
        username=username,
        hashed_password="x",
        role="nurse",
        site_name=site,
        full_name=full_name,
        is_active=active,
    )


def test_manage_users_create_adds_name_to_dropdowns(users_staff_db):
    user = _nurse("debika.amc", "Debika Kurmi")
    users_staff_db.add(user)
    users_staff_db.flush()
    sync_dropdowns_for_user(users_staff_db, user)
    users_staff_db.commit()
    row = (
        users_staff_db.query(models.SiteStaff)
        .filter_by(site_name="AMC", name="Debika Kurmi")
        .one()
    )
    assert row.is_active is True


def test_manage_users_delete_removes_name_from_dropdowns(users_staff_db):
    user = _nurse("debika.amc", "Debika Kurmi")
    users_staff_db.add(user)
    users_staff_db.flush()
    sync_dropdowns_for_user(users_staff_db, user)
    users_staff_db.commit()
    deactivate_dropdowns_for_user(users_staff_db, user)
    user.is_active = False
    users_staff_db.commit()
    row = (
        users_staff_db.query(models.SiteStaff)
        .filter_by(site_name="AMC", name="Debika Kurmi")
        .one()
    )
    assert row.is_active is False


def test_manage_users_rename_moves_dropdown_name(users_staff_db):
    user = _nurse("debika.amc", "Debika")
    users_staff_db.add(user)
    users_staff_db.flush()
    sync_dropdowns_for_user(users_staff_db, user)
    users_staff_db.commit()
    previous = user.full_name
    user.full_name = "Debika Kurmi"
    sync_dropdowns_for_user(
        users_staff_db, user, previous_name=previous, previous_site="AMC"
    )
    users_staff_db.commit()
    old = (
        users_staff_db.query(models.SiteStaff)
        .filter_by(site_name="AMC", name="Debika")
        .one()
    )
    new = (
        users_staff_db.query(models.SiteStaff)
        .filter_by(site_name="AMC", name="Debika Kurmi")
        .one()
    )
    assert old.is_active is False
    assert new.is_active is True


def test_manage_users_delete_keeps_shared_name(users_staff_db):
    a = _nurse("a.amc", "Shared Name")
    b = _nurse("b.amc", "Shared Name")
    users_staff_db.add_all([a, b])
    users_staff_db.flush()
    sync_dropdowns_for_user(users_staff_db, a)
    sync_dropdowns_for_user(users_staff_db, b)
    users_staff_db.commit()
    deactivate_dropdowns_for_user(users_staff_db, a)
    a.is_active = False
    users_staff_db.commit()
    row = (
        users_staff_db.query(models.SiteStaff)
        .filter_by(site_name="AMC", name="Shared Name")
        .one()
    )
    assert row.is_active is True


def test_manage_users_skips_superadmin(users_staff_db):
    admin = models.User(
        username="root",
        hashed_password="x",
        role="superadmin",
        site_name="AMC",
        full_name="Root Admin",
        is_active=True,
    )
    users_staff_db.add(admin)
    users_staff_db.flush()
    sync_dropdowns_for_user(users_staff_db, admin)
    users_staff_db.commit()
    assert users_staff_db.query(models.SiteStaff).count() == 0
