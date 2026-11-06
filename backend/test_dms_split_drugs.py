from dms_split_drugs import split_entries


def test_one_row_per_drug_keeps_stamps_and_first_id():
    e = {"cv_c": [{"id": "a1", "date": "2026-11-05", "time": "11:21",
                   "vasoactive_drugs": ["Dopamine", "Dobutamine"], "vasoactive_dose": "10", "vasoactive_unit": "mcg/kg/min"}]}
    new, notes = split_entries(e)
    rows = new["cv_c"]
    assert [r["vasoactive_drugs"] for r in rows] == [["Dopamine"], ["Dobutamine"]]
    assert [r["id"] for r in rows] == ["a1", "a1-2"]
    assert all(r["time"] == "11:21" and r["date"] == "2026-11-05" for r in rows)
    assert rows[0]["vasoactive_dose"] == "10" and "vasoactive_dose" not in rows[1]
    assert "kept on Dopamine only" in notes[0]


def test_owned_fields_follow_their_choice():
    e = {"heme_a": [{"id": "h", "transfusion_products": "Platelets, PRBC", "prbc_volume": "15"}],
         "resp_d": [{"id": "s", "postnatal_steroids": ["Other", "Hydrocortisone"], "steroid_other": "Prednisolone"}]}
    new, _ = split_entries(e)
    assert [r.get("prbc_volume") for r in new["heme_a"]] == [None, "15"]
    assert [r.get("steroid_other") for r in new["resp_d"]] == ["Prednisolone", None]


def test_single_values_untouched():
    e = {"cv_c": [{"id": "x", "vasoactive_drugs": ["Dopamine"]}], "cv_a": [{"id": "v", "sbp": "40"}]}
    new, notes = split_entries(e)
    assert new == e and notes == []
