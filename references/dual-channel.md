# Dual channel: Vivi + execution runtime

Vivi is the board of record (what work exists and is done). The execution runtime
(sub-agent, tmux, or vivi-pty) is the process layer (alive, idle, or broken).
Sensors normalize both into one nested `runtime` object.

| Channel | Truth of… |
| --- | --- |
| **Vivi board** | Work — what exists and is done |
| **Vivi role pid/host** | Process — which pid claimed the seat |
| **Execution runtime** | Process layer — alive, idle, or broken |

## Checking role liveness

`vivi board --process` (Vivi ≥ 6.1) gives the Mind one scan across all roles:

```bash
vivi board --process --project <root>           # all roles
vivi board --process --for hand-1 --project <root>
vivi role status hand-1 --project <root> --json  # one role, precise CPU
```

States: `alive`, `zombie`, `dead`, `sleep`, `not_set`, `remote`, `unknown`.
`not_set` = available to assign (no process claimed the seat). `remote` = host
mismatch; do not invent local process truth.

## Runtime backends

| Backend | When | Reference |
| --- | --- | --- |
| **Sub-agent** (default) | Harness supports spawning; event-driven completion | [`subagent.md`](subagent.md) |
| **tmux** | Persistent interactive sessions; harness lacks sub-agents; remote SSH | [`tmux.md`](tmux.md) |
| **vivi-pty** | Structured PTY sessions without tmux dependency | [`vivi-pty.md`](vivi-pty.md) |

## Concern → channel routing

| Concern | Prefer |
| --- | --- |
| "Unit done; evidence is …" | Vivi tasking done (+ optional mail **To mind**) |
| "Runtime idle with open tasking" | Backend-specific wake (see backend ref) |
| "Doorbell leaves text stuck / pane down" | Backend-specific reinit fallback (see backend ref) |
| "Over capacity / connection failed / hung" | Ops intervene (model / retry / restart) |
| "Human must decide / recover / guide" | Vivi **To `operator@`** (need/mail) — [`operator-mail.md`](operator-mail.md) |
| "Mind loop dead / cycle ticks stopped" | Optional per-fleet **steward** (default OFF) — [`dead-man.md`](dead-man.md) |
| "No mail and no runtime signal" | Do not invent progress; sleep or escalate if bag stale |
| "Fix landed upstream; consumer still red" | Check **pin-relative done** before re-verify |

Do not rely on completion mail alone (crash prevents send). Idle alone ≠ done:
idle + empty may be quiet; idle + open tasking = wake; idle after HEAD move
without done-handles still needs bag/Status honesty on thorough cycles.

## Canonical runtime states

All backends normalize to the same canonical state set:

```text
starting | waiting_for_input | submitting | running | approval_required |
completed | failed | stopped | unknown
```

| State | Mind action |
| --- | --- |
| `starting` / `submitting` | wait; do not stack input |
| `running` | sleep; do not wake/reinit |
| `waiting_for_input` / `completed` + open | Wake if work exists (backend-specific) |
| `approval_required` | Resolve the approval boundary; do not stack input |
| `failed` / `stopped` | Diagnose, rebind, or recreate |
| `unknown` | Use evidence and stability; never claim false certainty |

Backend-specific evidence markers and classification details: [`tmux.md`](tmux.md),
[`vivi-pty.md`](vivi-pty.md). Sub-agents do not require state classification
(completion is the notification).

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

Prefer `show` first; `thread` for multi-hop / residual / RTM. `--infer` = historical best-effort only. Reply: `vivi mail reply <handle>`; `--reply-to` / lifecycle `--note` captured (Vivi 4.6).

## Channel split (mandatory)

Applies to all backends — tight pointers in the runtime channel, full instructions in Vivi.

| Channel | Allowed content |
| --- | --- |
| **Runtime (send-keys / terminal write / sub-agent boot)** | **Tight pointers only** — identity, where to look (handle / folder / doc path), one verb. No essays, no policy dumps |
| **Vivi mail / task / need** | Full done-when, evidence bar, scope, approach, residuals |
| **Agents.md / factory goal / campaign** | Durable multi-agent law, architecture, stage criteria |

## Ready-to-merge mail (hand-2+ preferred template)

High-signal handoff so Mind absorbs without reverse-engineering the runtime.

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

Mind on receipt: **absorb** → review → **accept** or residual To worker → on accept, if work is on a feature branch, Mind merges when ready (see [SKILL.md § Commit authority and workflow](../SKILL.md#commit-authority-and-workflow)).

**Long-term continuous packets:** do **not** merge to hand-1 after every unit. Prefer **theme-level** RTM (major delivery unit, Stage N close, operator-named theme). Units → absorb/review/**refill next map unit** on packet only; one merge task per theme.

## Remote execution

Host axis on slots: `host`, `ssh`, host-scoped cwd/runtime/launch. Wake/reinit **on Hand host**. One mailspace DB. [`ssh-remote.md`](ssh-remote.md)
