# Dual channel: Vivi + tmux

Load for pane ops, wake/reinit, rehome, theme switch, or completion mail.

Vivi is the **board of record** (what work exists and is done).  
tmux is the **process layer** (whether the Hand process is alive, idle, or broken).

**Process address** is always fleet.json **`tmux_target`**, not a guessed session name. Legacy fleets use session==role (`hand-1:1.1`). Multi-fleet hosts prefer session=fleet_id, window=role (`mgs:hand-1.1`).

| Concern | Prefer |
| --- | --- |
| “This unit is done; evidence is …” | Vivi tasking done (+ optional mail **To mind**) |
| “Grok idle at prompt with open tasking” | tmux → **pointer doorbell** |
| “Codex done/idle at `›` with open tasking” | tmux → **reinit** (kill + fresh session + short bootstrap) — not stacked wakes |
| “Over capacity / connection failed / hung Waiting” | tmux → ops intervene (model change, retry, restart) |
| “Human must decide / recover / guide a fix” | Vivi **To `operator@`** (need/mail) — not status To mind; see `operator-mail.md` |
| “Mind loop dead / cycle ticks stopped” | per-fleet **steward** — see `dead-man.md`; rearm every successful mini-cycle |
| Multi-fleet pane address | fleet.json **`tmux_target`** (legacy `hand-1:1.1` or `mgs:hand-1.1`) — see `multi-fleet.md` |
| “No mail and no pane signal” | do not invent progress; sleep or escalate if bag stale |
| “Fix landed upstream; consumer still red” | Check **pin-relative done** before re-verify doorbell |

Do not rely on completion mail alone (overcapacity/disconnect/crash prevent send). Do not treat idle pane alone as done: idle + empty may be quiet; idle + open tasking is a wake; idle after HEAD move without done-handles still needs bag/Status honesty on thorough cycles.

When Hands or Heads run on another machine, pane ops go over SSH — see `ssh-remote.md`. Vivi still needs one coherent mailspace project root.

## Mailspace watch and thread (Vivi ≥ 4.6)

Project-local board liveness and conversation lineage. **Not** IMAP / `vivi sync` / `sync-events` watch — these read the fleet `.vivi/mail.sqlite` **event ledger** and reply graph.

Board CLI: Vivi project mailspace (see `companion-fallbacks.md`). Fleet usage:

### Watch — Mind sensors and paid waits

```bash
# Canonical
vivi mailspace watch --for <identity> --project <root> [filters…]

# Kind aliases (force that kind)
vivi mail watch | vivi task watch | vivi need watch | vivi want watch
```

| Flag | Fleet use |
| --- | --- |
| `--for <identity>` (Hand/Head, `mind`, or `operator`) | Whose local events wake the watcher |
| `--kinds mail,task,need` | Default; `want` opt-in via `--kinds` |
| `--events delivered,moved` | Default lifecycle |
| `--match-from hand-2` | Only that Hand’s deliveries |
| `--match-subject-prefix …` | e.g. ready-to-merge / `head-ceo report:` |
| `--handle <h>` | Wait for one item |
| `--once` | Non-blocking scan — **prefer on fail-fast cycles** |
| `--until-count N` | Exit after N matches (default 1) |
| `--timeout …` | Bound wait; nonzero if nothing matched |
| `--cursor-file` / `--write-cursor` | Durable watermark across Mind cycles (baseline path OK) |
| `--watermark-file` / `--write-watermark` | Aliases for cursor |
| `--json` | Machine-readable |
| `--poll-interval` | Default 250ms |

**Mind (cheap cycle):** `--once --write-cursor` against a fleet cursor file; if no events, continue other sensors / sleep.  
**Mind (paid path):** optional short `--timeout` wait for RTM or Head report instead of only status polling.  
**Do not** block a whole autonomous cycle on an unbounded watch (`--until-count 0` without timeout) unless the operator explicitly wants a long wait.

```bash
# Example: Mind cheap — board event scan (optional mind_inbox identity, or omit --for and use status)
vivi mailspace status --project "$ROOT"
vivi mailspace watch --for mind --project "$ROOT" \
  --once --write-cursor \
  --cursor-file "$ROOT/.vivi/mind-watch.cursor" \
  --json
# Only if fleet defined a board-only `mind` identity — Mind itself is still the operator TUI

# Example: bounded wait for hand-2 RTM (match-from; To: mind_inbox if used)
vivi mail watch --for mind --project "$ROOT" \
  --match-from hand-2 \
  --match-subject-prefix "ready-to-merge" \
  --timeout 60s --until-count 1
```

### Thread — exchange history (Mind and Hand)

```bash
vivi mail thread <handle> --project <root> [--json] [--infer] [--limit 50] [--max-depth 50]
```

`mail|task|need|want show` also attach thread context. Prefer `show` first; use `thread` when the exchange is multi-hop or Mind is reconstructing residuals / RTM lineage.

| Who | When |
| --- | --- |
| **Hand** | After selecting a handle, if replies/notes obscure done-when — thread before re-asking Mind |
| **Mind** | Before filing a residual that depends on prior mail; absorb head-ceo / RTM threads |
| **Either** | `--infer` only for historical best-effort links (marked; never overrides captured links) |

Reply lineage: `vivi mail reply <handle>`; sends support `--reply-to`; lifecycle `--note` becomes a captured reply (Vivi 4.6).

## Binding rule

**Mail identity token == tmux session name.**

| Mail | tmux session | Typical pane target |
| --- | --- | --- |
| `mind@…` | **none** | Operator TUI only |
| `hand-1@…` | `hand-1` | `hand-1` or `hand-1:1.1` (respect window base-index) |
| `hand-2@…` | `hand-2` | `hand-2` |
| `head-cto@…` | `head-cto` | `head-cto:1.1` |

Put the map in **project fleet config** (fleet-local path). Example shape:

```json
{
  "version": 1,
  "default_hand": "hand-1",
  "legacy_hand_identity": "codex",
  "mind_inbox": "mind",
  "mind_inbox_note": "Board-only To: mind. Process = operator TUI. No tmux for mind.",
  "mind": { "agent": "grok", "note": "Product harness for Hands; Mind is operator session" },
  "agent_policy": {
    "hands_follow_mind_harness": true,
    "heads_prefer_pi": true,
    "codex_reinit_after_kill": true
  },
  "preferred_models": {
    "grok": { "mind": "grok-4.5", "hand": "grok-4.5" },
    "codex": {
      "mind": { "model": "gpt-5.6-sol", "effort": "medium" },
      "hand": { "model": "gpt-5.6-luna", "effort": "xhigh" }
    },
    "head": { "agent": "pi", "model": "glm-5.2", "thinking": "high|xhigh" }
  },
  "hands": {
    "hand-1": {
      "mail_identity": "hand-1",
      "tmux_session": "hand-1",
      "tmux_target": "hand-1:1.1",
      "cwd": "/path/to/project",
      "agent": "grok",
      "merges_to_main": true,
      "wake_enabled": true,
      "wake_mode": "tmux_send_keys",
      "min_seconds_between_wakes": 180
    }
  },
  "head-ceo": { "mail_identity": "head-ceo", "tmux_session": "head-ceo", "agent": "pi" },
  "head-cto": { "mail_identity": "head-cto", "tmux_session": "head-cto", "agent": "pi", "self_directed": true },
  "head-cxo": { "mail_identity": "head-cxo", "tmux_session": "head-cxo", "agent": "pi", "self_directed": true },
  "binding_rule": "mail_identity == tmux_session token (Hands/Heads only; mind has no tmux)"
}
```

Fleet-specific durable law may live in a Mind/scheduler overlay or project `Agents.md` — treat as an **overlay** on this skill.

Arm:

```bash
vivi mailspace identity add mind --project <root>          # board only
vivi mailspace identity add hand-1 --project <root>
vivi mailspace identity add head-cto --project <root>
tmux new-session -d -s hand-1 -c <cwd>                     # Hands/Heads only
# no tmux for mind
```

## Pane scan (Mind, every cycle — keep cheap)

For each fleet Hand and Head (not mind):

```text
1. tmux has-session -t <tmux_session>   → down | up
2. if up: tmux capture-pane -t <tmux_target> -p -S -80
3. classify primarily on the last ~15–25 lines (avoid false running from earlier chrome)
4. store last_pane_class + short fingerprint in baseline
```

| Class | Example pane cues | Mind action |
| --- | --- | --- |
| `down` | no session | recreate session + agent; Codex: reinit with bootstrap |
| `running` | current `Waiting for response` / live spinner / Codex streaming | sleep (do not wake/reinit) |
| `idle_prompt` | Grok `❯` ready; Codex `›` ready without finished-turn monologue | **Grok:** doorbell if open tasking. **Codex:** reinit if session finished/stale + open tasking |
| `done_idle` | Codex turn-end / “tasking empty” / “standing by” then `›` | **Codex reinit** if open tasking or just filed targets; else refill or pause |
| `trust_prompt` | Workspace trust UI (“Yes, continue”) | Reinit auto-accept or send accept once; not `running` |
| `error_capacity` | over capacity, rate limit, 429 | ops: model change / retry / reinit |
| `error_connection` | connection failed, timeout, ECONNRESET | ops: retry / restart resume |
| `unknown` | unreadable TUI noise | record sample; do not thrash |

Grok: placeholder copy (“Build anything”) while idle is not an in-flight message. Prefer `Waiting for response` as the only hard `running` signal unless a live spinner is visible in the **tail**.

Codex: a `•` monologue followed by `›` is often an **answer that stopped**, not a wait for the next item. Stacking `HAND WAKE` lines is the failure mode.

Rate-limit wakes (`min_seconds_between_wakes`). Never `send-keys` into `running` unless operator policy allows cancel+replace.

Prefer a project **classify script** over ad-hoc greps when available (avoids false `error_connection` from tool text like `timeout 1800 ./script`).

### Situation → action

| Situation | Action |
| --- | --- |
| `idle_prompt`/`done_idle` + open tasking + **codex** | **Reinit** — not stacked wakes |
| `idle_prompt` + open tasking + **grok** | Pointer doorbell |
| `idle_prompt` + empty + map has next unblocked unit | **Starvation** — file next target same cycle; then wake/reinit by runtime |
| `idle_prompt` + empty + operational pause only | Quiet OK; note reason |
| `idle_prompt` + empty after unit/theme accept | Not default quiet — absorb/accept → **refill** → wake/reinit |

Never wake on dirty-only mid-flight; never reinit `running` without FORCE policy.

## Grok vs Codex (keyed on fleet `agent`, not H-number)

Under **Harness alignment**, product Hands share Mind’s harness, so the fleet usually runs one column for Mind + Hands. Heads may use the other on purpose.

| | **Grok** (`agent=grok`) | **Codex** (`agent=codex`) |
| --- | --- | --- |
| After unit + open tasking | Pointer **doorbell** | **Reinit** (kill + fresh + short bootstrap) |
| Theme switch same cwd | `/compact` then pointer | **Reinit** (do not rely on compact+wake) |
| Launch | Prefer plain `grok …` | Plain `codex …` via fleet `agent_launch` — **never `exec codex`** |
| Bootstrap | Pointer: identity, handle, `vivi --for` | Same short bootstrap as first user message — no multi-paragraph Phase-hold novels in argv |

## Codex reinit-after-unit

**Policy:** when a Codex-runtime Hand is **done** and next target exists, **kill Codex and start a fresh session**. One clean start — not five stacked wakes.

**When:** turn-end mail + next target; `done_idle` / long idle + open tasking; process down; unblock (pin-refresh/merge) + open tasking with **current** one-line fact.

**When not:** `running` / mid-unit; tasking empty + operational pause only (refill first if map has next); already reinited this Hand this cycle (unless died again); fleet `agent` is not `codex`.

**How:**

1. File next task/need **before** launch so a handle exists
2. Kill **Codex children of pane_pid only** — leave tmux + shell. If session gone: `tmux new-session -d -s hand-N -c <packet-cwd>`
3. Launch without `exec` using that Hand’s fleet **`agent_launch`**
4. One short first message: identity, never merge main (if packet), `vivi --for hand-N`, open handle(s), one verb, optional one-line unblock fact
5. Enter once. Record `last_codex_reinit_at` in baseline

### Goal bootstrap support

Use harness-native goal mode only where it is supported and useful:

| Harness | `/goal` guidance |
| --- | --- |
| **Codex** | **Preferred supported target.** The initial bootstrap may begin with `/goal <bounded objective>`; Codex treats it as the command and pursues the goal. Include the identity, task handle, scope, and done condition in the same short bootstrap. |
| **Grok** | Supported, but avoid by default. Prefer the normal pointer or Grok scheduled-loop pattern unless the operator explicitly wants `/goal`. |
| **Pi** | Not supported. Send a plain task pointer/prompt. |

Do not stack `/goal` onto an already-running turn or use it as a generic wake line. File the board target first, then use `/goal` during a clean Codex reinit when the work is a coherent bounded objective.

Production helper: skill `scripts/codex-reinit.sh` (doctor / heal / reinit / classify). Set `PROJECT` and `FLEET`. See `runtime-config.md`.

## Doorbell (wake) — primarily Grok

When `wake_enabled` and class is `idle_prompt` and Hand has open tasks/needs (or Mind just filed targets / answered a blocking need):

```bash
tmux send-keys -t '<tmux_target>' -l -- '<pointer only>'
tmux send-keys -t '<tmux_target>' Enter
```

For Codex, use **reinit** instead of stacking this doorbell after a unit. Pi local Hands use the same doorbell pattern as Grok (see `roles-and-harness.md`).

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

Ops interventions (model/retry) stay one-liners; detail goes to Vivi if needed. Record `last_hand_wake_at`, reason, target in baseline.

## tmux process ops (start / rehome / restart)

**Invariant:** fleet `cwd` / packet `root` (and `worker_cwd` once members exist) should match `tmux display -p -t <target> '#{pane_current_path}'`. A Hand assigned to a packet but running from project root writes against the wrong tree.

### Prefer rehome when

- hand-2+ reassigned to a new packet
- packet shell prepared but session still has main-checkout cwd
- operator wants clean baseline in the packet (fresh Grok, no resume)
- session `down` / process dead

Prefer **theme-switch `/compact`** (Grok) when cwd and identity are already correct. **Codex:** reinit after unit instead of compact+wake.

### Packet rehome sequence (Grok TUI in tmux)

```text
1. Pane must be idle_prompt (not Waiting) unless operator allows cancel
2. Exit Grok cleanly: send /quit  (alias /exit)  — own turn, then Enter
3. Wait until pane_current_command is a shell (zsh/bash), not grok
4. Confirm or create session with correct -c:
     tmux new-session -d -s hand-N -c <packet-or-main-cwd> -n main
   Respect window/pane base-index (often 1 → target hand-N:1.1)
5. From shell already in the right cwd, start Grok
6. Verify: pane path == fleet cwd; command is grok; then short bootstrap doorbell
```

```bash
# Pane shell already in packet root. Quote every --deny pattern with * for zsh.
grok --sandbox off \
  --deny 'Bash(sudo *)' \
  --deny 'Bash(rm -rf /)' \
  --deny 'Bash(rm -rf ~)' \
  --deny 'Bash(rm -rf $HOME)' \
  --always-approve
```

Bootstrap after restart is still **pointer-only**. Full assignment stays in Vivi + `PACKET.md`.

### tmux / shell pitfalls

| Do | Don't |
| --- | --- |
| `tmux send-keys -t … -l -- '…'` for literal text | Rely on unescaped `*` in unquoted shell args |
| Single-quote each `--deny 'Bash(…*)'` for zsh | Paste deny lists without quotes into interactive zsh |
| Prefer plain `grok …` / `codex …` | `exec grok` / **`exec codex`** — can leave pane unusable or destroy session |
| Recreate with `tmux new-session -d -s hand-N -c <cwd>` if session died | Assume old session still exists after bad restart |
| Match fleet `tmux_target` to real base-index (`1.1` vs `0.0`) | Hardcode wrong indices after recreate |
| Fresh Grok (no `--resume`) when rehoming to new packet baseline | Blindly resume main-checkout session into packet cwd |
| `--resume <id>` only when continuing same workspace/theme intentionally | Resume across packet reassignment without operator intent |
| After start: check `#{pane_current_path}` and short capture | Trust fleet JSON alone without verifying live pane |

```bash
tmux has-session -t hand-N || \
  tmux new-session -d -s hand-N -c '<fleet cwd>' -n main
```

Record restarts in baseline when useful. Product state still lives in Vivi; process rehome is not a bag event unless you also file/clear targets.

## Theme switch: `/compact` then continue (Grok)

When a Grok Hand finishes one theme and will receive another in the same session, prefer `/compact` plus a pointer wake. Start a new session only when the pane is down, needs different model/flags, remains confused after compaction, or the operator wants a clean slate.

**Codex:** after a unit with next target, **always reinit** — do not rely on compact+wake on a finished `›`.

Sequence (Grok):

1. File the next task/need first so its handle exists
2. Require `idle_prompt`, then send `/compact` alone and wait for idle again
3. Keep identity, `vivi --for`, main/packet role, and campaign in the compact instruction; drop finished implementation detail
4. Send: `HAND WAKE hand-N. Compact done. Show <handle>. Continue.`
5. Record compact/wake in baseline when useful

Never combine `/compact` and the new assignment in one keystroke or compact without next target. High TUI context usage is only a hint, not a control-plane field.

## Completion mail (optional; preferred when turn succeeds)

```text
From: hand-N → mind   # or fleet mind_inbox; optional if task done is enough
Subject: hand-N turn end: <one line>
Body: cleared <handle>|none · HEAD <sha>|dirty · tasking left: … · next: … · blocked: none|…
```

Board `task done` / `need done` remains the primary durable signal even if this mail is skipped.

## Ready-to-merge mail (hand-2+ preferred template)

High-signal handoff so Mind can absorb without reverse-engineering the pane. Send when packet unit is done, tree clean, worker stopped.

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

Mind on receipt: **absorb** → review → **accept** or residual mail back to worker → on accept set `pending_merges` state `queued_for_hand1` and file merge task to hand-1 (or queue if h1 mid-phase). Optional short tmux to worker: `Packet accepted. Merge with hand-1. Wait.`

**Long-term continuous packets:** do **not** file a merge to hand-1 after every task unit. Prefer **theme-level** ready-to-merge (major delivery unit, Stage N close, or operator-named theme). Units → absorb/review/**refill next map unit** on the packet only; one merge task per theme.

Ready-to-merge **validation** should include claimed tests **and** `cargo fmt --check` (or project equivalent) on touched packet repos so theme merges do not create red main. Merger re-checks green on main after absorb.
