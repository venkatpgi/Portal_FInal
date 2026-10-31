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
from types import SimpleNamespace

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
