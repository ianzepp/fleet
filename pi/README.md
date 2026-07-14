# Pi Fleet extension

This directory contains the shareable Pi extension for Fleet Mind sessions. The
extension is intentionally kept beside the Fleet skill and canonical helper
scripts; it does not reimplement Fleet policy.

## Local development

From a Pi checkout, load the extension directly:

```bash
pi -e /Users/ianzepp/work/ianzepp/fleet/pi/extensions/fleet.ts
```

Or install the Fleet repository as a Pi package:

```bash
pi install /Users/ianzepp/work/ianzepp/fleet
```

A shared git install should use a pinned commit or tag:

```bash
pi install git:github.com/ianzepp/fleet@<tag-or-commit>
```

Review the package before installation: Pi extensions run with full system
access, and this extension invokes Fleet's Python and shell helpers.

## Operator commands

```text
/fleet                 show attached fleets and loop state
/fleet attach .        detect and explicitly attach the current fleet
/fleet attach <root>   attach another fleet root
/fleet attach --takeover <root>
                       take over after confirming the other Mind is dead/yielded
/fleet detach <root>   detach an explicitly attached fleet
/fleet refresh         refresh read-only sensor state
/fleet start [5m]      start the Pi-owned internal loop
/fleet update 10m      update the internal loop cadence
/fleet stop            stop the internal loop
```

Attachment is session-scoped and recorded in Pi custom session entries so a
reload can restore it. A detected current-directory fleet is only a candidate;
it is never attached automatically. A foreign Mind attachment is refused unless
`--takeover` is supplied and the confirmation dialog approves that the other
Mind is dead or has yielded. The extension refuses to start its loop when a
canonical external `fleet-loop.py` loop is already active.

The human-facing widget is intentionally denser than the model-facing tool
output. It uses colored state glyphs for active/waiting/failed roles, compact
Hands (`H`) and Heads (`Hd`) rows, and a Vivi summary for work, mail, needs,
pending RTM, and signal counts. The native Pi footer remains intact and carries
a compact Fleet chip.

Each scheduled `FLEET_CYCLE` now includes a fresh, sanitized sensor preflight
from the extension. It contains role states, work/mail/need/RTM counts, and
signals; it does not include terminal tails or message bodies. The Mind still
owns interpretation and disposition and may refresh before acting.

The first implementation exposes read-only `fleet_sensors`, `fleet_board`, and
`fleet_runtime` tools plus the `fleet_loop` lifecycle tool. Steward, posture,
reinitialization, doorbell, task-routing, and other Fleet mutations remain
outside this initial read-only surface.
