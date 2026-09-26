import assert from "node:assert/strict";
import test from "node:test";

import { formatJstDate } from "../fortune-next-app/app/jst-date.ts";

const cases = [
  ["2026-09-24T14:59:59Z", "2026-09-24"],
  ["2026-09-24T15:00:00Z", "2026-09-25"],
  ["2026-09-24T22:03:00Z", "2026-09-25"],
  ["2026-09-25T14:59:59Z", "2026-09-25"],
  ["2026-09-25T15:00:00Z", "2026-09-26"],
];

for (const [instant, expected] of cases) {
  test(`${instant} is ${expected} in JST`, () => {
    assert.equal(formatJstDate(new Date(instant)), expected);
  });
}
