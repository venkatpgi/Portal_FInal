from datetime import date, datetime
from types import SimpleNamespace as NS

from death_alert import _email, form_i_death, grade_5_on_form, has_death_report, report_due


def test_due_is_24_hours_after_the_death():
    assert report_due(date(2026, 10, 30), "14:00") == datetime(2026, 10, 31, 14, 0)
    assert report_due(date(2026, 10, 30), None) == datetime(2026, 10, 31, 23, 59)
    assert report_due(None, "14:00") is None


def test_form_i_death_any_section_first_date_found():
    assert form_i_death(None) == (False, None, None)
    so = NS(mortality_7_days=None, death36=True, death36_date=date(2026, 10, 30), death36_time="14:00")
    assert form_i_death(so) == (True, date(2026, 10, 30), "14:00")
    assert form_i_death(NS(death36=True)) == (True, None, None)
    assert form_i_death(NS(death36=False)) == (False, None, None)


def test_a_grade_5_or_death_row_is_enough():
    assert not grade_5_on_form([{"description": "NEC", "grade": "3"}])
    assert grade_5_on_form([{"description": "NEC", "grade": "5"}])
    assert grade_5_on_form([{"description": "Death", "grade": None}])
    assert not grade_5_on_form(None)


def test_only_a_fatal_report_with_a_diagnosis_counts():
    fatal = NS(diagnosis="Shock", seriousness=["Death"], outcome=None)
    assert has_death_report([fatal])
    assert not has_death_report([NS(diagnosis="Shock", seriousness=[], outcome="Recovered")])
    assert not has_death_report([NS(diagnosis="", seriousness=["Death"], outcome="Fatal")])


def test_email_carries_ids_only():
    s = {"date": "2026-10-30", "time": "14:00", "due": "2026-10-31T14:00"}
    subject, html = _email("01-B-005", "PGIMER, Chandigarh", s, False)
    assert "Death recorded" in subject and "01-B-005" in subject
    assert "2026-10-31 14:00 IST" in html
    assert "Reminder" in _email("01-B-005", "PGIMER", s, True)[0]
