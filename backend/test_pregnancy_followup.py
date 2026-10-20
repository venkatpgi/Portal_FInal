from datetime import date

from pregnancy_followup import consent_change_error, followup_errors

TODAY = date(2026, 10, 20)
SCREENED = date(2026, 10, 1)


def test_refused_cannot_become_yes_once_saved():
    assert consent_change_error("No", "Yes", True, False, 200)
    assert consent_change_error("No", "Yes", False, False, 200) is None  # unsaved draft
    assert consent_change_error("No", "Yes", True, True, 200) is None    # PI correction


def test_given_consent_stands():
    assert "withdraws" in consent_change_error("Yes", "No", True, False, 200)


def test_not_approached_can_be_approached_in_window():
    assert consent_change_error("Not approached", "Yes", True, False, 30 * 7) is None
    assert "32w0d" in consent_change_error("Not approached", "Yes", True, False, 32 * 7)


def test_episodes_in_order():
    ok = {"pregnancy_episodes": [{"discharged": date(2026, 10, 5), "readmitted": date(2026, 10, 12)},
                                 {"discharged": date(2026, 10, 15), "readmitted": None}]}
    assert followup_errors(ok, "Yes", SCREENED, False, TODAY) == []
    bad = {"pregnancy_episodes": [{"discharged": date(2026, 10, 5), "readmitted": None},
                                  {"discharged": date(2026, 10, 15), "readmitted": None}]}
    assert followup_errors(bad, "Yes", SCREENED, False, TODAY)


def test_outcome_and_withdrawal_rules():
    assert followup_errors({"pregnancy_outcome": "Delivered elsewhere"}, "Yes", SCREENED, False, TODAY)  # no date
    assert followup_errors({"pregnancy_outcome": "Lost to follow-up", "pregnancy_outcome_date": TODAY},
                           "Yes", SCREENED, False, TODAY) == []
    assert followup_errors({"consent_withdrawn": True, "consent_withdrawn_date": TODAY},
                           "Yes", SCREENED, True, TODAY)  # Form B exists
    assert followup_errors({}, "No", SCREENED, False, TODAY)  # refused: no follow-up
