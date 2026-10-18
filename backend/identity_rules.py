"""CR number and name rules, enforced by the server (PI 2026-10-18).

The web pages already filtered what could be typed, but nothing stopped a
CR number of the wrong length (or a husband's name in the CR box) reaching
the database from another client or an older page: 23 such CRs were found
in the logs. These checks run on every save where a CR or a mother's /
husband's name is entered: Form A, Form B, Form C, the Gestation Log, the
Log of All Births and the AE form.

CR number (per site; the same patterns as utils/maternalUid.js):
  PGIMER  exactly 12 digits
  AMC     serial/year, e.g. 123/2026
  others  digits only ("-" or "/" allowed as separators), no letters
Names: no digits (twins are recorded with the Birth type / Birth order
fields, not "T1" / "T2" in the name).

Blank values are allowed here (whether a field is required is the form's
business). A value already stored is not re-checked when it is saved again
unchanged, so an old record with a bad value can still be edited; changing
it means entering a valid one.
"""
from __future__ import annotations

import re
from typing import Mapping, Optional

from fastapi import HTTPException

NAME_FIELD_LABELS = {
    "mother_name": "Mother's name",
    "mother_first_name": "Mother's first name",
    "mother_surname": "Mother's surname",
    "mother_name_first": "Mother's first name",
    "mother_name_surname": "Mother's surname",
    "husband_name": "Husband's name",
    "husband_first_name": "Husband's first name",
    "husband_surname": "Husband's surname",
}
CR_FIELDS = ("maternal_uid", "mother_uid")


def site_code(site) -> str:
    raw = str(site or "").strip().lower()
    if raw.startswith("pgimer"):
        return "PGIMER"
    if raw == "amc" or raw.startswith("amc "):
        return "AMC"
    return str(site or "").strip().upper()


def _clean(value) -> str:
    return str(value if value is not None else "").strip()


def cr_error(site, value) -> Optional[str]:
    v = _clean(value)
    if not v:
        return None
    code = site_code(site)
    if code == "PGIMER":
        return None if re.fullmatch(r"\d{12}", v) else "CR number must be exactly 12 digits (numbers only) at PGIMER"
    if code == "AMC":
        return None if re.fullmatch(r"\d+/\d{4}", v) else "CR number must be serial/year, e.g. 123/2026, at AMC"
    return None if re.fullmatch(r"\d+(?:[-/]\d+)*", v) else "CR number can contain numbers only"


def name_error(label: str, value) -> Optional[str]:
    v = _clean(value)
    if v and re.search(r"\d", v):
        return f"{label} cannot contain numbers"
    return None


def identity_errors(site, fields: Mapping, existing: Optional[Mapping] = None) -> list[str]:
    """Problems with the CR / name values in `fields` (any of the keys in
    CR_FIELDS / NAME_FIELD_LABELS; others ignored). `existing` = the values
    stored now; a value equal to its stored one is not checked."""
    existing = existing or {}
    out = []
    for key, value in fields.items():
        if key not in CR_FIELDS and key not in NAME_FIELD_LABELS:
            continue
        if _clean(value) and _clean(value) == _clean(existing.get(key)):
            continue
        err = cr_error(site, value) if key in CR_FIELDS else name_error(NAME_FIELD_LABELS[key], value)
        if err:
            out.append(err)
    return out


def require_valid_identity(site, fields: Mapping, existing: Optional[Mapping] = None) -> None:
    errors = identity_errors(site, fields, existing)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(dict.fromkeys(errors)) + ".")


def stored_values(record, keys) -> dict:
    """{key: record.key} for the keys the record has (None record -> {})."""
    if record is None:
        return {}
    return {k: getattr(record, k) for k in keys if hasattr(record, k)}
