"""Split DMS readings that hold more than one drug / product into one row
each (PI 2026-11-06: one drug per row, so a dose belongs to one drug and a
dose change is a new row).

    cd backend && venv/bin/python dms_split_drugs.py            # dry run: list what would change
    cd backend && venv/bin/python dms_split_drugs.py --apply    # write (audit rows via audit_trail)

Blocks: 5.1.C vasoactive drugs, 5.1.D PDA agent, 5.2.D postnatal steroids,
5.6.A transfusion products. Each new row keeps the reading's date, time and
saved-by stamps; the first keeps its id, the others get "<id>-2", "-3", ...
A field that belongs to one choice goes with it (PRBC volume -> PRBC,
steroid "Other" name -> Other); a dose recorded on a multi-drug reading cannot
be told apart, so it stays on the first row only (listed in the output).
"""
from __future__ import annotations

import argparse
import copy
import json

BLOCKS = {
    "cv_c": {"field": "vasoactive_drugs", "first_only": ("vasoactive_dose", "vasoactive_unit")},
    "cv_d": {"field": "pda_agent", "first_only": ("pda_dose",)},
    "resp_d": {"field": "postnatal_steroids", "first_only": ("steroid_dose",), "with": {"steroid_other": "Other"}},
    "heme_a": {"field": "transfusion_products", "first_only": ("transfusion_count",), "with": {"prbc_volume": "PRBC"}},
}


def _values(v) -> list[str]:
    if isinstance(v, list):
        return [x for x in v if x]
    return [x.strip() for x in str(v or "").split(",") if x.strip()]


def split_entries(entries: dict) -> tuple[dict, list[str]]:
    """(new entries, notes). Rows with one value or none are left as they are."""
    out = copy.deepcopy(entries or {})
    notes = []
    for block, cfg in BLOCKS.items():
        rows = out.get(block)
        if not isinstance(rows, list):
            continue
        new_rows = []
        for row in rows:
            vals = _values(row.get(cfg["field"])) if isinstance(row, dict) else []
            if len(vals) < 2:
                new_rows.append(row)
                continue
            dose_kept = [k for k in cfg["first_only"] if row.get(k) not in (None, "")]
            for n, val in enumerate(vals):
                r = dict(row)
                r[cfg["field"]] = [val]
                if n:
                    r["id"] = f"{row.get('id') or 'row'}-{n + 1}"
                    for k in cfg["first_only"]:
                        r.pop(k, None)
                for k, owner in cfg.get("with", {}).items():
                    if val != owner:
                        r.pop(k, None)
                new_rows.append(r)
            notes.append(f"{block} {row.get('time') or ''}: {', '.join(vals)} -> {len(vals)} rows"
                         + (f"; {', '.join(dose_kept)} kept on {vals[0]} only" if dose_kept else ""))
        out[block] = new_rows
    return out, notes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    import audit_trail
    from db import SessionLocal
    from models import MinimalMonitoringDayLog
    audit_trail.install()
    db = SessionLocal()
    changed = 0
    for m in db.query(MinimalMonitoringDayLog).order_by(MinimalMonitoringDayLog.enrollment_id,
                                                        MinimalMonitoringDayLog.record_date):
        raw = m.entries_json
        entries = json.loads(raw) if isinstance(raw, str) else (raw or {})
        new, notes = split_entries(entries)
        if not notes:
            continue
        changed += 1
        for x in notes:
            print(m.enrollment_id, m.record_date, x)
        if args.apply:
            m.entries_json = json.dumps(new) if isinstance(raw, str) else new
    if args.apply and changed:
        db.commit()
    print(f"{changed} sheet(s) {'changed' if args.apply else 'would change'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
