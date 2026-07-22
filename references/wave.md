# Wave execution and closeout

A wave is a bounded delivery interval for work that needs parallel Hands,
rolling planner inventory, independent review, and an aggregate closeout.

**Invariant:** a large parallel wave launches only admitted units, routes every
role handoff through the Mind, and cannot close until aggregate evidence is
reconciled.

Read [`wave-planning.md`](wave-planning.md), [`mind-cycle.md`](mind-cycle.md),
and the reference for the selected execution backend. This document defines
wave execution and closeout; it does not repeat preparation, role boot,
runtime, or partial-commit mechanics.

## When to use a wave

Use a wave when ordinary per-unit Fleet flow is not enough to keep dependency,
write-scope, review, and campaign truth coherent. Typical signals are several
concurrent Hands, multiple delivery graphs, shared hot files, cross-repo work,
or a required aggregate review.

A small low-risk batch can remain an ordinary Fleet loop. Use ordinary lowering
from [`lowering.md`](lowering.md); do not impose this preparation cycle on every
plan. If the work does not need a freeze and evidence reconciliation, do not
call it a wave.

Campaign overlays set numeric seat, inventory, sampling, and lock thresholds.
This reference intentionally does not make one campaign's numbers universal.

## Planning clock

Wave planning is rolling, not a phase that starts after the prior wave ends.

```text
bootstrap:  Wave 0 plans and audits the first READY inventory
steady:     Wave N executes while planners lower Wave N+1
boundary:   Wave N freezes, reconciles, and selects Wave N+1
```

Wave 0 is valid work. Idle product Hands are not starvation when the declared
posture is planning-only and planners or auditors own the active gates.

## Planning and admission

Large parallel waves use the separate P1 Forge, P2 Check, goal-reality audit,
P3 Delivery, and delivery-reality audit gates in
[`wave-planning.md`](wave-planning.md). Ordinary work stays on the standard
lowering path.

Launch only from one admission receipt with corrected planning artifacts, both
audit receipts, closed required findings, repository baselines, an ordered unit
graph, exact write scopes, validation policy, READY inventory, and a no-Hand
list. A delivery file or chat claim alone is not admission.

## Wave lifecycle

| Phase | Mind action | Exit evidence |
| --- | --- | --- |
| **Prepare** | Complete admission; record baseline, policies, and cutoff | READY packet exists |
| **Launch** | File a bounded burst that fits capacity and non-overlapping scopes | Active assignment ledger |
| **Flow** | Route completions, audits, repairs, and refills; planners build the next inventory | Every signal has a disposition |
| **Drain** | Stop new implementation filing at the cutoff; finish or park in-flight work | No unclassified in-flight unit |
| **Freeze** | Reconcile audit debt, aggregate findings, campaign state, repo evidence, and decisions | Freeze receipt passes |
| **Close** | Decision owner closes, extends, or holds the wave; clean transient state | Next posture is explicit |

Prepare precedes Launch. Flow is event-driven. Drain and Freeze are mandatory
for anything named a wave. A failed freeze reopens the same wave as an explicit
repair extension; it does not become a successful closeout.

## Role clocks

| Role | Looks at | Does not own |
| --- | --- | --- |
| **Mind** | Board, dependencies, write scopes, review debt, cutoff, dispositions | Product implementation, test execution, planning authorship, code review |
| **Planner** | Selected next-wave goal and routed audit findings | Product source, Hand filing, direct Auditor coordination |
| **Hand** | One admitted delivery unit or bounded repair | Raw campaign lowering, acceptance |
| **Auditor** | Goal-reality audit, delivery-reality audit, or selected landed unit | Planning corrections, product repair, acceptance |
| **Head** | Aggregate architecture, priority, or complexity trends | Unit review, GO stamp, unfreeze decision |

Concurrency is bounded by the smallest real bottleneck: write scopes, planner
refill rate, audit capacity, or Mind routing bandwidth. A nominal Hand cap is
not a target.

Before filing, record each active unit's exact scope. If scopes overlap, file a
different unit, serialize them, or use a Mind-created isolated branch/worktree.
Do not rely on a mental collision table during a long wave.

## Communication during a wave

A completion has three surfaces:

| Surface | Meaning |
| --- | --- |
| Runtime notification | Wake signal only |
| Vivi task and mail | Durable assignment, evidence, verdict, and disposition trail |
| Git receipt | Repository fact: commit, diff, and tip |

Process a completion by task handle plus commit receipt. Read the report,
confirm that the receipt exists and matches the declared scope, route required
review or repair, update dependency and scope state, then absorb the Mind's
mail. A repeated notification is duplicate only when the same task handle and
receipt already have a recorded disposition.

Never bulk-absorb unread mail. Absorption means the recipient read and
processed that item; it is not inbox cleanup or memory. Do not absorb mail for
another role merely to make counters green.

Keep durable state in artifacts and Vivi handles:

- active unit: task handle, role, scope, dependency, branch, expected receipt;
- review debt: auditor task handle and policy reason;
- repair chain: source verdict, repair task, re-audit task;
- planning state: goal artifact, audit report, delivery artifact; and
- freeze state: baseline tips, cutoff, unresolved signals, closeout receipt.

## Flow loop

During active execution, the Mind repeats a short routing loop:

1. Observe completions, mail, runtime failures, dependencies, and repo tips.
2. Give every material signal a Fleet disposition.
3. Route required audits before accepting the affected unit.
4. On a finding, file one bounded repair with the exact finding, expected
   behavior, scope, and validation.
5. Re-audit required repairs. Do not treat a repair author's validation as
   independent verification.
6. Free the completed scope and file the next qualified READY unit when
   capacity, inventory, cutoff, and policy allow.
7. Refill through Planners before READY inventory reaches the configured floor.

Sub-agent completion events drive the loop; the scheduled cadence is only a
backup. Use the adaptive cadence in [`mind-cycle.md`](mind-cycle.md), not
wave-specific hard-coded intervals.

### Audit policy

Define review classes before launch. Always review architecture, authority,
security, persistence, ABI, shared spine, prior-repair work, and any unit whose
acceptance depends on claimed compilation or test passage without an
independent receipt, unless a stronger project policy applies. Sample
genuinely low-risk families with a recorded rotation.

Auditor scarcity creates review debt, not permission to waive the policy. A
unit can land while review is queued, but it cannot be accepted while its
required review remains open. If a sampled unit fails, escalate the family and
inspect in-flight or pending siblings for the same defect pattern.

The Mind does not reproduce builds, tests, or code review. An independent
validation receipt is CI evidence or an Auditor/verification-Hand command and
result tied to the reviewed repository tip. The implementing Hand's assertion
is not independent. Route an unreceipted claim to an Auditor or a bounded
verification Hand before acceptance. This preserves independence and keeps the
Mind on the routing clock.

### Repair discipline

After a systemic `block_ship`:

1. stop filing the affected family or scope;
2. identify siblings exposed to the same assumption;
3. amend their packet criteria or file focused audits;
4. route the smallest coherent repair; and
5. resume normal sampling only after independent clean evidence.

If a Planner or Hand reports a missing commit, return the artifact to that role
for a correct receipt. The Mind never commits another role's work or impersonates
its identity. New files must be added before a path-scoped commit; backend boot
and commit details remain in the role and backend references.

## Unit packet

Every product task cites one admitted delivery unit and contains only the
context needed to execute it:

```text
unit: <delivery unit id and artifact path>
goal: <goal id and campaign path>
depends_on: <task handles or none>
done_when: <numbered behavioral criteria>
write_scope: <exact paths or owned tree>
read_scope: <needed context outside write scope>
forbidden: <explicit exclusions>
validation: <exact commands or evidence>
branch: <main, feature branch, or worktree>
model_class: <capacity reason>
audit: <policy class and family counter>
```

For a repair, replace general context with the source verdict handle, exact
finding, required behavior, scope, and re-audit requirement. Do not tell a Hand
to "fix the audit report."

## Wave freeze (mandatory)

Freeze is the aggregate truth gate that unit flow cannot provide. Declare it
before the current wave is called complete, even when all known units appear
accepted.

### Freeze sequence

1. Record the cutoff and baseline-to-tip range for every affected repository.
2. Stop filing new implementation units. Finish, cancel, or explicitly park
   each in-flight assignment.
3. Complete required audits and re-audits. Classify every landed unit as
   accepted, pending review, repair, reverted, or excluded from the wave.
4. Route aggregate Head samples for architecture, priority, or complexity as
   the campaign requires.
5. Give every Head finding a disposition. Advisory means Heads do not own the
   gate; it does not mean the Mind may ignore their evidence.
6. Reconcile campaign artifacts, dependency state, lock or capability ledgers,
   validation receipts, and repo tips against the accepted unit set.
7. Produce the retrospective and freeze receipt. Present material decisions to
   the named decision owner.
8. Close, hold, or reopen the same wave for a bounded repair extension.

Do not land new spine or product behavior inside the freeze. If a blocking
repair is required, record the failed freeze, reopen execution for that repair,
then run the freeze again.

### Freeze receipt

The receipt must name:

- baseline and final tips per repository;
- admitted, landed, accepted, repaired, pending, and excluded units;
- zero required review debt; list optional review debt and its disposition;
- validation evidence and known red or unrun checks;
- aggregate findings with dispositions;
- campaign and ledger changes with evidence;
- unexplained or foreign dirt without altering it;
- unresolved operator decisions; and
- the next posture: launch, hold, planning-only, or campaign close.

No chat estimate substitutes for this receipt.

## Retrospective

The Mind may assemble the retrospective, but a reviewer independent of the
implementation and routing work should validate material claims. A
self-authored narrative is useful evidence, not an objective audit.

Separate facts from interpretations:

| Class | Examples | Evidence |
| --- | --- | --- |
| **Measured fact** | unit count, task duration, verdict count, commit range | Vivi query, task handle, Git receipt |
| **Reviewed fact** | defect class, false premise, scope collision avoided | Auditor or Head report |
| **Inference** | a gate saved time, a model was mismatched, a buffer was healthy | Reasoning plus counterevidence |
| **Unknown** | missing timing, unrecorded idle, unverifiable causal claim | State unknown; do not estimate as fact |

For each material planning defect, record where it entered, which gate detected
it, its disposition, and whether the same defect class escaped into execution.
The preparation measure is fewer avoidable execution interruptions, not a high
finding count.

Use one compact structure:

1. objective and outcome against the admission packet;
2. evidence table of scope, receipts, validation, and audit results;
3. process deviations, impact, and detection source;
4. recurring patterns across units, not anecdotes alone;
5. changes to protocol, packet, capacity, or policy;
6. owner and next-wave check for every change; and
7. residual risks and unresolved decisions.

Avoid vanity throughput metrics without a derivation. Do not say an audit
"caught N errors before delivery" unless the report defines what counts as an
error, names the reports, and separates blocking findings from notes. Do not
claim causal savings from defects that were never allowed to proceed.


## Closeout cleanup

Cleanup reconciles wave-owned transient state before the next launch. It does
not erase history or normalize the shared workspace.

- Close or supersede wave-owned tasks, needs, and wants with a reason.
- Absorb only mail that the recipient actually processed.
- Keep durable decisions in campaign artifacts or memos; remove transient
  routing memos only after their facts are recoverable from handles.
- Record foreign dirt and leave it untouched.
- Confirm no wave-owned uncommitted change is unexplained.
- Run the repository's declared closeout validation through a Hand and attach
  its receipt. State red or skipped checks explicitly.
- File bounded maintenance when the freeze finds it. Do not make a full
  `$housekeeping` pass an automatic part of every wave; it can create unrelated
  work and obscure the wave diff.

"Clean" means wave-owned state is explained and reconciled. It does not mean
every shared tree and every role inbox is globally empty.

## Failure patterns

| Failure | Correction |
| --- | --- |
| Hands launch from raw campaign bullets | Return to large-wave preparation or ordinary lowering |
| Planner and Auditor coordinate directly | Route report and disposition through Mind |
| Fixed seat or READY counts treated as universal | Derive limits from current bottlenecks and campaign policy |
| Mind runs tests, reviews code, or commits role work | File verification, audit, or receipt repair to the correct role |
| Audit policy waived because Auditors are busy | Queue review debt; do not accept early |
| Claimed build or test passage accepted without an independent receipt | Route verification; keep the unit landed but unaccepted |
| Same defect recurs in a sibling unit | Pause family, inspect siblings, amend packets, escalate sampling |
| Completion inferred from notification or SHA alone | Reconcile task handle, report, receipt, and scope |
| Freeze skipped because units look done | Run aggregate reconciliation before declaring completion |
| Head report labeled advisory and ignored | Mind records a disposition and owns the decision |
| Bulk absorption used as cleanup | Read and process per recipient; preserve unresolved signals |
| Full housekeeping automatically follows every wave | Run declared closeout checks; file separate maintenance only when justified |
| Retrospective repeats Mind's narrative as fact | Independent review; label measured facts, inferences, and unknowns |

## Quick checklist

```text
PREPARE
[ ] objective, cutoff, decision owner, baselines
[ ] P1 intent gate; P2 goal audit and required corrections closed
[ ] P3 delivery audit and required corrections closed
[ ] admitted READY artifacts and no-Hand list
[ ] dependency, scope, validation, audit, and inventory policy

FLOW
[ ] every signal dispositioned
[ ] review debt tracked; required audits before accept
[ ] acceptance-critical build and test claims have independent receipts
[ ] systemic failures propagated to sibling packets
[ ] planners refill ahead of drain

FREEZE
[ ] filing stopped; in-flight work classified
[ ] accepted set and repo tips reconciled
[ ] aggregate findings dispositioned
[ ] ledgers, validation, retrospective, and freeze receipt complete

CLOSE
[ ] decision owner chose close, hold, or repair extension
[ ] wave-owned board, memory, mail, and dirt reconciled
[ ] next posture and next READY inventory explicit
```

## Related references

| Reference | Covers |
| --- | --- |
| [`wave-planning.md`](wave-planning.md) | Large-wave preparation, planning audits, and admission |
| [`subagent.md`](subagent.md) | Sub-agent backend mechanics (spawn, completion, partial-commit) |
| [`tmux.md`](tmux.md) | Persistent tmux backend mechanics |
| [`vivi-pty.md`](vivi-pty.md) | Structured PTY backend mechanics |
| [`mind-cycle.md`](mind-cycle.md) | Per-cycle operations (sensors, dispositions, absorb/accept) |
| [`lowering.md`](lowering.md) | Planner pipeline (goal-forge → delivery) |
| [`model-selection.md`](model-selection.md) | Model class routing by unit shape |
| [`multi-lane.md`](multi-lane.md) | Branch integration, write-scope non-overlap, lane lifecycle |
| [`tasking.md`](tasking.md) | Board kinds, multi-hand routing, stale task disposition |
