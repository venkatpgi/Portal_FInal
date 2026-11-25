"""Outcome matrix (PI 2026-11-26): one row per randomised baby, every Form I
outcome as a column, in the order the outcomes happen as the baby grows:
at birth (I.1) -> first 72 h / 7 days (I.2) -> to 28 days / the stay (I.2) ->
36 wk PMA (I.3) -> 40 wk (I.4) -> 44 wk (I.5) -> overall + composites (I.6,
Form L). A short "Key outcomes" view keeps the protocol outcomes together.

Each value: Form I's saved answer first; where Form I is blank, the same
suggestion Form I itself fills in (Form B for I.1, post-resus / respiratory /
infection / survival checks for I.2 and I.6, the 36/40/44 wk assessment
suggestion for I.3-I.5; main._form_i_suggestions). Key outcomes and the
composites use the Form L composite rules (main.get_composite_suggestion).
Never by arm.

Cell: {state, text, source, note}
  state   yes      occurred / done (with its date when known)
          no       did not occur
          val      a measured value (days, seconds)
          pending  not due yet ("due <date>", "at discharge")
          overdue  due and nothing known ("not entered", "overdue · <date>")
          na       not applicable (after the baby died; not in the MRI subset)
  source  recorded on Form I (Form K for MRI, Form L for a saved composite)
          detected from the data, not yet saved on Form I
For the PI and scientists (same people as Reports).
"""
from __future__ import annotations

from datetime import date, timedelta

GRACE_DAYS = 2           # checkpoint window +/- 2 days (followup_due.WINDOW_DAYS)

SECTIONS = [
    ("key", "Key outcomes (summary)"),
    ("birth", "At birth (resuscitation)"),
    ("week1", "First 72 hours – 7 days"),
    ("day28", "Up to 28 days / the stay"),
    ("pma36", "36 weeks PMA"),
    ("pma40", "40 weeks PMA"),
    ("pma44", "44 weeks PMA"),
    ("overall", "Overall and composites"),
]

# key, section, label, Form I field, kind, due, date field, extra
#   kind: yn (Yes/No), grade (text, "No ..."/"None" = No), num (value), text
#   due:  birth, dol3, dol7, dol28, stay (end of stay), cp36, cp40, cp44
ITEMS = [
    ("ventilation_required", "birth", "PPV needed", "yn", "birth", None),
    ("switched_100_o2", "birth", "Switched to 100% O₂", "yn", "birth", None),
    ("resus_chest_compressions", "birth", "Chest compressions", "yn", "birth", None),
    ("intubation_during_resus", "birth", "Intubated at resuscitation", "yn", "birth", None),
    ("time_to_spontaneous_breathing", "birth", "Time to spontaneous breathing (s)", "num", "birth", None),
    ("hie_grade", "birth", "HIE (Levene)", "grade", "dol3", None),
    ("resp_support_72h", "week1", "Respiratory support 0.5–72 h", "yn", "dol3", None),
    ("sepsis_eos", "week1", "Early-onset sepsis", "yn", "dol3", None),
    ("mortality_7_days", "week1", "Death ≤ 7 days", "yn", "dol7", "mortality_7d_date"),
    ("sepsis_los", "day28", "Late-onset sepsis", "yn", "stay", None),
    ("culture_positive_sepsis", "day28", "Culture-positive sepsis", "yn", "stay", None),
    ("mortality_28_days", "day28", "Death ≤ 28 days", "yn", "dol28", "mortality_28d_date"),
    ("death36", "pma36", "Death by 36 wk", "yn", "cp36", "death36_date"),
    ("bpd36_jensen_grade", "pma36", "BPD (Jensen)", "grade", "cp36", "bpd36_jensen_date"),
    ("bpd36_nichd_grade", "pma36", "BPD (NICHD)", "grade", "cp36", "bpd36_nichd_date"),
    ("nec36_stage", "pma36", "NEC ≥ IIA", "yn", "cp36", "nec36_date"),
    ("ivh36_grade3", "pma36", "IVH ≥ III", "yn", "cp36", "ivh36_date"),
    ("cpvl36_grade2", "pma36", "cPVL ≥ II", "yn", "cp36", "cpvl36_date"),
    ("rop36", "pma36", "ROP", "yn", "cp36", "rop36_date"),
    ("rop36_treated", "pma36", "ROP treated", "yn", "cp36", None),
    ("death40", "pma40", "Death 36–40 wk", "yn", "cp40", "death40_date"),
    ("nec40_stage", "pma40", "NEC ≥ IIA", "yn", "cp40", "nec40_date"),
    ("ivh40_grade3", "pma40", "IVH ≥ III", "yn", "cp40", "ivh40_date"),
    ("cpvl40_grade2", "pma40", "cPVL ≥ II", "yn", "cp40", "cpvl40_date"),
    ("rop40", "pma40", "ROP", "yn", "cp40", "rop40_date"),
    ("rop40_treated", "pma40", "ROP treated", "yn", "cp40", None),
    ("abnormal_mri_tea", "pma40", "Abnormal MRI at TEA", "text", "cp40", None),
    ("death44", "pma44", "Death 40–44 wk", "yn", "cp44", "death44_date"),
    ("nec44_stage", "pma44", "NEC ≥ IIA", "yn", "cp44", "nec44_date"),
    ("ivh44_grade3", "pma44", "IVH ≥ III", "yn", "cp44", "ivh44_date"),
    ("cpvl44_grade2", "pma44", "cPVL ≥ II", "yn", "cp44", "cpvl44_date"),
    ("rop44_assessed", "pma44", "ROP", "yn", "cp44", "rop44_date"),
    ("rop44_treated", "pma44", "ROP treated", "yn", "cp44", None),
    ("mv_days", "overall", "Invasive ventilation (days)", "num", "stay", None),
    ("cpap_days", "overall", "CPAP (days)", "num", "stay", None),
    ("hfnc_days", "overall", "HFNC (days)", "num", "stay", None),
    ("nippv_days", "overall", "NIPPV (days)", "num", "stay", None),
    ("sepsis_overall", "overall", "Sepsis (any)", "yn", "stay", None),
    ("mortality_in_hospital", "overall", "Death in hospital", "yn", "stay", "mortality_hospital_date"),
    ("mortality_after_discharge", "overall", "Death after discharge", "yn", "cp44", "mortality_after_discharge_date"),
]
KEY_COLUMNS = [
    ("k_death", "Death (by 44 wk)"),
    ("k_bpd", "BPD at 36 wk"),
    ("k_nec", "NEC ≥ IIA (by 44 wk)"),
    ("k_brain", "Brain injury (IVH ≥ III / cPVL ≥ II)"),
    ("k_rop", "ROP needing treatment"),
    ("k_mri", "MRI at term (subset)"),
    ("composite_1", "Composite 1 (36 wk)"),
    ("composite_2", "Composite 2 (44 wk)"),
]
VISIT_COLUMNS = {"pma36": ("visit36", "Form I visit"), "pma40": ("visit40", "Form I visit"),
                 "pma44": ("visit44", "Form I visit")}


def columns() -> list[dict]:
    """Every column in display order: [{key, label, section}]."""
    out = [{"key": k, "label": label, "section": "key"} for k, label in KEY_COLUMNS]
    for sec, _ in SECTIONS[1:]:
        if sec in VISIT_COLUMNS:
            k, label = VISIT_COLUMNS[sec]
            out.append({"key": k, "label": label, "section": sec})
        out += [{"key": i[0], "label": i[2], "section": sec} for i in ITEMS if i[1] == sec]
        if sec == "overall":
            out += [{"key": k, "label": label, "section": sec} for k, label in KEY_COLUMNS if k.startswith("composite")]
    return out


COLUMNS = [(c["key"], c["label"]) for c in columns()]
STATES = ("yes", "no", "val", "pending", "overdue", "na")


def fmt(d: date | None) -> str:
    """Short date for a cell: 23 Oct 26."""
    return d.strftime("%d %b %y") if d else ""


def _iso(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _yn(v):
    if v is True or (isinstance(v, str) and v.strip().lower() in ("yes", "true")):
        return True
    if v is False or (isinstance(v, str) and v.strip().lower() in ("no", "false")):
        return False
    return None


# ------------------------------------------------------------------ cells
def cell(value, *, target: date | None, today: date, died: bool, recorded: bool, when: date | None = None,
         detail: str = "", note: str = "", is_death: bool = False) -> dict:
    """A key-outcome cell from a component value "Yes" / "No" / "NA" / None."""
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
    return {"state": "overdue", "text": f"overdue · {fmt(target)}", "source": "", "note": note or detail}


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
        return {"state": "overdue", "text": f"overdue · {fmt(row['window_to'])}", "source": "",
                "note": row["text"]}
    label = "booked" if st == "booked" else "due"
    when = row.get("booked") or row["due"]
    return {"state": "pending", "text": f"{label} {fmt(when)}", "source": "", "note": row["text"]}


def due_date(rule: str, dob: date | None, t: dict, end: date | None) -> date | None:
    if rule == "stay":
        return end
    if rule in t:
        return t[rule]
    if dob is None:
        return None
    return dob + timedelta(days={"birth": 0, "dol3": 3, "dol7": 7, "dol28": 28}[rule])


def item_cell(item, fi, sugg: dict, *, dob, t: dict, end, admitted: bool, died: bool, death_date, today) -> dict:
    """One Form I item: saved answer, else the suggestion, else due / overdue."""
    key, _sec, _label, kind, rule, date_field = item
    saved = getattr(fi, key, None) if fi is not None else None
    recorded = not _blank(saved)
    value = saved if recorded else sugg.get(key)
    when = _iso(getattr(fi, date_field, None) if (fi is not None and date_field) else None) \
        or _iso(sugg.get(date_field) if date_field else None)
    src = "recorded" if recorded else "detected"
    if not _blank(value):
        if kind == "yn":
            v = _yn(value)
            if v is True:
                return {"state": "yes", "text": "Yes" + (f" · {fmt(when)}" if when else ""), "source": src, "note": ""}
            if v is False:
                return {"state": "no", "text": "No", "source": src, "note": ""}
        elif kind == "num":
            try:
                n = float(value)
                return {"state": "val", "text": f"{n:g}", "source": src, "note": ""}
            except (TypeError, ValueError):
                pass
        elif kind == "grade":
            text = str(value).split("→")[-1].strip()
            if text.lower().startswith(("no ", "none")) or text.lower() in ("no", "none"):
                return {"state": "no", "text": text, "source": src, "note": ""}
            return {"state": "yes", "text": text + (f" · {fmt(when)}" if when else ""), "source": src, "note": ""}
        else:   # free text: Yes / No / NA style answers
            v = _yn(value)
            if v is True:
                return {"state": "yes", "text": "Yes", "source": src, "note": ""}
            if v is False:
                return {"state": "no", "text": "No", "source": src, "note": ""}
            if str(value).strip().lower() in ("na", "n/a", "not applicable", "not done"):
                return {"state": "na", "text": "—", "source": src, "note": str(value)}
            return {"state": "val", "text": str(value), "source": src, "note": ""}
    target = due_date(rule, dob, t, end)
    if rule == "stay" and admitted:
        return {"state": "pending", "text": "at discharge", "source": "", "note": ""}
    if died and death_date and target and death_date < target and not key.startswith(("death", "mortality")):
        return {"state": "na", "text": "—", "source": "", "note": "after death"}
    if died and key in ("mortality_after_discharge",) and end and death_date and death_date <= end:
        return {"state": "na", "text": "—", "source": "", "note": "died in hospital"}
    if target is None:
        return {"state": "pending", "text": "date unknown", "source": "", "note": ""}
    grace = GRACE_DAYS if rule.startswith("cp") else 0
    if today <= target + timedelta(days=grace) and rule != "birth":
        return {"state": "pending", "text": f"due {fmt(target)}", "source": "", "note": ""}
    return {"state": "overdue", "text": "not entered" if rule == "birth" else f"overdue · {fmt(target)}",
            "source": "", "note": ""}


def form_i_dates(fi) -> dict:
    """When each key outcome occurred, from Form I's own date items."""
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


# ------------------------------------------------------------------ rows
def row_for(baby: dict, comp: dict, visits: dict, today: date, form_l=None, sugg: dict | None = None) -> dict:
    """baby: followup_due.babies() dict; comp: get_composite_suggestion();
    visits: {36: followup_list row, ...}; sugg: main._form_i_suggestions()."""
    parts = comp.get("components") or {}
    t36, t44 = _iso(comp.get("checkpoint_36")), _iso(comp.get("checkpoint_44"))
    dob, ga = baby.get("dob"), baby.get("ga_days")
    t = {}
    if dob is not None and ga is not None:
        t = {f"cp{wk}": dob + timedelta(days=wk * 7 - ga) for wk in (36, 40, 44)}
    t36 = t36 or t.get("cp36")
    t44 = t44 or t.get("cp44")
    fi = baby.get("form_i")
    dates = form_i_dates(fi)
    died = bool(baby.get("died"))
    end = (baby.get("end") or {}).get("date") if baby.get("end") else None

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
        "k_death": part("death44", t44, is_death=True),
        "k_bpd": part("bpd", t36),
        "k_nec": part("nec", t44),
        "k_brain": part("brain", t44),
        "k_rop": part("rop", t44),
        "k_mri": cell(mri.get("value"), target=t44, today=today, died=died, recorded=True,
                      note=mri.get("note") or ""),
        "composite_1": composite("composite_1", ("death36", "bpd")),
        "composite_2": composite("composite_2", ("death44", "bpd", "rop", "nec", "brain")),
    }
    if cells["k_mri"]["state"] == "overdue" and mri.get("value") is None:
        cells["k_mri"] = {"state": "pending", "text": "Form K not filled", "source": "", "note": mri.get("note") or ""}
    for wk in (36, 40, 44):
        cells[f"visit{wk}"] = visit_cell(visits.get(wk))
    sugg = sugg or {}
    for item in ITEMS:
        cells[item[0]] = item_cell(item, fi, sugg, dob=dob, t=t, end=end, admitted=baby.get("end") is None,
                                   died=died, death_date=baby.get("death_date"), today=today)
    return {"site": baby["site"], "enrollment_id": baby["enrollment_id"],
            "dob": dob.isoformat() if dob else None,
            "ga": (f"{ga // 7}+{ga % 7}" if ga is not None else ""),
            "status": ("Died" if died else "Admitted" if baby.get("end") is None else "Discharged"),
            "cells": cells}


def totals(rows: list[dict]) -> dict:
    """{column: {state: n}}, pooled (never by arm)."""
    out = {k: {s: 0 for s in STATES} for k, _ in COLUMNS}
    for r in rows:
        for k, _ in COLUMNS:
            c = r["cells"].get(k)
            if c:
                out[k][c["state"]] += 1
    return out


STATE_WORDS = {"yes": "Yes", "no": "No", "val": "Value", "pending": "Due", "overdue": "Overdue", "na": "N/A"}


def total_text(t: dict) -> str:
    """'Yes 2 · No 21 · Due 3' (empty states left out)."""
    return " · ".join(f"{STATE_WORDS[s]} {t[s]}" for s in STATES if t.get(s))


def report_sections(rows: list[dict], site_label) -> list[dict]:
    """Ready-made report: one table per section (time order), each with totals."""
    cols = columns()
    out = []

    def show(c):
        return c["text"] + (" *" if c.get("source") == "detected" else "")

    for sec, title in SECTIONS:
        sc = [c for c in cols if c["section"] == sec]
        t = totals(rows)
        out.append({
            "title": f"{title} ({len(rows)} babies)",
            "note": ("Form I first; where Form I is blank, what the data show (marked *: not yet saved on "
                     "Form I). Due = when it is assessed; overdue = due and nothing known. — = not applicable. "
                     "All arms together, never by arm.") if sec == "key" else "",
            "columns": ["Enrollment ID", "Site", "Status"] + [c["label"] for c in sc],
            "rows": ([["Totals", "", ""] + [total_text(t[c["key"]]) for c in sc]]
                     + [[r["enrollment_id"], site_label(r["site"]), r["status"]] + [show(r["cells"][c["key"]]) for c in sc]
                        for r in rows]),
        })
    return out
