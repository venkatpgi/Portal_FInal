"""Site summary (PI 2026-10-26), Monday and Thursday 08:00 IST.

    cd /home/ubuntu/portal/backend && venv/bin/python site_summary.py [--dry-run] [--only EMAIL] [--force]

One email per site (Site PI + Site Scientists) and one for all sites (Global
PI, Project Scientist), same recipients as the daily query email. The same
content is served live at GET /site-summary for the portal page.

Every randomised baby born since the trial start is checked against the
rules the PI approved on 2026-10-26 (rule sheet:
https://claude.ai/artifact/MSSUiC1sRbvQMqN2V6fNmZ ):
  W1-W11  safety watch list: close to an SAE
  A1      advisory: AE grade 1-2 (or blank) with no SAE decision
  active  morbidities still running
  M1-M10  missed data collection
Rule-based only; no AI. Nothing is grouped or shown by arm. The email names
babies by enrolment ID only; the portal page adds the name for people who may
see the site's PII (pii_names). The W / M codes are internal: neither the
page nor the email shows them (PI 2026-10-26). A nil summary is still sent.

W2 (grade going up) compares with the grades stored by the last live send
(audit row, table site_summary). W1, W3, W9 and W10 are also listed in the
8 am daily query email (urgent_items).

Simplifications (data the portal does not hold): gestation is Form B's (no
Form D NBS override); "resolved" for NEC is not recorded, so W5 looks at the
last 7 days of Helper 4; Form L is not checked after discharge because it is
filled after unblinding.
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape

logging.basicConfig(level=logging.WARNING)

from ae_candidates import collect_ae_candidates  # noqa: E402
from babies import baby_label, baby_no  # noqa: E402
from ae_reference import AE_DEFINITIONS  # noqa: E402
from ae_terms import term_of  # noqa: E402,F401  (AE-form row -> term; also used by the tests)
from bpd_suggestion import INVASIVE_MODES  # noqa: E402
from clinical_time import clinical_now  # noqa: E402
from data_checks import OPEN_STATES, colour  # noqa: E402
from form_completion import ROP_VISIT_DETAIL_FIELDS, answered, form_h_complete, form_i_complete  # noqa: E402
from infection_windows import _compute_infection_windows  # noqa: E402
from nec_suggestion import stage_rank  # noqa: E402
from ops_tasks import baby_tasks, iter_form_tasks  # noqa: E402
from rop_form_g_linkage import compute_rop_review_alerts  # noqa: E402
from sae_rules import fourteen_day_items, is_fatal, unreported_sae  # noqa: E402
from trial_dates import trial_start  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
ALL_SITES = "ALL"
REPORT_SITES = ["PGIMER", "GMCH", "GMCH-A", "AMC", "AFMC", "IOG"]
AUDIT_TABLE = "site_summary"
PORTAL_URL = "https://portaltrial.in/site-summary"
QUERIES_URL = "https://portaltrial.in/data-queries"
URGENT_RULES = ("W1", "W3", "W9", "W10", "W11")

RULES = {
    "W1": "Serious AE not yet reviewed for SAE",
    "W2": "Grade going up",
    "W3": "Severe brain scan not yet in Form H",
    "W4": "Proven infection",
    "W5": "Suspected NEC",
    "W6": "Metabolic value in the grade 2 band",
    "W7": "Escalating support",
    "W8": "Acute event",
    "W9": "Death without an SAE report",
    "W10": "SAE reporting deadline",
    "W11": "Converted to SAE, no report",
    "M1": "Daily logs",
    "M2": "Cranial ultrasound",
    "M3": "Brain scan asked for by Helper 2",
    "M4": "ROP screen",
    "M5": "Form I checkpoint",
    "M6": "Forms after discharge or death",
    "M7": "Form C (maternal details)",
    "M8": "Form B after delivery",
    "M9": "AE review",
    "M10": "Old data queries",
    "A1": "Review AE grade",
}

# One heading for the site summary and the daily query email (PI 2026-11-04).
WATCH_HEADING = "Safety watch list"

INFECTION_SLUGS = {"sepsis_culture_positive", "sepsis_culture_negative", "meningitis"}
PROVEN_INFECTION_SLUGS = {"sepsis_culture_positive", "meningitis"}
METABOLIC_SLUGS = {"aki", "hypernatremia", "hyperkalemia", "hyponatremia", "hypoglycemia", "hyperglycemia",
                   "hypothermia", "hyperthermia"}
BRAIN_SLUGS = {"ivh", "pvl", "ventriculomegaly_hydrocephalus"}
ACUTE_FLAGS = (("pneumothorax", "Pneumothorax"), ("pulm_hemorrhage", "Pulmonary haemorrhage"),
               ("shock", "Shock"), ("clinical_seizures", "Clinical seizure"), ("eeg_seizures", "EEG seizure"))
ROP_FIRST_SCREEN_DOL = 30     # national ROP operational guidelines (RBSK / NPCB): by 25-30 days of life
FORMS_AFTER_END_HOURS = 48
CHECKPOINTS = (36, 40, 44)


# ------------------------------------------------------------------ helpers
def _num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError, AttributeError):
        return None


def _int_grade(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError, AttributeError):
        return None


def _iso(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _fmt(d: date | None) -> str:
    return d.strftime("%d %b") if d else "?"


def _modes(log) -> set:
    return {m.strip() for m in (getattr(log, "support_modes", None) or "").split(",") if m.strip()}


def _invasive(log) -> bool:
    return getattr(log, "endotracheal_intubation", None) is True or bool(_modes(log) & INVASIVE_MODES)


def _fmt_pma(days) -> str:
    return f"{days // 7}+{days % 7} wk" if days is not None else "?"


# ------------------------------------------------------------- cranial USG
def cranial_windows(ga_days: int | None, birth_weight: float | None) -> list[tuple[str, int, int]]:
    """Form F scan schedule (page SCHEDULES) as (label, first DOL, last DOL).
    Same 3 scans for every baby (PI 2026-11-13): Day 7 ± 1, Day 28 ± 2, then
    discharge or 40 ± 1 wk PMA / TEA, whichever is earlier. A PMA window is
    DOL of 40+0 ± 7 days (DOL = PMA days − GA days + 1). Discharge-before-TEA
    is handled by skipping windows that start after the stay ended."""
    if ga_days is None:
        return []
    _ = birth_weight  # both GA bands now share the same 3 windows
    tea_dol = 40 * 7 - ga_days + 1
    return [
        ("Day 7 ± 1", 6, 8),
        ("Day 28 ± 2", 26, 30),
        ("40 ± 1 wk PMA / TEA", tea_dol - 7, tea_dol + 7),
    ]


def missed_cranial_windows(
    ga_days: int | None,
    birth_weight: float | None,
    dob: date | None,
    today: date,
    scan_dates: list,
    end: date | None,
) -> list[str]:
    """Schedule windows that have closed (plus 2 days) with no scan in them.
    Third scan is discharge or 40 ± 1 wk PMA / TEA, whichever is earlier:
    if the stay ended after the Day 28 window and before TEA starts, the
    last window is discharge ± 2 days."""
    if dob is None:
        return []
    dol_today = (today - dob).days + 1
    end_dol = (end - dob).days + 1 if end else None
    scan_dols = sorted((d - dob).days + 1 for d in scan_dates if d)
    wins = list(cranial_windows(ga_days, birth_weight))
    if end_dol is not None and wins:
        _lab, first, _last = wins[-1]
        if first > end_dol and end_dol > 30:
            wins[-1] = ("Discharge / TEA", max(1, end_dol - 2), end_dol)
    missed = []
    for label, first, last in wins:
        if end_dol is not None and first > end_dol:
            continue
        if dol_today > last + 2 and not any(first - 1 <= d <= last + 2 for d in scan_dols):
            missed.append(label)
    return missed


# ------------------------------------------------------------------ rules
def evaluate(b: dict, today: date, now: datetime, prev_grades: dict | None) -> dict:
    """Apply the PI's rules to one baby. b holds plain data (see _load);
    returns {watch, active, missed, advisory: [(code, text)], grades: {slug: grade}}."""
    watch, active, missed, advisory = [], [], [], []
    dob = b["dob"]
    dol_today = (today - dob).days + 1 if dob else None
    end = b.get("end_date")
    died = b.get("died")
    cands = b.get("candidates") or []
    events = [e for e in (b.get("ae_events") or []) if isinstance(e, dict)]
    terms_on_form = {term_of(e) for e in events} - {None}
    resp = sorted(b.get("resp_logs") or [], key=lambda l: l.nicu_day or 0)
    inf = sorted(b.get("inf_logs") or [], key=lambda l: l.nicu_day or 0)
    metab = sorted(b.get("metab_logs") or [], key=lambda l: l.nicu_day or 0)

    def recent(logs, days):
        return [l for l in logs if dol_today is not None and l.nicu_day is not None
                and l.nicu_day >= dol_today - days]

    def day_date(n):
        return dob + timedelta(days=n - 1) if dob and n else None

    # Current grade per AE term (worst of the AE form and the detectors), for W2.
    grades: dict[str, int] = {}
    names: dict[str, str] = {}
    for x in events + cands:
        slug, g = term_of(x), _int_grade(x.get("grade"))
        if slug and g:
            grades[slug] = max(g, grades.get(slug, 0))
            names[slug] = AE_DEFINITIONS[slug]["name"]

    # W1 serious AE not yet reviewed for SAE; A1 (PI 2026-11-04): a lower or
    # blank grade with no SAE decision is an advisory, not a watch item.
    for e in events:
        if answered(e.get("converted_to_sae")):
            continue
        g = _int_grade(e.get("grade"))
        what = (e.get("description") or (names.get(term_of(e)) if term_of(e) else None)
                or (f"AE {e['definition_no']}" if e.get("definition_no") not in (None, "", "NA")
                    else "AE (term not recorded)")).strip()
        start = _iso(e.get("start_date"))
        on = f" reported on {start.strftime('%d/%m/%y')}" if start else ""
        if g and g >= 3:
            watch.append(("W1", f"{what} grade {g}{on}: SAE decision not recorded"))
        elif g:
            advisory.append(("A1", f"{what} grade {g}{on}: review and confirm the AE grade"))
        else:
            advisory.append(("A1", f"{what}{on}: grade not recorded; enter and confirm the AE grade"))
    for c in cands:   # an auto-detected AE whose term is not on the AE form at all
        g = _int_grade(c.get("grade"))
        if g and g >= 3 and term_of(c) not in terms_on_form:
            watch.append(("W1", f"{c.get('description')} grade {g} auto-detected, not yet on the AE form"))

    # W2 grade going up since the last summary
    if prev_grades:
        for slug, g in sorted(grades.items()):
            p = prev_grades.get(slug)
            if p and g > p:
                watch.append(("W2", f"{names[slug]} grade {p} → {g}"))

    # W3 severe brain scan not yet in Form H
    for f in b.get("pending_usg") or []:
        watch.append(("W3", f"Form F: {f.get('side')} {f.get('finding')} grade {f.get('grade')}"
                            f" ({f.get('scan_date') or 'undated'}), not yet in Form H"))

    # W4 proven infection starting in the last 7 days
    for c in cands:
        start = _iso(c.get("start_date"))
        if c.get("definition_no") in PROVEN_INFECTION_SLUGS and start and start >= today - timedelta(days=6):
            watch.append(("W4", f"{c.get('description')} from {_fmt(start)}"))

    # W5 suspected NEC: stage I or suspected in the last 7 days, no stage IIA or above
    ranks = [stage_rank(b.get("nec_stage"))] + [stage_rank(l.nec_confirmed_stage) for l in inf]
    top = max([r for r in ranks if r], default=None)
    nec_recent = [l for l in recent(inf, 6) if l.nec_suspected is True or stage_rank(l.nec_confirmed_stage) in (1, 2)]
    if nec_recent and (top is None or top < 3):
        watch.append(("W5", f"NEC suspected / stage I on DOL {nec_recent[-1].nicu_day}, no stage IIA or above"))

    # W6 metabolic value in the NAESS grade 2 band
    for l in recent(metab, 2):
        na, k = _num(l.sodium_value), _num(l.potassium_value)
        if na is not None and (120 <= na < 130 or 151 <= na <= 160):
            watch.append(("W6", f"Na {na:g} mEq/L on DOL {l.nicu_day}"))
        if k is not None and 6.5 <= k <= 8.0:
            watch.append(("W6", f"K {k:g} mEq/L on DOL {l.nicu_day}"))
        aki = max(filter(None, [_int_grade(l.aki_kdigo_stage), _int_grade(l.aki_stage)]), default=None)
        if aki and aki >= 2:
            watch.append(("W6", f"AKI stage {aki} on DOL {l.nicu_day}"))
    lows = [(l.nicu_day, _num(l.lowest_glucose)) for l in recent(metab, 6)]
    lows = [(d, v) for d, v in lows if v is not None]
    band = [(d, v) for d, v in lows if 20 <= v <= 40]
    severe = [(d, v) for d, v in lows if v < 20]
    if severe:
        watch.append(("W6", f"Glucose {severe[-1][1]:g} mg/dL on DOL {severe[-1][0]}"))
    elif len(band) >= 2:
        watch.append(("W6", f"Glucose 20-40 mg/dL on {len(band)} days (last DOL {band[-1][0]})"))

    # W7 escalating support started in the last 3 days
    by_day = {l.nicu_day: l for l in resp}
    for l in recent(resp, 2):
        prev = by_day.get((l.nicu_day or 0) - 1)
        if prev is None:
            continue
        if _invasive(l) and not _invasive(prev):
            watch.append(("W7", f"Invasive ventilation started DOL {l.nicu_day}"))
        if l.vasoactive_support is True and prev.vasoactive_support is not True:
            watch.append(("W7", f"Inotropes started DOL {l.nicu_day}"))

    # W8 acute event in the last 7 days
    for attr, label in ACUTE_FLAGS:
        days = [l.nicu_day for l in recent(resp, 6) if getattr(l, attr, None) is True]
        if days:
            watch.append(("W8", f"{label} on DOL {', '.join(str(d) for d in days)}"))

    # W9 death without an SAE report
    if died and not b.get("has_death_report"):
        watch.append(("W9", f"Died{(' ' + _fmt(end)) if end else ''}: no SAE report recording the death (Form Y)"))

    # W10 SAE reporting deadlines (SAE list)
    for r in b.get("sae_rows") or []:
        if not isinstance(r, dict):
            continue
        start = _iso(r.get("start_date"))
        if not start:
            continue
        what = r.get("sae") or "SAE"
        if not answered(r.get("notification_24h")) and now.date() > start:
            watch.append(("W10", f"{what} from {_fmt(start)}: 24-hour notification not recorded"))
    for item in fourteen_day_items(b.get("sae_rows"), today):
        watch.append(("W10", f"{item['sae']}: 14-day report {'overdue (due' if item['overdue'] else 'due'} "
                             f"{_fmt(item['due'])}{')' if item['overdue'] else ''}"))

    # W11 an AE answered Converted to SAE with no report (PI 2026-10-31)
    for name in unreported_sae(events, b.get("sae_reports")):
        watch.append(("W11", f"{name}: Converted to SAE is Yes, no SAE report"))

    # ---------------------------------------------------- active morbidities
    if not end:
        abx = [l.nicu_day for l in recent(inf, 2) if l.antibiotics is True]
        if abx:
            infs = [c for c in cands if c.get("definition_no") in INFECTION_SLUGS]
            what = (infs[-1].get("description") + (f" grade {infs[-1]['grade']}" if infs[-1].get("grade") else "")
                    if infs else "Sepsis / infection")
            active.append(f"{what}: on antibiotics (DOL {abx[-1]})")
        if nec_recent or [l for l in recent(inf, 6) if stage_rank(l.nec_confirmed_stage)]:
            st = [l.nec_confirmed_stage for l in recent(inf, 6) if stage_rank(l.nec_confirmed_stage)]
            active.append(f"NEC {('stage ' + st[-1]) if st else 'suspected'}")
        if [l for l in recent(resp, 2) if l.pda_medical_rx is True or l.hs_pda is True]:
            active.append("PDA (haemodynamically significant or on treatment)")
        rop = b.get("rop")
        if rop is not None and (answered(rop.worst_stage) or rop.treatment_required is True) \
                and not answered(rop.outcome):
            active.append("ROP" + (f" stage {rop.worst_stage}" if answered(rop.worst_stage) else "")
                          + (", treatment required" if rop.treatment_required is True else ""))
        last_resp = resp[-1] if resp else None
        if last_resp is not None and last_resp.respiratory_support is True and dol_today \
                and last_resp.nicu_day >= dol_today - 2:
            modes = ", ".join(sorted(_modes(last_resp))) or "mode not recorded"
            active.append(f"Respiratory support ({modes})")
        if [l for l in recent(inf, 1) if l.phototherapy is True] or \
                [l for l in recent(inf, 2) if l.exchange_transfusion is True]:
            active.append("Jaundice on phototherapy / exchange")
        tx = [l for l in recent(inf, 6) if l.prbc_transfusion is True or l.platelet_transfusion is True]
        if tx:
            active.append(f"Transfusion in the last 7 days (DOL {tx[-1].nicu_day})")
        for c in cands:
            last = _iso(c.get("end_date") or c.get("start_date"))
            if c.get("definition_no") in METABOLIC_SLUGS and last and last >= today - timedelta(days=2):
                active.append(f"{c.get('description')}" + (f" grade {c['grade']}" if c.get("grade") else ""))
    for slug in sorted(BRAIN_SLUGS & set(grades)):
        active.append(f"Known: {names[slug]} grade {grades[slug]}")

    # ------------------------------------------------------- missed data
    end_dol = (end - dob).days + 1 if end and dob else None
    for key, detail in b.get("tasks") or []:
        if key == "daily_logs_missing":
            missed.append(("M1", detail))
        elif key == "ppv_no_form_c":
            missed.append(("M7", "Form C missing"))

    scans = [_iso((s or {}).get("scanDate")) for s in (b.get("scan_entries") or [])]
    scan_dols = sorted((d - dob).days + 1 for d in scans if d and dob)
    for label in missed_cranial_windows(
            b.get("ga_days"), b.get("birth_weight"), dob, today, scans, end):
        missed.append(("M2", f"Cranial USG {label} not done"))
    if b.get("helper2_brain_flag") and not scan_dols:
        missed.append(("M3", "Helper 2 flagged IVH / cPVL, Form F has no scan"))

    rop = b.get("rop")
    visits = [v for v in ((rop.screenings if rop else None) or []) if isinstance(v, dict) and _iso(v.get("date"))
              and (answered(v.get("signature")) or any(answered(v.get(f)) for f in ROP_VISIT_DETAIL_FIELDS))]
    if dol_today and not visits:
        if dol_today > ROP_FIRST_SCREEN_DOL and (end_dol is None or end_dol > ROP_FIRST_SCREEN_DOL):
            missed.append(("M4", f"No ROP screen by DOL {ROP_FIRST_SCREEN_DOL}"))
        elif end_dol is not None and end_dol <= ROP_FIRST_SCREEN_DOL and not died:
            missed.append(("M4", "Left the NICU before an ROP screen"))
    for a in (compute_rop_review_alerts(rop.screenings) if rop else []):
        when = f"DOL {a['nicu_day']}" if a.get("nicu_day") is not None else (a.get("detected_date") or "")
        missed.append(("M4", f"Auto-suggested Form G visit ({when}) not filled"))

    so = b.get("study_outcomes")
    ga = b.get("ga_days")
    if dob and ga is not None:
        for wk in CHECKPOINTS:
            due = dob + timedelta(days=wk * 7 - ga)
            if today <= due or (died and end and end < due):
                continue
            done = so is not None and (answered(getattr(so, f"encounter{wk}_method", None))
                                       or getattr(so, f"death{wk}", None) is True)
            if not done:
                missed.append(("M5", f"Form I {wk} wk checkpoint ({_fmt(due)}) not entered"))

    if end and now >= datetime.combine(end, datetime.min.time()) + timedelta(hours=FORMS_AFTER_END_HOURS):
        left = [f for f, ok in (("Form H", b.get("form_h_complete")), ("Form I", b.get("form_i_complete"))) if not ok]
        if left:
            missed.append(("M6", f"{' and '.join(left)} incomplete, stay ended {_fmt(end)}"))

    not_saved = [c for c in cands if term_of(c) not in terms_on_form]
    if not_saved:
        missed.append(("M9", f"{len(not_saved)} auto-detected AE(s) whose term is not on the AE form: "
                             + ", ".join(sorted({c.get('description') for c in not_saved}))))

    return {"watch": watch, "active": active, "missed": missed, "advisory": advisory, "grades": grades}


# ------------------------------------------------------------------ data
def _load(db, sites: list[str], now: datetime) -> list[dict]:
    from models import (AdverseEvents, BirthResuscitation, CranialUSGRecord, InfectGIHemaDayLog, MaternalDetails,
                        MetabRenalVascEyeDayLog, NeonatalMorbidities, NICUAdmission, RespCVNeuroDayLog,
                        ROPScreening, SAEList, SAEReport, Screening, StudyOutcomes)
    rows = (db.query(BirthResuscitation, Screening.site_name)
            .join(Screening, Screening.screening_id == BirthResuscitation.screening_id)
            .filter(Screening.is_deleted.isnot(True), Screening.site_name.in_(sites),
                    BirthResuscitation.randomised.is_(True),
                    BirthResuscitation.enrollment_id.isnot(None),
                    BirthResuscitation.date_of_birth >= trial_start())
            .order_by(Screening.site_name, BirthResuscitation.enrollment_id).all())
    babies = []
    for br, site in rows:
        eid = br.enrollment_id

        def q(model, order=None):
            x = db.query(model).filter(model.enrollment_id == eid)
            return x.order_by(order) if order is not None else x

        nm = q(NeonatalMorbidities, NeonatalMorbidities.id.desc()).first()
        resp = q(RespCVNeuroDayLog).all()
        inf = q(InfectGIHemaDayLog, InfectGIHemaDayLog.nicu_day).all()
        metab = q(MetabRenalVascEyeDayLog).all()
        nicu = q(NICUAdmission).first()
        usg = q(CranialUSGRecord).first()
        ae = q(AdverseEvents).first()
        sae = q(SAEList).first()
        dob = br.date_of_birth
        death_days = [l.nicu_day for l in metab if l.survived_the_day is False and l.nicu_day]
        died = (nm is not None and nm.outcome == "Died") or bool(death_days)
        end = _iso(nm.discharge_date) if nm else None
        if death_days and dob:
            dd = dob + timedelta(days=min(death_days) - 1)
            end = min(end, dd) if end else dd
        signatures = [w["signature"] for w in _compute_infection_windows(inf, nicu)] if inf else []
        so = q(StudyOutcomes, StudyOutcomes.id.desc()).first()
        cand = collect_ae_candidates(db, eid)
        ga_days = (br.gestation_weeks * 7 + (br.gestation_days or 0)) if br.gestation_weeks is not None else None
        helper_days = {2: {l.nicu_day for l in resp}, 4: {l.nicu_day for l in inf}, 5: {l.nicu_day for l in metab}}
        tasks = baby_tasks({"required_resuscitation": True, "dob": dob, "ga_birth_weeks": br.gestation_weeks,
                            "ga_birth_days": br.gestation_days,
                            "has_form_c": q(MaternalDetails).first() is not None,
                            "has_form_i": so is not None, "discharge_date": _iso(nm.discharge_date) if nm else None,
                            "death_day": min(death_days) if death_days else None,
                            "helper_days": helper_days}, now)
        babies.append({
            "enrollment_id": eid, "screening_id": br.screening_id, "site": site, "dob": dob, "ga_days": ga_days,
            # twins / triplets (babies.py): "Twin 2 of 2", "" for a singleton
            "baby_number": baby_no(br), "twin": baby_label(br.baby_number, br.number_of_babies),
            "birth_weight": getattr(br, "birth_weight", None),
            "end_date": end, "died": died, "candidates": cand.get("candidates") or [],
            "pending_usg": cand.get("pending_cranial_usg_findings") or [],
            "ae_events": (ae.events if ae else None) or [], "sae_rows": (sae.rows if sae else None) or [],
            # an empty Form Y (no diagnosis) is not a report (01-B-001, PI 2026-10-26); a report
            # about another event does not record the death (PI 2026-10-31)
            "has_death_report": any(answered(r.diagnosis) and is_fatal(r) for r in q(SAEReport).all()),
            "sae_reports": q(SAEReport).all(),
            "resp_logs": resp, "inf_logs": inf, "metab_logs": metab,
            "nec_stage": nm.nec_stage if nm else None,
            "rop": q(ROPScreening, ROPScreening.id.desc()).first(),
            "scan_entries": (usg.scan_entries if usg else None) or [],
            "helper2_brain_flag": any(l.ivh is True or l.cpvl_confirmed is True or l.pvl_suspected is True
                                      for l in resp),
            "study_outcomes": so, "form_h_complete": form_h_complete(nm, signatures),
            "form_i_complete": form_i_complete(so), "tasks": tasks,
        })
    return babies


def last_snapshot(db):
    """(sent_at, {enrollment_id: {slug: grade}}) of the last live send, or (None, {})."""
    from models import AuditLog
    row = (db.query(AuditLog).filter(AuditLog.table_name == AUDIT_TABLE, AuditLog.action == "EMAIL")
           .order_by(AuditLog.created_at.desc()).first())
    if not row:
        return None, {}
    return row.created_at, ((row.new_values or {}).get("grades") or {})


def build(db, scope: str, now: datetime | None = None, snapshot=None) -> dict:
    """The summary for one site or ALL_SITES, as plain data (page + email)."""
    from models import DataQuery
    now = now or clinical_now()
    today = now.date()
    sent_at, prev = snapshot if snapshot is not None else last_snapshot(db)
    sites = REPORT_SITES if scope == ALL_SITES else [scope]
    since = (sent_at + timedelta(hours=5, minutes=30)).date() if sent_at else today - timedelta(days=4)

    babies = []
    for b in _load(db, sites, now):
        r = evaluate(b, today, now, prev.get(b["enrollment_id"]))
        dol = (today - b["dob"]).days + 1 if b["dob"] else None
        pma = b["ga_days"] + dol - 1 if b["ga_days"] is not None and dol else None
        end = b["end_date"]
        babies.append({
            "enrollment_id": b["enrollment_id"], "screening_id": b["screening_id"], "site": b["site"], "dol": dol, "pma": _fmt_pma(pma),
            "status": ("Died" if b["died"] else "Stay ended") if end else "In NICU",
            "ended_on": end.isoformat() if end else None,
            "ended_since_last": bool(end and end >= since),
            "watch": [{"rule": c, "title": RULES[c], "detail": t} for c, t in r["watch"]],
            "active": r["active"],
            "missed": [{"rule": c, "title": RULES[c], "detail": t} for c, t in r["missed"]],
            "advisory": [{"rule": c, "title": RULES[c], "detail": t} for c, t in r["advisory"]],
            "grades": r["grades"],
        })

    # M8 is about the mother (no enrolment number yet); M10 counts the site's red queries.
    mothers = [{"site": site, "screening_id": ref, "rule": "M8", "title": RULES["M8"],
                "detail": "Birth logged / delivered here, Form B missing"}
               for key, site, ref, _ in iter_form_tasks(db, now) if key == "delivered_no_form_b" and site in sites]
    qs = db.query(DataQuery).filter(DataQuery.site_name.in_(sites), DataQuery.status.in_(OPEN_STATES)).all()
    red = defaultdict(int)
    for x in qs:
        if colour(x, datetime.utcnow()) == "red":
            red[x.site_name] += 1

    in_nicu = [b for b in babies if b["status"] == "In NICU"]
    per_site = {s: {"in_nicu": 0, "watch": 0, "missed": 0, "red_queries": red.get(s, 0)} for s in sites}
    for b in babies:
        p = per_site.setdefault(b["site"], {"in_nicu": 0, "watch": 0, "missed": 0, "red_queries": 0})
        p["in_nicu"] += b["status"] == "In NICU"
        p["watch"] += len(b["watch"])
        p["missed"] += len(b["missed"])
    for m in mothers:
        per_site[m["site"]]["missed"] += 1
    counts = {
        "in_nicu": len(in_nicu),
        "ended_since_last": sum(b["ended_since_last"] for b in babies),
        "watch_babies": sum(bool(b["watch"]) for b in babies),
        "watch": sum(len(b["watch"]) for b in babies),
        "active_babies": sum(bool(b["active"]) for b in in_nicu),
        "missed": sum(len(b["missed"]) for b in babies) + len(mothers),
        "advisory": sum(len(b["advisory"]) for b in babies),
        "red_queries": sum(red.values()),
    }
    return {"scope": scope, "generated_at": now.isoformat(timespec="minutes"), "since": since.isoformat(),
            "counts": counts, "per_site": per_site, "babies": babies, "mothers": mothers}


def pii_names(db, screening_ids, enrollment_ids=()) -> dict:
    """{screening_id: {"baby": "Baby of <mother>", "mother": "<mother>"}} from
    participant_pii, for the portal page only (the caller checks PII rights).
    A baby name typed on Form E wins unless it is itself "Baby of ...".
    enrollment_ids: twin 2+ (babies.py) have their own row, keyed here by
    enrollment id (screening and enrollment ids never look alike)."""
    from models import ParticipantPII
    sids = sorted({x for x in screening_ids if x})
    eids = sorted({x for x in enrollment_ids if x})
    out = {}

    def entry(p):
        mother = " ".join(x for x in (p.mother_first_name, p.mother_surname) if x).strip() or None
        own = (p.baby_name or "").strip()
        baby = own if own and not own.lower().startswith("baby of") else (f"Baby of {mother}" if mother else own)
        return {"baby": baby or None, "mother": mother}

    for p in db.query(ParticipantPII).filter(ParticipantPII.screening_id.in_(sids)).all() if sids else []:
        out[p.screening_id] = entry(p)
    for p in db.query(ParticipantPII).filter(ParticipantPII.enrollment_id.in_(eids)).all() if eids else []:
        if not p.screening_id:
            out[p.enrollment_id] = entry(p)
    return out


def urgent_items(db, scope: str, now: datetime | None = None) -> list[dict]:
    """W1, W3, W9, W10 for the daily query email: [{site, enrollment_id, rule, title, detail}]."""
    s = build(db, scope, now, snapshot=(None, {}))
    return [{"site": b["site"], "enrollment_id": b["enrollment_id"], **w}
            for b in s["babies"] for w in b["watch"] if w["rule"] in URGENT_RULES]


# ------------------------------------------------------------------ email
def _site_display(site: str) -> str:
    import sae_config
    return sae_config.site_for(site or "").get("display", site or "—")


TH = '<th style="text-align:left;padding:6px 8px;border-bottom:2px solid #e2e8f0;font-size:12px;color:#475569;">{}</th>'
TD = '<td style="padding:6px 8px;border-bottom:1px solid #eef2f7;vertical-align:top;">{}</td>'


def _h3(title, n=None, anchor=None):
    ident = f' id="{anchor}"' if anchor else ""
    return (f'<h3{ident} style="margin:22px 0 8px;font-size:15px;color:#00132c;">{escape(title)}'
            f'{f" ({n})" if n is not None else ""}</h3>')


def tile_cells(tiles) -> str:
    """Email count tiles; each number links to its list (PI 2026-11-04).
    tiles: (label, n, colour, url)."""
    return "".join(
        f'<td style="padding:10px 12px;border:1px solid #e2e8f0;border-radius:8px;text-align:center;">'
        f'<a href="{escape(url)}" style="text-decoration:none;display:block;">'
        f'<div style="font-size:22px;font-weight:700;color:{col};text-decoration:underline;">{n}</div>'
        f'<div style="font-size:11px;color:#64748b;">{escape(label)}</div></a></td>' for label, n, col, url in tiles)


def _rows_table(cols, rows):
    if not rows:
        return '<p style="margin:0;color:#64748b;font-size:13px;">None.</p>'
    return ('<table style="border-collapse:collapse;width:100%;font-size:13px;"><tr>'
            + "".join(TH.format(escape(c)) for c in cols) + "</tr>"
            + "".join("<tr>" + "".join(TD.format(c) for c in r) + "</tr>" for r in rows) + "</table>")


def rule_table(items, show_site) -> str:
    """Rows of {site, enrollment_id or screening_id, rule, title, detail} as an HTML table (no rule code)."""
    cols = (["Site"] if show_site else []) + ["Baby", "Concern", "Detail"]
    rows = [([escape(_site_display(x["site"]))] if show_site else [])
            + [escape(x.get("enrollment_id") or f"Form A {x.get('screening_id')}"),
               f"<strong>{escape(x['title'])}</strong>", escape(x["detail"])]
            for x in items]
    return _rows_table(cols, rows)


def render_email(s: dict) -> tuple[str, str]:
    all_sites = s["scope"] == ALL_SITES
    where = "All sites" if all_sites else _site_display(s["scope"])
    now = datetime.fromisoformat(s["generated_at"])
    day = now.strftime("%a %d %b %Y")
    c = s["counts"]
    nil = not (c["watch"] or c["missed"] or c.get("advisory") or c["in_nicu"] or c["ended_since_last"])
    subject = (f"PORTAL site summary — {where} — {day}: "
               + ("nil to report" if nil else
                  f"{c['in_nicu']} in NICU, {c['watch_babies']} on safety watch list, {c['missed']} missed items"))
    page = PORTAL_URL + ("" if all_sites else f"?site={s['scope']}")
    tile_html = tile_cells([
        ("In NICU", c["in_nicu"], "#0f172a", f"{page}#census"),
        ("Stays ended since last", c["ended_since_last"], "#475569", f"{page}#census"),
        ("Babies on safety watch list", c["watch_babies"], "#b91c1c", f"{page}#watch"),
        ("With active morbidity", c["active_babies"], "#b45309", f"{page}#active"),
        ("Missed data items", c["missed"], "#6d28d9", f"{page}#missed"),
        ("Advisory notes", c.get("advisory", 0), "#0f766e", f"{page}#advisory"),
        ("Overdue queries", c["red_queries"], "#0369a1", f"{QUERIES_URL}?show=red")])
    advisory = [{"site": b["site"], "enrollment_id": b["enrollment_id"], **a}
                for b in s["babies"] for a in b.get("advisory", [])]
    watch = [{"site": b["site"], "enrollment_id": b["enrollment_id"], **w} for b in s["babies"] for w in b["watch"]]
    missed = ([{"site": b["site"], "enrollment_id": b["enrollment_id"], **m} for b in s["babies"] for m in b["missed"]]
              + s["mothers"])
    active_rows = [([escape(_site_display(b["site"]))] if all_sites else [])
                   + [escape(b["enrollment_id"]), escape(f"DOL {b['dol']} · {b['pma']}"), escape("; ".join(b["active"]))]
                   for b in s["babies"] if b["status"] == "In NICU" and b["active"]]
    census = [([escape(_site_display(b["site"]))] if all_sites else [])
              + [escape(b["enrollment_id"]), escape(f"DOL {b['dol']} · {b['pma']}"), escape(b["status"])]
              for b in s["babies"] if b["status"] == "In NICU" or b["ended_since_last"]]
    by_site = ""
    if all_sites:
        by_site = _h3("By site") + _rows_table(
            ["Site", "In NICU", "Watch-list items", "Missed items", "Overdue queries"],
            [[escape(_site_display(site)), p["in_nicu"], p["watch"], p["missed"], p["red_queries"]]
             for site, p in s["per_site"].items()])
    nil_line = ('<p style="margin:16px 0 0;padding:10px 12px;background:#f0fdf4;border:1px solid #bbf7d0;'
                'border-radius:8px;color:#166534;font-size:14px;"><strong>Nil to report.</strong> No randomised baby '
                'in the NICU, nothing on the watch list and no missed data.</p>') if nil else ""
    site_col = ["Site"] if all_sites else []
    html = f"""<!doctype html><html><body style="margin:0;padding:0;background:#f8fafc;">
<div style="max-width:820px;margin:0 auto;padding:20px 16px;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
<div style="background:#00132c;color:#fff;padding:14px 18px;border-radius:10px 10px 0 0;">
  <div style="font-size:12px;opacity:.8;">PORTAL Trial — site summary (Monday and Thursday)</div>
  <div style="font-size:18px;font-weight:700;margin-top:2px;">{escape(where)} · {escape(day)}</div>
</div>
<div style="background:#fff;border:1px solid #e2e8f0;border-top:0;padding:16px 18px;border-radius:0 0 10px 10px;">
  <p style="margin:0 0 12px;font-size:13px;color:#475569;">Randomised babies born since the trial start.
  "Since last" means since {escape(s['since'])}. Every item comes from a fixed rule on the data in the portal;
  check the baby's forms before acting.</p>
  <table style="border-collapse:separate;border-spacing:6px;width:100%;"><tr>{tile_html}</tr></table>
  {nil_line}
  {by_site}
  {_h3(WATCH_HEADING + ": close to an SAE", len(watch), "watch")}{rule_table(watch, all_sites)}
  {_h3("Advisory: AE grades to review", len(advisory), "advisory")}{rule_table(advisory, all_sites)}
  {_h3("Active morbidities (babies in the NICU)", len(active_rows), "active")}{_rows_table(site_col + ["Baby", "Age", "Active"], active_rows)}
  {_h3("Missed data collection", len(missed), "missed")}{rule_table(missed, all_sites)}
  {_h3("Census: in the NICU or stay ended since last", len(census), "census")}{_rows_table(site_col + ["Baby", "Age", "Status"], census)}
  <p style="margin:22px 0 0;"><a href="{PORTAL_URL}" style="display:inline-block;background:#00132c;color:#fff;
  text-decoration:none;padding:10px 16px;border-radius:8px;font-size:14px;">Open the site summary in the portal</a></p>
  <p style="margin:18px 0 0;font-size:11px;color:#94a3b8;">IDs only: no names, CR or phone numbers, and nothing by
  study arm (names are on the portal page for staff who may see them). Sent Monday and Thursday at 08:00 IST to Site PIs and Site Scientists (own site), the Project
  Scientist and the Global PI (all sites). Do not reply; this mailbox is not read.</p>
</div></div></body></html>"""
    return subject, html


# ------------------------------------------------------------------ CLI
def already_sent_today(db, now_utc: datetime) -> bool:
    from models import AuditLog
    start_ist = now_utc.replace(tzinfo=timezone.utc).astimezone(IST).replace(hour=0, minute=0, second=0,
                                                                            microsecond=0)
    start_utc = start_ist.astimezone(timezone.utc).replace(tzinfo=None)
    return db.query(AuditLog).filter(AuditLog.table_name == AUDIT_TABLE, AuditLog.action == "EMAIL",
                                     AuditLog.created_at >= start_utc).first() is not None


def main(argv=None) -> int:
    from audit_service import record_audit
    from daily_query_email import recipients
    from db import SessionLocal
    from email_service import send_email

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    db = SessionLocal()
    try:
        live = not args.dry_run and not args.only
        if live and not args.force and already_sent_today(db, datetime.utcnow()):
            print("site summary: already sent today, skipped")
            return 0
        now = clinical_now()
        snapshot = last_snapshot(db)
        plan = recipients(db)
        failed, sent, grades = 0, [], {}
        for scope in sorted(plan, key=lambda x: (x != ALL_SITES, x)):
            to = plan[scope]
            if args.only:
                if args.only not in to:
                    continue
                to = [args.only]
            s = build(db, scope, now, snapshot)
            if scope == ALL_SITES:
                grades = {b["enrollment_id"]: b["grades"] for b in s["babies"]}
            subject, html = render_email(s)
            if args.dry_run:
                path = f"/tmp/site_summary_{scope}.html"
                with open(path, "w") as fh:
                    fh.write(html)
                print(f"[dry run] {scope}: {len(to)} recipient(s); {subject}  -> {path}")
                continue
            ok = send_email(to, subject, html)
            failed += not ok
            sent.append({"scope": scope, "recipients": len(to), "ok": ok, **s["counts"]})
            print(f"{scope}: {'sent' if ok else 'FAILED'} to {len(to)}; {subject}")
        if sent:
            if not grades:   # no all-sites recipient: still keep every baby's grades for W2
                grades = {b["enrollment_id"]: b["grades"] for b in build(db, ALL_SITES, now, snapshot)["babies"]}
            # A --only test is EMAIL_TEST: it neither counts as the day's send nor moves the W2 baseline.
            record_audit(db, user_id=None, username="system", action="EMAIL_TEST" if args.only else "EMAIL",
                         table_name=AUDIT_TABLE, new_values={"emails": sent, "grades": grades})
            db.commit()
        return 1 if failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
