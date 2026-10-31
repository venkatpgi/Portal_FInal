from datetime import date
from types import SimpleNamespace as NS

from routers.dashboard import followup_states

DOB = date(2026, 10, 1)        # 28+0: 36 wk 26 Nov, 40 wk 24 Dec, 44 wk 21 Jan


def form_i(**kw):
    return NS(**{**{f"{a}{w}{b}": None for w in (36, 40, 44) for a, b in (("death", ""), ("encounter", "_method"))}, **kw})


def states(today, fi=None, known=False, when=None):
    return followup_states(DOB, 28, 0, fi, known, when, today)


def test_no_data_waits_then_is_lost():
    assert states(date(2026, 11, 1)) == {36: "awaiting", 40: "awaiting", 44: "awaiting"}
    assert states(date(2026, 12, 25))[36] == "ltfu"


def test_form_i_death_stops_later_checkpoints():
    assert states(date(2026, 10, 5), form_i(death36=True)) == {36: "died"}
    assert states(date(2027, 1, 1), form_i(encounter36_method="Direct", death40=True)) == {36: "assessed", 40: "died"}


def test_form_i_answers_no_to_death_is_not_a_death():
    assert states(date(2026, 10, 5), form_i(death36=False))[36] == "awaiting"


def test_form_h_or_helper_death_counts_before_form_i_is_filled():
    assert states(date(2026, 10, 5), None, True, date(2026, 10, 3)) == {36: "died"}
    assert states(date(2026, 10, 5), None, True, None) == {36: "died"}


def test_death_after_36_weeks_counts_at_the_next_checkpoint():
    assert states(date(2026, 12, 2), form_i(encounter36_method="Telephonic"), True, date(2026, 12, 1)) == {
        36: "assessed", 40: "died"}


def test_no_dates_stays_awaiting():
    assert followup_states(None, None, None, None, False, None, date(2027, 6, 1))[36] == "awaiting"
