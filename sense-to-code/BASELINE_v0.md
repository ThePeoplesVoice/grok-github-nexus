# Sense Lab baseline v0

Observed 2026-09-13 from live link + CONTROL-01 report + this-chat walkthrough.

## Gate

- Eyebrow: PHYSICAL SIMULATION
- Title: Sense Lab
- Copy: Spawn spheres, boxes, and cylinders. Drag them. Stack a tower. The microphone turns volume into impulse and pitch into gravity and color.
- CTA: Enter Lab
- Note: MICROPHONE OPTIONAL

## Lab chrome

| Region | What is there |
|---|---|
| Top left | PHYSICAL SIMULATION, Sense Lab, object count |
| Top right | Mic chip: MIC / NO MIC, Hz (blank when no mic) |
| Left dock | Sphere, Box, Cylinder, Tower, Clear (trash) |
| Right dock | Gravity (shown 9.8), Bounciness (shown 0.34), Friction (shown 0.62) |
| Bottom left | SENSATION → PARAMETER legend: Volume→Impulse, Pitch→Gravity/color |
| Stage | Dark circular table on a grid. Gravity-bound primitives. |

Default scene at Enter: mixed tower of boxes, two spheres, one cylinder on the plate (~9 objects). Mic not granted in this-chat browser (NO MIC / — Hz). Same as CONTROL-01 until the browser grant.

## Mapping contract (do not silently change)

```
audition.volume  →  world.impulse     (exafferent → physics)
audition.pitch   →  world.gravity
                 →  display.color
hand.drag        →  object.pose       (self-generated)
slider.*         →  world.params      (self-generated prior)
clear            →  reset
```

Agency tags:

- Mic stream = world (or unknown until calibrated to *this* voice).
- Drag / spawn / sliders / clear = self.
- Collapse of a tower after a shout = error if you predicted it would stand.

## Missing from v0 (named holes, not bugs)

- No explicit prediction layer.
- No error cell.
- No precision / reweight control.
- No self/world badge on the HUD.
- No policy column (what action this sensation licenses).
- No stop control beyond closing the tab.
- No export of a posterior JSON for Pulse.
- SSR and legend were still being polished at handoff; treat layout as live-but-young.

## Calibration protocol (CONTROL-01)

1. Enable mic in the browser that will be used.
2. Note ambient Hz at silence (prior).
3. One short impulse (clap or syllable). Watch whether objects move. That is volume→impulse.
4. Hum low then high. Watch gravity and color. That is pitch.
5. Speak the sentence: true / false / partial.
6. Report one cell to Dictionary: modality, self-or-world, predicted-or-error.

Until that report, Dictionary will not invent a felt mapping.

## Control log — 2026-09-13 ~02:04 AWST

CONTROL-01 played the v0 set. Specific controls logged as exercised. felt_true open until marked.

| Control | Type | Mapping / effect | Agency | Exercised | felt_true |
|---|---|---|---|---|---|
| Sphere | spawn | add sphere to plate | self | yes | |
| Box | spawn | add box to plate | self | yes | |
| Cylinder | spawn | add cylinder to plate | self | yes | |
| Tower | spawn | stack boxes | self | yes | |
| Clear | reset | trash all objects | self | yes | |
| Drag | pose | hand moves object | self | yes | |
| Gravity slider | prior | world.gravity (default 9.8) | self | yes | |
| Bounciness slider | prior | restitution (default 0.34) | self | yes | |
| Friction slider | prior | friction (default 0.62) | self | yes | |
| Mic enable | gate | grant audition | self | no (NO MIC) | n/a |
| Volume | sensation | → impulse | world | blocked | |
| Pitch | sensation | → gravity / color | world | blocked | |
| Hz meter | display | pitch readout | observe | blank | |
| Enter Lab | gate | gate → lab | self | yes | |
