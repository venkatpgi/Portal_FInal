import { babyIdLabel, pageEnrollmentId, pageScreeningId, urlEnrollmentId } from "./enrollmentId";

const at = (path) => window.history.pushState({}, "", path);

beforeEach(() => localStorage.clear());

test("the address names this tab's baby, whatever another tab stored", () => {
  localStorage.setItem("current_enrollment_id", "02-A-001");
  localStorage.setItem("current_screening_id", "02-0001");
  at("/minimal-monitoring/NR-05-0026");
  expect(urlEnrollmentId()).toBe("NR-05-0026");
  expect(pageEnrollmentId()).toBe("NR-05-0026");
  expect(pageScreeningId()).toBeNull();
});

test("without a baby in the address the stored ids are used", () => {
  localStorage.setItem("current_enrollment_id", "02-A-001");
  localStorage.setItem("current_screening_id", "02-0001");
  at("/form-b/02-0001");
  expect(urlEnrollmentId()).toBeNull();
  expect(pageEnrollmentId()).toBe("02-A-001");
  expect(pageScreeningId()).toBe("02-0001");
});

test("same baby keeps its screening id", () => {
  localStorage.setItem("current_enrollment_id", "01-D-901");
  localStorage.setItem("current_screening_id", "01-0901");
  at("/vs6-1/01-D-901");
  expect(pageScreeningId()).toBe("01-0901");
});

test("baby label: in error, not randomised, randomised, missing", () => {
  expect(babyIdLabel({ enrollment_id: "01-B-007", randomised_in_error: true })).toBe("01-B-007 (in error)");
  expect(babyIdLabel({ enrollment_id: "NR-01-0140-2" })).toBe("not randomised");
  expect(babyIdLabel({ enrollment_id: "01-A-003" })).toBe("01-A-003");
  expect(babyIdLabel(null)).toBe("no Form B");
});
