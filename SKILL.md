---
name: fleet
description: Multi-agent fleet management with Mind/Head/Hand roles (Abbot pattern) — Mind (ops) fills tasking, Hands (workers) clear work, Heads (advisors) research; Hands share Mind harness, Heads prefer alternate models/harnesses; dual-channel Vivi+tmux, multi-lane integration, runtime fallback, wind-down. Use for hunter-N fleets, codex reinit, keep-screen-moving, don't-get-stuck, long unattended Mind cycles.
---

# Fleet

**Roles follow Abbot’s Mind / Head / Hand pattern** (see `~/work/ianzepp/abbot/README.md`: agent layer as roles under one control plane). This skill applies that pattern to a **multi-session fleet** (mail board + tmux panes), not Abbot’s in-process kernel.

| Role | Job | Typical callsign |
| --- | --- | --- |
| **Mind** | Ops / control loop: tasking, review, integrate, pane ops, cycle cadence | `reviewer` |
| **Head** | Advisory cognition: strategist, correctness, purity — research and reports, not bag drain | same as role name |
| **Hand** | Execution: take one open target, implement, validate, mark done | `hunter-1`…`hunter-N` |

Callsigns (`hunter-N`, `reviewer`) are **mail/tmux identities**. Skill vocabulary is Mind / Head / Hand.

**Evolution:** formerly `$hunter-gatherer`. Canonical skill name is **`$fleet`**.

**Invariant:** Mind fills the tasking bag; Hand empties it. Progress is **open tasking + campaign/map**, not approval stamps.

**Keep the screen moving:** empty tasking while the map still has unblocked next work is **starvation**, not success. Operational pause is the exception.

**Don't get stuck:** freeze is the failure mode. Name why, get unstuck — never status-only “blocked” for cycles without evidence.

**Harness alignment:** Hands run the **same agent harness as Mind**. Heads **prefer alternate harnesses/models**.

```text
campaign / focus map
        │
        ▼
   MIND ──files targets──► tasking bag (open tasks / needs)
        ▲                           │
        │                           ▼
        └──── residuals ────── HAND clears selected target
                 ▲
                 │ dual channel
        Vivi (truth of work) + tmux (truth of process)

   Heads (strategist / correctness / purity) ──mail To: Mind──► triage into tasking
```

## When To Use

- Project-local multi-agent loops (often Vivi mailspace identities)
- Factory/campaign work with a residual finder and an implementer
- Long recurring agent wakes (5–10m) that must **fail fast** when idle
- Reframing “reviewer approval” into residual tasks instead of stage licenses
- Fleet of Hand sessions bound to tmux panes (liveness + doorbell)

Do not use for ordinary personal IMAP email (`$mail`). Do not invent a second acceptance gate.

## References

Load only what the current turn needs. Core law lives in this file; detail lives in `references/`.

| Reference | Load when |
| --- | --- |
| [`roles-and-harness.md`](references/roles-and-harness.md) | Arming fleet, rebinding runtimes, Mind/Hand/Head duties, preferred models, Pi-as-Hand |
| [`tasking.md`](references/tasking.md) | Filing targets, queue kind vs severity, multi-hand routing, starvation, Hand decision continuity |
| [`dual-channel.md`](references/dual-channel.md) | Pane scan/classes, doorbell, Codex reinit, rehome, `/compact`, completion / ready-to-merge mail |
| [`mind-cycle.md`](references/mind-cycle.md) | Fail-fast wake, cycle kinds, sensors, proactive review, absorb vs accept, review debt, merge tasks |
| [`multi-lane.md`](references/multi-lane.md) | Side lanes, theme→main, base-update, pin-relative done, `pending_merges` |
| [`heads.md`](references/heads.md) | Strategist / correctness / purity loops |
| [`runtime-config.md`](references/runtime-config.md) | Capacity ladders, Codex reinit scripts, fleet/baseline schemas, wind-down / rearm |

## Don't get stuck (universal law)

**Basic rule:** do not freeze. Progress on a second-best target beats zero progress while “waiting.” Internal hesitation is not a board event — other agents and the operator only see Vivi, commits, and the pane.

### When stuck — same turn

```text
1. Name it     path / handle / dirt / pane class / missing decision
2. Why         unsent decision · unclassified dirt · integration lag ·
               topic monogamy · dead process · capacity · real upstream wall
3. Unstick     match the class below — do not only restate “blocked”
4. Pivot       if one item stays blocked, work other open tasking/map targets NOW
```

| Stuck class | Unstick (do) | Don't |
| --- | --- | --- |
| Decision / name / scope / stop condition | File **need or mail** same turn with **default + options**; keep working or pivot | Silent wait for confirmation never sent |
| One tasking item awkward / deferred | Externalize if needed → **switch targets** | Topic monogamy while other targets exist |
| Uncommitted dirt on a path you need | **Open the diff** → classify A/B/C → act | Status-only “foreign dirty → leave forever” |
| Integration lag (fix not on pin/main) | Queue merge / base-update / pin-refresh; pivot product | Thrash re-verify on correctly blocked consumer |
| Pane dead / capacity / stuck idle + open tasking | Wake / reinit / runtime fallback by fleet | Stack wakes; hope without ops |
| Hard human-only wall | Need filed + pivot other targets | Silent stall of the whole session |

**Only sleep** when the actionable bag for the focus is empty **and** the map has no next unblocked unit — not because one item is awkward.

**Forbidden:** sitting idle for confirmation never filed; treating filename uncertainty as a hard stop; parking the session on one uncertain item while other open tasking remains; assuming Mind/operator will poll private monologue; repeating “dirty / blocked” across cycles without new evidence.

### Half-dead targets (dirt that rots)

Uncommitted changes that **block** a selected unit are **half-dead targets**, not a permanent stop sign. They rot if status-only sensors keep saying “dirty” while no agent opens the diff.

**Invariant:** “foreign dirty” means **do not erase**. It does **not** mean “never look, never classify, freeze the spine for hours.”

| Class | What it usually is | Same-turn action |
| --- | --- | --- |
| **A — mechanical** | Formatter / pure layout after `git diff` (no semantic intent) | Style-commit in scope, or include with related work per formatter law. Not live multi-agent WIP. |
| **B — intentional other** | Another agent’s semantic WIP, docs/factory goals, deliberate partial | Work around, narrow scope, worktree, or escalate via Vivi. **Do not erase.** Record owner/guess + age. |
| **C — mixed** | Some hunks yours, some not | Stage/commit **only own safe hunks** when possible; leave the rest; continue other targets. |

```text
git status -sb
git diff -- <path>          # or git diff -U0 for size
# pure whitespace/layout after a landed commit → usually class A
# real logic/docs mid-edit by another pane → class B
```

| Role | Dirt duty |
| --- | --- |
| **Hand** | Classify A/B/C before abandoning a unit for dirt. A → clear or style-commit. B → need/mail + **pivot**. C → own hunks only. Never destructive cleanup of B. |
| **Mind** | Same paths block spine/packet for **≥2 cycles** with no classification → **open the diff**, note class, file claim/quarantine need or style residual. Track `half_dead` age; escalate, don’t restate. |
| **Either** | Second-best map targets while dirt is B-held is success. Zero commits “waiting on dirt” while other targets exist is failure. |

Formatter law (global Agents.md): after inspect, formatter output is intentional change to commit, not noise to freeze on.

## Roles (summary)

| Role | Job | Does not |
| --- | --- | --- |
| **Hand** | Drain own open tasks/needs; validate; mark done; polish unit sources | Wait for GO mail; merge packet→main (hunter-2+); erase foreign WIP |
| **Mind** | File targets; review; integrate; pane ops; refill starvation | Stage GO/NO-GO; steal Hand unit mid-flight; freeze on status-only dirty |
| **Head** | Report To Mind (sequencing / bugs / complexity) | Own product tasking; merge; stamp accept |

Identity ≠ assignment ≠ runtime. Hand harness follows Mind; Heads prefer alternate runtimes. Detail: [`roles-and-harness.md`](references/roles-and-harness.md).

## The tasking bag (summary)

| Kind | Use for |
| --- | --- |
| **task** | Implementable work with done-when (including critical defects) |
| **need** | Decision / authority / external input — include default + options |
| **want** | Non-blocking polish / later idea |
| **mail** | Deliberation — not the primary queue |

**Queue kind is not severity.** Urgency lives in subject/priority, not by misfiling defects as needs.

Hard stop: open tasks/needs for the current hunt.  
Not a hard stop: missing Mind “GO” mail.

**hunter-1** = main checkout, merges to main. **hunter-2+** = packet assignments, never merge to main; unit → refill; theme → ready-to-merge.

Empty product bags + map still has unblocked next work = **starvation** (file + wake same cycle). Detail: [`tasking.md`](references/tasking.md).

## Dual channel (summary)

Vivi = truth of work. tmux = truth of process. **Mail identity == tmux session name.**

| Pane class | Typical Mind action |
| --- | --- |
| `running` | Do not wake/reinit |
| `idle_prompt` + open tasking + **Grok** | Pointer doorbell |
| `idle_prompt`/`done_idle` + open tasking + **Codex** | **Reinit** (not stacked wakes) |
| empty + map next | Starvation — file then wake/reinit |
| `error_*` / `down` | Ops intervene / recreate |

tmux carries **pointers only**; full done-when lives in Vivi. Detail: [`dual-channel.md`](references/dual-channel.md).

## Lifecycle

### 1. Arm

- Bag exists (mailspace identities or equivalent)
- Hand and Mind share project root and map (campaign/GOAL)
- Record Mind’s harness; bind every Hand’s `agent` / `wake_mode` / reinit to it
- Apply preferred models (see `roles-and-harness.md`)
- Tiny role baselines: `last_cycle`, `quiet_streak`, fingerprints, pane classes

### 2. Select focus

- Campaign/map names current stage or package
- Hand selects one open target (oldest, priority, or map order)
- Do not wait for Mind stamp to start a selected map package

### 3. Gather

- Sensors: bag + HEADs/dirty + pane classes
- Paid path: scan what **moved**; file residuals to owning Hand
- Quiet when fingerprint and pane classes unchanged (or only `running`)
- Idle+open tasking or error class: wake or ops intervene

### 4. Work (Hand)

- `show` one target; implement; validate
- **End-of-unit polish** on changed product source from this unit (`$polish`)
- Mark done with evidence; absorb Status into campaign/docs when criteria hold
- Next target from bag, or next map package, or sleep (idle at prompt OK if Mind doorbell is armed)

### End-of-unit polish (Hand)

After each product unit that touches implementation source, run `$polish` **before** tasking done / turn-end, scoped to this unit:

```text
implement + targeted validate
  → list primary source files changed by THIS unit
  → $polish those files only (serial per-file)
  → then tasking done + turn-end (+ ready-to-merge if packet)
```

| Do | Don't |
| --- | --- |
| Target **primary source** this unit created or substantially edited | Repo-wide polish “while here” |
| Include only **directly related** tests/docs as `$polish` allows | Polish foreign dirty / other agents’ WIP |
| Prefer product source over pure Status/docs-only deltas | Force polish commits when inspect finds no useful change |

Skip only when the unit was docs-only / Status-only / merge-only, or operator waives. Packet workers polish **inside the packet worktree** before ready-to-merge. Mind does **not** run polish for the Hand.

### 5. Sleep / wake / backoff

See [`mind-cycle.md`](references/mind-cycle.md). Most wakes should be no-ops.

### 6. Retire

- Empty tasking + no next map package → stop loop or long backoff
- Operator may stop schedulers when camp is idle for hours
- Wind-down procedure: [`runtime-config.md`](references/runtime-config.md)

## Fail-fast wake (summary)

Most 5–10m wakes must **exit in seconds**. Cheap sensors first; sleep when fingerprint, HEADs/dirty, and panes are unchanged and no starvation/error/open-tasking wake is required.

When the cycle **acted**: scannable headline + fleet snapshot + board moves + pending debt. Use **absorb** (bookkeeping) vs **accept** (post-review quality bar) accurately.

Detail: [`mind-cycle.md`](references/mind-cycle.md). Multi-lane / theme merge / base-update: [`multi-lane.md`](references/multi-lane.md).

## Multi-agent shared workspace

Multiple agents often share one branch/worktree. Two laws hold at once:

1. **Do not erase** uncommitted work outside your allowed scope.
2. **Do not freeze** on unclassified dirt that blocks progress.

### Never (destructive)

- `stash` / `reset` / `restore` / `clean` / force-push to “make room”
- Polish or rewrite another hunter’s mid-flight semantic WIP
- Overwrite foreign paths with write tools just because the tree looks messy

### Always (when dirt blocks you)

```text
list paths → open diff → class A / B / C → act or pivot same turn
```

On unexpected dirt **outside** scope: do not erase — list, classify if blocking, work around or escalate. Sub-agents escalate to parent; parent escalates true ambiguity to the operator **after** filing a need with a default.

## Project overlay contract

**This skill is the portable process.** Camp files bind instances and may add product law. They must not redefine bag-vs-gate, absorb-vs-accept, don't-get-stuck, or **Harness alignment** (Hands = Mind harness).

| Lives in skill | Lives in project overlay |
| --- | --- |
| Roles, bag rules, dual channel, fleet axes | Concrete Hand roster, cwds, model ids |
| Harness alignment + preferred models | Live `mind.agent` / `agent_model` / `agent_launch`; Head Pi launches |
| Theme vs unit, merge clock, base-update *policy* | Campaign maps, product Status, validation commands |
| Head loops, cycle kinds, runtime fallback *structure* | Role-prompt paths, absolute tool binaries |
| Baseline *field meanings* and `pending_merges` states | Fat historical ledger rows, wind-up snapshots |
| Pane classes, reinit contract, wind-down procedure | Scheduler prompt path, durable 5m task id |

Typical camp file kinds (names/layout camp-local):

```text
fleet config           # roster + runtime + tooling + preferred models
Mind cycle baseline    # sensors + debt + advisor state
Mind scheduler overlay # thin camp process prompt
Head role prompts      # strategist / correctness / purity
reinit helper (opt.)   # Codex (or other) reinit doctor/heal
project Agents.md      # product + multi-agent law
```

Schema detail: [`runtime-config.md`](references/runtime-config.md).

## Anti-patterns (compact)

### Bag and gates

- Mind as game warden (stage licenses, GO/NO-GO) or blocking a Hand on missing GO with no residual
- Encoding severity as queue kind (implementable merge blocker filed as `need`)
- Sleeping with empty product tasking while the map has unblocked next work
- Filing to retired identities when `hunter-N` is default; packet merges / unbounded spine on hunter-2+
- Heads owning product tasking or merge queues; thrashing strategist assign while a report is outstanding

### Dual channel and process

- Relying on completion mail or idle pane alone
- Policy essays through tmux
- Mixed Hand harness under one Mind without explicit temporary exception
- Forcing Heads onto Mind’s harness “for uniformity”
- Stacking Codex `HAND WAKE` lines instead of reinit; `exec codex` / fragile `exec grok`
- Packet Hand with cwd still on main; unquoted `--deny` globs in zsh

### Integration and honesty

- Packet-green as consumer-green without pin ancestry
- “Compiler residual” when the class is integration lag
- Theme merge that creates durable red main
- Interrupting dirty hunter-1 for a merge; Mind merging packets; skipping watch-scope drift
- Accepting “complete” when evidence is static/manual but claim is product-run, without saying so
- Writing “absorb” when you mean **accept**

### Hygiene and multi-agent workspace

- Combining `/compact` with assignment, or new Grok session for every theme when compact would suffice
- Skipping end-of-unit polish, or polishing foreign dirty
- Destructive git cleanup of unexpected dirt
- Status-only dirt freeze without A/B/C classification
- Treating class A (fmt/layout) as permanent foreign WIP
- Topic monogamy under blockage; silent wait for confirmation never filed
- Dumping or deeply inspecting every wake while bag/trees/panes unchanged

## Related skills

- `$mail` — Vivi project mailspace CLI (task/need/want/mail); not the process
- `$polish` — end-of-unit per-file improvement on **this unit’s** changed primary source
- `$correctness` — behavioral bug / invariant audits (advisor or Hand tool)
- `$cleanliness` — structure/complexity scans (pairs with purity-style work)
- `$factory` — multi-phase implementation when the Hand executes a large unit
- `$campaign` / `$delivery` — map and delivery packages the Hand drains
- `$executive-team` — broader role cast; fleet is the tasking bag-loop subset
