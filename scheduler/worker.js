// The scheduler: a Cloudflare Worker that starts the GitHub workflows on time.
//
// GitHub's own cron (`schedule:` in the workflows) starts jobs hours late and sometimes not at
// all (measured Oct-Nov 2026: the 07:30 email ran at 13:45-15:30 IST). Cloudflare's Cron
// Trigger fires this Worker every 5 minutes; it looks up which jobs are due at that IST time
// and asks GitHub to start them (workflow_dispatch), which GitHub does within seconds.
// The GitHub schedules stay in the workflows as a backup: a second run is harmless (bots commit
// only when data changed; the newsletter sends once a day).
//
// Secret: GITHUB_TOKEN, a fine-grained token limited to this repo with "Actions: read and write",
// set by the maintainer in Cloudflare (Workers & Pages -> indiamacrofinance-scheduler -> Settings
// -> Variables and Secrets). Deployed by .github/workflows/scheduler.yml.
// Visiting the Worker's address shows the schedule and the next run of each job (read-only).

// Times are IST. days: 0 = Sunday ... 6 = Saturday.
const WEEKDAYS = [1, 2, 3, 4, 5];
const MON_SAT = [1, 2, 3, 4, 5, 6];
const ALL = [0, 1, 2, 3, 4, 5, 6];
export const SCHEDULE = [
  { workflow: "bot-markets.yml", what: "Markets, the rupee and its drivers (pre-email run)", days: MON_SAT, times: ["07:00"] },
  { workflow: "newsletter-morning.yml", what: "Morning email on the rupee", days: ALL, times: ["07:30"] },
  { workflow: "bot-markets.yml", what: "Markets, the rupee and its drivers (hourly)", days: WEEKDAYS,
    times: ["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30", "16:30", "17:30"] },
  { workflow: "bot-ministries.yml", what: "Ministries: trade, GST, accounts, fuel, autos (midday)", days: ALL, times: ["13:00"] },
  { workflow: "bot-mospi.yml", what: "MoSPI: inflation, GDP, IIP, jobs", days: MON_SAT, times: ["17:00", "20:00"] },
  { workflow: "bot-rbi.yml", what: "RBI: reserves, money, credit, external", days: MON_SAT, times: ["18:30"] },
  { workflow: "bot-ministries.yml", what: "Ministries: trade, GST, accounts, fuel, autos (evening)", days: MON_SAT, times: ["19:30"] },
];

const IST_MS = 5.5 * 3600 * 1000;
const STEP_MIN = 5;   // the Cron Trigger's interval

// IST weekday and minute-of-day for a UTC timestamp, rounded down to the 5-minute slot.
export function slot(ms) {
  const d = new Date(ms + IST_MS);
  const minute = d.getUTCHours() * 60 + d.getUTCMinutes();
  return { day: d.getUTCDay(), minute: minute - (minute % STEP_MIN) };
}

const toMin = (hhmm) => { const [h, m] = hhmm.split(":").map(Number); return h * 60 + m; };

export function due(ms) {
  const { day, minute } = slot(ms);
  return SCHEDULE.filter((j) => j.days.includes(day) && j.times.some((t) => toMin(t) === minute));
}

// The next time (UTC ms) each schedule entry fires, for the status page.
export function nextRuns(now) {
  return SCHEDULE.map((j) => {
    for (let k = STEP_MIN; k < 8 * 24 * 60; k += STEP_MIN) {
      const t = now + k * 60000;
      const { day, minute } = slot(t);
      if (j.days.includes(day) && j.times.some((x) => toMin(x) === minute)) {
        return { ...j, next: new Date(t - ((t + IST_MS) % (STEP_MIN * 60000))) };
      }
    }
    return { ...j, next: null };
  });
}

async function dispatch(env, workflow) {
  const r = await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows/${workflow}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "indiamacrofinance-scheduler",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  return { workflow, status: r.status, detail: r.status === 204 ? "" : (await r.text()).slice(0, 200) };
}

const fmtIst = (d) => new Date(d.getTime() + IST_MS).toISOString().replace("T", " ").slice(0, 16) + " IST";

export default {
  async scheduled(event, env, ctx) {
    const jobs = due(event.scheduledTime);
    if (!jobs.length) return;
    if (!env.GITHUB_TOKEN) { console.log("GITHUB_TOKEN not set; nothing started"); return; }
    const results = await Promise.all([...new Set(jobs.map((j) => j.workflow))].map((w) => dispatch(env, w)));
    for (const r of results) console.log(`${r.workflow}: ${r.status === 204 ? "started" : `failed ${r.status} ${r.detail}`}`);
  },

  async fetch(request, env) {
    const now = Date.now();
    const rows = nextRuns(now).sort((a, b) => a.next - b.next)
      .map((j) => `${fmtIst(j.next)}  ${j.workflow.padEnd(24)} ${j.what}`);
    // Read-only check that the token can see this repo's workflows (it never starts anything here).
    let token = "NO: set GITHUB_TOKEN in Cloudflare; nothing is started until it is";
    if (env.GITHUB_TOKEN) {
      const r = await fetch(`https://api.github.com/repos/${env.REPO}/actions/workflows?per_page=1`, {
        headers: { Authorization: `Bearer ${env.GITHUB_TOKEN}`, Accept: "application/vnd.github+json",
                   "User-Agent": "indiamacrofinance-scheduler", "X-GitHub-Api-Version": "2022-11-28" },
      });
      token = r.ok ? "set and working" : `set, but GitHub answered ${r.status}: check the token's repo and permissions`;
    }
    const lines = [
      "indiamacrofinance scheduler: starts the GitHub workflows on time (Cloudflare Cron Trigger, every 5 minutes).",
      `Now: ${fmtIst(new Date(now))}. GitHub token: ${token}.`,
      "",
      "Next run of each job:",
      ...rows,
      "",
      "Full schedule (IST):",
      ...SCHEDULE.map((j) => `  ${j.workflow.padEnd(24)} ${j.times.join(", ")}  on ${j.days.length === 7 ? "every day" : j.days.length === 6 ? "Mon-Sat" : "Mon-Fri"}  (${j.what})`),
      "",
      `Runs so far: https://github.com/${env.REPO}/actions`,
    ];
    return new Response(lines.join("\n") + "\n", { headers: { "content-type": "text/plain; charset=utf-8" } });
  },
};
