# Dual channel: Vivi + tmux

Pane ops, wake/reinit, rehome, theme switch, completion mail.

| Channel | Truth of… |
| --- | --- |
| **Vivi** | Board of record — what work exists and is done |
| **tmux** | Process layer — alive, idle, or broken |

**Process address** = fleet.json **`tmux_target`**. Prefer session-per-fleet
for new fleets: session=fleet_id, window=role (`mgs:hand-1.1`). Legacy
single-fleet targets are still supported: session==role (`hand-1:1.1`).

| Concern | Prefer |
| --- | --- |
| “Unit done; evidence is …” | Vivi tasking done (+ optional mail **To mind**) |
| “Pi/compatibility harness idle at prompt with open tasking” | tmux → **pointer doorbell** |
| “Codex doorbell leaves text stuck / pane down / trust or error prompt” | tmux → **reinit fallback** (kill + fresh + short bootstrap) |
| “Over capacity / connection failed / hung Waiting” | tmux → ops intervene (model / retry / restart) |
| “Human must decide / recover / guide a fix” | Vivi **To `operator@`** (need/mail) — not status To mind; `operator-mail.md` |
| “Mind loop dead / cycle ticks stopped” | optional per-fleet **steward** (default OFF) — `dead-man.md`; rearm only if that fleet’s steward is armed |
| Multi-fleet pane address | fleet.json **`tmux_target`** — `multi-fleet.md` |
| “No mail and no pane signal” | do not invent progress; sleep or escalate if bag stale |
| “Fix landed upstream; consumer still red” | Check **pin-relative done** before re-verify doorbell |

Do not rely on completion mail alone (crash prevents send). Idle alone ≠ done: idle + empty may be quiet; idle + open tasking = wake; idle after HEAD move without done-handles still needs bag/Status honesty on thorough cycles.

Remote panes: SSH — `ssh-remote.md`. Vivi needs one coherent mailspace project root.

## Mailspace watch and thread (Vivi ≥ 4.6)

Board liveness + conversation lineage. **Not** IMAP / `vivi sync`. Full flag tables: [`vivi.md`](vivi.md).

```bash
vivi mailspace watch --for <identity> --project <root> [filters…]
# --once --write-cursor  → cheap cycle (prefer)
# --timeout 60s          → paid wait (RTM / Head report)
# Do not unbounded-block on fail-fast cycles

vivi mailspace status --project "$ROOT"
vivi mailspace watch --for mind --project "$ROOT" \
  --once --write-cursor \
  --cursor-file "$ROOT/.vivi/mind-watch.cursor" \
  --json

vivi mail watch --for mind --project "$ROOT" \
  --match-from hand-2 \
  --match-subject-prefix "ready-to-merge" \
  --timeout 60s --until-count 1

vivi mail thread <handle> --project <root> [--json] [--infer] [--limit 50]
```

Prefer `show` first; `thread` for multi-hop / residual / RTM. `--infer` = historical best-effort only. Hand: when replies obscure done-when. Mind: before residual depending on prior mail; absorb head-ceo / RTM. Reply: `vivi mail reply <handle>`; `--reply-to` / lifecycle `--note` captured (Vivi 4.6).

## Binding rule

**Ops always use fleet.json `tmux_target`.** Two layouts:

| Layout | Mail identity | tmux session | Typical `tmux_target` |
| --- | --- | --- | --- |
| **session-per-fleet** (recommended for new fleets) | role (`hand-1`) | `fleet_id` | `mgs:hand-1.1` (window=role) |
| **legacy** (existing one-off fleets) | role (`hand-1`) | role (`hand-1`) | `hand-1:1.1` |

| Mail | tmux binding | Notes |
| --- | --- | --- |
| `mind@…` | **none** | Operator TUI only — no mind tmux |
| `hand-1@…` | `hand-1` or fleet session | Respect base-index; never invent target |
| `head-cto@…` | `head-cto` or fleet session | Heads may be lazy (create on first assign) |

Do **not** hardcode `session == role` when `tmux_target` is set. Multi-fleet detail: [`multi-fleet.md`](multi-fleet.md).

Map lives in **project fleet config**:

```json
{
  "version": 1,
  "default_hand": "hand-1",
  "legacy_hand_identity": "codex",
  "fleet_id": "example",
  "tmux_layout": "session_per_fleet",
  "mind_inbox": "mind",
  "mind_inbox_note": "Board-only To: mind. Process = operator TUI. No tmux for mind.",
  "head_report_inbox": "mind",
  "mind": { "agent": "pi", "note": "Pi is the product harness; Mind is operator session" },
  "agent_policy": {
    "hands_follow_mind_harness": true,
    "heads_prefer_pi": true,
    "codex_reinit_after_kill": true
  },
  "preferred_models": {
    "pi": {
      "mind": { "provider": "openai-codex", "model": "gpt-5.5", "thinking": "medium" },
      "hand": { "provider": "openai-codex", "model": "gpt-5.5", "thinking": "medium" },
      "head": { "provider": "zai", "model": "glm-5.2", "thinking": "high|xhigh" }
    }
  },
  "hands": {
    "hand-1": {
      "mail_identity": "hand-1",
      "tmux_session": "example",
      "tmux_window": "hand-1",
      "tmux_target": "example:hand-1.1",
      "cwd": "/path/to/project",
      "agent": "pi",
      "agent_launch": "pi --provider openai-codex --model gpt-5.5 --thinking medium --approve",
      "merges_to_main": true,
      "wake_mode": "tmux_send_keys",
      "min_seconds_between_wakes": 180
    }
  },
  "heads": {
    "head-ceo": {
      "mail_identity": "head-ceo",
      "tmux_session": "example",
      "tmux_window": "head-ceo",
      "tmux_target": "example:head-ceo.1",
      "agent": "pi"
    },
    "head-cto": {
      "mail_identity": "head-cto",
      "tmux_session": "example",
      "tmux_window": "head-cto",
      "tmux_target": "example:head-cto.1",
      "agent": "pi"
    },
    "head-cxo": {
      "mail_identity": "head-cxo",
      "tmux_session": "example",
      "tmux_window": "head-cxo",
      "tmux_target": "example:head-cxo.1",
      "agent": "pi"
    }
  },
  "binding_rule": "session_per_fleet: mail_identity==role, session==fleet_id, window==role; legacy: mail_identity==tmux_session; always use tmux_target (Hands/Heads only; mind has no tmux)"
}
```

Fleet-specific durable law may live in overlay / project `Agents.md` — **overlay** on this skill.

```bash
vivi mailspace identity add mind --project <root>          # board only
vivi mailspace identity add hand-1 --project <root>
vivi mailspace identity add head-cto --project <root>
tmux new-session -d -s example -n hand-1 -c <cwd>          # Hands/Heads only
# no tmux for mind
```

## Runtime scan (Mind, every cycle — keep cheap)

```text
1. Resolve the configured tmux or vivi_pty binding.
2. Observe process state and terminal evidence through that backend.
3. Normalize into the canonical nested runtime object.
4. Persist role→state in baseline.runtime_states.
```

| Canonical state | Example evidence | Mind action |
| --- | --- | --- |
| `starting` / `submitting` | runtime transition in progress | wait; do not stack input |
| `running` | current `Waiting for response` / live spinner / streaming / progress bar | sleep; do not wake/reinit |
| `waiting_for_input` | Pi input prompt; Codex `›`; opencode `Ask anything...` | Doorbell if open tasking |
| `completed` | finished turn with input prompt restored | Doorbell if work exists; otherwise refill or pause |
| `approval_required` | workspace trust or permission UI | Resolve once; do not treat as running or ready |
| `failed` | capacity, connection, or runtime evidence; inspect `runtime.detail` | model fallback, retry, or reinit by detail |
| `stopped` | process/session absent or exited | recreate runtime + agent |
| `unknown` | insufficient or contradictory evidence | record sample; do not claim certainty or thrash |

Codex: `•` monologue then `›` is often an **answer that stopped**. Back-to-back `HAND WAKE` lines without submit-settle are the failure mode.

Classifiers must prefer current bottom-of-pane prompt evidence over stale
scrollback failures. A live Codex `›` / `codex ›` prompt after an earlier error
is `waiting_for_input`, not `failed`.

**opencode:** pane classification keyed on opencode-specific markers (`OpenCode Zen`, `Build auto`, `Build ·`, `ctrl+p commands`). Bottom status bar determines state:
- `waiting_for_input`: `Ask anything...` in last ~6 lines
- `running`: progress bar `⬝` or `esc interrupt` in last ~6 lines
- Post-response done: `▣` completion marker visible, no progress, normalizes to `completed` or `waiting_for_input`

Rate-limit wakes (`min_seconds_between_wakes`) **only when that Hand already has a prior doorbell** (`last_hand_wake.by_hand.<name>.count ≥ 1`). **No last wake / count 0 → never rate-limit** (cold attach, first wake after recreate). Never `send-keys` into `running` unless operator allows cancel+replace. Prefer project **classify script** over ad-hoc greps (avoids false `failed` with connection detail from tool text like `timeout 1800 ./script`).

| Situation | Action |
| --- | --- |
| `waiting_for_input`/`completed` + open tasking | Pointer doorbell |
| New addressed mail + `waiting_for_input`/`completed`/`unknown` | Pointer doorbell in the same Mind cycle; the cycle is the debounce |
| New addressed mail + `starting`/`submitting`/`running` | Do not interrupt; retry when a later cycle observes readiness |
| Codex pointer text remains in composer / no active transition after submit | Reinit fallback after one retry/snapshot if useful |
| `waiting_for_input` + empty + map has next **product** unit + posture allows | **Starvation** — file next same cycle; then wake/reinit by runtime |
| `waiting_for_input` + empty + posture standby/dormant | Quiet OK — on-call / paused ([`fleet-posture.md`](fleet-posture.md)) |
| `waiting_for_input` + empty + operational pause only | Quiet OK; note reason |
| `waiting_for_input` + empty after unit/theme accept | Not default quiet — absorb/accept → **refill** → wake/reinit |

Never wake on dirty-only mid-flight; never reinit `running` without FORCE policy.

### Wake on addressed mail

Board mail is demand, not cadence. Every Mind cycle compares the newest mail addressed to each configured Hand or Head with the prior successful-cycle fingerprint. A changed top handle emits `mail_for_<role>` and, when the pane is idle, `mail_wake_candidate_<role>`. Mind doorbells the recipient with that handle in the same cycle.

This deliberately uses the Mind cycle as the debounce period: multiple messages between cycles collapse to one wake pointing at the newest inbox state. Do not stack wakes, interrupt a running pane, or wait for `head_due_*`. Executive cadence remains the timer for self-directed sweeps only.

## Agent harness (keyed on fleet `agent`, not H-number)

Mind, Hands, and Heads default to Pi. Provider/model diversity is allowed without changing harness.

| | **Pi** (`agent=pi`) | **Codex compatibility exception** (`agent=codex`) | **opencode compatibility exception** (`agent=opencode`) |
| --- | --- | --- | --- |
| After unit + open tasking | Pointer **doorbell** | Pointer **doorbell** with submit-settle delay | Pointer **doorbell** with explicit lifecycle commands |
| Theme switch same cwd | `/compact` then pointer | Pointer; reinit only for stale/stuck sessions | Pointer; include context because version may scroll away |
| Launch | Use the role's Pi `agent_launch` | Plain `codex …`; never `exec codex` | Plain `opencode`; `--auto` only when explicitly approved |
| Bootstrap | Pointer: identity, handle, `vivi --for` | Same short bootstrap as first user message | Pointer: identity, handle, exact Vivi lifecycle commands |

## Codex doorbell + reinit fallback

**Policy:** Codex Hand **done** + next target → normal pointer **doorbell** first. The helper waits briefly before Enter so Codex submits the composer instead of accumulating stale wake text. Reinit is recovery, not the default wake.

**Doorbell when:** turn-end + next target; `completed` / long `waiting_for_input` + open tasking; unblock + open tasking with **current** one-line fact.

**Reinit when:** process down; trust/error prompt that cannot be accepted inline; Codex text remains stuck after a doorbell retry; stale bootstrap repeats; operator wants a clean slate.

**When not:** `running` / mid-unit; empty + operational pause only (refill first if map has next); `agent` ≠ `codex`.

1. File next task/need **before** launch so a handle exists
2. Doorbell through `fleet-doorbell.sh` so Codex gets submit-settle
3. If it sticks, use `codex-reinit.sh doctor` / `snapshot` / `reinit`
4. Reinit launch must avoid `exec` and use that Hand’s **`agent_launch`** (helper honors it; synthesizes only if empty)
5. One short first message: identity, never merge main (if packet), `vivi --for hand-N`, open handle(s), one verb, optional one-line unblock fact

| Harness | `/goal` |
| --- | --- |
| **Codex** | **Preferred.** Bootstrap may begin `/goal <bounded objective>`; include identity, handle, scope, done condition in same short message |
| **Pi** | Not supported. Plain task pointer/prompt |
| **opencode** | Not supported (TUI-only). Plain pointer with explicit commands. |

Do not stack `/goal` onto a running turn. File board target first; `/goal` only during clean Codex reinit for coherent bounded objective.

Helper: `scripts/codex-reinit.sh` (doctor / heal / reinit / classify). Pass the standard project/fleet/role flags. See `runtime-config.md`.

## Doorbell (wake)

When `waiting_for_input` and Hand has open tasks/needs (or Mind just filed / answered blocking need):

```bash
scripts/fleet-doorbell.sh --project <root> --role hand-1 --handle <hex> --note '…'
# exit 0 sent · 1 refused · 2 usage/config
```

```bash
tmux send-keys -t '<tmux_target>' -l -- '<pointer only>'
tmux send-keys -t '<tmux_target>' Enter
```

**Codex:** use the same helper; it applies a small submit-settle delay before Enter.  
**Pi Hands:** plain pointer doorbell through `tmux send-keys`; keep the session resident.
**opencode compatibility:** plain `tmux send-keys` with no submit-settle delay; include explicit lifecycle commands in the pointer.

### Channel split (mandatory)

| Channel | Allowed content |
| --- | --- |
| **tmux send-keys** | **Tight pointers only** — identity, where to look (handle / folder / doc path), one verb. No essays, no policy dumps |
| **Vivi mail / task / need** | Full done-when, evidence bar, scope, approach, residuals |
| **Agents.md / factory goal / campaign** | Durable multi-agent law, architecture, stage criteria |

Good:

```text
HAND WAKE hand-1. Bag: show <handle>. vivi --project <root> --for hand-1. Continue.
```

```text
HAND WAKE hand-2. Read inbox/mail <handle> then bag. Identity hand-2. Continue.
```

Bad: full multi-agent policy, stage graphs, long defaults lists, quoting forbidden git verbs as “don’t do X.”

Ops interventions stay one-liners; detail to Vivi if needed. Record `last_hand_wake_at`, reason, target in baseline.

## tmux process ops (start / rehome / restart)

**Invariant:** fleet `cwd` / packet `root` (and `worker_cwd` once members exist) should match `tmux display -p -t <target> '#{pane_current_path}'`. Wrong cwd → writes against wrong tree.

**Prefer rehome when:** hand-2+ is reassigned, the pane has the wrong cwd, the operator wants a clean Pi session, or the process is down.

Prefer a pointer doorbell when cwd and identity are already correct. Reinit only for stale/stuck sessions, process death, clean-slate operator preference, or cwd rehome.

### Packet rehome sequence (Pi TUI in tmux)

```text
1. Runtime must be waiting for input unless the operator allows cancellation.
2. Exit Pi cleanly and wait until pane_current_command is a shell.
3. Recreate or retarget the tmux session/window with `-c <packet-or-main-cwd>`.
4. Start the role's configured Pi `agent_launch` from that cwd.
5. Verify pane path and process, then send one short bootstrap pointer.
```

Bootstrap after restart remains **pointer-only**. Full assignment stays in Vivi + `PACKET.md`.

| Do | Don't |
| --- | --- |
| Use `tmux send-keys -t … -l -- '…'` for literal text | Stack wake messages into a busy pane |
| Launch the exact Pi command from `fleet.json` | Invent provider/model flags during recovery |
| Recreate with `tmux new-session -d -s <fleet> -c <cwd>` when needed | Assume a dead session still exists |
| Match `tmux_target` to the real base index | Hardcode indices without checking |
| Start a fresh Pi session for a new packet | Resume context across packet reassignment |
| Verify `#{pane_current_path}` and capture the prompt | Trust configuration without checking runtime |

```bash
tmux has-session -t hand-N || \
  tmux new-session -d -s hand-N -c '<fleet cwd>' -n main
```

Record restarts in baseline when useful. Product state lives in Vivi; process rehome ≠ bag event unless you also file/clear targets.

## New assignment: `assignment_mode` (doorbell applies it)

When waking a **new** task/need handle, `fleet-doorbell.sh` applies the role’s
`assignment_mode` (`new` | `compact` | `continue` | `restart`) **before** the
pointer. Full table: [`runtime-config.md`](runtime-config.md) § `assignment_mode`.

```bash
# New handle → auto prepare per fleet.json assignment_mode, then pointer
scripts/fleet-doorbell.sh --project <root> --role hand-1 --handle <hex>

# Overrides
scripts/fleet-doorbell.sh … --mode restart
scripts/fleet-doorbell.sh … --no-prepare          # pointer only
scripts/fleet-doorbell.sh … --force-prepare       # re-apply mode even same handle
```

| Mode | Before pointer |
| --- | --- |
| `new` | Idle → `/new` → idle (or start if stopped) |
| `compact` | Idle → `/compact` → idle |
| `continue` | Pointer only (auto-start if stopped) |
| `restart` | `fleet-runtime.py restart --force` → idle |

Same-handle rewakes skip prepare. Do not stack wakes into `running` panes
(doorbell still refuses unless `--force`).

### Theme switch when mode is `compact` (or unset defaults to continue)

Historical “theme switch” path maps to **`assignment_mode: compact`**:

1. File next task/need first so handle exists
2. Require `waiting_for_input`, send `/compact` alone, wait for idle again
3. Keep identity, `vivi --for`, main/packet role, campaign in compact instruction; drop finished implementation detail
4. Send: `HAND WAKE hand-N. Compact done. Show <handle>. Continue.`
5. Record compact/wake in baseline when useful

Never combine `/compact` and new assignment in one keystroke or compact without next target. High TUI context usage is a hint only, not a control-plane field. If the role is `assignment_mode: new` or `restart`, do not theme-switch via compact — start clean.

## Completion mail (optional; preferred when turn succeeds)

```text
From: hand-N → mind   # or fleet mind_inbox; optional if task done is enough
Subject: hand-N turn end: <one line>
Body: cleared <handle>|none · HEAD <sha>|dirty · tasking left: … · next: … · blocked: none|…
```

Board `task done` / `need done` remains primary durable signal even if this mail is skipped.

## Ready-to-merge mail (hand-2+ preferred template)

High-signal handoff so Mind absorbs without reverse-engineering the pane. Send when packet unit done, tree clean, worker stopped.

```text
From: hand-2 → mind
Subject: hand-2 turn end: ready-to-merge <packet-slug>

ready-to-merge packet <packet-slug>

## Cleared
task <handle> (<subject>)

## Facts
- slug: <packet-slug>
- branch: factory/<packet-slug>
- <repo> HEAD: <full sha> (<short>)
- base: <base checkpoint>
- product commit(s): <oneline list>
- tree: clean (worker stopped)

## Validation
- <commands and PASS/FAIL or honest skip>
- What evidence is static vs manual/env-gated (be explicit)

## Scope touched
- <paths within write scope only>

## Watch-scope drift
- none | <paths that moved on main vs base — or "not checked">

## Integration
Operator/main merges via hand-1; this Hand does not merge to main.
```

Mind on receipt: **absorb** → review → **accept** or residual To worker → on accept set `pending_merges` `queued_for_hand1` + merge task to hand-1 (or queue if h1 mid-phase). Optional short tmux to worker: `Packet accepted. Merge with hand-1. Wait.`

**Long-term continuous packets:** do **not** merge to hand-1 after every unit. Prefer **theme-level** RTM (major delivery unit, Stage N close, operator-named theme). Units → absorb/review/**refill next map unit** on packet only; one merge task per theme.

RTM **validation** includes claimed tests **and** `cargo fmt --check` (or project equivalent) on touched packet repos. Merger re-checks green on main after absorb.
