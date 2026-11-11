import {
  describeAuditChange,
  diffAuditValues,
  formatAuditValue,
  groupAuditRowsByIstDate,
  humanizeField,
  pairSaveRows,
  sortAuditRowsNewestFirst,
  summarizeAuditChanges,
  tidyAuditRows,
} from "./auditDiff";

test("urine field labels are readable", () => {
  expect(humanizeField("urine_output_8am_2pm")).toBe("Urine 8am–2pm (ml)");
  expect(humanizeField("urine_output_total")).toBe("Urine output total (ml/kg/hr)");
});

test("formatAuditValue never dumps JSON", () => {
  const json = JSON.stringify([
    { id: "w1", date: "2026-11-11", time: "08:00", ph: "7.32" },
  ]);
  const shown = formatAuditValue(json);
  expect(shown).not.toMatch(/[{}\[\]]/);
  expect(shown).toContain("7.32");
  expect(shown).toContain("08:00");
});

test("formatAuditValue shows Yes/No and empty as dash", () => {
  expect(formatAuditValue(true)).toBe("Yes");
  expect(formatAuditValue(false)).toBe("No");
  expect(formatAuditValue(null)).toBe("empty");
  expect(formatAuditValue("")).toBe("empty");
});

test("diff shows earlier vs new for a urine ml change", () => {
  const { changes } = diffAuditValues(
    { urine_output_8am_2pm: 12, nicu_day: 3 },
    { urine_output_8am_2pm: 15, nicu_day: 3 },
  );
  expect(changes).toHaveLength(1);
  expect(changes[0].key).toBe("urine_output_8am_2pm");
  expect(changes[0].from).toBe(12);
  expect(changes[0].to).toBe(15);
  expect(formatAuditValue(changes[0].from)).toBe("12");
  expect(formatAuditValue(changes[0].to)).toBe("15");
});

test("reading JSON that only changes row id is not a clinical change", () => {
  const { changes } = diffAuditValues(
    { ph_readings_json: '[{"id":"a","date":"2026-11-11","time":"08:00","ph":"7.3"}]' },
    { ph_readings_json: '[{"id":"b","date":"2026-11-11","time":"08:00","ph":"7.3"}]' },
  );
  expect(changes).toHaveLength(0);
});

test("enrollment_id and saved_by are hidden as noise", () => {
  const { changes } = diffAuditValues(
    { enrollment_id: "01-A-001", saved_by: "Nurse A", aki_suspected: false },
    { enrollment_id: "01-A-001", saved_by: "Nurse B", aki_suspected: true },
  );
  expect(changes.map((c) => c.key)).toEqual(["aki_suspected"]);
});

test("Form A SAVE without clinical fields summarises as Saved", () => {
  const { changes } = diffAuditValues(
    null,
    { form: "A", explicitly_saved: true },
  );
  expect(changes).toHaveLength(0);
  expect(summarizeAuditChanges(changes, { action: "SAVE" })).toBe("Saved — no answers changed");
});

test("dummy SAVE row picks up the paired UPDATE answers", () => {
  const rows = pairSaveRows([
    {
      id: 2,
      action: "SAVE",
      table_name: "screenings",
      screening_id: "01-10000",
      created_at: "2026-11-11T10:22:00Z",
      new_values: { form: "Form A — Screening", explicitly_saved: true },
    },
    {
      id: 1,
      action: "UPDATE",
      table_name: "screenings",
      screening_id: "01-10000",
      created_at: "2026-11-11T10:22:01Z",
      old_values: { expected_delivery_date: "2026-03-20", consent_signature_captured_at: null },
      new_values: { expected_delivery_date: "2026-03-21", consent_signature_captured_at: "2026-11-11T10:20:00Z" },
    },
  ]);
  expect(rows).toHaveLength(1);
  expect(rows[0].action).toBe("SAVE");
  const { changes } = diffAuditValues(rows[0].old_values, rows[0].new_values);
  expect(changes.map((c) => c.key).sort()).toEqual([
    "consent_signature_captured_at",
    "expected_delivery_date",
  ]);
  expect(summarizeAuditChanges(changes, { action: "SAVE" })).toMatch(/Expected delivery date/);
});

test("adding a DMS weight entry shows the grams not a reading count", () => {
  const { changes } = diffAuditValues(
    { entries_json: JSON.stringify({ growth_a: [] }), saved_at: "2026-11-11T11:20:00Z" },
    {
      entries_json: JSON.stringify({
        growth_a: [{ id: "g1", date: "2026-11-11", slot_time: "16:50", weight_g: "400" }],
      }),
      saved_at: "2026-11-11T11:20:30Z",
    },
  );
  expect(changes.map((c) => c.key)).not.toContain("saved_at");
  expect(changes).toHaveLength(1);
  expect(changes[0].kind).toBe("added");
  expect(changes[0].fieldKey).toBe("weight_g");
  expect(changes[0].label).toMatch(/Weight/);
  const described = describeAuditChange(changes[0]);
  expect(described.was).toMatch(/empty/i);
  expect(described.now).toContain("400");
  expect(described.now).toContain("g");
});

test("describeAuditChange uses was/now language", () => {
  const added = describeAuditChange({
    kind: "added",
    from: null,
    to: "21 Mar 2026",
  });
  expect(added.was).toBe("empty (not filled)");
  expect(added.now).toBe("21 Mar 2026");
  const hidden = describeAuditChange({
    kind: "hidden",
    from: "[previous]",
    to: "[updated]",
  });
  expect(hidden.now).toMatch(/details not shown/);
});

test("DMS vitals are not repeated as SBP/DBP/MAP plus the reading", () => {
  const { changes } = diffAuditValues(
    {
      sbp: null,
      dbp: null,
      map_value: null,
      entries_json: JSON.stringify({
        cv_a: [{ id: "1", date: "2026-11-11", slot_time: "06:00", axillary_temp: "4" }],
      }),
    },
    {
      sbp: 31,
      dbp: 13,
      map_value: 33,
      entries_json: JSON.stringify({
        cv_a: [{
          id: "1", date: "2026-11-11", slot_time: "06:00",
          axillary_temp: "4", sbp: "31", dbp: "13", map_value: "33",
        }],
      }),
    },
  );
  expect(changes.map((c) => c.fieldKey).sort()).toEqual(["dbp", "map_value", "sbp"]);
  expect(changes.every((c) => /Vitals/.test(c.group))).toBe(true);
  expect(describeAuditChange(changes.find((c) => c.fieldKey === "sbp")).now).toMatch(/31/);
  expect(changes.some((c) => c.fieldKey === "axillary_temp")).toBe(false);
});

test("empty twin UPDATE is dropped when the same save has real changes", () => {
  const tidied = tidyAuditRows([
    {
      id: 3,
      action: "UPDATE",
      table_name: "minimal_monitoring_day_logs",
      enrollment_id: "01-D-039",
      created_at: "2026-11-11T11:37:02Z",
      old_values: { saved_at: "2026-11-11T11:37:00Z" },
      new_values: { saved_at: "2026-11-11T11:37:02Z" },
    },
    {
      id: 2,
      action: "UPDATE",
      table_name: "minimal_monitoring_day_logs",
      enrollment_id: "01-D-039",
      created_at: "2026-11-11T11:37:01Z",
      old_values: {
        entries_json: JSON.stringify({ cv_a: [{ id: "1", date: "2026-11-11", slot_time: "06:00", axillary_temp: "4" }] }),
      },
      new_values: {
        entries_json: JSON.stringify({
          cv_a: [{ id: "1", date: "2026-11-11", slot_time: "06:00", axillary_temp: "4", sbp: "31" }],
        }),
      },
    },
  ]);
  expect(tidied).toHaveLength(1);
  const { changes } = diffAuditValues(tidied[0].old_values, tidied[0].new_values);
  expect(changes.length).toBeGreaterThan(0);
  expect(summarizeAuditChanges(changes, { action: "UPDATE" })).not.toMatch(/No answers changed/);
});

test("baby timeline groups rows by IST calendar day", () => {
  const groups = groupAuditRowsByIstDate([
    { id: 2, created_at: "2026-11-11T11:37:00Z" },
    { id: 1, created_at: "2026-11-10T10:00:00Z" },
  ]);
  expect(groups).toHaveLength(2);
  expect(groups[0].label).toMatch(/11 Nov 2026/);
  expect(groups[1].label).toMatch(/10 Nov 2026/);
  expect(groups[0].rows.map((r) => r.id)).toEqual([2]);
  expect(groups[1].rows.map((r) => r.id)).toEqual([1]);
});

test("15:52 IST wall-clock sorts after a later 16:54 UTC save", () => {
  const realNow = Date.now;
  Date.now = () => Date.UTC(2026, 10, 11, 11, 25, 0); // 16:55 IST
  try {
    const sorted = sortAuditRowsNewestFirst([
      { id: 1, created_at: "2026-11-11T15:52:00" },
      { id: 2, created_at: "2026-11-11T11:24:00Z" },
    ]);
    expect(sorted.map((r) => r.id)).toEqual([2, 1]);
  } finally {
    Date.now = realNow;
  }
});
