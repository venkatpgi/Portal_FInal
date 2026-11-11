import {
  describeAuditChange,
  diffAuditValues,
  formatAuditValue,
  humanizeField,
  pairSaveRows,
  summarizeAuditChanges,
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
