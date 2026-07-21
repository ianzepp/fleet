# Launch a Fleet from dormant to fully running

Use this reference when a configured Fleet exists but its Mind loop, Hands, Heads,
or process runtimes are dormant. Initialization is a different operation: if the
project has no usable `.vivi/` mailspace or role records, start with
[`getting-started.md`](getting-started.md).

## Launch invariant

A Fleet is fully launched only when durable board truth, configured runtime
capacity, assignment-aware wakes, executive cadence, and a recurring Mind cycle
are all live and independently verified.

Launching is not “start every process and hope.” It is a controlled transition:

```text
validate overlay → inspect board + dirt → start runtimes → wake honest work
→ start due advisors → verify sensors → establish Mind loop → baseline
```

The launch remains backend-neutral. Each role uses its configured runtime;
operators do not convert tmux roles to `vivi_pty`, or the reverse, as a side
effect of launch.

## 1. Establish authority and scope

Before starting processes:

1. Load the Fleet skill and the project overlay (`AGENTS.md`,
   Vivi role records, and `.vivi/mind-baseline.json`).
2. Confirm the project root and mailspace. A workspace container may coordinate
   several child Git repositories from one `.vivi/` directory.
3. Identify the operator-visible Mind session. The Mind is the control plane,
   not another tmux or PTY role.
4. Read `fleet_posture.mode`:
   - `growth`: assigned product lanes should move; starvation triggers an
     executive refill sweep.
   - `standby`: launch on-call capacity, but do not manufacture product work.
   - `dormant`: an operator launch request authorizes process startup; change
     posture only when the operator also intends the Fleet to resume work.
5. Confirm whether the steward is enabled **and explicitly requested**. Launching
   a Fleet does not imply arming the steward.

Write down the intended transition in one sentence, for example:

> Bring configured roles online without changing assignments or runtime
> backends; wake only durable work and cadence-due advisory lanes.

## 2. Preflight the durable surfaces

Set the project and skill paths, then validate the overlay:

```bash
ROOT=/path/to/fleet
SK=/path/to/fleet-skill/scripts

# verify-fleet-json.py is removed; validate the roster via Vivi directly.
vivi role list --project "$ROOT"
vivi mailspace status --project "$ROOT"
python3 "$SK/fleet-baseline.py" get --project "$ROOT"
python3 "$SK/fleet-sensors.py" --project "$ROOT" --no-watch > /tmp/fleet-launch-before.json
```

Inspect, do not merely count:

- open Hand tasks and needs;
- addressed Hand and Head mail;
- pending RTM and integration lag;
- operator-to-Mind decisions;
- configured assignment, packet state, cwd, merge rights, and runtime per role;
- executive cadence and last completion evidence;
- existing process sessions, including stopped PTY tombstones;
- Git dirt in checkouts that a role will touch.

Classify dirt A/B/C before assigning work. Process startup may proceed around
foreign dirt, but no launch step authorizes cleanup, reset, stash, checkout, or
other destructive normalization.

### Existing runtime matrix

For each configured role, record:

```text
role | assignment state | open work | runtime kind | process state | action
```

Typical actions:

| Condition | Launch action |
| --- | --- |
| Process running + role actively working | Leave it alone |
| Process ready + open addressed work | Pointer doorbell |
| Process absent/stopped + assigned actionable lane | Start, then pointer doorbell |
| Process absent/stopped + paused lane | Start only if warm capacity is desired; do not wake |
| Process absent/stopped + unassigned lane | Usually leave dormant, or start ready capacity without inventing work |
| `approval_required` | Resolve approval; never stack input |
| `failed` | Diagnose before recreate or fallback |
| `unknown` | Inspect evidence and terminal stability; do not equate it with stopped |

## 3. Start configured Hand runtimes

Read each Hand’s binding from its Vivi role record. Do not infer a backend from the
agent name. The backend-neutral runtime helper (`fleet-runtime.py`) has been
removed; start runtimes directly through their configured backend. For tmux
roles, create the configured session/window and launch the agent from the Vivi
role record capacity. For `vivi_pty` roles, use `vivi-pty` session commands.

```bash
# tmux: create the configured session/window and launch the agent.
tmux new-session -d -s <fleet_id> -n hand-1 -c "$ROOT"
# launch command is constructed from the Vivi role record (provider/model/thinking + harness)
tmux send-keys -t <fleet_id>:hand-1.1 '<launch-command>' Enter

# vivi-pty: create/restart the configured session.
vivi-pty --project "$ROOT" session start <session-id> -- <command...>
vivi-pty --project "$ROOT" session restart <session-id>
```

After startup, require expected cwd, driver/agent command, model/effort
arguments when observable, and no duplicate session for the same role. The
initial harness footer may show a default model before the first request. When
model identity matters, confirm the configured argv and verify the footer again
after a harmless first turn.

## 4. Wake Hands by assignment, not by headcount

Starting capacity and assigning work are separate operations.

1. **Open actionable task/need:** wake with the handle.
2. **Addressed mail:** wake with a short pointer when the role is ready.
3. **Assigned active lane with an explicit next campaign unit:** wake it to read
   its bag and durable campaign, then continue the highest-priority honest unit.
4. **Paused packet:** preserve it; do not silently resume.
5. **Unassigned slot:** leave ready or dormant. Never invent polish or generic
   exploration merely because the process exists.

Use `tmux send-keys` (or `vivi-pty terminal write`) directly so backend selection,
state refusal, throttling, and wake records stay canonical:

```bash
# tmux backend — pointer doorbell:
tmux send-keys -t <fleet_id>:hand-3.1 "HAND WAKE hand-3. Task <hex>. Load charter and task from Vivi." Enter

# Assigned lane with durable campaign truth but no single handle:
tmux send-keys -t <fleet_id>:hand-3.1 \
  "HAND WAKE hand-3. Read your configured lane, Vivi bag, and campaign; continue the highest-priority honest unblocked unit." Enter

# vivi-pty backend:
vivi-pty --project "$ROOT" terminal write <session-id> "HAND WAKE hand-3. Task <hex>." --enter
```

Do not wake `starting`, `submitting`, `running`, or `approval_required` roles.
Because terminal classifiers are heuristic, reconcile a surprising idle state
with active markers and changing terminal revisions before sending input.

## 5. Start Heads according to policy

Heads are advisory capacity, not extra product Hands.

For each configured Head:

1. Start its configured runtime if missing. The `fleet-runtime.py` helper is
   removed; start directly through the configured backend (tmux or vivi-pty):

   ```bash
   # tmux
   tmux new-session -d -s <fleet_id> -n head-cto -c "$ROOT"
   tmux send-keys -t <fleet_id>:head-cto.1 '<launch-command>' Enter

   # vivi-pty
   vivi-pty --project "$ROOT" session start <session-id> -- <command...>
   ```

2. Load its persona and role prompt.
3. Inspect addressed mail.
4. Apply its policy:
   - cadence enabled and due: run the configured sweep;
   - self-directed: begin its bounded advisory lane;
   - lazy/on-demand: answer addressed work, then remain available;
   - `assignment_mode` (`new`/`compact`/`continue`/`restart`): prepare the
     session for a new assignment per [`runtime-config.md`](runtime-config.md)
     (legacy `clean_slate_per_assignment: true` ≡ `new`).
   - Head schedule: `executive_cadence.every_n_loops` — **0** on-call, **N≥1**
     scheduled (`N × mind_loop.interval_sec`). No separate `enabled` /
     `self_directed`.
5. Require reports to the configured Mind inbox. Heads do not file Hand work,
   merge, or create approval gates.

Cadence (when scheduled):

```text
every_n_loops × mind_loop.interval_sec     # every_n_loops == 0 → never due
```

A launch may run the first due sweep immediately for Heads with N≥1. It must
not invent perpetual sweeps for on-call Heads (N=0).

If a Head’s terminal layout normalizes to `unknown`, inspect process existence,
pane output, and activity directly. `unknown` is evidence debt, not permission
to repeatedly recreate an active advisor.

## 6. Establish the Mind monitoring loop

A running set of Hands without a living Mind is not a launched Fleet. Establish
one recurring control loop at the configured interval—commonly five minutes.
The durable prompt must identify the Fleet and root explicitly:

```text
FLEET_CYCLE fleets=<slug>
Roots:
  <slug>: /absolute/project/root

Load the Fleet skill and run one fail-fast Mind cycle. Process operator-to-Mind
mail first, run sensors, disposition every material signal, wake safe actionable
work, process RTM/integration lag, trigger due Heads, preserve foreign dirt, and
bump the baseline. Do not arm the steward unless separately requested.
```

A scheduler, desktop task, or other recurrence mechanism is valid only while it
can actually invoke a live Mind session. Record the scheduler/task identifier
and next fire time. Do not create duplicate loops for the same Fleet.

The first line of every scheduled payload follows the Fleet skill’s
`FLEET_CYCLE` grammar. Paths belong in the body, not invented keys on that line.

### tmux-backed fallback loop

When the Mind harness cannot create a native scheduled loop, use
`scripts/fleet-loop.py` to inject `FLEET_CYCLE` into the live operator/Mind tmux
pane. This is a scheduler fallback, not a second Mind and not the steward.

```bash
# Start a five-minute loop into the current tmux pane.
python3 "$SK/fleet-loop.py" --project "$ROOT" start 5m

# Prefer an explicit target when starting from another shell.
python3 "$SK/fleet-loop.py" --project "$ROOT" start 5m \
  --target operator:node.1

# If the target TUI leaves text in the composer, increase submit settling.
python3 "$SK/fleet-loop.py" --project "$ROOT" start 5m \
  --target operator:node.1 --submit-delay 1.2

# Check or stop the loop.
python3 "$SK/fleet-loop.py" --project "$ROOT" status
python3 "$SK/fleet-loop.py" --project "$ROOT" stop
```

State lives in `$ROOT/.vivi/fleet-loop.json`; logs live in
`$ROOT/.vivi/fleet-loop.log`. `start` refuses a duplicate live loop. `stop`
kills only the recorded loop process group. Use `--duration 2h` or
`--max-cycles N` for bounded supervision, and `--immediate` only when an
immediate cycle injection is useful. The helper types the payload, waits
`--submit-delay` seconds (default `0.8`), then sends `--submit-key` (default
`C-m`) so Codex-like TUIs submit instead of leaving text in the composer.

The loop only sends the scheduled prompt. The Mind cycle still has to run
sensors, disposition signals, wake/reinit roles, bump the baseline, and rearm
the steward only if that fleet's steward was separately enabled and armed.

## 7. Verify the assembled Fleet

Wait briefly for TUI startup, then run a fresh sensor pass:

```bash
python3 "$SK/fleet-sensors.py" --project "$ROOT" --no-watch \
  > /tmp/fleet-launch-after.json
```

Verify independently:

- every intended Hand session exists once;
- assigned Hands are `running`, or ready with a valid defer;
- paused/unassigned Hands received no invented work;
- every intended Head process exists and due work was delivered;
- sensor `runtime.kind`, `target`, state, process state, and evidence match the
  configured backend;
- operator mail, pending RTM, integration lag, failures, and unknown states each
  have a disposition;
- no project files changed merely because of a smoke prompt;
- foreign dirt remains preserved;
- the recurring Mind loop exists with the expected next fire;
- steward state still matches explicit operator intent.

A sensor exit of `2` means partial evidence, not automatic failure. Open the
JSON and explain the missing surface. Exit `1` is a hard failure.

### Minimal smoke turn

For a newly introduced runtime backend, send one harmless prompt to a single
ready role before launching the whole topology:

```text
Basic runtime smoke test only: do not modify files or run tools. Reply exactly RUNTIME_OK.
```

Require submit, active-state observation, expected response, return to ready,
and correct Fleet sensor normalization. Stop and fix backend-wide defects before
multiplying them across the roster.

## 8. Commit launch state and enter normal cycles

At the end of the launch cycle, bump the baseline through the helper rather than
editing counters manually:

```bash
python3 "$SK/fleet-baseline.py" bump --project "$ROOT" \
  -s 'fleet launched; assigned lanes and due Heads active' \
  --fingerprint-file /tmp/fleet-launch-after.json \
  --operator-engaged
```

Use the actual helper options supported by the installed Fleet version. The
baseline should retain canonical `runtime_states`, wake records, Head report
state, Mind-loop state, and operator engagement counters.

Report to the operator:

- roles started, already live, left paused, or intentionally not woken;
- runtime backend and normalized state by role;
- due Head sweeps triggered;
- unresolved `unknown`, failure, approval, or dirt evidence;
- monitoring-loop identifier and interval;
- whether the steward remains disabled or was explicitly armed;
- commits, or why launch-only overlay/runtime changes were not committable.

## Launch stop conditions

Stop expansion and report honestly when:

- the configured cwd or command does not exist;
- a live session has a different binding and replacement would destroy work;
- PTY session rebinding is required but unsupported;
- auth or quota prevents the chosen harness from starting;
- shared workspace dirt makes the assigned unit unsafe;
- the board lacks honest work for an unassigned slot;
- process and harness evidence conflict enough that safe doorbelling is unclear;
- scheduler creation would duplicate an existing Mind loop.

A partially launched Fleet with explicit dispositions is safer than a fully
populated process table that stacks input, invents work, or erases ownership.

## Dormant-to-live checklist

```text
[ ] Project root, mailspace, role records, and Mind authority confirmed
[ ] Vivi role records valid
[ ] Posture and steward intent confirmed
[ ] Board, assignments, packet states, cadence, and dirt inspected
[ ] Existing tmux/PTy sessions inventoried without destructive cleanup
[ ] One new backend smoke-tested before broad launch
[ ] Intended Hand runtimes started from configured bindings
[ ] Active assigned lanes doorbelled; paused/unassigned lanes not invented
[ ] Heads started and handled by cadence/self-directed/lazy policy
[ ] Fresh sensors reconcile process truth and board truth
[ ] Every material launch signal has a disposition
[ ] One recurring Mind loop exists; ID and next fire recorded
[ ] Baseline bumped through helper with canonical runtime states
[ ] Operator received launch summary, caveats, and commit report
```

Related references: [`dual-channel.md`](dual-channel.md),
[`mind-cycle.md`](mind-cycle.md), [`runtime-config.md`](runtime-config.md),
[`posture.md`](posture.md), [`heads.md`](heads.md), and
[`dead-man.md`](dead-man.md).
