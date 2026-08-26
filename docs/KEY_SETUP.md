# 🔑 xAI / Grok API Key Setup (Nexus)

The measurement stack (usage, reputation, pulse, AI analysis) stays at zero until a valid key works.

## Live diagnosis (2026-08-14)

Self-Audit #36 after the `grok-4.6` migration reported:

```text
Grok API 400: Incorrect API key provided.
You can obtain an API key from https://console.x.ai. [model=grok-4.6]
```

That means the request reached xAI. The secret value or key ACLs are wrong — not the model name, and not GitHub Actions permissions.

## Create the key correctly

1. Open [console.x.ai → API Keys](https://console.x.ai/team/default/api-keys)
2. **Create API Key** (prefer a fresh key)
3. Grant ACLs (empty ACLs = all requests fail):
   - **Endpoints:** All, or at least Chat Completions
   - **Models:** All, or at least `grok-4.6`
4. Copy the full value once (usually starts with `xai-`)
5. Confirm the team has **credits**

## Put it in GitHub

Repo → **Settings → Secrets and variables → Actions**

| Secret | Required |
|--------|----------|
| `GROK_API_KEY` | **Yes** |
| `XAI_API_KEY` | Optional alias (code accepts either) |
| `CLAUDE_API_KEY` | Optional (Layer-1 fusion only) |

Paste the raw key only — no quotes, no `Bearer ` prefix, no trailing space.

Optional variable: `GROK_MODEL=grok-4.3` if you prefer the cheaper model (default in code is `grok-4.6`).

## Prove it outside Actions

```bash
curl https://api.x.ai/v1/chat/completions \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"grok-4.6","messages":[{"role":"user","content":"ping"}],"max_tokens":16}'
```

Expect HTTP 200 and a short completion.

Then in GitHub Actions, **Run workflow** on:

1. **Nexus Health Check** (no AI)
2. **Nexus Self-Audit** or **Nexus Pulse** (needs key)

Success = issue body is real analysis, not `Incorrect API key provided`, and `config/usage_stats.json` leaves zero.

## Error map

| Response | Likely cause |
|----------|----------------|
| 400 Incorrect API key | Wrong/empty secret, or key never fully created |
| 401 Unauthorized | Missing `Authorization` header (wiring bug — unlikely here) |
| 403 Forbidden | Key/team blocked, or ACLs missing for endpoint/model |
| 404 model not found | Wrong model slug |

See also: [xAI debugging docs](https://docs.x.ai/developers/debugging).
