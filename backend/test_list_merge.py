from list_merge import MergeConflict, merge_rows, with_row_ids

KEYS = ("description", "grade", "severity_desc")


def conflict(*args, **kw):
    try:
        merge_rows(*args, **kw)
    except MergeConflict as e:
        return e.rows
    return None


def rows(*specs):
    return [{"row_id": rid, "description": d, "grade": g, "severity_desc": ""} for rid, d, g in specs]


BASE = rows(("r14", "Hyperthermia", "3"), ("r16", "VAP", ""))


def test_01_b_001_case_keeps_both_edits():
    # PI saved grade 2 on row 14 while the nurse had the form open; she then edits row 16 only
    current = rows(("r14", "Hyperthermia", "2"), ("r16", "VAP", ""))
    mine = rows(("r14", "Hyperthermia", "3"), ("r16", "VAP", "3"))
    out = merge_rows(BASE, current, mine, KEYS)
    assert [(r["row_id"], r["grade"]) for r in out] == [("r14", "2"), ("r16", "3")]


def test_same_row_changed_by_both_is_refused():
    current = rows(("r14", "Hyperthermia", "2"), ("r16", "VAP", ""))
    mine = rows(("r14", "Hyperthermia", "1"), ("r16", "VAP", ""))
    assert conflict(BASE, current, mine, KEYS, label=lambda r: r["description"]) == ["Hyperthermia"]


def test_adds_and_deletes_on_both_sides():
    current = rows(("r14", "Hyperthermia", "3"), ("r16", "VAP", ""), ("r17", "Apnea", "2"))   # they added r17
    mine = rows(("r16", "VAP", "")) + [{"description": "RDS", "grade": "2"}]                # I deleted r14, added RDS
    out = merge_rows(BASE, current, mine, KEYS)
    assert [r["description"] for r in out] == ["VAP", "Apnea", "RDS"] and all(r["row_id"] for r in out)


def test_deleted_by_them_edited_by_me_is_refused():
    current = rows(("r16", "VAP", ""))
    mine = rows(("r14", "Hyperthermia", "2"), ("r16", "VAP", ""))
    assert conflict(BASE, current, mine, KEYS)


def test_no_base_or_old_rows_replace_as_before():
    current = rows(("r14", "Hyperthermia", "2"))
    mine = [{"description": "Hyperthermia", "grade": "3"}]
    assert merge_rows(None, current, mine, KEYS)[0]["grade"] == "3"          # mobile app
    legacy = [{"description": "Hyperthermia", "grade": "2"}]
    assert merge_rows(legacy, legacy, mine, KEYS)[0]["grade"] == "3"         # rows without ids
    assert with_row_ids([{"a": 1}])[0]["row_id"]
