# tmux execution runtime

External tmux panes as a fleet execution backend. Use when the harness lacks
sub-agent spawning, when a persistent interactive session is needed, or when
the operator wants to watch a Hand work live. For the default sub-agent path,
see [`subagent.md`](subagent.md).

## When to use tmux

| Situation | Use tmux |
| --- | --- |
| Harness lacks sub-agent spawning | Yes |
| Persistent interactive session (long debugging, REPL) | Yes |
| Operator wants to watch a Hand work live | Yes |
| Remote host execution (SSH) | Yes (on remote host) |
| Default fleet execution | No — prefer sub-agent |

## Binding rule

**Ops always use `tmux_target` from the Vivi role record.** Two layouts:

| Layout | Mail identity | tmux session | Typical `tmux_target` |
| --- | --- | --- | --- |
| **session-per-fleet** (recommended) | role (`hand-1`) | `fleet_id` | `mgs:hand-1.1` (window=role) |
| **legacy** (existing one-off fleets) | role (`hand-1`) | role (`hand-1`) | `hand-1:1.1` |

| Mail | tmux binding | Notes |
| --- | --- | --- |
| `mind@…` | **none** | Operator TUI only — no mind tmux |
| `hand-1@…` | `hand-1` or fleet session | Respect base-index; never invent target |
| `head-cto@…` | `head-cto` or fleet session | Heads may be lazy (create on first assign) |

Do **not** hardcode `session == role` when `tmux_target` is set. Multi-fleet detail: [`multi-fleet.md`](multi-fleet.md).

## Session setup

```bash
vivi mailspace identity add mind --project <root>          # board only
vivi mailspace identity add hand-1 --project <root>
vivi mailspace identity add head-cto --project <root>
tmux new-session -d -s example -n hand-1 -c <cwd>          # Hands/Heads only
# no tmux for mind
```

Mind never has a tmux pane. The operator TUI is the Mind process.

## tmux bindings (Vivi role record)

Capacity (provider/model/thinking) lives on the Vivi role record; the role
record also holds operational tmux bindings:

```json
{
  "hands": {
    "hand-1": {
      "mail_identity": "hand-1",
      "tmux_session": "example",
      "tmux_window": "hand-1",
      "tmux_target": "example:hand-1.1",
      "cwd": "/path/to/project",
      "wake_mode": "tmux_send_keys",
      "min_seconds_between_wakes": 180
    }
  }
}
```

```bash
vivi role set hand-1 --project <root> \
  --harness tmux \
  --provider openai-codex --model gpt-5.5 --thinking medium
```

## Runtime state classification

Classify pane state from bottom-of-pane evidence. Prefer current prompt
evidence over stale scrollback failures.

| Canonical state | Example evidence | Mind action |
| --- | --- | --- |
| `starting` / `submitting` | runtime transition in progress | wait; do not stack input |
| `running` | live spinner / streaming / progress bar | sleep; do not wake/reinit |
| `waiting_for_input` | Pi input prompt; Codex `›`; opencode `Ask anything...` | Doorbell if open tasking |
| `completed` | finished turn with input prompt restored | Doorbell if work exists; otherwise refill or pause |
| `approval_required` | workspace trust or permission UI | Resolve once; do not treat as running or ready |
| `failed` | capacity, connection, or runtime evidence | model fallback, retry, or reinit by detail |
| `stopped` | process/session absent or exited | recreate runtime + agent |
| `unknown` | insufficient or contradictory evidence | record sample; do not claim certainty or thrash |

### Harness-specific markers

**Codex:** `•` monologue then `›` is often an answer that stopped. Back-to-back
prepared prompts without submit-settle are the failure mode. A live `›` /
`codex ›` prompt after an earlier error is `waiting_for_input`, not `failed`.

**opencode:** pane classification keyed on opencode-specific markers (`OpenCode Zen`, `Build auto`, `Build ·`, `ctrl+p commands`). Bottom status bar determines state:
- `waiting_for_input`: `Ask anything...` in last ~6 lines
- `running`: progress bar `⬝` or `esc interrupt` in last ~6 lines
- Post-response done: `▣` completion marker visible, no progress

**Kimi:** pane classification is current-state first:
- `waiting_for_input`: boxed `> ` composer plus `K<n> thinking:` / `context:` status chrome
- `running`: rotating moon phase (`🌑`…`🌕`) followed by `· Tip:`
- `approval_required`: approve/reject candidate list with `↵ confirm`

## Doorbell (wake)

When `waiting_for_input`, send the exact boot prompt emitted by `fleet prepare`.
See [`fleet-helper.md`](fleet-helper.md). Do not hand-write a pointer.

`fleet prepare` must succeed before `tmux send-keys`. Do not place new
authoritative instructions in the pane or backfill Vivi afterward.

```bash
tmux send-keys -t '<tmux_target>' -l -- '<exact fleet prepare output>'
tmux send-keys -t '<tmux_target>' Enter
# Before sending, classify the pane: only type into panes with positive agent
# chrome (waiting_for_input / completed). Refuse running/down/rate-limit.
```

**Doorbell fail-closed:** only type into panes with positive agent chrome (`waiting_for_input` / `completed`). Unmatched screens and bare shells classify as `unready` and are refused — never inject a pointer into zsh/bash. The helper that enforced this (`fleet-doorbell.sh`) is removed; the Mind must classify the pane before sending.

**Rate-limit wakes** (`min_seconds_between_wakes`) only when that Hand already has a prior doorbell (`last_hand_wake.by_hand.<name>.count ≥ 1`). No last wake / count 0 → never rate-limit.

### Channel split (mandatory)

| Channel | Allowed content |
| --- | --- |
| **tmux send-keys** | Exact `fleet prepare` output only |
| **Vivi mail / task / need** | Full done-when, evidence bar, scope, approach, residuals |
| **Vivi role charter** | Standing identity, capacity, non-goals, report-back expectations |
| **Agents.md / factory goal / campaign** | Durable multi-agent law, architecture, stage criteria |

Bad: hand-written wakes, full policy dumps, stage graphs, persona text, or
model/capacity flags added outside the prepared assignment.

### assignment_mode (doorbell applies it)

When waking a new task/need handle, apply the role's
`assignment_mode` before the pointer (the `fleet-doorbell.sh` helper that did
this is removed — apply the mode with direct `tmux send-keys` first):

| Mode | Before pointer |
| --- | --- |
| `new` | Idle → `/new` → idle (or start if stopped) |
| `compact` | Idle → `/compact` → idle |
| `continue` | Pointer only (auto-start if stopped) |
| `restart` | recreate the pane/session, then idle |

Same-handle rewakes reuse the originally captured generated prompt; they do not
prepare a second assignment. Full table: [`runtime-config.md`](runtime-config.md).

## Codex reinit fallback

**Policy:** deliver the generated Fleet prompt first. Reinit is recovery, not
the default wake. The `codex-reinit.sh` helper is removed; recovery is done by
recreating the pane/session directly.

**Reinit when:** process down; trust/error prompt that cannot be accepted inline; Codex text remains stuck after a doorbell retry; stale bootstrap repeats.

1. Run `fleet prepare` before launch so a generated prompt exists
2. Doorbell via `tmux send-keys` (with submit-settle for Codex)
3. If it sticks, recreate the pane/session directly with `tmux`
4. Reinit launch must avoid `exec` and use the role's configured capacity from Vivi
5. First message is the exact generated prompt

```bash
# Recreate a stuck Codex pane directly (codex-reinit.sh is removed):
tmux kill-window -t '<tmux_target>' 2>/dev/null
tmux new-window -t '<session>' -n '<window>' -c '<fleet cwd>'
tmux send-keys -t '<tmux_target>' -l -- '<codex launch from Vivi role capacity>'
tmux send-keys -t '<tmux_target>' Enter
```

## Process ops (start / rehome / restart)

**Invariant:** fleet `cwd` should match `tmux display -p -t <target> '#{pane_current_path}'`. Wrong cwd → writes against wrong tree.

### Packet rehome sequence (Pi TUI in tmux)

```text
1. Runtime must be waiting for input unless the operator allows cancellation.
2. Exit Pi cleanly and wait until pane_current_command is a shell.
3. Recreate or retarget the tmux session/window with `-c <packet-or-main-cwd>`.
4. Start the role's configured agent from that cwd (capacity from the Vivi role record).
5. Verify pane path and process, then send the exact generated prompt.
```

```bash
tmux has-session -t hand-N || \
  tmux new-session -d -s hand-N -c '<fleet cwd>' -n main
```

| Do | Don't |
| --- | --- |
| Use `tmux send-keys -t … -l -- '…'` for literal text | Stack wake messages into a busy pane |
| Launch the exact agent command from the role's capacity (Vivi role record) | Invent provider/model flags during recovery |
| Recreate with `tmux new-session -d -s <fleet> -c <cwd>` | Assume a dead session still exists |
| Match `tmux_target` to the real base index | Hardcode indices without checking |
| Verify `#{pane_current_path}` and capture the prompt | Trust configuration without checking runtime |

## Wake on addressed mail

Board mail is demand, not cadence. Every Mind cycle compares the newest mail
addressed to each configured Hand or Head with the prior successful-cycle
fingerprint. A changed top handle emits `mail_for_<role>` and, when the pane
is idle, `mail_wake_candidate_<role>`. Mind doorbells the recipient with that
handle in the same cycle.

The Mind cycle is the debounce period: multiple messages between cycles collapse
to one wake pointing at the newest inbox state. Do not stack wakes or interrupt
a running pane.

## Completion mail (optional)

```text
From: hand-N → mind
Subject: hand-N turn end: <one line>
Body: cleared <handle>|none · HEAD <sha>|dirty · tasking left: … · next: … · blocked: none|…
```

Board `task done` / `need done` remains primary durable signal even if this mail is skipped.

## Mind loop fallback

For Mind harnesses without native scheduled loops, `fleet-loop.py` injects
`FLEET_CYCLE` into the live operator pane via tmux:

```bash
scripts/fleet-loop.py --project <root> start 5m --target <operator-pane>
scripts/fleet-loop.py --project <root> status
scripts/fleet-loop.py --project <root> stop
```

Records `.vivi/fleet-loop.json`. Loop ≠ steward and never runs sensors itself.

## Scripts

| Script | Purpose |
| --- | --- |
| `fleet-loop.py` | tmux-backed FLEET_CYCLE injector |
| `fleet-resolve.py` | Resolve project + fleet + role → tmux target |

Removed helpers (use tmux directly): `fleet-doorbell.sh` (deliver exact
`fleet prepare`/`prompt` output with `tmux send-keys`), `codex-reinit.sh`
(Codex recovery — recreate pane directly), `opencode-hand-ctl.sh` (opencode
Hand control — operate the pane directly), `fleet-runtime.py`
(backend-neutral start/stop/restart — use tmux/vivi-pty directly).
