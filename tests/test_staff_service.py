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
from staff_service import seed_site_staff, strip_dr_from_site_staff
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
