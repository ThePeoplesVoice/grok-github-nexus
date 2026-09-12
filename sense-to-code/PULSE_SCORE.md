# One score shape

GRO-5 owns this dialect. Sense Lab does not get a second one.

## Pulse record (frozen)

```
source
id
severity   0–1
intent     fix | ship | pay | ignore
link
```

Dedup on `source + id`. Feeders write that block at the top of a Pulse-labelled Linear issue.

## Sense cell projects onto it — it does not replace it

| Sense cell | Pulse field | Rule |
|---|---|---|
| operator + lab | source | `sense-lab` or `control-01` |
| cell id | id | e.g. `cell-cal-v0` |
| precision × \|error\| | severity | 0 = noise, 1 = must act |
| policy | intent | see map below |
| lab URL or ticket | link | one URL |

### Policy → intent

| Sense policy | Pulse intent |
|---|---|
| measure / spawn / drag | ignore (local lab) or fix if it blocks work |
| leave | ignore |
| abort / stop | ignore |
| call (site / customer) | ship |
| pay-shaped hole | pay |
| broken feeder / test / deploy | fix |

If the policy is not work, severity stays 0 and intent is `ignore`. That keeps Sense play off the Pulse chamber.

## Worked example (this night)

```
source:    sense-lab
id:        cell-cal-v0
severity:  0
intent:    ignore
link:      https://linear.app/grok-github-nexus/issue/GRO-12
```

felt_true on volume/pitch is a calibration fact. It is not a Vercel fail. Severity 0.

## Not this issue

A new JSON standard. A second Pulse. Merging Voice #167. Fifty internet meaning protocols (already out on GRO-5).
