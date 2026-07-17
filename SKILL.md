---
name: fleet
description: Multi-agent fleet management with Mind/Head/Hand roles (Abbot pattern) — Mind session attaches to one or more fleets; Hands/Heads; steward dead-man; dual-channel Vivi+tmux; multi-fleet FLEET_CYCLE. Use for hand-N fleets, multi-fleet attach, codex reinit, opencode hand-ctl, steward arm/rearm/disarm.
---

# Fleet

**Official source:** [https://github.com/ianzepp/fleet](https://github.com/ianzepp/fleet) — clone or pull from there for updates; do not treat monorepo skill mirrors as canonical.

Abbot **Mind / Head / Hand** roles on a **multi-session fleet** (Vivi board + tmux panes), not an in-process kernel.

| Role | Job | Identity |
| --- | --- | --- |
| **Mind** | Tasking, integrate, pane ops, cycles | Operator TUI + board **`mind@…`** (no tmux) |
| **Operator mail** | Human escalations | Board **`operator@…`** (no tmux) |
| **Head** | Advise / report — not bag drain | **`head-ceo` / `head-cto` / `head-cxo`** (+ optional org Heads) |
| **Hand** | Execute work (implement **or** audit) | **`hand-1`…`hand-N`**, **`auditor-1` / `auditor-2`** (Hands with review duty; **`$auditor`**) |

## Prime directive: Mind owns liveness

A Mind is not a reporter. A Mind owns forward progress for every attached fleet: observe Vivi + tmux, keep honest work moving, refill empty product capacity, route decisions, repair runtime capacity, and preserve human blockers until they are answered.

**A cycle is incomplete until every material sensor signal has a disposition.** Treat `fleet-sensors.py` `signals[]`, open operator mail, pane failures, dirty blockers, pending merges/RTM, idle Hands, Head reports, and board events as obligations — not trivia.

| Disposition | Meaning |
| --- | --- |
| `acted` | Fixed, filed, woke, reinit'd, merged/queued, absorbed, or presented this cycle |
| `delegated` | Converted to a concrete task/need/mail for the correct Hand/Head/Mind owner |
| `escalated` | Sent To `operator@` with default/options because human-only or unsafe to default |
| `deferred-valid` | Explicitly held by posture, operational pause, running pane, merge wait, or real dependency |
| `sleep-valid` | No material signals, no honest unblocked work, and posture permits quiet |

Reporting a blocker without acting, delegating, escalating, or recording a valid defer is a failed Mind cycle. “Pane unavailable,” “foreign dirt,” “operator need exists,” “empty bag,” and “Head not running” are not dispositions by themselves.

## Identity + binding

| Identity | Mail | tmux | Notes |
| --- | --- | --- | --- |
| **mind** | `mind@…` | none | Board To: Mind; process = this chat |
| **operator** | `operator@…` | none | Human only — [`operator-mail.md`](references/operator-mail.md) |
| **steward** | optional opt-in | tmux runtime | Dead-man, not Mind — **off by default**; operator must enable+arm per fleet — [`dead-man.md`](references/dead-man.md) |
| **hand-N** | `hand-N@…` | configured runtime | `hand-1` merges to main; product implementers |
| **auditor-N** | `auditor-N@…` | configured runtime | **Still a Hand** (same bag/wake machinery under `hands`); code-review duty; load **`$auditor`**; no merge; report To mind |
| **head-*** | `head-*@…` | configured runtime | ceo=strategist; cto **gate honesty / architecture** (not default code-review queue); cxo purity; cso security; coo ops |

| Layout | Binding |
| --- | --- |
| Single-fleet | `mail_identity == tmux_session`; target e.g. `hand-1:1.1` |
| Session-per-fleet | role mail; session=`fleet_id`; window=role; target e.g. `mgs:hand-1.1` |

**Ops use the role's configured runtime binding and consume canonical `runtime` observations.** No mind/operator runtime. No dual Mind process.
**Fleet** = project root + `.vivi/`.

### Standard helper scope

Every fleet helper uses the same scope vocabulary:

```text
--project/-p <project-root>   durable fleet project boundary
--fleet/-f <fleet-id>         logical fleet identity, validated against fleet.json
--fleet-file <path>           explicit fleet.json path override
--role <role>                 logical Hand/Head role (repeatable where selection needs it)
--runtime-target <target>     concrete tmux/Vivi-PTY target override for the helper call
```

`--fleet` is never a fleet.json pathname, and a backend target is never used as
the fleet identity. `scripts/fleet-resolve.py` is the narrow shared adapter for
turning `project + fleet + role` into the configured tmux session/window/pane or
Vivi-PTY session. Helpers may expose only the flags relevant to their operation,
but use these meanings when they do.

### Tokens (disambiguation)

| Token | Means | Not |
| --- | --- | --- |
| **`HEAD`** / “main tip” | Git commit pointer (`git rev-parse HEAD`) | Advisor role |
| **Head** / `head-*` | Advisor role (`head-ceo` / `head-cto` / `head-cxo`) | Git tip |
| **bag** | Open tasks+needs for an identity (Vivi) | Status essays |
| **map** | Campaign/factory plan of next packages | The bag itself |
| **unit** | One implementable package of work | Full theme |
| **theme** | Multi-unit delivery chunk; merge boundary for packets | Single residual |
| **packet** | hand-2+ worktree/branch (not main) | Main checkout |
| **RTM** | ready-to-merge (mail signal for a packet/theme) | Done on main |
| **absorb** | Bookkeeping when something moved | Integration bar |
| **accept** | Integration bar (clear review debt / queue merge) — not code review | absorb; auditor residual |
| **GO stamp** | Forbidden stage license / approval gate | Residual tasking |

Canon for absorb/accept: [`mind-cycle.md`](references/mind-cycle.md) § Absorb vs accept. Do not invent a third meaning.

| Invariant | Rule |
| --- | --- |
| Process | Mind fills bag; Hand empties. Progress = open tasking + map — not GO stamps |
| Mind memory | Use **mind memos** as atomic durable checklist facts that would otherwise live only in chat: current thesis, lane ownership, intentional defers, operator policy, invariants, and next likely moves. Tasks route work; mail reports events; baseline tracks counters; memos preserve cold-boot context. **Durability test:** would this fact still matter after a reinit, or in a week? If not — cycle dispatch, wake/queue state, per-commit status, pane state — it is **loop state** (baseline / `mind_loop` state), not a memo. |
| Multi-hand | Mind files/wakes/merges clock; head-ceo side-lane bucket (`effort`+`est_tokens`); Mind calibrates est vs actual |
| Campaign truth | `head-ceo` periodically audits campaign/factory status against Git, board, validation, release, and deploy evidence; Mind files bounded `$zombie-docs` repair when prose lies |
| Lane lifecycle | A bound idle Hand is investigated after the configured grace; Mind reconciles map/task/worktree truth before continue, park, cooldown, or release. Runtime release never implies worktree deletion |
| Floater shape | **Recommended for multi-repo containers:** keep **hand-1** as the dedicated main/integration lane; use **hand-2..hand-4** as floaters that may run in parallel when their assigned repos/worktrees do not overlap. This is a strong default, not a universal requirement; explicit fleet config or operator direction wins. |
| Starvation | Empty bag + **honest unblocked product unit on the map** → file+wake. Never invent polish/makework to fill bags |
| Growth liveness | In `growth`, an idle product Hand with no queued unit is **not** a quiet cycle: trigger an executive refill sweep immediately; do not wait for the normal Head cadence. |
| Wake on mail | Each Mind cycle is the debounce: new board mail addressed to a process role wakes that role when idle. Executive cadence governs unsolicited sweeps, never addressed work. Running panes are not interrupted; the next cycle retries after they become idle. |
| Posture | Per-fleet `growth` \| `standby` \| `dormant` — switch atomically with `scripts/fleet-posture.py`; willing to sleep when charter says so — [`fleet-posture.md`](references/fleet-posture.md) |
| Assignment mode | Per Hand/Head `assignment_mode`: `new` \| `compact` \| `continue` \| `restart` — session prep on each **new** work item ([`runtime-config.md`](references/runtime-config.md)); legacy `clean_slate_per_assignment: true` ≡ `new` |
| Loop continuity | Before ending a turn with delegated Hand/Head work outstanding, ensure a Fleet loop is active to collect the result. Create one if absent; if an existing interval is too slow for new operator-requested work, tighten it. Never create a duplicate — [`mind-cycle.md`](references/mind-cycle.md#adaptive-scheduled-cadence) |
| Cadence | Scheduled loops adapt: thin/unchanged results → lengthen; accumulated work faster than absorption → shorten; completion → cancel. Replace schedules without duplicates and preserve goal/limits/stop condition — [`mind-cycle.md`](references/mind-cycle.md#adaptive-scheduled-cadence) |
| COO DR | Top-level `disaster_recovery` is default-off and calendar/maturity-triggered. COO reports recoverability evidence/gaps only; no backup, restore, secret/provider/spend/external action. Policy/config, one Git remote, or backup-job success is never restore proof. |
| Stuck | Freeze fails — name, unstick, pivot. No status-only blocked cycles. Stuck ≠ “must invent work” |
| Harness | **Default:** Mind, Hands, and Heads use Pi; provider/model diversity preserves advisor independence. **Fleet config exceptions win** (desktop Mind, compatibility harness, operator-recorded mixed) — [`roles-and-harness.md`](references/roles-and-harness.md) |
| Quality | Product Hands ship unit quality. **Code review** is a **Hand duty** on **`auditor-1` / `auditor-2`** (same category as other hands; skill **`$auditor`**) — **not** head-cto by default. Mind decides: low-risk → accept from implementer `done` evidence; **risk / auth-persistence / sample** → task an auditor Hand. **Never** universal review on every completion. **head-cto** = gate honesty / architecture only |
| Head backpressure | A Head that refuses or does not run is **`deferred-valid`**: record once in baseline, retry on cadence. Do **not** re-dispatch to it this cycle and do **not** memo the stall. Dispatch/refuse churn is a failed cycle, not a disposition |
| Mind mail hygiene | The loop does not narrate itself into mail. Self-addressed mail (`mind@` → `mind@`) and reply-thread echoes are not a memory substitute — a cycle's record lives in baseline / `mind_loop` state, same as memos. Mail To `mind@` is routing/triage and deliberation, not an append-only audit sink. `mail absorb` marks mail read (the consume lifecycle) and is not a memory mechanism — durable context belongs in `memo` |
| Peer communication | Heads and Hands may send advisory **mail** to one another. They may not assign or reroute peer tasks, needs, or wants; transfer ownership; authorize merges; or create gates. Material peer mail must remain visible to Mind. |
| Hygiene | Mind never runs `$polish`/`$housekeeping` itself; never thrash polish for continuity |

| Mind hygiene | When | Action |
| --- | --- | --- |
| Polish advisory | Main **git `HEAD`** moved | Cheap ranker → ≤1 bounded `$polish` task if scores ≥ threshold |
| Housekeeping | Campaign end / large merge / stage closeout / operator | One `$housekeeping` task To hand-1 — never routine lands |
```text
map → MIND ─files→ bag → HAND clears target → residuals → MIND
       Vivi = work truth · tmux = process truth
Heads ─mail To mind→ triage · problems → operator@ · status → mind@ + recap
```

Peer mail is allowed for findings, questions, early review feedback, and handoffs. It is advisory and may wake the recipient on the next Mind cycle. Queue ownership remains centralized: Mind alone files or reroutes tasks/needs/wants between process roles. Avoid automatic reply chains; one peer reply is not a new assignment.

## When to use

Multi-agent project loops, factory/campaign residual+implementer, fail-fast 5–10m wakes, tmux Hands/Heads (local or SSH). **Not** personal IMAP (`$mail`); not a second acceptance gate.

## Hard bans vs guidance

| Kind | Examples |
| --- | --- |
| **Hard ban** | Destructive git on foreign dirt; erase other WIP; `exec` that kills pane session |
| **Guidance** | Mode, harness alignment, head-ceo, absorb/accept, merge cadence, models |
| **Not a ban** | “Might break autonomous” — if operator engaged or default safe, **act** |

**Decide now:** reversible default → take it. Human-only → `operator@` need/mail (default+options) + pivot.

## Loading map

Core process here; detail in `references/` + `scripts/`.

| Session context | Required reading |
| --- | --- |
| **Cold attach** (new session, empty context, or compact without recap) | This file → [`vivi.md`](references/vivi.md) → [`mind-cycle.md`](references/mind-cycle.md). Add [`getting-started.md`](references/getting-started.md) §3 for attach, [`multi-fleet.md`](references/multi-fleet.md) before multi-fleet commands, [`pi.md`](references/pi.md) inside Pi, [`fleet-guide.md`](references/fleet-guide.md) only when vocabulary is cold, and [`cold-boot.md`](references/cold-boot.md) only when durable memory is missing. |
| **Hot cycle** (mode/counters/state already in context) | This file alone if quiet; open a ref when that surface hits |
| **Arm / first Mind turn on a live fleet** | This file + refs for surfaces you will touch this turn |

| Load when | Path |
| --- | --- |
| Install / init / attach | [`getting-started.md`](references/getting-started.md) |
| Cold boot (no institutional memory) | [`cold-boot.md`](references/cold-boot.md) |
| Dormant → fully launched | [`launch.md`](references/launch.md) |
| Vocab / shape (cold) | [`fleet-guide.md`](references/fleet-guide.md) |
| Roles / harness / models | [`roles-and-harness.md`](references/roles-and-harness.md) |
| Filing / starvation | [`tasking.md`](references/tasking.md) |
| Board CLI | [`vivi.md`](references/vivi.md) |
| Panes / wake / reinit | [`dual-channel.md`](references/dual-channel.md) |
| Modes / fail-fast / polish / HK / absorb·accept | [`mind-cycle.md`](references/mind-cycle.md) |
| operator@ | [`operator-mail.md`](references/operator-mail.md) |
| Steward | [`dead-man.md`](references/dead-man.md), [`scripts/steward.sh`](scripts/steward.sh) |
| Multi-fleet | [`multi-fleet.md`](references/multi-fleet.md) |
| Posture / sleep vs continuity | [`fleet-posture.md`](references/fleet-posture.md) |
| Side lanes / lane lifecycle / merge | [`multi-lane.md`](references/multi-lane.md); canonical disposition gates in [`mind-cycle.md`](references/mind-cycle.md) |
| Heads | [`heads.md`](references/heads.md), [`heads/cast.md`](references/heads/cast.md) |
| Remote | [`ssh-remote.md`](references/ssh-remote.md) |
| Schema / ladders / wind-down | [`runtime-config.md`](references/runtime-config.md) |
| Missing companions | [`companion-fallbacks.md`](references/companion-fallbacks.md) |
| Pi Mind extension | [`pi.md`](references/pi.md) |
| Sensors / baseline / doorbell | [`fleet-sensors.py`](scripts/fleet-sensors.py), [`fleet-baseline.py`](scripts/fleet-baseline.py), [`fleet-doorbell.sh`](scripts/fleet-doorbell.sh), [`fleet-resolve.py`](scripts/fleet-resolve.py). Doorbell records `last_hand_wake`; sensors cover RTM/integration lag, Git drift, dirt, and lane reconciliation. |
| Mind loop fallback | [`scripts/fleet-loop.py`](scripts/fleet-loop.py). tmux-backed `FLEET_CYCLE` injector for Mind harnesses without native scheduled loops. Records `.vivi/fleet-loop.json`; `start`, `status`, `stop`; loop ≠ steward and never runs sensors itself. |
| Runtime lifecycle | [`scripts/fleet-runtime.py`](scripts/fleet-runtime.py). Backend-neutral start/stop/restart/status for configured Hand/Head runtimes; use before doorbell when a role is stopped. |
| Runtime rebind | [`scripts/fleet-runtime-rebind.py`](scripts/fleet-runtime-rebind.py). Plan/apply atomic runtime config changes across Heads and Hands. |
| Cycle close | [`scripts/fleet-cycle-close.py`](scripts/fleet-cycle-close.py). One command: sensors → baseline bump → optional steward rearm. |
| Codex pane | [`scripts/codex-reinit.sh`](scripts/codex-reinit.sh) |
| Codex plugin | [`plugins/fleet/`](plugins/fleet) |
| opencode pane | [`scripts/opencode-hand-ctl.sh`](scripts/opencode-hand-ctl.sh) |
| Portability smoke | [`scripts/lib/env.sh`](scripts/lib/env.sh), [`smoke-portability.sh`](scripts/smoke-portability.sh) |

## Don't get stuck

**Rule:** second-best progress > freeze. Hesitation is not a board event.

```text
1 Name → 2 Why → 3 Unstick by class → 4 Pivot if still blocked
```

| Class | Do | Don't |
| --- | --- | --- |
| Decision / scope | need/mail + default+options same turn | Silent wait |
| Awkward item | Switch targets | Topic monogamy |
| Dirt on path | `git diff` → class A/B/C → act | Status-only “foreign dirty” |
| Integration lag | Queue **merge** or **base-update** (whichever unblocks); **then** pivot other product work | Thrash re-verify on blocked consumer |
| Pane dead/idle+open | Wake / reinit / runtime ladder | Stack wakes |
| Human wall | File `operator@` + pivot | Silent stall |
| Hand idle, tasks unprocessed | Verify the helper resolved the logical fleet and role to the expected runtime target. Also: hands receive **direct prompts** with task content, not `vivi board` — the board is Mind's dashboard, not a wake command. Send the task instructions inline. | Re-file task; send board to claim it was filed |
Sleep when bag empty **and** no honest next product unit (or posture is standby/dormant). Sleep is allowed — do not invent work.

### Growth-liveness refill

Growth posture has a stronger continuity contract than standby or dormant:

1. If any product Hand is idle with an empty actionable bag, and no honest
   unblocked map unit is already available, trigger the configured executive
   sweep **in this cycle**. Do not wait three to six hours for the scheduled
   `head-ceo`/CTO/CXO cadence.
2. Run `head-ceo` first for map health and bounded next-unit proposals; run the
   configured technical, product, security, marketing, or purity Heads in
   parallel when their domains are relevant. Heads return bounded buckets with
   scope, done-when, dependencies, and effort/token estimates; they do not file
   Hand tasks themselves.
3. Mind converts honest, unblocked Head proposals into Hand tasks and
   doorbells in the same cycle. A growth fleet may sleep only when the sweep
   finds no honest product scope, or when a real human/environment gate is
   recorded with a default and pivot.
4. A configured executive pane that is missing, `unknown`, `down`, or in an
   error state is a capacity failure, not a reason to wait: reinit/recreate it
   in the same cycle. If the fleet has no configured executive topology, file
   an operational need to repair the roster and pivot to any remaining
   grounded work.
5. Repeated growth cycles with idle Hands and no executive result are a
   fleet-control defect. Report the defect and keep the refill path active;
   never normalize it as `quiet`.

### Dirt (half-dead targets)

**Ban:** destructive git on foreign/unknown WIP.  
**Guidance:** open the diff — foreign ≠ ignore forever.

| Class | Is | Act |
| --- | --- | --- |
| **A** | fmt/layout only | Style-commit / include — not multi-cycle freeze |
| **B** | Other agent semantic WIP | Work around / escalate — never erase |
| **C** | Mixed | Own safe hunks only |

Hand: A same turn; B need+pivot; C own hunks. Mind: ≥2 cycles blocked unclassified → open diff, classify, track age.

## Roles (compact)

| Role | Does | Does not |
| --- | --- | --- |
| Hand (implementer) | Drain product bag; validate; polish unit; ship | Wait for GO; erase foreign WIP; hand-2+ merge |
| Hand (auditor-N) | Drain **review** bag; `$auditor`; report To mind | Product implement; merge; GO stamp |
| Mind | File/wake/integrate; **triage whether to file auditor Hand**; operator mail | GO stamps; deep code review itself |
| operator@ | Human escalations | Status; bag drain |
| head-cto | Technical **gate honesty** + architecture | Default code-review queue (use auditor Hands) |
| head-ceo | **Strategist:** map health, misprioritization, gate honesty; side-lane buckets; continuity consult; posture-scaled proactivity | File Hand tasks; merge; invent polish |
| head-cxo | Complexity/purity (gates invented by shape) | Product bag; operator mail |

Identity ≠ assignment ≠ runtime. Detail: [`roles-and-harness.md`](references/roles-and-harness.md).

## Mind modes (guidance)

Job fixed; **budget** follows engagement (not model id). Write every cycle:

| Counter | Meaning |
| --- | --- |
| `quiet_streak` | Cycles with no product signal |
| `turns_since_operator_message` | Cycles since last **human** prose |
| `last_operator_message_at` | For recap window |

**Operator message** = human prose in this session **or** board mail **From operator@ To mind@**. **Not:** `FLEET_CYCLE…` injections, Hand/Head board mail, pane captures.

### FLEET_CYCLE prefix (required)

**First line** = attach log only (what fleets this fire covers). **Do not** invent path keys on the topic line (`also=`, `also2=`, …).

```text
# Single fleet — either slug or one project= is enough
FLEET_CYCLE fleets=mgs
FLEET_CYCLE project=/path/to/one/fleet

# Multi-fleet — slugs only on the first line
FLEET_CYCLE fleets=mgs,faber,nacht
```

**Paths** live **below** the first line (loop body / durable prompt), as a plain slug→root map Mind already knows from attach:

```text
Roots:
  mgs:   /path/to/minted-geek-swarm
  faber: /path/to/faberlang
  nacht: /path/to/nachtbagger
```

Resolve each slug via that map (or `fleet.json` `project` when already open). Loop lives in the operator TUI — no fake Mind pane. Multi-fleet: mini-cycle **each** named fleet; baseline bump per fleet. **`steward.sh rearm` only if that fleet’s steward is enabled and armed** (opt-in).  
**Bug:** `FLEET_CYCLE`-only payload ≠ silence — count human chat **between** fires.

```text
engaged = human prose this turn OR since last_operator_message_at (not FLEET_CYCLE)
if engaged: interactive; silence=0; present operator@ if N>0; refresh recap
else: silence += 1; silence≥3 → autonomous (else keep prior; turns 1–2 may still watch)
```

**Hard never (mode counters) — both directions:**

| Forbidden | Why |
| --- | --- |
| `turns += 1` / force `autonomous` only because payload is `FLEET_CYCLE…` | Ignores human chat **between** fires |
| Force `turns = 0` / force `interactive` on **every** FLEET_CYCLE | Silence never advances; autonomous never arrives |

**Do:** resolve engagement first. Human prose this turn **or** since `last_operator_message_at` → `--operator-engaged` (reset). Else let `fleet-baseline.py bump` **increment** silence (default). **Never** hand-edit counters after bump.

Override: `Mind: deep` / `Mind: ops only`.

| Mode | Budget | Report |
| --- | --- | --- |
| **Autonomous** (silence≥3 **true** human gaps) | Thin ops; decide-now defaults | Compact one-liner / short headline |
| **Interactive** | Full human reasoning; fail-fast ops | **Rich** every FLEET_CYCLE (even quiet) |

Report tracks **mode**, not acted/sleep alone. Templates: [`mind-cycle.md`](references/mind-cycle.md).

**Recap:** compact deltas since last operator (git tips, handles, panes, mode, debt). Re-seed after `/compact`.

### Multi-fleet / steward / operator@

| Topic | Rule |
| --- | --- |
| Multi-fleet | One Mind session may supervise many fleets; **one Mind per fleet** (advisory `mind_session`); fleets= on FLEET_CYCLE line; prefer session=`fleet_id`. **Per-fleet posture** — standby/dormant mini-cycles stay quiet |
| Posture | `growth` ships map + aggressive Head research; `standby` = on-call Hands quiet, Heads **stewardship**; `dormant` = Heads rare. Head schedule = one dial `executive_cadence.every_n_loops`: **0** on-call, **N≥1** due every `N × mind_loop.interval_sec` (no separate `enabled`/`self_directed`). Continuity doubt → head-ceo once, not polish thrash — [`fleet-posture.md`](references/fleet-posture.md) |
| Mind loop fallback | If the harness has no native loop/tool scheduler, `scripts/fleet-loop.py --project <root> start 5m --target <operator-pane>` may inject `FLEET_CYCLE` into the live operator pane. `status` before starting; `stop` when the campaign ends or a better scheduler replaces it. |
| Steward | **Default OFF.** Per-fleet dead-man only when operator **explicitly** enables `steward.enabled` **and** asks to arm **that** fleet. Loop ≠ steward. When armed: rearm each successful mini-cycle; disarm same turn on detach. Not second Mind |
| operator@ | **Both directions every cheap cycle:** (1) **To operator@** escalations waiting on human (2) **From operator@ → mind@** decisions/feedback — absorb **first**. Sensors: `operator_mail` + `operator_to_mind`. [`operator-mail.md`](references/operator-mail.md) |

## Tasking (summary)

| Kind | Use |
| --- | --- |
| task | Implementable + done-when (incl. critical defects) |
| need | Decision — default+options |
| want | Non-blocking later |
| mail | Deliberation — not primary queue |

Kind ≠ severity. Hard stop = open tasks/needs. Not a stop = missing GO mail.  
hand-1 = main + merges; hand-2+ = packets, never main merge; unit done → refill; theme done → RTM mail.  
Recommended multi-repo layout: **hand-1** stays dedicated to the main/integration lane, while **hand-2..hand-4** are floaters. Mind may reassign floaters across repos/worktrees and run them in parallel only when write scopes do not overlap; if scopes collide, serialize or choose a different repo. This is a suggested operating shape, not a hard schema requirement.
Starvation: empty product bag + **product** map unit → file+wake. Not polish theater. Posture: [`fleet-posture.md`](references/fleet-posture.md). [`tasking.md`](references/tasking.md)

## Role memory (memos)

Memos are durable, project-local context for a role's own future sessions. They
are not routed work, communication, or part of the actionable bag. This surface
is for **Mind and Head identities only**; Hands do not create, read, or maintain
memos. Hands return findings through their assigned task and normal advisory
mail, while Mind or a Head decides what deserves durable memory.

Mind and Heads should review their own memos when attaching or resuming, and
save stable decisions, recurring constraints, strategy, or findings that
should survive a cycle or reinitialization:

```sh
vivi memo list   --project <root> --for <mind-or-head-id>
vivi memo show   --project <root> <handle>
vivi memo save   --project <root> --for <mind-or-head-id> --subject '...' --body '...'
vivi memo dump   --project <root> --for <mind-or-head-id>
vivi memo delete --project <root> --for <mind-or-head-id> <handle>
```

Use `memo dump --for` for an explicitly scoped memory review. Do not use memos
to assign, delegate, or report work; use task, need, want, or mail for those
purposes. Memos do not appear in `vivi board`, task dumps, or normal mail
dumps, and Hands are not a fallback memory store.

**Transient routing state is not memory.** Per-cycle dispatch, wake/queue
state, per-commit status, and Head-refusal stalls belong in baseline /
`mind_loop` state — never in memos. Do not memoize “cycle N dispatched…”; the
loop narrating its own mechanics to itself is the core memo anti-pattern. When
attaching to a repo that has real history but no Vivi memory (lost store, or
first fleet management), rebuild a small seed set from durable sources — see
[`cold-boot.md`](references/cold-boot.md).

## Dual channel (summary)

Vivi = work truth. The configured tmux or `vivi_pty` runtime = process truth. Sensors normalize both into one nested `runtime` object.

| Runtime state | Action |
| --- | --- |
| `starting` / `submitting` / `running` | No wake |
| `waiting_for_input` / `completed` + open | Pointer doorbell. First wake per Hand never rate-limits |
| `waiting_for_input` / `completed` + open + stuck after doorbell | Harness-specific reinit fallback |
| `approval_required` | Resolve the approval boundary; do not stack input |
| `failed` / `stopped` | Diagnose, rebind, or recreate |
| `unknown` | Use evidence and stability; never claim false certainty |

**`assignment_mode`** (per Hand/Head in `fleet.json`): how sessions are prepared
for each **new** work item — `new` | `compact` | `continue` | `restart`.
`fleet-doorbell.sh` applies this automatically when `--handle` differs from the
last wake handle (override with `--mode` / `--no-prepare` / `--force-prepare`).
Resolved via `fleet-resolve.py`. Legacy `clean_slate_per_assignment: true` ≡
`new`. Full table: [`runtime-config.md`](references/runtime-config.md) §
assignment_mode.

Pointers go through the configured runtime; done-when stays in Vivi. CLI: [`vivi.md`](references/vivi.md). Watch/thread: [`dual-channel.md`](references/dual-channel.md). Remote: [`ssh-remote.md`](references/ssh-remote.md).

| Vivi ≥4.6 | Use |
| --- | --- |
| `mailspace watch --once --write-cursor` | Cheap board events |
| `mail|task|need watch` | Filtered paid wait |
| `mail thread` | Multi-hop lineage |

## Remote (summary)

Host axis on slots: `host`, `ssh`, host-scoped cwd/tmux/launch. Wake/reinit **on Hand host**. One mailspace DB. [`ssh-remote.md`](references/ssh-remote.md)

## Lifecycle

1. **Arm/attach** — identities; harness; runtime binding; baseline counters; `mind_session`; **do not** arm steward unless operator asked for that fleet. Dormant-to-live procedure: [`launch.md`](references/launch.md)
2. **Focus** — map package; Hand picks open target (no GO wait)  
3. **Gather** — `fleet-sensors.py`; process new addressed mail before cadence; quiet if fingerprint/panes unchanged; doorbell/reinit; end: `fleet-cycle-close.py` (sensors → baseline → optional steward rearm) or `fleet-baseline.py bump` (+ `steward.sh rearm` **only if steward armed for that fleet**)
4. **Hand work** — show → implement → validate → unit `$polish` → done → next/sleep  
5. **Sleep** — most wakes no-ops ([`mind-cycle.md`](references/mind-cycle.md))  
6. **Detach/wind-down** — if steward was armed, `steward.sh disarm` same turn; drop idle panes  

### Polish / housekeeping

| Who | When | Scope |
| --- | --- | --- |
| Hand | End of product unit | Primary sources this unit only; serial `$polish` |
| Mind | Main git tip moved | `suggest-polish-files.py` → ≤1 task, top files, score ≥ threshold (default 500) |
| Mind | Major inflection only | One HK task To hand-1; never every land |

```bash
# <skill> and <main> are placeholders — substitute real paths
python3 <skill>/scripts/suggest-polish-files.py --repo <main> --json --limit 15
```

## Fail-fast

Exit in seconds on sensors/ops. Mode first → sensors → sleep if quiet. Autonomous: thin ops + compact report. Interactive: fail-fast ops + **rich** report. No unbounded watch. **absorb ≠ accept** — [`mind-cycle.md`](references/mind-cycle.md). Code review → Hand roles **auditor-1/2** + `$auditor`; head-cto for gate honesty only.

## Shared workspace

**Ban:** destructive git / overwrite outside scope.  
**Guidance:** dirt blocks → diff → A/B/C → act or pivot same turn. Ambiguity → `operator@` with default.

## Overlay contract

Skill = portable process. Overlay = roster, paths, models, ssh, maps, Status.

```text
.vivi/fleet.json · mind-baseline.json · FLEET_CYCLE scheduler · Head prompts · Agents.md
```

```bash
# Placeholders: <skill> <root> <hex> — tokens without <> are literals
python3 <skill>/scripts/fleet-sensors.py --project <root> --fleet <fleet-id> --text
python3 <skill>/scripts/fleet-runtime.py --project <root> --fleet <fleet-id> --role hand-1 start
<skill>/scripts/fleet-doorbell.sh --project <root> --fleet <fleet-id> --role hand-1 --handle <hex>
# Agent recovery only if doorbell sticks/errors:
<skill>/scripts/codex-reinit.sh doctor --project <root> --fleet <fleet-id> --role hand-1      # Codex
<skill>/scripts/opencode-hand-ctl.sh doctor --project <root> --fleet <fleet-id> --role hand-1  # opencode
# Cycle close: sensors → baseline → optional steward rearm in one command
python3 <skill>/scripts/fleet-cycle-close.py --project <root> --acted --summary '…'
# or: --quiet for sleep cycles; --operator-engaged resets silence
# silence: default bump increments turns_since_operator_message
python3 <skill>/scripts/fleet-baseline.py bump -p <root> --fleet <fleet-id> -s 'sleep' --quiet \
  --fingerprint-file /tmp/fleet-sensors.json
# only if human prose this turn or since last_operator_message_at:
# python3 …/fleet-baseline.py bump … --operator-engaged
# Runtime rebind: plan dry-run or atomic apply
python3 <skill>/scripts/fleet-runtime-rebind.py plan --project <root> --hands all --agent pi --provider openai-codex --model gpt-5.5 --thinking medium
python3 <skill>/scripts/fleet-runtime-rebind.py apply --project <root> --hands all --agent pi --provider openai-codex --model gpt-5.5 --thinking medium --restart
# only if operator enabled+armed steward for this fleet:
# scripts/steward.sh rearm --project <root>
```

Desktop Mind OK; Hands stay terminal/tmux. Schema: [`runtime-config.md`](references/runtime-config.md).

## Anti-patterns

- **Bag:** GO warden; severity-as-kind; sleep with product work; sleep in growth
  before an executive refill sweep; invent continuity work; dual Mind; Heads own
  bags; idle floaters despite safe parallel work; zombie campaign lanes; retire
  from idle alone; overlap write scopes without serialize/defer; wait on Head
  cadence or CEO permission for obvious spine work; omit bucket costs.
- **Process:** mail-only or pane-only truth; tmux policy; mixed Hand harnesses;
  stacked wakes; wrong-host tmux; IMAP bag sensing; unbounded watch; standby-fleet
  busywork; per-cycle dispatch memos; universal completion review; route review to
  `head-cto` instead of auditors; dispatch/refuse churn; narration mail;
  completion hidden in replies.
- **Integration:** equate packet-green with consumer-green; label integration lag
  a compiler residual; merge red themes; let Mind merge packets; treat absorb as
  accept.
- **Hygiene/workspace:** skip unit polish; polish foreign work; Mind runs polish or
  housekeeping; polish for continuity; housekeeping every land; score as merge
  gate; destructive or status-only dirt handling; topic monogamy; deep-plan every
  autonomous cycle; stay interactive forever; let `FLEET_CYCLE` force autonomous
  mode or zero turns; hand-edit silence after baseline bump; compact while
  interactive; invent autonomous report formats; freeze on CEO permission; omit
  the `FLEET_CYCLE` prefix; send status to `operator@`; skip present-on-return;
  arm steward without operator authority; leave it armed after stop-loop; use it
  as Mind; count heartbeat without a real cycle; scan global rosters; ignore
  configured `tmux_target` mappings.

## Companions / first exposure

Missing skills → [`companion-fallbacks.md`](references/companion-fallbacks.md). Package is self-contained.  
**No fleet visible on load** → brief the operator ([`getting-started.md`](references/getting-started.md) §0); do not invent attach.  
First install/init/attach: [`getting-started.md`](references/getting-started.md). Vocab: [`fleet-guide.md`](references/fleet-guide.md). Design archive: [`multi-fleet-design.md`](references/multi-fleet-design.md). Personas: [`heads/cast.md`](references/heads/cast.md) — not every cycle.
