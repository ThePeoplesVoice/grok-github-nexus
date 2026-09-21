## Nexus code review profile

When performing a review in this repository, optimize for context-aware, high-signal findings:

1. Prioritize correctness, security, and workflow safety over style.
2. Check alignment with `NORTH_STAR.md`, `CHECKS_AND_BALANCES.md`, and `config/gates.json` when changes touch governance, money, deploy, or public visibility paths.
3. For workflow changes, verify triggers, permissions, secret handling, and non-bot guardrails.
4. For `nexus/` runtime changes, verify artifact persistence remains consistent (`usage_stats`, `reputation`, Astra JSON, and badge paths where applicable).
5. Flag only actionable issues with concrete impact and file references.
