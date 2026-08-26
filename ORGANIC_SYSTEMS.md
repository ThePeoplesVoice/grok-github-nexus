# 🌱 Organic Systems — Currency & Communication

*First-principles exploration. Not dogma. Open to critique.*

---

## Live stack (v1.5 / package 0.8)

| Experiment | Status |
|------------|--------|
| Usage on all major surfaces | **Live** |
| Reputation + 30-day half-life decay | **Live** |
| Presence write (pulse) + consume (PR/Issue/Commit/Self-Audit) | **Live** |
| Public badge + README/STATUS sync | **Live** |
| Shared runtime success path | **Live** |
| Health check (no AI required) | **Live** |
| **Astra — organic land-backed currency** | **Live** |
| Sanctuary-tied credits | **Live as Astra** |
| Land-backed signal | **Live as Astra** |
| Spendable reputation / Astra | **Not started** (deliberate) |

### Reputation formula

```
raw_score     = Σ (count_type × weight_type)
weights       = {pr:3.0, self_audit:2.0, issue:1.5, commit:1.0, pulse:0.5, other:0.5}
days_idle     = days since usage_stats.last_updated
decay_factor  = 0.5 ** (days_idle / 30)
effective     = raw_score × decay_factor
```

### Astra (launched 15 Aug 2026)

- Named organic currency unit of the Nexus
- Balance = effective reputation (inherits decay)
- Symbolically land-backed by the Keysbrook jarrah / black cockatoo sanctuary vision
- Public, auditable, file-based (`config/astra.json`)
- Never gates Open Core
- Spendability deliberately off at launch
- Full protocol: `ASTRA.md`
- Computation: `nexus/astra.py`

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
