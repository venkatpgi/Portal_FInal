"""Form A CR / hospital-number duplicate check. Pure functions, no database."""
from types import SimpleNamespace as R

from identifier_duplicates import find_identifier_conflict, normalize_identifier

ROWS = [
    R(screening_id="01-0001", maternal_uid="2026-0464 4795", hospital_admission_number="9988776655"),
    R(screening_id="01-0002", maternal_uid=None, hospital_admission_number=None),
    R(screening_id="01-0003", maternal_uid="123/2026", hospital_admission_number="44-55 66"),
]


def test_normalisation():
    assert normalize_identifier(" 2026-0464 4795 ") == "202604644795"
    assert normalize_identifier(None) == ""
    assert normalize_identifier("   ") == ""


def test_blank_never_clashes():
    assert find_identifier_conflict(ROWS, "", "") is None
    assert find_identifier_conflict(ROWS, None, None) is None
    assert find_identifier_conflict(ROWS, "", "not-a-match") is None


def test_same_cr_ignoring_case_space_dash():
    label, row = find_identifier_conflict(ROWS, "202604644795", "")
    assert label == "CR number" and row.screening_id == "01-0001"
    label, row = find_identifier_conflict(ROWS, "123/2026", None)
    assert label == "CR number" and row.screening_id == "01-0003"


def test_same_hospital_number():
    label, row = find_identifier_conflict(ROWS, "", "99 88-776655")
    assert label == "Hospital number" and row.screening_id == "01-0001"


def test_either_identifier_alone_triggers():
    label, _ = find_identifier_conflict(ROWS, "202604644795", "unique-hosp")
    assert label == "CR number"
    label, row = find_identifier_conflict(ROWS, "unique-cr", "445566")
    assert label == "Hospital number" and row.screening_id == "01-0003"


def test_unique_values_pass():
    assert find_identifier_conflict(ROWS, "000000000001", "111") is None


def test_resaving_the_same_screening_unchanged_is_allowed():
    assert find_identifier_conflict(
        ROWS, "2026-0464 4795", "9988776655", exclude_screening_id="01-0001"
    ) is None


def test_existing_duplicate_pair_can_be_resaved_unchanged():
    pair = [
        R(screening_id="01-0001", maternal_uid="ABC", hospital_admission_number="1"),
        R(screening_id="01-0009", maternal_uid="abc", hospital_admission_number="1"),
    ]
    assert find_identifier_conflict(
        pair, "ABC", "1", exclude_screening_id="01-0001"
    ) is None
    assert find_identifier_conflict(
        pair, "ABC", "1", exclude_screening_id="01-0009"
    ) is None


def test_changing_an_identifier_to_another_screenings_value_is_blocked():
    label, row = find_identifier_conflict(
        ROWS, "123/2026", "9988776655", exclude_screening_id="01-0001"
    )
    assert label == "CR number" and row.screening_id == "01-0003"
    label, row = find_identifier_conflict(
        ROWS, "202604644795", "445566", exclude_screening_id="01-0001"
    )
    assert label == "Hospital number" and row.screening_id == "01-0003"
