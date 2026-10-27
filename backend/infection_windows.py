"""Infection trigger windows from the Infect/GI/Hema day logs (Helper 4).

Moved out of main.py unchanged (2026-10-26) so the site summary can use the
same episodes as Form H's H11 banner, Form I I.2 and the AE scan.
"""
import json
from datetime import timedelta


def _consecutive_day_runs(days):
    """Collapses a sorted, deduplicated list of NICU day numbers into
    maximal consecutive runs, e.g. [4,5,6,9,10] -> [(4,6), (9,10)]."""
    if not days:
        return []
    runs = []
    start = prev = days[0]
    for d in days[1:]:
        if d == prev + 1:
            prev = d
            continue
        runs.append((start, prev))
        start = prev = d
    runs.append((start, prev))
    return runs


def _compute_infection_windows(logs, nicu):
    """Shared trigger-window builder used by both get_infection_detect
    (Form H's advisory H11 banner) and get_post_resus_prefill (Form I's
    I.2 EOS/LOS/culture derivation) — kept as one function so the trigger
    rule only needs to be right in one place. See get_infection_detect's
    own docstring for the full trigger rule and the reasoning behind it
    (culture > screen > antibiotic-duration priority, no cross-type
    merging, etc.) — that reasoning is unchanged, this is a pure
    extraction, not a behavior change.
    """

    def date_for(day):
        if not nicu or not nicu.day1_date:
            return None
        return (nicu.day1_date + timedelta(days=day - 1)).isoformat()

    def make_window(signature, reason, suggested_type, start, end, **extra):
        return {
            "signature": signature,
            "reason": reason,
            "suggested_type": suggested_type,
            "nicu_day_start": start,
            "nicu_day_end": end,
            "date_start": date_for(start),
            "date_end": date_for(end),
            **extra,
        }

    windows = []

    culture_days = sorted({l.nicu_day for l in logs if l.blood_culture_positive is True})
    for start, end in _consecutive_day_runs(culture_days):
        windows.append(make_window(
            f"culture:{start}-{end}", "Blood culture positive", "culture", start, end,
        ))

    # Helper Form 3 stores "Awaited" as sent=True with positive still None.
    # Do not fold these into culture_days / covered_days — a pending result
    # must not suppress a >5-day antibiotics clinical-sepsis suggestion.
    culture_awaited_days = sorted({
        l.nicu_day for l in logs
        if l.blood_culture_sent is True and l.blood_culture_positive is None
    })
    for start, end in _consecutive_day_runs(culture_awaited_days):
        windows.append(make_window(
            f"culture_awaited:{start}-{end}", "Blood culture sent, result awaited",
            "culture_awaited", start, end,
        ))

    screen_positive_days = set()
    for l in logs:
        try:
            screens = json.loads(l.sepsis_screens_json) if l.sepsis_screens_json else []
        except (ValueError, TypeError):
            screens = []
        if any((s or {}).get("result") == "Positive" for s in screens):
            screen_positive_days.add(l.nicu_day)
    screen_only_days = sorted(screen_positive_days - set(culture_days))
    for start, end in _consecutive_day_runs(screen_only_days):
        windows.append(make_window(
            f"screen:{start}-{end}", "Sepsis screen positive", "screen", start, end,
        ))

    covered_days = set(culture_days) | screen_positive_days
    antibiotic_days = sorted({l.nicu_day for l in logs if l.antibiotics is True})
    for start, end in _consecutive_day_runs(antibiotic_days):
        if (end - start + 1) > 5 and not (set(range(start, end + 1)) & covered_days):
            windows.append(make_window(
                f"antibiotics:{start}-{end}", "Antibiotics >5 continuous days", "clinical", start, end,
            ))

    meningitis_days = sorted({
        l.nicu_day for l in logs
        if l.meningitis is True or (l.meningitis_type or "").strip()
    })
    for start, end in _consecutive_day_runs(meningitis_days):
        windows.append(make_window(
            f"meningitis:{start}-{end}", "Meningitis", None, start, end, meningitis=True,
        ))

    clabsi_days = sorted({l.nicu_day for l in logs if l.clabsi is True})
    for start, end in _consecutive_day_runs(clabsi_days):
        windows.append(make_window(
            f"clabsi:{start}-{end}", "CLABSI", None, start, end, clabsi=True,
        ))

    vap_days = sorted({l.nicu_day for l in logs if l.vap is True})
    for start, end in _consecutive_day_runs(vap_days):
        windows.append(make_window(
            f"vap:{start}-{end}", "VAP", None, start, end, vap=True,
        ))

    windows.sort(key=lambda w: w["nicu_day_start"])
    return windows
