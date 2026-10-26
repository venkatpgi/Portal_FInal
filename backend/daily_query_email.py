"""Daily data-query email (PI 2026-10-25), 08:00 IST every day.

    cd /home/ubuntu/portal/backend && venv/bin/python daily_query_email.py [--dry-run] [--only EMAIL] [--force]

Who gets what:
  - Site PI and Site Scientist: their own site.
  - Overall Project Scientist (and Global Scientist) and the Global PI
    (superadmin): one email covering all sites.
Each email lists queries new in the last 24 h, overdue (red, 7 days past
due), and resolved / confirmed correct in the last 24 h, with open counts,
plus the site summary's urgent safety items (W1, W3, W9, W10).
It is sent on quiet days too: "nil to report" is itself the report (PI).

Content is the query text, which carries IDs, numbers and dates only
(data_checks.py: no names, CR or phone numbers). Runs the checks first so
the email reflects this morning's data. One send per IST day: each send is
written to the audit log (action EMAIL, table daily_query_email; a --only
test is EMAIL_TEST and does not count) and a
second run the same day skips unless --force. Mail goes out only where
SES_SENDER_EMAIL is set (the trial server; the training site has none).

--dry-run  build every email, print recipients and counts, send nothing,
           write the HTML to /tmp/daily_query_email_<scope>.html
--only     send only to this address (its own email is used as the template;
           used for the first live test)
"""
from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape

logging.basicConfig(level=logging.WARNING)

from audit_service import record_audit  # noqa: E402
from data_checks import CHECKS_BY_ID, OPEN_STATES, colour, run_checks  # noqa: E402
from db import SessionLocal  # noqa: E402
from deps import (ROLE_GLOBAL_SCIENTIST, ROLE_PROJECT_SCIENTIST, ROLE_SITE_PI,  # noqa: E402
                  ROLE_SITE_SCIENTIST, ROLE_SUPERADMIN)
from email_service import send_email  # noqa: E402
from models import AuditLog, DataQuery, User  # noqa: E402
import sae_config  # noqa: E402
import site_summary  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))
SITE_ROLES = {ROLE_SITE_PI, ROLE_SITE_SCIENTIST}
CENTRAL_ROLES = {ROLE_SUPERADMIN, ROLE_PROJECT_SCIENTIST, ROLE_GLOBAL_SCIENTIST}
ALL_SITES = "ALL"
PORTAL_URL = "https://portaltrial.in/data-queries"
LIST_LIMIT = 40          # rows per section; the rest are counted, not listed
AUDIT_TABLE = "daily_query_email"
REPORT_SITES = ["PGIMER", "GMCH", "GMCH-A", "AMC", "AFMC", "IOG"]   # all-sites table lists every site


def _ist(dt) -> str:
    if not dt:
        return "—"
    return dt.replace(tzinfo=timezone.utc).astimezone(IST).strftime("%d %b %Y %H:%M")


def _site_display(site: str) -> str:
    return sae_config.site_for(site or "").get("display", site or "—")


RECORD_LABELS = {"ga_check": "Gestation Log #", "birth_log": "Birth log #"}


def _record(q) -> str:
    return f"{RECORD_LABELS.get(q.record_type, '')}{q.record_key or '—'}"


def recipients(db) -> dict[str, list[str]]:
    """{site name or ALL_SITES: [email, ...]} for active users with an email."""
    out: dict[str, list[str]] = defaultdict(list)
    for u in db.query(User).filter(User.is_active.is_(True)).all():
        email = (u.email or "").strip()
        role = (u.role or "").lower()
        if not email:
            continue
        if role in CENTRAL_ROLES:
            out[ALL_SITES].append(email)
        elif role in SITE_ROLES and u.site_name:
            out[u.site_name].append(email)
    return {k: sorted(set(v)) for k, v in out.items()}


def _sections(queries, now, since):
    new = [q for q in queries if q.status in OPEN_STATES and q.first_seen_at and q.first_seen_at >= since]
    red = [q for q in queries if q.status in OPEN_STATES and colour(q, now) == "red"]
    closed = [q for q in queries if q.status not in OPEN_STATES
              and max(filter(None, [q.resolved_at, q.confirmed_at]), default=None) is not None
              and max(filter(None, [q.resolved_at, q.confirmed_at])) >= since]
    open_ = [q for q in queries if q.status in OPEN_STATES]
    counts = {
        "open": len(open_), "new": len(new), "red": len(red),
        "amber": sum(colour(q, now) == "amber" for q in open_),
        "awaiting_signoff": sum(q.status == "awaiting_signoff" for q in open_),
        "closed": len(closed),
    }
    return counts, new, red, closed


def _table(title, rows, show_site, empty, kind):
    head = f'<h3 style="margin:22px 0 8px;font-size:15px;color:#00132c;">{escape(title)} ({len(rows)})</h3>'
    if not rows:
        return head + f'<p style="margin:0;color:#64748b;font-size:13px;">{escape(empty)}</p>'
    th = ('<th style="text-align:left;padding:6px 8px;border-bottom:2px solid #e2e8f0;font-size:12px;'
          'color:#475569;">{}</th>')
    cols = (["Site"] if show_site else []) + ["Record", "Query", "Area",
                                              "Raised" if kind != "closed" else "Closed"]
    html = [head, '<table style="border-collapse:collapse;width:100%;font-size:13px;">',
            "<tr>" + "".join(th.format(c) for c in cols) + "</tr>"]
    td = '<td style="padding:6px 8px;border-bottom:1px solid #eef2f7;vertical-align:top;">{}</td>'
    for q in rows[:LIST_LIMIT]:
        check = CHECKS_BY_ID.get(q.check_id)
        when = q.first_seen_at if kind != "closed" else (q.confirmed_at or q.resolved_at)
        status = ""
        if kind == "closed":
            status = " (confirmed correct)" if q.status == "confirmed_correct" else " (fixed)"
        cells = ([escape(_site_display(q.site_name))] if show_site else []) + [
            escape(_record(q)),
            f"<strong>{escape(q.title or '')}</strong>{escape(status)}"
            + (f'<br><span style="color:#475569;">{escape(q.detail)}</span>' if q.detail and kind != "closed" else ""),
            escape(check.area if check else "—"),
            escape(_ist(when)),
        ]
        html.append("<tr>" + "".join(td.format(c) for c in cells) + "</tr>")
    html.append("</table>")
    if len(rows) > LIST_LIMIT:
        html.append(f'<p style="margin:6px 0 0;color:#64748b;font-size:12px;">…and {len(rows) - LIST_LIMIT} more '
                    f'in the portal.</p>')
    return "".join(html)


def build_email(db, scope: str, now: datetime) -> tuple[str, str, dict]:
    """(subject, html, counts) for one site or ALL_SITES."""
    since = now - timedelta(hours=24)
    qy = db.query(DataQuery)
    if scope != ALL_SITES:
        qy = qy.filter(DataQuery.site_name == scope)
    queries = qy.order_by(DataQuery.site_name, DataQuery.due_at.asc().nulls_last(), DataQuery.id).all()
    counts, new, red, closed = _sections(queries, now, since)
    all_sites = scope == ALL_SITES
    try:   # site summary rules W1, W3, W9, W10 (PI 2026-10-26); the query email goes out regardless
        urgent = site_summary.urgent_items(db, scope)
        urgent_html = site_summary.rule_table(urgent, all_sites)
    except Exception:
        logging.exception("urgent safety items failed for %s", scope)
        db.rollback()
        urgent, urgent_html = [], ('<p style="margin:0;color:#b91c1c;font-size:13px;">Could not be checked today; '
                                   'see the site summary in the portal.</p>')
    counts["urgent"] = len(urgent)
    where = "All sites" if all_sites else _site_display(scope)
    day = now.replace(tzinfo=timezone.utc).astimezone(IST).strftime("%d %b %Y")
    nil = not (counts["new"] or counts["red"] or counts["closed"] or counts["open"] or counts["urgent"])
    subject = (f"PORTAL data queries — {where} — {day}: "
               + ("nil to report" if nil else
                  (f"{counts['urgent']} URGENT safety, " if counts["urgent"] else "")
                  + f"{counts['new']} new, {counts['red']} overdue, {counts['open']} open"))

    tiles = [("Open", counts["open"], "#0f172a"), ("New (24 h)", counts["new"], "#0369a1"),
             ("Overdue (red)", counts["red"], "#b91c1c"), ("Ageing (amber)", counts["amber"], "#b45309"),
             ("Awaiting sign-off", counts["awaiting_signoff"], "#6d28d9"),
             ("Closed (24 h)", counts["closed"], "#15803d")]
    tile_html = "".join(
        f'<td style="padding:10px 12px;border:1px solid #e2e8f0;border-radius:8px;text-align:center;">'
        f'<div style="font-size:22px;font-weight:700;color:{c};">{n}</div>'
        f'<div style="font-size:11px;color:#64748b;">{escape(label)}</div></td>'
        for label, n, c in tiles)

    by_site = ""
    if all_sites:
        per = defaultdict(lambda: {"open": 0, "red": 0, "new": 0})
        for q in queries:
            if q.status in OPEN_STATES:
                per[q.site_name]["open"] += 1
                per[q.site_name]["red"] += colour(q, now) == "red"
        for q in new:
            per[q.site_name]["new"] += 1
        sites = sorted(set(REPORT_SITES) | set(per), key=lambda s: (s not in REPORT_SITES, REPORT_SITES.index(s) if s in REPORT_SITES else 0, s or ""))
        rows = "".join(
            f'<tr><td style="padding:5px 8px;border-bottom:1px solid #eef2f7;">{escape(_site_display(s))}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #eef2f7;text-align:right;">{per[s]["open"]}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #eef2f7;text-align:right;">{per[s]["new"]}</td>'
            f'<td style="padding:5px 8px;border-bottom:1px solid #eef2f7;text-align:right;color:#b91c1c;">'
            f'{per[s]["red"]}</td></tr>'
            for s in sites)
        by_site = ('<h3 style="margin:22px 0 8px;font-size:15px;color:#00132c;">By site</h3>'
                   '<table style="border-collapse:collapse;font-size:13px;min-width:320px;">'
                   '<tr><th style="text-align:left;padding:5px 8px;">Site</th><th style="padding:5px 8px;">Open</th>'
                   '<th style="padding:5px 8px;">New</th><th style="padding:5px 8px;">Overdue</th></tr>'
                   f'{rows}</table>')

    nil_line = ('<p style="margin:16px 0 0;padding:10px 12px;background:#f0fdf4;border:1px solid #bbf7d0;'
                'border-radius:8px;color:#166534;font-size:14px;"><strong>Nil to report.</strong> No open, new, '
                'overdue or closed data queries and no urgent safety items.</p>') if nil else ""

    html = f"""<!doctype html><html><body style="margin:0;padding:0;background:#f8fafc;">
<div style="max-width:760px;margin:0 auto;padding:20px 16px;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
<div style="background:#00132c;color:#fff;padding:14px 18px;border-radius:10px 10px 0 0;">
  <div style="font-size:12px;opacity:.8;">PORTAL Trial — daily data-query report</div>
  <div style="font-size:18px;font-weight:700;margin-top:2px;">{escape(where)} · {escape(day)}</div>
</div>
<div style="background:#fff;border:1px solid #e2e8f0;border-top:0;padding:16px 18px;border-radius:0 0 10px 10px;">
  <p style="margin:0 0 12px;font-size:13px;color:#475569;">Covers the 24 hours to {escape(_ist(now))} IST.
  Queries are raised automatically by the portal's data checks.</p>
  <table style="border-collapse:separate;border-spacing:6px;width:100%;"><tr>{tile_html}</tr></table>
  {nil_line}
  <h3 style="margin:22px 0 8px;font-size:15px;color:#b91c1c;">Urgent safety items ({len(urgent)})</h3>
  <p style="margin:0 0 6px;color:#64748b;font-size:12px;">Serious AE not reviewed for SAE, severe brain scan not
  in Form H, death without an SAE report, SAE reporting deadline. Full list in the twice-weekly site summary.</p>
  {urgent_html}
  {by_site}
  {_table("New in the last 24 hours", new, all_sites, "None.", "new")}
  {_table("Overdue (red: 7 days past due)", red, all_sites, "None.", "red")}
  {_table("Closed in the last 24 hours", closed, all_sites, "None.", "closed")}
  <p style="margin:22px 0 0;"><a href="{PORTAL_URL}" style="display:inline-block;background:#00132c;color:#fff;
  text-decoration:none;padding:10px 16px;border-radius:8px;font-size:14px;">Open data queries in the portal</a></p>
  <p style="margin:18px 0 0;font-size:11px;color:#94a3b8;">IDs only: this email carries no names, CR or phone
  numbers. Sent every day at 08:00 IST to Site PIs and Site Scientists (own site), the Project Scientist and the
  Global PI (all sites). Do not reply; this mailbox is not read.</p>
</div></div></body></html>"""
    return subject, html, counts


def already_sent_today(db, now: datetime) -> bool:
    start_ist = now.replace(tzinfo=timezone.utc).astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_ist.astimezone(timezone.utc).replace(tzinfo=None)
    return db.query(AuditLog).filter(AuditLog.table_name == AUDIT_TABLE, AuditLog.action == "EMAIL",
                                     AuditLog.created_at >= start_utc).first() is not None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    db = SessionLocal()
    try:
        try:
            if not args.dry_run:   # a dry run only reads
                run_checks(db)
        except Exception:   # the email still goes out on yesterday's queries
            logging.exception("data checks failed before the daily email")
            db.rollback()
        now = datetime.utcnow()
        live = not args.dry_run and not args.only
        if live and not args.force and already_sent_today(db, now):
            print("daily query email: already sent today, skipped")
            return 0
        plan = recipients(db)
        failed, sent = 0, []
        for scope in sorted(plan, key=lambda s: (s != ALL_SITES, s)):
            to = plan[scope]
            if args.only:
                if args.only not in to:
                    continue
                to = [args.only]
            subject, html, counts = build_email(db, scope, now)
            if args.dry_run:
                path = f"/tmp/daily_query_email_{scope}.html"
                with open(path, "w") as fh:
                    fh.write(html)
                print(f"[dry run] {scope}: {len(to)} recipient(s); {subject}  -> {path}")
                continue
            ok = send_email(to, subject, html)
            failed += not ok
            sent.append({"scope": scope, "recipients": len(to), "ok": ok, **counts})
            print(f"{scope}: {'sent' if ok else 'FAILED'} to {len(to)}; {subject}")
        if sent:
            # A --only test is logged as EMAIL_TEST so it does not stop the 08:00 send.
            record_audit(db, user_id=None, username="system", action="EMAIL_TEST" if args.only else "EMAIL",
                         table_name=AUDIT_TABLE, new_values={"emails": sent})
            db.commit()
        return 1 if failed else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
