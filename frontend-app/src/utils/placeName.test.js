import { isPlaceNameInput, placeNameError } from "./placeName";

test("village / tehsil cannot contain digits", () => {
  expect(placeNameError("Chandigarh")).toBe("");
  expect(placeNameError("New Delhi")).toBe("");
  expect(placeNameError("Sector 12")).toBe("Letters only — numbers are not allowed");
  expect(placeNameError("123")).toBe("Letters only — numbers are not allowed");
  expect(isPlaceNameInput("Panchkula")).toBe(true);
  expect(isPlaceNameInput("Ward 4")).toBe(false);
});

test("empty optional tehsil is allowed; village is required", () => {
  expect(placeNameError("", { required: false })).toBe("");
  expect(placeNameError("", { required: true, label: "Village / VPO" }))
    .toBe("Village / VPO required");
});
