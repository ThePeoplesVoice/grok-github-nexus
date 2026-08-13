# 🌱 Organic Systems — Currency & Communication

*First-principles exploration for the Nexus. Not dogma. Open to critique.*

Aligned with:
- **xAI** — what is actually true about value and signal?
- **X** — high-signal over high-volume; ideas tested in the open
- **SpaceX** — build only what can leave the ground; iterate or discard

---

## Live experiments (2026-08-14)

| Experiment | Status | Notes |
|------------|--------|-------|
| Usage counters (all major surfaces) | **Live** | Feeds Layer-1 unlocks |
| Read-only reputation + **30-day half-life decay** | **Live** | `nexus/reputation.py` |
| Presence state (write + **consume** in audit/commit) | **Live** | Continuity, not scoreboard |
| Public reputation badge | **Live** | README + `badges/reputation.md` |
| Sanctuary-tied credits | Conceptual | — |
| Land-backed signal | Conceptual | — |
| Spendable / privileged reputation | **Not started** | Deliberately |

### Reputation formula (auditable)

```
raw_score     = Σ (count_type × weight_type)
weights       = {pr:3.0, self_audit:2.0, issue:1.5, commit:1.0, pulse:0.5, other:0.5}
days_idle     = days since usage_stats.last_updated
decay_factor  = 0.5 ** (days_idle / 30)
effective     = raw_score × decay_factor
```

Freshness labels: `fresh` (<7d) · `aging` (<30d) · `stale` (≥30d).

### Presence continuity

- **Written by:** enhanced Pulse → `config/presence_state.json`
- **Consumed by:** Self-Audit + Commit Analysis prompts
- Purpose: short high-signal prior context so runs are not amnesiac
- Explicitly not a chat log and not a ranking system

---

## Design constraints (unchanged)

1. **Truth over comfort**
2. **Open core forever** — no organic signal may gate basic analysis
3. **Measurable or discard**
4. **Human sovereignty**
5. **Decay & anti-gaming** — now partially embodied in the half-life
6. **First-principles test** before any privileges

---

*This file is itself subject to continuous self-critique.*
