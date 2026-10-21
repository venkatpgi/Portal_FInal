from datetime import date, datetime

from ops_tasks import baby_tasks, woman_tasks

TODAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 20, 10, 0)


def _w(**kw):
    w = {"consent_given": "Yes", "consent_withdrawn": False, "has_form_b": False, "birth_logged": False,
         "pregnancy_outcome": None, "ga_weeks": 28, "ga_days": 0, "screened_on": date(2026, 10, 1)}
    w.update(kw)
    return w


def test_pregnant_woman_is_not_a_task():
    assert woman_tasks(_w(), TODAY) == []


def test_birth_logged_without_form_b_is_a_task():
    assert woman_tasks(_w(birth_logged=True), TODAY)[0][0] == "delivered_no_form_b"
    assert woman_tasks(_w(pregnancy_outcome="Delivered here"), TODAY)[0][0] == "delivered_no_form_b"


def test_overdue_at_37_weeks_unless_outcome_recorded():
    old = _w(ga_weeks=31, ga_days=0, screened_on=date(2026, 9, 1))  # 31w0d + 49 d = 38w0d
    assert woman_tasks(old, TODAY) == [("consented_overdue_no_birth", "now 38w0d")]
    assert woman_tasks(dict(old, pregnancy_outcome="Delivered elsewhere"), TODAY) == []
    assert woman_tasks(dict(old, consent_withdrawn=True), TODAY) == []


def test_refused_or_form_b_done_never_a_task():
    assert woman_tasks(_w(consent_given="No", birth_logged=True), TODAY) == []
    assert woman_tasks(_w(has_form_b=True, birth_logged=True), TODAY) == []


def _b(**kw):
    b = {"required_resuscitation": True, "dob": date(2026, 10, 15), "ga_birth_weeks": 28, "ga_birth_days": 0,
         "has_form_c": True, "has_form_i": False, "discharge_date": None, "death_day": None,
         "helper_days": {2: {1, 2, 3, 4, 5}, 4: {1, 2, 3, 4, 5}, 5: {1, 2, 3, 4, 5}}}
    b.update(kw)
    return b


def test_new_baby_with_logs_has_no_task():
    # Form I not due at 28w5d PMA; days 1-5 (to yesterday) all logged
    assert baby_tasks(_b(), NOW) == []


def test_no_ppv_baby_never_a_task():
    assert baby_tasks(_b(required_resuscitation=False, has_form_c=False, helper_days={}), NOW) == []


def test_form_c_and_form_i_due():
    keys = [k for k, _ in baby_tasks(_b(has_form_c=False, ga_birth_weeks=35, ga_birth_days=2), NOW)]
    assert keys == ["ppv_no_form_c", "form_i_due"]
    assert ("form_i_due", "stay ended") in baby_tasks(_b(discharge_date=date(2026, 10, 18),
                                                       helper_days={h: {1, 2, 3, 4} for h in (2, 4, 5)}), NOW)


def test_missing_daily_logs_stop_at_discharge():
    gaps = baby_tasks(_b(helper_days={2: {1, 2, 3, 4, 5}, 4: {1, 2, 3}, 5: {1, 2, 3, 4, 5}}), NOW)
    assert gaps == [("daily_logs_missing", "Helper 4: 2 of 5 days")]
    # discharged on day 3: days 4-5 are not required
    assert baby_tasks(_b(discharge_date=date(2026, 10, 17), has_form_i=True,
                         helper_days={h: {1, 2, 3} for h in (2, 4, 5)}), NOW) == []
