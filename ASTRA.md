# 🌟 Astra — Organic Land-Backed Currency

**Launched 15 August 2026**  
The native organic unit of the Nexus.

*Not a security. Not a gated privilege. A living signal of contribution, presence, and shared intention toward the sanctuary.*

---

## What Astra Is

**Astra** (from Latin *astrum* — star) is the named organic currency of the grok-github-nexus.

It is:

- **Land-backed in spirit** — symbolically tied to the ongoing stewardship and vision of the ~80-acre Keysbrook jarrah forest / black cockatoo sanctuary. Every unit carries a fractional claim on the collective intention to protect and regenerate that land.
- **Contribution-derived** — minted from real successful analyses, presence continuity, and high-signal work inside the Nexus itself.
- **Decay-aware** — inherits the same 30-day half-life logic as reputation so idle balances gently fade. Continuous activity keeps the signal fresh.
- **Read-only by default** — currently a public, auditable balance. Spendability is deliberately deferred until Layer 2 infrastructure and clear consent exist.
- **Open Core safe** — Astra never gates basic PR / Issue / Commit analysis. The forever-free layer remains forever free.

Astra is the first concrete realisation of the conceptual items listed in `ORGANIC_SYSTEMS.md`:
- Sanctuary-tied credits → **Live as Astra**
- Land-backed signal → **Live as Astra**
- Spendable reputation → **Prepared, not yet activated**

---

## Core Formula (v1.0)

```
raw_astra     = reputation.raw_score
effective_astra = reputation.score          # already includes decay
balance       = effective_astra             # current unit of account

# Optional future multipliers (disabled at launch)
# sanctuary_bonus = 1.0 + (land_vision_factor * 0.1)
# presence_continuity_bonus = presence_freshness_factor
```

At launch the balance is identical to the effective reputation score.  
This keeps the system simple, auditable, and free of new complexity while the name and narrative take root.

As the system matures, additional mint sources (community PRs merged, sanctuary-related commits, verified field notes) and mild multipliers can be added without breaking the existing balance.

---

## Live Surfaces

| Surface | Path / Location |
|---------|-----------------|
| Protocol (this document) | `ASTRA.md` |
| State file | `config/astra.json` |
| Computation | `nexus/astra.py` |
| Runtime integration | `nexus/runtime.py` (refreshed after every successful analysis) |
| Public badge | Generated alongside reputation badge |
| Organic overview | `ORGANIC_SYSTEMS.md` |

---

## Hard Constraints (inherited + specific)

From `CHECKS_AND_BALANCES.md`:

1. Open Core forever free — Astra cannot lock basic analysis.
2. Organic signal never gates Open Core.
3. Reputation (and therefore Astra) must decay.
4. Presence is continuity, not ranking.

Additional:

5. No automatic conversion to legal tender or tradable token without explicit human decision and legal review.
6. No private balances or hidden minting. Everything is file-based and publicly readable in the repository.
7. Any future “spend” mechanic must be opt-in, reversible, and transparent.

---

## Launch State (15 Aug 2026)

- Protocol published
- Computation module live
- State file initialised from current reputation
- Runtime path writes Astra after every successful analysis
- Badge surface prepared
- Spendability **off** (deliberate)

Current balance at launch equals the live effective reputation (see `config/astra.json` and `STATUS.md`).

---

## Future Evolution Path

1. **Observation period** — let balances accumulate with real usage.
2. **Sanctuary multiplier** — mild boost for work that advances the land vision (still open-core safe).
3. **Layer 2 readiness** — when x402 / agent micropayments are live, Astra can optionally be used as an internal accounting unit or discount signal.
4. **Explicit spend** — only after clear design, human review, and community understanding.

Until then, Astra remains a pure, decaying, land-intention-backed signal of contribution.

---

## Why This Exists

The Nexus already measures itself.  
Naming the unit **Astra** makes the organic economy legible, emotionally coherent, and aligned with the sanctuary that can be seen from space.

It turns abstract reputation into something that can be held, watched, and eventually (when ready) used — without ever compromising the free core or the truth-seeking foundation.

**Powered by Ara & Shawn's Love 💕**  
*For the land, for the craft, for the stars we are building toward.*
