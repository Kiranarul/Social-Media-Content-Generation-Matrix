# 🔁 Polling & Scheduling Strategy

## Change 1: Recommendation Status → "Done" (Safe by Default)

**Problem:** When AI auto-creates a recommendation in Active Request with status `Ready to Generate`,
the poll loop picks it up immediately next cycle and auto-triggers topic generation — wasting API credits
and potentially generating unwanted content.

**Fix:** Change status to `Done` when creating the recommendation item.
The human then **manually changes the status to `Ready to Generate`** only when they want to proceed.

```
ai_engine.py → run_recommendation_stage() → status: "Done"   (was "Ready to Generate")
```

This is a 1-line change. ✅ Approved to execute immediately.

---

## Change 2: Polling & Scheduling — Comparison of All Options

### The Core Problem

GitHub Actions scheduled crons (`*/5 * * * *`) have two fatal flaws:
1. **Silently disabled after 60 days** of repo inactivity (no pushes)
2. **Delayed up to 15–30 minutes** during peak GitHub load — not reliable for 5-min intervals
3. **6-hour maximum job time** — but since each poll run finishes in ~60 seconds this doesn't apply

---

### Option A: GitHub Actions Cron Only (Current State) ❌ Unreliable

```yaml
schedule:
  - cron: '*/5 * * * *'
```

| ✅ Pros | ❌ Cons |
|---|---|
| Zero cost, zero setup | Disabled after 60 days inactivity |
| Built-in, no external dependencies | Can be delayed 10–30 min during peak |
| Triggers recommendation daily too | No guarantee of exact timing |

**Verdict:** Works for low-urgency content workflows but not reliable enough for 5-min SLA.

---

### Option B: UptimeRobot → GitHub API Trigger ✅ RECOMMENDED

UptimeRobot (free tier: 50 monitors, 5-min intervals) pings a public endpoint every 5 minutes.
That endpoint triggers the GitHub Actions workflow via the GitHub API.

**Architecture:**
```
UptimeRobot (every 5 min)
  → HTTP GET → Render/Railway free web service (tiny Flask app)
    → GitHub API POST /repos/{owner}/{repo}/actions/workflows/{id}/dispatches
      → GitHub Actions runs "poll" job
        → ai_engine.py poll → scans Monday.com → reacts
```

**Cost:** Free (UptimeRobot free + Render free tier or Railway $5/mo)

**Setup Steps:**
1. Create a tiny Flask app (`trigger_server.py`) with one `GET /trigger` endpoint
2. Deploy to Render (free) or Railway
3. The endpoint calls GitHub API to dispatch `content_ai.yml` with `mode=poll`
4. Add `GITHUB_TOKEN` as env var to Render
5. In UptimeRobot: Add HTTP monitor → URL = your Render app `/trigger` → every 5 min

| ✅ Pros | ❌ Cons |
|---|---|
| Guaranteed 5-min intervals | Requires tiny web app deployment |
| Never disabled | Small setup overhead (~30 min) |
| UptimeRobot dashboard shows health | Render free tier spins down after 15 min idle |
| Free | Need to handle Render cold start (~10s) |

---

### Option C: GitHub Actions Self-Chaining Workflow ⚠️ Hacky

A workflow that at its end triggers itself again using `workflow_dispatch` via GitHub API.

```yaml
- name: Re-trigger self
  run: |
    curl -X POST \
      -H "Authorization: token ${{ secrets.GITHUB_TOKEN }}" \
      https://api.github.com/repos/${{ github.repository }}/actions/workflows/content_ai.yml/dispatches \
      -d '{"ref":"main","inputs":{"mode":"poll"}}'
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

| ✅ Pros | ❌ Cons |
|---|---|
| No external services | GitHub may rate-limit or block circular triggers |
| Stays alive indefinitely | Creates huge run history noise |
| Self-healing | Counted against Actions minutes quota |
| Zero cost | GitHub ToS grey area |

**Verdict:** Works but messy. Not recommended.

---

### Option D: Dedicated "Keepalive" Workflow ⚠️ Partial Fix

Create a second workflow `keepalive.yml` with its own cron. Since two different schedules restart
independently, repo inactivity disables BOTH simultaneously — doesn't solve the real problem.

**Verdict:** Doesn't fix the 60-day inactivity issue. Rejected.

---

### Option E: Render Cron Job (Paid $7/mo) ✅ Cleanest

Render has a native "Cron Job" service type that runs a script on a schedule.
Script calls GitHub API to dispatch the workflow.

```python
# cron_trigger.py — deployed as Render Cron Job
import requests, os
requests.post(
    f"https://api.github.com/repos/{os.environ['REPO']}/actions/workflows/content_ai.yml/dispatches",
    headers={"Authorization": f"token {os.environ['GITHUB_TOKEN']}"},
    json={"ref": "main", "inputs": {"mode": "poll"}}
)
```

| ✅ Pros | ❌ Cons |
|---|---|
| Native cron scheduling | $7/month |
| Extremely reliable | Slightly more setup than UptimeRobot |
| No cold start issues | |
| Clean GitHub Actions history | |

---

## 🏆 Recommended Architecture

### For Now (Zero Cost): Option B — UptimeRobot + Render Free

```
UptimeRobot (free, 5-min)
  ↓ HTTP GET /trigger
Render Web Service (free)  ← tiny Flask app, always-on on free tier
  ↓ GitHub API dispatch
GitHub Actions content_ai.yml (poll mode)
  ↓
ai_engine.py poll → scans Monday → reacts
```

**Daily Recommendation:** Keep GitHub Actions cron `0 8 * * *` (daily 8AM IST) as backup.
Even if it fires slightly late, daily is acceptable for recommendations.

### For Reliability ($7/mo): Option E — Render Cron Job

Replace UptimeRobot + Flask with a single Render Cron Job. No cold starts, no workarounds.

---

## Implementation Plan (If Approved)

### Phase 1 — Code Change (Immediate, ~2 min)
- [ ] `ai_engine.py`: Change recommendation status from `Ready to Generate` → `Done`

### Phase 2 — Polling Fix (Option B, ~30 min)
- [ ] Create `trigger_server/app.py` — Flask app with `/trigger` and `/health` endpoints
- [ ] Create `trigger_server/requirements.txt`
- [ ] Create `Procfile` for Render deployment
- [ ] Update `.github/workflows/content_ai.yml`:
  - Keep `*/5 * * * *` as fallback (GitHub's own cron)
  - Add `0 8 * * *` daily recommendation (instead of weekly)
- [ ] Deploy Flask app to Render (user action — takes ~10 min)
- [ ] Set up UptimeRobot monitor (user action — takes ~5 min)

### Phase 3 — Secrets Needed
- `GITHUB_TOKEN` — Generate at GitHub → Settings → Developer Settings → PAT (Classic)
  - Scope: `repo` + `actions:write`
- Add to Render environment variables

---

## What To Do Right Now

1. **Approve Phase 1** — I'll change the status to `Done` immediately (safe, 1-line change)
2. **Choose polling option** — Option B (free) or Option E ($7/mo)
3. **Approve Phase 2** — I'll build the trigger server and update workflows

> [!NOTE]
> The daily recommendation cron will always work even without UptimeRobot because
> a daily commit/push from the poll workflow itself counts as repo activity,
> preventing the 60-day inactivity disable.

> [!TIP]
> UptimeRobot free tier supports up to 50 monitors at 5-minute intervals.
> The Render free web service works fine — the Flask app responds in < 500ms
> before UptimeRobot considers it "down".
