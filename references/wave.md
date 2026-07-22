# Wave execution with sub-agents

How to run a large parallel wave of work using sub-agent Hands, Planners, and
Auditors. Covers the wave lifecycle, concurrent communication management,
churn reduction, and operational patterns learned from multi-hour autonomous
campaign execution.

**Prerequisite reading:** [`subagent.md`](subagent.md) (backend mechanics),
[`mind-cycle.md`](mind-cycle.md) (per-cycle ops), [`lowering.md`](lowering.md)
(planner pipeline), [`mind-protocol.md`](mind-protocol.md) (delegation
principle).

---

## When this applies

| Situation | Use this reference |
| --- | --- |
| Wave with 8+ delivery units across 3+ repos | Yes |
| Wave with 2+ concurrent Hands + 2 Planners + 2 Auditors | Yes |
| Single-repo, 1-2 unit factory loop | No — use `subagent.md` directly |
| tmux/PTY backend | No — this is sub-agent specific |

---

## Wave lifecycle

A wave has five phases. The Mind owns all five; Hands/Planners/Auditors/Heads
execute within them.

```text
Phase 1: PLANNING (planners + Heads)
  └── Goal-forge → goal-check → auditor reality-check → delivery specs
      └── Output: READY inventory on disk (8-15 delivery units)

Phase 2: LAUNCH (Mind)
  └── File initial Hands from READY inventory (non-overlapping write scopes)
      └── Output: 4-6 concurrent sub-agents spawned

Phase 3: EXECUTION (Hands + Planners + Auditors, concurrent)
  └── Hands implement → commit → report
  └── Planners lower next-wave inventory concurrently
  └── Auditors review completed units
  └── Mind routes completions, files next units, manages block_ships
      └── Output: units land, audit, accept, repair, re-audit cycle

Phase 4: FREEZE (Mind + Heads)
  └── Declare freeze → no new Hand units
  └── Auditors finish pending reviews
  └── Heads sample aggregate diff (architecture + complexity)
  └── Lock ledger rescore with evidence
  └── Output: rescored locks, Head advisory reports

Phase 5: OPERATOR REVIEW
  └── Present rescored locks + Head findings to operator
  └── Operator decides: unfreeze, adjust scope, or hold
      └── Output: unfreeze → next wave begins at Phase 1
```

### Phase ordering is strict

Phases 1 → 2 → 3 are sequential (planning before launch before execution).
Phase 4 (freeze) is **mandatory** — it is not optional even when all units are
accepted. Phase 5 (operator review) requires the freeze outputs.

**Common failure:** declaring "wave complete" and skipping the freeze. The
freeze provides aggregate-level review (Head architecture sampling, lock
rescore) that individual unit audits cannot provide.

---

## Concurrent role management

During Phase 3 (execution), multiple roles run concurrently on different
clock positions:

```text
time ─────────────────────────────────────────────────────►

Planners    ████████ lowering next wave ████████ done
Hands       ──────── implementing ──── commit ── done ── next
Auditors    ────────────────────────── reviewing ── verdict
Heads       ───────────────────────────────────────── sample (freeze only)
Mind        route route route route route route route route route
```

### Role concurrency rules

| Role | Concurrency | Communication |
| --- | --- | --- |
| Planners | 2 parallel (non-overlapping goals) | Report READY To mind when spec lands |
| Hands | 4-6 parallel (non-overlapping write scopes) | Report done + mail To mind on completion |
| Auditors | 2 parallel (different units) | Report verdict To mind |
| Heads | 2-3 at freeze only | Advisory reports To mind |
| Mind | 1 (serial routing) | Files tasks, absorbs mail, routes verdicts |

### Write-scope collision check

Before filing any Hand, verify the unit's write scope does not overlap with
any currently assigned Hand's write scope. If it does:
- File a different unit
- Wait for the blocking Hand to commit
- Serialize the two units

The write-scope matrix is the Mind's responsibility — no Hand enforces it.

```text
# Example collision check before filing
hand-5: radix/crates/radix-mir-wgsl/src/lib.rs  (d-p-01 S1)
hand-2: radix/crates/radix/src/driver/mod.rs    (d-a-02 S1)
hand-6: faber/crates/exempla/                   (d-p-02)
→ No overlap. Safe to file all three concurrently.
```

---

## Communication management during a wave

A large wave generates significant communication volume. Wave 1 of mir-swarm
produced ~200 mail items, ~75 commits across 7 repos, and ~50 verdicts over
~55 active cycles. Managing this without drowning requires discipline.

### The three communication channels

| Channel | What it carries | Mind action |
| --- | --- | --- |
| Sub-agent completion notification | "I'm done" signal | Read output, verify, route |
| Vivi mail (To mind) | Verdicts, reports, findings | Absorb after processing |
| Git commits | The actual work | Verify scope, accept or audit |

### Processing a completion

When a sub-agent completes, process in this order:

1. **Read the sub-agent output** (the short pointer)
2. **Verify the commit** — `git show <sha> --stat`, check scope
3. **Classify** — is this an accept-on-evidence, needs-audit, or block?
4. **Route** — file auditor task if needed; file next unit to the freed Hand
5. **Absorb the mail** — `vivi mail absorb <handle> --for mind`

Never absorb mail before processing the completion. The mail is the durable
record; the sub-agent output is the working signal.

### Absorbing mail

Mail accumulates fast during dense cycles. Absorb promptly to keep the inbox
clean:

```bash
# Per-item (when reading verdicts)
vivi mail absorb <handle> --for mind --project <root>

# Bulk (for stale notifications already processed inline)
vivi mail list --for mind --project <root> | grep "absorbed=false" | awk '{print $1}' | while read h; do
  vivi mail absorb "$h" --for mind --project <root>
done
```

**When to bulk-absorb:** after processing completions inline (the mail items
are stale confirmations of what you already handled). **When not to
bulk-absorb:** when you haven't read the verdict yet — always read before
absorbing.

### Duplicate completion notifications

Sub-agent completion notifications can arrive multiple times for the same
unit (harness re-delivery). Track what you've already processed:

```text
hand-5 landed d-spine-01 S1 (aead2be51). Filed auditor-1 review.
→ Later notification for same sub-agent_id = duplicate. No action.
```

The git commit SHA is the authoritative signal. If you've seen the SHA, the
unit is processed regardless of how many notifications arrive.

---

## Churn management

Churn is the enemy of a long wave. Every unnecessary context switch, redundant
verification, or duplicate processing burns Mind context that should go to
routing decisions.

### Source 1: Block_ship repair cycles

**Pattern:** auditor block_ship → repair filed → repair lands → re-audit →
possibly another block_ship → repair again.

**Management:**
- After a block_ship, read the auditor report fully before filing repair
- Include the specific findings + fix directions in the repair task body
- For systemic patterns (e.g., dead code, test exclusion), check sibling units
  from the same Hand for the same risk before they land
- Verify compile claims independently (`cargo build` in Mind shell) before
  filing re-audit — a false build claim wastes an audit cycle

**Block_ship chain example:**
```text
d-a-03 U1 original → block_ship (UB FFI)
  → 1st repair → block_ship (E0502 borrow conflict, lib doesn't compile)
    → 2nd repair → clean_pass
```

Three audit cycles on one unit. The 2nd block_ship was preventable: the Mind
should have run `cargo build` before filing re-audit.

### Source 2: Stale mail accumulation

**Pattern:** during dense cycles, 10-20 mail items accumulate between
absorption passes.

**Management:**
- Absorb after each completion processing (not at end of cycle)
- Bulk-absorb stale items at cycle start if count > 10
- Never let inbox exceed ~50 unabsorbed items

### Source 3: Write-scope serialization

**Pattern:** two units need the same file; one must wait.

**Management:**
- Track active write scopes in a mental table (or baseline field)
- When a Hand completes, immediately check if its freed scope unblocks a
  waiting unit
- File the unblocked unit same-turn, not next cycle

### Source 4: Planner spec commit failures

**Pattern:** `git commit --only` rejects untracked files (new delivery specs).
Planner creates the file, reports done, but the commit silently fails.

**Management:**
- Add `git add <file>` before `git commit --only` in planner spawn prompts
- After planner completion, verify the commit exists with `git log --oneline -1`
- If uncommitted, Mind commits the spec under the planner's identity

### Source 5: Auditor availability gating

**Pattern:** both auditors busy with spine units; leaf units pile up unaudited.

**Management:**
- Track audit sampling rotation per family (spine: always; leaf: every 3rd;
  exempla: 1/batch; HV: every 4th)
- When both auditors are busy, queue the audit (don't accept on Hand evidence
  alone for units above sample threshold)
- Prioritize auditor tasks by risk: spine > A-rail > leaf > test-only

---

## Task body quality

The task body is the Hand's only instruction. A vague task body produces
scope creep, missed requirements, and block_ships. A precise task body
produces clean units.

### Required fields in every Hand task body

```text
Unit: <delivery-id> Stage <N> (<rail>, <model class>)
Delivery spec: <path> (read <section> section in FULL)
Campaign: <path> (<goal-id>)
Depends on: <prior stage commit or "none">

DONE-WHEN:
- <numbered criteria from the delivery spec>

WRITE SCOPE (<scope type>):
- <exact file paths>

FORBIDDEN:
- <files the Hand must not touch>

VALIDATION: <cargo test commands>

BRANCH: main (<repo>)
MODEL CLASS: <mechanical|judgement>
AUDIT: <always|sample|deferred>

Read hand-protocol.md: /path/to/hand-protocol.md
Report done via vivi task done + vivi mail send To mind.
```

### Include the P3 audit corrections

If the delivery spec has a "P3 audit corrections" section, cite it in the
task body. These are hot-file or write-scope gaps that the delivery audit
caught. The Hand needs to know about them before starting.

### Include block_ship context for repairs

When filing a repair task, include:
- The specific auditor findings (not just "fix auditor report")
- The fix direction from the auditor
- The write scope (same as original)
- **Verify compile claims independently** before filing re-audit

---

## Cycle pacing during a wave

### Active wave (Phase 3)

- Cadence: **15m** (base for sub-agent fleets during active execution)
- Every cycle: absorb mail, check for completions, route verdicts, file next
  units
- The scheduler is the backup; sub-agent completions are the primary driver
- Tighten to 5-10m if multiple completions pile up

### Freeze (Phase 4)

- Cadence: **15m** (short — freeze agents in flight)
- Process: wait for rescore + Head samples, then present to operator

### Post-wave idle (Phase 5 waiting for operator)

- Cadence: lengthen per quiet_streak table
- quiet_streak 3 → 30m; quiet_streak 7 → 1h; quiet_streak 11+ → consider
  stopping scheduler

### Operator re-engagement

- Reset cadence to base (15m) when operator speaks
- Switch from autonomous to interactive mode
- Cancel the idle scheduler; arm a new one when work is delegated

---

## Spawn prompt essentials

Every sub-agent spawn prompt must include:

```text
You are fleet role <name> (<class>, <model>@<thinking>).

Read your role protocol before acting:
  <absolute path to protocol>

Load your charter:
  vivi role charter show <name> --project <root>

Load your task:
  vivi task show <handle> --project <root>
  (run vivi task list --for <name> --project <root> first if handle unknown)

Register pid:
  vivi role set <name> --pid $$ --project <root>

Project root: <root>
Assignment: <one-line description>

<task body or pointer to task>

IMPORTANT COMMIT NOTE: New files must be git add-ed BEFORE committing:
  git add <file>
  git <identity> commit --only -m '...' -- <file>

When done:
  vivi task done <handle> --for <name> --note '<evidence>' --project <root>
  vivi mail send --from <name> --to mind --subject 'Re: <subject>' --body '<findings>' --project <root>
  vivi role set <name> --clear-pid --project <root>

For long bodies use --body-file <path>; do not pipe stdin.
Run one vivi command per shell call.

Commit identity:
  git -c user.name="<model-slug>" -c user.email="<name>@<mailspace>" commit --only -m '...' -- <pathspec>

Return only a short pointer.
```

### Key spawn prompt rules

- **Name the protocol**: the sub-agent must read its role protocol before
  acting. State the absolute path.
- **Include the task handle**: the sub-agent loads its own task from Vivi.
  If the handle is unknown, instruct it to `vivi task list --for <name>`.
- **git add for new files**: always include the commit note for new files.
  This prevents the `--only` untracked-file gotcha.
- **Model slug in commit identity**: `user.name` is the model slug
  (`deepseek-v4-flash`, `glm-5.2`), not the role handle. This makes
  `git log --author=<model>` pull exactly one tier's output.
- **Short pointer return**: the sub-agent returns only a short pointer
  ("Done. Commit `<sha>`. Mail `<handle>`."). The detailed report lives in
  Vivi.

---

## Wave freeze (mandatory)

The freeze is a formal gate between waves. It is **not optional**, even when
all units are already accepted.

### Freeze sequence

1. **Declare freeze** in baseline. No new Hand units filed.
2. **Hands complete current units.** No new assignments.
3. **Auditors finish pending reviews.**
4. **Mind accept pass.** Accept clean units; route residuals.
5. **Heads sample wave tip.** File head-cto (architecture) and head-cxo
   (complexity) samples on the aggregate wave diff. Advisory only — do not
   block unfreeze.
6. **Lock ledger rescore.** File a doc Hand to update `lock-levels.md` with
   evidence from wave commits. Every changed row cites its evidence commit(s).
7. **Operator review.** Present rescored locks + Head findings. Operator
   decides unfreeze.

### What the freeze provides that per-unit audits cannot

- **Aggregate architecture review**: do the spine design docs form a
  consistent law set? Do any units contradict each other?
- **Pattern analysis**: block_ship patterns (e.g., "dead code + test
  exclusion" recurring) reveal systemic issues
- **Evidence-based lock rescore**: chat estimates are not sufficient — the
  rescore ties percentages to specific commits
- **Clean breakpoint**: the operator gets a moment to review before the next
  wave starts

---

## Operational lessons (from Wave 1 of mir-swarm)

These are concrete lessons from a 3-hour, 13-goal, 41-unit wave. They are not
universal rules — they are patterns that recurred.

### After a systemic block_ship, check siblings

When a block_ship reveals a systemic pattern (e.g., "correct math but missing
integration"), scan all in-flight and pending units from the same Hand for the
same risk. Add explicit verification criteria to their task bodies.

**Example:** d-a-02 S4 block_ship (prove_reduction_companion zero callers)
should have triggered a check on d-a-02 S5 (prove_matmul_companion). It
didn't — S5 landed with the identical defect.

### Verify compile claims independently

For any Hand claiming "cargo build passes" or "N/N tests pass", run the
command in the Mind's own shell before filing re-audit. Takes seconds, prevents
false-assurance cycles.

### Track what you've already processed

Sub-agent completion notifications can duplicate. Git commit SHAs are
authoritative. If you've seen the SHA, the unit is processed — ignore further
notifications for the same sub-agent ID.

### File the next unit immediately on Hand free

When a Hand completes and its write scope frees up, file the next unit from
READY inventory **same turn**, not next cycle. Idle Hands during active waves
is lost throughput.

### Use the right model class

- **Volume Hands** (`deepseek-v4-flash`): mechanical units (match arms,
  metadata, test additions, doc edits)
- **Judgement Hands** (`deepseek-v4-pro`): design docs, autograd VJPs, AIR
  proofs, multi-file stacks
- **Planners** (`deepseek-v4-pro`): goal-forge, delivery lowering
- **Auditors** (`glm-5.2`): independent adversarial review

Filing a judgement unit to a volume Hand produces block_ships. Filing a
mechanical unit to a judgement Hand wastes scarce capacity.

### Don't over-file during the launch burst

At wave launch, file 4-6 concurrent Hands (not 12). Let the first wave of
completions arrive before filing more. This keeps the Mind's context
manageable and prevents write-scope collisions from cascading.

---

## Post-wave cleanup (mandatory)

After the freeze completes and the operator reviews, run a cleanup cycle
before the next wave begins. This prevents transient state from accumulating
across waves and keeps the board, mail, and memory surfaces honest.

### Cleanup checklist

Run each item across **all roles** (mind, heads, planners, auditors, hands):

| Surface | What to clean | How |
| --- | --- | --- |
| **Memos** | Retire transient status/cycle-dispatch. Keep only durable law, policy, capacity, and milestone memos that would matter after a cold boot. | `vivi memo list --for <role>` → review → `vivi memo delete <handle> --for <role>` for each transient one |
| **Tasks** | Close any stale tasks (completed but not marked done, obsolete, or superseded). | `vivi task list --for <role>` → `vivi task done <handle> --for <role> --note 'stale: <reason>'` |
| **Needs** | Review open needs — close resolved ones, keep genuine open decisions. | `vivi need list --for <role>` → close or keep |
| **Wants** | Close resolved residuals and obsolete items. Keep genuine follow-ups. | `vivi want list --for <role>` → `vivi want done <handle> --for <role> --note 'resolved: <reason>'` |
| **Mail** | Absorb all unabsorbed mail across every role. | `vivi mail list --for <role>` → bulk absorb everything `absorbed=false` |

### Memo retention test

A memo earns its place only if **both** tests pass:

1. Would losing this across a cold boot cause a worse decision?
2. Can it be recovered from a Vivi handle, git history, or a document instead?

If yes to #2, it belongs in a document or compaction pointer — not a memo.
Transient routing state (cycle dispatch, per-commit status, Hand progress,
audit results) is **loop state**, not memory.

Typical memo survivors after cleanup: 5-10 durable items (law, policy,
capacity bindings, campaign milestones, operator mandates).

### Bulk mail absorption

During a dense wave, mail accumulates across all roles — not just Mind. A
3-hour wave with 12 concurrent agents can produce 300+ mail items. Bulk-absorb
at cleanup time:

```bash
for role in mind head-ceo head-cto head-cxo head-cso head-cmo head-cpo \
            planner-1 planner-2 auditor-1 auditor-2 \
            hand-1 hand-2 hand-3 hand-4 hand-5 hand-6; do
  vivi mail list --for "$role" --project <root> | grep "absorbed=false" | awk '{print $1}' | while read h; do
    vivi mail absorb "$h" --for "$role" --project <root>
  done
done
```

### When to run cleanup

- **Always** after wave freeze + operator review (before next wave launch)
- **Optionally** during long idle periods (quiet_streak 5+) if mail has
  accumulated
- **Never** during active execution — cleanup mid-wave risks absorbing
  verdicts before processing them

---

## Related references

| Reference | Covers |
| --- | --- |
| [`subagent.md`](subagent.md) | Sub-agent backend mechanics (spawn, completion, partial-commit) |
| [`mind-cycle.md`](mind-cycle.md) | Per-cycle operations (sensors, dispositions, absorb/accept) |
| [`lowering.md`](lowering.md) | Planner pipeline (goal-forge → delivery) |
| [`model-selection.md`](model-selection.md) | Model class routing by unit shape |
| [`multi-lane.md`](multi-lane.md) | Branch integration, write-scope non-overlap, lane lifecycle |
| [`tasking.md`](tasking.md) | Board kinds, multi-hand routing, stale task disposition |
