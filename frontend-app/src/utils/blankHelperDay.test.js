import { isBlankHelperDay, isBlankHelperDayRefusal } from "./blankHelperDay";

test("empty helper payload is blank; explicit No is not", () => {
  expect(isBlankHelperDay({
    enrollment_id: "x",
    nicu_day: 4,
    submission_status: "draft",
    weight: null,
  })).toBe(true);
  expect(isBlankHelperDay({
    ph_readings_json: '[{"id":"1","date":"d","time":"t","ph":""}]',
  })).toBe(true);
  expect(isBlankHelperDay({ survived_the_day: false })).toBe(false);
  expect(isBlankHelperDay({
    ph_readings_json: '[{"id":"1","ph":"7.3"}]',
  })).toBe(false);
  expect(isBlankHelperDay({ map_cpap: 8 })).toBe(false);
});

test("Helper 2 empty create payload is blank even if support_modes is \"\"", () => {
  expect(isBlankHelperDay({
    enrollment_id: "01-C-099",
    nicu_day: 2,
    support_modes: "",
    vasoactive_drugs: "",
    respiratory_support: null,
    fluid_bolus_given: null,
    submission_status: "draft",
    saved_at: "2026-11-04T10:00:00.000Z",
    saved_by: "Nurse",
  })).toBe(true);
});

test("refuse_blank_helper_day 422 is recognized", () => {
  expect(isBlankHelperDayRefusal({
    response: { status: 422, data: { detail: "Nothing entered for this day yet." } },
  })).toBe(true);
  expect(isBlankHelperDayRefusal({
    response: { status: 422, data: { detail: "This baby died on 30 Oct 2026 (Day 3): no entries after that day." } },
  })).toBe(false);
});
