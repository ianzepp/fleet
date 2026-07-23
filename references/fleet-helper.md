# Fleet helper process

`scripts/fleet.py` is the canonical transition layer between the Mind and every
Planner, Hand, Auditor, and Head. It turns assignment filing, runtime claim,
completion reporting, dependency chains, and gate checks into one fail-closed
state machine.

Direct `vivi` commands remain appropriate for observation and administration:
`board`, `task show/list`, `mail show/list/absorb`, role configuration, memos,
and operator mail. Do not use raw `vivi task send`, `task done`, or role report
mail for Fleet assignments. The helper owns those transitions.

## Commands

Set the skill root once in examples:

```bash
SK=/path/to/fleet
FLEET="$SK/scripts/fleet.py"
ROOT=/path/to/project
```

### 1. Mind prepares

```bash
python3 "$FLEET" prepare --project "$ROOT" \
  --to hand-1 --pass implement --scope 'src/widget/' \
  --subject 'Implement widget retry policy' \
  --body 'Full bounded assignment, invariant, done-when, and verification.'
```

Use `--body-file <path>` for a long assignment. `prepare` resolves and freezes
the role binding, creates the Vivi task, seals the normalized assignment body,
writes `.vivi/fleet/chain/<handle>.json`, and prints the complete canonical boot
prompt. Deliver that output unchanged to the runtime.

When work depends on an earlier assignment, add its prepared handle:

```bash
python3 "$FLEET" prepare --project "$ROOT" \
  --to auditor-1 --pass review --scope 'src/widget/' \
  --depends-on <implement-handle> \
  --subject 'Review widget retry policy' \
  --body 'Review the landed implementation and receipts.'
```

`--depends-on` is repeatable. The helper refuses dependencies that lack Fleet
receipts. This creates the chain later checked by `advance`.

#### Work-graph nodes (`--node`)

When the durable topology lives in a Vivi work graph (planning pipeline or
product delivery DAG), pass the ready node:

```bash
python3 "$FLEET" prepare --project "$ROOT" \
  --to hand-1 --pass implement --scope 'src/widget/' \
  --node mir-wave-2:verify \
  --subject 'Re-verify unit after repair' \
  --body-file /tmp/assignment.md
```

| Step | Behavior |
| --- | --- |
| `prepare --node <graph>:<source-id>` | Calls `vivi graph ready`; refuses blocked, active, terminal, or missing nodes; stores `graph_node` on the receipt |
| `claim` | After a durable claim reply, calls `vivi graph activate <node> --task <handle>` |
| `settle` | Completes the **task** and report chain only — does **not** mark the graph node done |
| After acceptance / disposition | Mind (or explicit disposition path) runs `vivi graph complete <graph>:<source-id>` so successors enter the ready frontier |

Do not use `--node` for ordinary standalone tasks that are not graph members.
Do not hand-call `graph activate` before claim when using the helper chain — claim
is the activation gate. Observation and board frontiers: [`vivi.md`](vivi.md)
§ Executable work graphs.

| Role | Allowed `--pass` |
| --- | --- |
| `planner-N` | `goal-forge`, `delivery`, `p1`, `p2`, `p3` |
| `hand-N` | `implement` |
| `auditor-N` | `review`, `goal-audit`, `delivery-audit` |
| `head-*` | `advisory` |

### 2. Mind delivers / runtime claims

`prepare` stores and prints the boot prompt. To recover or re-wake the same
handle, reprint that captured prompt without creating another assignment:

```bash
python3 "$FLEET" prompt <handle> --project "$ROOT"
```

Deliver `prepare` / `prompt` output unchanged.

The boot prompt begins with:

```bash
python3 "$FLEET" claim <handle> --role <role> --project "$ROOT"
```

`claim` verifies the prepared receipt, task recipient, normalized body hash,
and live role binding. It then files the claim reply and records the claim.
If the receipt includes `graph_node`, claim activates that Vivi work-graph node
with the task handle after the claim edge is durable. The runtime must refuse
the assignment if this command fails.

After claim, the runtime loads the charter and named task, then executes only
that handle. The boot prompt contains the exact commands.

### 3. Runtime settles

```bash
python3 "$FLEET" settle <handle> --role <role> --project "$ROOT" \
  --note 'Concise completion evidence' \
  --report-file /tmp/<role>-<handle>-report.md \
  [--repo <repo> --tip <sha>] \
  [--verdict clean_pass|residual|block_ship]
```

`settle` completes the Vivi task, replies to the assignment with the durable
report, verifies both transitions, and records the settlement. `--repo` and
`--tip` travel together. Auditor passes (`review`, `goal-audit`,
`delivery-audit`) require a
verdict. Use `--report '<body>'` instead of `--report-file` only for a short
report.

A successful runtime return is only:

```text
Settled <handle>. Full report is attached to that Vivi chain.
```

The Mind reconciles the receipt and repository state. Runtime chat cannot fill
in a missing claim or settlement.

### 4. Mind advances

Acceptance terminates at a clean auditor `review` assignment that depends on
at least one settled `implement` assignment. Both implementation and terminal
review settlements must include the repository and Git tip:

```bash
python3 "$FLEET" advance --project "$ROOT" \
  --gate acceptance --handle <review-handle> --json
```

Admission terminates at a clean auditor `delivery-audit` assignment whose
dependency chain contains settled planner `p1`, `p2`, and `p3` assignments plus
the clean auditor `goal-audit` assignment:

```bash
python3 "$FLEET" advance --project "$ROOT" \
  --gate admission --handle <delivery-audit-handle> --json
```

`advance` is pure read. It recursively checks every prepared dependency
against live Vivi task and trace state, the frozen body, claim, report, and
settlement. Acceptance also requires the terminal review repository and Git tip
to match an implementation receipt. `residual` and `block_ship` do not pass
either gate. Prepare repair or planning-correction assignments, then prepare a
new terminal audit.

When a cycle records acceptance or admission, couple the check to cycle close:

```bash
python3 "$SK/scripts/fleet-cycle-close.py" --project "$ROOT" --acted \
  --summary 'accepted widget retry policy' \
  --gate-check acceptance:<review-handle> \
  --disposition '<signal>=acted:<evidence>'
```

## Runtime delivery

The helper output is the boot prompt. Backends only deliver it:

| Backend | Delivery | Completion wake |
| --- | --- | --- |
| Sub-agent | spawn with the exact `prepare` output | completion event |
| tmux | send the exact output to the role pane | poll classification |
| vivi-pty | write the exact output to the role terminal | poll diagnostics |

Never reconstruct a custom boot prompt. Never spawn before `prepare` succeeds.
Use `prompt` for same-handle recovery or re-wake. One prepared handle maps to
one runtime invocation at a time.

## Failure recovery

| Failure | Action |
| --- | --- |
| `prepare` fails | Repair role binding, dependency, scope, or Vivi task filing; do not spawn |
| `claim` fails | Runtime refuses work; Mind prepares a corrected assignment |
| `settle` partially fails | Re-run the same settle command; it resumes from live task/report state |
| `advance` fails | Read named gaps; prepare repair/correction work; do not accept or admit |
| Receipt missing for historical work | Prepare a new recovery assignment; do not backfill a fake original handoff |

The helper does not choose runtime capacity, branch strategy, write scope,
verdict, or product policy. Those remain role and Mind judgments. It enforces
that the resulting transitions have one durable, linked shape.

Fleet receipts are local integrity records, not cryptographic attestations.
Write access to the project `.vivi` directory is inside the trust boundary.
`advance` cross-checks each declared assignment against live Vivi and checks
the recorded Git receipt linkage. The Mind still verifies the actual repository
state. The helper cannot protect a mailspace from a privileged local writer.
