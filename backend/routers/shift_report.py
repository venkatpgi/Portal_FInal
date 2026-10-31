"""GET /shift-report: the twice-daily report for a site's WhatsApp group
(shift_report.py). Any staff member of a site, own site; Global PI and the
central scientists pick a site. PTS3 has no reports. Nothing by arm, IDs only.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from audit_service import record_audit
from db import get_db
from deps import ROLE_TECH_SUPPORT, get_current_user
from models import User
from routers.reports import ALL_SITES, CENTRAL
import shift_report

router = APIRouter(prefix="/shift-report", tags=["Twice-daily report"])


def _site(user: User, site: str | None) -> str:
    role = (user.role or "").lower()
    if role in CENTRAL:
        if site not in ALL_SITES:
            raise HTTPException(status_code=422, detail="Pick a site.")
        return site
    if role != ROLE_TECH_SUPPORT and user.site_name:
        return user.site_name
    raise HTTPException(status_code=403, detail="The twice-daily report is for site staff.")


@router.get("")
def get_shift_report(site: str | None = None, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    return shift_report.build(db, _site(current_user, site))


@router.get("/pdf")
def get_shift_report_pdf(site: str | None = None, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    report = shift_report.build(db, _site(current_user, site))
    record_audit(db, user_id=current_user.id, username=current_user.username, action="EXPORT",
                 table_name="shift_report", new_values={"site": report["site"], "babies": len(report["babies"])})
    db.commit()
    name = shift_report.file_name(report)
    return Response(shift_report.render_pdf(report), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
