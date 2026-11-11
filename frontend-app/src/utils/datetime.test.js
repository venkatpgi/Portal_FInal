import { nicuDayForCalendarYmd, parseApiUtcDate, formatAuditClock, formatAuditDateTime, formatAuditDay } from "./datetime";

test("death on 30 Oct with Day 1 = 28 Oct is NICU Day 3", () => {
  expect(nicuDayForCalendarYmd("2026-10-28", "2026-10-30")).toBe(3);
  expect(nicuDayForCalendarYmd("2026-10-28", "2026-11-04")).toBe(8);
});

test("naive ISO timestamps from the API are treated as UTC", () => {
  const naive = parseApiUtcDate("2026-09-26T04:26:17");
  const zulu = parseApiUtcDate("2026-09-26T04:26:17Z");
  expect(naive.getTime()).toBe(zulu.getTime());
});

test("audit timestamps are shown in IST", () => {
  expect(formatAuditDateTime("2026-09-26T04:26:17Z")).toMatch(
    /26 Sept? 2026.*09:56 IST/,
  );
  expect(formatAuditClock("2026-09-26T04:26:17Z")).toBe("09:56 IST");
  expect(formatAuditDay("2026-09-26T04:26:17Z")).toMatch(/Sat.*26 Sept? 2026/);
});

test("naive IST wall-clock times are not shifted +5:30", () => {
  const realNow = Date.now;
  Date.now = () => Date.UTC(2026, 10, 11, 10, 18, 0); // 15:48 IST
  try {
    expect(formatAuditDateTime("2026-11-11T15:47:00")).toMatch(/15:47 IST/);
    expect(formatAuditDateTime("2026-11-11T15:47:00Z")).toMatch(/15:47 IST/);
    expect(formatAuditDateTime("2026-11-11T10:17:00Z")).toMatch(/15:47 IST/);
  } finally {
    Date.now = realNow;
  }
});
