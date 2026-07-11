# Dual channel: Vivi + tmux

Pane ops, wake/reinit, rehome, theme switch, completion mail.

| Channel | Truth of… |
| --- | --- |
| **Vivi** | Board of record — what work exists and is done |
| **tmux** | Process layer — alive, idle, or broken |

**Process address** = fleet.json **`tmux_target`**. Legacy: session==role (`hand-1:1.1`). Multi-fleet: session=fleet_id, window=role (`mgs:hand-1.1`).

| Concern | Prefer |
| --- | --- |
| “Unit done; evidence is …” | Vivi tasking done (+ optional mail **To mind**) |
| “Grok idle at prompt with open tasking” | tmux → **pointer doorbell** |
| “Codex done/idle at `›` with open tasking” | tmux → **reinit** (kill + fresh + short bootstrap) — not stacked wakes |
| “Over capacity / connection failed / hung Waiting” | tmux → ops intervene (model / retry / restart) |
| “Human must decide / recover / guide a fix” | Vivi **To `operator@`** (need/mail) — not status To mind; `operator-mail.md` |
| “Mind loop dead / cycle ticks stopped” | per-fleet **steward** — `dead-man.md`; rearm every successful mini-cycle |
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

**Mail identity token == tmux session name.**

| Mail | tmux session | Typical pane target |
| --- | --- | --- |
| `mind@…` | **none** | Operator TUI only |
| `hand-1@…` | `hand-1` | `hand-1` or `hand-1:1.1` (respect base-index) |
| `hand-2@…` | `hand-2` | `hand-2` |
| `head-cto@…` | `head-cto` | `head-cto:1.1` |

Map lives in **project fleet config**:

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

Fleet-specific durable law may live in overlay / project `Agents.md` — **overlay** on this skill.

```bash
vivi mailspace identity add mind --project <root>          # board only
vivi mailspace identity add hand-1 --project <root>
vivi mailspace identity add head-cto --project <root>
tmux new-session -d -s hand-1 -c <cwd>                     # Hands/Heads only
# no tmux for mind
```

## Pane scan (Mind, every cycle — keep cheap)

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
| `idle_prompt` | Grok `❯` ready; Codex `›` ready without finished-turn monologue | **Grok:** doorbell if open tasking. **Codex:** reinit if finished/stale + open tasking |
| `done_idle` | Codex turn-end / “tasking empty” / “standing by” then `›` | **Codex reinit** if open tasking or just filed targets; else refill or pause |
| `trust_prompt` | Workspace trust UI (“Yes, continue”) | Reinit auto-accept or send accept once; not `running` |
| `error_capacity` | over capacity, rate limit, 429 | ops: model change / retry / reinit |
| `error_connection` | connection failed, timeout, ECONNRESET | ops: retry / restart resume |
| `unknown` | unreadable TUI noise | record sample; do not thrash |

Grok: placeholder (“Build anything”) while idle ≠ in-flight. Prefer `Waiting for response` as only hard `running` unless live spinner in **tail**.

Codex: `•` monologue then `›` is often an **answer that stopped**. Stacking `HAND WAKE` lines is the failure mode.

Rate-limit wakes (`min_seconds_between_wakes`). Never `send-keys` into `running` unless operator allows cancel+replace. Prefer project **classify script** over ad-hoc greps (avoids false `error_connection` from tool text like `timeout 1800 ./script`).

| Situation | Action |
| --- | --- |
| `idle_prompt`/`done_idle` + open tasking + **codex** | **Reinit** — not stacked wakes |
| `idle_prompt` + open tasking + **grok** | Pointer doorbell |
| `idle_prompt` + empty + map has next unblocked unit | **Starvation** — file next same cycle; then wake/reinit by runtime |
| `idle_prompt` + empty + operational pause only | Quiet OK; note reason |
| `idle_prompt` + empty after unit/theme accept | Not default quiet — absorb/accept → **refill** → wake/reinit |

Never wake on dirty-only mid-flight; never reinit `running` without FORCE policy.

## Grok vs Codex (keyed on fleet `agent`, not H-number)

Hands share Mind’s harness (usually one column). Heads may use the other on purpose.

| | **Grok** (`agent=grok`) | **Codex** (`agent=codex`) |
| --- | --- | --- |
| After unit + open tasking | Pointer **doorbell** | **Reinit** (kill + fresh + short bootstrap) |
| Theme switch same cwd | `/compact` then pointer | **Reinit** (do not rely on compact+wake) |
| Launch | Prefer plain `grok …` | Plain `codex …` via `agent_launch` — **never `exec codex`** |
| Bootstrap | Pointer: identity, handle, `vivi --for` | Same short bootstrap as first user message — no multi-paragraph novels in argv |

## Codex reinit-after-unit

**Policy:** Codex Hand **done** + next target → **kill Codex, fresh session**. One clean start — not five stacked wakes.

**When:** turn-end + next target; `done_idle` / long idle + open tasking; process down; unblock + open tasking with **current** one-line fact.

**When not:** `running` / mid-unit; empty + operational pause only (refill first if map has next); already reinited this Hand this cycle (unless died again); `agent` ≠ `codex`.

1. File next task/need **before** launch so a handle exists
2. Kill **Codex children of pane_pid only** — leave tmux + shell. If session gone: `tmux new-session -d -s hand-N -c <packet-cwd>`
3. Launch without `exec` using that Hand’s **`agent_launch`** (helper honors it; synthesizes only if empty)
4. One short first message: identity, never merge main (if packet), `vivi --for hand-N`, open handle(s), one verb, optional one-line unblock fact
5. Enter once. Record `last_codex_reinit_at` in baseline

| Harness | `/goal` |
| --- | --- |
| **Codex** | **Preferred.** Bootstrap may begin `/goal <bounded objective>`; include identity, handle, scope, done condition in same short message |
| **Grok** | Supported; avoid by default — prefer pointer or scheduled-loop unless operator wants `/goal` |
| **Pi** | Not supported. Plain task pointer/prompt |

Do not stack `/goal` onto a running turn. File board target first; `/goal` during clean Codex reinit for coherent bounded objective.

Helper: `scripts/codex-reinit.sh` (doctor / heal / reinit / classify). Set `PROJECT` and `FLEET`. See `runtime-config.md`.

## Doorbell (wake) — primarily Grok

When `wake_enabled` and `idle_prompt` and Hand has open tasks/needs (or Mind just filed / answered blocking need):

```bash
scripts/fleet-doorbell.sh --project <root> hand-1 --handle <hex> --note '…'
# exit 0 sent · 1 refused · 2 usage/config
```

```bash
tmux send-keys -t '<tmux_target>' -l -- '<pointer only>'
tmux send-keys -t '<tmux_target>' Enter
```

Codex: **reinit** instead of stacking doorbell. Pi local Hands: same doorbell as Grok (`roles-and-harness.md`).

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

**Prefer rehome when:** hand-2+ reassigned; packet shell prepared but session still on main cwd; operator wants clean baseline (fresh Grok, no resume); session `down` / process dead.

Prefer **theme-switch `/compact`** (Grok) when cwd + identity already correct. **Codex:** reinit after unit instead of compact+wake.

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

Bootstrap after restart still **pointer-only**. Full assignment stays in Vivi + `PACKET.md`.

| Do | Don't |
| --- | --- |
| `tmux send-keys -t … -l -- '…'` for literal text | Rely on unescaped `*` in unquoted shell args |
| Single-quote each `--deny 'Bash(…*)'` for zsh | Paste deny lists without quotes into interactive zsh |
| Prefer plain `grok …` / `codex …` | `exec grok` / **`exec codex`** — can leave pane unusable or destroy session |
| Recreate with `tmux new-session -d -s hand-N -c <cwd>` if session died | Assume old session still exists after bad restart |
| Match fleet `tmux_target` to real base-index (`1.1` vs `0.0`) | Hardcode wrong indices after recreate |
| Fresh Grok (no `--resume`) when rehoming to new packet | Blindly resume main-checkout session into packet cwd |
| `--resume <id>` only when continuing same workspace/theme intentionally | Resume across packet reassignment without operator intent |
| After start: check `#{pane_current_path}` and short capture | Trust fleet JSON alone without verifying live pane |

```bash
tmux has-session -t hand-N || \
  tmux new-session -d -s hand-N -c '<fleet cwd>' -n main
```

Record restarts in baseline when useful. Product state lives in Vivi; process rehome ≠ bag event unless you also file/clear targets.

## Theme switch: `/compact` then continue (Grok)

Grok theme → next in same session: `/compact` + pointer wake. New session only when pane down, different model/flags, still confused after compact, or operator wants clean slate.

**Codex:** after unit with next target, **always reinit** — do not rely on compact+wake on finished `›`.

1. File next task/need first so handle exists
2. Require `idle_prompt`, send `/compact` alone, wait for idle again
3. Keep identity, `vivi --for`, main/packet role, campaign in compact instruction; drop finished implementation detail
4. Send: `HAND WAKE hand-N. Compact done. Show <handle>. Continue.`
5. Record compact/wake in baseline when useful

Never combine `/compact` and new assignment in one keystroke or compact without next target. High TUI context usage is a hint only, not a control-plane field.

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
