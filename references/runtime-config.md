# Runtime fallback, config, baseline, wind-down

Load for capacity recovery, Codex reinit, fleet/baseline schemas, wind-up.

## Skill scripts

Paths under this skill’s `scripts/`.

### Portability (macOS + Linux)

| Requirement | Detail |
| --- | --- |
| **Shell** | **bash 3.2+** (`#!/usr/bin/env bash`). Not `sh`/zsh-as-script. macOS stock bash OK. |
| **Python** | **3.9+** via `#!/usr/bin/env python3` (or `PYTHON_BIN`). No third-party deps. |
| **PATH** | `scripts/lib/env.sh` fills common dirs without login shell. |
| **Overrides** | `TMUX_BIN`, `PYTHON_BIN`, `VIVI_BIN`, `CODEX_BIN`, `PS_BIN`, … |
| **Dates** | Prefer `date -u +%s` / `+%Y-%m-%dT%H:%M:%SZ`. ISO `Z` → `+00:00` in Python for 3.9–3.10. |
| **JSON** | UTF-8; baseline updates use same-dir temp + `os.replace`. |
| **Smoke** | `scripts/smoke-portability.sh [--project <root>]` |

Do **not** hardcode only `/opt/homebrew/...`. Prefer `fleet_find_*` from `lib/env.sh` or PATH + multi-candidate lists.

### `fleet-sensors.py`

```bash
python3 scripts/fleet-sensors.py --project <root>            # JSON (default)
python3 scripts/fleet-sensors.py --project <root> --text
python3 scripts/fleet-sensors.py --project <root> --no-watch # skip mailspace watch
python3 scripts/fleet-sensors.py -p <root> --fleet <fleet-id> --fleet-file <path/to/fleet.json>
python3 scripts/fleet-sensors.py -p <root> --tail 12 --cursor-file <path>
python3 scripts/fleet-sensors.py -p <root> --record-cycle [--cycle-id <id>]
python3 scripts/fleet-sensors.py -p <root> --history 10 [--role hand-1]
```

Emits board status, open handles, pane classes, git tip, ahead/behind counts, bounded dirty paths, pending RTM/integration-lag evidence, fingerprint, `signals[]`, `quiet_hint`, posture, Head cadence due flags, and model provenance for every configured Head/Hand. `configured` normalizes fleet role fields (`agent`; explicit `provider`; `model` or `agent_model`; and `reasoning`, `agent_reasoning_effort`, `thinking`, or `effort`) and may fill otherwise absent values from the role's unambiguous `preferred_models` profile; it never parses `agent_launch`. `observed` comes only from structured normalized runtime diagnostics and remains null when not provable. `match_status` therefore distinguishes `match`, `mismatch`, `configured_only`, `observed_only`, and `unknown` without treating config as observation. RTM reconciliation uses advertised commit ancestry when available and newer main-Hand merge-completion mail as the cheap fallback. Exit `0` ok · `1` hard · `2` partial.

Sensor history is opt-in and normal/ad-hoc invocations never write it:

```json
{
  "sensor_log": {
    "enabled": true,
    "level": "summary",
    "directory": ".vivi/logs/sensors",
    "retention_cycles": 100
  }
}
```

Levels are `off`, `events` (material fingerprint diffs), `summary` (fixed reduced fields), and `full` (conservatively redacted snapshot). `path` is accepted instead of `directory`; relative paths resolve under the project and the default is `.vivi/logs/sensors`, intended to remain gitignored. A recorded call uses a serialized first-write-wins atomic write to create one schema-versioned JSON file per cycle. Cycle IDs are canonical non-negative decimal integers. Retrying the same cycle and level is idempotent; conflicting metadata is reported without replacing the original, then retention prunes oldest cycle IDs. Logging failures add `sensor_log_failed`, return partial, and still print the live snapshot. Persisted full records exclude pane bodies/tails, runtime evidence text, mail subjects/bodies, customer content, and secret/token/password/credential fields. They never persist raw pane tails.

### `fleet-baseline.py`

```bash
python3 scripts/fleet-baseline.py get -p <root>
python3 scripts/fleet-baseline.py bump -p <root> -s 'sleep' --quiet \
  --fingerprint-file /tmp/sensors.json
# optional: --acted · --operator-engaged · --kind superficial|thorough · --mode …
# · --fingerprint-json · --pane-classes-json · --debt-json · --recap · --no-increment-silence
python3 scripts/fleet-baseline.py rearm-note -p <root>   # cycle clock only
python3 scripts/fleet-baseline.py wound-up -p <root> -s 'wound_up' --dropped hand-1,hand-2
```

`--project/-p` works before or after the subcommand. Keep regression coverage
for both shapes; the command parser intentionally accepts global project scope
on the parent parser and on each subcommand. `bump` increments `last_cycle`,
quiet/mode counters, stores fingerprint/runtime_states, merges `sensors.heads`
→ `head-*`.`last_report_*`, touches **`mind_loop.last_successful_cycle_at`**
(dead-man cycle clock). It does **not** arm steward or stamp
`steward.last_rearm_at` — that is `steward.sh arm|rearm` only (when steward is
enabled+armed).

### `verify-fleet-json.py`

```bash
python3 scripts/verify-fleet-json.py --project <root>                  # text summary
python3 scripts/verify-fleet-json.py --fleet-file /path/to/fleet.json --json
python3 scripts/verify-fleet-json.py --project <root> --strict         # warnings as errors
python3 scripts/verify-fleet-json.py --project <root> --no-path-checks # skip on-disk refs
```

Validates fleet.json shape, cross-references (`default_hand` resolves,
`mail_identity` unique, auditor Hands cannot merge and use fresh assignments), `executive_cadence` /
wake-field well-formedness, and that referenced absolute paths (`role_prompt`,
`persona`, `tooling` binaries) exist, and validates `sensor_log` level/path/retention shape. The schema is permissive ("extend freely;
skill cares about meanings") — unknown keys are NOT rejected. Exit `0` ok ·
`1` validation errors (or any warning under `--strict`) · `2` usage.

### `fleet-posture.py`

```bash
python3 scripts/fleet-posture.py get --project <root> [--json]
python3 scripts/fleet-posture.py set --project <root> growth|standby|dormant \
  --reason 'why' [--wake-trigger '...']... [--json]
```

Updates only `fleet.json.fleet_posture`, preserves unspecified posture fields, stamps `since`, strictly validates a same-directory temporary candidate, and atomically replaces the overlay. It does not wake roles, run sensors, bump the Mind baseline, or arm the steward; normal Mind-cycle processing applies the transition. Exit `0` ok · `1` data/validation error · `2` usage.

### `fleet-runtime.py`

```bash
python3 scripts/fleet-runtime.py --project <root> --role head-cto status
python3 scripts/fleet-runtime.py --project <root> --heads all start
python3 scripts/fleet-runtime.py --project <root> --role hand-1 restart --boot 'HAND WAKE hand-1. Read your bag.'
python3 scripts/fleet-runtime.py --project <root> --hands all stop
python3 scripts/fleet-runtime.py --project <root> --role head-ceo doctor
```

Backend-neutral process lifecycle for configured Hand/Head roles. It resolves
`fleet.json` bindings and dispatches to `tmux` or `vivi_pty` without changing
assignments, posture, board state, or runtime backend. Use it when a role is
stopped/missing before using `fleet-doorbell.sh` to deliver a work pointer.

| Command | Meaning |
| --- | --- |
| `status` / `doctor` | Inspect configured runtime state; `doctor` exits non-zero for stopped/failed roles |
| `start` | Create/start the configured runtime if absent or stopped; never assigns work |
| `restart` / `reinit` | Stop then start through the configured backend; optional `--boot` pointer |
| `stop` | Tear down the configured process/session/window for selected roles |

Selectors: `--role` (repeatable), `--hands all|h1,h2`, `--heads all|head-ceo,…`.
A boot pointer is transport-only; still use board handles for durable work truth.
For tmux roles, `start` will not stack a launch command into an existing target
unless `--force` is passed. For Vivi-PTY roles, stopped tombstones are restarted
through `vivi-pty session restart` and new sessions use the configured command
array without shell evaluation.

### `fleet-doorbell.sh`

```bash
scripts/fleet-doorbell.sh --project <root> --fleet <fleet-id> --role hand-1 [--handle HEX] [--note '…'] [--force]
scripts/fleet-doorbell.sh --project <root> --fleet <fleet-id> --role hand-1 --runtime-target <session:win.pane> --message '…'
# optional env: FLEET_DOORBELL_SUBMIT_DELAY_SEC (Codex submit-settle)
```

Resolves the logical role through `fleet-resolve.py`; refuses running/down/rate-limit unless `--force`; records `last_hand_wake`.

Prompt classification is current-state first. In particular, Codex panes must
treat a live bottom prompt (`›` / `codex ›`) as ready even if older scrollback
contains failed commands, connection messages, or test errors.

### `fleet-loop.py`

```bash
python3 scripts/fleet-loop.py --project <root> start 5m --target operator:node.1
python3 scripts/fleet-loop.py --project <root> start 10m --duration 2h
python3 scripts/fleet-loop.py --project <root> start 5m --submit-delay 1.2
python3 scripts/fleet-loop.py --project <root> status
python3 scripts/fleet-loop.py --project <root> stop
```

Fallback scheduler for Mind harnesses without native scheduled-loop/tool-call
support. It periodically injects a `FLEET_CYCLE` message into the live Mind tmux
pane via `tmux send-keys`; it does not run sensors or mutate the fleet baseline.

| Flag | Meaning |
| --- | --- |
| `start [interval]` | Start background injector; interval accepts `5m`, `300s`, `1h`; default `5m` |
| `--target <session:window.pane>` | Mind/operator pane to receive the cycle; default is current tmux pane when inferable |
| `--duration <duration>` | Optional total runtime before the loop exits |
| `--max-cycles N` | Optional stop after N injections |
| `--immediate` | Send one cycle immediately before sleeping |
| `--fleets <slugs>` | Override generated `FLEET_CYCLE fleets=...` first line |
| `--payload <text>` | Custom payload; must still start with `FLEET_CYCLE`; expands `{project}` and `{fleet}` |
| `--submit-delay <sec>` | Wait after typing text before submit; default `0.8` or `FLEET_LOOP_SUBMIT_DELAY_SEC` |
| `--submit-key <key>` | tmux key used to submit; default `C-m` |

State: `$ROOT/.vivi/fleet-loop.json`. Log:
`$ROOT/.vivi/fleet-loop.log`. `start` refuses a duplicate live PID. `stop`
kills only the recorded process group and removes the state file. `status`
reports whether the recorded PID is still live.

The helper sends the payload as literal text, waits for the submit delay, then
sends the submit key. If a Mind TUI leaves cycle text in the composer, stop and
restart the loop with a longer `--submit-delay` rather than stacking manual
Enter keys.

Loop ≠ steward. Starting this helper does not enable or arm the dead-man; rearm
still happens only after a successful Mind cycle and only when that fleet's
steward was explicitly enabled and armed.

### `codex-reinit.sh` (fallback)

```bash
scripts/codex-reinit.sh doctor --project /path/to/fleet --fleet <fleet-id>
scripts/codex-reinit.sh heal --project /path/to/fleet --fleet <fleet-id> --role hand-3
scripts/codex-reinit.sh reinit --project /path/to/fleet --fleet <fleet-id> --role hand-1 --boot 'HAND WAKE …'
scripts/codex-reinit.sh classify --project /path/to/fleet --fleet <fleet-id> --role hand-2
```

| Rule | Detail |
| --- | --- |
| Defaults | `PROJECT` from cwd; `FLEET_FILE`=`$PROJECT/.vivi/fleet.json`; `--fleet` selects the logical ID |
| Launch | Prefer Hand **`agent_launch`** (after `cd` to fleet cwd). If empty: `codex -m <agent_model> -c model_reasoning_effort=xhigh` (`CODEX_EFFORT` / `--model` overrides). Never `exec codex` |
| Exit | reinit `0/1/2 stuck_idle/3`; doctor `0/1/2` (script header) |
| Symlink | Fleets may wrap via `.vivi/codex-reinit.sh` |

### `steward.sh`

See [`dead-man.md`](dead-man.md). Subcommands: `arm` / `rearm` / `disarm` / `check` / `status` / `clear` / `trip` / `loop`. Default **enabled false**.

## Runtime fallback

**Invariant:** assignment (hand-N, side lane, merge rights) does **not** change on model full. Only **runtime** rebinds (`agent_model`, `agent_launch`, carefully `agent`/`wake_mode`). Source: fleet `runtime_fallback` + per-hand fields + harness alignment.

### Failure classes

| Class | Cues | First response |
| --- | --- | --- |
| **Capacity** | rate limit, 429, usage limit, “try again later” | Step model ladder (**same harness as Mind** for Hands) |
| **Auth / quota hard stop** | account exhausted, login required | Park harness; escalate operator; pivot other hands |
| **Connection** | ECONNRESET, disconnect | One same-model reinit; then capacity ladder |
| **Harness dead** | crash loop, session destroy | Recreate shell + launch; if loop → model ladder → **Mind-aligned** harness recovery |

### Model ladder

Prefer **Mind-aligned product harness**. Fleet names ordered ladders **per harness** (do not invent ids not in fleet):

```text
pi_model_ladder_mind:  [ openai-codex/gpt-5.5@medium, zai/glm-5.2@high, … ]
pi_model_ladder_hand:  [ openai-codex/gpt-5.5@medium, zai/glm-5.2@high, … ]
pi_model_ladder_head:  [ zai/glm-5.2@high, zai/glm-5.2@xhigh, … ]
```

**On `failed` with `runtime.detail=capacity`:**

1. Not mid-successful `running` with real progress → wait
2. Advance Hand `agent_model` one step **same harness**; rewrite `agent_launch`
3. Doorbell if idle; reinit only for down/stuck/error recovery — short bootstrap, no stacked wakes
4. Baseline `last_runtime_fallback` {hand, from, to, reason, cycle, at}
5. **≤1 model step per Hand per cycle**
6. Ladder exhausted → park or escalate; **do not** silently move Hand to different harness while Mind stays on original (exception: operator note + re-align plan)

**Heads** may use own ladder/alternate harness without waiting for Mind.

### Harness fallback (after model ladder exhausted)

**Hands** stay harness-aligned with Mind. Product harness flip = **fleet-wide Mind decision**, not per-Hand convenience:

1. Exhaust same-harness model ladder on affected Hand(s)
2. If Mind harness fleet-dead: recover **Mind**, set new `mind.agent`, rebind **all Hands** on clean breakpoints
3. Temporary single-Hand exception (operator only): baseline note; re-align ASAP
4. Heads already on alternate harnesses: leave unless they fail too

Do **not** change a single Hand's harness while the Mind and other Hands remain Pi. Capacity fallback changes Pi provider/model first.

A rare harness flip updates `mind.agent` + every Hand’s `agent` + `agent_launch` + `wake_mode` at a clean breakpoint. **Assignment remains unchanged.**

### Per-cycle budget (anti-thrash)

| Rule | Detail |
| --- | --- |
| Capacity model flips | Max **~2**/cycle fleet-wide for product slots |
| Product harness flips | Rare (Mind-plane) |
| Reinit-after-unit | Does **not** count as fallback |
| Running Hand | Never flip for capacity unless pane shows hard capacity error |
| Prefer | Flip **idle/error** product slots first (model only, same harness) |

### Mind hard limit

If Mind dies (hard quota / dead harness), it cannot self-heal inside the dead session.

| Situation | Works | Does not |
| --- | --- | --- |
| Soft pressure | Same-harness cheaper models; shorten prose; skip nonessential Head wakes | Migrating Hands to different harness while Mind stays |
| Session alive, tool errors | Fail-fast sleep; one-line baseline; next fire retries | Infinite retry same turn |
| **Hard stop** | **Operator recovery** | Silent hope; thrashing hands without live Mind |

**Operator recovery:** leave mid-unit hands if working → start **new Mind** → open `$fleet` + overlay; one cycle or re-arm → set `mind.agent` (plan Hand rebind if harness changed) → optional temp-runtime note → do **not** stop product hands unless rebinding them.

**Scheduler honesty:** durable interval only helps if **some** session is alive. Dead Mind → operator reattach or run manually.

Always write fallbacks into baseline + fleet per-hand runtime fields.

## Codex doorbell + reinit fallback

**Problem:** Codex parks at ready prompt after a unit. Back-to-back wake text can stay in the composer if Enter arrives before the TUI is ready.

**Policy:** `agent=codex` **done** + next work exists → pointer doorbell first through `fleet-doorbell.sh`. The helper uses a Codex submit-settle delay before Enter. Reinit is fallback recovery, not the normal wake.

| Doorbell first | Reinit fallback |
| --- | --- |
| Turn-end / ready-to-merge **and** bag has next target | Process down + open tasking or standby with current law |
| `completed` or long `waiting_for_input` + **open tasking** | Approval/failure state; capacity/connection recovery |
| Unblock (pin-refresh, merge) + open tasking — current one-line fact | Doorbell text remains stuck after retry; stale bootstrap repeats |
| Theme switch in same cwd | Operator wants clean slate / cwd rehome |

### Prefer project script

| Command | Role |
| --- | --- |
| `doctor` / `doctor hand-N` | Bag-aware health; no kill |
| `heal` / `heal hand-N` | Auto-reinit idle/done/error + open tasking |
| `snapshot` / `snapshot hand-N` | Forensic dump (pane, board, fleet) |
| `classify` / `status` | Pane class / status |
| `reinit hand-N --boot '…'` | One Hand; refuse if running unless FORCE |
| `reinit-all --boot-template '…{name}…'` | Sparingly; budget still applies |

Exit (reinit): `0` ok · `1` hard · `2` **stuck_idle** · `3` bad args. Doctor: `0` healthy · `1` unhealthy · `2` trust/stuck/starving.  
Exit 2 → one more reinit same cycle OK; still stuck next cycle → model ladder or snapshot + operator.

**Classify traps:** do not treat tool `timeout N cmd` or `error: test failed` as `failed` with connection detail when the runtime is live and working. Prefer current bottom prompt evidence and doctor evidence over raw greps of older scrollback.

**Manual fallback:** kill agent children of pane only; leave tmux+shell; launch without `exec` via fleet `agent_launch`; short bootstrap; record `last_codex_reinit_at`.

**Forbidden:** multi-paragraph argv holds; repeated doorbells without submit-settle/inspection; reinit `running` without FORCE; `exec codex`.

Mind under thrash: doorbell once, then **doctor/snapshot/reinit** over hand greps + stacked wakes.

## Canonical runtime observation

Fleet configuration retains backend-specific bindings, but sensor output and baseline wake records use one backend-neutral shape:

```json
{
  "runtime": {
    "kind": "tmux",
    "target": "hand-1:1.1",
    "state": "waiting_for_input",
    "process_state": "running",
    "confidence": "medium",
    "evidence": [],
    "tail": "…",
    "tail_hash": "0123456789abcdef"
  }
}
```

A `vivi_pty` observation has the same keys plus optional `socket`. Canonical states are:

```text
starting | waiting_for_input | submitting | running | approval_required |
completed | failed | stopped | unknown
```

No backend-specific state aliases (`idle_prompt`, `done_idle`, `trust_prompt`, `down`) or flat locator fields (`runtime_target`, `runtime_state`, `tmux_target`) appear in sensor rows. `runtime_states` is the role→state summary persisted in the baseline. Wake records store the same nested locator subset: `runtime.kind`, `runtime.target`, and optional `runtime.socket`.

## `assignment_mode` (Hand + Head session policy)

Per-role field on every Hand and Head. Controls how Mind prepares the agent
session when starting a **new work item** (new task/need handle), not mid-unit
progress wakes.

| Value | Meaning | Typical use |
| --- | --- | --- |
| **`new`** | Fresh agent session for this assignment (`/new` in-pane, or recreate session leaving shell/cwd). Drop prior chat context. | Cold-cache fleets; high context cost; CEO-style one-shot analysis; default when operator wants no transcript carry-over |
| **`compact`** | Same process; send `/compact` (or harness equivalent), then pointer doorbell with the new handle | Theme switch same cwd when context is still coherent |
| **`continue`** | Same session; pointer doorbell only (no compact, no recreate) | Cheap follow-ups; sticky multi-step units that intentionally share context |
| **`restart`** | Kill the agent process (or whole runtime slot) and relaunch via `agent_launch` / `fleet-runtime.py restart` before the assignment boot | Stuck harness; model/provider flag change; dirty process that `/new` cannot clear |

**Resolved by:** `fleet_common.resolve_assignment_mode` / `fleet-resolve.py`
(`assignment_mode` on the binding JSON and `RESOLVED_ASSIGNMENT_MODE` in shell).

**Default when unset:** `continue` (historical Hand behavior: pointer into the
existing pane).

**Legacy:** `clean_slate_per_assignment: true` → `new`; `false` → `continue`.
If both are set, **`assignment_mode` wins**. Prefer the new field; do not add
`clean_slate_per_assignment` on new fleets.

**Doorbell applies modes automatically** (`scripts/fleet-doorbell.sh`):

| When | Behavior |
| --- | --- |
| New `--handle` (≠ last wake handle for that role) | Apply role `assignment_mode` before pointer |
| Same `--handle` rewake | Skip prepare; pointer only (still refuses if running) |
| `--no-prepare` | Force pointer-only |
| `--force-prepare` | Apply mode even on same handle |
| `--mode <m>` | Override fleet.json for this call |
| Stopped runtime | Start (or restart) before pointer when needed |

Prepare steps:

- `new` — idle → send `/new` → wait idle → pointer (or start fresh process if stopped)
- `compact` — idle → `/compact` → wait idle → pointer
- `continue` — pointer only (auto-start if stopped)
- `restart` — `fleet-runtime.py restart --force` → wait idle → pointer

Same-handle rewakes and mid-unit progress do **not** re-apply mode. Durable
context for `new`/`restart` seats: Heads use **vivi memos**; Hands re-read the
task/need and mail To mind@ — not prior chat. Prefer calling doorbell with the
new handle rather than hand-rolling `/new` + pointer.

**Not the same as:**

| Field | Concern |
| --- | --- |
| `assignment_sticky` | Lane/packet ownership stickiness |
| `runtime_sticky` | Runtime binding stickiness |
| `reinit_after_kill` / `codex_reinit_after_kill` | Recovery after process death |

`verify-fleet-json.py` rejects unknown mode strings.

## Fleet config schema

Recommended keys (extend freely; skill cares about meanings):

```json
{
  "version": 1,
  "default_hand": "hand-1",
  "legacy_hand_identity": "codex",
  "fleet_id": "mgs",
  "tmux_layout": "legacy",
  "git": {
    "main_cwd": "/path/to/primary/git/checkout",
    "note": "optional — workspace containers without .git at fleet root; sensors use this tip"
  },
  "fleet_posture": {
    "mode": "growth",
    "reason": "campaign spine — or standby for on-call fleets",
    "since": "2026-07-11T00:00:00Z",
    "wake_triggers": ["operator product task", "operator@ need"],
    "ceo_continuity_min_hours": 6
  },
  "lane_lifecycle": {
    "stale_after_cycles": 5,
    "resume_stale_after_hours": 24,
    "release_grace_cycles": 2,
    "worktree_cleanup": "manual"
  },
  "mind_inbox": "mind",
  "operator_inbox": "operator",
  "operator_inbox_note": "Human escalations only (problems/blockers/guidance). Not status. No tmux.",
  "head_report_inbox": "mind",
  "head_report_inbox_note": "Inbox Heads report into for sweep-completion detection. Default mind (process law: To mind@). Legacy camps may set reviewer until renamed.",
  "steward": {
    "enabled": false,
    "note": "default OFF — operator must enable:true and explicitly ask to arm per fleet; loop ≠ steward",
    "tmux_session": "steward",
    "tmux_window": "steward",
    "tmux_target": "steward:1.1",
    "grace_sec": 900,
    "poll_sec": 60,
    "mode": "hold",
    "notify": {
      "operator_board": true,
      "external_email": false,
      "account": "personal-proton",
      "to": [],
      "dedupe_hours": 6,
      "preauthorized_exec_send": false
    }
  },
  "binding_rule": "legacy: mail_identity==tmux_session; session_per_fleet: mail_identity==role, tmux_session==fleet_id, tmux_window==role; always use tmux_target",
  "mind": {
    "agent": "pi",
    "agent_model": "gpt-5.5",
    "provider": "openai-codex",
    "thinking": "medium",
    "note": "Pi is the product harness; Mind is not a fleet process slot"
  },
  "agent_policy": {
    "hands_follow_mind_harness": true,
    "heads_prefer_pi": true
  },
  "preferred_models": {
    "pi": {
      "mind": { "provider": "openai-codex", "model": "gpt-5.5", "thinking": "medium" },
      "hand": { "provider": "openai-codex", "model": "gpt-5.5", "thinking": "medium" },
      "head": { "provider": "zai", "model": "glm-5.2", "thinking": "high|xhigh" }
    }
  },
  "tooling": {
    "pi": { "binary": "/abs/path/to/pi" },
    "codex": { "binary": "/abs/path/to/codex" },
    "opencode": { "binary": "/abs/path/to/opencode" },
    "vivi": { "binary": "/abs/path/to/vivi" }
  },
  "runtime_fallback": {
    "pi_model_ladder_mind": ["openai-codex/gpt-5.5", "zai/glm-5.2"],
    "pi_model_ladder_hand": ["openai-codex/gpt-5.5", "zai/glm-5.2"],
    "pi_model_ladder_head": ["zai/glm-5.2"],
    "hand_harness_follows_mind": true,
    "heads_prefer_pi": true
  },
  "hands": {
    "hand-1": {
      "mail_identity": "hand-1",
      "host": "local",
      "tmux_session": "hand-1",
      "tmux_target": "hand-1:1.1",
      "cwd": "/path/to/main",
      "agent": "pi",
      "provider": "openai-codex",
      "agent_model": "gpt-5.5",
      "thinking": "medium",
      "agent_launch": "pi --provider openai-codex --model gpt-5.5 --thinking medium --approve",
      "merges_to_main": true,
      "assignment_sticky": true,
      "runtime_sticky": false,
      "assignment_mode": "new",
      "wake_mode": "tmux_send_keys",
      "min_seconds_between_wakes": 180
    },
    "hand-2": {
      "mail_identity": "hand-2",
      "host": "remote.example",
      "ssh": "ssh -o BatchMode=yes remote.example",
      "cwd": "/path/on/remote/side-lane",
      "agent": "pi",
      "provider": "openai-codex",
      "agent_model": "gpt-5.5",
      "agent_launch": "pi --provider openai-codex --model gpt-5.5 --thinking medium --approve",
      "wake_mode": "tmux_send_keys_via_ssh",
      "merges_to_main": false,
      "assignment_sticky": false,
      "assignment_mode": "continue",
      "packet": { "slug": "…", "branch": "…", "state": "assigned" }
    },
    "auditor-1": {
      "mail_identity": "auditor-1",
      "host": "local",
      "tmux_session": "auditor-1",
      "tmux_target": "auditor-1:1.1",
      "cwd": "/path/to/main",
      "agent": "pi",
      "provider": "openai-codex",
      "agent_model": "gpt-5.5",
      "thinking": "high",
      "agent_launch": "pi --provider openai-codex --model gpt-5.5 --thinking high --approve",
      "merges_to_main": false,
      "assignment_sticky": false,
      "assignment_mode": "new",
      "wake_mode": "tmux_send_keys",
      "min_seconds_between_wakes": 180,
      "note": "review Hand; assignments explicitly invoke $auditor; reports To mind"
    },
    "hand-3": {
      "mail_identity": "hand-3",
      "tmux_session": "hand-3",
      "tmux_target": "hand-3:1.1",
      "cwd": "/path/to/campaign-worktree",
      "agent": "pi",
      "merges_to_main": false,
      "assignment_mode": "continue",
      "lane": {
        "campaign": "docs/CAMPAIGN.md",
        "goal": "factory/goals/example.md",
        "branch": "campaign/example",
        "state": "active",
        "wake_trigger": null
      }
    }
  },
  "head-ceo": {
    "mail_identity": "head-ceo",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "agent_launch": "pi --provider zai --model glm-5.2 --thinking high",
    "assignment_mode": "new",
    "role_prompt": "<fleet-path>/head-ceo-role-prompt.txt",
    "executive_cadence": {
      "every_n_loops": 36,
      "sweep_mode": "expansion"
    }
  },
  "head-cto": {
    "mail_identity": "head-cto",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "executive_cadence": { "every_n_loops": 6 }
  },
  "head-cxo": {
    "mail_identity": "head-cxo",
    "tmux_session": "head-cxo",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "executive_cadence": { "every_n_loops": 12 }
  },
  "head-cso": {
    "mail_identity": "head-cso",
    "agent": "pi",
    "executive_cadence": { "every_n_loops": 0, "sweep_mode": "security" }
  }
}
```

### Head schedule (`executive_cadence.every_n_loops`)

Single dial — no `enabled`, no `self_directed`:

| Value | Meaning |
| --- | --- |
| **0** | **On-call** — sensors never emit scheduled `head_due_*`; Mind files explicit tasks when needed |
| **N ≥ 1** | **Scheduled** — due every `N × mind_loop.interval_sec`; Mind should wake a sweep with persona/posture charter |

```text
sweep_interval_sec = every_n_loops × mind_loop.interval_sec   # only when N >= 1
```

Prefer **explicit** `every_n_loops` on every Head. Legacy: `enabled: false` ≡ 0;
`enabled: true` without N uses posture×role defaults (CTO/CXO/CEO only).

**Mind loop tick (optional).** Base FLEET_CYCLE spacing for Head cadence math:

```json
"mind_loop": { "interval_sec": 300 }
```

Default **`300`** (5 minutes) when omitted. Alias: top-level `loop_interval_sec`.

**Disaster recovery stewardship (optional, top-level).** Default-off; omitted, `enabled:false`, or `tier:"off"` is silent and produces no COO DR due signals.

```json
"disaster_recovery": {
  "enabled": true,
  "tier": "inventory|critical|regulated_or_irreplaceable|off",
  "freshness_check_days": 30,
  "analysis_days": 90,
  "restore_drill_days": null,
  "grace_days": 7
}
```

Default cadences by tier: `inventory` freshness 30d, analysis 90d, no restore drill; `critical` freshness 14d, analysis 60d, restore drill 180d; `regulated_or_irreplaceable` freshness 7d, analysis 30d, restore drill 90d. `grace_days` defaults to 7. This cadence is calendar/maturity-triggered and independent of `executive_cadence.every_n_loops`.

Baseline receipts are separate evidence state under `mind-baseline.json.disaster_recovery` and are never auto-derived from config, directories, repository size, remotes, or backup-job success:

```json
"disaster_recovery": {
  "last_freshness_check_at": "2026-07-01T00:00:00Z",
  "last_analysis_at": "2026-07-01T00:00:00Z",
  "last_restore_drill_at": null,
  "last_report_handle": "abc123",
  "last_report_at": "2026-07-01T00:00:00Z",
  "last_status": "partial|ok|unknown|contradicted",
  "last_coverage": "summary only, no manifests",
  "last_rpo": "unknown|...",
  "last_rto": "unknown|...",
  "last_restore_evidence": "none|receipt summary"
}
```

No receipts plus an enabled policy makes analysis due first; sensors never schedule a meaningless freshness-only first pass. Freshness receipts never set restore proof. Receipt timestamps materially in the future are invalid/unknown (no clock-skew tolerance is currently granted), not clamped to age zero or treated as fresh. Sensor output includes compact policy/receipt/due state and signals (`head_due_coo_dr_freshness`, `head_due_coo_dr_analysis`, `head_due_coo_dr_restore_drill`, plus `head_overdue_*` after grace). Sensors do not page the operator, file COO assignments, perform restore work, or mutate baseline receipts. Existing COO DR assignments are reported as backpressure so Mind does not duplicate them.

**Executive cadence (optional, per head).** Opt-in block: `{enabled, every_n_loops?, sweep_mode?}`.
When `enabled`, `fleet-sensors.py` surfaces `head_due_<role>` after the **cadence
interval** since last completion mail (pane not `running`). Completion = new mail
from the head's `mail_identity` or `legacy_aliases` in `head_report_inbox` (default
**`mind`**). Durable state: baseline `head-*`.`last_report_handle` / `last_report_at`.

**Interval law:**

```text
sweep_interval_sec = every_n_loops × mind_loop.interval_sec
```

`every_n_loops` is **configurable per head** via `executive_cadence.every_n_loops`.
When unset, it defaults from the posture × role table below (overridable default
ladder — not immutable law):

| Posture | head-cto | head-cxo | head-ceo | @ `interval_sec=300` |
| --- | --- | --- | --- | --- |
| **growth** | ×6 | ×12 | ×36 | 30m / 1h / 3h |
| **standby** | ×18 | ×36 | ×72 | 1.5h / 3h / 6h |
| **dormant** | — | — | — | sweeps **paused** |

`every_n_loops: 0` is on-call; `N >= 1` is scheduled (interval =
`N × mind_loop.interval_sec`). Prefer explicit N on every Head. Legacy
`enabled` folds into that resolution; `self_directed` is ignored.
`interval_sec` and `min_seconds_between_sweeps` are **ignored** (legacy).
`sweep_mode` is free-form for Mind assign flavor; when unset, sensors default
from posture: growth → `expansion`, standby → `stewardship`, dormant →
`paused`. Detail: [`fleet-posture.md`](fleet-posture.md). Validate with
`verify-fleet-json.py`.

**Never hardcode model strings as Hand identity.** Read `agent_launch` from fleet. Hand `agent` should match `mind.agent` unless baseline records operator exception. Defaults from preferred_models; override for capacity/experiment, re-align when quiet.

Prefer absolute paths from fleet `tooling` over `which` every cycle.

## Baseline schema

```text
last_cycle, last_cycle_at, last_cycle_kind, last_cycle_summary
quiet_streak                      # consecutive no-signal product cycles
turns_since_operator_message      # Mind cycles since last human operator prose
mind_mode                         # autonomous | interactive
mind_mode_override optional       # ops_only | deep | clear
last_operator_message_at
operator_recap                    # short material status since last operator message
operator_mail                     # {identity, open_count, last_filed_at, last_presented_*}
steward                           # {armed, last_rearm_at, tripped, tripped_at, last_external_*}
mind_loop.last_successful_cycle_at
mind_session optional             # advisory attach lock {label, host, pid, attached_at}
mind_loop.state                    # running | detached | wound_up | dead_man_tripped | …
fleet_posture optional            # mirror of fleet.json: mode growth|standby|dormant, reason, last_ceo_continuity_at
mind_watch_cursor_path optional
last_actionable_fingerprint
  <role>_mail_top                 # newest addressed mail observed this cycle
  <role>_mail_pending             # changed mail waiting for an idle-pane doorbell
pending_reviews[]
pending_merges[]
active_packets{} or active_lanes{}
lane_progress{}
  # hand -> {signature, unchanged_cycles, last_progress_at, candidate,
  #          reason stale_bound|empty_retained|resume_stale,
  #          binding, git, has_open_work}
lane_lifecycle{}
  # hand -> {state active|stale_candidate|reconciling|parked|cooldown|released,
  #          reason, truth_report_handle?, blocker_handle?, wake_trigger?,
  #          cooldown_since_cycle?, release_after_cycle?}
last_thorough_cycle, last_thorough_fingerprint
fleet_mirror / runtime_states
last_hand_wake                     # nested runtime locator + per-role by_hand records
last_codex_reinit_*, last_runtime_fallback
head-ceo.{awaiting_report, last_assign_handle, last_reinit_at,
          last_report_handle, last_report_at}   # assign loop + cadence completion
side_lane_candidates[] optional
  # {id, title, why_off_main, seams, packet_scope,
  #  effort S|M|L|XL, est_tokens, est_basis,
  #  status open|bound|done|dropped, filed_handle?,
  #  actual_tokens?, actual_source harness|mind_estimate|unavailable?, closed_at?}
cost_calibration[] optional
  # {id, title, head_ceo_effort, est_tokens, actual_tokens?, actual_source,
  #  delta_ratio?, head_ceo_model, hand_model, closed_at, notes}
  # Codex TUI: often actual_source=unavailable — never invent actual_tokens
head-cto.{last_report_handle, last_report_at, …}   # gate-honesty / architecture cadence
head-cxo.{last_report_handle, last_report_at, …}
mind_loop.{state, handoff, mechanism, …}
half_dead[] optional              # path, class A/B/C, age_cycles, note
polish_advisory optional:
  score_threshold          # default 500
  max_files_per_task       # default 3
  max_tasks_per_cycle      # default 1
  script optional
  last_scan_head, last_scan_at, last_top[], open_polish_paths[], last_filed_handle
housekeeping_advisory optional:
  last_filed_at, last_filed_head, last_reason
  open_handle optional
  min_commits_for_large_merge optional
```

| Counter | Meaning |
| --- | --- |
| `quiet_streak` | Product silence |
| `turns_since_operator_message` | **Human** silence in Mind chat |

Busy fleet can have `quiet_streak=0` and still be **autonomous** if operator silent ≥3 cycles. Scheduled wakes use **`FLEET_CYCLE`** prefix (main skill / mind-cycle).

Ignore-lists may live in baseline (`ignore_bag_handles`, `ignore_subjects_prefixes`) without deleting board history.

**Polish advisory:** after main lands, Mind runs `$polish`’s `suggest-polish-files.py` (read-only). Score ≥ threshold → one bounded polish **task**. Defaults: `mind-cycle.md`.

**Housekeeping advisory:** file `$housekeeping` only at **major inflection** (campaign end / large merge / stage closeout / operator). Never every land. Procedure: `mind-cycle.md`.

**Lane lifecycle:** sensors persist `lane_progress`; Mind owns the separate
disposition state. Candidate signals trigger reconciliation, not teardown.
`worktree_cleanup` is fixed to `manual`; lane release only clears assignment and
runtime capacity. Procedure: `mind-cycle.md`.

```json
"polish_advisory": {
  "score_threshold": 500,
  "max_files_per_task": 3,
  "max_tasks_per_cycle": 1,
  "script": null
},
"housekeeping_advisory": {
  "note": "file only at major inflection; one open task at a time"
}
```

## Fleet wind-down and rearm

Orderly shutdown (lifecycle **Retire**).

| When | |
| --- | --- |
| Operator requests wind-up / stop after N cycles | |
| Map empty + bags empty + no pending merge queue for long quiet streak | |
| Orchestrator must stop; product residue can wait | |

### Procedure

1. **Stop** filing new keep-screen-moving targets (unless last drain)
2. **Absorb** finished lands: HEADs, light-accept, honest `pending_reviews`/`pending_merges` (no invent theme RTMs)
3. **Classify each slot:** empty+clean/idle → drop; mid-unit product → keep or operator-stop with residual; human/env gate only → finished for wind-down, leave need open
4. **Drop panes** for finished hands/Heads (`tmux kill-session`); leave mid-product if residual drain wanted
5. **Baseline** `mind_loop.state = wound_up`: dropped/kept panes, tips, residual handles, handoff
6. Optional pointer to kept hands: fleet wound up; continue bag or idle
7. Cancel Mind `/loop` or harness scheduler **in operator session** if stopping loop
8. **`steward.sh disarm --project <root>`** same turn — **per fleet** if multi-attached
9. Clear or stamp `mind_session` / `mind_loop.state = wound_up` (or `detached`)

| Wind-down is not | |
| --- | --- |
| “All side tips on main” | Re-check ancestry separately |
| Permission to `stash`/`reset` foreign dirt | |
| Auto-closing open needs | Env gates / operator decisions stay on board |

### Rearm

1. Recreate tmux sessions from fleet (`cwd`, `agent_launch`)
2. Read baseline handoff + open taskings
3. Refill starvation if maps still have work
4. Set `mind_loop.state = armed|running`; clear or archive wind-up block
5. Optional head-ceo assign if structural debt remains
6. Mind remains operator TUI — no second Mind process
