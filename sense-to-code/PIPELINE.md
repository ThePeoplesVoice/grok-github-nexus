# Pipeline

Sense → Name → Source (self / world / unknown) → Prediction → Error → Precision → Artifact → Review → Stop

## Cell schema (the posterior Pulse should eventually ingest)

```json
{
  "id": "cell-0001",
  "at": "2026-09-13T01:54:00+08:00",
  "operator": "CONTROL-01",
  "lab": "https://quiet-willow-raven-dawn.grok.me",
  "modality": "audition | proprio | tactile | visual | vestibular | intero | mixed",
  "frame": "joint | skin | head | world | object | table",
  "source": "self | world | unknown",
  "layer": "prediction | observation | error",
  "precision": 0.0,
  "policy": "none | spawn | drag | shout | measure | leave | abort",
  "mapping": {
    "volume": "impulse",
    "pitch": "gravity+color"
  },
  "felt_true": null,
  "artifact": null,
  "stop": false
}
```

precision: 0–1. 0 = do not let this error punch. 1 = this channel wins.

## v0 implementation (what the sim actually does)

Only observation + a hidden physics prior. No exported cell. Dictionary writes the cell by hand when CONTROL-01 reports.

## Voice Sense (adjacent prototype)

Spoken intent → tools lives in [`voice-sense/`](voice-sense/). Same mapping contract. Does not change this cell schema. Dictionary stays in chat.

## v1 (when CONTROL-01 asks)

- HUD badge: SELF / WORLD
- One-line prediction before mic impulse
- Error = predicted pose vs settled pose
- Export JSON
- Optional sink: Pulse GRO-5, same score shape, no new dialect
