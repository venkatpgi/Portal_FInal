"""Data queries inbox API (Phase 1, PI 2026-10-15).

Who: Global PI (superadmin) and the Overall Project Scientist
(project_scientist / global_scientist) see and act on all sites; Site PI and
Site Scientist their own site. Nurses and technical support: no access.
Acting on a query (acknowledge, confirm correct, sign off) is oversight, so
the view-only Project Scientist may do it (deps.READ_ONLY_ALLOWED_WRITE_PREFIXES).
Checks that need a second sign-off: a site-level "confirm correct" waits for
the Project Scientist or Global PI. Every action is written to the audit log.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from audit_service import record_audit
from data_checks import CHECKS, CHECKS_BY_ID, OPEN_STATES, colour, run_checks
from db import get_db
from deps import (ROLE_GLOBAL_SCIENTIST, ROLE_NURSE, ROLE_PROJECT_SCIENTIST, ROLE_SITE_PI, ROLE_SITE_SCIENTIST,
                  ROLE_SUPERADMIN, get_current_user, is_superadmin)
from models import DataQuery, User

router = APIRouter(prefix="/data-queries", tags=["Data queries"])

CENTRAL = {ROLE_SUPERADMIN, ROLE_PROJECT_SCIENTIST, ROLE_GLOBAL_SCIENTIST}
SITE_ROLES = {ROLE_SITE_PI, ROLE_SITE_SCIENTIST}


def _role(user: User) -> str:
    return (user.role or "").lower()


def _scope(user: User) -> Optional[str]:
    """None = all sites; a site name = that site only. Others are refused."""
    role = _role(user)
    if role in CENTRAL:
        return None
    if role in SITE_ROLES and user.site_name:
        return user.site_name
    raise HTTPException(status_code=403, detail="Data queries are for Site PIs, scientists and the Global PI.")


def _get(db: Session, user: User, query_id: int) -> DataQuery:
    site = _scope(user)
    q = db.query(DataQuery).filter(DataQuery.id == query_id).first()
    if not q or (site is not None and q.site_name != site):
        raise HTTPException(status_code=404, detail="Query not found")
    return q


def _out(q: DataQuery, now: datetime) -> dict:
    check = CHECKS_BY_ID.get(q.check_id)
    return {
        "id": q.id, "check_id": q.check_id, "area": check.area if check else None,
        "site_name": q.site_name, "record_type": q.record_type, "record_key": q.record_key,
        "title": q.title, "detail": q.detail, "status": q.status, "colour": colour(q, now),
        "needs_second_signoff": bool(q.needs_second_signoff),
        "due_at": q.due_at.isoformat() if q.due_at else None,
        "first_seen_at": q.first_seen_at.isoformat() if q.first_seen_at else None,
        "resolved_at": q.resolved_at.isoformat() if q.resolved_at else None,
        "reopened_count": q.reopened_count or 0,
        "acknowledged_by": q.acknowledged_by, "confirmed_by": q.confirmed_by,
        "confirmed_reason": q.confirmed_reason, "signoff_by": q.signoff_by,
    }


def _audit(db, user, q, action, old):
    record_audit(db, user_id=user.id, username=user.username, action=action, table_name="data_queries",
                 record_id=q.id, old_values=old, new_values={"status": q.status, "check_id": q.check_id,
                                                              "record": f"{q.record_type}:{q.record_key}"})


@router.get("/checks")
def list_checks(current_user: User = Depends(get_current_user)):
    _scope(current_user)
    return [{"check_id": c.check_id, "area": c.area, "description": c.description,
             "second_signoff": c.second_signoff} for c in CHECKS]


@router.get("/")
def list_queries(
    status: str = Query("open", pattern="^(open|closed|all)$"),
    site: Optional[str] = None,
    record_key: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """status=open: open, acknowledged, awaiting sign-off. closed: resolved,
    confirmed correct. Sorted most overdue first."""
    scope = _scope(current_user)
    qy = db.query(DataQuery)
    if scope is not None:
        qy = qy.filter(DataQuery.site_name == scope)
    elif site:
        qy = qy.filter(DataQuery.site_name == site)
    if record_key:
        qy = qy.filter(DataQuery.record_key == record_key)
    if status == "open":
        qy = qy.filter(DataQuery.status.in_(OPEN_STATES))
    elif status == "closed":
        qy = qy.filter(~DataQuery.status.in_(OPEN_STATES))
    now = datetime.utcnow()
    rows = qy.order_by(DataQuery.due_at.asc().nulls_last(), DataQuery.id.asc()).limit(1000).all()
    return [_out(q, now) for q in rows]


@router.get("/for-record")
def for_record(
    keys: list[str] = Query(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Open queries on the records a form is showing, for the banner on that
    form. Also for nurses (their site), who otherwise have no inbox."""
    role = _role(current_user)
    keys = [k for k in keys if k][:10]
    if not keys:
        return []
    if role in CENTRAL:
        site = None
    elif role in SITE_ROLES | {ROLE_NURSE} and current_user.site_name:
        site = current_user.site_name
    else:
        return []
    qy = db.query(DataQuery).filter(DataQuery.status.in_(OPEN_STATES), DataQuery.record_key.in_(keys))
    if site is not None:
        qy = qy.filter(DataQuery.site_name == site)
    now = datetime.utcnow()
    return [{"id": q.id, "title": q.title, "detail": q.detail, "colour": colour(q, now), "status": q.status}
            for q in qy.order_by(DataQuery.due_at.asc().nulls_last()).all()]


@router.get("/summary")
def summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Open counts by site and colour, for the sidebar badge and dashboard."""
    scope = _scope(current_user)
    qy = db.query(DataQuery).filter(DataQuery.status.in_(OPEN_STATES))
    if scope is not None:
        qy = qy.filter(DataQuery.site_name == scope)
    now = datetime.utcnow()
    out = {"total": 0, "red": 0, "amber": 0, "awaiting_signoff": 0, "by_site": {}}
    for q in qy.all():
        c = colour(q, now)
        out["total"] += 1
        out[c] = out.get(c, 0) + 1
        out["awaiting_signoff"] += q.status == "awaiting_signoff"
        s = out["by_site"].setdefault(q.site_name or "-", {"total": 0, "red": 0, "amber": 0})
        s["total"] += 1
        if c in ("red", "amber"):
            s[c] += 1
    return out


@router.post("/{query_id}/acknowledge")
def acknowledge(query_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = _get(db, current_user, query_id)
    if q.status != "open":
        raise HTTPException(status_code=409, detail=f"Query is {q.status}, not open.")
    old = {"status": q.status}
    q.status, q.acknowledged_by, q.acknowledged_at = "acknowledged", current_user.username, datetime.utcnow()
    _audit(db, current_user, q, "QUERY_ACKNOWLEDGE", old)
    db.commit()
    return _out(q, datetime.utcnow())


class ConfirmBody(BaseModel):
    reason: str


@router.post("/{query_id}/confirm-correct")
def confirm_correct(query_id: int, body: ConfirmBody, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """The data is right although the rule fired. Needs a reason. For checks
    on the second sign-off list a site-level confirmation waits for the
    Project Scientist / Global PI; a central user's confirmation is final."""
    q = _get(db, current_user, query_id)
    reason = (body.reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=422, detail="Give a reason (at least 5 characters).")
    if q.status not in ("open", "acknowledged"):
        raise HTTPException(status_code=409, detail=f"Query is {q.status}.")
    old = {"status": q.status}
    now = datetime.utcnow()
    q.confirmed_by, q.confirmed_at, q.confirmed_reason = current_user.username, now, reason
    if q.needs_second_signoff and _role(current_user) not in CENTRAL:
        q.status = "awaiting_signoff"
    else:
        q.status = "confirmed_correct"
        if q.needs_second_signoff:
            q.signoff_by, q.signoff_at = current_user.username, now
    _audit(db, current_user, q, "QUERY_CONFIRM_CORRECT", old)
    db.commit()
    return _out(q, now)


@router.post("/{query_id}/signoff")
def signoff(query_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Second sign-off of a site-level 'confirmed correct' (Project Scientist / Global PI)."""
    if _role(current_user) not in CENTRAL:
        raise HTTPException(status_code=403, detail="Second sign-off is by the Overall Project Scientist or Global PI.")
    q = _get(db, current_user, query_id)
    if q.status != "awaiting_signoff":
        raise HTTPException(status_code=409, detail=f"Query is {q.status}, not awaiting sign-off.")
    old = {"status": q.status}
    q.status, q.signoff_by, q.signoff_at = "confirmed_correct", current_user.username, datetime.utcnow()
    _audit(db, current_user, q, "QUERY_SIGNOFF", old)
    db.commit()
    return _out(q, datetime.utcnow())


@router.post("/{query_id}/reject-confirmation")
def reject_confirmation(query_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Second reviewer disagrees: the query goes back to open."""
    if _role(current_user) not in CENTRAL:
        raise HTTPException(status_code=403, detail="Only the Overall Project Scientist or Global PI can do this.")
    q = _get(db, current_user, query_id)
    if q.status != "awaiting_signoff":
        raise HTTPException(status_code=409, detail=f"Query is {q.status}, not awaiting sign-off.")
    old = {"status": q.status, "confirmed_by": q.confirmed_by, "reason": q.confirmed_reason}
    q.status = "open"
    q.confirmed_by = q.confirmed_at = q.confirmed_reason = None
    _audit(db, current_user, q, "QUERY_SIGNOFF_REJECTED", old)
    db.commit()
    return _out(q, datetime.utcnow())


@router.post("/run")
def run_now(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Run every check now (Global PI only; the hourly timer does this too)."""
    if not is_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Global PI only.")
    return run_checks(db)
