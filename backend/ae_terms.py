"""Which NAESS term an AE-form row is, and whether a detected candidate is
already on the form (PI 2026-10-26).

The AE form's "No." is free text: staff type the term key, the CDISC / MedDRA
codes ("C154928 | 10082059"), "NA" or nothing, and the description in their
own words ("Patent  Ductus  Arteriosus ", "Apnea"). The scan's candidates use
the term key, so matching on key + start date (as the page did) added every
hand-typed AE again. Here a row is matched to a term by key, then code, then
name (ignoring case, spacing, a bracketed abbreviation and a leading
"Neonatal" / "Infantile").
"""
from __future__ import annotations

import re
from datetime import date

from ae_reference import AE_DEFINITIONS

_CODE_RE = re.compile(r"\b(?:C\d{5,}|\d{8})\b")

# Codes staff use on the AE form for terms whose definition text quotes none
# (seen on PGIMER forms, Oct 2026).
EXTRA_CODES = {
    "apnea": {"C154938", "10077322"},
    "feeding_intolerance": {"C154944", "10076042"},
}

# Same event if the start dates are this close (or either is missing).
SAME_EVENT_DAYS = 3


def _norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def name_keys(text) -> set[str]:
    """Spellings a term name or a typed description may match on."""
    out = set()
    for part in re.split(r"\s*/\s*", str(text or "")):
        bare = re.sub(r"\([^)]*\)", " ", part)
        for v in (part, bare):
            n = _norm(v)
            if n:
                out.add(n)
                out.add(re.sub(r"^(neonatal|infantile) ", "", n))
        out.update(_norm(a) for a in re.findall(r"\(([^)]*)\)", part) if _norm(a))
    return out


_CODES = {slug: set(_CODE_RE.findall(d.get("definition") or "")) | EXTRA_CODES.get(slug, set())
          for slug, d in AE_DEFINITIONS.items()}
_NAMES: dict[str, str] = {}
for _slug, _d in AE_DEFINITIONS.items():
    for _k in name_keys(_d["name"]):
        _NAMES.setdefault(_k, _slug)


def term_of(e) -> str | None:
    """The NAESS term key of an AE row or candidate, or None."""
    no = str((e or {}).get("definition_no") or "").strip()
    if no in AE_DEFINITIONS:
        return no
    codes = set(_CODE_RE.findall(no))
    if codes:
        for slug, known in _CODES.items():
            if codes & known:
                return slug
    for k in sorted(name_keys((e or {}).get("description")), key=len, reverse=True):
        if k in _NAMES:
            return _NAMES[k]
    return None


def _day(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def duplicate_of(candidate: dict, rows: list) -> int | None:
    """1-based number of the AE-form row that already records this candidate:
    same term, and its start within SAME_EVENT_DAYS of the row's start..end
    (or a start date missing on either side). None if it is new."""
    term = term_of(candidate)
    if not term:
        return None
    c_start = _day(candidate.get("start_date"))
    for i, r in enumerate(rows or [], start=1):
        if not isinstance(r, dict) or term_of(r) != term:
            continue
        r_start = _day(r.get("start_date"))
        if c_start is None or r_start is None:
            return i
        r_end = _day(r.get("end_date")) or r_start
        if (r_start - c_start).days <= SAME_EVENT_DAYS and (c_start - r_end).days <= SAME_EVENT_DAYS:
            return i
    return None
