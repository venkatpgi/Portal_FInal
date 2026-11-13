import { RANGE_BY_KEY, RANGE_BY_NAME, rangeCheck, rangeCheckText, textNumbers } from "./valueRanges";

test("PI ranges: refuse, warn, fine", () => {
  const g = RANGE_BY_KEY.dms_glucose;
  expect(rangeCheck(g, 650).level).toBe("impossible");
  expect(rangeCheck(g, 250).level).toBe("high");
  expect(rangeCheck(g, 15).level).toBe("low");
  expect(rangeCheck(g, 90)).toBeNull();
  expect(rangeCheck(g, "")).toBeNull();
  expect(rangeCheck(RANGE_BY_KEY.d_fio2, 15).level).toBe("impossible");
});

test("inputs are matched by name", () => {
  expect(RANGE_BY_NAME.birth_weight.confirmHi).toBe(3000);
  expect(RANGE_BY_NAME.nicu_peep.refuseHi).toBe(15);
  expect(RANGE_BY_NAME.sib_peep_cmh2o).toBeUndefined();   // dropped by the PI
});

test("text boxes with ranges", () => {
  expect(textNumbers("45-60")).toEqual([45, 60]);
  expect(textNumbers("Result Awaited")).toEqual([]);
  expect(rangeCheckText(RANGE_BY_KEY.dms_pao2, "20-700").level).toBe("impossible");
  expect(rangeCheckText(RANGE_BY_KEY.h5_creatinine, "1.1")).toBeNull();
});
