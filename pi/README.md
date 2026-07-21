# Pi Fleet extension

This directory contains the shareable Pi extension for Fleet Mind sessions. The
extension is intentionally kept beside the Fleet skill and canonical helper
scripts; it does not reimplement Fleet policy. The skill-facing reference is
[`../references/pi.md`](../references/pi.md).

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
/fleet attach --monitor <root>
                       attach a Pi-local read-only monitor without claiming Mind
/fleet monitor start 60s
/fleet monitor status
/fleet monitor stop
/fleet preflight [id]  run a read-only Fleet preflight
/fleet prepare [id]    produce a read-only launch assessment
/fleet detach <root>   detach an explicitly attached fleet
/fleet refresh         refresh read-only sensor state
/fleet compact         show one summary line per fleet
/fleet expand          show full detail rows for every fleet
/fleet focus <id>      expand one fleet and compact every other fleet
/fleet start [5m]      start the Pi-owned internal loop
/fleet update 10m      update the internal loop cadence
/fleet stop            stop the internal loop
```

Pi autocomplete suggests these subcommands as you type. Commands that select a
Fleet (`focus`, `detach`, `preflight`, `prepare`, and monitor detach) also offer
the currently attached or monitored Fleet IDs.

Mind attachment is session-scoped and recorded in Pi custom session entries so
a reload can restore it. A detected current-directory fleet is only a candidate;
it is never attached automatically. A foreign Mind attachment is refused unless
`--takeover` is supplied and the confirmation dialog approves that the other
Mind is dead or has yielded. The extension refuses to start its loop when a
canonical external `fleet-loop.py` loop is already active. Pi-owned loop intent
and cadence are stored in Pi session entries. After `/reload`, an active loop is
recreated with a fresh countdown at the saved cadence; the exact pre-reload
next-fire time is not preserved. A stopped loop remains stopped.

Monitor attachment is separate Pi-local state. It never claims `mind_session`,
never writes Vivi role records or `mind-baseline.json`, never emits `FLEET_CYCLE`, and
uses `fleet-sensors.py --no-watch` for read-only observation. Multiple monitored
fleets are aggregated in the human panel. Mind-attached and monitor-only fleets
use the same detail rows: mode/posture/cycle timing, Hands, Heads, Vivi counts,
and the last cycle summary. Mind-attached fleets show the internal loop
countdown; monitor-only timing is estimated from the observed baseline cadence.
Vivi PTY roles are shown from canonical `process_state` when their terminal
marker is unavailable, with low confidence preserved as a warning state.

The human-facing widget is intentionally denser than the model-facing tool
output. It uses colored state glyphs for active/waiting/failed roles and
separate managed Mind (`M`), Hand (`H`), and Head (`Hd`) classifications. Role
rows with no configured instances are omitted. Managed Minds are identified by
the configured `role: managed-mind` (or `role: mind`) even when the canonical
sensor currently carries that runtime in its `hands` collection. The panel also
includes a Vivi summary for work, mail, needs, pending RTM, and signal counts. `/fleet compact` reduces every fleet to one
summary line, `/fleet expand` restores all detail rows, and `/fleet focus <id>`
keeps the selected fleet expanded while compacting the rest. The view choice is
Pi session-local presentation state and does not modify Fleet or Vivi state.
The native Pi footer remains intact and carries a compact Fleet chip.

Each scheduled `FLEET_CYCLE` now includes a fresh, sanitized sensor preflight
from the extension. It contains role states, work/mail/need/RTM counts, and
signals; it does not include terminal tails or message bodies. The Mind still
owns interpretation and disposition and may refresh before acting.

The extension exposes `fleet_attach` and `fleet_detach` tools for explicit Mind
or monitor operations, plus read-only `fleet_preflight` and `fleet_prepare`
tools. It also exposes read-only `fleet_sensors`, `fleet_board`, and
`fleet_runtime` tools plus the `fleet_loop` lifecycle tool. Launching runtimes,
posture changes, reinitialization, doorbells, task-routing, steward control, and
other Fleet mutations remain outside the launch-assessment surface.
