import {
  LOCATION_AREAS,
  helperLocationOptions,
  isPgimerBaby,
  locationLabel,
  normalizeHelperLocations,
} from "./helperLocation";

test("PGIMER is enrollment prefix 01, not the logged-in user", () => {
  expect(isPgimerBaby({ enrollmentId: "01-C-099" })).toBe(true);
  expect(isPgimerBaby({ enrollmentId: "02-A-001", site: "PGIMER" })).toBe(false);
  expect(isPgimerBaby({ enrollmentId: "06-B-010" })).toBe(false);
  expect(isPgimerBaby({ site: "PGIMER" })).toBe(true);
  expect(isPgimerBaby({ site: "GMCH" })).toBe(false);
});

test("every site gets the same generic areas; Form D has no DR", () => {
  expect(helperLocationOptions()).toEqual(LOCATION_AREAS);
  expect(helperLocationOptions({ noDR: true })).not.toContain("DR");
  expect(helperLocationOptions({ noDR: true })).toContain("NICU");
});

test("PGIMER buttons show the AMCC ward; other sites the area only", () => {
  expect(locationLabel("NICU", { enrollmentId: "01-C-099" })).toBe("NICU (AMCC 4A / 4B)");
  expect(locationLabel("KMC nursery", { site: "PGIMER" })).toBe("KMC nursery (AMCC 5C)");
  expect(locationLabel("HDU", { enrollmentId: "01-C-099" })).toBe("HDU");
  expect(locationLabel("NICU", { enrollmentId: "03-A-002" })).toBe("NICU");
});

test("earlier labels map onto the generic areas; unknown values are kept", () => {
  expect(normalizeHelperLocations(["Step-down/Nursery", "KMC-N", "AMCC-4A (NICU)", "AMCC-1C(NURSERY)"]))
    .toEqual(["Nursery", "KMC nursery", "NICU", "Transitional nursery"]);
  expect(helperLocationOptions({ selected: ["NICU", "Other"] })).toEqual([...LOCATION_AREAS, "Other"]);
});
