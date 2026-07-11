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
python3 scripts/fleet-sensors.py --project <root>            # JSON
python3 scripts/fleet-sensors.py --project <root> --text
python3 scripts/fleet-sensors.py --project <root> --no-watch # skip mailspace watch
```

Emits board status, open handles, pane classes, git tip, fingerprint, `signals[]`, `quiet_hint`. Exit `0` ok · `1` hard · `2` partial.

### `fleet-baseline.py`

```bash
python3 scripts/fleet-baseline.py get -p <root>
python3 scripts/fleet-baseline.py bump -p <root> -s 'sleep' --quiet \
  --fingerprint-file /tmp/sensors.json
python3 scripts/fleet-baseline.py rearm-note -p <root>
python3 scripts/fleet-baseline.py wound-up -p <root> -s 'wound_up' --dropped hand-1,hand-2
```

`--project/-p` before or after subcommand. `bump` increments `last_cycle`, quiet/mode counters, stores fingerprint/pane_classes, touches `mind_loop.last_successful_cycle_at` (pair with `steward.sh rearm`).

### `fleet-doorbell.sh`

```bash
scripts/fleet-doorbell.sh --project <root> hand-1 [--handle HEX] [--note '…'] [--force]
```

Resolves fleet.json `tmux_target`; refuses running/down/rate-limit unless `--force`; records `last_hand_wake`.

### `codex-reinit.sh` (fallback)

```bash
PROJECT=/path/to/fleet FLEET=/path/to/fleet.json scripts/codex-reinit.sh doctor
scripts/codex-reinit.sh heal hand-3
scripts/codex-reinit.sh reinit hand-1 --boot 'HAND WAKE …'
scripts/codex-reinit.sh classify hand-2
```

| Rule | Detail |
| --- | --- |
| Defaults | `PROJECT` from cwd or parent of `FLEET`; `FLEET`=`$PROJECT/.vivi/fleet.json` |
| Launch | Prefer Hand **`agent_launch`** (after `cd` to fleet cwd). If empty: `codex -m <agent_model> -c model_reasoning_effort=xhigh` (`CODEX_EFFORT` / `--model` overrides). Never `exec codex` |
| Exit | reinit `0/1/2 stuck_idle/3`; doctor `0/1/2` (script header) |
| Symlink | Fleets may wrap via `.vivi/codex-reinit.sh` |

### `steward.sh`

See [`dead-man.md`](dead-man.md). `arm` / `rearm` / `disarm` / `check` / `clear` / `loop`.

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
codex_model_ladder_mind:  [ gpt-5.6-sol@medium, … ]
codex_model_ladder_hand:  [ gpt-5.6-luna@xhigh, … ]
grok_model_ladder:        [ grok-4.5, … ]
head_pi_model:            [ glm-5.2@high, glm-5.2@xhigh, … ]
```

**On `error_capacity`:**

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

Do **not** default to “flip H3 to pi while Mind stays Grok.”

Harness flip = update `mind.agent` + every Hand’s `agent` + `agent_launch` + `wake_mode`, clean launch. **Assignment unchanged.**

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
| `done_idle` or long `idle_prompt` + **open tasking** | Trust/error prompt; capacity/connection recovery |
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

**Classify traps:** do not treat tool `timeout N cmd` or `error: test failed` as `error_connection` when pane is live Working. Prefer doctor evidence over raw greps.

**Manual fallback:** kill agent children of pane only; leave tmux+shell; launch without `exec` via fleet `agent_launch`; short bootstrap; record `last_codex_reinit_at`.

**Forbidden:** multi-paragraph argv holds; repeated doorbells without submit-settle/inspection; reinit `running` without FORCE; `exec codex`.

Mind under thrash: doorbell once, then **doctor/snapshot/reinit** over hand greps + stacked wakes.

## Fleet config schema

Recommended keys (extend freely; skill cares about meanings):

```json
{
  "version": 1,
  "default_hand": "hand-1",
  "legacy_hand_identity": "codex",
  "fleet_id": "mgs",
  "tmux_layout": "legacy",
  "mind_inbox": "mind",
  "operator_inbox": "operator",
  "operator_inbox_note": "Human escalations only (problems/blockers/guidance). Not status. No tmux.",
  "steward": {
    "enabled": true,
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
    "agent": "grok",
    "agent_model": "grok-4.5",
    "note": "Product harness for Hands; Mind is not a fleet process slot"
  },
  "agent_policy": {
    "hands_follow_mind_harness": true,
    "heads_prefer_pi": true
  },
  "preferred_models": {
    "grok": { "mind": "grok-4.5", "hand": "grok-4.5" },
    "codex": {
      "mind": { "model": "gpt-5.6-sol", "effort": "medium" },
      "hand": { "model": "gpt-5.6-luna", "effort": "xhigh" }
    },
    "head": { "agent": "pi", "model": "glm-5.2", "thinking": "high|xhigh" }
  },
  "tooling": {
    "pi": { "binary": "/abs/path/to/pi" },
    "codex": { "binary": "/abs/path/to/codex" },
    "grok": { "binary": "/abs/path/to/grok" },
    "vivi": { "binary": "/abs/path/to/vivi" }
  },
  "runtime_fallback": {
    "grok_model_ladder": ["grok-4.5"],
    "codex_model_ladder_mind": ["gpt-5.6-sol"],
    "codex_model_ladder_hand": ["gpt-5.6-luna"],
    "head_pi_model_ladder": ["glm-5.2"],
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
      "agent": "grok",
      "agent_model": "grok-4.5",
      "agent_launch": "…",
      "merges_to_main": true,
      "assignment_sticky": true,
      "runtime_sticky": false,
      "wake_enabled": true,
      "wake_mode": "tmux_send_keys",
      "min_seconds_between_wakes": 180
    },
    "hand-2": {
      "mail_identity": "hand-2",
      "host": "remote.example",
      "ssh": "ssh -o BatchMode=yes remote.example",
      "cwd": "/path/on/remote/side-lane",
      "agent": "grok",
      "wake_mode": "tmux_send_keys_via_ssh",
      "merges_to_main": false,
      "assignment_sticky": false,
      "packet": { "slug": "…", "branch": "…", "state": "assigned" }
    }
  },
  "head-ceo": {
    "mail_identity": "head-ceo",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "agent_launch": "pi --provider zai --model glm-5.2 --thinking high",
    "clean_slate_per_assignment": true,
    "role_prompt": "<fleet-path>/head-ceo-role-prompt.txt"
  },
  "head-cto": {
    "mail_identity": "head-cto",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "self_directed": true
  },
  "head-cxo": {
    "mail_identity": "head-cxo",
    "tmux_session": "head-cxo",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "self_directed": true
  }
}
```

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
mind_watch_cursor_path optional
last_actionable_fingerprint
pending_reviews[]
pending_merges[]
active_packets{} or active_lanes{}
last_thorough_cycle, last_thorough_fingerprint
fleet_mirror / pane_classes
last_hand_wake_*, last_codex_reinit_*, last_runtime_fallback
head-ceo.{awaiting_report, last_assign_handle, last_reinit_at}
side_lane_candidates[] optional
  # {id, title, why_off_main, seams, packet_scope,
  #  effort S|M|L|XL, est_tokens, est_basis,
  #  status open|bound|done|dropped, filed_handle?,
  #  actual_tokens?, actual_source harness|mind_estimate|unavailable?, closed_at?}
cost_calibration[] optional
  # {id, title, head_ceo_effort, est_tokens, actual_tokens?, actual_source,
  #  delta_ratio?, head_ceo_model, hand_model, closed_at, notes}
  # Codex TUI: often actual_source=unavailable — never invent actual_tokens
head-cto.last_report_*, head-cxo.last_report_*
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
