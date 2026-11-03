// node scheduler/test.mjs: checks the schedule maths (IST slots, due jobs, next runs) and the
// shape of /api/status that the live dashboard reads.
import assert from "node:assert/strict";
import { SCHEDULE, due, nextRuns, shapeStatus, slot } from "./worker.js";

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

// /api/status: running runs carry their current step; `last` is the latest completed run per workflow.
const run = (id, path, status, conclusion, started) => ({ id, path: `.github/workflows/${path}`, name: path, display_title: "t",
  event: "workflow_dispatch", status, conclusion, run_started_at: started, updated_at: started, html_url: "u" });
const st = shapeStatus({
  now: utc("2026-11-03T13:05:00"),
  runs: [run(3, "bot-rbi.yml", "in_progress", null, "2026-11-03T13:00:00Z"),
         run(2, "deploy.yml", "completed", "success", "2026-11-03T12:00:00Z"),
         run(1, "deploy.yml", "completed", "failure", "2026-11-03T11:00:00Z")],
  commits: [{ sha: "abcdef0123", commit: { author: { name: "rbi-bot", date: "2026-11-03T12:59:00Z" }, message: "rbi: x\n\nbody" } }],
  issues: [{ number: 5, title: "broken", html_url: "u", labels: [{ name: "scraper-broken" }] }, { number: 6, pull_request: {}, labels: [] }],
  jobs: { 3: [{ steps: [{ name: "Set up", status: "completed" }, { name: "Fetch", status: "in_progress" }] }] },
  siteMap: null,
});
assert.deepEqual(st.active.map((r) => [r.workflow, r.step]), [["bot-rbi.yml", "Fetch"]]);
assert.equal(st.last["deploy.yml"].conclusion, "success");
assert.equal(st.commits[0].message, "rbi: x");
assert.deepEqual(st.issues.map((i) => i.number), [5]);
assert.equal(st.schedule.length, SCHEDULE.length);
console.log("scheduler tests ok");
