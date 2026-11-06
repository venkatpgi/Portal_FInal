"""Report builder (PI 2026-10-24): pick columns from any form, filter, download CSV.

Who: Global PI (superadmin) and the Overall Project Scientist see all sites
(optionally one); Site PI and Site Scientist their own site only. Nurses and
technical support: no access (deps.TECH_SUPPORT_DENIED_PREFIXES).

What: one row per Form A (screened woman / her baby). Every row starts with
site, screening ID and enrollment (randomisation) number. Columns come only
from FORMS below -- a fixed server-side list, never SQL from the browser.
Forms with one row per baby are joined on screening_id (A, B) or
enrollment_id (C-J); if a table ever holds two rows for one baby the latest
(highest id) is used. Day-by-day logs are not offered (many rows per baby).

Never in a report (PI 2026-10-24: IDs only):
  - participant identity: names, CR / UID / admission numbers, phone,
    address, email, signatures (PII_WORDS + pii_service field lists);
  - anything that could unblind: delivery-room FiO2 minute values
    (study_outcomes fio2_0..fio2_10), Form K (MRI subset) and Form L
    (blender summaries) are not offered at all.

Downloads are written to the audit trail (action EXPORT, table "report").
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import JSON, Boolean, select
from sqlalchemy.orm import Session

from audit_service import record_audit
from db import get_db
from deps import (ROLE_GLOBAL_SCIENTIST, ROLE_PROJECT_SCIENTIST, ROLE_SITE_PI, ROLE_SITE_SCIENTIST,
                  ROLE_SUPERADMIN, get_current_user)
from models import Base, User
from participant_counts import COUNT_KEYS, members, scoped_screenings, stage_items
from patient_stage import stage_payload
from report_labels import label as column_label
from pii_service import (BIRTH_PII_FIELDS, MATERNAL_PII_FIELDS, NICU_PII_FIELDS, POSTNATAL_PII_FIELDS,
                         SCREENING_PII_FIELDS)
from trial_dates import trial_start

router = APIRouter(prefix="/reports", tags=["Reports"])

CENTRAL = {ROLE_SUPERADMIN, ROLE_PROJECT_SCIENTIST, ROLE_GLOBAL_SCIENTIST}
SITE_ROLES = {ROLE_SITE_PI, ROLE_SITE_SCIENTIST}
ALL_SITES = ["PGIMER", "GMCH", "IOG", "AFMC", "GMCH-A", "AMC"]

# (form key, label, table, join column)
FORMS = [
    ("A", "Form A — Screening", "screenings", "screening_id"),
    ("B", "Form B — Birth & resuscitation", "birth_resuscitation", "screening_id"),
    ("C", "Form C — Maternal details", "maternal_details", "enrollment_id"),
    ("D", "Form D — Postnatal day 1", "postnatal_day1", "enrollment_id"),
    ("E", "Form E — NICU admission", "nicu_admission", "enrollment_id"),
    ("F", "Form F — Cranial USG", "cranial_usg_records", "enrollment_id"),
    ("G", "Form G — ROP screening", "rop_screening", "enrollment_id"),
    ("H", "Form H — Neonatal morbidities", "neonatal_morbidities", "enrollment_id"),
    ("I", "Form I — Outcomes", "study_outcomes", "enrollment_id"),
    ("J", "Form J — External hospital outcomes", "external_hospital_assessments", "enrollment_id"),
]
FORMS_BY_KEY = {f[0]: f for f in FORMS}

PII_FIELDS = frozenset(SCREENING_PII_FIELDS + BIRTH_PII_FIELDS + MATERNAL_PII_FIELDS
                       + POSTNATAL_PII_FIELDS + NICU_PII_FIELDS)
# A column is identity if any "_"-separated word of its name is one of these
# (word match, so fluid_bolus is kept although it contains "uid").
PII_WORDS = frozenset({"name", "names", "contact", "phone", "mobile", "address", "email", "uid",
                       "aadhaar", "signature", "image", "photo", "pincode", "landmark", "cr"})
CLINICAL_DESPITE_WORDS = frozenset({"aed_name"})   # anti-epileptic drug, Form H
BLINDED_COLUMNS = {"study_outcomes": re.compile(r"^fio2_\d+$")}
# Row keys and bookkeeping; the IDs are always the first three report columns.
SKIP_COLUMNS = frozenset({"id", "is_deleted", "screening_id", "enrollment_id", "site_name"})

ID_HEADERS = ["site", "screening_id", "enrollment_id"]
ID_LABELS = ["Site", "Screening ID", "Enrollment (randomisation) number"]
HEADINGS = ("both", "variable", "english")   # CSV headings: "Birth weight (B_birth_weight)" / code / English
PREVIEW_ROWS = 50
MAX_COLUMNS = 300


def _scope_sites(user: User, site: str | None) -> list[str]:
    role = (user.role or "").lower()
    if role in CENTRAL:
        if site:
            if site not in ALL_SITES:
                raise HTTPException(status_code=422, detail=f"Unknown site {site!r}")
            return [site]
        return list(ALL_SITES)
    if role in SITE_ROLES and user.site_name:
        return [user.site_name]
    raise HTTPException(status_code=403, detail="Reports are for the Global PI, Project Scientist, Site PIs and Site Scientists.")


def _offered(table_name: str, col) -> bool:
    name = col.name
    if name in SKIP_COLUMNS or name in PII_FIELDS or "admission_number" in name or "admission_no" in name:
        return False
    if PII_WORDS & set(name.split("_")) and name not in CLINICAL_DESPITE_WORDS:
        return False
    blinded = BLINDED_COLUMNS.get(table_name)
    return not (blinded and blinded.match(name))


def _kind(col) -> str:
    if isinstance(col.type, Boolean):
        return "yes/no"
    if isinstance(col.type, JSON):
        return "list"
    try:
        py = col.type.python_type
    except NotImplementedError:
        return "text"
    if py in (int, float):
        return "number"
    if py in (date, datetime, time):
        return "date"
    return "text"


def catalogue() -> list[dict]:
    out = []
    for key, label, table_name, _ in FORMS:
        table = Base.metadata.tables[table_name]
        fields = [{"id": f"{key}.{c.name}", "column": c.name, "header": f"{key}_{c.name}",
                   "label": column_label(key, c.name), "kind": _kind(c)}
                  for c in table.columns if _offered(table_name, c)]
        out.append({"form": key, "label": label, "fields": fields})
    return out


def _field_index():
    return {f["id"]: (form["form"], f["column"], f["header"], f["label"])
            for form in catalogue() for f in form["fields"]}


@router.get("/fields")
def get_fields(current_user: User = Depends(get_current_user)):
    """Columns a report may include, grouped by form, plus the row filters."""
    _scope_sites(current_user, None)
    return {
        "forms": catalogue(),
        "groups": [{"key": k} for k in COUNT_KEYS],
        "trial_start_date": trial_start().isoformat(),
    }


class ReportRequest(BaseModel):
    columns: list[str]
    site: str | None = None
    group: str | None = None          # a participant_counts tile, e.g. "randomised"
    screened_from: date | None = None
    screened_to: date | None = None
    trial_only: bool = False          # screened on or after trial_dates.trial_start()
    include_stage: bool = True
    headings: str = "both"            # one of HEADINGS
    # Keep a row only if each of these columns holds one of the values (PI
    # 2026-11-06). Values as shown in the report; BLANK for an empty cell.
    filters: dict[str, list[str]] = {}


BLANK = "(blank)"
MAX_VALUES = 300


def _filter_key(v) -> str:
    return BLANK if v == "" else str(v)


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (datetime, date, time)):
        return v.isoformat()
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return v


def build_report(db: Session, user: User, req: ReportRequest):
    """(variable headers, English labels, rows) for a report request; rows are lists of cell values."""
    sites = _scope_sites(user, req.site)
    if not req.columns:
        raise HTTPException(status_code=422, detail="Pick at least one column.")
    if len(req.columns) > MAX_COLUMNS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_COLUMNS} columns per report.")
    index = _field_index()
    unknown = [c for c in req.columns if c not in index]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Not available in reports: {', '.join(unknown[:5])}")
    if req.headings not in HEADINGS:
        raise HTTPException(status_code=422, detail=f"Unknown headings {req.headings!r}")
    if req.group and req.group not in COUNT_KEYS:
        raise HTTPException(status_code=422, detail=f"Unknown group {req.group!r}")
    filters = {c: {str(v) for v in vals} for c, vals in (req.filters or {}).items() if vals}
    bad = [c for c in filters if c not in index]
    if bad:
        raise HTTPException(status_code=422, detail=f"Not available in reports: {', '.join(bad[:5])}")

    rows = scoped_screenings(db, sites)
    start = trial_start() if req.trial_only else None
    if req.screened_from and (start is None or req.screened_from > start):
        start = req.screened_from

    def screened_on(r):
        dt = r.screening_datetime or r.created_at
        return dt.date() if dt else None

    if start or req.screened_to:
        rows = [r for r in rows if screened_on(r)
                and (not start or screened_on(r) >= start)
                and (not req.screened_to or screened_on(r) <= req.screened_to)]
    items = stage_items(db, rows)
    if req.group:
        keep = set(members(items)[req.group])
        items = [it for it in items if it[0].screening_id in keep]
    items.sort(key=lambda it: (it[0].site_name or "", it[0].screening_id or ""))

    by_form: dict[str, list[str]] = {}
    for c in dict.fromkeys(list(req.columns) + list(filters)):
        form, column = index[c][:2]
        by_form.setdefault(form, []).append(column)

    sids = [it[0].screening_id for it in items if it[0].screening_id]
    eids = [it[0].enrollment_id for it in items if it[0].enrollment_id]
    values: dict[str, dict[str, dict]] = {}
    for form, columns in by_form.items():
        _, _, table_name, join = FORMS_BY_KEY[form]
        table = Base.metadata.tables[table_name]
        keys = sids if join == "screening_id" else eids
        found: dict[str, dict] = {}
        if keys:
            stmt = (select(table.c[join], *(table.c[c] for c in columns))
                    .where(table.c[join].in_(keys)).order_by(table.c.id))
            for rec in db.execute(stmt).mappings():
                found[rec[join]] = dict(rec)   # ordered by id: the latest row wins
        values[form] = found

    headers = list(ID_HEADERS) + (["stage"] if req.include_stage else [])
    headers += [index[c][2] for c in dict.fromkeys(req.columns)]
    labels = list(ID_LABELS) + (["Stage"] if req.include_stage else [])
    labels += [index[c][3] for c in dict.fromkeys(req.columns)]
    def cell_of(r, c):
        form, column = index[c][:2]
        key = r.screening_id if FORMS_BY_KEY[form][3] == "screening_id" else r.enrollment_id
        return _cell((values[form].get(key) or {}).get(column))

    out = []
    for r, _, stage, _ in items:
        if any(_filter_key(cell_of(r, c)) not in allowed for c, allowed in filters.items()):
            continue
        line = [r.site_name, r.screening_id, r.enrollment_id or ""]
        if req.include_stage:
            line.append(stage_payload(stage)["label"])
        for c in dict.fromkeys(req.columns):
            line.append(cell_of(r, c))
        out.append(line)
    return headers, labels, out


def csv_headings(headers, labels, style):
    if style == "variable":
        return headers
    if style == "english":
        return labels
    return [f"{lab} ({code})" for code, lab in zip(headers, labels)]


@router.post("/values")
def column_values(req: ReportRequest, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    """Distinct values of one column (req.columns[0]) among the rows the other
    filters keep, with counts, for that column's filter list (PI 2026-11-06)."""
    if len(req.columns) != 1:
        raise HTTPException(status_code=422, detail="Ask for one column.")
    col = req.columns[0]
    others = {c: v for c, v in (req.filters or {}).items() if c != col}
    headers, _, rows = build_report(db, current_user, req.model_copy(
        update={"filters": others, "include_stage": False}))
    i = headers.index(_field_index()[col][2])
    counts: dict[str, int] = {}
    for line in rows:
        v = _filter_key(line[i])
        counts[v] = counts.get(v, 0) + 1
    out = sorted(counts.items(), key=lambda kv: (kv[0] == BLANK, -kv[1], kv[0]))
    return {"values": [{"value": v, "n": n} for v, n in out[:MAX_VALUES]], "more": len(out) > MAX_VALUES}


@router.post("/preview")
def preview_report(req: ReportRequest, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    headers, labels, rows = build_report(db, current_user, req)
    return {"headers": headers, "labels": labels, "rows": rows[:PREVIEW_ROWS], "total": len(rows)}


@router.post("/csv")
def download_report(req: ReportRequest, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    headers, labels, rows = build_report(db, current_user, req)
    record_audit(
        db,
        user_id=current_user.id,
        username=current_user.full_name or current_user.username,
        action="EXPORT",
        table_name="report",
        new_values={"columns": req.columns, "filters": req.model_dump(exclude={"columns"}, mode="json"),
                    "rows": len(rows)},
    )
    db.commit()
    buf = io.StringIO()
    buf.write("﻿")   # BOM so Excel reads UTF-8 (em dashes, Hindi text)
    w = csv.writer(buf)
    w.writerow(csv_headings(headers, labels, req.headings))
    w.writerows(rows)
    name = f"portal_report_{datetime.now():%Y%m%d_%H%M}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})
