# Vivi board CLI (fleet)

Observing Fleet work, managing non-assignment communication and role memory,
watching board events, threads, and `operator@` escalations.

**Fleet communication invariant:** role assignments, claims, settlements, and
admission/acceptance checks use [`fleet-helper.md`](fleet-helper.md). Vivi
remains the durable store and the direct surface for observation, needs, wants,
operator mail, decisions, memos, and administration.

**Scope:** project-local **mailspace** only (`.vivi/` under fleet root). Not personal IMAP (`vivi sync` / Proton) unless steward external page.

**Hard dependency:** `vivi` binary — [`getting-started.md`](getting-started.md). Normal fleet command set so Mind/Hands do not re-scan full CLI every cycle.

**Not here:** pane wake/reinit → [`dual-channel.md`](dual-channel.md); queue kind → [`tasking.md`](tasking.md); operator routing → [`operator-mail.md`](operator-mail.md).

## Universal flags

**Placeholders:** `<angle-brackets>` and `…` mean substitute before run. Tokens **without** them are literals (`--once`, `--json`, `status`, …).

```bash
--project <ROOT>     # fleet project root that owns .vivi/
--for <identity>     # list / done / board / watch (whose bag)
--from <identity>    # send / reply (who is writing)
--to <identity>      # send (may repeat)
```

Prefer short tokens: `mind`, `operator`, `hand-1`, `hand-2`, `head-ceo`, …

```bash
--body 'literal text'           # shell-real newlines: $'line1\nline2'
--body @/path/to/file           # when supported
--body-file /path/to/file

vivi --help
vivi <command> --help
vivi <command> <subcommand> --help
vivi --version                  # graph-backed fleets require ≥ 7.1 (`graph ready` + `board --graph`); 6.4+ provides trace, memo search, task deps, verdicts, mailspace description, and the subagent PID fix
```

## Kinds (what to send)

| Kind | Command family | Use for | Primary queue? |
| --- | --- | --- | --- |
| **task** | `vivi task …` | Implementable work + done-when (incl. defects) | **Yes** |
| **need** | `vivi need …` | Decision / authority / external input (default + options) | **Yes** |
| **want** | `vivi want …` | Non-blocking later idea | No |
| **mail** | `vivi mail …` | Deliberation, status, operator/admin messages; Fleet reports are emitted by `fleet settle` | No |
| **memo** | `vivi memo …` | Private durable context for Mind/Head identities | No |

| To | Content |
| --- | --- |
| `hand-N` | Work that Hand drains (tasks/needs) |
| `mind` | Done/evidence, Head reports, RTM, bag bookkeeping, **all role mail needing response or action** |
| `operator` | Human escalations only — not status ([`operator-mail.md`](operator-mail.md)) |
| `head-*` | Prepared advisory assignments; settlements return **To mind** |

Mind owns the spawn clock and all role routing. A role with a question or
finding files it **To mind**; Mind answers from context, prepares the next role
assignment or files a need, then spawns it, or escalates to `operator@`.

The order is mandatory: `fleet prepare`, deliver its generated prompt, `fleet
claim`, work, `fleet settle`, then `fleet advance` where a gate applies.

## Command shapes roles must get right

The helper owns role transitions:

```bash
python3 <skill>/scripts/fleet.py claim <handle> --role <name> --project <root>
python3 <skill>/scripts/fleet.py settle <handle> --role <name> --project <root> \
  --note '<evidence>' --report-file <path> \
  [--repo <repo> --tip <sha>] [--verdict clean_pass|residual|block_ship]
```

| Helper flag | Semantics |
| --- | --- |
| `--note` | Concise task-completion evidence. |
| `--report-file` | Full reply body linked to the assignment. |
| `--repo` + `--tip` | Paired land receipt. |
| `--verdict` | Required on auditor passes. |

Common mistakes: hand-writing task/report transitions, skipping claim, settling
without a report, or accepting from chat without `fleet advance`.

## FLEET_CYCLE cheat sheet (Mind)

Prefer **`fleet-sensors.py`** for the first two; raw CLI:

```bash
ROOT=/path/to/fleet
CURSOR="$ROOT/.vivi/mind-watch.cursor"

# Sensors include bounded Mind memo checklist metadata by default.
# Use --memo-limit 0 to disable, or show a memo body only when needed:
python3 <fleet-skill>/scripts/fleet-sensors.py --project "$ROOT" --text
vivi memo show --project "$ROOT" <handle>

vivi mailspace status --project "$ROOT"
# Fleet-level charter (≥ 6.4)
vivi mailspace description --project "$ROOT"                      # show current
vivi mailspace description --project "$ROOT" --set 'description'  # set

vivi mailspace watch --for mind --project "$ROOT" \
  --once --write-cursor --cursor-file "$CURSOR"

vivi task list --for hand-1 --project "$ROOT" --status open
vivi need list --for hand-1 --project "$ROOT" --status open

# Human backlog (To operator@)
vivi need list --for operator --project "$ROOT" --status open
vivi mail list --for operator --project "$ROOT"

# Operator feedback To mind (From operator@) — part of cheap cycle; absorb first
vivi mail list --for mind --project "$ROOT"   # scan From: operator@

vivi mail show <handle> --project "$ROOT"   # prefer over bare show when multi-project
vivi mail thread <handle> --project "$ROOT"   # multi-hop lineage
```

Prefer **`fleet-sensors.py`**: emits `operator_mail` (To operator) and **`operator_to_mind`** (From operator).

Paid path: list/show what changed; `mail thread` when lineage matters; residual **tasks** To owning Hand. **Do not** unbounded-block on `watch` during fail-fast cycles.

## Communication tracing

`vivi trace` reconstructs the cross-role communication tree around any handle.
The helper consumes it during `settle` and `advance`; use it directly for
diagnosis, not as a hand-operated substitute for the helper gate.

```bash
vivi trace <handle> --project "$ROOT"
vivi trace <handle> --project "$ROOT" --json --max-depth 5 --limit 100
```

The tree includes:
- **Captured** edges from `In-Reply-To` / `References` reply links
- **Event** edges from `task from` lifecycle events
- **Inferred** edges from body handle citations and stripped subject matching

Captured and event edges are preferred historical evidence. Inferred edges are
best-effort recovery, not proof that a required contemporaneous handoff occurred.
If a task was created after its runtime started, record that as a process
deviation in a new recovery task or need to the actual owner. Link the surviving
evidence instead of treating the later handle as the original assignment.

| When to use | Instead of |
| --- | --- |
| Verify a lowering actually links to the Hand units prepared from it | Guessing from subject prefixes |
| Trace an audit chain (block_ship → repair → verify) | Reading mail list in chronological order |
| Confirm a task has real reply edges to its parent goal | Assuming the link exists because subjects match |
| Understand the full history of a unit before acting | Shell-diving into individual mail handles |

Text output prints per-node metadata, copy lists, and labeled edges. JSON output
contains `seed` and `nodes`; each node carries its own `edges` list.

## Executable work graphs

`vivi graph` is the durable authority for **planning and delivery topology**
(import Mermaid, ready frontier, task-attempt binding). It is not `vivi trace`
and not a substitute for `fleet prepare` / claim / settle.

This command surface requires Vivi 7.1 or newer. `graph` is a top-level command.
`graph show` renders Mermaid topology; `graph ready` and `board --graph` expose
the compact machine-readable frontier.

| Authority | Surface |
| --- | --- |
| Eligible work (ready nodes) | `vivi graph ready` / `board --graph` |
| Topology | `vivi graph show` / `vivi graph export` (Mermaid) |
| Who runs now | Mind + `fleet prepare --node <graph>:<source-id>` |
| Execution proof | `fleet claim` (activates node) → `fleet settle` |
| Node accepted / unlocked | Explicit `vivi graph complete` (settle does **not** auto-complete) |

```bash
# Import or revise a delivery / planning DAG
vivi graph import --project "$ROOT" --code mir-wave-2 --file wave.mmd --check --json
vivi graph import --project "$ROOT" --code mir-wave-2 --file wave.mmd --json
vivi graph apply --project "$ROOT" mir-wave-2 --file wave-v2.mmd --json
vivi graph show --project "$ROOT" mir-wave-2 --include-state
vivi graph ready --project "$ROOT" mir-wave-2 --json
vivi board --project "$ROOT" --graph --json

# Lifecycle (Mind / disposition)
vivi graph activate --project "$ROOT" mir-wave-2:verify --task <task-handle> --json
vivi graph complete --project "$ROOT" mir-wave-2:verify --json
vivi graph export --project "$ROOT" mir-wave-2 --include-state

# Watch newly ready nodes (Mind decides dispatch; no auto-spawn)
vivi mailspace watch --for mind --project "$ROOT" \
  --kinds graph --events node_ready --once --json
```

| Rule | Fleet consequence |
| --- | --- |
| Ready = open + all prereqs `done` | `prepare --node` refuses blocked / active / terminal |
| Activate binds a task attempt | `claim` calls activate after a durable claim |
| Complete unlocks successors | Emits `node_ready`; Mind may prepare next `--node` |
| Apply freezes done/active prereqs | Do not rewrite history; append successors or new nodes |

Helper integration: [`fleet-helper.md`](fleet-helper.md) § prepare `--node`.

## Role memory (Mind and Heads only)

Memos are durable, project-local context for a role's own future sessions. They
are not board traffic, routed work, communication, or a Hand work product.
Only **Mind and Head identities** use this surface; Hands do not create, read,
or maintain memos. A Hand's findings return through `fleet settle`, and Mind or
a Head decides what should persist.

At cold attach or resume, Mind and Heads must review their own memory before
reconstructing state from chat. Save only stable decisions, recurring
constraints, strategy, or findings worth carrying across a cycle or
reinitialization:

```bash
vivi memo list --project "$ROOT" --for <mind-or-head-id>
vivi memo search --project "$ROOT" --for <mind-or-head-id> "keyword"
vivi memo search --project "$ROOT" --for <mind-or-head-id> --subject "ACCEPT*"
vivi memo show --project "$ROOT" <handle>
vivi memo save --project "$ROOT" --for <mind-or-head-id> \\
  --subject '…' --body '…'
vivi memo dump --project "$ROOT" --for <mind-or-head-id>
vivi memo delete --project "$ROOT" --for <mind-or-head-id> <handle>
```

`memo dump --for` is deliberately identity-scoped. Do not use memos to assign,
delegate, or report work; use task, need, want, or mail. Memos are omitted from
`vivi board`, task dumps, and normal mail dumps.

### Mind operating checklist

Mind memos are checklist line items, not documents. Keep each memo atomic: one
durable fact, invariant, assignment, or next-action pointer per memo. The
subject should carry the summary; the body should add only the minimum evidence,
handle, timestamp, or next command needed to act.

Use subjects like:

```text
ops: posture growth; loop 5m; true operator blocks only
policy: Railway reversible smoke proceeds without operator approval
lane: hand-1 owns Railway candidate; hand-2 owns Mind Console
gate: rerun integration suite_56 after swarm /doc mount lands
invariant: candidate swarmd must not proxy to external services
next: cold boot starts with fleet-sensors.py then newest mind mail
```

Update checklist memos when a material transition occurs: campaign start or
close, operator policy change, lane reassignment, merge/proof gate change, fleet
topology change, or a repeated defer that a future Mind must understand. Delete
or supersede stale line items instead of preserving history in the memo surface.
Do not write every sensor tick, pane tail, routine task result, or multi-section
status note.

Use mail when another identity needs to know something now. Use a task/need
when work must be drained. Use a memo when the same identity needs durable
context later.

## Mailspace (setup + status + watch)

```bash
vivi mailspace init --project "$ROOT"              # once per project (case 2)
vivi mailspace status --project "$ROOT"
# Fleet-level charter (≥ 6.4)
vivi mailspace description --project "$ROOT"                      # show current
vivi mailspace description --project "$ROOT" --set 'description'  # set            # every cheap cycle
vivi mailspace identity list --project "$ROOT"
vivi role add <name> --kind hand --harness subagent --project "$ROOT"   # one-step role seat (identity + role record)
vivi mailspace identity add <name> --project "$ROOT"                     # thin identity only (no role metadata)
# vivi mailspace identity rename <old> <new> --project "$ROOT"
```

### Watch — board liveness, not IMAP

```bash
vivi mailspace watch --for <identity> --project "$ROOT" [filters…]
vivi mail watch  | vivi task watch | vivi need watch | vivi want watch
```

| Flag | Fleet use |
| --- | --- |
| `--for <id>` | Whose events (`mind`, `hand-1`, `operator`, …) |
| `--once` | **Prefer on fail-fast cycles** — scan and exit |
| `--write-cursor` + `--cursor-file PATH` | Durable watermark across cycles |
| `--timeout 60s` | Bound paid wait (RTM / report) |
| `--until-count N` | Exit after N matches (default 1) |
| `--match-from hand-2` | Only that sender |
| `--match-subject-prefix ready-to-merge` | RTM / Head subject filters |
| `--kinds mail,task,need[,graph]` | Default mail/task/need; add `graph` for work-graph events |
| `--events node_ready,…` | With `--kinds graph`: `node_ready`, `node_state`, `attempt_bound`, … |
| `--json` | Machine-readable |
| `--handle <h>` | Wait for one item |

```bash
vivi mailspace watch --for mind --project "$ROOT" \
  --once --write-cursor --cursor-file "$ROOT/.vivi/mind-watch.cursor"

vivi mail watch --for mind --project "$ROOT" \
  --match-from hand-2 \
  --match-subject-prefix "ready-to-merge" \
  --timeout 60s --until-count 1
```

## List / show / board (read)

```bash
vivi task list --for hand-1 --project "$ROOT" [--status open|done] [--json]
vivi need list --for hand-1 --project "$ROOT" [--status open|done]
vivi want list --for hand-1 --project "$ROOT"
vivi mail list --for mind --project "$ROOT" [--json]
# text columns: handle  date  from  subject

vivi task show <handle> --project "$ROOT"
vivi need show <handle> --project "$ROOT"
vivi want show <handle> --project "$ROOT"
vivi mail show <handle> --project "$ROOT"

vivi board --for hand-1 --project "$ROOT" [--json] [--since …] [--graph]
vivi mail thread <handle> --project "$ROOT" [--json] [--infer] [--limit 50]
```

`--graph` adds `graphs[]` (ready/blocked/active nodes, blocked-by **handles**,
successors) without removing task/need/want board fields.

| Prefer | Avoid on every cycle |
| --- | --- |
| `list` + one `show` | Full `dump` of all kinds |
| `board --graph` for multi-unit waves | Reconstructing DAGs from chat/Markdown alone |
| `show` first | `thread` only when multi-hop / RTM residuals |
| `mailspace status` | Re-parsing sqlite |

**Dump is audit**, not heartbeat:

```bash
vivi task dump --project "$ROOT" --status open
vivi mail dump --project "$ROOT"                 # heavy
```

## Send (non-assignment communication)

```bash
# Query blocked tasks (≥ 6.4)
vivi task list --for hand-3 --project "$ROOT" --blocked
vivi task list --for hand-3 --project "$ROOT" --blocking <handle>

vivi need send --project "$ROOT" \
  --from mind --to hand-1 \
  --subject 'need: choose approach' \
  --body 'default: A. options: A | B. …'

vivi want send --project "$ROOT" \
  --from mind --to hand-1 \
  --subject 'want: later polish …' \
  --body '…'

```

Role assignments and reports use `fleet prepare` and `fleet settle`, not this
section. Long bodies use their `--body-file` / `--report-file` flags.

### Role turn-end pattern

```bash
python3 <skill>/scripts/fleet.py settle <handle> --role hand-1 \
  --project "$ROOT" --note 'tests … commit abc123' \
  --report-file /tmp/hand-1-report.md --repo <repo> --tip abc123

vivi need done --for hand-1 --project "$ROOT" <handle> [--note '…']
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

## Operator@ (human escalations)

Policy: [`operator-mail.md`](operator-mail.md).

```bash
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

## External email (steward pages only)

**Not** normal fleet chat. Only when fleet preauthorizes steward notify:

```bash
vivi compose --account <account> --to you@example.com \
  --subject '…' --body '…' --html-body-auto
vivi exec send --account <account> path/to/draft.eml
```

[`dead-man.md`](dead-man.md). Do not `exec send` for ordinary agent mail.

## Role → command map

| Who | Typical vivi |
| --- | --- |
| **Mind (cheap cycle)** | `mailspace status`, `mailspace watch --once`, `task|need list` per Hand, operator list if engaged; `board --graph` when waves are graph-backed; memo list at attach/resume |
| **Mind (route work)** | `fleet prepare` for roles (`--node` when graph-backed); direct `need send` / rare `want send` |
| **Mind (integrate)** | `mail list/show` To mind; `mail thread` / `trace`; `graph complete` when a logical node is accepted; prepare residual / next ready node |
| **Mind (operator return)** | `need|mail list --for operator` first |
| **Hand** | `fleet claim`; `show` / `thread`; `fleet settle`; direct needs when blocked |
| **Head** | `fleet claim` / `fleet settle`; memo list/show/save for durable role context |
| **Steward** | board notify To operator; optional `compose`+`exec send` |
| **Sensors helper** | wraps status + watch + lists — `scripts/fleet-sensors.py` |

## What is *not* fleet board traffic

Skip unless operator asks for personal mail / release work:

| Area | Commands (see help) |
| --- | --- |
| Personal IMAP / Proton | `sync`, `sync-events`, `list` (folder), `folders`, `proton`, `doctor` |
| Search / index | `search`, `index` |
| Outbound queue | `enqueue`, `queue` (non-steward) |
| Labels | `labels`, `label` |
| Agent poll of downloaded mail | `agent` |
| Global config | `init` (vivarium home, not project mailspace) |

```bash
vivi help
vivi help sync
vivi help exec
vivi help enqueue
```

## Discover more

```bash
vivi --help                          # mailspace, board, task|need|want|mail|memo, …
vivi <family> --help                 # e.g. vivi task send --help
vivi <family> <verb> --help          # e.g. vivi mailspace watch --help
# fleet core: mailspace · board · graph · task|need|want|mail · memo (Mind/Heads only)
# not fleet heartbeat: sync | search | index | enqueue | queue
```

## Anti-patterns (board CLI)

| Don’t | Do |
| --- | --- |
| Omit `--project` and hit wrong/default store | Always `--project $ROOT` for the fleet |
| `dump` every cycle | `status` + `list` + targeted `show` |
| Unbounded `watch` on fail-fast | `--once` or short `--timeout` |
| Use IMAP `sync` as bag sensor | `mailspace watch` / status |
| Task To `operator` | need/mail To `operator` |
| Status To `operator` | `operator_recap` + mind board |
| Treat mail or runtime alone as process truth | Require the prepared helper chain |
| Re-scan full `vivi --help` every action | **this file** + one targeted `--help` |

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
