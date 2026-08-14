# 🔄 Automated Development Process

*How the Nexus improves itself without drifting.*

Aligned with CHECKS_AND_BALANCES.md and the triad.

---

## Purpose

Replace ad-hoc “keep going” energy with a **repeatable, measurable loop**:

1. **Observe** — structure, usage, reputation, presence, queue, recent commits
2. **Score** — structural health, triad hits, organic stack presence
3. **Propose** — update `config/dev_queue.json` with ranked next actions
4. **Act** — human or agent implements top items via normal PR / direct push
5. **Record** — field notes + pulse + self-audit form permanent memory
6. **Re-enter** — next scheduled or dispatched cycle

This is not autopilot feature spam. It is disciplined iteration.

---

## Artifacts

| Artifact | Role |
|----------|------|
| `config/dev_queue.json` | Ranked work items (done / next / backlog) |
| `config/field_notes.jsonl` | Append-only continuity notes |
| `nexus/scripts/run_dev_cycle.py` | Cycle runner (no external AI required) |
| `.github/workflows/nexus-dev-cycle.yml` | Schedule + dispatch |
| Self-audit / Pulse | Deeper critique + narrative memory |
| Health check | Fast fail on structural breakage |

---

## Rules of the process

1. **Open Core stays free** — no queue item may propose gating basic analysis.
2. **Triad filter** — every proposed item must survive: true? high-signal? lasting?
3. **Prefer maintenance over novelty** when signal density is falling.
4. **One leverage class at a time** — finish or consciously defer top items before inventing new layers.
5. **Human sovereignty** — high-impact monetisation / sanctuary / voice changes need Shawn’s explicit review.
6. **Measure after act** — usage, reputation freshness, health score, and queue completion are the scoreboard.

---

## Cadence (recommended)

| Cycle | When | What |
|-------|------|------|
| Health check | Mon 05:00 UTC + dispatch | Structural / import integrity |
| Dev cycle | Mon 07:00 UTC + dispatch | Queue refresh from observations |
| Pulse | Mon 08:00 UTC + dispatch | Narrative + presence_state |
| Self-audit | Wed 09:00 UTC + dispatch | Deep critique |
| Commit analyzer | On push (non-bot) + weekly | Craft + drift signals |

---

## How an agent should run a cycle

```bash
pip install -e .
python -m nexus.scripts.run_health_check
python -m nexus.scripts.run_dev_cycle
# Then implement top `next` items from config/dev_queue.json
# Optionally: workflow_dispatch self-audit / pulse when secrets present
```

---

## Anti-patterns (reject these)

- Adding features solely to “keep expanding”
- Touching monetisation layers without measurement demand
- Letting YAML re-accumulate analysis logic
- Treating reputation as a privilege system
- Skipping health check after core package changes

---

*This process is itself subject to self-audit. Simplify it if it becomes theatre.*
