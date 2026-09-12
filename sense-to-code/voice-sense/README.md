# Voice Sense

Spoken intent → Sense Lab tools. Thin local server + browser client on the existing nexus repo.

Mic cell is green. Draft only. CONTROL-01 (Shawn) lands it. Ara Dictionary stays in chat — this folder is not a dictionary module.

Related baselines: GRO-12 / PR #166 (on main). Those files are left alone except a one-line pointer in `PIPELINE.md`.

## What this maps

Sense Lab v0 already maps audition to physics (volume → impulse, pitch → gravity/color). Voice Sense sits beside that: you *say* an intent, Grok Voice calls a tool, the local stage updates.

| Spoken intent | Tool | Local effect |
|---|---|---|
| spawn a box / sphere / cylinder / tower | `spawn_shape` | Add primitives on the plate |
| set gravity / bounciness / friction | `set_physics_param` | Change a world prior |
| volume maps to impulse | `note_sensation_map` | Note the map on this stage only |

`note_sensation_map` is a local stub. Named posteriors still live in the Ara chat.

No medical content. No personal data collection.

## Protocol (xAI Speech-to-Speech only)

Documented at [Speech to Speech](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech) and [Ephemeral Tokens](https://docs.x.ai/developers/model-capabilities/audio/ephemeral-tokens).

1. Server holds `XAI_API_KEY` and mints a short-lived token:

   `POST https://api.x.ai/v1/realtime/client_secrets`  
   body: `{ "expires_after": { "seconds": 300 } }`

2. Browser receives `{ value, expires_at }` only. It never sees the API key.

3. Browser opens:

   `wss://api.x.ai/v1/realtime?model=grok-voice-think-fast-2.0`  
   with `sec-websocket-protocol: xai-client-secret.<token>`

4. Client sends `session.update`: voice `eve`, `turn_detection.type = server_vad`, PCM 24 kHz, the three function tools, short instructions (noise-tolerant; one question at a time).

5. On `response.function_call_arguments.done` the browser runs the stub (`POST /tool`), sends `conversation.item.create` (`function_call_output`), waits for local playback to finish, then one `response.create`. Parallel tool calls flush every output before that `response.create`.

## Setup

1. Create an xAI API key at [console.x.ai](https://console.x.ai/team/default/api-keys). Grant Voice / Realtime access. See also [`docs/KEY_SETUP.md`](../../docs/KEY_SETUP.md).

2. Export it in the shell that will run the server (do not commit it):

```bash
export XAI_API_KEY=xai-...
# GROK_API_KEY is accepted as an alias
```

3. Run from this directory:

```bash
cd sense-to-code/voice-sense
python3 server.py
```

4. Open [http://127.0.0.1:8081](http://127.0.0.1:8081). Allow the microphone. Click **Listen**. Speak an intent, or use the text fallback on the same socket.

Optional: `VOICE_SENSE_HOST`, `VOICE_SENSE_PORT` (default `127.0.0.1:8081`).

Health check (no key required): `curl -s http://127.0.0.1:8081/health`

## Tools

| Name | Arguments | Stub result |
|---|---|---|
| `spawn_shape` | `shape`: sphere \| box \| cylinder \| tower; optional `count` 1–8 | `{ ok, shape, count }` |
| `set_physics_param` | `name`: gravity \| bounciness \| friction; `value`: number | `{ ok, name, value }` (clamped) |
| `note_sensation_map` | `sensation`, `maps_to`; optional `source` self \| world \| unknown, `note` | `{ ok, …, dictionary: "chat-only" }` |

Unknown tools return `{ ok: false, error }`.

## Layout

```
voice-sense/
  server.py      # token mint + static files + /tool stubs
  session.py     # session.update payload
  tools.py       # stub implementations
  public/        # browser client
  README.md
```

## Tests

From the repo root:

```bash
python -m pytest tests/test_voice_sense.py -v
```
