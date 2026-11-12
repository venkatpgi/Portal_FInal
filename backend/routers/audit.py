"""Audit log read API — global roles (all sites) and site_pi (own site only)."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, aliased

from audit_service import utc_now_naive
from db import get_db
from deps import ROLE_SITE_PI, get_current_user, is_global
from models import (
    AuditLog,
    AdverseEvents,
    BirthResuscitation,
    BlenderStudySummary,
    CranialUltrasound,
    ExternalHospitalAssessment,
    MaternalDetails,
    MRIBrainAssessment,
    NeonatalMorbidities,
    NICUAdmission,
    PostnatalDay1,
    ROPScreening,
    SAEList,
    SAEReport,
    Screening,
    StudyOutcomes,
    User,
)
from schemas import AuditLogOut

# Keep in sync with dashboard.py ALL_SITES (site filter validation).
_VALID_SITES = frozenset({"PGIMER", "GMCH", "IOG", "AFMC", "GMCH-A", "AMC"})

router = APIRouter(prefix="/audit", tags=["Audit"])


def _can_view_audit(user: User) -> bool:
    return is_global(user) or (user.role or "").lower() == ROLE_SITE_PI


def _parse_date_param(value: str | None, end_of_day: bool = False) -> datetime | None:
    if not value:
        return None
    try:
        d = date.fromisoformat(value[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date: {value}")
    if end_of_day:
        return datetime.combine(d, time(23, 59, 59, 999999), tzinfo=timezone.utc)
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


def _audit_site_column():
    """Resolve site at query time: prefer screening_id join, else enrollment_id → screenings."""
    scr_by_sid = aliased(Screening)
    scr_by_enr = aliased(Screening)
    return func.coalesce(scr_by_sid.site_name, scr_by_enr.site_name), scr_by_sid, scr_by_enr


@router.get("/", response_model=list[AuditLogOut])
def list_audit_logs(
    table_name: str | None = None,
    enrollment_id: str | None = None,
    screening_id: str | None = None,
    action: str | None = None,
    site: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_view_audit(current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view audit logs")

    site_col, scr_by_sid, scr_by_enr = _audit_site_column()
    changer = aliased(User)

    query = (
        db.query(AuditLog, site_col.label("resolved_site"), changer)
        .outerjoin(scr_by_sid, scr_by_sid.screening_id == AuditLog.screening_id)
        .outerjoin(
            scr_by_enr,
            and_(
                AuditLog.enrollment_id.isnot(None),
                AuditLog.enrollment_id != "",
                scr_by_enr.enrollment_id == AuditLog.enrollment_id,
            ),
        )
        .outerjoin(changer, changer.id == AuditLog.user_id)
    )
    utc = utc_now_naive()
    when_utc = case(
        (AuditLog.created_at > utc, AuditLog.created_at - timedelta(hours=5, minutes=30)),
        else_=AuditLog.created_at,
    )
    query = query.order_by(when_utc.desc(), AuditLog.id.desc())

    if is_global(current_user):
        if site and site in _VALID_SITES:
            query = query.filter(site_col == site)
    else:
        pi_site = (current_user.site_name or "").strip()
        if not pi_site:
            return []
        query = query.filter(site_col == pi_site)

    if table_name:
        query = query.filter(AuditLog.table_name == table_name)
    if enrollment_id:
        query = query.filter(AuditLog.enrollment_id == enrollment_id)
    if screening_id:
        query = query.filter(AuditLog.screening_id == screening_id)
    if action:
        query = query.filter(AuditLog.action == action.upper())

    dt_from = _parse_date_param(date_from)
    dt_to = _parse_date_param(date_to, end_of_day=True)
    if dt_from:
        query = query.filter(AuditLog.created_at >= dt_from)
    if dt_to:
        query = query.filter(AuditLog.created_at <= dt_to)

    rows = query.offset(skip).limit(limit).all()
    out: list[AuditLogOut] = []
    for log, resolved_site, changer_row in rows:
        out.append(
            AuditLogOut(
                id=log.id,
                user_id=log.user_id,
                username=_person_display_name(log, changer_row),
                action=log.action,
                table_name=log.table_name,
                record_id=log.record_id,
                enrollment_id=log.enrollment_id,
                screening_id=log.screening_id,
                old_values=log.old_values,
                new_values=log.new_values,
                created_at=log.created_at,
                site=resolved_site,
            )
        )
    return out


def _person_display_name(log: AuditLog, user_row: Optional[User]) -> Optional[str]:
    """Prefer the staff member's full name over their login id."""
    if user_row is not None:
        name = (user_row.full_name or user_row.username or "").strip()
        if name:
            return name
    fallback = (log.username or "").strip()
    return fallback or None


_FORM_LABELS = {
    "screenings": "Form A — Screening",
    "birth_resuscitation": "Form B — Birth & Resuscitation",
    "maternal_details": "Form C — Maternal Details",
    "postnatal_day1": "Form D — Postnatal Day 1",
    "nicu_admission": "Form E — NICU Admission",
    "cranial_ultrasound": "Form F — Cranial USG",
    "rop_screening": "Form G — ROP Screening",
    "neonatal_morbidities": "Form H — Neonatal Morbidities",
    "study_outcomes": "Form I — Study Outcomes",
    "external_hospital_assessments": "Form J — External Hospital",
    "mri_brain_assessments": "Form K — MRI Brain",
    "blender_study_summaries": "Form L — Blender Summary",
    "minimal_monitoring_day_logs": "Daily Monitoring Sheet (DMS)",
    "resp_cv_neuro_day_logs": "Helper 2 — Resp/CV/Neuro",
    "fio2_auc_logs": "Helper 3 — FiO₂ Logging",
    "infect_gi_hema_day_logs": "Helper 4 — Infect/GI/Hema",
    "metab_renal_vasc_eye_day_logs": "Helper 5 — Metab/Renal/Eye",
    "sae_reports": "Form Y — SAE Report",
    "adverse_events": "Adverse Events",
    "sae_list": "SAE Listing",
}

# Latest INSERT/UPDATE is shown when a form was saved before SAVE-action logging.
_FALLBACK_MODELS = (
    (BirthResuscitation, "birth_resuscitation"),
    (MaternalDetails, "maternal_details"),
    (PostnatalDay1, "postnatal_day1"),
    (NICUAdmission, "nicu_admission"),
    (CranialUltrasound, "cranial_ultrasound"),
    (ROPScreening, "rop_screening"),
    (NeonatalMorbidities, "neonatal_morbidities"),
    (StudyOutcomes, "study_outcomes"),
    (ExternalHospitalAssessment, "external_hospital_assessments"),
    (MRIBrainAssessment, "mri_brain_assessments"),
    (BlenderStudySummary, "blender_study_summaries"),
    (AdverseEvents, "adverse_events"),
    (SAEReport, "sae_reports"),
    (SAEList, "sae_list"),
)


def _is_explicit_save(log: AuditLog) -> bool:
    if (log.action or "").upper() == "SAVE":
        return True
    new_values = log.new_values or {}
    old_values = log.old_values or {}
    return new_values.get("explicitly_saved") is True and old_values.get("explicitly_saved") is not True


@router.get("/patient")
def patient_save_history(
    screening_id: str,
    enrollment_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Saves for one participant. Any user who can open that screening may read it.
    Form A Save clicks are action SAVE. Other forms were logged as INSERT/UPDATE
    until SAVE-on-explicit-save; those still appear (latest per form if needed)."""
    screening = (
        db.query(Screening)
        .filter(Screening.screening_id == screening_id, Screening.is_deleted.isnot(True))
        .first()
    )
    if not screening:
        raise HTTPException(status_code=404, detail="Screening not found")
    if not is_global(current_user) and (screening.site_name or "") != (current_user.site_name or ""):
        raise HTTPException(status_code=403, detail="Not authorized for this site")

    filters = [AuditLog.screening_id == screening_id]
    # every baby of this mother (twins: babies.py)
    eids = {screening.enrollment_id, enrollment_id} | {
        e for (e,) in db.query(BirthResuscitation.enrollment_id)
        .filter(BirthResuscitation.screening_id == screening_id).all()}
    eids.discard(None)
    eids.discard("")
    if eids:
        filters.append(AuditLog.enrollment_id.in_(eids))
    form_tables = list(_FORM_LABELS.keys())
    logs = (
        db.query(AuditLog)
        .filter(or_(*filters))
        .filter(or_(AuditLog.action == "SAVE", AuditLog.table_name.in_(form_tables)))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(500)
        .all()
    )
    saves = [log for log in logs if _is_explicit_save(log)]
    have_save_tables = {log.table_name for log in saves}

    def _log_when(log):
        t = log.created_at
        if t is None:
            return datetime.min
        return t.replace(tzinfo=None) if getattr(t, "tzinfo", None) else t

    # Forms saved before SAVE-action logging: keep the latest INSERT/UPDATE.
    latest_other = {}
    for log in logs:
        table = log.table_name
        if table in have_save_tables or table == "screenings":
            continue
        if table not in _FORM_LABELS:
            continue
        if (log.action or "").upper() not in ("INSERT", "UPDATE", "SAVE"):
            continue
        prev = latest_other.get(table)
        if prev is None or _log_when(log) > _log_when(prev) or (
            _log_when(log) == _log_when(prev) and (log.id or 0) > (prev.id or 0)
        ):
            latest_other[table] = log
    saves.extend(latest_other.values())
    # A new Save click also writes UPDATE. Keep the SAVE row and drop the twin UPDATE.
    save_marks = {
        (log.user_id, log.screening_id, log.created_at.replace(microsecond=0) if log.created_at else None)
        for log in saves
        if (log.action or "").upper() == "SAVE"
    }
    deduped = []
    for log in saves:
        stamp = log.created_at.replace(microsecond=0) if log.created_at else None
        if (log.action or "").upper() != "SAVE" and (log.user_id, log.screening_id, stamp) in save_marks:
            continue
        deduped.append(log)

    user_ids = {log.user_id for log in deduped if log.user_id}
    handles = {log.username for log in deduped if log.username}
    handles.update(
        h for h in (screening.updated_by, screening.created_by) if h
    )
    by_id = {}
    by_username = {}
    if user_ids or handles:
        clauses = []
        if user_ids:
            clauses.append(User.id.in_(user_ids))
        if handles:
            clauses.append(User.username.in_(handles))
        found = db.query(User).filter(or_(*clauses)).all() if clauses else []
        for user in found:
            name = (user.full_name or "").strip()
            if not name:
                continue
            by_id[user.id] = name
            if user.username:
                by_username[user.username] = name

    def person_name(log) -> str:
        return (
            by_id.get(log.user_id)
            or by_username.get(log.username or "")
            or "—"
        )

    rows = []
    for log in sorted(
        deduped,
        key=lambda log: (_log_when(log), log.id or 0),
        reverse=True,
    ):
        form = (log.new_values or {}).get("form") or _FORM_LABELS.get(log.table_name) or log.table_name
        rows.append({
            "id": log.id,
            "form": form,
            "saved_by": person_name(log),
            "saved_at": log.created_at.isoformat() if log.created_at else None,
        })
    shown_tables = {log.table_name for log in deduped}
    if "screenings" not in shown_tables and screening.explicitly_saved and screening.updated_at:
        who = by_username.get(screening.updated_by or "") or by_username.get(screening.created_by or "") or "—"
        rows.append({
            "id": 0,
            "form": "Form A — Screening",
            "saved_by": who,
            "saved_at": screening.updated_at.isoformat(),
        })
    eid_list = list(eids)
    for model, table in _FALLBACK_MODELS:
        if table in shown_tables:
            continue
        rec = None
        if eid_list and hasattr(model, "enrollment_id"):
            rec = db.query(model).filter(model.enrollment_id.in_(eid_list)).first()
        if rec is None and hasattr(model, "screening_id"):
            rec = db.query(model).filter(model.screening_id == screening_id).first()
        if rec is None:
            continue
        when = getattr(rec, "updated_at", None) or getattr(rec, "created_at", None)
        if when is None:
            continue
        who_handle = getattr(rec, "updated_by", None) or getattr(rec, "created_by", None)
        if who_handle:
            handles.add(who_handle)
        who = by_username.get(who_handle or "") or who_handle or "—"
        rows.append({
            "id": f"fallback-{table}-{getattr(rec, 'id', 0)}",
            "form": _FORM_LABELS[table],
            "saved_by": who,
            "saved_at": when.isoformat() if hasattr(when, "isoformat") else str(when),
        })
    rows.sort(key=lambda r: r.get("saved_at") or "", reverse=True)
    return rows
