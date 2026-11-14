import {
  completedByNameOptions,
  isMannatGuliani,
  withMannatLast,
} from "./completedByDesignation";

test("Mannat Guliani is last in completed-by options, with or without Dr.", () => {
  const roster = [
    { full_name: "Yashvi Jolly" },
    { full_name: "Dr. Mannat Guliani" },
    { full_name: "Geetika" },
    { full_name: "Shalini Dhiman" },
  ];
  expect(completedByNameOptions(roster, "")).toEqual([
    "Yashvi Jolly",
    "Geetika",
    "Shalini Dhiman",
    "Dr. Mannat Guliani",
  ]);
  expect(withMannatLast(["Mannat Guliani", "Geetika"])).toEqual([
    "Geetika",
    "Mannat Guliani",
  ]);
  expect(isMannatGuliani("Dr. Mannat Guliani")).toBe(true);
  expect(isMannatGuliani("Shalini Dhiman")).toBe(false);
  expect(completedByNameOptions(roster, "Historical Name").slice(-1)).toEqual([
    "Dr. Mannat Guliani",
  ]);
});
