"""Twice-daily report (PI 2026-10-31): one page a site's staff generate and
share to the site's WhatsApp group, morning and evening.

Columns: enrolment ID, area admitted, morbidities till date. Randomised babies
born since the trial start who are still admitted, or whose stay ended in the
last 7 days (the area column then shows Discharged / Died). The file leaves the
portal, so it carries IDs only: no names, CR or phone numbers, and nothing by
study arm. A nil report is still produced.

Area is the Location on the latest Helper 5 day that has one (multi-select,
comma separated), with that day, so an old entry is visible as old.
Morbidities are every AE term to date from the AE form and the AE detectors
(ae_candidates.py), worst grade, plus severe Form F scans not yet in Form H;
anything not on the AE form is marked auto-detected.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape
from io import BytesIO

from ae_reference import AE_DEFINITIONS
from ae_terms import term_of
from clinical_time import clinical_now
from deps import logins_from_trial
from site_summary import _int_grade, _load, _site_display

RECENT_END_DAYS = 7
NOT_RECORDED = "Not recorded"
NO_MORBIDITY = "None recorded"


def area_of(metab_logs) -> tuple[str, int | None]:
    """(latest Location, its day of life) from Helper 5, or (NOT_RECORDED, None)."""
    days = [l for l in metab_logs if l.nicu_day and (l.location or "").strip()]
    if not days:
        return NOT_RECORDED, None
    last = max(days, key=lambda l: l.nicu_day)
    return ", ".join(x.strip() for x in last.location.split(",") if x.strip()), last.nicu_day


def morbidities_of(b: dict) -> list[dict]:
    """[{name, grade, auto}], one per term, worst grade first."""
    terms: dict[str, dict] = {}

    def add(x, auto):
        slug = term_of(x)
        name = AE_DEFINITIONS[slug]["name"] if slug else (x.get("description") or "").strip()
        if not name:
            return
        t = terms.setdefault(slug or name.lower(), {"name": name, "grade": None, "auto": True})
        g = _int_grade(x.get("grade"))
        if g and g > (t["grade"] or 0):
            t["grade"] = g
        t["auto"] = t["auto"] and auto

    for e in b.get("ae_events") or []:
        if isinstance(e, dict):
            add(e, False)
    for c in b.get("candidates") or []:
        add(c, True)
    out = list(terms.values())
    for f in b.get("pending_usg") or []:
        out.append({"name": f"Form F: {f.get('side')} {f.get('finding')} grade {f.get('grade')}",
                    "grade": None, "auto": True})
    return sorted(out, key=lambda t: (-(t["grade"] or 0), t["name"]))


def morbidity_text(m: dict) -> str:
    return m["name"] + (f" grade {m['grade']}" if m["grade"] else "") + (" (auto-detected)" if m["auto"] else "")


def row_of(b: dict, today: date) -> dict | None:
    """One baby's row, or None if the stay ended over RECENT_END_DAYS ago."""
    end = b.get("end_date")
    if end and end < today - timedelta(days=RECENT_END_DAYS):
        return None
    area, area_day = area_of(b.get("metab_logs") or [])
    if end:
        area, area_day = f"{'Died' if b.get('died') else 'Discharged'} {end.strftime('%d %b')}", None
    return {"enrollment_id": b["enrollment_id"], "area": area, "area_day": area_day,
            "morbidities": morbidities_of(b)}


def build(db, site: str, now: datetime | None = None) -> dict:
    now = now or clinical_now()
    rows = [r for r in (row_of(b, now.date()) for b in _load(db, [site], now)) if r]
    for r in rows:
        r["morbidity_text"] = "; ".join(morbidity_text(m) for m in r["morbidities"]) or NO_MORBIDITY
    return {"site": site, "site_name": _site_display(site), "generated_at": now.isoformat(timespec="minutes"),
            "training": logins_from_trial(), "babies": rows}


def file_name(r: dict) -> str:
    return f"PORTAL_{r['site']}_report_{r['generated_at'].replace('T', '_').replace(':', '')}.pdf"


def render_pdf(r: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    navy = colors.HexColor("#00132c")
    cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=10, leading=13)
    idc = ParagraphStyle("id", parent=cell, fontName="Helvetica-Bold")
    head = ParagraphStyle("head", parent=idc, textColor=colors.white)
    title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=navy)
    small = ParagraphStyle("small", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#475569"))
    warn = ParagraphStyle("warn", parent=title, textColor=colors.HexColor("#b91c1c"))

    when = datetime.fromisoformat(r["generated_at"]).strftime("%d %b %Y, %H:%M IST")
    story = []
    if r["training"]:
        story.append(Paragraph("TRAINING SITE: practice data, not the trial", warn))
    story += [Paragraph(f"PORTAL Trial: {escape(r['site_name'])}", title),
              Paragraph(f"Twice-daily report, {when}. Randomised babies still admitted or whose stay ended "
                        f"in the last {RECENT_END_DAYS} days: {len(r['babies'])}.", small),
              Spacer(1, 3 * mm)]
    if r["babies"]:
        data = [[Paragraph(x, head) for x in ("Enrollment ID", "Area admitted", "Morbidities till date")]]
        for b in r["babies"]:
            area = escape(b["area"]) + (f"<br/><font size=8 color='#475569'>Day {b['area_day']}</font>"
                                        if b["area_day"] else "")
            data.append([Paragraph(escape(b["enrollment_id"]), idc), Paragraph(area, cell),
                         Paragraph(escape(b["morbidity_text"]), cell)])
        table = Table(data, colWidths=[30 * mm, 38 * mm, 112 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("<b>Nil to report.</b> No randomised baby admitted, and no stay ended "
                               f"in the last {RECENT_END_DAYS} days.", cell))
    story += [Spacer(1, 3 * mm),
              Paragraph("Area: Location on the latest Helper 5 entry, with its day of life. Auto-detected: found from "
                        "the portal data, not yet on the AE form. IDs only: do not add names or photographs.", small)]
    out = BytesIO()
    SimpleDocTemplate(out, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                      bottomMargin=14 * mm, title="PORTAL twice-daily report").build(story)
    return out.getvalue()
