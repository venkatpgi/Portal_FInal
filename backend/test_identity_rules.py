"""CR number / name rules (identity_rules.py). Values made up."""
import pytest
from fastapi import HTTPException

from identity_rules import cr_error, identity_errors, name_error, require_valid_identity


def test_pgimer_cr_exactly_12_digits():
    assert cr_error("PGIMER", "202604585608") is None
    for bad in ("20204555598", "2026024585608", "ASARUL HAK", "2026-0458-5608", "20260458560a"):
        assert cr_error("PGIMER", bad)


def test_amc_and_other_sites():
    assert cr_error("AMC", "123/2026") is None
    assert cr_error("AMC", "1232026")
    assert cr_error("GMCH", "20260495-4829") is None
    assert cr_error("IOG", "AB1234")
    assert cr_error("PGIMER", "") is None


def test_names_without_digits():
    assert name_error("Mother's name", "Reeta Devi") is None
    assert name_error("Mother's name", "Reeta T1")
    assert name_error("Mother's name", "202604601832")


def test_unchanged_stored_value_not_rechecked():
    stored = {"mother_uid": "20204555598", "mother_name": "Reeta T1"}
    assert identity_errors("PGIMER", dict(stored), stored) == []
    assert identity_errors("PGIMER", {"mother_uid": "2020455559"}, stored)


def test_require_raises_422_with_all_problems():
    with pytest.raises(HTTPException) as e:
        require_valid_identity("PGIMER", {"maternal_uid": "123", "mother_first_name": "Seema2", "other": "x"})
    assert e.value.status_code == 422
    assert "12 digits" in e.value.detail and "numbers" in e.value.detail
