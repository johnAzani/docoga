// DocOga clock — a Cloudflare Worker that rings GitHub's doorbell on time.
//
// Every five minutes (Cron Trigger "*/5 * * * *", UTC) it reads schedule.json —
// generated from the repo's own workflow crons by tools/clock_schedule.py — and
// dispatches every lane whose cron fired in the last five minutes:
//
//   POST https://api.github.com/repos/{owner}/{repo}/actions/workflows/{file}/dispatches
//   { ref: "main", inputs: {...} }
//
// Why: GitHub's own `schedule:` has delivered a fraction of this repo's slots,
// hours late, since 26 Aug 2026 (see tools/clock_schedule.py). workflow_dispatch
// starts within seconds. Workers Free: 100k requests/day, 10 ms CPU per cron
// invocation (waiting on fetch is not CPU), 50 subrequests per invocation — this
// Worker uses at most ~6 per tick. Cost: nothing.
//
// Secrets / vars (wrangler secret put …, or the deploy workflow):
//   GH_DISPATCH_TOKEN  fine-grained PAT, repository docoga, Actions: read & write
//   GH_REPO            "johnAzani/docoga" (var, in wrangler.toml)
//   CLOCK              "off" pauses every dispatch (var; absent = on)
//
// Idempotency: windows (tick-5, tick] are disjoint and taken from
// event.scheduledTime (the slot Cloudflare meant), not Date.now(), so a late
// tick still dispatches its own five minutes and never its neighbour's. GitHub's
// own late cron can still arrive for the same slot — every lane's duplicate
// guard turns that into a green no-op.

import schedule from "./schedule.json" with { type: "json" };

const UA = "docoga-clock (+https://docoga.com.ng)";

function field(spec, lo, hi) {
  const out = new Set();
  for (const part0 of spec.split(",")) {
    let part = part0, step = 1;
    if (part.includes("/")) { const [p, s] = part.split("/"); part = p; step = parseInt(s, 10); }
    let start, end;
    if (part === "*") { start = lo; end = hi; }
    else if (part.includes("-")) { const [a, b] = part.split("-"); start = parseInt(a, 10); end = parseInt(b, 10); }
    else { start = end = parseInt(part, 10); }
    for (let v = start; v <= end; v += step) if (v >= lo && v <= hi) out.add(v);
  }
  return out;
}

// Mirror of tools/clock_schedule.py:matches — keep the two in step (the test suite does).
export function matches(cron, when) {
  const [minute, hour, dom, month, dow] = cron.trim().split(/\s+/);
  if (!field(minute, 0, 59).has(when.getUTCMinutes())) return false;
  if (!field(hour, 0, 23).has(when.getUTCHours())) return false;
  if (!field(month, 1, 12).has(when.getUTCMonth() + 1)) return false;
  const domOk = field(dom, 1, 31).has(when.getUTCDate());
  const d = when.getUTCDay();                       // 0 = Sunday
  const dowSet = field(dow, 0, 7);
  const dowOk = dowSet.has(d) || (d === 0 && dowSet.has(7));
  if (dom === "*" && dow === "*") return true;
  if (dom === "*") return dowOk;
  if (dow === "*") return domOk;
  return domOk || dowOk;
}

export function due(entries, tickMs, tickMinutes) {
  const tick = new Date(Math.floor(tickMs / 60000) * 60000);
  const out = [];
  for (const row of entries) {
    for (let back = 0; back < tickMinutes; back++) {
      const when = new Date(tick.getTime() - back * 60000);
      if (matches(row.cron, when)) { out.push({ ...row, fires_at: when.toISOString() }); break; }
    }
  }
  return out;
}

async function dispatch(env, row) {
  const url = `https://api.github.com/repos/${env.GH_REPO}/actions/workflows/${row.workflow}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.GH_DISPATCH_TOKEN}`,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      "User-Agent": UA,
    },
    body: JSON.stringify({ ref: schedule.ref || "main", inputs: row.inputs || {} }),
  });
  const text = res.status === 204 ? "" : (await res.text()).slice(0, 200);
  return { workflow: row.workflow, status: res.status, detail: text };
}

export async function tick(env, scheduledTime, log = console.log) {
  const rows = due(schedule.entries, scheduledTime, schedule.tick_minutes || 5);
  if ((env.CLOCK || "").toLowerCase() === "off") {
    log(`CLOCK=off due=${rows.length} — paused by the CLOCK variable`);
    return { paused: true, due: rows, results: [] };
  }
  if (!env.GH_DISPATCH_TOKEN) {
    log(`CLOCK=no-token due=${rows.length} — set GH_DISPATCH_TOKEN (docs/CLOCK.md); GitHub's own cron is the only clock until then`);
    return { paused: false, due: rows, results: [] };
  }
  const results = [];
  for (const row of rows) {
    try { results.push(await dispatch(env, row)); }
    catch (err) { results.push({ workflow: row.workflow, status: 0, detail: String(err).slice(0, 200) }); }
  }
  for (const r of results) log(`CLOCK_DISPATCH ${r.workflow} -> ${r.status}${r.detail ? " " + r.detail : ""}`);
  return { paused: false, due: rows, results };
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(tick(env, event.scheduledTime));
  },
  // GET / — a human-readable health page: what is due in this tick, token present or not.
  async fetch(request, env) {
    const now = Date.now();
    const rows = due(schedule.entries, now, schedule.tick_minutes || 5);
    const body = {
      ok: true,
      repo: env.GH_REPO,
      token: env.GH_DISPATCH_TOKEN ? "present" : "missing",
      paused: (env.CLOCK || "").toLowerCase() === "off",
      entries: schedule.entries.length,
      due_this_tick: rows.map((r) => r.workflow),
      utc: new Date(now).toISOString(),
    };
    return new Response(JSON.stringify(body, null, 2), { headers: { "content-type": "application/json" } });
  },
};
