"""Form Y rules (PI 2026-10-31), shared by the save endpoints, the Word report
and the site summary.

Causality (items 19, 20): not asked on an Initial report, optional on a
Follow-up, required on a Final. An Initial report saved before this rule keeps
what it holds.

Death: one report per SAE. A fatal SAE is reported once, as "<SAE>, Death"
(worked out when shown, the diagnosis stays as typed). A death from an SAE
already reported is a Follow-up or Final of that SAE. An unrelated death is a
separate report, so a report marked fatal must be about the death.
"""
from datetime import date, timedelta
from types import SimpleNamespace

from ae_terms import term_of

CAUSALITY_FIELDS = ("causality", "sponsor_causality")
CAUSALITY_PENDING = "To be provided in the final report"


def is_fatal(sae) -> bool:
    """Fatal SAE: "Death" ticked under seriousness OR outcome "Fatal"."""
    seriousness = sae.seriousness if isinstance(sae.seriousness, list) else []
    return "Death" in seriousness or (getattr(sae, "outcome", None) or "") == "Fatal"


def event_title(diagnosis, fatal: bool) -> str:
    """The event as reported: "NEC, Death" for a fatal SAE."""
    dx = (diagnosis or "").strip()
    if not fatal or "death" in dx.lower():
        return dx
    return f"{dx}, Death" if dx else "Death"


def list_row(sae) -> dict:
    """The SAE list row for a saved Initial report (its deadlines start here)."""
    linked = sae.linked_ae if isinstance(sae.linked_ae, dict) else {}
    start = (sae.onset_datetime or sae.date_of_death or sae.report_date or "")[:10]
    return {"sae": event_title(sae.diagnosis, is_fatal(sae)), "definition_no": linked.get("definition_no"),
            "start_date": start or None, "end_date": (sae.end_datetime or "")[:10] or None}


def _base(name) -> str:
    return (name or "").lower().replace(", death", "").strip()


def filled_rows(rows) -> list:
    return [r for r in rows or [] if isinstance(r, dict) and any(v for k, v in r.items() if k != "row_id")]


def on_list(rows, row: dict) -> bool:
    """Already listed: same event name, or the same name before ", Death" was added."""
    return any(_base(r.get("sae")) == _base(row["sae"]) for r in filled_rows(rows))


def add_to_list(rows, row: dict) -> list:
    """rows with this report's event: a draft "Death" row takes the event's name."""
    out = filled_rows(rows)
    if on_list(out, row):
        return out
    for r in out:
        if _base(r.get("sae")) == "death":
            return [{**x, "sae": row["sae"]} if x is r else x for x in out]
    return [*out, row]


DETAIL_REPORT_DAYS = 14
WARN_DAYS = 3


def _day(v):
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def fourteen_day_items(rows, today: date) -> list[dict]:
    """SAE list rows whose 14-day report is due within WARN_DAYS or overdue. The
    report date is the list's "14 days" field (column notify_10d, once labelled
    10 days)."""
    out = []
    for r in filled_rows(rows):
        start = _day(r.get("start_date"))
        if not start or str(r.get("notify_10d") or "").strip():
            continue
        due = start + timedelta(days=DETAIL_REPORT_DAYS)
        if today >= due - timedelta(days=WARN_DAYS):
            out.append({"sae": r.get("sae") or "SAE", "due": due, "overdue": today > due})
    return out


def mark_14_day(rows, record) -> list | None:
    """A saved Follow-up or Final report fills its row's 14-day date. None if no change."""
    if record.report_type not in ("Follow-up", "Final") or not _day(record.report_date):
        return None
    name = _base(record.diagnosis)
    changed = False
    out = []
    for r in rows or []:
        if isinstance(r, dict) and name and _base(r.get("sae")) == name and not str(r.get("notify_10d") or "").strip():
            r = {**r, "notify_10d": str(record.report_date)[:10]}
            changed = True
        out.append(r)
    return out if changed else None


def unreported_sae(events, reports) -> list[str]:
    """AE rows answered Converted to SAE = Yes with no Form Y report for them."""
    def keys(x):
        return {k for k in (term_of(x), _base(x.get("description"))) if k}

    filed = set()
    fatal = False
    for r in reports or []:
        if not (r.diagnosis or "").strip():
            continue
        fatal = fatal or is_fatal(r)
        filed |= keys({"description": r.diagnosis})
        if isinstance(r.linked_ae, dict):
            filed |= keys(r.linked_ae)
    out = []
    for e in events or []:
        if not isinstance(e, dict) or str(e.get("converted_to_sae") or "").strip() != "Yes":
            continue
        name = (e.get("description") or e.get("definition_no") or "AE").strip()
        if keys(e) & filed or (fatal and "death" in name.lower()):
            continue
        out.append(" ".join(name.split()))
    return out


def apply_rules(payload: dict, old=None) -> str | None:
    """Fix up a Form Y payload before saving; returns a refusal message or None.
    old: the saved report on an update."""
    fatal = is_fatal(SimpleNamespace(seriousness=payload.get("seriousness"), outcome=payload.get("outcome")))
    if fatal and payload.get("death_from_event") is False:
        return ("This report is marked as a death, but the death did not come from this SAE. Remove Death and "
                "Fatal here, and file a separate SAE report for the death.")
    if not fatal:
        payload["death_from_event"] = None

    report_type = payload.get("report_type")
    if report_type == "Initial":
        for f in CAUSALITY_FIELDS:
            payload[f] = getattr(old, f, None)
    elif report_type == "Final":
        missing = [label for f, label in (("causality", "Causality (item V)"),
                                          ("sponsor_causality", "Causality by Sponsor (item 20)"))
                   if not (payload.get(f) or "").strip()]
        if missing:
            return f"A Final report needs {' and '.join(missing)}."
    return None
