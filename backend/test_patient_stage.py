from patient_stage import STAGES, patient_stage


def test_consent_refused_is_not_pending():
    # B/o Shveta (2026-10-20): consent No used to show as "Pending".
    assert patient_stage("Not Eligible", "No", 28, 2, False) == "consent_refused"


def test_ga_outside_window_wins_over_consent():
    assert patient_stage("Not Eligible", "No", 33, 0, False) == "ga_out_of_window"
    assert patient_stage("Not Eligible", "Not approached", 29, 0, False) == "not_approached"


def test_form_a_stages():
    assert patient_stage("Screen Failure", None, None, None, False) == "excluded"
    assert patient_stage("Pending", None, None, None, False) == "form_a_incomplete"
    assert patient_stage("Pending", None, 27, 3, False) == "consent_pending"
    assert patient_stage("Eligible", "Yes", 27, 3, False) == "awaiting_delivery"


def test_form_b_stages():
    assert patient_stage("Eligible", "Yes", 27, 3, True, True, True) == "randomised"
    assert patient_stage("Eligible", "Yes", 27, 3, True, False, None) == "no_ppv"
    assert patient_stage("Eligible", "Yes", 27, 3, True, True, False) == "not_randomised"
    assert patient_stage("Eligible", "Yes", 27, 3, True, None, None) == "form_b_incomplete"


def test_every_stage_has_a_label():
    assert all(len(v) == 2 for v in STAGES.values())
