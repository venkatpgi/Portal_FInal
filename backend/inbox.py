"""In-app notification inbox (tablet). IDs only, split by login.

Nurses see ward work (Form Y, cranial USG due, queries to correct, Form I
visits). Site scientists and PIs see review items (death SAE outstanding,
watch-list W1/W3/W9/W10/W11, a query digest, follow-up bookings). The same
event can appear for more than one role with different wording.

Urgency:
  now    must be done this shift (badge count)
  today  due today / this window
  later  coming this week

Items clear themselves when the underlying check or form no longer fires
(no separate “mark as read”). Training and live share this GET; nothing is
emailed from here. Form F closed/missed windows stay on the site summary (M2)
and are not listed as data queries.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from deps import (ROLE_GLOBAL_SCIENTIST, ROLE_NURSE, ROLE_PROJECT_SCIENTIST,
                  ROLE_SITE_PI, ROLE_SITE_SCIENTIST, ROLE_SUPERADMIN, ROLE_TECH_SUPPORT)
from site_summary import REPORT_SITES

AUDIENCE_NURSE = "nurse"
AUDIENCE_SCIENTIST = "scientist"
AUDIENCE_PI = "pi"

NURSE_ROLES = {ROLE_NURSE, "deo"}
SCIENTIST_ROLES = {ROLE_SITE_SCIENTIST, ROLE_PROJECT_SCIENTIST, ROLE_GLOBAL_SCIENTIST}
PI_ROLES = {ROLE_SITE_PI, ROLE_SUPERADMIN}

WATCH_PI_SCI = {"W1", "W3", "W9", "W10", "W11"}

URGENCY_ORDER = {"now": 0, "today": 1, "later": 2}


def audience_for(role: str | None) -> str | None:
    r = (role or "").strip().lower()
    if r in NURSE_ROLES:
        return AUDIENCE_NURSE
    if r in SCIENTIST_ROLES:
        return AUDIENCE_SCIENTIST
    if r in PI_ROLES:
        return AUDIENCE_PI
    if r in ("monitor", "pii_officer"):
        return AUDIENCE_SCIENTIST
    return None


def followup_urgency(days_to_due: int, stage: str) -> str:
    if stage == "overdue" or (stage == "window" and days_to_due <= 0):
        return "now" if stage == "overdue" else "today"
    if days_to_due <= 2:
        return "today"
    return "later"


def death_copy(audience: str) -> tuple[str, str]:
    if audience == AUDIENCE_NURSE:
        return ("Death recorded. Complete Form Y within 24 hours.", "Open Form Y")
    if audience == AUDIENCE_PI:
        return ("Death SAE. 24-hour Form Y still outstanding.", "Open Form Y")
    return ("Death SAE. No Form Y report received yet.", "Open Form Y")


def enrollment_id_of(record_key: str | None) -> str | None:
    s = (record_key or "").strip()
    if re.match(r"^\d{2}-[A-D]-\d{3}$", s, re.I) or re.match(r"^\d{2}-\d{3,5}$", s):
        return s
    return None


def query_route(record_type: str | None) -> str:
    t = (record_type or "").lower()
    if t == "ga_check":
        return "gestation_log"
    if t == "birth_log":
        return "birth_log"
    if t in ("screening", "form_a"):
        return "form_a"
    if t in ("birth_resuscitation", "form_b", "birth"):
        return "form_b1"
    if t in ("cranial_usg", "form_f"):
        return "form_f"
    if t in ("study_outcomes", "form_i"):
        return "form_i"
    if t in ("range", "minimal_monitoring"):
        return "helper_dms"
    if t in ("maternal", "form_c"):
        return "form_c"
    return "form_h"


def item(*, key: str, urgency: str, kind: str, title: str, message: str, action: str,
         route: str, enrollment_id: str | None = None, screening_id: str | None = None,
         site: str | None = None, query_id: int | None = None) -> dict:
    return {
        "id": key,
        "urgency": urgency,
        "kind": kind,
        "title": title,
        "message": message,
        "action": action,
        "route": route,
        "enrollment_id": enrollment_id,
        "screening_id": screening_id,
        "site": site,
        "query_id": query_id,
    }


def _sites(user) -> list[str]:
    role = (user.role or "").lower()
    if role in {ROLE_SUPERADMIN, ROLE_PROJECT_SCIENTIST, ROLE_GLOBAL_SCIENTIST}:
        return list(REPORT_SITES)
    if (user.site_name or "").strip():
        return [user.site_name]
    return []


def feed(db, user, now: datetime | None = None) -> dict:
    """GET /notifications payload. Empty for roles with no inbox."""
    from clinical_time import clinical_now
    from data_checks import OPEN_STATES, colour
    from models import DataQuery
    from site_summary import _iso, _load, evaluate, last_snapshot, open_cranial_windows
    from ops_tasks import iter_form_tasks
    import followup_due as fd

    audience = audience_for(user.role)
    if audience is None or (user.role or "").lower() == ROLE_TECH_SUPPORT:
        return {"audience": None, "badge_now": 0, "items": []}
    sites = _sites(user)
    if not sites:
        return {"audience": audience, "badge_now": 0, "items": []}

    now = now or clinical_now()
    today = now.date()
    _, prev = last_snapshot(db)
    out: list[dict] = []

    raw = _load(db, sites, now)
    for b in raw:
        eid = b["enrollment_id"]
        site = b["site"]
        sid = b.get("screening_id")
        r = evaluate(b, today, now, prev.get(eid))
        for code, text in r["watch"]:
            if code == "W9":
                msg, act = death_copy(audience)
                out.append(item(key=f"death:{eid}", urgency="now", kind="death_sae",
                                title=eid, message=msg, action=act, route="form_y",
                                enrollment_id=eid, screening_id=sid, site=site))
            elif code in WATCH_PI_SCI and audience != AUDIENCE_NURSE:
                overdue = "overdue" in text.lower() or "24-hour" in text
                urg = "now" if overdue or (code in ("W9", "W11") and audience == AUDIENCE_PI) else "today"
                route = "form_y" if code in ("W9", "W10", "W11") else ("form_h" if code == "W3" else "ae")
                out.append(item(key=f"watch:{code}:{eid}:{text[:40]}", urgency=urg, kind="watch",
                                title=eid, message=text, action="Open record", route=route,
                                enrollment_id=eid, screening_id=sid, site=site))
            elif code in ("W10", "W11") and audience == AUDIENCE_NURSE:
                overdue = "overdue" in text.lower() or "24-hour" in text
                out.append(item(key=f"sae:{eid}:{text[:40]}", urgency="now" if overdue else "today",
                                kind="sae_deadline", title=eid, message=text,
                                action="Open Form Y" if "Form Y" in text or code == "W11" else "Open SAE list",
                                route="form_y" if code == "W11" else "sae_list",
                                enrollment_id=eid, screening_id=sid, site=site))

        if audience == AUDIENCE_NURSE and not b.get("end_date"):
            scans = [_iso((s or {}).get("scanDate")) for s in (b.get("scan_entries") or [])]
            due = open_cranial_windows(
                b.get("ga_days"), b.get("birth_weight"), b.get("dob"), today, scans, b.get("end_date"))
            for d in due:
                window = d.get("window") or d.get("label") or "window open"
                out.append(item(key=f"usg:{eid}:{d.get('key')}", urgency="today", kind="cranial_usg",
                                title=eid,
                                message=f"Cranial USG due. {window}.",
                                action="Open Form F", route="form_f",
                                enrollment_id=eid, screening_id=sid, site=site))

        if audience == AUDIENCE_NURSE:
            for code, text in r["missed"]:
                if code == "M1":
                    out.append(item(key=f"logs:{eid}", urgency="today", kind="logs_missing",
                                    title=eid, message=text, action="Open daily logs",
                                    route="helper_dms", enrollment_id=eid, screening_id=sid, site=site))
                elif code == "M7":
                    out.append(item(key=f"formc:{eid}", urgency="today", kind="form_c_missing",
                                    title=eid, message="Form C missing.", action="Open Form C",
                                    route="form_c", enrollment_id=eid, screening_id=sid, site=site))

    if audience == AUDIENCE_NURSE:
        for key, site, ref, detail in iter_form_tasks(db, now):
            if key != "delivered_no_form_b" or site not in sites:
                continue
            out.append(item(key=f"formb:{ref}", urgency="today", kind="form_b_missing",
                            title=ref, message="Delivered: Form B not filled.",
                            action="Open Form B", route="form_b1",
                            screening_id=ref, site=site))

    qs = (db.query(DataQuery).filter(DataQuery.site_name.in_(sites),
                                     DataQuery.status.in_(OPEN_STATES)).all())
    utc = datetime.utcnow()
    since = utc - timedelta(hours=24)
    red = [q for q in qs if colour(q, utc) == "red"]
    new = [q for q in qs if q.first_seen_at and q.first_seen_at >= since]
    if audience == AUDIENCE_NURSE:
        for q in qs[:20]:
            eid = enrollment_id_of(q.record_key)
            urg = "now" if colour(q, utc) == "red" else "today"
            out.append(item(key=f"query:{q.id}", urgency=urg, kind="data_query",
                            title=eid or (q.record_key or "Query"),
                            message=q.title or "Open data query.",
                            action="Open form", route=query_route(q.record_type),
                            enrollment_id=eid, screening_id=None if eid else q.record_key,
                            site=q.site_name, query_id=q.id))
    else:
        n_red, n_new = len(red), len(new)
        if n_red or n_new or qs:
            urg = "now" if (audience == AUDIENCE_PI and n_red) else "today"
            bits = []
            if n_new:
                bits.append(f"{n_new} new in the last 24 hours")
            if n_red:
                bits.append(f"{n_red} red")
            if not bits:
                bits.append(f"{len(qs)} open")
            msg = "Data queries: " + ", ".join(bits) + "."
            if audience == AUDIENCE_PI:
                msg += " Daily digest is also emailed at 08:00."
            out.append(item(key="queries:digest", urgency=urg, kind="query_digest",
                            title=sites[0] if len(sites) == 1 else "All sites",
                            message=msg, action="Open data queries", route="data_queries",
                            site=sites[0] if len(sites) == 1 else None))

    for r in fd.coming_up(fd.collect(db, sites, today)):
        eid, wk = r["enrollment_id"], r["checkpoint"]
        urg = followup_urgency(r["days_to_due"], r["stage"])
        when = fd.when_text(r)
        if audience == AUDIENCE_NURSE:
            msg = f"{wk} wk Form I visit {when}. Confirm the family or record Form I."
            act = "Open Form I"
        else:
            msg = f"{wk} wk follow-up {when}."
            act = "Open Form I"
        out.append(item(key=f"fu:{eid}:{wk}", urgency=urg, kind="followup",
                        title=eid, message=msg, action=act, route="form_i",
                        enrollment_id=eid, site=r.get("site")))

    try:
        import followup_booking as fb
        for cal in fb.all_calendars(db, sites, today):
            if fb.is_complete(cal["rows"]):
                continue
            eid = cal["enrollment_id"]
            if audience == AUDIENCE_NURSE:
                msg = "Follow-up dates not booked. Complete H12.6 before the baby leaves."
                urg, act, route = "today", "Open Form H", "form_h"
            else:
                msg = "Follow-up calendar incomplete after a live discharge."
                urg, act, route = "today", "Open Form H", "form_h"
            out.append(item(key=f"fu-book:{eid}", urgency=urg, kind="followup_unbooked",
                            title=eid, message=msg, action=act, route=route,
                            enrollment_id=eid, site=cal.get("site")))
    except Exception:
        pass

    seen = set()
    uniq = []
    for it in out:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        uniq.append(it)
    uniq.sort(key=lambda it: (URGENCY_ORDER.get(it["urgency"], 9), it.get("title") or ""))
    badge = sum(1 for it in uniq if it["urgency"] == "now")
    return {"audience": audience, "badge_now": badge, "items": uniq[:80]}
