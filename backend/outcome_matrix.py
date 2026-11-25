"""Outcome matrix (PI 2026-11-26): one row per randomised baby, one column per
protocol outcome, so every baby's outcomes can be seen at a glance.

Values come from the same rules as Form L's composite suggestion
(main.get_composite_suggestion, composite_suggestion.py, docs ch05): Form I's
saved answers first; the live BPD / ROP / NEC / brain-injury / death
suggestions from daily logs, Form H, Form F and Form J only where Form I is
blank. Never by arm.

Each cell: {state, text, source, note}
  state   yes      occurred (with its date when known)
          no       assessed, did not occur
          pending  the time point has not come yet ("due <date>")
          overdue  the time point (+2 days) has passed and nothing is known
          na       not applicable (after a death; not in the MRI subset)
  source  recorded  on Form I (Form K for MRI; composites: their deciding
                    parts are on Form I)
          detected  from daily logs / Form H / Form F / Form J, not yet on Form I
For the PI and scientists (routers: same people as Reports).
"""
from __future__ import annotations

from datetime import date, timedelta

GRACE_DAYS = 2           # checkpoint window +/- 2 days (followup_due.WINDOW_DAYS)
COLUMNS = [
    ("death", "Death (by 44 wk)"),
    ("bpd", "BPD at 36 wk"),
    ("nec", "NEC ≥ IIA"),
    ("brain", "Brain injury (IVH ≥ III / cPVL ≥ II)"),
    ("rop", "ROP needing treatment"),
    ("mri", "MRI at term (subset)"),
    ("composite_1", "Composite 1 (36 wk)"),
    ("composite_2", "Composite 2 (44 wk)"),
    ("visit36", "Form I 36 wk"),
    ("visit40", "Form I 40 wk"),
    ("visit44", "Form I 44 wk"),
]
STATES = ("yes", "no", "pending", "overdue", "na")


def fmt(d: date | None) -> str:
    return d.strftime("%d %b %Y") if d else ""


def _iso(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def form_i_dates(fi) -> dict:
    """When each outcome occurred, from Form I's own date items."""
    if fi is None:
        return {}
    g = lambda k: getattr(fi, k, None)   # noqa: E731
    out = {}
    for wk in (36, 40, 44):
        if g(f"death{wk}") is True and g(f"death{wk}_date") and "death" not in out:
            out["death"] = g(f"death{wk}_date")
        if g(f"nec{wk}_stage") is True and g(f"nec{wk}_date") and "nec" not in out:
            out["nec"] = g(f"nec{wk}_date")
        for flag, dk in ((f"ivh{wk}_grade3", f"ivh{wk}_date"), (f"cpvl{wk}_grade2", f"cpvl{wk}_date")):
            if g(flag) is True and g(dk):
                out["brain"] = min(out.get("brain", g(dk)), g(dk))
        if g(f"rop{wk}_treated") is True and g(f"rop{wk}_date") and "rop" not in out:
            out["rop"] = g(f"rop{wk}_date")
    if g("bpd36_jensen_grade") and "No BPD" not in str(g("bpd36_jensen_grade")) and g("bpd36_jensen_date"):
        out["bpd"] = g("bpd36_jensen_date")
    return out


def cell(value, *, target: date | None, today: date, died: bool, recorded: bool, when: date | None = None,
         detail: str = "", note: str = "", is_death: bool = False) -> dict:
    """One outcome cell from a component value "Yes" / "No" / "NA" / None."""
    src = "recorded" if recorded else "detected"
    if value == "Yes":
        bits = [b for b in (fmt(when), detail) if b]
        return {"state": "yes", "text": "Yes" + (f" · {', '.join(bits)}" if bits else ""), "source": src,
                "note": note}
    if value == "No":
        return {"state": "no", "text": "No", "source": src, "note": note}
    if value == "NA":
        return {"state": "na", "text": "—", "source": "recorded", "note": note}
    if died and not is_death:
        return {"state": "na", "text": "—", "source": "", "note": "after death"}
    if target is None:
        return {"state": "pending", "text": "date unknown", "source": "", "note": note or detail}
    if today <= target + timedelta(days=GRACE_DAYS):
        return {"state": "pending", "text": f"due {fmt(target)}", "source": "", "note": note or detail}
    return {"state": "overdue", "text": f"overdue since {fmt(target)}", "source": "", "note": note or detail}


def visit_cell(row: dict | None) -> dict:
    """Form I checkpoint visit from followup_list.rows_for()."""
    if row is None:
        return {"state": "pending", "text": "date unknown", "source": "", "note": ""}
    st = row["status"]
    if st == "done":
        return {"state": "yes", "text": "Done", "source": "recorded", "note": ""}
    if st == "ended":
        return {"state": "na", "text": "—", "source": "", "note": row["text"]}
    if st == "overdue":
        return {"state": "overdue", "text": f"overdue since {fmt(row['window_to'])}", "source": "",
                "note": row["text"]}
    label = "booked" if st == "booked" else "due"
    when = row.get("booked") or row["due"]
    return {"state": "pending", "text": f"{label} {fmt(when)}", "source": "", "note": row["text"]}


def row_for(baby: dict, comp: dict, visits: dict, today: date, form_l=None) -> dict:
    """baby: followup_due.babies() dict; comp: get_composite_suggestion() output;
    visits: {36: followup_list row, ...}."""
    parts = comp.get("components") or {}
    t36, t44 = _iso(comp.get("checkpoint_36")), _iso(comp.get("checkpoint_44"))
    dates = form_i_dates(baby.get("form_i"))
    died = bool(baby.get("died"))

    def part(key, target, is_death=False):
        c = parts.get(key) or {}
        when = dates.get("death" if key.startswith("death") else key)
        if key.startswith("death") and not when and c.get("value") == "Yes":
            when = baby.get("death_date")
        return cell(c.get("value"), target=target, today=today, died=died, recorded=c.get("source") == "Form I",
                    when=when, detail="" if when else (c.get("detail") or ""), is_death=is_death,
                    note=(c.get("source") or "") if c.get("source") != "Form I" else "")

    def composite(key, names):
        c = comp.get(key) or {}
        deciding = [parts.get(n) or {} for n in names]
        if c.get("value") == "Yes":
            recorded = any(d.get("value") == "Yes" and d.get("source") == "Form I" for d in deciding)
        else:
            recorded = all(d.get("source") == "Form I" for d in deciding)
        saved = getattr(form_l, key, None) if form_l is not None else None
        if saved in ("yes", "no"):
            return cell("Yes" if saved == "yes" else "No", target=None, today=today, died=False, recorded=True,
                        note="Form L")
        return cell(c.get("value"), target=t36 if key == "composite_1" else t44, today=today, died=False,
                    recorded=recorded, note=c.get("note") or "")

    mri = comp.get("mri_abnormality") or {}
    cells = {
        "death": part("death44", t44, is_death=True),
        "bpd": part("bpd", t36),
        "nec": part("nec", t44),
        "brain": part("brain", t44),
        "rop": part("rop", t44),
        "mri": cell(mri.get("value"), target=t44, today=today, died=died, recorded=True,
                    note=mri.get("note") or ""),
        "composite_1": composite("composite_1", ("death36", "bpd")),
        "composite_2": composite("composite_2", ("death44", "bpd", "rop", "nec", "brain")),
    }
    # MRI is only known when Form K says so; an unknown MRI is never "overdue"
    # before Form K is filled (subset selection may come later).
    if cells["mri"]["state"] == "overdue" and mri.get("value") is None:
        cells["mri"] = {"state": "pending", "text": "Form K not filled", "source": "", "note": mri.get("note") or ""}
    for wk in (36, 40, 44):
        cells[f"visit{wk}"] = visit_cell(visits.get(wk))
    return {"site": baby["site"], "enrollment_id": baby["enrollment_id"],
            "dob": baby["dob"].isoformat() if baby.get("dob") else None,
            "ga": (f"{baby['ga_days'] // 7}+{baby['ga_days'] % 7}" if baby.get("ga_days") is not None else ""),
            "status": ("Died" if died else "Admitted" if baby.get("end") is None else "Discharged"),
            "cells": cells}


def totals(rows: list[dict]) -> dict:
    """{column: {state: n}}, pooled (never by arm)."""
    out = {k: {s: 0 for s in STATES} for k, _ in COLUMNS}
    for r in rows:
        for k, _ in COLUMNS:
            out[k][r["cells"][k]["state"]] += 1
    return out


def report_sections(rows: list[dict], site_label) -> list[dict]:
    """Ready-made report: totals, then one line per baby."""
    t = totals(rows)
    names = {"yes": "Occurred / done", "no": "No", "pending": "Pending", "overdue": "Overdue", "na": "Not applicable"}
    total_rows = [[names[s]] + [t[k][s] for k, _ in COLUMNS] for s in STATES]

    def show(c):
        mark = " *" if c.get("source") == "detected" else ""
        return c["text"] + mark

    return [{
        "title": f"Totals ({len(rows)} babies, all arms together)",
        "note": "Counts per outcome. Never split by study arm.",
        "columns": ["State"] + [label for _, label in COLUMNS],
        "rows": total_rows,
    }, {
        "title": f"Per baby ({len(rows)})",
        "note": "Form I first; where Form I is blank, the outcome found in daily logs / Form H / Form F / "
                "Form J (marked *: not yet on Form I). Due = the checkpoint date; overdue = 2 days after it "
                "with nothing known. — = not applicable (after death, or not in the MRI subset).",
        "columns": ["Enrollment ID", "Site", "GA", "Status"] + [label for _, label in COLUMNS],
        "rows": [[r["enrollment_id"], site_label(r["site"]), r["ga"], r["status"]]
                 + [show(r["cells"][k]) for k, _ in COLUMNS] for r in rows],
    }]
