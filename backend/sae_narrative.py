"""Draft narrative for Form Y item VIII (PI 2026-10-31): fixed rules, no AI.

Every sentence comes from a saved entry, oldest first, for the investigator to
edit. Anything missing says "not recorded". Nothing is inferred.

Blinded: no FiO2 or SpO2 value is read, because they could suggest the arm, and
AE "evidence" text is not used for the same reason. No names or hospital
numbers: only enrolment ID, Form B, the daily logs and the AE terms.
"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from ae_candidates import collect_ae_candidates
from ae_reference import AE_DEFINITIONS
from ae_terms import term_of
from babies import baby_label
from sae_rules import event_title, is_fatal
from site_summary import ACUTE_FLAGS, _int_grade, _iso, _modes

NOT_RECORDED = "not recorded"
DRAFT_LINE = "[Draft built from the portal data. Check it, edit it and delete this line before submitting.]"


def _date(d: date | None) -> str:
    return d.strftime("%d %b %Y") if d else NOT_RECORDED


def course_events(resp, inf, metab, ae_terms) -> list[tuple[int | None, date | None, str]]:
    """[(day of life, date, text)] from the daily logs and AE terms."""
    out = []
    prev_modes = None
    for l in sorted(resp, key=lambda x: x.nicu_day or 0):
        modes = _modes(l)
        if prev_modes is not None and modes != prev_modes:
            out.append((l.nicu_day, None, ("Respiratory support: " + ", ".join(sorted(modes))) if modes
                        else "Respiratory support stopped"))
        elif prev_modes is None and modes:
            out.append((l.nicu_day, None, "Respiratory support: " + ", ".join(sorted(modes))))
        prev_modes = modes
        for attr, label in ACUTE_FLAGS:
            if getattr(l, attr, None) is True:
                out.append((l.nicu_day, None, label))
    days = [l.nicu_day for l in resp if l.vasoactive_support is True]
    if days:
        out.append((min(days), None, "Inotrope support started"))

    previous = {}
    for l in sorted(inf, key=lambda x: x.nicu_day or 0):
        if l.antibiotics is True and not previous.get("abx"):
            out.append((l.nicu_day, None, "Antibiotics started"))
        previous["abx"] = l.antibiotics is True
        if l.nec_confirmed_stage and l.nec_confirmed_stage != previous.get("nec"):
            out.append((l.nicu_day, None, f"NEC stage {l.nec_confirmed_stage}"))
            previous["nec"] = l.nec_confirmed_stage
        elif l.nec_suspected is True and not previous.get("nec"):
            out.append((l.nicu_day, None, "NEC suspected"))
            previous["nec"] = "suspected"
        if l.prbc_transfusion is True:
            out.append((l.nicu_day, None, "Packed red cell transfusion"))
        if l.platelet_transfusion is True:
            out.append((l.nicu_day, None, "Platelet transfusion"))

    for l in metab:
        if l.survived_the_day is False:
            out.append((l.nicu_day, None, "Did not survive the day (Helper 5)"))
    for name, start, grade, auto in ae_terms:
        text = name + (f" grade {grade}" if grade else "") + (" (auto-detected)" if auto else " (AE form)")
        out.append((None, start, text))
    return out


def ae_terms_of(events, candidates) -> list[tuple[str, date | None, int | None, bool]]:
    """[(term, start, grade, auto)], one per term and start, worst grade."""
    seen: dict[tuple, list] = {}
    for rows, auto in ((events, False), (candidates, True)):
        for x in rows or []:
            if not isinstance(x, dict):
                continue
            slug = term_of(x)
            name = AE_DEFINITIONS[slug]["name"] if slug else (x.get("description") or "").strip()
            if not name:
                continue
            key = (name, _iso(x.get("start_date")))
            row = seen.setdefault(key, [name, key[1], None, auto])
            g = _int_grade(x.get("grade"))
            if g and g > (row[2] or 0):
                row[2] = g
    return [tuple(r) for r in seen.values()]


def compose(baby: dict, events: list, form: dict, day1: date | None, today: date) -> str:
    bits = [f"Enrolment {form.get('enrollment_id')}:", "preterm baby"]
    if baby.get("twin"):
        bits.append(f"({baby['twin']})")
    bits.append(f"born on {_date(baby.get('dob'))}")
    bits.append(f"at {baby.get('gestation') or 'gestation ' + NOT_RECORDED},")
    bits.append(f"birth weight {baby['birth_weight']:g} g," if baby.get("birth_weight")
                else f"birth weight {NOT_RECORDED},")
    bits.append(f"{baby.get('gender') or 'sex ' + NOT_RECORDED},")
    bits.append(f"delivery {baby.get('delivery_mode') or NOT_RECORDED}.")

    dated = []
    for day, when, text in events:
        when = when or (day1 + timedelta(days=day - 1) if day1 and day else None)
        if day is None and when and day1:
            day = (when - day1).days + 1
        if when is None or when <= today:
            dated.append((when or date.max, day or 0, text))
    lines = [f"{_date(w) if w != date.max else 'Date ' + NOT_RECORDED}"
             f"{f' (Day {d})' if d else ''}: {t}." for w, d, t in sorted(dated)]

    fatal = is_fatal(SimpleNamespace(seriousness=form.get("seriousness"), outcome=form.get("outcome")))
    onset = (form.get("onset_datetime") or "").replace("T", " ") or NOT_RECORDED
    seriousness = ", ".join(form.get("seriousness") or []) or NOT_RECORDED
    event = [f"SAE: {event_title(form.get('diagnosis'), fatal) or NOT_RECORDED}. Onset {onset}.",
             f"Seriousness: {seriousness}. Severity: {form.get('severity') or NOT_RECORDED}.",
             f"Action taken: {form.get('action_taken') or NOT_RECORDED}.",
             f"Outcome: {'ongoing' if form.get('ongoing') else form.get('outcome') or NOT_RECORDED}."]
    if fatal:
        event.append(f"Date of death: {form.get('date_of_death') or NOT_RECORDED}.")

    parts = [DRAFT_LINE, " ".join(bits)]
    parts.append("Course:\n" + "\n".join(lines) if lines else f"Course: daily entries {NOT_RECORDED}.")
    parts.append(" ".join(event))
    return "\n\n".join(parts)


def build(db, enrollment_id: str, form: dict, today: date | None = None) -> str:
    from clinical_time import clinical_today
    from models import (AdverseEvents, BirthResuscitation, InfectGIHemaDayLog, MetabRenalVascEyeDayLog,
                        NICUAdmission, RespCVNeuroDayLog)

    def logs(model):
        return db.query(model).filter(model.enrollment_id == enrollment_id).all()

    br = db.query(BirthResuscitation).filter(BirthResuscitation.enrollment_id == enrollment_id).first()
    nicu = db.query(NICUAdmission).filter(NICUAdmission.enrollment_id == enrollment_id).first()
    ae = db.query(AdverseEvents).filter(AdverseEvents.enrollment_id == enrollment_id).first()
    baby = {}
    if br:
        d = br.gestation_days or 0
        ga = f"{br.gestation_weeks} weeks {d} day{'' if d == 1 else 's'}" if br.gestation_weeks is not None else None
        baby = {"dob": br.date_of_birth, "gestation": ga, "birth_weight": br.birth_weight, "gender": br.gender,
                "delivery_mode": br.delivery_mode, "twin": baby_label(br.baby_number, br.number_of_babies)}
    terms = ae_terms_of((ae.events if ae else None), collect_ae_candidates(db, enrollment_id).get("candidates"))
    day1 = (nicu.day1_date if nicu else None) or baby.get("dob")
    events = course_events(logs(RespCVNeuroDayLog), logs(InfectGIHemaDayLog), logs(MetabRenalVascEyeDayLog), terms)
    return compose(baby, events, {**form, "enrollment_id": enrollment_id}, day1, today or clinical_today())
