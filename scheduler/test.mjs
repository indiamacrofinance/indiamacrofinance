// node scheduler/test.mjs: checks the schedule maths (IST slots, due jobs, next runs).
import assert from "node:assert/strict";
import { due, nextRuns, slot } from "./worker.js";

const utc = (s) => Date.parse(s + "Z");
// 07:30 IST on Tuesday 3 Nov 2026 = 02:00 UTC
assert.deepEqual(slot(utc("2026-11-03T02:00:00")), { day: 2, minute: 450 });
assert.deepEqual(due(utc("2026-11-03T02:00:20")).map((j) => j.workflow), ["newsletter-morning.yml"]);
assert.deepEqual(due(utc("2026-11-03T01:30:00")).map((j) => j.workflow), ["bot-markets.yml"]);        // 07:00 IST
assert.deepEqual(due(utc("2026-11-03T02:05:00")), []);                                                 // 07:35: nothing
assert.deepEqual(due(utc("2026-11-08T01:30:00")), []);                                                 // Sunday 07:00: no markets
assert.deepEqual(due(utc("2026-11-08T02:00:00")).map((j) => j.workflow), ["newsletter-morning.yml"]); // Sunday email
assert.deepEqual(due(utc("2026-11-07T04:00:00")), []);                                                 // Saturday 09:30: no hourly
assert.equal(due(utc("2026-11-03T13:00:00")).length, 1);                                              // 18:30 IST: RBI
const next = nextRuns(utc("2026-11-03T02:02:00")).find((j) => j.workflow === "newsletter-morning.yml");
assert.equal(next.next.toISOString(), "2026-11-04T02:00:00.000Z");                                    // just missed: tomorrow
console.log("scheduler tests ok");
