"""Follow-up calendar on Form H (followup_booking.py, PI 2026-11-19).

GET  /followup-bookings/{eid}            the calendar from the saved Form H
PUT  /followup-bookings/{eid}            book dates / reasons (site staff)
GET  /followup-bookings/{eid}/slip.pdf   parent slip (baby's name only with PII rights)
GET  /followup-bookings/clinic/{site}    where families come, whom they call
PUT  /followup-bookings/clinic/{site}    Site PI / Site Scientist of that site, Global PI
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from audit_service import record_audit
from babies import screening_for_enrollment
from clinical_time import clinical_today
from db import get_db
from deps import (ROLE_SITE_PI, ROLE_SITE_SCIENTIST, ensure_same_site, get_current_user, is_read_only,
                  is_superadmin)
from models import BirthResuscitation, FollowupClinic, User
from pii_service import can_view_pii_for_site
import followup_booking as fb

router = APIRouter(prefix="/followup-bookings", tags=["Follow-up calendar"])


def _site_of(db, eid: str, user: User) -> str:
    screening = screening_for_enrollment(db, eid)
    if not screening:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    ensure_same_site(screening.site_name, user)
    return screening.site_name


def _clinic_out(c, site) -> dict:
    return {"site_name": site, "place": c.place if c else None, "days_times": c.days_times if c else None,
            "phone": c.phone if c else None,
            "weekdays": [fb.WEEKDAYS[i] for i in fb.parse_weekdays(c.weekdays if c else None)]}


@router.get("/clinic/{site}")
def get_clinic(site: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_same_site(site, current_user)
    return _clinic_out(db.get(FollowupClinic, site), site)


@router.put("/clinic/{site}")
def put_clinic(site: str, data: dict = Body(...), db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    ensure_same_site(site, current_user)
    role = (current_user.role or "").lower()
    if not (is_superadmin(current_user) or role in (ROLE_SITE_PI, ROLE_SITE_SCIENTIST)):
        raise HTTPException(status_code=403, detail="The Site PI or a Site Scientist sets the clinic details.")
    c = db.get(FollowupClinic, site)
    if c is None:
        c = FollowupClinic(site_name=site)
        db.add(c)
    for k in ("place", "days_times", "phone"):
        v = (data.get(k) or "").strip()
        setattr(c, k, v[:300] or None)
    days = data.get("weekdays")
    if isinstance(days, list):
        days = ",".join(str(x) for x in days)
    c.weekdays = ",".join(fb.WEEKDAYS[i] for i in fb.parse_weekdays(days)) or None
    c.updated_by = current_user.username
    db.commit()
    return _clinic_out(c, site)


@router.get("/{enrollment_id}")
def get_calendar(enrollment_id: str, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    site = _site_of(db, enrollment_id, current_user)
    out = fb.calendar(db, enrollment_id, clinical_today())
    out["clinic"] = _clinic_out(db.get(FollowupClinic, site), site)
    return out


@router.put("/{enrollment_id}")
def put_calendar(enrollment_id: str, items: list[dict] = Body(..., embed=True), db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    site = _site_of(db, enrollment_id, current_user)
    if is_read_only(current_user):
        raise HTTPException(status_code=403, detail="Read-only account.")
    try:
        out = fb.save(db, enrollment_id, items, current_user.username, clinical_today())
    except fb.BookingError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    out["clinic"] = _clinic_out(db.get(FollowupClinic, site), site)
    return out


@router.get("/{enrollment_id}/slip.pdf")
def get_slip(enrollment_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    site = _site_of(db, enrollment_id, current_user)
    cal = fb.calendar(db, enrollment_id, clinical_today())
    if not cal["applies"]:
        raise HTTPException(status_code=422, detail=cal["why"])
    name = None
    if can_view_pii_for_site(current_user, site):
        from site_summary import pii_names
        screening = screening_for_enrollment(db, enrollment_id)
        br = db.query(BirthResuscitation).filter(BirthResuscitation.enrollment_id == enrollment_id).first()
        twin = br is not None and (br.baby_number or 1) > 1
        names = pii_names(db, [screening.screening_id], [enrollment_id] if twin else [])
        if twin:
            mother = (names.get(screening.screening_id) or {}).get("mother")
            name = (names.get(enrollment_id) or {}).get("baby") or (f"Baby of {mother}" if mother else None)
        else:
            name = (names.get(screening.screening_id) or {}).get("baby")
    from daily_query_email import _site_display
    pdf = fb.slip_pdf(cal, db.get(FollowupClinic, site), name, _site_display(site))
    record_audit(db, user_id=current_user.id, username=current_user.username, action="EXPORT",
                 table_name="followup_slip", enrollment_id=enrollment_id, new_values={"with_name": bool(name)})
    db.commit()
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="followup_{enrollment_id}.pdf"'})
