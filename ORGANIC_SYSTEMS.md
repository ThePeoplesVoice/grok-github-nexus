# 🌱 Organic Systems — Currency & Communication

*First-principles exploration for the Nexus. Not dogma. Open to critique.*

Aligned with:
- **xAI** — what is actually true about value and signal?
- **X** — high-signal over high-volume; ideas tested in the open
- **SpaceX** — build only what can leave the ground; iterate or discard

This document exists so expansion does not drift into fashion. Every proposal must survive continuous self-critique (see `CHECKS_AND_BALANCES.md`).

---

## Why this exists

Layer 2 (x402 / USDC) is a clear, practical micropayment path. It is not the only path.

The sanctuary vision and the open-core Nexus both suggest a deeper question:

> What forms of value and presence can emerge *organically* from contribution, attention, and place — without forcing them into purely financial abstraction too early?

Organic systems here mean: systems that grow from actual work, reputation, and shared presence rather than being imposed top-down as tokens-first designs.

---

## Native value candidates (currency-like)

### 1. Contribution Reputation Credits — **first experiment live**
- Earned by: successful analyses (weighted by type), future: merged PRs, high-signal issues.
- **Live now:** read-only score in `config/reputation.json`, computed by `nexus/reputation.py`.
- Weights (auditable): pr=3.0 · self_audit=2.0 · issue=1.5 · commit=1.0 · pulse=0.5
- Not spendable. Does not gate Open Core.
- Risk: gaming. Mitigation: transparent weights, continuous critique, no privileges yet.

### 2. Sanctuary-Tied Credits
- Explicitly linked to land / sanctuary vision.
- Earned by work that advances preservation, documentation, or public understanding of place.
- Still conceptual.

### 3. Land-Backed Signal
- Transparent ledger of *signal* tied to stewardship milestones — not a security.
- Still conceptual.

### 4. Attention / Presence Units
- Coherent attention is scarce.
- **First step live:** `config/presence_state.json` written by the enhanced Pulse — compressed context for continuity between runs, not a scoreboard.

**Non-negotiable:** none of the above replace or gate the forever-free Open Core (Layer 0).

---

## Communication candidates (beyond comments)

### 1. Presence Pulses — **enhanced and live**
- Weekly (and on-demand) high-signal digests via `nexus/scripts/run_pulse.py`.
- Now includes: full usage breakdown, reputation snapshot, Ara reflection, and compressed presence state.

### 2. Shared Field Notes
- Append-only, timestamped observations under a clear voice label.
- Still conceptual.

### 3. Multi-Model Fusion as Dialogue
- Already live: Grok primary + Claude complementary across PR / Issue / Commit / Self-Audit.
- Expansion path: make disagreement more visible as dialogue rather than a single fused blob.

### 4. Place-Linked Broadcasts
- Occasional grounded updates from sanctuary context when relevant.
- Still conceptual.

---

## Relationship to existing layers

| Layer | Role relative to organic systems |
|-------|----------------------------------|
| 0 Open Core | Forever free; organic systems must not enclose it |
| 1 Progressive Unlocks | Usage + contribution feed unlocks; reputation amplifies signal honestly |
| 2 x402 / USDC | Practical cash path for premium depth; coexists with organic signal |
| 3 Network / Sanctuary | Natural home for sanctuary-tied credits and revenue share |

---

## Design constraints (checks & balances)

1. **Truth over comfort** — do not invent value that is not backed by real work or real place.
2. **Open core forever** — no organic currency may gate basic analysis.
3. **Measurable or discard** — if a credit system cannot be audited, it is theatre.
4. **Human sovereignty** — agents propose and assist; humans decide binding outcomes.
5. **Decay & anti-gaming** — reputation and presence signals should remain critique-able and revisable.
6. **First-principles test** — before any activation of privileges: “Does this help us see more clearly and build what lasts, or does it mainly create a new scoreboard?”

---

## Current status (2026-08-14)

| Experiment | Status |
|------------|--------|
| Usage counters (all major surfaces) | **Live** |
| Read-only reputation surface | **Live** (`nexus/reputation.py` + `config/reputation.json`) |
| Enhanced presence pulse + presence_state | **Live** |
| Sanctuary-tied credits | Conceptual |
| Land-backed signal | Conceptual |
| Spendable / privileged reputation | Not started (deliberately) |

Next concrete levers:
1. Optional decay function on reputation components.
2. Surface reputation score in STATUS.md or a tiny public badge later.
3. Field-notes experiment only if continuity pain becomes real.

---

*This file is itself subject to continuous self-critique. Expand, prune, or delete proposals that fail the triad.*
