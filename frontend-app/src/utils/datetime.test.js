import { nicuDayForCalendarYmd } from "./datetime";

test("death on 30 Oct with Day 1 = 28 Oct is NICU Day 3", () => {
  expect(nicuDayForCalendarYmd("2026-10-28", "2026-10-30")).toBe(3);
  expect(nicuDayForCalendarYmd("2026-10-28", "2026-11-04")).toBe(8);
});
