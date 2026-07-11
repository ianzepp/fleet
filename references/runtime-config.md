# Runtime fallback, config, baseline, wind-down

Load for capacity recovery, Codex reinit scripts, fleet/baseline schemas, or camp wind-up.

## Skill script: `scripts/codex-reinit.sh`

Camp-agnostic Codex doctor/heal/reinit (ported from faberlang production helper).

```bash
# from camp root, or set PROJECT + FLEET
PROJECT=/path/to/camp FLEET=/path/to/fleet.json \
  path/to/skills/fleet/scripts/codex-reinit.sh doctor
path/to/skills/fleet/scripts/codex-reinit.sh heal hand-3
path/to/skills/fleet/scripts/codex-reinit.sh reinit hand-1 --boot 'HAND WAKE …'
path/to/skills/fleet/scripts/codex-reinit.sh classify hand-2
```

- Defaults: `PROJECT` from cwd or parent of `FLEET`; `FLEET` = `$PROJECT/.vivi/fleet.json` (legacy filename `hunter-fleet.json` still accepted)
- Never `exec codex`; pane shell stays parent; short bootstrap only
- Exit codes: reinit `0/1/2 stuck_idle/3`; doctor `0/1/2` as in script header
- Camps may symlink into `.vivi/codex-reinit.sh` and wrap env

## Runtime fallback (capacity / unavailability)

**Invariant:** assignment (hand-N, side lane, merge rights) does **not** change when a model is full. Only **runtime** rebinds (`agent_model`, `agent_launch`, and only carefully `agent` / `wake_mode`). Source of truth: fleet `runtime_fallback` + per-hand fields + **Harness alignment**.

### Failure classes

| Class | Cues | First response |
| --- | --- | --- |
| **Capacity** | over capacity, rate limit, 429, usage limit, “try again later” | Step model ladder (**same harness as Mind** for Hands) |
| **Auth / quota hard stop** | account exhausted, login required | Park that harness; escalate operator; pivot other hands |
| **Connection** | ECONNRESET, disconnect | One same-model reinit; then capacity ladder |
| **Harness dead** | crash loop, session destroy | Recreate shell + launch; if loop → model ladder, then **Mind-aligned** harness recovery |

### Model ladder

Prefer staying on the **Mind-aligned product harness** while possible. Fleet names an ordered ladder **per harness** (example shape only — do not invent ids not in fleet):

```text
codex_model_ladder_mind:  [ gpt-5.6-sol@medium, … ]
codex_model_ladder_hand:  [ gpt-5.6-luna@xhigh, … ]
grok_model_ladder:        [ grok-4.5, … ]
head_pi_model:            [ glm-5.2@high, glm-5.2@xhigh, … ]
```

**When `error_capacity` on a Hand (or similar):**

1. Confirm not mid-successful `running` with real progress → wait
2. Advance that Hand’s `agent_model` one step **on the same harness**; rewrite `agent_launch`
3. **Reinit** (Codex) or doorbell after restart (Grok) with short bootstrap — not stacked wakes
4. Baseline `last_runtime_fallback` {hand, from, to, reason, cycle, at}
5. **At most one model step per Hand per cycle** — do not spin the whole ladder
6. Ladder exhausted → park Hand or escalate; **do not** silently move the Hand to a different harness while Mind stays on the original (exception requires operator note + plan to re-align)

**Heads** may use their own ladder / alternate harness without waiting for Mind.

### Harness fallback (after model ladder exhausted)

**Hands** stay harness-aligned with Mind. Product harness flip is a **fleet-wide Mind decision**, not a per-Hand convenience:

1. Exhaust same-harness model ladder on the affected Hand(s)
2. If Mind’s harness is fleet-dead: recover **Mind** (operator if needed), set new `mind.agent`, then rebind **all Hands** to that harness on clean breakpoints
3. Temporary single-Hand exception (operator only): record in baseline; still prefer re-align ASAP
4. Heads may already be on alternate harnesses; leave them unless they fail too

Do **not** treat “flip H3 to pi while Mind stays Grok” as the default recovery.

Harness flip for the product plane = update `mind.agent` + every Hand’s `agent` + `agent_launch` + `wake_mode`, then clean launch. **Assignment unchanged.**

### Per-cycle budget (anti-thrash)

- Max **~2** capacity-driven model flips per cycle fleet-wide for product slots
- Product **harness** flips are rare (Mind-plane); do not burn the budget on them casually
- Normal reinit-after-unit does **not** count as fallback
- Never flip a `running` Hand for capacity unless pane shows hard capacity error
- Prefer flipping **idle/error** product slots first (model only, same harness)

### Mind / orchestrator hard limit — recovery

If the Mind session dies (hard quota / dead harness), it cannot self-heal inside the dead session.

| Situation | What works | What does not |
| --- | --- | --- |
| Soft pressure | Keep product on **same-harness cheaper models**; shorten prose; skip nonessential Head wakes | Migrating Hands onto a different harness while Mind stays put |
| Session alive but tool errors | Fail-fast sleep; one-line baseline; next fire retries | Infinite retry same turn |
| **Hard stop** | **Operator recovery** (below) | Silent hope; thrashing hands without a live Mind |

**Operator recovery:**

1. Leave mid-unit product hands alone if still working
2. Start a **new Mind** session (same or temporary harness) in the project
3. Open `$fleet` + camp overlay; run **one** cycle or re-arm scheduler
4. Set/update `mind.agent` for the live Mind harness. If Mind harness changed, plan Hand rebind on clean breakpoints
5. Optional fleet note for temporary Mind runtime; revert later
6. Do **not** require product hands to stop for Mind recovery unless rebinding them to the new harness

**Scheduler honesty:** a durable interval task only helps if **some** session is alive to execute it. Dead Mind → operator must reattach or run manually.

Always write fallbacks into baseline and fleet per-hand runtime fields.

## Codex reinit production contract

**Problem:** Codex after a unit parks at ready prompt and does not pull the next tasking item. Stacked wake lines fail or keep **stale bootstrap** alive for hours.

**Policy:** when `agent=codex` is **done** and next work exists → **kill Codex + fresh session + short bootstrap**. One clean start. Harness is a fleet binding, not part of the H-number.

### When to reinit

1. Turn-end / ready-to-merge this cycle **and** bag has (or just received) next target
2. `done_idle` or long `idle_prompt` + **open tasking**
3. Process down + open tasking or need to stand by with current law
4. Unblock (pin-refresh, merge) + open tasking — reinit with **current** one-line fact

### When not

- `running` / mid-unit
- Tasking empty + operational pause only (refill first if map has next)
- Already reinited this Hand this cycle (unless died again)
- Fleet `agent` is not `codex`

### Prefer a project script

Camps often ship a reinit helper (path is camp-local). Suggested commands:

| Command | Role |
| --- | --- |
| `doctor` / `doctor hand-N` | Bag-aware health; no kill |
| `heal` / `heal hand-N` | Auto-reinit slots that need it (idle/done/error + open tasking) |
| `snapshot` / `snapshot hand-N` | Forensic dump (pane, board, fleet) |
| `classify` / `status` | Pane class / status |
| `reinit hand-N --boot '…'` | One Hand; refuse if running unless FORCE |
| `reinit-all --boot-template '…{name}…'` | Sparingly; budget still applies |

Suggested exit codes (reinit): `0` ok · `1` hard fail · `2` **stuck_idle** (ready but never Working) · `3` bad args.  
Doctor: `0` healthy · `1` unhealthy · `2` trust/stuck/starving.  
On reinit exit 2: one more reinit same cycle OK; if still stuck next cycle → model ladder or snapshot + operator.

**Classify traps:** do not treat tool `timeout N cmd` or `error: test failed` as `error_connection` when pane is live Working. Prefer doctor evidence over raw greps.

**Manual fallback** if script missing: kill agent children of pane only; leave tmux+shell; launch without `exec` via fleet `agent_launch`; short bootstrap; record `last_codex_reinit_at`.

**Forbidden:** multi-paragraph argv holds; stacking wakes on finished ready; reinit `running` without FORCE; `exec codex`.

Mind default under thrash: **doctor then heal** over hand greps + stacked wakes.

## Fleet config schema

Recommended keys (extend freely; skill cares about meanings):

```json
{
  "version": 1,
  "default_hand": "hand-1",
  "legacy_hand_identity": "codex",
  "mind_inbox": "mind",
  "binding_rule": "mail_identity == tmux_session token (Hands/Heads only; Mind is operator TUI)",
  "mind": {
    "agent": "grok",
    "agent_model": "grok-4.5",
    "note": "Product harness for Hands; Mind is not a fleet slot / not reviewer"
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
  "head-strategist": {
    "mail_identity": "head-strategist",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "agent_launch": "pi --provider zai --model glm-5.2 --thinking high",
    "clean_slate_per_assignment": true,
    "role_prompt": "<camp-path>/strategist-role-prompt.txt"
  },
  "head-correctness": {
    "mail_identity": "head-correctness",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "self_directed": true
  },
  "head-purity": {
    "mail_identity": "head-purity",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "self_directed": true
  }
}
```

**Never hardcode model strings as Hand identity.** Read `agent_launch` from fleet. Hand `agent` should match `mind.agent` unless baseline records an operator exception. Default model picks come from preferred models; fleet may override for capacity or experiment, then re-align when quiet.

Prefer absolute paths from fleet `tooling` over `which` every cycle (nvm/`pi` often missing from bare Mind shells).

## Baseline schema

Maintain at least:

```text
last_cycle, last_cycle_at, last_cycle_kind, last_cycle_summary
quiet_streak                      # consecutive no-signal product cycles
turns_since_operator_message      # Mind cycles since last human operator prose
mind_mode                         # autonomous | interactive (resolved this cycle)
mind_mode_override optional       # ops_only | deep | clear — operator sticky force
last_operator_message_at          # timestamp or cycle id of last operator prose
operator_recap                    # short material-change list since last operator message
mind_watch_cursor_path optional   # path to vivi mailspace watch --cursor-file
last_actionable_fingerprint   # fleet bags + heads/dirty + panes
pending_reviews[]
pending_merges[]
active_packets{} or active_lanes{}   # slug → head, branch, worker
last_thorough_cycle, last_thorough_fingerprint
fleet_mirror / pane_classes   # (legacy key: hunter_fleet)
last_hand_wake_*, last_codex_reinit_*, last_runtime_fallback   # (legacy: last_hunter_wake_*)
head-strategist.{awaiting_report, last_assign_handle, last_reinit_at}
side_lane_candidates[] optional   # from strategist: {title, why_off_main, seams, status open|bound|dropped}
head-correctness.last_report_*, head-purity.last_report_*
mind_loop.{state, handoff, mechanism, …}   # armed | running | stopping | wound_up; mechanism e.g. grok_/loop
half_dead[] optional                # path, class A/B/C, age_cycles, note
polish_advisory optional:
  score_threshold          # default 500 — file polish task only if score >= this
  max_files_per_task       # default 3
  max_tasks_per_cycle      # default 1
  script optional          # override path to suggest-polish-files.py
  last_scan_head           # main tip last scanned (skip re-scan until HEAD moves)
  last_scan_at
  last_top[]               # {path, score} sample from last run
  open_polish_paths[]      # paths already covered by open polish tasks
  last_filed_handle optional
housekeeping_advisory optional:
  last_filed_at
  last_filed_head          # main tip when housekeeping was filed
  last_reason              # campaign_end | large_merge | stage_closeout | operator
  open_handle optional     # open task handle if any
  min_commits_for_large_merge optional  # camp heuristic; default defer if unsure
```

**Mode counters vs quiet:** `quiet_streak` is product silence (nothing to do). `turns_since_operator_message` is **human** silence in the Mind chat. A busy fleet can have `quiet_streak = 0` and still be **autonomous** if the operator has not spoken for ≥ 3 cycles. Scheduled wakes must use the **`FLEET_CYCLE`** prefix (see main skill / mind-cycle).

Ignore-lists for tasking noise may live in baseline (`ignore_bag_handles`, `ignore_subjects_prefixes`) without deleting board history.

**Polish advisory:** after main lands, Mind runs `$polish`’s `suggest-polish-files.py` (read-only). Score ≥ threshold → one bounded polish **task** to a Hand. Defaults and procedure: `mind-cycle.md`.

**Housekeeping advisory:** Mind files `$housekeeping` only at **major inflection** (campaign end / large merge / stage closeout / operator). Never every land. Procedure: `mind-cycle.md`.

Optional fleet JSON mirror:

```json
"polish_advisory": {
  "score_threshold": 500,
  "max_files_per_task": 3,
  "max_tasks_per_cycle": 1,
  "script": "/Users/ianzepp/work/ianzepp/skills/polish/scripts/suggest-polish-files.py"
},
"housekeeping_advisory": {
  "note": "file only at major inflection; one open task at a time"
}
```

## Fleet wind-down and rearm

Part of orderly camp shutdown (and lifecycle **Retire**).

### When to wind down

- Operator requests wind-up / stop after N cycles
- Map empty + bags empty + no pending merge queue for a long quiet streak
- Orchestrator must stop but product residue can wait

### Procedure

1. **Stop filing new keep-screen-moving targets** unless operator wants one last drain
2. **Absorb** finished lands: note HEADs, light-accept recent ranges, update `pending_reviews` / `pending_merges` honesty (do not invent theme RTMs)
3. **Classify each slot:**
   - empty tasking + clean/idle → finished → eligible to drop pane
   - open product tasking mid-unit → **keep** or operator-stop with residual noted
   - open tasking is only human/env gate → treat as finished for wind-down; leave need open
4. **Drop panes** for finished hands and Heads (`tmux kill-session`); leave mid-product hands if operator wants residual drain
5. **Baseline** `mind_loop.state = wound_up` with: dropped/kept panes, tips, residual open handles, handoff for rearm
6. Optional pointer to kept hands: fleet wound up; continue bag or idle
7. Cancel Mind `/loop` or harness scheduler **in the operator session** if stopping the loop

### What wind-down is not

- Not “all side tips are on main” (re-check ancestry separately)
- Not permission to `stash`/`reset` foreign dirt
- Not auto-closing open needs (env gates, operator decisions stay on the board)

### Rearm

1. Recreate tmux sessions from fleet (`cwd`, `agent_launch`)
2. Read baseline handoff + open taskings
3. Refill starvation if maps still have work
4. Set `mind_loop.state = armed|running`; clear or archive wind-up block
5. Optional head-strategist assign if structural debt remains (e.g. merge-order research)
6. Mind remains the operator TUI — do not recreate a `reviewer` pane
