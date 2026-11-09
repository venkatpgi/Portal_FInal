"""Monthly AE / SAE summary for the IEC and DSMB (PI 2026-11-09): once a
month, pooled across both arms (no unblinding unless the DSMB asks), by site,
with the literature baseline (ae_baseline.py) beside each AE term.

Period = AE start date (SAE onset) from / to; cumulative = everything that
started by the end of the period. Denominator = randomised babies born by the
end of the period. A baby counts once per term however many rows it has.
Terms are typed by hand on the AE form, so each row is grouped under its INC
AE term (ae_reference.AE_DEFINITIONS): the definition number when it is a
term key, else the description matched to a term name, else "Other: <as
typed>". Rows with no readable start date count in the cumulative columns
and are listed under data checks. IDs only, never names.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date

import ae_baseline
from ae_reference import AE_DEFINITIONS

GRADES = ("1", "2", "3", "4", "5")
_DROP = {"neonatal", "infantile", "of", "the", "newborn", "acute"}
_FIXES = (("billi", "bili"), ("brachy", "brady"), ("haem", "hem"), ("anaem", "anem"))


def _norm(text) -> str:
    t = str(text or "").lower()
    for a, b in _FIXES:
        t = t.replace(a, b)
    return " ".join(w for w in re.findall(r"[a-z]+", t) if w not in _DROP)


def _keys(name: str) -> set[str]:
    full = _norm(name)
    bare = _norm(re.sub(r"\([^)]*\)", " ", name))
    keys = {full, bare} | {_norm(p) for p in re.split(r"/", re.sub(r"\([^)]*\)", " ", name))}
    keys |= {_norm(a) for a in re.findall(r"\(([^)]*)\)", name)}
    return {k for k in keys if k}


TERM_KEYS = {slug: _keys(d["name"]) for slug, d in AE_DEFINITIONS.items()}


def term_of(e: dict) -> tuple[str | None, str]:
    """(INC term slug or None, label)."""
    code = str(e.get("definition_no") or "").strip()
    if code in AE_DEFINITIONS:
        return code, AE_DEFINITIONS[code]["name"]
    desc = _norm(e.get("description"))
    if desc:
        for slug, keys in TERM_KEYS.items():
            if desc in keys:
                return slug, AE_DEFINITIONS[slug]["name"]
        for slug, keys in TERM_KEYS.items():   # cut-off text, e.g. "respiratory distress syndrome rds"
            if any(len(k) > 6 and (desc.startswith(k) or k.startswith(desc)) for k in keys):
                return slug, AE_DEFINITIONS[slug]["name"]
    shown = " ".join(str(e.get("description") or code or "not named").split())
    return None, f"Other: {shown[:60]}"


def _day(v) -> date | None:
    try:
        d = date.fromisoformat(str(v or "").strip()[:10])
    except ValueError:
        return None
    return d if d.year >= 2000 else None


def _in(d, date_from, date_to) -> bool:
    return d is not None and (not date_from or d >= date_from) and (not date_to or d <= date_to)


def _by_end(d, date_to) -> bool:
    return not date_to or d is None or d <= date_to


def _pct(n, d) -> str:
    return f"{n} ({100 * n / d:.1f}%)" if d else str(n)


def _fmt(d) -> str:
    return d.strftime("%d-%m-%Y") if d else "—"


def sections(babies, events_by_baby, saes, deaths, date_from, date_to, site_label):
    """babies [(site, eid, dob)]; events_by_baby {eid: [AE rows]}; saes [SAE
    report rows]; deaths {eid: death date or None}."""
    babies = [b for b in babies if _by_end(b[2], date_to)]
    site_of = {eid: s for s, eid, _ in babies}
    order = sorted({s for s, _, _ in babies})
    cols = order + (["ALL"] if len(order) > 1 else [])
    n_babies = Counter(site_of.values())
    n_babies["ALL"] = len(babies)

    rows = []   # (eid, site, slug, label, start, end, grade, sae, raw)
    checks = []
    for eid, evs in events_by_baby.items():
        if eid not in site_of:
            continue
        for i, e in enumerate(evs or [], start=1):
            if not isinstance(e, dict):
                continue
            slug, label = term_of(e)
            start, end = _day(e.get("start_date")), _day(e.get("end_date"))
            if not _by_end(start, date_to):
                continue
            grade = str(e.get("grade") or "").strip()
            rows.append((eid, site_of[eid], slug, label, start, end, grade,
                         str(e.get("converted_to_sae") or "").strip() == "Yes", e))
            if start is None:
                checks.append([eid, site_label(site_of[eid]), f"Row {i}", label, "No readable start date"])
            if str(e.get("end_date") or "").strip() and (end is None or (start and end < start)):
                checks.append([eid, site_label(site_of[eid]), f"Row {i}", label,
                               "End date not valid" if end is None else "End date before start date"])
            if slug is None:
                checks.append([eid, site_label(site_of[eid]), f"Row {i}", label, "Not matched to an INC AE term"])
            if grade not in GRADES:
                checks.append([eid, site_label(site_of[eid]), f"Row {i}", label, "Grade blank"])
    period = [r for r in rows if _in(r[4], date_from, date_to)]
    saes = [s for s in saes if s.enrollment_id in site_of and _by_end(_day(s.onset_datetime), date_to)]
    died = {e: d for e, d in deaths.items() if e in site_of and _by_end(d, date_to)}

    def at(s, xs, key=lambda x: x[1]):
        return [x for x in xs if s == "ALL" or key(x) == s]

    summary = []
    for label, fn in (
        ("Randomised babies (denominator)", lambda s: n_babies[s]),
        ("Babies with any AE", lambda s: _pct(len({r[0] for r in at(s, rows)}), n_babies[s])),
        ("AE rows started in the period", lambda s: len(at(s, period))),
        ("AE rows, cumulative", lambda s: len(at(s, rows))),
        ("AE rows grade 3 or more, cumulative", lambda s: len([r for r in at(s, rows) if r[6] in ("3", "4", "5")])),
        ("AE rows converted to SAE, cumulative", lambda s: len([r for r in at(s, rows) if r[7]])),
        ("SAE reports (Form Y), cumulative", lambda s: len(at(s, saes, key=lambda x: site_of[x.enrollment_id]))),
        ("Deaths, cumulative", lambda s: _pct(len([e for e in died if s == "ALL" or site_of[e] == s]), n_babies[s])),
    ):
        summary.append([label] + [fn(s) for s in cols])

    terms = defaultdict(list)
    for r in rows:
        terms[(r[2], r[3])].append(r)
    death_label = ("death", "Death (any cause)")
    term_rows, site_rows, chart = [], [], []
    for (slug, label), rs in sorted(terms.items(), key=lambda kv: (kv[0][0] is None, -len({r[0] for r in kv[1]}), kv[0][1])):
        kids = {r[0] for r in rs}
        g = Counter(r[6] if r[6] in GRADES else "blank" for r in rs)
        term_rows.append([label, _pct(len(kids), len(babies)),
                          len([r for r in rs if _in(r[4], date_from, date_to)]), len(rs)]
                         + [g[x] for x in GRADES] + [g["blank"], len([r for r in rs if r[7]]),
                                                     ae_baseline.baseline(slug) if slug else "—"])
        site_rows.append([label] + [_pct(len({r[0] for r in rs if s == "ALL" or r[1] == s}), n_babies[s]) for s in cols])
        if slug:
            chart.append((label, round(100 * len(kids) / len(babies), 1) if babies else 0.0))
    term_rows.append([death_label[1], _pct(len(died), len(babies)), len([d for d in died.values() if _in(d, date_from, date_to)]),
                      len(died)] + [""] * 7 + [ae_baseline.baseline("death")])
    site_rows.append([death_label[1]] + [_pct(len([e for e in died if s == "ALL" or site_of[e] == s]), n_babies[s])
                                          for s in cols])

    sae_rows = [[s.enrollment_id, site_label(site_of[s.enrollment_id]), s.report_type or "—",
                 " ".join(str(s.diagnosis or "—").split()), _fmt(_day(s.onset_datetime)),
                 ", ".join(s.seriousness) if isinstance(s.seriousness, list) else str(s.seriousness or "—"),
                 s.severity or "—", s.causality or "—", s.outcome or "—"]
                for s in sorted(saes, key=lambda s: (_day(s.onset_datetime) or date.min, s.enrollment_id))
                if _in(_day(s.onset_datetime), date_from, date_to) or not (date_from or date_to)]
    listing = [[r[0], site_label(r[1]), r[3], _fmt(r[4]), _fmt(r[5]), r[6] or "—", "Yes" if r[7] else "No"]
               for r in sorted(period, key=lambda r: (r[1], r[0], r[4] or date.min))]
    names = ["All sites" if s == "ALL" else site_label(s) for s in cols]
    draft = "" if ae_baseline.APPROVED else " DRAFT: the literature values are awaiting the PI's approval."
    return [{
        "title": "Summary by site",
        "note": "Pooled across both study arms (blinded). Denominator: randomised babies born by the end of the "
                "period; '3 (12.5%)' = 3 babies of the denominator. Deaths: from the DMS / Form H end of stay or Form I.",
        "columns": ["Measure"] + names, "rows": summary,
    }, {
        "title": "AEs by term, all sites (cumulative)",
        "note": "A baby counts once per term. Grade columns count AE rows. Literature baseline: the published "
                "frequency in a comparable population, with its source below; populations differ from PORTAL "
                "(25+0 to 31+6 weeks), so read it as a guide, not a test." + draft,
        "columns": ["AE term", "Babies affected", "Rows in period", "Rows cumulative", "G1", "G2", "G3", "G4", "G5",
                    "Grade blank", "To SAE", "Literature baseline"],
        "widths": [16, 9, 6, 7, 3.5, 3.5, 3.5, 3.5, 3.5, 5, 5, 32],
        "rows": term_rows,
        "chart": {"title": "% of randomised babies with each AE (cumulative)", "unit": "%",
                  "labels": [c[0] for c in chart[:15]],
                  "series": [{"name": "% of babies", "values": [c[1] for c in chart[:15]]}]},
    }, {
        "title": "AEs by term and site (babies affected, cumulative)",
        "note": "Percent of that site's randomised babies.",
        "columns": ["AE term"] + names, "rows": site_rows,
    }, {
        "title": "SAE reports (Form Y)" + (" with onset in the period" if date_from or date_to else ""),
        "note": "One line per report (Initial / Follow-up / Final).",
        "columns": ["Enrolment ID", "Site", "Report", "SAE", "Onset", "Seriousness", "Severity", "Causality", "Outcome"],
        "rows": sae_rows,
    }, {
        "title": "AE line listing, rows started in the period",
        "note": "Term as grouped above; the AE form keeps the text as typed.",
        "columns": ["Enrolment ID", "Site", "AE term", "Start", "End", "Grade", "Converted to SAE"],
        "rows": listing,
    }, {
        "title": "Data checks for the sites",
        "note": "Rows the summary could not place exactly. Fix them on the AE form.",
        "columns": ["Enrolment ID", "Site", "Row", "AE term", "Check"], "rows": checks,
    }, {
        "title": "Literature baseline: sources",
        "note": "Values are quoted from each source's abstract." + draft,
        "columns": ["Ref", "Source", "Population"],
        "widths": [5, 65, 30],
        "rows": [[k, cite, pop] for k, (cite, pop) in ae_baseline.SOURCES.items()],
    }]


def collect(db, babies_with_site):
    """(babies [(site, eid, dob)], events_by_baby, saes, deaths) for these babies."""
    import death_alert
    from models import AdverseEvents, BirthResuscitation, SAEReport
    eids = [eid for _, eid in babies_with_site]
    if not eids:
        return [], {}, [], {}
    dob = dict(db.query(BirthResuscitation.enrollment_id, BirthResuscitation.date_of_birth)
               .filter(BirthResuscitation.enrollment_id.in_(eids)))
    babies = [(s, eid, dob.get(eid)) for s, eid in babies_with_site]
    events = {a.enrollment_id: a.events for a in
              db.query(AdverseEvents).filter(AdverseEvents.enrollment_id.in_(eids))}
    saes = db.query(SAEReport).filter(SAEReport.enrollment_id.in_(eids)).all()
    deaths = {}
    for eid in eids:
        st = death_alert.status(db, eid)
        if st["died"]:
            deaths[eid] = _day(st["date"])
    return babies, events, saes, deaths
