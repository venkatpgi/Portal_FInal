import {
  caffeineMgPerKg,
  formatCaffeineMgPerKg,
  typicalCaffeineLoadingMg,
} from "./caffeineDose";

test("loading dose is mg/kg from absolute mg ÷ birth weight kg", () => {
  expect(caffeineMgPerKg(16, 800)).toBeCloseTo(20);
  expect(formatCaffeineMgPerKg(16, 800)).toBe("20.00");
  expect(typicalCaffeineLoadingMg(800)).toBeCloseTo(16);
});

test("maintenance uses the same mg/kg arithmetic (per day, not per frequency)", () => {
  expect(caffeineMgPerKg(8, 800)).toBeCloseTo(10);
});
