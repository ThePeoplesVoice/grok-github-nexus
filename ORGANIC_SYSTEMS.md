# 🌱 Organic Systems — Currency & Communication

*First-principles exploration. Not dogma. Open to critique.*

---

## Live stack (v1.5 / package 0.6)

| Experiment | Status |
|------------|--------|
| Usage on all major surfaces | **Live** |
| Reputation + 30-day half-life decay | **Live** |
| Presence write (pulse) + consume (PR/Issue/Commit/Self-Audit) | **Live** |
| Public badge + README/STATUS sync | **Live** |
| Shared runtime success path | **Live** |
| Health check (no AI required) | **Live** |
| Sanctuary-tied credits | Conceptual |
| Land-backed signal | Conceptual |
| Spendable reputation | **Not started** (deliberate) |

### Reputation formula

```
raw_score     = Σ (count_type × weight_type)
weights       = {pr:3.0, self_audit:2.0, issue:1.5, commit:1.0, pulse:0.5, other:0.5}
days_idle     = days since usage_stats.last_updated
decay_factor  = 0.5 ** (days_idle / 30)
effective     = raw_score × decay_factor
```

### Presence continuity

- Written by Pulse → `config/presence_state.json`
- Consumed by PR, Issue, Commit, Self-Audit prompts
- Continuity context only — not a ranking system

### Hard constraints

See `CHECKS_AND_BALANCES.md` items 7–9:
- Organic signal never gates Open Core
- Reputation must decay
- Presence is continuity, not ranking

---

*Subject to continuous self-critique.*
