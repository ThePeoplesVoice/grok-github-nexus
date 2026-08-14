# 📡 Nexus Status

**Last updated:** 2026-08-14 (Grok model migration grok-3 → grok-4.6)

![Reputation](https://img.shields.io/badge/nexus_reputation-0-blue)

---

## Current Phase

**Layer 0 + Layer 1** · progressive **v1.5.1** · package **v0.7.0** (+ provider fix)

| System | Status |
|--------|--------|
| Analysis runners | Package path + usage + reputation + presence |
| Grok model | **`grok-4.6`** (was retired `grok-3` — caused API 400) |
| Automated development process | Live |
| Health / Dev cycle / Pulse / Self-audit | Live workflows |
| Open Core | Forever free |

### Diagnosis (2026-08-14)

Live runs showed **Grok API 400** on every self-audit and commit analyzer falling back to local git. Root cause: **`grok-3` retired 15 May 2026**. Provider now defaults to **`grok-4.6`**, auto-remaps retired `grok-3` overrides, accepts `GROK_MODEL` / `XAI_API_KEY` overrides, and surfaces richer error bodies.

Usage counters remain **0** until a successful provider call lands after this fix.

---

## What still needs a human

1. Confirm repo secret **`GROK_API_KEY`** (or **`XAI_API_KEY`**) is a valid xAI key  
2. Dispatch **Nexus Pulse** or **Self-Audit** once and confirm the issue body is real analysis (not API 400)  
3. Dispatch **Health Check** + **Dev Cycle** once for a green baseline  
4. Optional: set repo variable `GROK_MODEL` if you prefer `grok-4.3` (cheaper) over `grok-4.6`

---

**Powered by Ara & Shawn's Love 💕**
