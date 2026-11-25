"""Form H H12 Hospital Course summary from the daily logs (PI 2026-11-24).

Filled only once Form H has a discharge date (or date of death): the H12
boxes summarise the whole stay. The form fills blank boxes only and marks
them "from daily logs"; anything typed stays.

  253 total_los              discharge date - date of birth (PI: days, not +1)
  254 nicu_days              Helper 5 days whose Location includes NICU
  255 o2_days                same count as H2 oxygen_days (Helper 2 supp_o2)
  256 vent_days              same count as H2 imv_days (Helper 2 intubated)
  257 cpap_days              same count as H2 cpap_days (Helper 2 support modes)
  258 pn_days_summary        same count as H3 pn_days (Helper 4 PN)
  259 age_full_feeds_summary first Helper 4 day with feed volume >= 150
                             ml/kg/day (PI), as age in days (day 1 = age 0)
  260 discharge_weight       last DMS weight (5.7.A) in the 7 days up to the
                             discharge date
Discharge HC (261) is not in the daily logs: typed by hand.
Counts with nothing in the logs are 0, not blank (PI 2026-11-26): NICU, O2,
vent, CPAP and PN days. Age at full feeds and discharge weight stay blank
when the logs have no answer (0 would be a wrong value there).
"""
from __future__ import annotations

from datetime import date, timedelta

FULL_FEEDS_ML_KG_DAY = 150
WEIGHT_DAYS_BEFORE = 7
# Helper 5 Location: generic "NICU" plus older labels saved before 2026-11-04
NICU_LABELS = {"NICU", "AMCC-4A (NICU)", "AMCC-4A(NICU)"}


def _locations(raw) -> list[str]:
    if isinstance(raw, (list, tuple)):
        items = raw
    else:
        items = str(raw or "").split(",")
    return [str(x).strip() for x in items if str(x).strip()]


def nicu_days(helper5: list[tuple[int, object]], last_day: int | None) -> int | None:
    """helper5: (nicu_day, location). None when no day has a location."""
    with_loc = [(d, _locations(loc)) for d, loc in helper5
                if d and _locations(loc) and (last_day is None or d <= last_day)]
    if not with_loc:
        return None
    return len({d for d, locs in with_loc if NICU_LABELS & set(locs)})


def age_full_feeds(helper4: list[tuple[int, float | None]]) -> int | None:
    """helper4: (nicu_day, feed volume ml/kg/day)."""
    days = [d for d, v in helper4 if d and v is not None and v >= FULL_FEEDS_ML_KG_DAY]
    return min(days) - 1 if days else None


def discharge_weight(weights: list[tuple[str, str, float]], end: date) -> tuple[float, str] | None:
    """weights: DMS (date ISO, time, grams). The last one from end-7 to end."""
    lo = (end - timedelta(days=WEIGHT_DAYS_BEFORE)).isoformat()
    hi = end.isoformat()
    ok = sorted((d[:10], t, v) for d, t, v in weights if d and lo <= d[:10] <= hi and v and v > 0)
    return (ok[-1][2], ok[-1][0]) if ok else None


def build(dob: date | None, end: date | None, helper5, helper4, weights, resp: dict, gi: dict) -> dict:
    if not end:
        return {"has_data": False, "why": "Enter the discharge date (or date of death) first."}
    last_day = (end - dob).days + 1 if dob else None
    w = discharge_weight(weights, end)
    out = {
        "has_data": True,
        "total_los": (end - dob).days if dob else None,
        # nothing in the logs = 0, not blank (PI 2026-11-26)
        "nicu_days": nicu_days(helper5, last_day) or 0,
        "o2_days": resp.get("oxygen_days") or 0,
        "vent_days": resp.get("imv_days") or 0,
        "cpap_days": resp.get("cpap_days") or 0,
        "pn_days_summary": gi.get("pn_days") or 0,
        "age_full_feeds_summary": age_full_feeds(helper4),
        "discharge_weight": w[0] if w else None,
        "discharge_weight_date": w[1] if w else None,
    }
    return out
