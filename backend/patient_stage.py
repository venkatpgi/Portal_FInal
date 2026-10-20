"""Where each screened woman (Form A) stands in the trial pathway.

Shown as the "Stage" column of the dashboard's Screened Participants list
(PI 2026-10-20). It replaced a badge that mapped screening_status
Eligible -> "Active", Screen Failure -> "Failure" and everything else ->
"Pending", so a woman who refused consent (status "Not Eligible") was shown
as Pending.

Form A decides the first stages (compute_screening_status in main.py); once
she has consented, Form B (birth_resuscitation) decides the rest.
"""

# (key, label, tone). Tone picks the badge colour on the page.
STAGES = {
    "form_a_incomplete": ("Form A incomplete", "pending"),
    "consent_pending": ("Consent pending", "pending"),
    "excluded": ("Excluded (A4 / GA unknown)", "failure"),
    "ga_out_of_window": ("Not eligible (GA)", "failure"),
    "consent_refused": ("Consent refused", "failure"),
    "not_approached": ("Not approached for consent", "failure"),
    "awaiting_delivery": ("Consented, awaiting delivery", "active"),
    "form_b_incomplete": ("Delivered, Form B incomplete", "pending"),
    "no_ppv": ("Delivered, no PPV (A-B only)", "complete"),
    "not_randomised": ("PPV, not randomised", "complete"),
    "randomised": ("Randomised", "eligible"),
}


def _ga_in_window(weeks, days):
    if weeks is None:
        return False
    total = int(weeks) * 7 + int(days or 0)
    return 25 * 7 <= total <= 31 * 7 + 6


def patient_stage(screening_status, consent_given, gestation_weeks, gestation_days,
                  has_form_b, required_resuscitation=None, randomised=None):
    """Return a STAGES key for one Form A (+ its Form B, if any)."""
    if screening_status == "Screen Failure":
        return "excluded"
    if screening_status == "Not Eligible":
        if not _ga_in_window(gestation_weeks, gestation_days):
            return "ga_out_of_window"
        if consent_given == "No":
            return "consent_refused"
        if consent_given == "Not approached":
            return "not_approached"
        return "ga_out_of_window"
    if screening_status != "Eligible":
        return "form_a_incomplete" if gestation_weeks is None else "consent_pending"
    if not has_form_b:
        return "awaiting_delivery"
    if randomised is True:
        return "randomised"
    if required_resuscitation is False:
        return "no_ppv"
    if required_resuscitation is True and randomised is False:
        return "not_randomised"
    return "form_b_incomplete"


def stage_payload(key):
    label, tone = STAGES[key]
    return {"stage": key, "label": label, "tone": tone}
