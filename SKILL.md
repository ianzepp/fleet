---
name: fleet
description: Multi-agent fleet management with Mind/Head/Hand roles (Abbot pattern) — Mind session attaches to one or more fleets; Hands/Heads via sub-agents (default), tmux, or vivi-pty; Vivi board as work truth; event-driven or polling completion; multi-fleet FLEET_CYCLE.
---

# Fleet

**Official source:** [https://github.com/ianzepp/fleet](https://github.com/ianzepp/fleet) — clone or pull from there for updates; do not treat monorepo skill mirrors as canonical.

Abbot **Mind / Head / Hand** roles on a **multi-session fleet** (Vivi board + execution runtime), not an in-process kernel.

| Role | Job | Identity |
| --- | --- | --- |
| **Mind** | Tasking, integrate, cycles | Operator TUI + board **`mind@…`** (no external runtime) |
| **Operator mail** | Human escalations | Board **`operator@…`** (no external runtime) |
| **Head** | Advise / report on cadence — not bag drain | **`head-ceo` / `head-cto` / `head-cxo`** (+ optional org Heads). Carries cadence |
| **Planner** | Goal-forge and delivery lowering | **`planner-1`…`planner-N`** (Hands with planning duty; **`$campaign`** + **`$delivery`**; mid-tier) |
| **Hand** | Execute work (implement only) | **`hand-1`…`hand-N`** (product implementers; all Hands are equivalent floaters; low-tier) |
| **Auditor** | Review completed work | **`auditor-1` / `auditor-2`** (Hands with review duty; **`$auditor`**; high-tier) |

## Execution model

Fleet Hands and Heads run via one of three execution backends:

| Backend | Completion | Use | Reference |
| --- | --- | --- | --- |
| **Sub-agent** (default) | Event-driven | Harness supports spawning; parallel work; advisory Heads | [`subagent.md`](references/subagent.md) |
| **tmux** | Polled | Persistent interactive sessions; harness lacks sub-agents; remote SSH | [`tmux.md`](references/tmux.md) |
| **vivi-pty** | Polled | Structured PTY sessions without tmux | [`vivi-pty.md`](references/vivi-pty.md) |

**Sub-agent is the default** for harnesses that support it (Grok Build, Codex, etc.) — completion notifications drive the Mind; no polling or pane management. Capacity (provider/model/thinking) and charter live on the Vivi role record; boot and report are backend-neutral — see [Role communication contract](#role-communication-contract).

## Role communication contract

Every Hand and Head session — regardless of backend — follows one boot and report shape. The Vivi role record is the single source for identity, capacity, and charter; the Vivi board is the single source for work and results.

### Boot

The parent delivers a thin pointer. The role loads its own context from Vivi.

```text
You are fleet role <name>.
Read your role protocol:  mind-protocol.md | planner-protocol.md | hand-protocol.md | auditor-protocol.md | head-protocol.md
Load charter:  vivi role charter show <name> --project <root>
Load task:     vivi task show <handle> --project <root>
Register pid:  vivi role set <name> --pid $$ --project <root>
Optional bag:  vivi board --for <name> --project <root> --json

Execute per charter and protocol. File results with the literal commands below (do not paraphrase flags).
  vivi task done <handle> --for <name> --note '<evidence>' --project <root>
  vivi mail send --from <name> --to mind --subject '<subject>' --body '<body>' --project <root>
  vivi role set <name> --clear-pid --project <root>
For long bodies use --body-file <path>; do not pipe stdin.
Run one vivi command per shell call. Run `vivi <sub> --help` first if unsure of flags.
Return only a short pointer.
```

### Report

Before returning, the role files results through Vivi and clears its process binding:

```bash
vivi task done <handle> --for <name> --note '<evidence: what changed, why, residuals>'
vivi mail send --from <name>@<mailspace> --to mind@<mailspace> \
  --subject 'Re: <task subject>' --body '<durable findings>'
vivi role set <name> --clear-pid --project <root>
```

| Flag | Semantics |
| --- | --- |
| `--for <name>` (task done) | The **assignee** completing the task, not the sender. Same identity axis as `task list --for` and `board --for`. |
| `--from <name>` (mail send) | The **sender** role. Required; not inferred from charter or pid binding. |
| `--body` / `--body-file` | Use `--body-file <path>` for long bodies (auditor reports, multi-section findings). Do not pipe stdin. |

Returns to parent: short pointer only.

```text
Done. Commit <sha>. Mail <handle> has the full report.
```

Detailed report lives in Vivi for audit; parent context stays lean.

### Backend delivery

Boot and report shapes are identical across backends. Only delivery differs.

| Backend | Boot pointer via | Completion by |
| --- | --- | --- |
| **Sub-agent** | Thin spawn prompt | Notification (event) |
| **tmux** | `tmux send-keys` | Pane classification (poll) |
| **vivi-pty** | `vivi-pty terminal write` | Session diagnostics (poll) |

Mechanics: [`subagent.md`](references/subagent.md), [`tmux.md`](references/tmux.md), [`vivi-pty.md`](references/vivi-pty.md).

## Commit authority and workflow

Hands commit their own work. The Hand has the diff context; re-deriving it in the Mind is waste. The Mind's job is review-after (sampling, auditor on risk), not commit-before.

### Standard delivery flow

```text
1. Operator + Mind   discuss feature scope
2. Mind              assigns goal-forge to planner-N
3. Planner           runs goal-forge → goal-check; reports READY To mind
4. Mind              reviews; queues goal or sends back with gaps
   ─── goal sits READY in queue ───
5. Mind              when execution imminent, assigns delivery lower to planner-N
6. Planner           runs $delivery → ordered unit graph; reports To mind
7. Mind              schedules units; files implement tasks to Hands
8. Hand              executes, commits on assigned branch, returns SHA + report
9. Mind              routes completed work to auditor-N
10. Auditor          reviews; reports To mind (clean_pass, residual, or block_ship)
11. Mind             files residuals to Hand as repair tasks (if any)
12. Hand             fixes, commits, reports back
13. Mind             routes to auditor for verification
14. Auditor          verifies pass
15. Mind             accepts; phase marked done
```

When execution is imminent and the operator is engaged, steps 2–6 collapse to one planner assignment (full pipeline). The planner self-checkpoints at goal-check READY and proceeds to delivery lowering without returning to the Mind.

The audit loop (steps 9–14) is the integration bar. `accept` means the audit loop passed, not that something is queued for merge.

### Branch strategy is a Mind decision

| Situation | Branch | Who creates |
| --- | --- | --- |
| Default | **Main** — Mind scopes to non-overlapping areas; commit lands directly | (no branch needed) |
| Large feature or overlap risk | **Feature branch** — Mind creates branch, assigns Hand to it | Mind |
| Isolated experiment or parallel work | **Worktree** at predetermined path — Mind sets up, hands path to Hand | Mind |

Most work lands on main because the Mind scopes non-overlapping work across repos/crates. Feature branches are the exception, not the default.

### Push

Push is the Mind's decision, not the Hand's default. The Mind knows per-repo deployment posture:

| Repo type | Push default |
| --- | --- |
| Railway-linked (auto-deploy) | **Do not push** without explicit Mind decision |
| Railway-linked (manual deploy) | Safe to push when Mind approves |
| No remote / local-only | Moot |

### Commit identity (model slug, not role)

Every role that commits does so under a git identity that records **which model** authored the change — not the role handle. `hand-1` vs `hand-2` is a scheduling accident (all Hands are equivalent floaters); the **model tier** is the real variable, and role capacity is mutable (a role can be capacity-stepped), so the model that actually authored a commit is otherwise unrecoverable from the role record later.

```bash
# role reads its own model from its Vivi record, then partial-commits its own scope:
MODEL=$(vivi role show <name> --project <root> | awk '/model:/{print $2}')
git add -- <own scope>
git -c user.name="$MODEL" -c user.email="<name>@<mailspace>" commit --only -m '…' -- <own scope>
```

`--only` with an explicit pathspec builds the commit from HEAD plus your paths, **disregarding anything else staged in the shared index** — so concurrent Hands on one working tree cannot capture each other's files. This is the shared-tree parallel-commit contract (see [`subagent.md`](references/subagent.md)); it removes the need for a worktree when write scopes are disjoint.

- **`user.name` = model slug** (`haiku`, `sonnet`, `deepseek-v4-flash`, `glm-5.2`). Makes `git shortlog -sn` read as capability contribution and `git log --author=<model>` pull exactly one tier's output — the audit-focus query the model-selection thesis wants (scrutinize cheap-tier work first).
- **`user.email` = `<role>@<mailspace>`** — keeps the role queryable and is the attribution key: a **product** commit authored with `mind@…` is drift no legitimate flow produces.
- **Per-commit `git -c`, not `git config --local`** — the default branch is shared `main`, and concurrent sub-agents on one worktree would race on local config; `-c` scopes the identity to that one invocation. (In an isolated worktree, `git config --local` at boot is equivalent.)
- Provider matters? Use `user.name="<provider>/<model>"`. Never put the role in `user.name` — keep `hand-N` noise out of the capability view.

### What does not exist anymore

- **`merges_to_main` field.** No per-Hand merge flag. Branch strategy is a Mind decision at assignment time.
- **`default_hand` field.** No dedicated integration Hand. All Hands are equivalent floaters.
- **`pending_merges` / fleet-level RTM tracking.** Feature-branch merges flow through ordinary task/need/mail. The Mind tracks branches it created.
- **hand-1 as integration lane.** Single-repo fleets that want one integration Hand configure that through assignment, not through a fleet-wide field.

## Prime directive: Mind owns liveness

A Mind is not a reporter. A Mind is not an implementer. A Mind is an air traffic controller: it directs traffic, it does not fly planes. When work needs doing, the Mind's default action is to **route it** — file a task to a Hand, assign a lower to a planner-N. The Mind does not write code, run factory, write tests, or do analysis, even when the work is small, obvious, or faster to do directly. A Mind that implements is a Mind that has stopped managing the fleet.

A Mind owns forward progress for every attached fleet: observe Vivi + runtime state, keep honest work moving, refill empty product capacity, route decisions, repair runtime capacity, and preserve human blockers until they are answered.

**A cycle is incomplete until every material sensor signal has a disposition.** Treat `fleet-sensors.py` `signals[]`, open operator mail, runtime failures, dirty blockers, idle Hands, Head reports, and board events as obligations — not trivia.

| Disposition | Meaning |
| --- | --- |
| `acted` | Fixed, filed, woke, spawned, absorbed, or presented this cycle |
| `delegated` | Converted to a concrete task/need/mail for the correct Hand/Head/Mind owner |
| `escalated` | Sent To `operator@` with default/options because human-only or unsafe to default |
| `deferred-valid` | Explicitly held by posture, operational pause, running agent, branch wait, or real dependency |
| `sleep-valid` | No material signals, no honest unblocked work, and posture permits quiet |

Reporting a blocker without acting, delegating, escalating, or recording a valid defer is a failed Mind cycle.

## Identity + binding

| Identity | Mail | Runtime | Notes |
| --- | --- | --- | --- |
| **mind** | `mind@…` | none | Board To: Mind; process = this chat |
| **operator** | `operator@…` | none | Human only — [`operator-mail.md`](references/operator-mail.md) |
| **steward** | optional opt-in | configured runtime | Dead-man, not Mind — **off by default**; operator must enable+arm per fleet — [`dead-man.md`](references/dead-man.md) |
| **planner-N** | `planner-N@…` | configured runtime | Goal-forge + delivery lowering; mid-tier model; `$campaign` + `$delivery` |
| **hand-N** | `hand-N@…` | configured runtime | Product implementers; low-tier model; all Hands are equivalent floaters |
| **auditor-N** | `auditor-N@…` | configured runtime | Review Hands; high-tier model; **`$auditor`**; no merge; report To mind |
| **head-*** | `head-*@…` | configured runtime | Advisory only on cadence or direct question; ceo=strategist; cto gate honesty / architecture; cxo purity; cso security; coo ops |

**Fleet** = project root + `.vivi/`.

### Standard helper scope

Every fleet helper uses the same scope vocabulary:

```text
--project/-p <project-root>   durable fleet project boundary; roster resolved from Vivi roles
--role <role>                 logical Hand/Head role (repeatable where selection needs it)
--runtime-target <target>     concrete runtime target override for the helper call
```

### Tokens (disambiguation)

| Token | Means | Not |
| --- | --- | --- |
| **`HEAD`** / "main tip" | Git commit pointer (`git rev-parse HEAD`) | Advisor role |
| **Head** / `head-*` | Advisor role (`head-ceo` / `head-cto` / `head-cxo`) | Git tip |
| **bag** | Open tasks+needs for an identity (Vivi) | Status essays |
| **map** | Campaign/factory plan of next packages | The bag itself |
| **unit** | One implementable package of work | Full theme |
| **theme** | Multi-unit delivery chunk | Single residual |
| **packet** | Branch-bound assignment (any Hand) | Main checkout |
| **RTM** | ready-to-merge (mail signal for branch work) | Done on main |
| **absorb** | Bookkeeping when something moved | Integration bar |
| **accept** | Audit loop passed; review debt cleared | absorb; auditor residual |
| **GO stamp** | Forbidden stage license / approval gate | Residual tasking |

Canon for absorb/accept: [`mind-cycle.md`](references/mind-cycle.md) § Absorb vs accept.

## Invariants

### Process structure

| Invariant | Rule |
| --- | --- |
| Process | Mind fills bag; Hand empties. Progress = open tasking + map — not GO stamps |
| Delegation | The Mind routes, not implements. See a task → file to a Hand. See a goal → assign lower to planner-N. See a bug → file to a Hand. Default action for any work = route it. Detail: [`mind-protocol.md`](references/mind-protocol.md) § Delegation principle |
| Hand equivalence | All Hands are equivalent floaters. The Mind picks any available Hand for each assignment. No Hand has a special integration role; there is no fleet-wide main in a multi-repo container. Single-repo fleets don't need a dedicated merger either — see [Commit authority and workflow](#commit-authority-and-workflow) |
| Lowering | **Campaign goal → planner-N lowers** (`$campaign` goal-forge → goal-check READY → `$delivery` docs) → Mind files Hands from those units. Hands do **not** lower raw goals via factory. Heads do **not** lower — they are advisory-only. — [`lowering.md`](references/lowering.md) |
| Commit authority | **Hands commit their own work.** The Hand has the diff context; re-deriving it in the Mind is waste. The Mind's job is review-after (sampling, auditor on risk), not commit-before. See [Commit authority and workflow](#commit-authority-and-workflow) |
| Branch strategy | **Branch and worktree decisions belong to the Mind.** Default is main (Mind scopes non-overlapping work). Feature branch is the exception, created by Mind when scope is large or overlap risk is real. Hands commit to whatever branch they're assigned. |
| Push authority | **Push is the Mind's decision.** Default off. The Mind knows per-repo deployment posture: Railway auto-deploy = do not push without explicit decision; Railway manual = safe when Mind approves; no remote = moot. |
| Role routing | All role mail routes **To mind**. Mind owns the spawn clock; direct peer mail dead-letters when the recipient isn't running. Mind answers from context, files to the correct role and spawns it, or escalates to `operator@` |

### Quality

| Invariant | Rule |
| --- | --- |
| Audit loop | The audit loop is the integration bar: implement → commit → auditor review → repair → verify → accept. `accept` means the loop passed, not that something is queued for merge. Green self-authored tests ≠ ready. |
| Charter sufficiency | The boot pattern fails if charters are thin. A charter must encode: who the seat is (role, lens, report style), process law that applies to every unit, report-back expectations, and non-goals. If cold-boot fails, extend the charter — do not rely on accumulated state. |
| Quality | Product Hands ship unit quality. **Code review** is a **Hand duty** on **`auditor-1` / `auditor-2`** — **not** head-cto by default. **Never** universal review on every completion |
| Campaign truth | `head-ceo` periodically audits campaign/factory status against Git, board, validation, release, and deploy evidence; Mind files bounded `$zombie-docs` repair when prose lies |

### Capacity and continuity

| Invariant | Rule |
| --- | --- |
| Starvation | Empty bag + **honest unblocked product unit on the map** → file+wake. Never invent polish/makework to fill bags |
| Growth refill | Sensors emit **`growth_refill_required`** + **`refill_hint.disposition=file_planner_lower`** when growth product Hand bags are empty. Treat as act-now: planner lower / refill |
| Growth liveness | In `growth`, an idle product Hand with no queued unit is **not** a quiet cycle: trigger an executive refill sweep immediately |
| Head backpressure | A Head that refuses or does not run is **`deferred-valid`**: record once in baseline, retry on cadence |
| Loop continuity | Before ending a turn with delegated work outstanding, ensure a Fleet loop is active to collect the result. Create one if absent; never create a duplicate — [`mind-cycle.md`](references/mind-cycle.md#adaptive-scheduled-cadence) |

### Operational

| Invariant | Rule |
| --- | --- |
| Mind memory | Memos carry rules and policy that must survive a **cold boot** — a brand-new session with no compaction history. Two tests, both must fail for a memo to be warranted: (1) would losing this across a cold boot cause a worse decision? (2) can it be recovered from a Vivi handle instead? If yes to the second, use a pointer in compaction — not a memo. Things tied to the current working arc (task status, hand progress, audit results) belong in compaction or the board, not memos. |
| Mind mail hygiene | Mail To mind is routing and triage, not memory. Read it, act on it, absorb it. Do not accumulate open mail as a backlog; do not self-address mail as a parking lot. Absorb marks mail read (the consume lifecycle) and is not a memory mechanism — durable context belongs in memo, working context belongs in compaction. On major inflection (campaign end, stage closeout), audit memos and retire ones that reference superseded architecture. |
| Wake on mail | Each Mind cycle is the debounce: new board mail addressed to a process role wakes that role when idle. Running agents are not interrupted |
| Posture | Per-fleet `growth` \| `standby` \| `dormant` — [`posture.md`](references/posture.md) |
| Assignment mode | Per Hand/Head `assignment_mode`: `new` \| `compact` \| `continue` \| `restart` — [`runtime-config.md`](references/runtime-config.md) |
| Cadence | Sub-agent fleets: **15–30m** backup loop (event-driven). tmux/PTY fleets: **3–5m** polling loop. Adapt per [`mind-cycle.md`](references/mind-cycle.md#event-driven-cadence-sub-agent-fleets) |
| Lane lifecycle | A bound idle Hand is investigated after the configured grace; Mind reconciles map/task/worktree truth before continue, park, cooldown, or release. Runtime release never implies worktree deletion |
| Multi-hand | Mind files/wakes on the assignment clock; head-ceo side-lane bucket (`effort`+`est_tokens`); Mind calibrates est vs actual |
| Hygiene | Mind never runs `$polish`/`$housekeeping` itself; never thrash polish for continuity |

### Safety

| Invariant | Rule |
| --- | --- |
| Stuck | Freeze fails — name, unstick, pivot. No status-only blocked cycles |
| Harness | **Default:** Hands share Mind's harness. Fleet config exceptions win — [`roles-and-harness.md`](references/roles-and-harness.md) |
| Models | **Mid-tier planner → low-tier implement → high-tier audit.** Planner runs goal-forge + delivery (mid). Hands run volume implement (low). Auditors run adversarial review (high). Volume implement only **after** planning lowering. Live strings on the Vivi role record. Process: [`model-selection.md`](references/model-selection.md) |

```text
map → MIND ─files→ bag → HAND clears target → residuals → MIND
       Vivi = work truth · runtime = process truth
Heads ─mail To mind→ triage · problems → operator@ · status → mind@ + recap
```

## When to use

Multi-agent project loops, factory/campaign residual+implementer, event-driven or polling fleet management. **Not** personal IMAP (`$mail`); not a second acceptance gate.

## Hard bans vs guidance

| Kind | Examples |
| --- | --- |
| **Hard ban** | Destructive git on foreign dirt; erase other WIP; `exec` that kills a runtime session |
| **Guidance** | Mode, harness alignment, head-ceo, absorb/accept, models |
| **Not a ban** | "Might break autonomous" — if operator engaged or default safe, **act** |

**Decide now:** reversible default → take it. Human-only → `operator@` need/mail (default+options) + pivot.

## Loading map

Core process here; detail in `references/` + `scripts/`.

| Session context | Required reading |
| --- | --- |
| **Cold attach** | This file → **role protocol** ([`mind-protocol.md`](references/mind-protocol.md), [`hand-protocol.md`](references/hand-protocol.md), or [`head-protocol.md`](references/head-protocol.md) for your role) → [`subagent.md`](references/subagent.md) (or [`tmux.md`](references/tmux.md) / [`vivi-pty.md`](references/vivi-pty.md) for those backends) → [`mind-cycle.md`](references/mind-cycle.md). Add [`getting-started.md`](references/getting-started.md) for attach, [`multi-fleet.md`](references/multi-fleet.md) before multi-fleet. |
| **Hot cycle** (state already in context) | This file alone if quiet; open a ref when that surface hits |
| **Arm / first Mind turn** | This file + your role protocol + refs for surfaces you will touch this turn |

### Role protocols (mandatory, checks-and-balances)

Each role has a compact mandatory-read protocol. It distills the rules from the reference library into a dense runbook (~100 lines) that the role must read before acting. Each protocol enforces not only its own role's rules but the rules other roles must follow — a Hand refuses an improperly scoped task; a Planner refuses to lower without a READY goal; an Auditor refuses a predetermined verdict; a Mind corrects its process when a refusal arrives rather than overriding it.

| Protocol | Who reads | What it enforces |
| --- | --- | --- |
| [`mind-protocol.md`](references/mind-protocol.md) | Mind | Delegation principle, lowering bar, tasking kinds, assignment rules, commit/push/merge authority, cycle structure, routing to planner-N / auditor-N |
| [`planner-protocol.md`](references/planner-protocol.md) | Planner (planner-N) | Two-phase pipeline (goal-forge + delivery), horizon rules, write scope, refusal conditions, READY-gate enforcement |
| [`hand-protocol.md`](references/hand-protocol.md) | Hand (hand-N) | Delivery-unit requirement, execution cycle, commit authority, refusal conditions, workspace safety |
| [`auditor-protocol.md`](references/auditor-protocol.md) | Auditor (auditor-N) | Verdict types, audit method, clean-slate isolation, refusal conditions including predetermined-verdict refusal |
| [`head-protocol.md`](references/head-protocol.md) | Head (all variants) | Advisory-only boundary, no lowering duty, cadence-or-direct-question, refusal conditions |

**Boot must name the role's protocol.** A role that has not read its protocol will violate the process — lowering, tasking, authority boundaries, and workspace safety all depend on it. The boot text must say: `Read <protocol> before acting.`

| Load when | Path |
| --- | --- |
| **Mind mandatory read** | [`mind-protocol.md`](references/mind-protocol.md) |
| **Planner mandatory read** | [`planner-protocol.md`](references/planner-protocol.md) |
| **Hand mandatory read** | [`hand-protocol.md`](references/hand-protocol.md) |
| **Auditor mandatory read** | [`auditor-protocol.md`](references/auditor-protocol.md) |
| **Head mandatory read** | [`head-protocol.md`](references/head-protocol.md) |
| Sub-agent execution | [`subagent.md`](references/subagent.md) |
| tmux execution | [`tmux.md`](references/tmux.md) |
| vivi-pty execution | [`vivi-pty.md`](references/vivi-pty.md) |
| Install / init / attach | [`getting-started.md`](references/getting-started.md) |
| Cold boot | [`cold-boot.md`](references/cold-boot.md) |
| Dormant → fully launched | [`launch.md`](references/launch.md) |
| Vocab / shape (cold) | [`fleet-guide.md`](references/fleet-guide.md) |
| Roles / harness / models | [`roles-and-harness.md`](references/roles-and-harness.md) |
| Model selection | [`model-selection.md`](references/model-selection.md) |
| Goal lowering | [`lowering.md`](references/lowering.md) |
| Filing / starvation | [`tasking.md`](references/tasking.md) |
| Board CLI | [`vivi.md`](references/vivi.md) |
| Communication tracing | [`vivi.md`](references/vivi.md) § Communication tracing |
| Runtime channel concept | [`dual-channel.md`](references/dual-channel.md) |
| Modes / fail-fast / polish / HK | [`mind-cycle.md`](references/mind-cycle.md) |
| operator@ | [`operator-mail.md`](references/operator-mail.md) |
| Steward | [`dead-man.md`](references/dead-man.md) |
| Multi-fleet | [`multi-fleet.md`](references/multi-fleet.md) |
| Posture / sleep vs continuity | [`posture.md`](references/posture.md) |
| Large parallel wave execution | [`wave.md`](references/wave.md) |
| Side lanes / lane lifecycle / merge | [`multi-lane.md`](references/multi-lane.md) |
| Heads | [`heads.md`](references/heads.md), [`heads/cast.md`](references/heads/cast.md) |
| Remote | [`ssh-remote.md`](references/ssh-remote.md) |
| Schema / ladders / wind-down | [`runtime-config.md`](references/runtime-config.md) |
| Missing companions | [`companion-fallbacks.md`](references/companion-fallbacks.md) |
| Pi Mind extension | [`pi.md`](references/pi.md) |
| Pi Hand/Head wrappers | [`pi-role-wrappers.md`](references/pi-role-wrappers.md) |
| Sensors / baseline | [`fleet-sensors.py`](scripts/fleet-sensors.py), [`fleet-baseline.py`](scripts/fleet-baseline.py), [`fleet-resolve.py`](scripts/fleet-resolve.py) |
| Mind loop fallback | [`scripts/fleet-loop.py`](scripts/fleet-loop.py) |
| Runtime lifecycle | start/stop/restart directly via the configured backend (`tmux` / `vivi-pty`) — the `fleet-runtime.py` helper is removed |
| Runtime rebind | restart affected sessions directly — the `fleet-runtime-rebind.py` helper is removed |
| Cycle close | [`scripts/fleet-cycle-close.py`](scripts/fleet-cycle-close.py) |

## Don't get stuck

**Rule:** second-best progress > freeze. Hesitation is not a board event.

```text
1 Name → 2 Why → 3 Unstick by class → 4 Pivot if still blocked
```

| Class | Do | Don't |
| --- | --- | --- |
| Decision / scope | need/mail + default+options same turn | Silent wait |
| Awkward item | Switch targets | Topic monogamy |
| Dirt on path | `git diff` → class A/B/C → act | Status-only "foreign dirty" |
| Branch lag | Queue **merge** or **base-update**; **then** pivot other product work | Thrash re-verify on blocked consumer |
| Agent dead/idle+open | Wake / reinit / spawn (backend-specific) | Stack wakes |
| Human wall | File `operator@` + pivot | Silent stall |

Sleep when bag empty **and** no honest next product unit (or posture is standby/dormant).

### Growth-liveness refill

Growth posture has a stronger continuity contract:

1. If any product Hand is idle with an empty actionable bag, trigger the configured executive sweep **in this cycle**.
2. Run `head-ceo` first for map health and bounded next-unit proposals (advisory only).
3. Mind converts honest, unblocked proposals into planner-N lowering assignments.
4. A configured executive that is missing, `unknown`, `down`, or in an error state is a capacity failure: report and keep the refill path active.
5. Repeated growth cycles with idle Hands and no executive result are a fleet-control defect. Report and keep the refill path active.

### Dirt (half-dead targets)

**Ban:** destructive git on foreign/unknown WIP.
**Guidance:** open the diff — foreign ≠ ignore forever.

| Class | Is | Act |
| --- | --- | --- |
| **A** | fmt/layout only | Style-commit / include — not multi-cycle freeze |
| **B** | Other agent semantic WIP | Work around / escalate — never erase |
| **C** | Mixed | Own safe hunks only |

## Roles (compact)

| Role | Does | Does not |
| --- | --- | --- |
| Planner (planner-N) | Goal-forge + delivery lowering; produce planning artifacts; report READY + unit specs To mind | Implement product code; file Hand tasks; merge; review; act as advisor on cadence |
| Hand (implementer) | Drain product bag; validate; commit own work; polish unit; ship | Wait for GO; erase foreign WIP; touch another Hand's WIP; lower goals; review work |
| Auditor (auditor-N) | Drain review bag; `$auditor`; independent adversarial review; report To mind | Product implement; commit product code; GO stamp; plan or lower goals |
| Mind | File/wake/integrate; **route planning to planner-N, review to auditor-N**; operator mail; route all work — never implement | GO stamps; deep code review itself; **implement code, write tests, run factory, do analysis** — route to the correct role |
| operator@ | Human escalations | Status; bag drain |
| Head | Advisory on cadence or direct question; report findings To mind | Lower goals; implement; file tasks; merge; block production; act as required step in the pipeline |

Identity ≠ assignment ≠ runtime. Detail: [`roles-and-harness.md`](references/roles-and-harness.md).

## Mind modes (guidance)

Job fixed; **budget** follows engagement. Write every cycle:

| Counter | Meaning |
| --- | --- |
| `quiet_streak` | Cycles with no product signal |
| `turns_since_operator_message` | Cycles since last **human** prose |
| `last_operator_message_at` | For recap window |

**Operator message** = human prose in this session **or** board mail **From operator@ To mind@**. **Not:** `FLEET_CYCLE…` injections, Hand/Head board mail, runtime captures.

### FLEET_CYCLE prefix (required)

**First line** = attach log only. The body is a thin pointer that mirrors the sub-agent boot shape: identity → protocol check → gather state → execute → close.

```text
FLEET_CYCLE fleets=mgs

Roots:
  mgs:   /path/to/minted-geek-swarm

Protocol: if the fleet skill (SKILL.md) or mind-protocol.md are not in working memory (common after compaction), re-read before acting.
  cat $SK/SKILL.md
  cat $SK/references/mind-protocol.md

Gather state (two calls):
  vivi board --project "$ROOT"                                    # work truth: tasks/needs/wants per identity, Head cadence
  python3 $SK/fleet-sensors.py --project "$ROOT" --text            # process truth: git tips, dirty paths, runtime, signals

Execute cycle per mind-protocol.md: resolve mode → sensors → classify each signal → disposition → act same turn → sleep if quiet.

Close cycle:
  python3 $SK/fleet-cycle-close.py --project "$ROOT" --acted --summary '…' \
    --disposition '<signal>=<disposition>:<evidence>'
  python3 $SK/fleet-baseline.py bump -p "$ROOT" -s '…' [--acted|--quiet] [--operator-engaged]
```

Multi-fleet uses slugs on the first line; the body repeats per-fleet state pointers:

```text
FLEET_CYCLE fleets=mgs,faber,nacht

Roots:
  mgs:   /path/to/minted-geek-swarm
  faber: /path/to/faberlang
  nacht: /path/to/nachtbagger
```

The protocol check, gather, execute, and close steps are the same per fleet. The protocol re-read covers both the fleet skill (SKILL.md) and mind-protocol.md. Run one fail-fast mini-cycle per fleet; each fleet writes its own `last_successful_cycle_at`.

| Mode | Budget | Report |
| --- | --- | --- |
| **Autonomous** (silence≥3) | Thin ops; decide-now defaults | Compact one-liner |
| **Interactive** | Full human reasoning; fail-fast ops | **Rich** every FLEET_CYCLE |

### Multi-fleet / steward / operator@

| Topic | Rule |
| --- | --- |
| Multi-fleet | One Mind session may supervise many fleets; **one Mind per fleet**; per-fleet posture |
| Posture | `growth` ships map + aggressive research; `standby` = on-call quiet; `dormant` = rare activity |
| Mind loop fallback | If the harness has no native loop, `scripts/fleet-loop.py` may inject `FLEET_CYCLE` via tmux |
| Steward | **Default OFF.** Per-fleet dead-man only when operator explicitly enables+arms |
| operator@ | Both directions every cycle: (1) To operator@ escalations (2) From operator@ → mind@ decisions — absorb first |

## Tasking (summary)

| Kind | Use |
| --- | --- |
| task | Implementable + done-when |
| need | Decision — default+options |
| want | Non-blocking later |
| mail | Deliberation — not primary queue |

Kind ≠ severity. Hard stop = open tasks/needs. Not a stop = missing GO mail.

Starvation: empty product bag + **product** map unit → file+wake. If the next map item is **unlowered**, assign **lower** to planner-N — do **not** dump the raw goal on a Hand. [`lowering.md`](references/lowering.md)

## Role memory (memos)

Memos are durable, project-local context for a role's own future sessions. This surface is for **Mind and Head identities only**; Hands do not create, read, or maintain memos.

```sh
vivi memo list   --project <root> --for <mind-or-head-id>
vivi memo search --project <root> --for <mind-or-head-id> "keyword"
vivi memo show   --project <root> <handle>
vivi memo save   --project <root> --for <mind-or-head-id> --subject '...' --body '...'
```

**Transient routing state is not memory.** Per-cycle dispatch, wake/queue state, per-commit status belong in baseline — never in memos.

## Runtime channel (concept)

Vivi = work truth. The execution runtime = process truth. Sensors normalize both into one nested `runtime` object.

| Runtime state | Action |
| --- | --- |
| `starting` / `submitting` / `running` | No wake |
| `waiting_for_input` / `completed` + open | Wake (backend-specific) |
| `approval_required` | Resolve the approval boundary |
| `failed` / `stopped` | Diagnose, rebind, or recreate |
| `unknown` | Use evidence and stability |

Backend-specific mechanics: [`subagent.md`](references/subagent.md), [`tmux.md`](references/tmux.md), [`vivi-pty.md`](references/vivi-pty.md). Full concept: [`dual-channel.md`](references/dual-channel.md).

## Lifecycle

1. **Arm/attach** — identities; harness; runtime binding; baseline counters; `mind_session`. Dormant-to-live: [`launch.md`](references/launch.md)
2. **Focus** — map package; Hand picks open target
3. **Gather** — `vivi board --project <root>` + `fleet-sensors.py`; process mail; wake/spawn; end with `fleet-cycle-close.py`
4. **Hand work** — show→implement→validate→unit `$polish`→done→next/sleep
5. **Sleep** — most wakes no-ops
6. **Detach/wind-down** — disarm steward if armed; drop idle runtimes

### Polish / housekeeping

| Who | When | Scope |
| --- | --- | --- |
| Hand | End of product unit | Primary sources this unit only; serial `$polish` |
| Mind | Main git tip moved | `suggest-polish-files.py` → ≤1 task |
| Mind | Major inflection only | One HK task; never every land |

## Fail-fast

Exit in seconds on sensors/ops. Mode first → sensors → sleep if quiet. **absorb ≠ accept**. Code review → auditor Hands + `$auditor`; head-cto for gate honesty only.

## Shared workspace

**Ban:** destructive git / overwrite outside scope.
**Guidance:** dirt blocks → diff → A/B/C → act or pivot same turn.

## Overlay contract

Skill = portable process. Overlay = roster, paths, models, ssh, maps, Status.

```text
Vivi role records · mind-baseline.json · FLEET_CYCLE scheduler · Head prompts · Agents.md
```

```bash
python3 <skill>/scripts/fleet-sensors.py --project <root> --fleet <fleet-id> --text
python3 <skill>/scripts/fleet-cycle-close.py --project <root> --acted --summary '…'
```

## Anti-patterns

- **Bag:** GO warden; severity-as-kind; sleep with product work; sleep in growth before executive refill sweep; invent continuity work; dual Mind; Heads own bags; idle floaters despite safe parallel work; zombie campaign lanes; **campaign goal → Hand** without planner lowering; Hand invents factory/delivery for an unlowered stage; **using a Head as an inline lowering step** that production waits behind
- **Process:** mail-only or runtime-only truth; mixed Hand harnesses; stacked wakes; unbounded watch; standby-fleet busywork; per-cycle dispatch memos; universal completion review; route review to `head-cto` instead of auditors; route lowering to a Head instead of planner-N; dispatch/refuse churn; narration mail; completion hidden in replies
- **Integration:** equate packet-green with consumer-green; commit another Hand's WIP; treat absorb as accept
- **Hygiene/workspace:** skip unit polish; polish foreign work; Mind runs polish or housekeeping; polish for continuity; housekeeping every land; destructive or status-only dirt handling; topic monogamy; freeze on CEO permission; omit the `FLEET_CYCLE` prefix; send status to `operator@`; arm steward without operator authority

## Companions / first exposure

Missing skills → [`companion-fallbacks.md`](references/companion-fallbacks.md). Package is self-contained.
**No fleet visible on load** → brief the operator ([`getting-started.md`](references/getting-started.md) §0); do not invent attach.
