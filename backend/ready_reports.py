"""Ready-made reports (PI 2026-11-06): one click, preview / CSV / PDF.

  consent       Eligible births to consent: births at 25+0 to 31+6 weeks with
                no Form A (Log of All Births, with reasons), screened women not
                asked (reasons), then consent refusals: by site, by the staff who took consent
                (share of the women each asked who refused), reasons, from
                whom consent was sought, and the list.
  exclusions    Exclusions out of all Form A (screened): by site, reasons.
  completeness  Form completeness for randomised babies: complete / not yet
                complete per form and site (the sidebar green tick).
  glance        At a glance per site: screened, excluded, not approached,
                refused, eligible, randomised, follow-up at 36 / 40 / 44
                weeks, outcomes (components of the composites).
  ae_summary    Monthly AE / SAE summary for the IEC and DSMB, with the
                literature baseline (ae_summary.py; dates = AE start date).

Same definitions as the Trial Monitoring CONSORT (routers/dashboard.py):
excluded = Box 4a (gestation outside 25+0 to 31+6 weeks, or not recorded)
+ Box 4b (an A4 exclusion); refused = consent No; eligible = Box 5;
randomised = babies (Form B randomised); follow-up = Form I via
followup_states. Rows are women (Form A) except randomised babies. IDs only,
never names; nothing by study arm (blinded).

A report is {key, title, scope, generated_at, sections: [{title, note,
columns, rows, chart}]}; chart = {title, labels, series: [{name, values}],
unit} drawn as bars in the PDF and on the page.
"""
from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from datetime import date, datetime

from clinical_time import clinical_now
from participant_counts import scoped_screenings

REPORTS = [
    {"key": "consent", "title": "Eligible births to consent",
     "description": "Eligible births with no Form A (with reasons), screened women not asked, then consent "
                    "refusals by site and by the staff who took consent, with reasons and from whom consent was sought."},
    {"key": "exclusions", "title": "Exclusions",
     "description": "Women excluded out of all screened (Form A), with reasons, by site."},
    {"key": "completeness", "title": "Form completeness",
     "description": "Randomised babies: forms complete and not yet complete, by form and site."},
    {"key": "glance", "title": "At a glance",
     "description": "Per site: screened, excluded, refused, eligible, randomised, follow-up and outcomes."},
    {"key": "blender_check", "title": "Blender check",
     "description": "Enrollment IDs used on each blender (randomised and randomised in error), with gaps "
                    "that may be activations never entered."},
    {"key": "ae_summary", "title": "AE summary for IEC / DSMB",
     "description": "Monthly: AEs and SAEs by term and site, pooled (blinded), with the literature baseline. "
                    "Dates = AE start date."},
]
REPORT_KEYS = {r["key"] for r in REPORTS}

NOT_RECORDED = "(not recorded)"
EXCLUSION_LABELS = {
    "Structural anomaly": "Major structural anomaly",
    "Fetal hydrops": "Fetal hydrops",
    "Forego resuscitation": "Decision to forego resuscitation",
    "Insufficient time": "Insufficient time to approach for consent",
    "IUFD": "IUFD (before 24 Sep: then a Form A exclusion)",
}
FORM_TICKS = [   # (enrollment-status key, label), sidebar order
    ("form_a_complete", "Form A Screening"), ("form_b_complete", "Form B Birth & resuscitation"),
    ("form_c_complete", "Form C Maternal details"), ("form_d_complete", "Form D Postnatal day 1"),
    ("form_e_complete", "Form E Admission"), ("form_f_complete", "Form F Cranial USG"),
    ("form_g_complete", "Form G ROP screening"), ("form_h_complete", "Form H Morbidities"),
    ("form_i_complete", "Form I Outcomes"), ("form_j_complete", "Form J External hospital"),
    ("adverse_events_complete", "AE form"), ("sae_list_complete", "SAE list"),
]
OUTCOMES = [   # (component key from the composite suggestion, label)
    ("death36", "Death by 36 wk PMA"), ("bpd", "BPD at 36 wk (Jensen)"),
    ("death44", "Death by 44 wk PMA"), ("rop", "ROP needing treatment"),
    ("nec", "NEC stage IIA or more"), ("brain", "Brain injury (IVH III+ / cPVL II+)"),
    ("composite_1", "Composite 1: death or BPD by 36 wk"),
    ("composite_2", "Composite 2: death, BPD, ROP-Rx, NEC or brain injury by 44 wk"),
]


# ------------------------------------------------------------------ helpers
def pct(n, d) -> str:
    return f"{100 * n / d:.1f}%" if d else "—"


def _num(n, d) -> float:
    return round(100 * n / d, 1) if d else 0.0


def site_label(site: str) -> str:
    """Short site code in tables and charts; the full name is in the scope line."""
    return site or "—"


def site_full_name(site: str) -> str:
    import sae_config
    return sae_config.site_for(site or "").get("display", site or "—")


def _split(v) -> list[str]:
    return [x.strip() for x in str(v or "").split(",") if x.strip()]


def _screened_on(r):
    dt = r.screening_datetime or r.created_at
    return dt.date() if dt else None


def screenings(db, sites, date_from: date | None, date_to: date | None):
    rows = scoped_screenings(db, sites)
    if date_from or date_to:
        rows = [r for r in rows if _screened_on(r)
                and (not date_from or _screened_on(r) >= date_from)
                and (not date_to or _screened_on(r) <= date_to)]
    return sorted(rows, key=lambda r: (r.site_name or "", r.screening_id or ""))


def ga_days(r):
    if r.gestation_weeks is None:
        return None
    return int(r.gestation_weeks) * 7 + int(r.gestation_days or 0)


def exclusion_reasons(r) -> list[str]:
    """CONSORT Box 4a / 4b reasons for one Form A; [] if not excluded."""
    if r.exclusion_present:
        return [EXCLUSION_LABELS.get(x, x) for x in _split(r.exclusion_reasons)] or ["Exclusion ticked, reason not recorded"]
    days = ga_days(r)
    if days is None:
        return ["Gestation not recorded / could not be determined"]
    if days < 25 * 7 or days > 31 * 7 + 6:
        return ["Gestation outside 25+0 to 31+6 weeks"]
    return []


def _site_order(sites_present, sites):
    return [s for s in sites if s in sites_present] or list(sites)


def _with_total(rows_by_site: dict, sites: list, cols: int, total_row):
    rows = [rows_by_site[s] for s in sites if s in rows_by_site]
    if len(rows) > 1:
        rows.append(total_row)
    return rows


FORM_A_FOUND = ("matched", "possible_match")
CONSENT_NOT_RECORDED = "Consent not yet recorded"


def eligible_births(db, sites, date_from: date | None, date_to: date | None) -> list[dict]:
    """Women whose baby was born at 25+0 to 31+6 weeks (Log of All Births),
    on or after the trial start, dated by date of birth. One per mother and
    birth date (twins = one woman); she has a Form A when any of her babies
    matched one (match_status matched / possible_match, refreshed first as
    the CONSORT does). No names: the birth-log row numbers only."""
    from birth_log_matching import _normalize_uid, classify_ga_range, refresh_birth_log_matches
    from models import BirthLogEntry
    from trial_dates import trial_start
    if not sites:
        return []
    refresh_birth_log_matches(db, sites)
    start = max(d for d in (date_from, trial_start()) if d)
    women: dict = {}
    for e in db.query(BirthLogEntry).filter(BirthLogEntry.site_name.in_(list(sites))).all():
        born = e.date_of_birth or (e.created_at.date() if e.created_at else None)
        if not born or born < start or (date_to and born > date_to):
            continue
        if classify_ga_range(e.gestation_weeks, e.gestation_days) != "in_range":
            continue
        uid = _normalize_uid(e.mother_uid)
        w = women.setdefault((e.site_name, uid, born) if uid else ("row", e.id), {
            "site": e.site_name, "born": born, "rows": [], "ga": [], "form_a": False, "reasons": [], "other": []})
        w["rows"].append(e.id)
        w["ga"].append(f"{e.gestation_weeks}+{e.gestation_days or 0}")
        w["form_a"] |= e.match_status in FORM_A_FOUND
        for x in _split(e.reason_not_approached):
            if x not in w["reasons"]:
                w["reasons"].append(x)
        other = (e.reason_not_approached_other or "").strip().rstrip(".").strip()
        if other and other.lower() not in (o.lower() for o in w["other"]):
            w["other"].append(other)
    return sorted(women.values(), key=lambda w: (w["site"] or "", w["born"], w["rows"][0]))


def not_asked_reasons(r) -> list[str]:
    """Why a woman with a Form A was not asked for consent."""
    return exclusion_reasons(r) or _split(getattr(r, "reason_not_approached", None)) or [CONSENT_NOT_RECORDED]


def births_to_consent_sections(births, rows, sites) -> list[dict]:
    """Eligible births with no Form A, then screened women not asked, asked,
    consented and refused (PI 2026-11-09)."""
    missed = [w for w in births if not w["form_a"]]
    not_asked = [r for r in rows if r.consent_given not in ("Yes", "No")]
    present = {w["site"] for w in births} | {r.site_name for r in rows}
    order = _site_order(present, sites)

    def site_row(label, b, rs):
        miss = sum(not w["form_a"] for w in b)
        asked = [r for r in rs if r.consent_given in ("Yes", "No")]
        ref = sum(r.consent_given == "No" for r in asked)
        return [label, len(b), miss, pct(miss, len(b)), len(rs), len(rs) - len(asked), len(asked),
                len(asked) - ref, ref, pct(ref, len(asked))]

    by_site = {s: site_row(site_label(s), [w for w in births if w["site"] == s],
                           [r for r in rows if r.site_name == s]) for s in order}
    show_sites = len(order) > 1
    sections = [{
        "title": "From eligible births to consent",
        "note": "Eligible births = women whose baby was born at 25+0 to 31+6 weeks (Log of All Births, from the "
                "trial start, by date of birth; twins = one woman). No Form A = none of her babies matched a "
                "Form A. Screened = Form A, by screening date, so the two groups overlap but are not the same "
                "women. Asked = consent Yes or No.",
        "columns": ["Site", "Eligible births", "No Form A", "% missed", "Screened (Form A)", "Not asked",
                    "Asked for consent", "Consented", "Refused", "% refused"],
        "rows": _with_total(by_site, order, 10, site_row("All sites", births, rows)),
        "chart": {"title": "Lost before consent, and consent answers (n)", "unit": "n",
                  "labels": [site_label(s) for s in order],
                  "series": [{"name": name, "values": [by_site[s][i] for s in order]}
                             for name, i in (("No Form A", 2), ("Not asked", 5), ("Refused", 8), ("Consented", 7))]},
    }]

    def reason_section(title, note, items, reasons_of, site_of, total_label):
        n_by, by_site_n = Counter(), defaultdict(Counter)
        for it in items:
            for x in reasons_of(it):
                n_by[x] += 1
                by_site_n[x][site_of(it)] += 1
        return {
            "title": title, "note": note,
            "columns": ["Reason", "n", f"% of {total_label}"] + ([site_label(s) for s in order] if show_sites else []),
            "rows": [[x, n, pct(n, len(items))] + ([by_site_n[x][s] for s in order] if show_sites else [])
                     for x, n in n_by.most_common()],
            "chart": {"title": f"{title} (n)", "unit": "n", "labels": [x for x, _ in n_by.most_common()],
                      "series": [{"name": "Women", "values": [n for _, n in n_by.most_common()]}]},
        }

    sections.append(reason_section(
        "Eligible births with no Form A: reasons",
        "Reason not approached, from the Log of All Births. A woman may have more than one reason.",
        missed, lambda w: w["reasons"] or [NOT_RECORDED], lambda w: w["site"], "missed"))
    sections.append(reason_section(
        "Screened but not asked for consent: reasons",
        "Form A exclusion (A4, or gestation outside 25+0 to 31+6), else the reason not approached; "
        f"\"{CONSENT_NOT_RECORDED}\" = no consent answer and no reason yet.",
        not_asked, not_asked_reasons, lambda r: r.site_name, "not asked"))
    sections.append({
        "title": f"List of eligible births with no Form A ({len(missed)})",
        "note": "Log of All Births row numbers (no names). Gestation at birth; twins show each baby.",
        "columns": ["Birth log no.", "Site", "Date of birth", "Gestation (wk+d)", "Reason(s)", "Other reason"],
        "rows": [[", ".join(str(i) for i in w["rows"]), site_label(w["site"]), w["born"].strftime("%d-%m-%Y"),
                  ", ".join(w["ga"]), ", ".join(w["reasons"]) or NOT_RECORDED, "; ".join(w["other"])]
                 for w in missed],
    })
    sections.append({
        "title": f"List of screened women not asked for consent ({len(not_asked)})",
        "note": "Screening IDs only.",
        "columns": ["Screening ID", "Site", "Screened on", "Gestation (wk+d)", "Reason(s)"],
        "rows": [[r.screening_id, site_label(r.site_name),
                  _screened_on(r).strftime("%d-%m-%Y") if _screened_on(r) else "",
                  f"{r.gestation_weeks}+{r.gestation_days or 0}" if r.gestation_weeks is not None else "",
                  ", ".join(not_asked_reasons(r))]
                 for r in not_asked],
    })
    return sections


# ------------------------------------------------------------------ reports
def consent_report(rows, sites, births=None):
    asked = [r for r in rows if r.consent_given in ("Yes", "No")]
    refused = [r for r in asked if r.consent_given == "No"]
    by_site = defaultdict(lambda: [0, 0])
    for r in asked:
        by_site[r.site_name][0] += 1
        by_site[r.site_name][1] += r.consent_given == "No"
    order = _site_order(by_site, sites)
    site_rows = {s: [site_label(s), by_site[s][0], by_site[s][1], pct(by_site[s][1], by_site[s][0])] for s in order}
    sections = births_to_consent_sections(births, rows, sites) if births is not None else []
    sections += [{
        "title": "Refusals by site",
        "note": "Asked = women whose consent answer is Yes or No (Form A).",
        "columns": ["Site", "Asked for consent", "Refused", "% refused"],
        "rows": _with_total(site_rows, order, 4, ["All sites", len(asked), len(refused), pct(len(refused), len(asked))]),
        "chart": {"title": "% of women asked who refused", "unit": "%", "labels": [site_label(s) for s in order],
                  "series": [{"name": "% refused", "values": [_num(by_site[s][1], by_site[s][0]) for s in order]}]},
    }]

    staff = defaultdict(lambda: [0, 0])
    for r in asked:
        k = (r.site_name, (r.consent_taken_by or "").strip() or NOT_RECORDED)
        staff[k][0] += 1
        staff[k][1] += r.consent_given == "No"
    staff_keys = sorted(staff, key=lambda k: (sites.index(k[0]) if k[0] in sites else 99, -staff[k][1], k[1]))
    sections.append({
        "title": "By the staff who took consent",
        "note": "Each staff member's refusals as a share of the women they asked.",
        "columns": ["Site", "Consent taken by", "Asked", "Refused", "% refused"],
        "rows": [[site_label(s), n, staff[(s, n)][0], staff[(s, n)][1], pct(staff[(s, n)][1], staff[(s, n)][0])]
                 for s, n in staff_keys],
        "chart": {"title": "% refused, by staff", "unit": "%",
                  "labels": [n if len(order) == 1 else f"{n} ({s})" for s, n in staff_keys],
                  "series": [{"name": "% refused", "values": [_num(staff[k][1], staff[k][0]) for k in staff_keys]}]},
    })

    reasons = Counter()
    reasons_site = defaultdict(Counter)
    for r in refused:
        for x in _split(r.reason_for_consent_refusal) or [NOT_RECORDED]:
            reasons[x] += 1
            reasons_site[x][r.site_name] += 1
    show_sites = len(order) > 1
    sections.append({
        "title": "Reasons for refusal",
        "note": "A woman may give more than one reason, so the percentages can add up to more than 100.",
        "columns": ["Reason", "n", "% of refusals"] + ([site_label(s) for s in order] if show_sites else []),
        "rows": [[x, n, pct(n, len(refused))] + ([reasons_site[x][s] for s in order] if show_sites else [])
                 for x, n in reasons.most_common()],
        "chart": {"title": "Reasons for refusal (n)", "unit": "n", "labels": [x for x, _ in reasons.most_common()],
                  "series": [{"name": "Refusals", "values": [n for _, n in reasons.most_common()]}]},
    })

    rel = defaultdict(lambda: [0, 0])
    for r in asked:
        k = (r.relationship_to_participant or "").strip() or NOT_RECORDED
        rel[k][0] += 1
        rel[k][1] += r.consent_given == "No"
    sections.append({
        "title": "From whom consent was sought",
        "note": "Form A: relationship of the person who gave or refused consent.",
        "columns": ["Consent sought from", "Asked", "Refused", "% refused"],
        "rows": [[k, v[0], v[1], pct(v[1], v[0])] for k, v in sorted(rel.items(), key=lambda kv: -kv[1][0])],
    })

    sections.append({
        "title": f"List of refusals ({len(refused)})",
        "note": "Screening IDs only. Date and time of consent as recorded on Form A.",
        "columns": ["Screening ID", "Site", "Consent recorded", "Taken by", "Sought from", "Reason(s)", "Other reason"],
        "rows": [[r.screening_id, site_label(r.site_name),
                  r.consent_datetime.strftime("%d-%m-%Y %H:%M") if r.consent_datetime else "",
                  (r.consent_taken_by or "").strip() or NOT_RECORDED,
                  " / ".join(x for x in ((r.relationship_to_participant or "").strip(),
                                         (r.relationship_other or "").strip()) if x) or NOT_RECORDED,
                  ", ".join(_split(r.reason_for_consent_refusal)) or NOT_RECORDED,
                  r.reason_for_consent_refusal_other or ""]
                 for r in sorted(refused, key=lambda r: (r.site_name or "", r.consent_datetime or datetime.min))],
    })
    return sections


def exclusions_report(rows, sites):
    excl = [(r, exclusion_reasons(r)) for r in rows]
    excl = [(r, x) for r, x in excl if x]
    by_site = defaultdict(lambda: [0, 0])
    for r in rows:
        by_site[r.site_name][0] += 1
    for r, _ in excl:
        by_site[r.site_name][1] += 1
    order = _site_order(by_site, sites)
    site_rows = {s: [site_label(s), by_site[s][0], by_site[s][1], pct(by_site[s][1], by_site[s][0])] for s in order}
    sections = [{
        "title": "Exclusions by site",
        "note": "Out of all women screened (Form A filled). Excluded = did not meet the inclusion criteria "
                "(gestation) or met an exclusion criterion; consent refusals are not exclusions.",
        "columns": ["Site", "Screened (Form A)", "Excluded", "% excluded"],
        "rows": _with_total(site_rows, order, 4, ["All sites", len(rows), len(excl), pct(len(excl), len(rows))]),
        "chart": {"title": "% of screened women excluded", "unit": "%", "labels": [site_label(s) for s in order],
                  "series": [{"name": "% excluded", "values": [_num(by_site[s][1], by_site[s][0]) for s in order]}]},
    }]
    reasons = Counter()
    reasons_site = defaultdict(Counter)
    for r, xs in excl:
        for x in xs:
            reasons[x] += 1
            reasons_site[x][r.site_name] += 1
    show_sites = len(order) > 1
    sections.append({
        "title": "Reasons for exclusion",
        "note": "More than one exclusion can be ticked for a woman, so the percentages can add up to more than 100.",
        "columns": ["Reason", "n", "% of excluded", "% of screened"] + ([site_label(s) for s in order] if show_sites else []),
        "rows": [[x, n, pct(n, len(excl)), pct(n, len(rows))] + ([reasons_site[x][s] for s in order] if show_sites else [])
                 for x, n in reasons.most_common()],
        "chart": {"title": "Reasons for exclusion (n)", "unit": "n", "labels": [x for x, _ in reasons.most_common()],
                  "series": [{"name": "Excluded", "values": [n for _, n in reasons.most_common()]}]},
    })
    sections.append({
        "title": f"List of excluded women ({len(excl)})",
        "note": "Screening IDs only.",
        "columns": ["Screening ID", "Site", "Screened on", "Gestation", "Reason(s)"],
        "rows": [[r.screening_id, site_label(r.site_name),
                  _screened_on(r).strftime("%d-%m-%Y") if _screened_on(r) else "",
                  f"{r.gestation_weeks}+{r.gestation_days or 0}" if r.gestation_weeks is not None else "",
                  "; ".join(xs)] for r, xs in excl],
    })
    return sections


def randomised_babies(db, rows):
    """[(site, enrollment_id)] of randomised babies of these women."""
    from models import BirthResuscitation
    site_of = {r.screening_id: r.site_name for r in rows}
    if not site_of:
        return []
    q = (db.query(BirthResuscitation.screening_id, BirthResuscitation.enrollment_id)
         .filter(BirthResuscitation.screening_id.in_(list(site_of)), BirthResuscitation.randomised.is_(True)))
    return sorted((site_of[sid], eid) for sid, eid in q if eid)


def in_error_babies(db, sites):
    """Form B rows of babies randomised in error (randomised_in_error.py) at these sites."""
    from models import BirthResuscitation, Screening
    if not sites:
        return []
    return (db.query(BirthResuscitation, Screening.site_name)
            .join(Screening, Screening.screening_id == BirthResuscitation.screening_id)
            .filter(Screening.site_name.in_(list(sites)), Screening.is_deleted.isnot(True),
                    BirthResuscitation.blender_activated.is_(True),
                    BirthResuscitation.required_resuscitation.is_(False))
            .all())


def _in_error_reason(b) -> str:
    r = b.blender_activation_reason or NOT_RECORDED
    return f"{r}: {b.blender_activation_reason_other}" if r == "Other" and b.blender_activation_reason_other else r


def blender_check_report(db, sites):
    """Enrollment IDs used per site and blender (PI 2026-11-11). Every
    activation uses the next allocation, so a missing number may be an
    activation never entered on Form B."""
    import re

    from models import BirthResuscitation, Screening
    pat = re.compile(r"^(\d{2})-([A-D])-(\d{3})$", re.IGNORECASE)
    used = defaultdict(dict)      # (site, letter) -> {number: in_error}
    for b, site in (db.query(BirthResuscitation, Screening.site_name)
                    .join(Screening, Screening.screening_id == BirthResuscitation.screening_id)
                    .filter(Screening.site_name.in_(list(sites)), Screening.is_deleted.isnot(True)).all()):
        m = pat.match((b.enrollment_id or "").strip())
        in_error = b.blender_activated is True and b.required_resuscitation is False
        if m and (b.randomised is True or in_error):
            used[(site, m.group(2).upper())][int(m.group(3))] = in_error
    keys = sorted(used, key=lambda k: (sites.index(k[0]) if k[0] in sites else 99, k[1]))
    gaps = {k: [n for n in range(1, max(used[k]) + 1) if n not in used[k]] for k in keys}
    rows = [[site_label(s), letter, len(used[(s, letter)]), sum(used[(s, letter)].values()),
             f"{min(used[(s, letter)]):03d}", f"{max(used[(s, letter)]):03d}",
             ", ".join(f"{n:03d}" for n in gaps[(s, letter)]) or "none"] for s, letter in keys]
    errors = sorted(in_error_babies(db, sites), key=lambda x: (x[1] or "", x[0].enrollment_id or ""))
    return [{
        "title": "Enrollment IDs used, by blender",
        "note": "All Form B to date: randomised babies and babies randomised in error. A gap is a number "
                "below the highest one with no Form B; it may be an activation never entered. This "
                "assumes the number in the ID is the blender's own allocation counter (to be confirmed "
                "with the blender engineer). An ID can be saved only once, so duplicates cannot occur.",
        "columns": ["Site", "Blender", "IDs used", "Of these, in error", "Lowest", "Highest", "Missing numbers"],
        "rows": rows,
    }, {
        "title": f"Randomised in error ({len(errors)})",
        "note": "Blender activated, PPV not required. Not counted as randomised, not followed, excluded "
                "from analysis (PI 2026-11-11). Site PI confirms in Data queries; Global PI signs off.",
        "columns": ["Enrollment ID", "Site", "Date of birth", "Activated at", "Reason", "Activated by"],
        "rows": [[b.enrollment_id, site_label(site), b.date_of_birth.strftime("%d-%m-%Y") if b.date_of_birth else "",
                  b.blender_activation_time.strftime("%H:%M") if b.blender_activation_time else "",
                  _in_error_reason(b), b.blender_activated_by or NOT_RECORDED] for b, site in errors],
    }]


def completeness_report(babies, sites, status_for):
    ticks = {eid: status_for(eid) or {} for _, eid in babies}
    per_site = defaultdict(list)
    for s, eid in babies:
        per_site[s].append(eid)
    order = _site_order(per_site, sites)
    rows = []
    for key, label in FORM_TICKS:
        line = [label]
        for s in order + (["ALL"] if len(order) > 1 else []):
            eids = [e for _, e in babies] if s == "ALL" else per_site[s]
            done = sum(1 for e in eids if ticks[e].get(key) is True)
            line += [f"{done}/{len(eids)}", pct(len(eids) - done, len(eids))]
        rows.append(line)
    cols = ["Form"]
    for s in order + (["ALL"] if len(order) > 1 else []):
        name = "All sites" if s == "ALL" else site_label(s)
        cols += [f"{name}: complete", f"{name}: % not complete"]
    per_baby = []
    for s, eid in babies:
        missing = [label for key, label in FORM_TICKS if ticks[eid].get(key) is not True]
        per_baby.append([eid, site_label(s), f"{len(FORM_TICKS) - len(missing)}/{len(FORM_TICKS)}", ", ".join(missing)])
    return [{
        "title": "Forms complete by form and site",
        "note": f"Randomised babies ({len(babies)}). Complete = the sidebar green tick. Forms that fall due later "
                "(Form I at 36 / 40 / 44 weeks, Form J after discharge) count as not complete until filled.",
        "columns": cols, "rows": rows,
        "chart": {"title": "% of randomised babies with the form not complete" + (" (all sites)" if len(order) > 1 else ""),
                  "unit": "%", "labels": [lab for _, lab in FORM_TICKS],
                  "series": [{"name": "% not complete", "values": [
                      _num(sum(1 for _, e in babies if ticks[e].get(key) is not True), len(babies)) for key, _ in FORM_TICKS]}]},
    }, {
        "title": "Forms not yet complete, per baby",
        "note": "Enrolment IDs only.",
        "columns": ["Enrolment ID", "Site", "Forms complete", "Not yet complete"],
        "rows": per_baby,
    }]


def glance_report(db, rows, sites, composite_for, followup_for):
    babies = randomised_babies(db, rows)
    order = _site_order({r.site_name for r in rows} | {s for s, _ in babies}, sites)
    cols_sites = order + (["ALL"] if len(order) > 1 else [])
    sids = {r.screening_id for r in rows}
    in_error = in_error_babies(db, sites)

    def women(s):
        return rows if s == "ALL" else [r for r in rows if r.site_name == s]

    def kids(s):
        return [e for site, e in babies if s == "ALL" or site == s]

    def row(label, fn):
        return [label] + [fn(s) for s in cols_sites]

    def frac(n, d):
        return f"{n} ({pct(n, d)})" if d else str(n)

    lines = [
        row("Screened (Form A filled)", lambda s: len(women(s))),
        row("Excluded (inclusion / exclusion criteria)",
            lambda s: frac(sum(1 for r in women(s) if exclusion_reasons(r)), len(women(s)))),
        row("Not approached for consent",
            lambda s: frac(sum(1 for r in women(s) if r.consent_given == "Not approached"), len(women(s)))),
        row("Refused consent",
            lambda s: frac(sum(1 for r in women(s) if r.consent_given == "No"), len(women(s)))),
        row("Eligible (met the criteria)",
            lambda s: frac(sum(1 for r in women(s) if not exclusion_reasons(r)), len(women(s)))),
        row("Consented", lambda s: frac(sum(1 for r in women(s) if r.consent_given == "Yes"), len(women(s)))),
        row("Randomised (babies)", lambda s: len(kids(s))),
        row("Randomised in error (babies; not counted above, not followed)",
            lambda s: sum(1 for b, site in in_error if b.screening_id in sids and (s == "ALL" or site == s))),
    ]
    fu, why = {}, {}
    for _, eid in babies:
        fu[eid], why[eid] = followup_for(eid)
    for wk in (36, 40, 44):
        for state, label in (("assessed", "assessed"), ("died", "died by then"), ("ltfu", "lost to follow-up"),
                             ("awaiting", "not yet due / awaiting")):
            lines.append(row(f"{wk} wk PMA: {label}",
                             lambda s, wk=wk, state=state: frac(sum(1 for e in kids(s) if fu[e].get(wk) == state),
                                                                len(kids(s)))))
    def reasons(s):
        c = Counter(r for e in kids(s) for r in why[e].values())
        return "; ".join(f"{r} ({n})" for r, n in c.most_common()) or "—"
    lines.append(row("Reasons for loss to follow-up (any checkpoint)", reasons))
    comps = {eid: composite_for(eid) or {} for _, eid in babies}
    for key, label in OUTCOMES:
        def outcome(s, key=key):
            vals = [(comps[e].get(key) or {}).get("value") for e in kids(s)]
            yes, known = sum(v == "Yes" for v in vals), sum(v in ("Yes", "No") for v in vals)
            return (f"{yes}/{known} ({pct(yes, known)})" if known else "—") + \
                   (f" · {len(vals) - known} pending" if len(vals) > known else "")
        lines.append(row(label, outcome))

    header = ["Measure"] + [("All sites" if s == "ALL" else site_label(s)) for s in cols_sites]
    chart_rows = [("Screened", lambda s: len(women(s))),
                  ("Eligible", lambda s: sum(1 for r in women(s) if not exclusion_reasons(r))),
                  ("Consented", lambda s: sum(1 for r in women(s) if r.consent_given == "Yes")),
                  ("Randomised", lambda s: len(kids(s)))]
    return [{
        "title": "At a glance, by site",
        "note": "Women (Form A) down to Consented; babies from Randomised on (twins count twice). Percentages: "
                "of women screened, or of randomised babies. Follow-up: Form I at each checkpoint (lost to follow-up "
                "= reason recorded on Form I, or 28 days past the expected date with no assessment). Outcomes: Form I first, else the live "
                "suggestions, as on Form L; '2/3 (66.7%) · 1 pending' = 2 Yes of 3 known, 1 not yet known. "
                "Pooled, never by study arm.",
        "columns": header, "rows": lines,
        "chart": {"title": "Screened to randomised, by site", "unit": "n", "labels": [site_label(s) for s in order],
                  "series": [{"name": name, "values": [fn(s) for s in order]} for name, fn in chart_rows]},
    }]


def build(key, db, sites, date_from=None, date_to=None, *, status_for=None, composite_for=None, followup_for=None):
    if key not in REPORT_KEYS:
        raise KeyError(key)
    if key == "ae_summary":
        import ae_summary
        babies = ae_summary.collect(db, randomised_babies(db, screenings(db, sites, None, None)))
        sections = ae_summary.sections(*babies, date_from, date_to, site_label)
        period = ("AEs starting " + " to ".join(d.strftime("%d-%m-%Y") for d in (date_from, date_to) if d)
                  + " · cumulative to the end date" if date_from or date_to else "all AEs to date")
        return _report(key, sites, period, sections)
    if key == "blender_check":
        return _report(key, sites, "all Form B to date", blender_check_report(db, sites))
    rows = screenings(db, sites, date_from, date_to)
    if key == "consent":
        sections = consent_report(rows, sites, eligible_births(db, sites, date_from, date_to))
    elif key == "exclusions":
        sections = exclusions_report(rows, sites)
    elif key == "completeness":
        sections = completeness_report(randomised_babies(db, rows), sites, status_for)
    else:
        sections = glance_report(db, rows, sites, composite_for, followup_for)
    period = ("screened " + " to ".join(d.strftime("%d-%m-%Y") for d in (date_from, date_to) if d)
              if date_from or date_to else "all women screened")
    return _report(key, sites, period, sections)


def _report(key, sites, period, sections):
    meta = next(r for r in REPORTS if r["key"] == key)
    where = "All sites" if len(sites) > 1 else site_full_name(sites[0])
    return {"key": key, "title": meta["title"], "scope": f"{where} · {period}",
            "generated_at": clinical_now().strftime("%d-%m-%Y %H:%M IST"), "sections": sections}


# ------------------------------------------------------------------ files
def to_csv(rep) -> str:
    buf = io.StringIO()
    buf.write("﻿")   # Excel reads UTF-8
    w = csv.writer(buf)
    w.writerow([f"PORTAL Trial — {rep['title']}"])
    w.writerow([rep["scope"], f"Generated {rep['generated_at']}"])
    for sec in rep["sections"]:
        w.writerow([])
        w.writerow([sec["title"]])
        if sec.get("note"):
            w.writerow([sec["note"]])
        w.writerow(sec["columns"])
        w.writerows(sec["rows"])
    return buf.getvalue()


PALETTE = ["#1d4ed8", "#0f766e", "#b45309", "#7c3aed", "#be123c", "#15803d"]


def _chart(chart, width):
    from reportlab.graphics.charts.barcharts import HorizontalBarChart
    from reportlab.graphics.charts.legends import Legend
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors

    labels = [str(x)[:48] for x in chart["labels"]]
    series = chart["series"]
    if not labels or not series:
        return None
    n_bars = len(labels) * len(series)
    plot_h = max(50, min(12 * n_bars + 6 * len(labels), 320))
    legend_h = 16 if len(series) > 1 else 0
    d = Drawing(width, plot_h + 46 + legend_h)
    d.add(String(0, plot_h + 34 + legend_h, chart["title"], fontName="Helvetica-Bold", fontSize=9))
    bc = HorizontalBarChart()
    bc.x, bc.y, bc.height, bc.width = 170, 18, plot_h, width - 170 - 70
    bc.data = [list(s["values"]) or [0] for s in series]
    bc.categoryAxis.categoryNames = labels
    bc.categoryAxis.reverseDirection = 1
    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.boxAnchor = "e"
    bc.valueAxis.valueMin = 0
    top = max([max(s["values"] or [0]) for s in series] + [1])
    bc.valueAxis.valueMax = 100 if chart["unit"] == "%" and top <= 100 else top * 1.15
    bc.valueAxis.labels.fontSize = 7
    bc.barLabels.fontSize = 6
    bc.barLabelFormat = "%.1f%%" if chart["unit"] == "%" else "%d"
    bc.barLabels.nudge = 8
    bc.barSpacing = 1
    for i in range(len(series)):
        bc.bars[i].fillColor = colors.HexColor(PALETTE[i % len(PALETTE)])
        bc.bars[i].strokeColor = None
    d.add(bc)
    if len(series) > 1:
        lg = Legend()
        lg.x, lg.y = 170, plot_h + 30
        lg.alignment, lg.columnMaximum, lg.fontSize = "right", 1, 7
        lg.dx = lg.dy = 7
        lg.colorNamePairs = [(colors.HexColor(PALETTE[i % len(PALETTE)]), s["name"]) for i, s in enumerate(series)]
        d.add(lg)
    return d


def to_pdf(rep) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=14 * mm, title=f"PORTAL — {rep['title']}")
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=colors.HexColor("#00132c"))
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=8,
                        textColor=colors.HexColor("#00132c"))
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#475569"))
    cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.5, leading=9)
    head = ParagraphStyle("head", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)
    width = page[0] - 24 * mm

    def esc(v):
        return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    story = [Paragraph(f"PORTAL Trial — {esc(rep['title'])}", h1),
             Paragraph(f"{esc(rep['scope'])} · generated {esc(rep['generated_at'])} · IDs only, no names, "
                       "nothing by study arm", small), Spacer(1, 6)]
    for k, sec in enumerate(rep["sections"]):
        block = [Paragraph(esc(sec["title"]), h2)]
        if sec.get("note"):
            block.append(Paragraph(esc(sec["note"]), small))
        block.append(Spacer(1, 3))
        if sec.get("chart"):
            ch = _chart(sec["chart"], width)
            if ch:
                block += [ch, Spacer(1, 4)]
        story.append(KeepTogether(block))   # heading + note (+ chart) stay together
        data = [[Paragraph(esc(c), head) for c in sec["columns"]]]
        data += [[Paragraph(esc(c), cell) for c in r] for r in sec["rows"]] or \
                [[Paragraph("None.", cell)] + [""] * (len(sec["columns"]) - 1)]
        widths = sec.get("widths")
        if widths:
            widths = [width * w / sum(widths) for w in widths]
        elif len(sec["columns"]) > 6:
            widths = [width / len(sec["columns"])] * len(sec["columns"])
        t = Table(data, repeatRows=1, hAlign="LEFT", colWidths=widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00132c")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(t)
        if k < len(rep["sections"]) - 1:
            story.append(Spacer(1, 8))

    def footer(canvas, _doc):
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawString(12 * mm, 7 * mm, f"PORTAL Trial · {rep['title']} · {rep['generated_at']}")
        canvas.drawRightString(page[0] - 12 * mm, 7 * mm, f"Page {canvas.getPageNumber()}")

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
