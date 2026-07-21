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
| **Head** | Advise / report — not bag drain | **`head-ceo` / `head-cto` / `head-cxo`** (+ optional org Heads) |
| **Hand** | Execute work (implement **or** audit) | **`hand-1`…`hand-N`**, **`auditor-1` / `auditor-2`** (Hands with review duty; **`$auditor`**) |

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
Load charter:  vivi role charter show <name> --project <root>
Load task:     vivi task show <handle> --project <root>
Optional bag:  vivi board --for <name> --project <root> --json
Execute per charter. Report via vivi task done + vivi mail send.
Return only a short pointer.
```

### Report

Before returning, the role files results through Vivi:

```bash
vivi task done <handle> --for <name> --note '<evidence: what changed, why, residuals>'
vivi mail send --from <name>@<mailspace> --to mind@<mailspace> \
  --subject 'Re: <task subject>' --body '<durable findings>'
```

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
| **tmux** | `fleet-doorbell.sh` / `tmux send-keys` | Pane classification (poll) |
| **vivi-pty** | `fleet-doorbell.sh` / `terminal write` | Session diagnostics (poll) |

Mechanics: [`subagent.md`](references/subagent.md), [`tmux.md`](references/tmux.md), [`vivi-pty.md`](references/vivi-pty.md).

## Commit authority and workflow

Hands commit their own work. The Hand has the diff context; re-deriving it in the Mind is waste. The Mind's job is review-after (sampling, auditor on risk), not commit-before.

### Standard delivery flow

```text
1. Operator + Mind   discuss feature
2. Mind              creates goal doc
3. Head              runs goal-check; Mind verifies
4. Head              lowers into delivery phases; Mind reviews + prioritizes
5. Mind              assigns phase to a Hand (picks branch strategy: main or feature)
6. Hand              executes, commits on assigned branch, returns SHA + report
7. Mind              sends commit to auditor
8. Auditor           reviews; reports bugs To mind (or pass)
9. Mind              forwards bugs to Hand as follow-up with commit ref
10. Hand             fixes, commits, reports back
11. Mind             sends to auditor for verification
12. Auditor           verifies pass
13. Mind             accepts; phase marked done
```

The audit loop (steps 7–12) is the integration bar. `accept` means the audit loop passed, not that something is queued for merge.

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

### What does not exist anymore

- **`merges_to_main` field.** No per-Hand merge flag. Branch strategy is a Mind decision at assignment time.
- **`default_hand` field.** No dedicated integration Hand. All Hands are equivalent floaters.
- **`pending_merges` / fleet-level RTM tracking.** Feature-branch merges flow through ordinary task/need/mail. The Mind tracks branches it created.
- **hand-1 as integration lane.** Single-repo fleets that want one integration Hand configure that through assignment, not through a fleet-wide field.

## Prime directive: Mind owns liveness

A Mind is not a reporter. A Mind owns forward progress for every attached fleet: observe Vivi + runtime state, keep honest work moving, refill empty product capacity, route decisions, repair runtime capacity, and preserve human blockers until they are answered.

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
| **hand-N** | `hand-N@…` | configured runtime | Product implementers and reviewers; all Hands are equivalent floaters |
| **auditor-N** | `auditor-N@…` | configured runtime | **Still a Hand** (same bag/wake machinery under `hands`); code-review duty; load **`$auditor`**; no merge; report To mind |
| **head-*** | `head-*@…` | configured runtime | ceo=strategist; cto **gate honesty / architecture** (not default code-review queue); cxo purity; cso security; coo ops |

**Fleet** = project root + `.vivi/`.

### Standard helper scope

Every fleet helper uses the same scope vocabulary:

```text
--project/-p <project-root>   durable fleet project boundary
--fleet/-f <fleet-id>         logical fleet identity, validated against fleet.json
--fleet-file <path>           explicit fleet.json path override
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
| Hand equivalence | All Hands are equivalent floaters. The Mind picks any available Hand for each assignment. No Hand has a special integration role; there is no fleet-wide main in a multi-repo container. Single-repo fleets don't need a dedicated merger either — see [Commit authority and workflow](#commit-authority-and-workflow) |
| Lowering | **Campaign goal → Head lowers** (`goal-forge` → `$goal-check` READY → `$delivery` docs) → Mind files Hands from those units. Hands do **not** lower raw goals via factory. — [`lowering.md`](references/lowering.md) |
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
| Growth refill | Sensors emit **`growth_refill_required`** + **`refill_hint.disposition=file_head_lower`** when growth product Hand bags are empty. Treat as act-now: Head lower / executive refill |
| Growth liveness | In `growth`, an idle product Hand with no queued unit is **not** a quiet cycle: trigger an executive refill sweep immediately |
| Head backpressure | A Head that refuses or does not run is **`deferred-valid`**: record once in baseline, retry on cadence |
| Loop continuity | Before ending a turn with delegated work outstanding, ensure a Fleet loop is active to collect the result. Create one if absent; never create a duplicate — [`mind-cycle.md`](references/mind-cycle.md#adaptive-scheduled-cadence) |

### Operational

| Invariant | Rule |
| --- | --- |
| Mind memory | Memos carry rules and policy that must survive a **cold boot** — a brand-new session with no compaction history. Two tests, both must fail for a memo to be warranted: (1) would losing this across a cold boot cause a worse decision? (2) can it be recovered from a Vivi handle instead? If yes to the second, use a pointer in compaction — not a memo. Things tied to the current working arc (task status, hand progress, audit results) belong in compaction or the board, not memos. |
| Mind mail hygiene | Mail To mind is routing and triage, not memory. Read it, act on it, absorb it. Do not accumulate open mail as a backlog; do not self-address mail as a parking lot. Absorb marks mail read (the consume lifecycle) and is not a memory mechanism — durable context belongs in memo, working context belongs in compaction. On major inflection (campaign end, stage closeout), audit memos and retire ones that reference superseded architecture. |
| Wake on mail | Each Mind cycle is the debounce: new board mail addressed to a process role wakes that role when idle. Running agents are not interrupted |
| Posture | Per-fleet `growth` \| `standby` \| `dormant` — [`fleet-posture.md`](references/fleet-posture.md) |
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
| Models | **Cheap well-scoped implement → strong independent audit → cheap repair.** Volume implement only **after** Head lowering. Live strings on the Vivi role record. Process: [`model-selection.md`](references/model-selection.md) |

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
| **Cold attach** | This file → [`subagent.md`](references/subagent.md) (or [`tmux.md`](references/tmux.md) / [`vivi-pty.md`](references/vivi-pty.md) for those backends) → [`mind-cycle.md`](references/mind-cycle.md). Add [`getting-started.md`](references/getting-started.md) for attach, [`multi-fleet.md`](references/multi-fleet.md) before multi-fleet. |
| **Hot cycle** (state already in context) | This file alone if quiet; open a ref when that surface hits |
| **Arm / first Mind turn** | This file + refs for surfaces you will touch this turn |

| Load when | Path |
| --- | --- |
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
| Runtime channel concept | [`dual-channel.md`](references/dual-channel.md) |
| Modes / fail-fast / polish / HK | [`mind-cycle.md`](references/mind-cycle.md) |
| operator@ | [`operator-mail.md`](references/operator-mail.md) |
| Steward | [`dead-man.md`](references/dead-man.md) |
| Multi-fleet | [`multi-fleet.md`](references/multi-fleet.md) |
| Posture / sleep vs continuity | [`fleet-posture.md`](references/fleet-posture.md) |
| Side lanes / lane lifecycle / merge | [`multi-lane.md`](references/multi-lane.md) |
| Heads | [`heads.md`](references/heads.md), [`heads/cast.md`](references/heads/cast.md) |
| Remote | [`ssh-remote.md`](references/ssh-remote.md) |
| Schema / ladders / wind-down | [`runtime-config.md`](references/runtime-config.md) |
| Missing companions | [`companion-fallbacks.md`](references/companion-fallbacks.md) |
| Pi Mind extension | [`pi.md`](references/pi.md) |
| Pi Hand/Head wrappers | [`pi-role-wrappers.md`](references/pi-role-wrappers.md) |
| Sensors / baseline | [`fleet-sensors.py`](scripts/fleet-sensors.py), [`fleet-baseline.py`](scripts/fleet-baseline.py), [`fleet-resolve.py`](scripts/fleet-resolve.py) |
| Mind loop fallback | [`scripts/fleet-loop.py`](scripts/fleet-loop.py) |
| Runtime lifecycle | [`scripts/fleet-runtime.py`](scripts/fleet-runtime.py) |
| Runtime rebind | [`scripts/fleet-runtime-rebind.py`](scripts/fleet-runtime-rebind.py) |
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
2. Run `head-ceo` first for map health and bounded next-unit proposals.
3. Mind converts honest, unblocked Head proposals into Hand tasks in the same cycle.
4. A configured executive that is missing, `unknown`, `down`, or in an error state is a capacity failure: reinit/recreate it in the same cycle.
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
| Hand (implementer) | Drain product bag; validate; commit own work; polish unit; ship | Wait for GO; erase foreign WIP; touch another Hand's WIP |
| Hand (auditor-N) | Drain **review** bag; `$auditor`; report To mind | Product implement; commit product code; GO stamp |
| Mind | File/wake/integrate; **triage whether to file auditor Hand**; operator mail | GO stamps; deep code review itself |
| operator@ | Human escalations | Status; bag drain |
| head-cto | Technical **gate honesty** + architecture | Default code-review queue |
| head-ceo | **Strategist + default lowering seat** | File Hand tasks; merge; product code |
| head-cxo | Complexity/purity | Product bag; operator mail |

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

**First line** = attach log only.

```text
FLEET_CYCLE fleets=mgs
FLEET_CYCLE fleets=mgs,faber,nacht
```

**Paths** live **below** the first line as a plain slug→root map:

```text
Roots:
  mgs:   /path/to/minted-geek-swarm
  faber: /path/to/faberlang
```

Resolve engagement first. Human prose this turn or since `last_operator_message_at` → `--operator-engaged` (reset). Else let baseline bump increment silence. Never hand-edit counters after bump.

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

Starvation: empty product bag + **product** map unit → file+wake. If the next map item is **unlowered**, assign **lower** To the Head seat — do **not** dump the raw goal on a Hand. [`lowering.md`](references/lowering.md)

## Role memory (memos)

Memos are durable, project-local context for a role's own future sessions. This surface is for **Mind and Head identities only**; Hands do not create, read, or maintain memos.

```sh
vivi memo list   --project <root> --for <mind-or-head-id>
vivi memo show   --project <root> <handle>
vivi memo save   --project <root> --for <mind-or-head-id> --subject '...' --body '...'
```

> **Known gap: no `memo search`.** `memo list` dumps every memo for a role;
> there is no keyword or handle query to find memos mentioning a topic. This
> forces a Mind to load all of a role's memos into context, which defeats the
> purpose of selective durable memory. Until a `vivi memo search` command
> exists, keep each role's memo set small and use descriptive handles/subjects
> so a `memo list` scan stays cheap.

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
3. **Gather** — `fleet-sensors.py`; process mail; wake/spawn; end with `fleet-cycle-close.py`
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
.vivi/fleet.json · mind-baseline.json · FLEET_CYCLE scheduler · Head prompts · Agents.md
```

```bash
python3 <skill>/scripts/fleet-sensors.py --project <root> --fleet <fleet-id> --text
python3 <skill>/scripts/fleet-cycle-close.py --project <root> --acted --summary '…'
```

## Anti-patterns

- **Bag:** GO warden; severity-as-kind; sleep with product work; sleep in growth before executive refill sweep; invent continuity work; dual Mind; Heads own bags; idle floaters despite safe parallel work; zombie campaign lanes; **campaign goal → Hand** without Head lowering; Hand invents factory/delivery for an unlowered stage
- **Process:** mail-only or runtime-only truth; mixed Hand harnesses; stacked wakes; unbounded watch; standby-fleet busywork; per-cycle dispatch memos; universal completion review; route review to `head-cto` instead of auditors; dispatch/refuse churn; narration mail; completion hidden in replies
- **Integration:** equate packet-green with consumer-green; commit another Hand's WIP; treat absorb as accept
- **Hygiene/workspace:** skip unit polish; polish foreign work; Mind runs polish or housekeeping; polish for continuity; housekeeping every land; destructive or status-only dirt handling; topic monogamy; freeze on CEO permission; omit the `FLEET_CYCLE` prefix; send status to `operator@`; arm steward without operator authority

## Companions / first exposure

Missing skills → [`companion-fallbacks.md`](references/companion-fallbacks.md). Package is self-contained.
**No fleet visible on load** → brief the operator ([`getting-started.md`](references/getting-started.md) §0); do not invent attach.
