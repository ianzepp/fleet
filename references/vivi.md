# Vivi board CLI (fleet)

**Load when:** filing work, listing bags, marking done, watching for board events, reading threads, or escalating to `operator@` during a fleet cycle.

**Scope:** project-local **mailspace** only (`.vivi/` under the fleet root). Not personal IMAP (`vivi sync` / Proton) unless steward external page.

**Hard dependency:** the `vivi` binary must be installed — see [`getting-started.md`](getting-started.md). This file is the **normal fleet command set** so Mind/Hands do not re-scan the whole CLI every cycle.

**Not here:** pane wake/reinit (tmux) → [`dual-channel.md`](dual-channel.md); queue kind policy → [`tasking.md`](tasking.md); operator routing policy → [`operator-mail.md`](operator-mail.md).

---

## Universal flags

Almost every fleet command needs:

```bash
--project <ROOT>     # fleet project root that owns .vivi/
```

Identity filters:

```bash
--for <identity>     # list / done / board / watch (whose bag)
--from <identity>    # send / reply (who is writing)
--to <identity>      # send (may repeat)
```

Prefer short identity tokens: `mind`, `operator`, `hand-1`, `hand-2`, `head-ceo`, …

Bodies:

```bash
--body 'literal text'           # shell-real newlines if needed: $'line1\nline2'
--body @/path/to/file           # when supported
--body-file /path/to/file
```

Discover flags live (edge cases):

```bash
vivi --help
vivi <command> --help
vivi <command> <subcommand> --help
vivi --version                  # fleet prefers ≥ 4.6 (watch/thread); 4.7+ fine
```

---

## Kinds (what to send)

| Kind | Command family | Use for | Primary queue? |
| --- | --- | --- | --- |
| **task** | `vivi task …` | Implementable work + done-when (incl. defects) | **Yes** |
| **need** | `vivi need …` | Decision / authority / external input (default + options) | **Yes** |
| **want** | `vivi want …` | Non-blocking later idea | No |
| **mail** | `vivi mail …` | Deliberation, status, Head reports, RTM, handoff | No |

**To: routing (fleet):**

| To | Content |
| --- | --- |
| `hand-N` | Work that Hand drains (tasks/needs) |
| `mind` | Done/evidence, Head reports, RTM, bag bookkeeping |
| `operator` | Human escalations only — not status ([`operator-mail.md`](operator-mail.md)) |
| `head-*` | Assigns / research requests; reports return **To mind** |

---

## FLEET_CYCLE cheat sheet (Mind)

Cheap cycle — prefer **`fleet-sensors.py`** which wraps the first two; raw CLI:

```bash
ROOT=/path/to/fleet
CURSOR="$ROOT/.vivi/mind-watch.cursor"

# 1) Board counts + bags
vivi mailspace status --project "$ROOT"

# 2) New events since last cycle (non-blocking)
vivi mailspace watch --for mind --project "$ROOT" \
  --once --write-cursor --cursor-file "$CURSOR"

# 3) Open work per Hand
vivi task list --for hand-1 --project "$ROOT" --status open
vivi need list --for hand-1 --project "$ROOT" --status open

# 4) Operator inbox on engagement / return
vivi need list --for operator --project "$ROOT" --status open
vivi mail list --for operator --project "$ROOT"

# 5) One item in depth
vivi task show <handle> --project "$ROOT"
# multi-hop lineage:
vivi mail thread <handle> --project "$ROOT"
```

Paid path (moved work, RTM, Head report): list/show what changed; `mail thread` when lineage matters; file residuals as **tasks** To owning Hand.

**Do not** unbounded-block on `watch` during fail-fast cycles.

---

## Mailspace (setup + status + watch)

```bash
vivi mailspace init --project "$ROOT"              # once per project (case 2)
vivi mailspace status --project "$ROOT"            # every cheap cycle
vivi mailspace identity list --project "$ROOT"
vivi mailspace identity add <name> --project "$ROOT"
# vivi mailspace identity rename <old> <new> --project "$ROOT"
```

### Watch (Vivi ≥ 4.6) — board liveness, not IMAP

```bash
# Canonical
vivi mailspace watch --for <identity> --project "$ROOT" [filters…]

# Kind-scoped aliases
vivi mail watch  | vivi task watch | vivi need watch | vivi want watch
```

| Flag | Fleet use |
| --- | --- |
| `--for <id>` | Whose events wake the watcher (`mind`, `hand-1`, `operator`, …) |
| `--once` | **Prefer on fail-fast cycles** — scan and exit |
| `--write-cursor` + `--cursor-file PATH` | Durable watermark across cycles |
| `--timeout 60s` | Bound a paid wait (RTM / report) |
| `--until-count N` | Exit after N matches (default 1) |
| `--match-from hand-2` | Only that sender |
| `--match-subject-prefix ready-to-merge` | RTM / Head subject filters |
| `--kinds mail,task,need` | Default; add `want` if needed |
| `--json` | Machine-readable events |
| `--handle <h>` | Wait for one item |

```bash
# Cheap Mind sensor
vivi mailspace watch --for mind --project "$ROOT" \
  --once --write-cursor --cursor-file "$ROOT/.vivi/mind-watch.cursor"

# Bounded wait for hand-2 ready-to-merge (paid path)
vivi mail watch --for mind --project "$ROOT" \
  --match-from hand-2 \
  --match-subject-prefix "ready-to-merge" \
  --timeout 60s --until-count 1
```

---

## List / show / board (read)

```bash
# Per-kind lists (default status=open for task/need)
vivi task list --for hand-1 --project "$ROOT" [--status open|done] [--json]
vivi need list --for hand-1 --project "$ROOT" [--status open|done]
vivi want list --for hand-1 --project "$ROOT"
vivi mail list --for mind --project "$ROOT"

# One handle
vivi task show <handle> --project "$ROOT"
vivi need show <handle> --project "$ROOT"
vivi want show <handle> --project "$ROOT"
vivi mail show <handle> --project "$ROOT"

# Cross-kind actionable board (optional orientation)
vivi board --for hand-1 --project "$ROOT" [--json] [--since …]

# Conversation lineage
vivi mail thread <handle> --project "$ROOT" [--json] [--infer] [--limit 50]
```

| Prefer | Avoid on every cycle |
| --- | --- |
| `list` + one `show` | Full `dump` of all kinds |
| `show` first | `thread` only when multi-hop / RTM residuals |
| `mailspace status` | Re-parsing sqlite |

**Dump is audit** (archaeology), not heartbeat:

```bash
vivi task dump --project "$ROOT" --status open   # if you must dump
vivi mail dump --project "$ROOT"                 # heavy
```

---

## Send (Mind files; Heads report; Hands rarely file)

Same shape for task / need / want / mail:

```bash
vivi task send --project "$ROOT" \
  --from mind --to hand-1 \
  --subject 'unit: …' \
  --body 'done-when: … evidence: …'

vivi need send --project "$ROOT" \
  --from mind --to hand-1 \
  --subject 'need: choose approach' \
  --body 'default: A. options: A | B. …'

vivi want send --project "$ROOT" \
  --from mind --to hand-1 \
  --subject 'want: later polish …' \
  --body '…'

vivi mail send --project "$ROOT" \
  --from head-cto --to mind \
  --subject 'head-cto report: main review …' \
  --body '…'

# Thread onto an existing handle
vivi task send … --reply-to <handle> --body '…'
```

Long bodies: `--body-file /tmp/body.md` or `--body @/tmp/body.md`.

### Hand turn-end patterns

```bash
# Complete work
vivi task done --for hand-1 --project "$ROOT" <handle> \
  --note 'evidence: tests … commit abc123'

# Optional status / evidence To mind (not a substitute for done)
vivi mail send --project "$ROOT" \
  --from hand-1 --to mind \
  --subject 'done: <short unit>' \
  --body 'handle … evidence …'

# Packet ready-to-merge signal (subject convention; Mind watches)
vivi mail send --project "$ROOT" \
  --from hand-2 --to mind \
  --subject 'ready-to-merge: <packet>' \
  --body '…'
```

```bash
vivi need done --for hand-1 --project "$ROOT" <handle> [--note '…']
vivi task reopen --for hand-1 --project "$ROOT" <handle>   # rare
vivi need reopen --for hand-1 --project "$ROOT" <handle>
```

### Wants lifecycle

```bash
vivi want list --for hand-1 --project "$ROOT"
vivi want promote --for hand-1 --project "$ROOT" <handle>   # → need
vivi want done|drop --for hand-1 --project "$ROOT" <handle>
```

### Replies (any kind)

```bash
vivi mail reply <handle> --project "$ROOT" \
  --from mind \
  --body 'decision: take default A. …'
# --to defaults to parent sender; override with --to if needed
```

---

## Operator@ (human escalations)

Policy: [`operator-mail.md`](operator-mail.md). CLI:

```bash
# Present on return / engagement
vivi need list --for operator --project "$ROOT" --status open
vivi mail list --for operator --project "$ROOT"

vivi need send --project "$ROOT" \
  --from mind --to operator \
  --subject 'operator: need — …' \
  --body 'default: …. options: …'

vivi mail send --project "$ROOT" \
  --from mind --to operator \
  --subject 'operator: problem|blocker|bug-guidance — …' \
  --body 'evidence … ask …'
```

Never **task** To `operator`. Never dump cycle status To `operator`.

---

## External email (steward pages only)

**Not** normal fleet chat. Only when fleet preauthorizes steward notify:

```bash
vivi compose --account <account> --to you@example.com \
  --subject '…' --body '…' --html-body-auto
vivi exec send --account <account> path/to/draft.eml
```

Detail: [`dead-man.md`](dead-man.md). Do not `exec send` for ordinary agent mail.

---

## Role → command map

| Who | Typical vivi |
| --- | --- |
| **Mind (cheap cycle)** | `mailspace status`, `mailspace watch --once`, `task|need list` per Hand, operator list if engaged |
| **Mind (file work)** | `task send` / `need send` To `hand-N`; rare `want send` |
| **Mind (integrate)** | `mail list/show` To mind; `mail thread`; file residual **tasks** |
| **Mind (operator return)** | `need|mail list --for operator` first |
| **Hand** | `task|need list --for self`; `show` / `thread`; `task done` (+ optional mail To mind) |
| **Head** | `mail send --to mind` reports; read assigns via `mail|task list --for head-*` |
| **Steward** | board notify To operator; optional `compose`+`exec send` |
| **Sensors helper** | wraps status + watch + lists — `scripts/fleet-sensors.py` |

---

## What is *not* fleet board traffic

These are Vivi’s broader product surface. **Skip unless** the operator asks for personal mail / release work:

| Area | Commands (see help) |
| --- | --- |
| Personal IMAP / Proton | `sync`, `sync-events`, `list` (folder), `folders`, `proton`, `doctor` |
| Search / index | `search`, `index` |
| Outbound queue | `enqueue`, `queue` (non-steward) |
| Labels | `labels`, `label` |
| Agent poll of downloaded mail | `agent` |
| Global config | `init` (vivarium home, not project mailspace) |

If you need one of these, open the help tree rather than inventing flags:

```bash
vivi help
vivi help sync
vivi help exec
vivi help enqueue
```

---

## Discover more (help tree)

```text
vivi --help
├── mailspace          # init, status, watch, identity  ← fleet core
├── board              # cross-kind open work
├── task | need | want | mail   # send, list, show, done, watch, …
├── show | thread | reply | compose | export   # message-level
├── exec | enqueue | queue     # external writes (steward edge)
└── sync | search | index | …  # personal mail / not fleet heartbeat
```

Pattern for any unknown flag:

```bash
vivi <family> --help
vivi <family> <verb> --help
```

Examples: `vivi task send --help`, `vivi mailspace watch --help`, `vivi mail thread --help`.

---

## Anti-patterns (board CLI)

| Don’t | Do |
| --- | --- |
| Omit `--project` and hit the wrong/default store | Always `--project $ROOT` for the fleet |
| `dump` every cycle | `status` + `list` + targeted `show` |
| Unbounded `watch` on fail-fast | `--once` or short `--timeout` |
| Use IMAP `sync` as bag sensor | `mailspace watch` / status |
| Task To `operator` | need/mail To `operator` |
| Status To `operator` | `operator_recap` + mind board |
| Treat mail alone as process truth | dual channel — panes via tmux |
| Re-scan full `vivi --help` every action | **this file** + one targeted `--help` |

---

## Related

| Doc | When |
| --- | --- |
| [`getting-started.md`](getting-started.md) | Install Vivi; init mailspace |
| [`tasking.md`](tasking.md) | Which kind / To: / starvation |
| [`operator-mail.md`](operator-mail.md) | Human inbox rules |
| [`dual-channel.md`](dual-channel.md) | Watch/thread detail + tmux |
| [`mind-cycle.md`](mind-cycle.md) | When sensors run in a cycle |
| [`dead-man.md`](dead-man.md) | Steward board + external page |
| Optional `$mail` skill | Richer Vivi/IMAP product workflows (not required if this file + binary present) |
