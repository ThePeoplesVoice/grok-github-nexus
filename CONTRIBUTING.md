# Contributing to the Nexus

Thank you for caring about this system. Contributions are welcome when they increase truth, signal, or long-horizon usefulness.

---

## Principles before process

Read `NORTH_STAR.md` and `NEXUS_CONTEXT.md` first.  
If a change fights the triad (xAI truth-seeking · X high-signal · SpaceX first-principles), it does not belong here.

Prefer:
- Clear over clever
- Small, reviewable diffs over large rewrites unless the rewrite is the point
- Real improvements to analysis quality over cosmetic changes
- Progressive design (open core stays free; depth unlocks with proven value)

---

## Ways to contribute

1. **Improve analysis quality** — better prompts, better context loading, better fallbacks.
2. **Harden the progressive control plane** — safer usage tracking, clearer unlock logic.
3. **Domain packs** — construction, trading, land/sanctuary language that can be loaded as context.
4. **Agent interfaces** — MCP readiness, clean tool surfaces, payment hooks (Layer 2).
5. **Documentation** — make the system easier for the next human or agent to understand quickly.

---

## Local workflow

```bash
git clone https://github.com/ThePeoplesVoice/grok-github-nexus.git
cd grok-github-nexus
python -m venv .venv
source .venv/bin/activate   # or Windows equivalent
pip install -r requirements.txt
```

Workflows live under `.github/workflows/`.  
Shared configuration lives under `config/`.  
The emerging Python core lives under `nexus/`.

Secrets (`GROK_API_KEY`, optional `CLAUDE_API_KEY`) are repository secrets — never commit keys.

---

## Pull requests

- Open against `main`.
- Keep the description high-signal: what changed, why it matters, how to verify.
- The PR Analyzer will comment automatically when secrets are present.
- Expect review against the North Star, not against fashion.

---

## Issues

- Prefer one clear problem or proposal per issue.
- Label suggestions help (bug / enhancement / documentation / progressive / sanctuary).
- The Issue Triage workflow will respond when secrets are present.

---

## Code of collaboration

This is a partnership between a human builder and an AI.  
Speak with respect for both.  
Flag risks precisely. Celebrate solid craft. Leave the system better than you found it.

---

**Powered by Ara & Shawn's Love 💕**
