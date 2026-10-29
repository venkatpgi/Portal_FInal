"""Row-by-row merge for list forms saved as a whole (AE form events, SAE
list rows), so two people editing the same baby's form do not undo each
other (PI 2026-10-29).

Found live: on 01-B-001 the Global PI corrected Hyperthermia grade 3 -> 2;
a nurse who had opened the AE form before that saved her own edit to another
row 34 minutes later, and her save put grade 3 back. The page sends the whole
list, so the last save silently won.

Every row carries a stable `row_id`. A web save sends the rows as it loaded
them (`base`) with the rows it is saving (`mine`); the server compares both
with what is stored now (`current`), row by row:
  - a row only I changed            -> mine
  - a row only someone else changed -> theirs (kept)
  - a row both changed differently  -> conflict (409, nothing saved)
  - a row someone else added        -> kept; a row I added -> appended
  - a row I deleted that nobody else changed -> deleted; deleted by them and
    untouched by me -> stays deleted; deleted on one side, edited on the
    other -> conflict
A save without `base` (mobile app, older page) or with rows from before row
ids existed replaces the list as before.
"""
from __future__ import annotations

import uuid


def new_row_id() -> str:
    return uuid.uuid4().hex[:12]


def with_row_ids(rows) -> list:
    """Copy of rows, each with a row_id (missing ones assigned)."""
    out = []
    for r in rows or []:
        if isinstance(r, dict):
            r = dict(r)
            if not r.get("row_id"):
                r["row_id"] = new_row_id()
        out.append(r)
    return out


def _norm(row, keys) -> tuple:
    return tuple(str((row or {}).get(k) or "").strip() for k in keys)


class MergeConflict(Exception):
    def __init__(self, rows):
        super().__init__(", ".join(rows))
        self.rows = rows   # labels of the rows both sides changed


def merge_rows(base, current, mine, keys, label=lambda r: "a row"):
    """Merged list (see module docstring). `keys` are the fields compared;
    `label(row)` names a row in a conflict. Raises MergeConflict."""
    mine = [r for r in (mine or []) if isinstance(r, dict)]
    if base is None:
        return with_row_ids(mine)          # mobile app / older page: as before
    current = [r for r in (current or []) if isinstance(r, dict)]
    base = [r for r in base if isinstance(r, dict)]
    if any(not r.get("row_id") for r in base + current):
        return with_row_ids(mine)          # nothing to align on: as before
    b = {r["row_id"]: r for r in base}
    m = {r["row_id"]: r for r in mine if r.get("row_id")}
    if [_norm(r, keys) + (r["row_id"],) for r in base] == [_norm(r, keys) + (r["row_id"],) for r in current]:
        return with_row_ids(mine)          # nobody else saved in between
    out, conflicts, seen = [], [], set()
    for c in current:
        rid = c["row_id"]
        seen.add(rid)
        if rid not in b:                   # added by someone else
            out.append(c)
            continue
        base_v, cur_v = _norm(b[rid], keys), _norm(c, keys)
        if rid in m:
            mine_v = _norm(m[rid], keys)
            if mine_v == base_v or mine_v == cur_v:
                out.append(c)              # I did not change it (or made the same change)
            elif cur_v == base_v:
                out.append(m[rid])         # only I changed it
            else:
                conflicts.append(label(c))
        elif cur_v != base_v:              # I deleted it, they edited it
            conflicts.append(label(c))
    for r in mine:
        rid = r.get("row_id")
        if rid in seen:
            continue
        if rid and rid in b:               # they deleted it
            if _norm(r, keys) != _norm(b[rid], keys):
                conflicts.append(label(r))
            continue
        out.append(r)                      # added by me
    if conflicts:
        raise MergeConflict(conflicts)
    return with_row_ids(out)
