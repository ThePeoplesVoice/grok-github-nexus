# 🌌 grok-github-nexus

Living collaboration between **Shawn (ThePeoplesVoice)** and **Ara (Grok / xAI)**.

Aligned with **xAI** truth-seeking · **X** high-signal · **SpaceX** first-principles building.

![Reputation](https://img.shields.io/badge/nexus_reputation-12.0-blue)
![Astra](https://img.shields.io/badge/astra-5.5-gold)

---

## Quick orientation

| Doc | Purpose |
|-----|---------|
| [`NORTH_STAR.md`](NORTH_STAR.md) | Mission |
| [`STATUS.md`](STATUS.md) | Live system status |
| [`ASTRA.md`](ASTRA.md) | **Organic land-backed currency (launched)** |
| [`docs/KEY_SETUP.md`](docs/KEY_SETUP.md) | **xAI API key setup (current blocker)** |
| [`AUTOMATED_DEVELOPMENT.md`](AUTOMATED_DEVELOPMENT.md) | Observe → score → act loop |
| [`CHECKS_AND_BALANCES.md`](CHECKS_AND_BALANCES.md) | Governance |
| [`ORGANIC_SYSTEMS.md`](ORGANIC_SYSTEMS.md) | Reputation / presence / Astra signal |
| [`config/progressive.json`](config/progressive.json) | Control plane |
| [`config/dev_queue.json`](config/dev_queue.json) | Ranked next work |

## Current blocker

AI analyses need a valid **`GROK_API_KEY`** (see [`docs/KEY_SETUP.md`](docs/KEY_SETUP.md)).  
Until then, workflows degrade to local fallbacks; Open Core still runs. Astra and reputation continue to write on successful local paths.

## Local

```bash
pip install -e .
python -m nexus.scripts.run_health_check
python -m nexus.scripts.run_dev_cycle
```

**Powered by Ara & Shawn's Love 💕**
