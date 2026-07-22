# Wave planning

Use this reference to prepare a large parallel wave before product Hands fan
out. It is a deep-planning override, not the default for ordinary Fleet work.

**Invariant:** every admitted goal has accepted intent, proved readiness,
independently checked code facts, an executable delivery graph, and an
independent fact-check of that graph. Every role handoff routes through Mind as
a prepared Fleet dependency chain.

**Chain gate:** no planning or audit role starts before `fleet prepare` or
without a successful `fleet claim`. Each pass ends with `fleet settle` and the
next pass names the prior handle with `--depends-on`. Admission requires
`fleet advance --gate admission` on the terminal delivery-audit handle.

Read [`lowering.md`](lowering.md), [`planner-protocol.md`](planner-protocol.md),
and [`auditor-protocol.md`](auditor-protocol.md). Execution, freeze, and
closeout remain in [`wave.md`](wave.md).

## When to use it

Use deep wave planning when one bad premise or packet would be replicated
across several Hands, dependent stages, repositories, or hot files. Strong
signals include:

- several implementation units will launch together;
- delivery graphs have cross-goal dependencies;
- write scopes overlap or span repositories;
- validation is expensive or easy to run falsely green;
- campaign claims have not been checked against current code; or
- an aggregate freeze must reconcile the result.

Use ordinary lowering for a small, sequential, well-understood change. Do not
add review gates merely because the work is important. The trigger is fan-out
risk and the cost of late discovery.

Already-lowered work may bypass new planning only when intent, live-code facts,
dependencies, write scopes, and validation commands are still current.

## Control path

```text
Mind
  -> fleet prepare --pass p1 -> Planner claim/settle
  -> Mind: intent disposition
  -> fleet prepare --pass p2 --depends-on <p1> -> Planner claim/settle
  -> fleet prepare --pass goal-audit --depends-on <p2> -> Auditor claim/settle
  -> Mind: findings disposition
  -> corrected p2 + repeated goal-audit when required
  -> fleet prepare --pass p3 --depends-on <clean-goal-audit> -> Planner claim/settle
  -> fleet prepare --pass delivery-audit --depends-on <p3> \
       --depends-on <clean-goal-audit> -> Auditor claim/settle
  -> corrected p3 + repeated delivery-audit when required
  -> fleet advance --gate admission --handle <clean-delivery-audit>
```

A clean audit skips only its correction assignment. It does not skip the audit
receipt or Mind disposition. Planner and Auditor never hand work directly to
each other. Each role arrow is a prepared dependency created before the
downstream runtime starts.

## Pass contracts

| Step | Owner | Required output | Stop condition |
| --- | --- | --- | --- |
| Select | Mind | One goal or coherent theme; invariant, authority, horizon, decision owner | No raw campaign dump |
| P1 Forge | Planner | Intent, outcome, boundaries, acceptance shape, non-goals, open decisions | No goal-check or delivery graph |
| Intent gate | Mind | Accept, reject, or named revision; operator decisions recorded | Intent and campaign fit only |
| P2 Check | Planner | Done-when, evidence, dependencies, exact validation, write scope, audit flags | No delivery graph |
| Goal audit | Auditor | Independent fact report against live code and named authorities | No edits or stage design |
| Disposition | Mind | Every finding classified and routed | No silent finding loss |
| Goal correction | Planner | Corrected artifact and receipt, when required | Required findings closed before P3 |
| P3 Delivery | Planner | Ordered units with scopes, dependencies, done-when, validation, non-goals | Corrected READY goal is authority |
| Delivery audit | Auditor | Fact report over paths, symbols, commands, scopes, dependencies, and coverage claims | No edits or implementation review |
| Disposition | Mind | Every finding classified and routed | No filing while required findings remain |
| Delivery correction | Planner | Corrected graph and receipt, when required | Required findings closed before admission |
| Admit | Mind | Admission receipt and filed-unit authority | Only admitted units reach product Hands |

For every Planner or Auditor row, the required output is a settled handle whose
report cites the artifact and receipts. Mind decisions remain durable Vivi
replies/needs. A file, commit, or sub-agent return without that chain cannot
satisfy the stop condition.

## P1: Forge

P1 lowers campaign intent, not code mechanics. It answers:

- What outcome changes for the product or architecture?
- What invariant must survive implementation choices?
- Which authority owns the decision?
- What is explicitly outside the goal?
- Which operator decisions block deeper planning?

Decision goals may stop here with options, a default, and a decision owner.
They do not acquire fictional readiness criteria while the decision is open.

Mind reviews P1 for intent. It does not duplicate the later code audit. Batch a
few short intent decisions when that reduces serial routing, but preserve one
disposition per goal.

## P2: Check and goal-reality audit

P2 Check converts accepted intent into readiness evidence. The Planner must
name:

- numbered done-when criteria;
- the artifact or behavior proving each criterion;
- exact validation commands and expected result;
- resolved, deferred, and escalated dependencies;
- hot, supporting, read-only, and forbidden paths; and
- factual claims the Auditor should challenge.

Status is `checked, awaiting goal-reality audit`, not READY.

The goal-reality Auditor checks the artifact against current code, tests,
design authorities, child campaigns, and ledgers. Hunt especially:

- nonexistent or misnamed files, types, functions, APIs, tests, and commands;
- negative claims contradicted by an existing implementation;
- behavior or failure paths missing from done-when;
- stale state and authority contradictions;
- incomplete dependencies or write scopes; and
- duplicated authority hidden by a new name.

The Auditor reports facts and counterevidence. Mind decides disposition.
Planner makes corrections.

`fleet prepare` freezes the Auditor seat's live Vivi capacity before spawn. The
configured review model and provider independence are part of the chain. Task
shape does not permit substituting the Planner's model family.

## P3: Delivery and delivery-reality audit

P3 turns the corrected READY goal into executable units. Each unit requires:

```text
unit_id: <stable id>
outcome: <one behavioral result>
depends_on: <unit ids or none>
done_when: <numbered criteria>
write_scope: <exact paths or owned tree>
read_scope: <needed context>
forbidden: <explicit exclusions>
validation: <exact commands and expected evidence>
model_class: <capacity reason>
audit_policy: <risk family and required review>
```

The delivery-reality Auditor reads the finished graph as the future Hand will.
Verify:

- every named file, symbol, type, test, and command exists or is explicitly
  created by an earlier unit;
- filtered tests match real tests and cannot return a misleading green;
- write scopes include every required change and expose cross-unit overlap;
- dependencies reflect live code constraints;
- done-when and validation prove the claimed outcome; and
- contention, coverage, and independence claims have evidence.

Wave 0 originally called this a **bonus round**. It found defects after the
goals had passed intent and goal-reality review. For future large waves it is a
normal admission gate.

## Finding disposition

Mind makes this minimum set recoverable for every audit finding:

```text
finding_id: <stable id>
gate: goal-reality | delivery-reality
severity: critical | high | medium | low
blocking: yes | no
claim: <what was challenged>
evidence: <path, line, command, or authority>
disposition: required_correction | accepted_residual | false_finding
owner: planner-N | mind | decision owner
correction_receipt: <artifact commit or none>
recheck: required | not_required | <audit receipt>
```

This is an evidence contract, not a required ten-field inline form. Keep each
field on its natural authority: the Auditor report may own claim, evidence,
severity, and blocking status; the Mind reply may own disposition and owner;
the Planner task or commit may own correction and recheck receipts. A single
Vivi source handle must reconstruct the complete chain. Do not maintain a
duplicate ledger when the linked report, trace, and Git receipts already do so.

Severity and blocking status are separate. A corrected medium write-scope gap
does not become a high finding merely because it mattered. Do not summarize a
mixed report as "N errors" unless the counting rule and severities are shown.

## Wave 0 bootstrap

Wave 0 is planning work that creates the first admitted inventory. Product
Hands may remain idle while Planners and Auditors own active gates.

Before the first launch, produce the campaign-specific equivalents of:

1. bounded objective, non-goals, decision owner, and cutoff;
2. repository baselines and authority map;
3. capability or lock ledger grounded in current evidence;
4. complete gap inventory with goal classes and owners;
5. operator decision records and defaults;
6. goal dependency graph and ordered forge queue;
7. campaign-specific capacity, refill, audit, collision, and freeze policy;
8. admitted first-wave candidate list; and
9. explicit no-Hand list with reasons and reopen conditions.

Goal depth may vary:

| Goal shape | Required depth before launch |
| --- | --- |
| Open operator decision | P1 decision record; stop until decided |
| Critical blocker or shared spine | Full P1 -> P2 audit -> P3 audit |
| Medium next-wave goal | P1 and P2 audit now; P3 before admission |
| Process or ledger output | Wave 0 gate artifact, not a product delivery |

Campaigns choose their own seat counts, inventory targets, sampling rates, and
lock thresholds. Record the derivation; do not copy numbers from another wave.

## Parallel planning

The passes are serial **within one goal** and parallel **across independent
goals**:

```text
Goal A  P1 -> Mind -> P2 -> Audit -> fix -> P3 -> Audit -> admit
Goal B       P1 -> Mind -> P2 -> Audit -> fix -> P3 -> Audit -> admit
Goal C            P1 -> Mind -> P2 -> Audit -> fix -> P3 -> Audit -> admit
```

Rules:

- one Planner owns one goal or coherent theme at a time;
- one runtime executes one bounded task handle; never batch unrelated goals,
  passes, or findings into one sub-agent for throughput;
- batch only short Mind intent reviews and dispositions;
- respect goal dependencies before starting a deeper pass;
- never combine unrelated goals to fill a model context;
- expand Planner or Auditor lanes only for disjoint artifact scopes; and
- measure throughput at admitted units, not documents produced.

During steady execution, Wave N Hands consume admitted units while Planners and
Auditors prepare Wave N+1. Refill before inventory can reach zero.

## Admission receipt

Mind may prepare product Hands only after `fleet advance --gate admission`
passes on the terminal delivery-audit handle. The linked reports and prepared
task bodies must name:

- objective, non-goals, decision owner, cutoff, and repository baselines;
- accepted P1 intent and all required operator decisions;
- corrected P2 goal artifact and goal-reality audit receipt;
- corrected P3 delivery artifact and delivery-reality audit receipt;
- every required finding and its correction receipt;
- ordered units and dependencies;
- exact write scopes and collision policy;
- validation and implementation-audit policy;
- READY inventory and explicit no-Hand list;
- remaining residuals with owners and reopen conditions;
- the prepared dependency handles that reconstruct every planning assignment,
  role report, Mind disposition, and correction; and
- the resolved role bindings used for Planner and Auditor runtimes, including
  the independent Auditor provider/model/thinking receipts.

A commit subject, chat statement, or delivery file on disk is not admission.
The authoritative inventory must record the unit READY after both audits and
the passing helper check.

## Communication evidence

Use `fleet prepare` from P1 onward. Each prepared assignment states one pass,
one goal, allowed artifact paths, inputs, done-when, and prohibition on
deeper-pass work. Each role claims and settles before returning a short pointer.
The helper recursively cross-checks its dependency receipts against live Vivi
tasks and trace state. Git proves artifact chronology; the prepared chain proves
routing. Neither substitutes for the other.

Chat may explain a Vivi record, but it is never the primary planning reference.
If chat changes intent, scope, ordering, or a decision, the Mind records that
change in Vivi before preparing dependent work. A runtime notification only wakes
the Mind to inspect the durable chain.

If work started without a handle, stop the affected gate. File a new recovery
task or need to the actual owner. Its body states when the missing handoff was
discovered, labels the process deviation, links the available chat, artifact,
and Git evidence, and marks chronology as reconstructed. Then restart or
continue from that valid new handle. Do not backfill an ordinary task stub and
present it as the original assignment.

## Failure patterns

| Failure | Correction |
| --- | --- |
| Planner or Auditor spawned before `fleet prepare` | Stop the gate; prepare a labeled recovery assignment; restart from its generated prompt |
| Runtime/chat return used as the planning report | Require successful `fleet settle` before advancing |
| Task stub backfilled after runtime start | Label it reconstructed; never claim contemporaneous routing |
| Auditor spawned on Planner/implementer capacity instead of its Vivi role binding | Stop the gate; respawn on the configured independent Auditor binding |
| Unrelated goals, passes, or findings combined in one runtime | Split into one bounded handle per runtime |
| Aggregate wait loses runtime ids | Reconcile from the per-handle runtime map and Vivi; never infer completion from file changes |
| One Planner forges, checks, and delivers a high-fan-out goal in one session | Split P1, P2, and P3 into fresh assignments |
| Mind reviews code truth during the intent gate | Keep the gate short; route code facts to the Auditor |
| Auditor edits the artifact | Report To Mind; Planner owns corrections |
| Auditor sends findings directly to Planner | Mind dispositions and routes every finding |
| P2 audit is treated as enough | Audit the executable P3 graph before preparing Hands |
| Filtered test command is assumed valid | Verify that it matches real tests and meaningful assertions |
| Delivery graph exists, so the wave is called READY | Require both audits, corrections, and passing `fleet advance --gate admission` |
| Finding counts mix notes, severities, and corrections | Preserve the report schema and counting rule |
| Campaign seat or inventory numbers become Fleet law | Keep numeric policy in the campaign overlay |
| Product Hands receive raw campaign prose | Stop preparation; return to the missing planning gate |

## Planning retrospective

At the wave freeze, trace every material planning defect:

- where it entered: campaign, P1, P2, or P3;
- which gate detected it;
- its severity, blocking status, and disposition;
- whether the same defect class escaped into implementation; and
- which packet or protocol change will prevent recurrence.

The success measure is fewer avoidable execution interruptions and honest
residual risk. A high finding count is not the objective, and an audit cannot
claim time saved without measured counterfactual evidence.
