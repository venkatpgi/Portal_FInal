import {
  DEFAULT_HELPER_LOCATIONS,
  PGIMER_HELPER_LOCATIONS,
  helperLocationOptions,
  isPgimerBaby,
  normalizeHelperLocations,
} from "./helperLocation";

test("PGIMER is enrollment prefix 01, not the logged-in user", () => {
  expect(isPgimerBaby({ enrollmentId: "01-C-099" })).toBe(true);
  expect(isPgimerBaby({ enrollmentId: "02-A-001", site: "PGIMER" })).toBe(false);
  expect(isPgimerBaby({ enrollmentId: "06-B-010" })).toBe(false);
  expect(isPgimerBaby({ site: "PGIMER" })).toBe(true);
  expect(isPgimerBaby({ site: "GMCH" })).toBe(false);
});

test("PGIMER babies get AMCC wards; other sites keep the current chips", () => {
  expect(helperLocationOptions({ enrollmentId: "01-C-099" })).toEqual(
    PGIMER_HELPER_LOCATIONS,
  );
  expect(helperLocationOptions({ enrollmentId: "03-A-002" })).toEqual(
    DEFAULT_HELPER_LOCATIONS,
  );
  expect(helperLocationOptions({ site: "IOG" })).toEqual(DEFAULT_HELPER_LOCATIONS);
});

test("legacy DR/NICU on a PGIMER row map onto AMCC labels", () => {
  expect(
    normalizeHelperLocations(["DR", "NICU", "KMC-N"], { enrollmentId: "01-C-099" }),
  ).toEqual(["AMCC-1A (DR)", "AMCC-4A (NICU)", "KMC-N"]);
  expect(
    normalizeHelperLocations(["AMCC-1A(DR)"], { enrollmentId: "01-C-099" }),
  ).toEqual(["AMCC-1A (DR)"]);
  expect(
    helperLocationOptions({
      enrollmentId: "01-C-099",
      selected: ["AMCC-1A (DR)", "KMC-N"],
    }),
  ).toEqual([...PGIMER_HELPER_LOCATIONS, "KMC-N"]);
});
