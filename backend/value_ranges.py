"""Plausible-range rules for numbers typed into the forms (PI 2026-11-11).

Urine output (Helper 5, item 13) is the first one. Nurses type millilitres
per window (8am-2pm 6 h, 2pm-8pm 6 h, 8pm-8am 12 h); the rate is
ml / (weight kg x hours), with the weight Harsh's screen uses: the latest
DMS 5.7.A weight on or before that day, or the birth weight if the DMS
weight is lower or missing (frontend effectiveFeedWeightKg).

  rate > 15 ml/kg/hr          refused on save (no preterm baby passes this)
  rate > 6 or < 0.5 ml/kg/hr  saved, the screen warns, and a data query asks
                              the site to confirm against the bedside chart
  window left blank           data query once the day is over (no status ticked)

The data queries live in data_checks.py: URINE_OUT_OF_RANGE and
URINE_WINDOW_MISSING. Facts carry ml only, so a later weight does not reopen
a value the site has confirmed.
"""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import HTTPException

URINE_WINDOWS = (
    ("urine_output_8am_2pm", "8am-2pm", 6),
    ("urine_output_2pm_8pm", "2pm-8pm", 6),
    ("urine_output_8pm_8am", "8pm-8am", 12),
)
URINE_REFUSE_ABOVE = 15.0
URINE_HIGH_ABOVE = 6.0
URINE_LOW_BELOW = 0.5
# End of a NICU day's last window (8am next day IST) in UTC, plus a day's grace
DAY_END_UTC = time(2, 30)
MISSING_GRACE = timedelta(hours=24)


class RangeError(HTTPException):
    """A save the range rules refuse: a 422 with a plain message. An
    HTTPException, so endpoints that re-raise HTTPException pass it through."""

    def __init__(self, message: str):
        super().__init__(status_code=422, detail=message)

    def __str__(self) -> str:
        return str(self.detail)


def _num(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if n == n else None   # NaN


def effective_weight_kg(birth_weight_g, dms_kg) -> Optional[float]:
    """Same rule as the screen: DMS weight once it is back to birth weight."""
    birth = _num(birth_weight_g)
    birth = birth / 1000.0 if birth and birth > 0 else None
    dms = _num(dms_kg)
    dms = dms if dms and dms > 0 else None
    if birth and dms:
        return max(birth, dms)
    return birth or dms


def rate(ml, weight_kg, hours) -> Optional[float]:
    ml, kg = _num(ml), _num(weight_kg)
    if ml is None or not kg or kg <= 0 or not hours:
        return None
    return round(ml / (kg * hours), 2)


def level(r: Optional[float]) -> Optional[str]:
    if r is None:
        return None
    if r > URINE_REFUSE_ABOVE:
        return "impossible"
    if r > URINE_HIGH_ABOVE:
        return "high"
    if r < URINE_LOW_BELOW:
        return "low"
    return None


def total_rate(values: dict, weight_kg) -> Optional[float]:
    """Daily ml/kg/hr over the windows that have a value (as the screen)."""
    ml = hours = 0.0
    for field, _label, h in URINE_WINDOWS:
        if values.get(f"{field}_status"):
            continue
        v = _num(values.get(field))
        if v is None:
            continue
        ml, hours = ml + v, hours + h
    if not hours:
        return None
    return rate(ml, weight_kg, hours)


def fmt(r: Optional[float]) -> Optional[str]:
    if r is None:
        return None
    s = f"{r:.2f}".rstrip("0").rstrip(".")
    return s or "0"


def flags(values: dict, weight_kg) -> list[dict]:
    """Out-of-range windows: field, label, ml, rate, level."""
    out = []
    for field, label, h in URINE_WINDOWS:
        if values.get(f"{field}_status"):
            continue
        r = rate(values.get(field), weight_kg, h)
        lv = level(r)
        if lv:
            out.append({"field": field, "label": label, "ml": _num(values.get(field)), "rate": r, "level": lv})
    return out


# ------------------------------------------------------------------ weights
def dms_weights(entries_rows) -> list[tuple[str, str, float]]:
    """(date, time, kg) from DMS 5.7.A rows of (record_date, entries_json)."""
    out = []
    for record_date, raw in entries_rows:
        if not raw:
            continue
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            continue
        block = (parsed or {}).get("growth_a") if isinstance(parsed, dict) else None
        if not isinstance(block, list):
            continue
        for e in block:
            if not isinstance(e, dict):
                continue
            d = e.get("date") or record_date
            g = _num(e.get("weight_g"))
            if d and g and g > 0:
                out.append((str(d)[:10], str(e.get("time") or ""), g / 1000.0))
    return out


def dms_weight_on(weights, as_of: str) -> Optional[float]:
    """Latest DMS weight on or before as_of (YYYY-MM-DD)."""
    best = None
    for d, t, kg in weights:
        if d <= as_of and (best is None or (d, t) > best[0]):
            best = ((d, t), kg)
    return best[1] if best else None


def weight_for_day(db, enrollment_id: str, nicu_day: int) -> Optional[float]:
    from sqlalchemy import text
    row = db.execute(text("SELECT birth_weight, date_of_birth FROM birth_resuscitation WHERE enrollment_id = :e"),
                     {"e": enrollment_id}).first()
    if not row:
        return None
    dms = None
    if row[1] and nicu_day:
        as_of = (row[1] + timedelta(days=int(nicu_day) - 1)).isoformat()
        rows = db.execute(text("SELECT record_date, entries_json FROM minimal_monitoring_day_logs "
                               "WHERE enrollment_id = :e"), {"e": enrollment_id}).all()
        dms = dms_weight_on(dms_weights(rows), as_of)
    return effective_weight_kg(row[0], dms)


# ------------------------------------------------------------------ on save
def check_urine_save(db, enrollment_id: str, nicu_day: int, sent: dict, prior=None) -> dict:
    """Refuse an impossible urine value that is being typed now, and store the
    total as ml/kg/hr worked out on the server. Returns the fields to store
    (sent + urine_output_total). Values already saved are left alone, so an
    old wrong value never blocks saving the rest of the day."""
    if not any(k.startswith("urine_output_") for k in sent):
        return sent
    merged = {}
    for field, _l, _h in URINE_WINDOWS:
        for k in (field, f"{field}_status"):
            merged[k] = sent[k] if k in sent else getattr(prior, k, None)
    kg = weight_for_day(db, enrollment_id, nicu_day)
    for f in flags(merged, kg):
        changed = f["field"] in sent and _num(sent.get(f["field"])) != _num(getattr(prior, f["field"], None))
        if f["level"] == "impossible" and changed:
            raise RangeError(
                f"Urine output {f['label']} of {fmt(f['ml'])} ml is {fmt(f['rate'])} ml/kg/hr for a "
                f"{fmt(kg)} kg baby, more than {fmt(URINE_REFUSE_ABOVE)} ml/kg/hr. Check the bedside chart: "
                "enter the millilitres passed in that window.")
    out = dict(sent)
    if kg:
        out["urine_output_total"] = fmt(total_rate(merged, kg))
    return out


# ------------------------------------------------------------------ data checks
def day_over(dob: date, nicu_day: int, now: datetime) -> Optional[datetime]:
    """When the day's last window has ended plus the grace, in naive UTC;
    None if that time has not come yet."""
    end = datetime.combine(dob + timedelta(days=int(nicu_day)), DAY_END_UTC) + MISSING_GRACE
    return end if now >= end else None
