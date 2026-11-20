"""GET /notifications — role-filtered in-app inbox (tablet). IDs only."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from deps import get_current_user
from models import User
import inbox as inbox_mod

router = APIRouter(tags=["Notifications"])


@router.get("/notifications")
def get_notifications(db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    return inbox_mod.feed(db, current_user)
