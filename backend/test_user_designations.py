"""Designation autofill for Completion Details at every site."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from db import Base
from user_seed import (
    DEFAULT_LOGIN_USERS,
    DESIGNATION_NURSE,
    DESIGNATION_PROJECT_SCIENTIST,
    DESIGNATION_SITE_SCIENTIST,
    designation_for_account,
    is_mannat_guliani,
    name_without_dr,
    sort_completed_by_names,
)
from user_service import backfill_scientist_names


def test_pgimer_nurse_matches_tanvi_yashvi():
    assert designation_for_account("Tanvi Saini", "nurse", "PGIMER") == DESIGNATION_NURSE
    assert designation_for_account("Yashvi Jolly", "nurse", "PGIMER") == DESIGNATION_NURSE


def test_other_site_nurses_same_as_tanvi():
    assert designation_for_account("Anosh", "nurse", "GMCH") == DESIGNATION_NURSE
    assert designation_for_account("Oli Konwar", "nurse", "AMC") == DESIGNATION_NURSE
    assert (
        designation_for_account("Samiksha Deepak Khandagale", "nurse", "GMCH-A")
        == DESIGNATION_NURSE
    )


def test_other_site_scientists_are_prs_ii_medical():
    assert (
        designation_for_account("Kirti Vishnu Rathod", "site_scientist", "GMCH-A")
        == DESIGNATION_SITE_SCIENTIST
    )
    assert (
        designation_for_account("Manpreet Kaur", "site_scientist", "GMCH")
        == DESIGNATION_SITE_SCIENTIST
    )
    assert (
        designation_for_account("Nafifa Tasmeen Rahman", "site_scientist", "AMC")
        == DESIGNATION_SITE_SCIENTIST
    )
    assert (
        designation_for_account("Sobhana", "site_scientist", "IOG")
        == DESIGNATION_SITE_SCIENTIST
    )
    # Historical completed-by values still resolve after the Dr. prefix.
    assert (
        designation_for_account("Dr. Kirti Vishnu Rathod", "site_scientist", "GMCH-A")
        == DESIGNATION_SITE_SCIENTIST
    )


def test_pgimer_named_scientist_titles_unchanged():
    assert (
        designation_for_account("Mannat Guliani", "project_scientist", None)
        == DESIGNATION_PROJECT_SCIENTIST
    )
    assert (
        designation_for_account("Shalini Dhiman", "site_scientist", "PGIMER")
        == "Project Research Scientist III (Non-Medical)"
    )
    assert (
        designation_for_account("Dr. Shalini Dhiman", "site_scientist", "PGIMER")
        == "Project Research Scientist III (Non-Medical)"
    )


def test_seeded_scientist_names_have_no_dr_prefix():
    for _username, full_name, role, _site in DEFAULT_LOGIN_USERS:
        if role in ("site_scientist", "project_scientist"):
            assert not full_name.lower().startswith("dr.")
            assert not full_name.lower().startswith("dr ")


def test_name_without_dr_strips_title_only():
    assert name_without_dr("Dr. Shalini Dhiman") == "Shalini Dhiman"
    assert name_without_dr("Dr Shalini Dhiman") == "Shalini Dhiman"
    assert name_without_dr("Shalini Dhiman") == "Shalini Dhiman"
    assert name_without_dr("Drake") == "Drake"


def test_mannat_guliani_sorts_last_in_completed_by():
    names = [
        "Yashvi Jolly",
        "Dr. Mannat Guliani",
        "Geetika",
        "Shalini Dhiman",
        "Navkiran Kaur",
    ]
    ordered = sort_completed_by_names(names)
    assert ordered[-1] == "Dr. Mannat Guliani"
    assert ordered[:-1] == ["Geetika", "Navkiran Kaur", "Shalini Dhiman", "Yashvi Jolly"]
    assert is_mannat_guliani("Mannat Guliani")
    assert is_mannat_guliani("Dr. Mannat Guliani")
    assert not is_mannat_guliani("Shalini Dhiman")
    assert sort_completed_by_names(["Mannat Guliani", "Geetika"])[-1] == "Mannat Guliani"


@pytest.fixture
def users_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[models.User.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_backfill_scientist_names_strips_dr(users_db):
    users_db.add(
        models.User(
            username="shalini.pgimer",
            hashed_password="x",
            role="site_scientist",
            site_name="PGIMER",
            full_name="Dr. Shalini Dhiman",
        )
    )
    users_db.add(
        models.User(
            username="tanvi.pgimer",
            hashed_password="x",
            role="nurse",
            site_name="PGIMER",
            full_name="Tanvi Saini",
        )
    )
    users_db.commit()
    assert backfill_scientist_names(users_db) == 1
    assert (
        users_db.query(models.User)
        .filter_by(username="shalini.pgimer")
        .one()
        .full_name
        == "Shalini Dhiman"
    )
    assert backfill_scientist_names(users_db) == 0
