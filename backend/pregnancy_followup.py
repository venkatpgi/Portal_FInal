"""Form A pregnancy follow-up and consent changes after Form A is saved
(PI 2026-10-20).

- Consent given once stands for every later admission of the same pregnancy,
  unless the woman herself withdraws it (recorded here as consent withdrawn,
  never by changing A5 consent to No).
- A woman who refused is not approached again: once Form A is saved, consent
  No cannot be changed (only the Global PI or Site PI may correct a
  data-entry mistake).
- A woman never approached may be approached on a later admission: consent
  "Not approached" may change to Yes while her GA today is still within
  25w0d-31w6d.
- An undelivered woman sent home and readmitted keeps her one Form A; the
  discharges/readmissions and the final pregnancy outcome are recorded here.
"""
from datetime import date

OUTCOMES = ("Delivered here", "Delivered elsewhere", "Lost to follow-up")
GA_MIN_DAYS = 25 * 7
GA_MAX_DAYS = 31 * 7 + 6


def ga_today_days(ga_weeks, ga_days, screened_on: date | None, today: date):
    if ga_weeks is None or screened_on is None:
        return None
    return int(ga_weeks) * 7 + int(ga_days or 0) + (today - screened_on).days


def consent_change_error(old, new, already_saved: bool, can_correct: bool, ga_now_days):
    """Return an error message, or None when the change is allowed."""
    if not already_saved or old == new or not old or new is None:
        return None
    if can_correct:
        return None
    if old == "No":
        return ("She refused consent, and a woman who refused is not approached again. "
                "If 'No' was a data-entry mistake, ask the Site PI or Global PI to correct it.")
    if old == "Yes":
        return ("Consent was given and stands for every admission of this pregnancy. If she withdraws it "
                "herself, record that under 'Pregnancy follow-up' on Form A instead of changing consent. "
                "If 'Yes' was a data-entry mistake, ask the Site PI or Global PI to correct it.")
    if old == "Not approached" and new == "Yes" and ga_now_days is not None:
        if not GA_MIN_DAYS <= ga_now_days <= GA_MAX_DAYS:
            w, d = divmod(ga_now_days, 7)
            return (f"Her GA today is {w}w{d}d, outside 25w0d-31w6d, so she can no longer be enrolled. "
                    "Leave consent as 'Not approached'.")
    return None


def followup_errors(p: dict, consent_given, screened_on: date | None, has_form_b: bool, today: date):
    """p: pregnancy_episodes [{discharged, readmitted}], pregnancy_outcome,
    pregnancy_outcome_date, consent_withdrawn, consent_withdrawn_date.
    Returns a list of messages (empty = valid)."""
    errs = []
    if consent_given != "Yes":
        return ["Pregnancy follow-up is only for a woman who gave consent."]
    floor = screened_on

    def _bad(d):
        return d is not None and ((floor and d < floor) or d > today)

    prev_end = floor
    eps = p.get("pregnancy_episodes") or []
    for i, ep in enumerate(eps, 1):
        dis, re_ = ep.get("discharged"), ep.get("readmitted")
        if dis is None:
            errs.append(f"Episode {i}: discharge date is required.")
            continue
        if _bad(dis) or (prev_end and dis < prev_end):
            errs.append(f"Episode {i}: discharge date must be after screening / the previous readmission and not in the future.")
        if re_ is not None and (re_ < dis or re_ > today):
            errs.append(f"Episode {i}: readmission date must be on/after the discharge and not in the future.")
        if re_ is None and i < len(eps):
            errs.append(f"Episode {i}: only the last discharge can be without a readmission date.")
        prev_end = re_ or dis

    outcome = p.get("pregnancy_outcome")
    if outcome:
        if outcome not in OUTCOMES:
            errs.append("Pregnancy outcome must be one of: " + ", ".join(OUTCOMES) + ".")
        if p.get("pregnancy_outcome_date") is None:
            errs.append("Give the date of the pregnancy outcome.")
        elif _bad(p["pregnancy_outcome_date"]):
            errs.append("Pregnancy outcome date must be after screening and not in the future.")
        if has_form_b and outcome != "Delivered here":
            errs.append("Form B exists, so she delivered here.")
    if p.get("consent_withdrawn"):
        if has_form_b:
            errs.append("Form B already exists; consent withdrawn after the birth is not recorded here. Contact the PI.")
        if p.get("consent_withdrawn_date") is None:
            errs.append("Give the date she withdrew consent.")
        elif _bad(p["consent_withdrawn_date"]):
            errs.append("Consent withdrawal date must be after screening and not in the future.")
    return errs
