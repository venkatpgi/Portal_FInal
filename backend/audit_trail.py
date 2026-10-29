"""Automatic audit trail for every form table (PI 2026-10-26).

Until now audit_log only had Form A (screenings, written by hand in main.py),
day-log override unlocks, data queries and emails: Forms B-L, the daily logs,
the AE form, Form Y and the SAE list left no trace of who changed what.

An after_flush listener on every ORM session writes one audit_log row per
inserted, updated or deleted object, in the same transaction as the change:
  INSERT  new_values = the saved columns
  UPDATE  old_values / new_values = only the columns that changed
  DELETE  old_values = the row as it was
The user comes from session.info["audit_user"], set by deps.get_current_user
for every request (web, mobile app, API); scripts are "system".

Never stored: participant identity. Encrypted columns and the names, UIDs,
contacts, addresses, annual number and signature images below are written
as "[redacted]" (the audit row still shows that they changed). participant_pii
keeps only its keys.

Not covered: tables already audited elsewhere or written by the system
(SKIP_TABLES), and bulk query().update() / delete(), which bypass the ORM
(only the legacy /respiratory-log-bulk uses one).

Switched on by AUDIT_ALL_FORMS=1 in the backend env file (training 2026-10-26, trial 2026-10-28).
"""
from __future__ import annotations

import os

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from audit_service import _serialize
from crypto import EncryptedString

SKIP_TABLES = frozenset({
    "audit_log",
    "screenings",     # Form A: main.py already writes SAVE / INSERT / UPDATE / SOFT_DELETE rows
    "data_queries",   # raised and closed by the hourly checks; user actions audited in routers/data_queries.py
    "users",          # passwords, login bookkeeping
})
REDACT_COLUMNS = frozenset({
    "mother_name", "mother_name_first", "mother_name_surname", "mother_first_name", "mother_surname",
    "husband_name", "husband_first_name", "husband_surname", "baby_name",
    "baby_uid", "maternal_uid", "mother_uid", "hospital_admission_number", "annual_number",
    "mother_contact", "husband_contact", "contact_mother", "contact_husband", "reporter_contact",
    "address", "house", "city", "district", "state", "pincode", "landmark", "email", "email_address",
    "consent_signature_image", "pi_signature_image",
})
PII_KEYS = frozenset({"id", "enrollment_id", "screening_id", "site_name", "created_at", "updated_at"})
REDACTED = "[redacted]"


def enabled() -> bool:
    return os.getenv("AUDIT_ALL_FORMS", "").strip().lower() in ("1", "true", "yes")


def _redacted(table: str, col) -> bool:
    if table == "participant_pii":
        return col.name not in PII_KEYS
    return isinstance(col.type, EncryptedString) or col.name in REDACT_COLUMNS


def _value(table, col, v):
    if v is None:
        return None
    return REDACTED if _redacted(table, col) else _serialize(v)


def _changes(obj, action: str):
    """(old_values, new_values) for one flushed object."""
    state = inspect(obj)
    table = obj.__table__.name
    old, new = {}, {}
    for prop in state.mapper.column_attrs:
        col = prop.columns[0]
        if action in ("INSERT", "DELETE"):
            # state.dict: values already in memory (no SELECT inside the flush)
            v = state.dict.get(prop.key)
            if v is not None:
                (new if action == "INSERT" else old)[col.name] = _value(table, col, v)
            continue
        hist = state.attrs[prop.key].history
        if not hist.has_changes() or col.name == "updated_at":
            continue
        before = hist.deleted[0] if hist.deleted else None
        after = hist.added[0] if hist.added else None
        if _serialize(before) == _serialize(after):
            continue
        old[col.name] = _value(table, col, before)
        new[col.name] = _value(table, col, after)
    return old, new


def _after_flush(session: Session, flush_context) -> None:
    if not enabled():
        return
    from models import AuditLog
    user_id, username = session.info.get("audit_user") or (None, "system")
    rows = []
    for action, objs in (("INSERT", session.new), ("UPDATE", session.dirty), ("DELETE", session.deleted)):
        for obj in objs:
            table = getattr(getattr(obj, "__table__", None), "name", None)
            if not table or table in SKIP_TABLES:
                continue
            if action == "UPDATE" and not session.is_modified(obj, include_collections=False):
                continue
            old, new = _changes(obj, action)
            if action == "UPDATE" and not new and not old:
                continue
            st = inspect(obj)
            pk = [st.dict.get(st.mapper.get_property_by_column(c).key) for c in st.mapper.primary_key]
            rows.append({
                "user_id": user_id, "username": username, "action": action, "table_name": table,
                "record_id": (str(pk[0]) if len(pk) == 1 else str(tuple(pk))) if any(v is not None for v in pk) else None,
                "enrollment_id": getattr(obj, "enrollment_id", None)
                if isinstance(getattr(obj, "enrollment_id", None), str) else None,
                "screening_id": getattr(obj, "screening_id", None)
                if isinstance(getattr(obj, "screening_id", None), str) else None,
                "old_values": old or None, "new_values": new or None,
            })
    if rows:
        session.connection().execute(AuditLog.__table__.insert(), rows)


def install() -> None:
    """Register the listener once for every Session (idempotent)."""
    if not event.contains(Session, "after_flush", _after_flush):
        event.listen(Session, "after_flush", _after_flush)
