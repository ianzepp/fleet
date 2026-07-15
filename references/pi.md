# Pi Fleet Mind reference

This reference applies when the Fleet skill is running inside the shareable Pi
Fleet extension. It describes the additional model-callable tools, operator
commands, lifecycle boundaries, and human-facing summaries. It does not replace
Fleet policy in this skill or create a second Fleet control plane.

## Activation

The extension must be loaded in Pi:

```bash
pi -e /Users/ianzepp/work/ianzepp/fleet/pi/extensions/fleet.ts
```

Or install the Fleet package:

```bash
pi install /Users/ianzepp/work/ianzepp/fleet
```

A detected `.vivi/fleet.json` in the current directory is only a **candidate**.
Pi never becomes Mind automatically. The operator or the user must explicitly
request attachment.

## Operating invariant

> Pi may present and operate the canonical Fleet state, but it must never
> replace Fleet/Vivi policy with a Pi-local control plane.

Mind attachment is canonical advisory state. Monitor attachment is Pi-local
read-only state. Read-only observations never wake an LLM, emit `FLEET_CYCLE`,
advance watch cursors, or modify Fleet files.

## Recommended Pi workflow

For a user asking Pi to become Mind and get ready:

```text
1. fleet_attach(mode="mind", ...)
2. fleet_preflight()
3. Load this skill and the repository's normal warm-up/context references.
4. fleet_prepare()
5. Report blockers and the proposed launch actions.
6. Wait for explicit operator confirmation before launch side effects.
```

`fleet_preflight` is the Fleet-specific operational inspection. Generic
repository warm-up remains useful for understanding code, history, and local
`AGENTS.md` instructions, but it is not a substitute for Fleet preflight.

There is currently no `fleet_launch` tool. Starting runtimes, waking agents,
changing posture, filing tasks, reinitializing panes, and steward operations
remain explicit Fleet operations governed by [`launch.md`](launch.md),
[`mind-cycle.md`](mind-cycle.md), and the other canonical references.

## Model-callable tools

All tools return a concise text summary plus structured details. Tool results
are observations for the Mind; terminal text is not Fleet truth.

### `fleet_attach`

Attach a Fleet as the current Mind or as a separate read-only monitor.

Parameters:

```json
{
  "root": "/path/to/project",
  "fleet_id": "swarm",
  "mode": "mind",
  "takeover": false
}
```

- `root` is the Fleet project root containing `.vivi/fleet.json`.
- `fleet_id` can identify the current-directory candidate or an existing
  session attachment when a root is not supplied.
- `mode` is `"mind"` by default or `"monitor"`.
- Mind attachment validates the Fleet and uses the canonical baseline helper.
- A foreign `mind_session` lock is refused unless `takeover: true` is passed;
  Pi still requires an interactive confirmation that the former Mind is dead or
  has yielded.
- Monitor attachment never claims or overwrites `mind_session`.

Example:

```text
User: You are now Mind for swarm. Attach it, but do not launch anything.
Mind: fleet_attach({"fleet_id":"swarm","mode":"mind"})
```

A successful Mind attachment is a state-changing operation and should be
announced clearly. A successful monitor attachment should be described as
read-only observation, not ownership.

### `fleet_detach`

Detach the current Mind or stop a Pi-local monitor.

```json
{
  "fleet_id": "swarm",
  "mode": "mind"
}
```

- Mind detachment updates the canonical baseline and requires confirmation
  when invoked as a model tool.
- Monitor detachment only removes the session-local monitor registration.
- Omitting `mode` selects the Mind attachment when both kinds are not present;
  specify it when the distinction matters.

### `fleet_preflight`

Run a read-only Fleet-specific preflight for explicitly attached or monitored
fleets.

```json
{}
```

Or select one fleet:

```json
{"fleet_id":"swarm"}
```

Preflight inspects:

- `fleet.json`, Fleet identity, and configured role/runtime shape
- `mind-baseline.json`, last cycle, loop state, steward state, and pauses
- canonical sensors and posture (`growth`, `standby`, or `dormant`)
- Hands, Heads, runtime/pane observations, and external loop state
- Vivi work, mail, operator needs, operator-to-Mind decisions, and pending RTM
- signal, failure, approval, dirty-path, and launch hazards

Preflight uses no-watch sensor reads. It does not start a process, wake a role,
file work, change posture, update a baseline, or arm a steward. It only works
on fleets already attached or monitored in this Pi session.

Typical summary:

```text
swarm mode=mind posture=growth cycle=98 work=3 mail=1 operator-needs=0
pending-rtm=1 signals=runtime_hand-2_stopped recommendations=start/wake hand-2;
review pending integration
```

### `fleet_prepare`

Produce a read-only launch assessment after preflight.

```json
{"fleet_id":"swarm"}
```

This repeats a fresh preflight and adds recommended runtime, operator, posture,
and tasking follow-ups. Recommendations are posture-aware: queued Hand work in
`standby` or `dormant` is reported as a launch gate, not converted into a broad
wake instruction. It returns `side_effects: "none"` and explicitly states that
operator confirmation is required before launch actions.

Typical result:

```text
Launch assessment:
swarm mode=mind posture=standby cycle=98 work=0 mail=0 operator-needs=1
pending-rtm=0 signals=none recommendations=resolve operator backlog before launch
```

### `fleet_sensors`

Read canonical sensor snapshots for explicitly Mind-attached fleets.

```json
{}
```

This returns sanitized role, work, mail, need, RTM, posture, and signal data.
It does not return terminal tails or message bodies. Use `fleet_preflight` when
monitor-only fleets must be included.

### `fleet_board`

Read board, task, need, mail, and integration observations for Mind-attached
fleets.

```json
{"fleet_id":"swarm"}
```

This is read-only. It is appropriate when the preflight identifies work or
operator signals that need interpretation.

### `fleet_runtime`

Read configured process and pane observations for Mind-attached fleets.

```json
{}
```

Use this to distinguish configured assignments from observed runtime state.
Do not infer runtime truth from copied tmux text.

### `fleet_loop`

Inspect or control the Pi-owned internal Mind loop.

```json
{"action":"status"}
{"action":"start","interval":"5m"}
{"action":"update","interval":"10m"}
{"action":"stop"}
```

- `status` is read-only.
- `start` and `update` create or change the Pi-owned cycle timer.
- `stop` stops Pi's internal timers.
- Cadence is bounded; intervals must be at least 60 seconds.
- The tool refuses to create a duplicate when an external canonical
  `fleet-loop.py` is already active.
- The tool never arms a steward.
- Starting or changing the loop is an operational mutation and should follow
  explicit operator intent.
- Pi records the internal loop's running/stopped intent and cadence in session
  entries. `/reload` tears down the old JavaScript timers, then recreates an
  active loop with a fresh countdown after attachments and external-loop state
  are restored. The exact pre-reload next-fire time is not preserved.

Each scheduled internal cycle refreshes a sanitized sensor preflight and queues
one valid `FLEET_CYCLE` follow-up when Pi is busy rather than interrupting an
active turn. The Mind still interprets signals and owns disposition.

## Runtime backends and Head status

Fleet roles may run under either configured tmux targets or Vivi PTY sessions.
Pi does not assume that every role has a tmux pane.

For Vivi PTY roles, canonical sensors may report:

```json
{
  "kind": "vivi_pty",
  "state": "unknown",
  "process_state": "running",
  "confidence": "low"
}
```

This means the PTY process is alive, but the terminal does not expose a stable
Pi marker that proves the agent's current screen state. The Pi panel therefore
uses `process_state` as the observed lifecycle state and renders the active
Head with a warning-colored active glyph. It should be read as **running with
low confidence**, not as a clean successful/idle state. `fleet_runtime` and
`fleet_preflight` retain the backend, state, process state, and confidence so
the Mind can distinguish process liveness from agent health.

A Head that is configured as `vivi_pty` should not be reported as absent merely
because its tmux target is stopped or unused. Conversely, a live PTY process is
not proof that the Head has completed its sweep; inspect `sweep_due`, mail,
signals, and the last cycle before acting.

## Monitor mode

Monitor mode is for observing a Fleet owned by another Mind session:

```text
/fleet attach --monitor /path/to/project
/fleet monitor start 60s
/fleet monitor status
/fleet monitor stop
/fleet monitor detach /path/to/project
```

A monitor:

- reads `fleet.json`, baseline, Vivi observations, and sensors with watch
  persistence disabled;
- may observe multiple foreign-owned fleets;
- never writes `fleet.json`, `mind-baseline.json`, watch cursors, sensor
  history, or other Fleet state;
- never claims `mind_session`;
- never emits `FLEET_CYCLE` or wakes a Mind;
- does not make the Pi conversation the Fleet Mind.

Use `fleet_preflight` for a complete read-only monitor report. The normal
`sensors`, `board`, and `runtime` tools intentionally require Mind attachment.

## Operator commands

The same operations are available as human commands:

```text
/fleet
/fleet attach .
/fleet attach /path/to/project
/fleet attach --takeover /path/to/project
/fleet attach --monitor /path/to/project
/fleet preflight [fleet-id]
/fleet prepare [fleet-id]
/fleet refresh
/fleet compact
/fleet expand
/fleet focus <fleet-id>
/fleet detach /path/to/project
/fleet start [5m]
/fleet update 10m
/fleet stop
```

The `/fleet` command provides argument autocomplete for its subcommands and
cadence examples. Fleet-selecting commands dynamically suggest currently
attached or monitored Fleet IDs.

`/fleet attach --takeover` is never implied by a natural-language request to
attach. Pi must receive the explicit takeover option and confirmation.

## Human-facing Fleet summaries

The extension adds a Fleet widget and status chip without replacing Pi's native
footer. `/fleet compact` renders one summary line per fleet, `/fleet expand`
renders the full detail panel for every fleet, and `/fleet focus <fleet-id>`
expands the named fleet while compacting all others. This view mode is Pi-local
session presentation state and does not alter Fleet/Vivi state. Token, cache,
cost, context, provider, model, and working metadata remain Pi-owned.

### Candidate, not attached

```text
◇ candidate swarm /Users/ianzepp/work/mintedgeek → /fleet attach .
```

### One Mind-attached Fleet

```text
 ◈ swarm Mind growth  cycle 98 · period 300s · next 4m 12s
   Hand 1/2 ● h1:3  × h2:0
   Head 1/3 ● ceo:on  ○ cto:—  ○ cxo:—
   Vivi ● work 3  ✉1  ⚑0  ↻1  !1
   last: acted · dispatched hand-2 and recorded integration lag
```

The glyphs summarize observed runtime state: `●` active, `○` waiting or
inactive, `×` stopped/failed, `!` approval required, and `?` unknown. A
warning-colored `●` indicates an active process whose runtime confidence is
low, as commonly happens with Vivi PTY. Managed Mind roles (`role:
managed-mind` or `role: mind`) render on a separate Mind row even when sensors
carry them in the `hands` collection. Empty Mind, Hand, or Head classifications
are omitted entirely. Mind and Hand metrics show actionable work; Head metrics
show sweep state.

### Monitor-only Fleet

```text
 ◈ nacht Monitor standby  cycle 50 · period 300s · next est 2m 10s
   Hand 0/2 × h1:0  × h2:0
   Head 0/5 ○ ceo:—  ○ cto:—  ○ cxo:—  ○ cpo:—  ○ cmo:—
   Vivi ● work 0  ✉0  ⚑0  ↻0  !5
   last: quiet · observed baseline cycle 50
```

The `next est` label means the monitor estimates timing from the observed
baseline cadence; it is not a Pi-owned Mind loop.

### Multiple fleets

Each fleet is rendered independently with a blank row between sections:

```text
 ◈ swarm Mind growth  cycle 98 · period 300s · next 4m 12s
   Hand 1/2 ● h1:3  × h2:0
   Head 1/3 ● ceo:on  ○ cto:—  ○ cxo:—
   Vivi ● work 3  ✉1  ⚑0  ↻1  !1
   last: acted · dispatched hand-2 and recorded integration lag

 ◈ nacht Monitor standby  cycle 50 · period 300s · next est 2m 10s
   Hand 0/2 × h1:0  × h2:0
   Head 0/5 ○ ceo:—  ○ cto:—  ○ cpo:—  ○ cmo:—  ○ cxo:—
   Vivi ● work 0  ✉0  ⚑0  ↻0  !5
   last: quiet · observed baseline cycle 50
```

The status chip is additive and intentionally compact. Examples:

```text
◈ swarm · H1/2 · Hd1/3 · ✉1 · !1
◌ monitor:nacht · M1
```

## Sensor preflight in `FLEET_CYCLE`

A Pi-owned cycle includes an observation-only preflight so the Mind receives
fresh state without requiring terminal scraping:

```text
FLEET_CYCLE fleets=swarm
Roots:
  swarm: /Users/ianzepp/work/mintedgeek

Sensor preflight (observation only; Mind owns disposition):
  swarm: captured=2026-07-14T14:54:52Z
    work=3 mail=1 operator-needs=0 pending-rtm=1
    Hands: h1=running/3 h2=stopped/0
    Heads: ceo=running/on cto=stopped/— cxo=stopped/—
    signals: runtime_hand-2_stopped, pending_rtm
```

The Mind must still apply the normal signal-disposition gate, absorb operator
feedback before acting, and refresh sensors before consequential operations.
