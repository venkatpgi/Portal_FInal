import { urineRateWarning, urineMlPerKgHr } from "./mmlHelperSync";

test("urine rate warnings match backend/value_ranges.py", () => {
  // 01-B-006 day 12: 130.6 ml in 6 h at 975 g
  expect(urineRateWarning(urineMlPerKgHr(130.6, 0.975, 6)).level).toBe("impossible");
  expect(urineRateWarning("10.7").level).toBe("high");
  expect(urineRateWarning("0.11").level).toBe("low");
  expect(urineRateWarning("4.4")).toBeNull();
  expect(urineRateWarning(null)).toBeNull();
  expect(urineRateWarning("")).toBeNull();
});
