"""Plausible ranges for typed numbers, approved by the Global PI 2026-11-12
(reviews/PORTAL_value_ranges_review_2026-11-12.xlsx, "Final" columns).

Two limits per field:
  confirm range  outside it the value saves; the screen warns and the data
                 query VALUE_OUT_OF_RANGE asks the site to check it
  refuse limit   outside it the save is refused (422), web and tablet alike

The server check is one SQLAlchemy before_flush listener (install()), so every
save path is covered. It looks only at values being typed or changed in this
save: a wrong value saved earlier never blocks saving the rest of a record.
Urine output has its own rules in value_ranges.py (it needs weight and hours).

The same table is in frontend-app/src/utils/valueRanges.js: keep them in step.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from value_ranges import RangeError, _num, fmt

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


@dataclass(frozen=True)
class Rule:
    key: str                 # unique id, also used by the frontend
    form: str
    label: str
    unit: str
    table: str
    column: str              # column, DMS block, or readings column
    confirm_lo: Optional[float]
    confirm_hi: Optional[float]
    refuse_lo: Optional[float]
    refuse_hi: Optional[float]
    kind: str = "col"        # col | text | readings | dms | per_kg
    field: Optional[str] = None   # key inside a DMS entry or a reading

    @property
    def attr(self) -> str:
        """The stored column (DMS blocks live in entries_json)."""
        return "entries_json" if self.kind == "dms" else self.column


R = Rule
RULES: tuple[Rule, ...] = (
    # Form B
    R("birth_weight", "Form B", "Birth weight", "g", "birth_resuscitation", "birth_weight", 400, 3000, 300, 4000),
    R("cord_clamp_time", "Form B", "Cord clamping time", "s", "birth_resuscitation", "cord_clamp_time", None, 180, 0, 600),
    R("spo2_5min", "Form B", "SpO2 at 5 min", "%", "birth_resuscitation", "spo2_5min", 40, None, 0, 100),
    R("cord_ph", "Form B", "Cord pH", "", "birth_resuscitation", "cord_ph", 6.8, 7.5, 6.5, 7.8),
    R("cord_pco2", "Form B", "Cord pCO2", "mmHg", "birth_resuscitation", "cord_pco2", 25, 90, 10, 150),
    R("cord_sbe", "Form B", "Cord base excess", "mmol/L", "birth_resuscitation", "cord_sbe", -20, 5, -30, 10),
    R("tpiece_pip", "Form B", "T-piece PIP", "cmH2O", "birth_resuscitation", "tpiece_pip", 12, 30, 5, 40),
    R("tpiece_peep", "Form B", "T-piece PEEP", "cmH2O", "birth_resuscitation", "tpiece_peep", 4, 8, 3, 15),
    R("tpiece_flow", "Form B", "T-piece gas flow", "L/min", "birth_resuscitation", "tpiece_flow", 4, 12, 1, 15),
    # Form C
    R("mother_age", "Form C", "Mother's age", "years", "maternal_details", "mother_age", 16, 45, 12, 60),
    # Form D
    R("d_fio2", "Form D", "FiO2", "%", "postnatal_day1", "fio2_percent", None, None, 21, 100),
    R("d_max_fio2_1hr", "Form D", "Max FiO2 in first hour", "%", "postnatal_day1", "max_fio2_1hr", None, None, 21, 100),
    R("d_cpap", "Form D", "CPAP pressure", "cmH2O", "postnatal_day1", "cpap_cm", 4, 10, 0, 15),
    R("d_surfactant", "Form D", "Surfactant dose", "mg/kg", "postnatal_day1", "surfactant_dose", 100, 200, 50, 300),
    R("d_caffeine_load", "Form D", "Caffeine loading dose", "mg/kg", "postnatal_day1", "caffeine_loading_abs",
      10, 25, 5, 50, kind="per_kg"),
    # Form E
    R("e_temp_dr", "Form E", "Delivery room temperature", "°C", "nicu_admission", "temp_dr", 35, 38, 25, 42),
    R("e_temp_skin", "Form E", "Skin temperature on admission", "°C", "nicu_admission", "temp_skin", 35, 38, 25, 42),
    R("e_temp_axillary", "Form E", "Axillary temperature on admission", "°C", "nicu_admission", "temp_axillary", 35, 38, 25, 42),
    R("e_transport_fio2", "Form E", "Transport FiO2", "%", "nicu_admission", "transport_fio2", None, None, 21, 100),
    R("e_nicu_fio2", "Form E", "NICU FiO2", "%", "nicu_admission", "nicu_fio2", None, None, 21, 100),
    R("e_transport_cpap", "Form E", "Transport CPAP", "cmH2O", "nicu_admission", "transport_cpap", 4, 10, 0, 15),
    R("e_nicu_cpap", "Form E", "NICU CPAP", "cmH2O", "nicu_admission", "nicu_cpap", 4, 10, 0, 15),
    R("e_transport_peep", "Form E", "Transport PEEP", "cmH2O", "nicu_admission", "transport_peep", 4, 10, 0, 15),
    R("e_nicu_peep", "Form E", "NICU PEEP", "cmH2O", "nicu_admission", "nicu_peep", 4, 10, 0, 15),
    R("e_transport_pip", "Form E", "Transport PIP", "cmH2O", "nicu_admission", "transport_pip", 12, 30, 5, 40),
    R("e_nicu_pip", "Form E", "NICU PIP", "cmH2O", "nicu_admission", "nicu_pip", 12, 30, 5, 40),
    R("e_transport_map", "Form E", "Transport MAP (HFO)", "cmH2O", "nicu_admission", "transport_map", 6, 18, 0, 30),
    R("e_nicu_map", "Form E", "NICU MAP (HFO)", "cmH2O", "nicu_admission", "nicu_map", 6, 18, 0, 30),
    # DMS (entries_json blocks)
    R("dms_weight", "DMS 5.7.A", "Weight", "g", "minimal_monitoring_day_logs", "growth_a", None, None, 300, 6000,
      kind="dms", field="weight_g"),
    R("dms_temp", "DMS 5.1.A", "Axillary temperature", "°C", "minimal_monitoring_day_logs", "cv_a", 35, 37.8, 24, 42,
      kind="dms", field="axillary_temp"),
    R("dms_sbp", "DMS 5.1.A", "Systolic BP", "mmHg", "minimal_monitoring_day_logs", "cv_a", 30, 90, 15, 140,
      kind="dms", field="sbp"),
    R("dms_dbp", "DMS 5.1.A", "Diastolic BP", "mmHg", "minimal_monitoring_day_logs", "cv_a", 10, 60, 5, 100,
      kind="dms", field="dbp"),
    R("dms_map", "DMS 5.1.A", "Mean BP", "mmHg", "minimal_monitoring_day_logs", "cv_a", 15, 60, 10, 100,
      kind="dms", field="map_value"),
    R("dms_glucose", "DMS 5.3.A", "Glucose", "mg/dL", "minimal_monitoring_day_logs", "met_a", 20, 200, 5, 600,
      kind="dms", field="glucose"),
    R("dms_ph", "DMS 5.2.B", "pH", "", "minimal_monitoring_day_logs", "resp_b", 6.8, 7.6, 6.5, 7.9,
      kind="dms", field="ph"),
    R("dms_paco2", "DMS 5.2.B", "PaCO2", "mmHg", "minimal_monitoring_day_logs", "resp_b", 20, 100, 10, 150,
      kind="dms", field="paco2"),
    R("dms_pao2", "DMS 5.2.B", "PaO2", "mmHg", "minimal_monitoring_day_logs", "resp_b", 25, 200, 10, 600,
      kind="dms", field="pao2"),
    # Helper 2
    R("h2_ph", "Helper 2", "Lowest pH", "", "resp_cv_neuro_day_logs", "lowest_ph", 6.8, 7.6, 6.5, 7.9, kind="text"),
    R("h2_paco2", "Helper 2", "PaCO2", "mmHg", "resp_cv_neuro_day_logs", "paco2_range", 20, 100, 10, 150, kind="text"),
    R("h2_pao2", "Helper 2", "PaO2", "mmHg", "resp_cv_neuro_day_logs", "pao2_range", 25, 200, 10, 600, kind="text"),
    R("h2_max_fio2", "Helper 2", "Max FiO2", "%", "resp_cv_neuro_day_logs", "max_fio2", None, None, 21, 100),
    R("h2_max_flow", "Helper 2", "Max gas flow", "L/min", "resp_cv_neuro_day_logs", "max_flow", None, 20, 0, 30),
    # Helper 4
    R("h4_feed", "Helper 4", "Feed volume", "ml/kg/day", "infect_gi_hema_day_logs", "feed_volume", None, 200, 0, 300),
    R("h4_hb", "Helper 4", "Haemoglobin", "g/dL", "infect_gi_hema_day_logs", "hb_value", 7, 22, 3, 28),
    R("h4_tsb", "Helper 4", "Peak TSB", "mg/dL", "infect_gi_hema_day_logs", "peak_tsb", None, 25, 0, 40),
    # Helper 5
    R("h5_creatinine", "Helper 5", "Serum creatinine", "mg/dL", "metab_renal_vasc_eye_day_logs", "creatinine_value",
      0.2, 2.0, 0.1, 6.0, kind="text"),
    R("h5_sodium", "Helper 5", "Sodium", "mmol/L", "metab_renal_vasc_eye_day_logs", "sodium_readings_json",
      125, 155, 100, 190, kind="readings", field="value"),
    R("h5_potassium", "Helper 5", "Potassium", "mmol/L", "metab_renal_vasc_eye_day_logs", "potassium_readings_json",
      2.5, 7.5, 1.5, 10, kind="readings", field="value"),
    R("h5_calcium", "Helper 5", "Ionised calcium", "mmol/L", "metab_renal_vasc_eye_day_logs", "calcium_readings_json",
      0.6, 1.5, 0.4, 2.5, kind="readings", field="value"),
    # Form H
    R("h_discharge_weight", "Form H", "Discharge weight", "g", "neonatal_morbidities", "discharge_weight",
      1000, 4000, 800, 8000),
    R("h_los", "Form H", "Length of stay", "days", "neonatal_morbidities", "total_los_days", None, 150, 0, 365),
)
BY_TABLE: dict[str, list[Rule]] = {}
for _r in RULES:
    BY_TABLE.setdefault(_r.table, []).append(_r)


def level(rule: Rule, v: Optional[float]) -> Optional[str]:
    """'impossible' outside the refuse limits, 'high' / 'low' outside the
    confirm range, None when fine or not a number."""
    if v is None:
        return None
    if (rule.refuse_lo is not None and v < rule.refuse_lo) or (rule.refuse_hi is not None and v > rule.refuse_hi):
        return "impossible"
    if rule.confirm_hi is not None and v > rule.confirm_hi:
        return "high"
    if rule.confirm_lo is not None and v < rule.confirm_lo:
        return "low"
    return None


def expected(rule: Rule) -> str:
    lo, hi = rule.confirm_lo, rule.confirm_hi
    if lo is not None and hi is not None:
        return f"{fmt(lo)}-{fmt(hi)}"
    return f"up to {fmt(hi)}" if hi is not None else (f"{fmt(lo)} or more" if lo is not None else "")


def possible(rule: Rule) -> str:
    lo, hi = rule.refuse_lo, rule.refuse_hi
    if lo is not None and hi is not None:
        return f"{fmt(lo)}-{fmt(hi)}"
    return f"up to {fmt(hi)}" if hi is not None else f"{fmt(lo)} or more"


def text_numbers(v) -> list[float]:
    """Numbers in a typed text value ("45-60", "6.9", "Result Awaited")."""
    if v is None:
        return []
    if isinstance(v, (int, float)):
        return [float(v)]
    s = str(v).replace("–", " ").replace("—", " ")
    out = []
    for m in NUM_RE.finditer(s):
        tok = m.group(0)
        # "45-60" is a range, not 45 and -60
        if tok.startswith("-") and m.start() > 0 and s[m.start() - 1].isdigit():
            tok = tok[1:]
        out.append(float(tok))
    return out


def _json(v):
    if not v:
        return None
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return None


def dms_values(entries_json, block: str, field: str) -> list[tuple[str, str, float]]:
    """(date, time, value) for one field of one DMS block."""
    parsed = _json(entries_json)
    rows = parsed.get(block) if isinstance(parsed, dict) else None
    out = []
    for e in rows if isinstance(rows, list) else []:
        if isinstance(e, dict):
            n = _num(e.get(field))
            if n is not None:
                out.append((str(e.get("date") or ""), str(e.get("time") or ""), n))
    return out


def reading_values(readings_json, field: str) -> list[tuple[str, str, float]]:
    rows = _json(readings_json)
    out = []
    for e in rows if isinstance(rows, list) else []:
        if isinstance(e, dict):
            n = _num(e.get(field))
            if n is not None:
                out.append((str(e.get("date") or ""), str(e.get("time") or ""), n))
    return out


def values_of(rule: Rule, raw, weight_kg: Optional[float] = None) -> list[tuple[str, str, float]]:
    """Every number a rule applies to in one stored column value."""
    if rule.kind == "col":
        n = _num(raw)
        return [] if n is None else [("", "", n)]
    if rule.kind == "per_kg":
        n = _num(raw)
        return [] if n is None or not weight_kg else [("", "", round(n / weight_kg, 1))]
    if rule.kind == "text":
        return [("", "", n) for n in text_numbers(raw)]
    if rule.kind == "readings":
        return reading_values(raw, rule.field)
    if rule.kind == "dms":
        return dms_values(raw, rule.column, rule.field)
    return []


def _refusal(rule: Rule, v: float) -> str:
    unit = f" {rule.unit}" if rule.unit else ""
    return (f"{rule.form}: {rule.label} of {fmt(v)}{unit} is not possible (allowed {possible(rule)}{unit}). "
            "Check the value and its unit.")


# ------------------------------------------------------------------ on save
def _weight_for(session: Session, obj) -> Optional[float]:
    """Form D caffeine: Form D birth weight, else Form B."""
    g = _num(getattr(obj, "birth_weight", None))
    if not g:
        from models import BirthResuscitation
        with session.no_autoflush:
            b = session.query(BirthResuscitation.birth_weight).filter(
                BirthResuscitation.enrollment_id == getattr(obj, "enrollment_id", None)).first()
        g = _num(b[0]) if b else None
    return g / 1000.0 if g and g > 0 else None


def check_object(session: Session, obj) -> None:
    """Refuse an impossible value typed or changed in this save."""
    rules = BY_TABLE.get(getattr(obj, "__tablename__", ""))
    if not rules:
        return
    state = inspect(obj)
    for rule in rules:
        attr = state.attrs.get(rule.attr)
        if attr is None:
            continue
        hist = attr.load_history()
        if not hist.has_changes():
            continue
        new = hist.added[0] if hist.added else None
        old = hist.deleted[0] if hist.deleted else None
        kg = _weight_for(session, obj) if rule.kind == "per_kg" else None
        before = {v for v in values_of(rule, old, kg)}
        for item in values_of(rule, new, kg):
            if item in before:
                continue   # already saved before: never block the rest of the save
            if level(rule, item[2]) == "impossible":
                raise RangeError(_refusal(rule, item[2]))
    if getattr(obj, "__tablename__", "") == "minimal_monitoring_day_logs":
        _check_bp_order(obj)


def _check_bp_order(obj) -> None:
    """DMS: diastolic must be below systolic on the same reading (new readings)."""
    state = inspect(obj)
    hist = state.attrs.entries_json.load_history()
    if not hist.has_changes():
        return
    old = _json(hist.deleted[0] if hist.deleted else None) or {}
    new = _json(hist.added[0] if hist.added else None) or {}
    seen = {json.dumps(e, sort_keys=True) for e in (old.get("cv_a") or []) if isinstance(e, dict)}
    for e in new.get("cv_a") or []:
        if not isinstance(e, dict) or json.dumps(e, sort_keys=True) in seen:
            continue
        s, d = _num(e.get("sbp")), _num(e.get("dbp"))
        if s is not None and d is not None and d >= s:
            raise RangeError(f"DMS 5.1.A: diastolic {fmt(d)} mmHg is not below systolic {fmt(s)} mmHg "
                             f"({e.get('time') or 'reading'}). Check both values.")


def _before_flush(session: Session, flush_context, instances) -> None:
    for obj in list(session.new) + list(session.dirty):
        if getattr(obj, "__tablename__", "") in BY_TABLE:
            check_object(session, obj)


def install() -> None:
    if not event.contains(Session, "before_flush", _before_flush):
        event.listen(Session, "before_flush", _before_flush)
