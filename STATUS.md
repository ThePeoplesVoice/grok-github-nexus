# 📡 Nexus Status

**Last updated:** 2026-08-14 (presence continuity · reputation decay · public badge)

![Reputation](https://img.shields.io/badge/nexus_reputation-0-blue)

This file is the living pulse of the repository. It is intended to be honest, current, and useful to both humans and agents.

---

## Current Phase

**Layer 0 (Open Core) + Layer 1 (Progressive Unlocks) — live and gated**

- Grok primary + Claude complementary across PR / Issue / Commit / Self-Audit
- Real PR diff ingestion live
- **Usage tracking live on all major surfaces**
- **Reputation v0.2** — raw + effective score with **30-day half-life decay**
- **Presence continuity** — self-audit + commit analysis inherit `presence_state.json`
- **Public reputation badge** — README + `badges/reputation.md`
- `nexus/` package at **v0.5.0**
- Bot-actor guards prevent usage-commit feedback loops

---

## System Surface

| Component | Status | Notes |
|-----------|--------|-------|
| Usage tracking | **Live** | self_audit · pr · issue · commit · pulse |
| Reputation + decay | **Live** | effective = raw × 0.5^(days_idle/30) |
| Presence state | **Live** | written by pulse; consumed by audit + commit |
| Public badge | **Live** | README + badges/reputation.md |
| PR / Issue / Commit / Self-Audit / Pulse | **Package path** | YAML heredocs retired for runners |
| `nexus/` package | **v0.5.0** | + presence module |
| ORGANIC_SYSTEMS.md | Live | Documents experiments + constraints |
| x402 / sanctuary layers | Designed | Not activated |

---

## Known Gaps (honest)

1. Reputation still usage-derived only (no merged-PR graph yet).
2. Presence state is consumed by audit/commit prompts but not yet by PR/issue runners.
3. Badge score in README is static until the next reputation refresh commits an update (or a tiny action rewrites it).
4. Claude credits can go to zero; degrade path remains clean.
5. Layer 2 / 3 still inactive by design.

---

## Direction of Travel

1. Optionally sync the README badge on every reputation refresh (already writing `badges/reputation.md`).
2. Feed presence into PR/issue prompts if continuity proves useful in audit/commit.
3. Keep reputation privileges **off** until the signal is clearly load-bearing.
4. Continuous self-critique remains non-negotiable.

---

**Powered by Ara & Shawn's Love 💕**  
*Aligned with xAI truth-seeking · X high-signal · SpaceX first-principles building*
