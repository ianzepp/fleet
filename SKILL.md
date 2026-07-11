---
name: fleet
description: Multi-agent fleet management with Mind/Head/Hand roles (Abbot pattern) — Mind (operator TUI + mind@ board inbox), Hands (hand-1…hand-N) clear work, Heads (head-strategist/head-correctness/head-purity) advise; Hands share Mind harness; dual-channel Vivi+tmux; multi-lane integration. Use for hand-N fleets, codex reinit, keep-screen-moving, don't-get-stuck, FLEET_CYCLE Mind loops.
---

# Fleet

**Roles follow Abbot’s Mind / Head / Hand pattern** (see `~/work/ianzepp/abbot/README.md`: agent layer as roles under one control plane). This skill applies that pattern to a **multi-session fleet** (mail board + tmux panes), not Abbot’s in-process kernel.

| Role | Job | Canonical identity |
| --- | --- | --- |
| **Mind** | Ops: tasking, integrate, pane ops, cycle cadence | **Operator’s current TUI** + board-only mail **`mind@…`** (no tmux) |
| **Head** | Advisory research/reports, not bag drain | **`head-strategist`**, **`head-correctness`**, **`head-purity`** (mail + tmux) |
| **Hand** | Execute one selected target | **`hand-1`…`hand-N`** (mail + tmux) |

## Identity contract (canonical)

| Identity | Mail | tmux session | Notes |
| --- | --- | --- | --- |
| **mind** | `mind@<mailspace>.local` | **none** | Board inbox for To: Mind only. Process = operator TUI. |
| **hand-N** | `hand-N@…` | `hand-N` | Workers. `hand-1` merges to main; `hand-2+` packets. |
| **head-strategist** | `head-strategist@…` | `head-strategist` | Sequencing / ownership advice |
| **head-correctness** | `head-correctness@…` | `head-correctness` | Post-main code review / bug audit |
| **head-purity** | `head-purity@…` | `head-purity` | Complexity / excess-layer audit |

**Binding rule (Hands/Heads only):** mail identity token == tmux session name.  
**Mind is not a fleet process slot.** Do not create `reviewer`, dual Mind panes, or tmux for `mind`.

**Retired:** `reviewer`, `gatherer`, bare `strategist` / `correctness` / `purity` as mail ids, `hunter-N` as default (legacy camps may still use `hunter-N` / `hunters` key during migration; **new** fleets use `hand-N` / `hands`).

**Evolution:** formerly `$hunter-gatherer`. Canonical skill is **`$fleet`**.

**Process core (strong guidance):** Mind fills the tasking bag; Hand empties it. Progress is **open tasking + campaign/map**, not approval stamps.

**Multi-hand split:** **Mind** coordinates and **doles out** work (file, wake, merge clock). **head-strategist** advises sequencing and maintains a **side-lane bucket** — what **hand-2+** could run in parallel when free. Strategist does not own bag refill; Mind does not invent parallel work without map or strategist/map candidates when a second Hand sits empty.

**Keep the screen moving:** empty tasking while the map still has unblocked next work is **starvation**, not success. Operational pause is the exception.

**Don't get stuck:** freeze is the failure mode. Name why, get unstuck — never status-only “blocked” for cycles without evidence.

**Harness alignment (strong guidance):** Hands run the **same agent harness as Mind**. Heads **prefer alternate harnesses/models**.

**Mind is the operator entry point.** The harness conversation the human is in (this TUI, desktop app, or CLI) **is** Mind. There is no separate “reviewer” process. Model and reasoning tier are operator setup. Cognitive budget follows **interaction mode** (below), not guessed model id.

**Code quality ownership:** each **Hand** ships the best code it can (implement, validate, polish). **head-correctness** owns **code review on main after merge** — not Mind peer-review of every WIP/packet. Build fast, fail fast; bugs on main are fixed on main.

| Mind hygiene | When | Cost | Action |
| --- | --- | --- | --- |
| **Post-main polish advisory** | Main HEAD moved (merge / unit land) | Cheap (`suggest-polish-files.py`) | Optional bounded `$polish` **task** if scores ≥ threshold |
| **Major-inflection housekeeping** | Campaign end, large multi-theme merge, stage closeout, operator ask | **Very expensive** (full `$housekeeping`) | File **one** housekeeping **task** To hand-1 — never on routine lands |

Mind does **not** run `$polish` or `$housekeeping` itself.

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

   Heads (head-strategist / head-correctness / head-purity) ──mail To: mind──► triage into tasking
```

## When To Use

- Project-local multi-agent loops (often Vivi mailspace identities)
- Factory/campaign work with a residual finder and an implementer
- Long recurring agent wakes (5–10m) that must **fail fast** when idle
- Reframing approval stamps into residual tasks instead of stage licenses
- Fleet of Hand sessions bound to tmux panes (liveness + doorbell)
- Hands/Heads on remote hosts via SSH + tmux (same process, different host)

Do not use for ordinary personal IMAP email (`$mail`). Do not invent a second acceptance gate.

## Hard bans vs strong guidance

Reserve **hard ban** language for actions that break the platform, tree, or multi-agent contract. Soft process preferences are **strong guidance** — follow them by default, but do **not** freeze, refuse useful work, or wait on heat death of a Head when a safe default decision unblocks the camp.

| Kind | Examples |
| --- | --- |
| **Hard bans** | Destructive git on foreign/unknown dirt (`stash` / `reset` / `restore` / `clean` / force-push to “make room”); `rm -rf` of project/home trees; erasing another agent’s semantic WIP; `exec codex`/`exec grok` that destroys the tmux session |
| **Strong guidance** | Interaction mode, thorough modulus, harness alignment, head-strategist use, absorb/accept vocabulary, theme vs unit merge cadence, preferred models |
| **Not a ban** | “I might violate autonomous mode if I think hard” — if the operator is engaged or a safe default is clear, **act** |

**Decide now:** waiting multiple cycles for head-strategist / head-correctness / operator permission when a reversible default exists is a rules-of-engagement failure. File a need with default when human input is truly required; otherwise pick the default, record it, continue.

## References

**Core process lives in this file.** Detail lives in `references/` and `scripts/`.

**Mind load set:** on arm or first Mind turn, prefer loading **this file plus all of `references/`** — most Mind work touches them eventually. On a thin autonomous quiet cycle, this file alone is enough if mode/counters and last ops state are already in context; open a reference when the cycle hits that surface (pane error → dual-channel; merge → multi-lane; Head mail → heads).

| Reference / script | Load when |
| --- | --- |
| [`roles-and-harness.md`](references/roles-and-harness.md) | Arming, rebinding, duties, preferred models, Pi-as-Hand; Mind = operator session |
| [`tasking.md`](references/tasking.md) | Filing targets, queue kind, multi-hand, starvation, Hand decision continuity |
| [`dual-channel.md`](references/dual-channel.md) | Pane classes, doorbell, reinit, rehome, `/compact`, mail templates, **mailspace watch / thread** |
| [`mind-cycle.md`](references/mind-cycle.md) | Modes, cycle prefix, fail-fast, absorb/accept, **polish advisory**, **housekeeping inflection**, operator recap |
| [`multi-lane.md`](references/multi-lane.md) | Side lanes, theme→main, base-update, pin-relative, `pending_merges` |
| [`heads.md`](references/heads.md) | head-strategist / **head-correctness** / head-purity |
| [`ssh-remote.md`](references/ssh-remote.md) | Hands/Heads on another host (SSH + remote tmux); host-scoped cwd; remote reinit |
| [`runtime-config.md`](references/runtime-config.md) | Capacity ladders, baseline schema, wind-down, script env, `host`/`ssh` fields |
| [`scripts/codex-reinit.sh`](scripts/codex-reinit.sh) | Codex doctor / heal / reinit / classify (camp-agnostic; set `PROJECT`/`FLEET`) |

## Don't get stuck (strong guidance)

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

**Hard ban:** do not erase foreign/unknown uncommitted work with destructive git.  
**Strong guidance:** “foreign dirty” does **not** mean “never look, never classify, freeze for hours.” Status-only “blocked on dirt” without `git diff` is a process failure — it has burned real camp time on pure `cargo fmt` / brace moves.

| Class | What it usually is | Same-turn action |
| --- | --- | --- |
| **A — mechanical** | Formatter / pure layout after `git diff` (no semantic intent) — e.g. `cargo fmt` whitespace/braces | Style-commit in scope, or include with related work. **Not** a multi-cycle freeze. Not live multi-agent semantic WIP. |
| **B — intentional other** | Another agent’s semantic WIP, docs/factory goals, deliberate partial | Work around, narrow scope, worktree, or escalate via Vivi. **Do not erase.** Record owner/guess + age. |
| **C — mixed** | Some hunks yours, some not | Stage/commit **only own safe hunks** when possible; leave the rest; continue other targets. |

```text
git status -sb
git diff -- <path>          # mandatory before multi-cycle dirt freeze
# pure whitespace/layout after a landed commit → usually class A → clear it
# real logic/docs mid-edit by another pane → class B
```

| Role | Dirt duty |
| --- | --- |
| **Hand** | Classify A/B/C before abandoning a unit for dirt. A → clear or style-commit **same turn**. B → need/mail + **pivot**. C → own hunks only. Never destructive cleanup of B. |
| **Mind** | Same paths block spine/packet for **≥2 cycles** with no classification → **open the diff**, note class, file style residual or claim/quarantine. Track `half_dead` age; escalate, don’t restate. |
| **Either** | Second-best map targets while dirt is B-held is success. Zero commits “waiting on dirt” while other targets exist is failure. |

Formatter guidance (global Agents.md): after inspect, formatter output is intentional change to commit, not noise to freeze on.

## Roles (summary)

| Role | Job | Does not |
| --- | --- | --- |
| **Hand** (`hand-N`) | Drain own open tasks/needs; validate; mark done; polish unit sources; own ship quality | Wait for GO mail; merge packet→main (`hand-2+`); erase foreign WIP |
| **Mind** (operator TUI + `mind@`) | File targets; integrate; pane ops; refill starvation; pick side-lane work from map/strategist bucket | Stage GO/NO-GO; steal Hand unit; freeze on status-only dirty; deep code review; **tmux slot named reviewer/mind** |
| **head-correctness** | **Code review / bug hunt on main after merge** | Own product tasking bag; block merges as GO/NO-GO stamp |
| **head-strategist** | Sequencing; ownership; **hand-2+ candidate buckets** | File Hand tasks; merge; stamp accept |
| **head-purity** | Complexity / excess-layer audit | Own product tasking; merge; stamp accept |

Identity ≠ assignment ≠ runtime. Hand harness follows Mind; Heads prefer alternate runtimes. Detail: [`roles-and-harness.md`](references/roles-and-harness.md).

## Mind interaction modes (strong guidance)

Mind’s **job** (bag, dual channel, integration clock) is constant. Its **cognitive budget** is not. Mode is auto-detected from operator engagement — not from model tier. This is guidance, not a hard ban: do not refuse useful operator-facing work because a counter is awkward.

Track (write every cycle into the Mind baseline):

| Counter | Meaning |
| --- | --- |
| `quiet_streak` | Consecutive cycles with no actionable product signal |
| `turns_since_operator_message` | Mind cycles since the last **human operator** message |
| `last_operator_message_at` | Cycle id / time of last operator prose (for recap) |

**Operator message** = prose/instruction/question from the human in the Mind session (any human turn that is not a scheduled cycle injection).

**Not** operator messages:

- Scheduled cycle wakes in **this** Mind session that begin with **`FLEET_CYCLE`** (Grok `/loop`, harness scheduler, etc.)
- Hand/Head board mail, pane captures, automation boilerplate without that human intent

### Scheduled cycle prefix (required for auto-mode)

When Mind uses a harness loop/scheduler **in the operator session** (e.g. Grok `/loop 5m …`), the recurring prompt **must** begin with:

```text
FLEET_CYCLE cycle=<N> project=<root>
…rest of thin cycle instructions…
```

Do **not** implement Mind cadence by spawning a second agent pane or a shell that `send-keys` into a “reviewer” session. Loop lives where Mind lives — the operator TUI.

**Critical:** a wake whose *payload* is only `FLEET_CYCLE …` is not itself operator prose — but operator may have spoken **between** the previous cycle and this one in the same session. Mode resolution must look at **session history since `last_operator_message_at` / last cycle**, not only the current injection text. Blindly `+= 1` on every FLEET_CYCLE while ignoring intervening human chat is a mode bug.

### Mode selection

```text
# 1) Detect operator engagement (any of these → engaged)
if this turn’s user content is human prose (not FLEET_CYCLE-only):
  engaged = true
else if session history has a human message since last_operator_message_at
         (or since last_cycle_at when last_operator_message_at is null)
         that is not a FLEET_CYCLE injection:
  engaged = true   # e.g. operator asked a skill question between 5m fires
else:
  engaged = false

# 2) Apply
if engaged:
  → interactive (full reasoning allowed on operator turns; thin ops still OK on FLEET_CYCLE)
  → turns_since_operator_message = 0
  → last_operator_message_at = time of that human message (or now if this turn)
  → refresh operator_recap window
else:
  → turns_since_operator_message += 1
  → if turns_since_operator_message >= 3:
       autonomous until next operator message
     else:
       stay on prior mode; prefer autonomous when unset/ambiguous
       # turns 1–2 after operator: they may still be watching
```

Optional override (`Mind: deep` / `Mind: ops only`) beats auto-detect until cleared.

| Mode | When | Cognitive budget | **Cycle report output** |
| --- | --- | --- | --- |
| **Autonomous** | `turns_since_operator_message >= 3` with **no** human prose since last reset | **Thin ops** even if high reasoning is available. Sensors, classify, file/wake/reinit, short absorb/integration accept, fail-fast sleep. **Decide now** on reversible defaults. | **Compact:** one-line quiet or short acted headline. No fleet essay. |
| **Interactive** | Human prose this turn **or** since last cycle (even if this wake is FLEET_CYCLE), or fewer than 3 silent cycles after engagement | Full reasoning for human exchanges; ops still fail-fast (no deep peer review every cycle) | **Rich:** fuller status write-up every FLEET_CYCLE — operator is watching |

**Output follows mode, not sleep/acted alone.** Interactive + quiet in-flight still gets a readable multi-section status. Autonomous + major act still stays short (table/headline). Do not emit autonomous one-liners while `mind_mode=interactive`.

### Cycle report shape (mode-gated)

| Mode | Quiet / sleep | Acted |
| --- | --- | --- |
| **Autonomous** | One line: `cycle N … sleep` | Short headline + optional tiny table; no narrative |
| **Interactive** | **Rich status** even if no board moves: fleet table, what each Hand is doing, HEAD/dirty, open debt, why sleep | Rich + board moves, absorbs, next risk, operator_recap delta |

Detail + templates: [`mind-cycle.md`](references/mind-cycle.md).

### Operator recap buffer

After the last operator message, assume ~1–2 cycles of monitoring, then they may be gone. Keep a **compact recap** in context (and baseline if useful) of what changed since `last_operator_message_at`: merges, HEADs, filed/done handles, pane/ops events, mode flips, open debt. Survive `/compact` by re-stating the recap in the compact keep-list. When the operator returns (“catch me up”, “what happened”), answer from that buffer first — reduced detail is fine; blank amnesia is not.

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

**hand-1** = main checkout, merges to main. **hand-2+** = packet assignments, never merge to main; unit → refill; theme → ready-to-merge.

Empty product bags + map still has unblocked next work = **starvation** (file + wake same cycle). Detail: [`tasking.md`](references/tasking.md).

## Dual channel (summary)

Vivi = truth of work. tmux = truth of process. **Mail identity == tmux session name** (on the host that owns the pane).

| Pane class | Typical Mind action |
| --- | --- |
| `running` | Do not wake/reinit |
| `idle_prompt` + open tasking + **Grok** | Pointer doorbell |
| `idle_prompt`/`done_idle` + open tasking + **Codex** | **Reinit** (not stacked wakes) |
| empty + map next | Starvation — file then wake/reinit |
| `error_*` / `down` | Ops intervene / recreate |

tmux carries **pointers only**; full done-when lives in Vivi.

**Vivi ≥ 4.6 (board liveness / lineage):**

| Command | Fleet use |
| --- | --- |
| `vivi mailspace watch --for <id> --once --write-cursor` | Cheap Mind sensor for new board events (not IMAP) |
| `vivi mail\|task\|need watch …` | Kind-filtered wait / RTM / report filters |
| `vivi mail thread <handle>` | Exchange history for Mind residuals or Hand multi-hop context |

Detail: [`dual-channel.md`](references/dual-channel.md). Remote panes: [`ssh-remote.md`](references/ssh-remote.md).

## Remote Hands / Heads (summary)

Hands and Heads may run on a **different host** than Mind (SSH + remote tmux). Same roles and dual-channel rules; add a **host** axis:

- Fleet fields: `host`, `ssh`, host-scoped `cwd` / `tmux_*` / `agent_launch`
- Wake/capture/reinit run **on that host** (SSH-wrap or remote script)
- One mailspace board of record — `vivi --project` must hit the DB the camp owns
- Desktop or CLI Mind both work; remote slots improve failure isolation and machine split

Generic recipes (no particular server name): [`ssh-remote.md`](references/ssh-remote.md).

## Lifecycle

### 1. Arm

- Bag exists: identities **`mind`** (board only), **`hand-N`**, **`head-*`**
- Hands/Heads share project map; Mind is operator TUI (no mind tmux)
- Record product harness for Hands; bind every Hand’s `agent` / `wake_mode` / reinit
- Apply preferred models (see `roles-and-harness.md`)
- Tiny baselines: `last_cycle`, `quiet_streak`, `turns_since_operator_message`, `mind_mode`, fingerprints, pane classes

### 2. Select focus

- Campaign/map names current stage or package
- Hand selects one open target (oldest, priority, or map order)
- Do not wait for Mind stamp to start a selected map package

### 3. Gather

- Sensors: bag + optional **mailspace watch --once** + HEADs/dirty + pane classes (local/SSH)
- Paid path: scan what **moved**; `mail thread` when lineage matters; file residuals to owning Hand
- Quiet when fingerprint, watch cursor, and pane classes unchanged (or only `running`)
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

Skip only when the unit was docs-only / Status-only / merge-only, or operator waives. Packet workers polish **inside the packet worktree** before ready-to-merge. Mind does **not** run `$polish` for the Hand.

### Post-main polish advisory (Mind)

After **main HEAD moves** (merge, theme land, spine unit on main) — not every quiet cycle — Mind may run the polish skill’s read-only ranker:

```bash
python3 ~/work/ianzepp/skills/polish/scripts/suggest-polish-files.py \
  --repo <main_checkout> --json --limit 15
```

Scores are **churn-since-last-polish routing**, not a quality grade. If any path’s score is ≥ camp `polish_advisory.score_threshold` (default **500**), file **at most one** bounded **task** (default top **3** files) To hand-1 (or the owning Hand) to run `$polish` on those primaries only. Record `last_scan_head` so the same tip is not re-scanned every wake. Detail + caps: [`mind-cycle.md`](references/mind-cycle.md).

### Major-inflection housekeeping (Mind)

`$housekeeping` is among the **most expensive** Hand jobs (multi-phase lint/hygiene/test/docs). Mind files it **only at major inflection points**, never as a post-every-land backstop:

| File housekeeping when… | Do **not** file when… |
| --- | --- |
| Entire **campaign / factory goal** marked complete | Ordinary unit land on main |
| **Large multi-theme or multi-packet merge** batch lands | Single-package residual / one P0 family |
| Stage / delivery **closeout** on the map | Thorough cycle `% N` alone |
| Operator explicitly asks for housekeeping | Polish advisory already covering a few files |

Default: **one** open housekeeping task at a time To **hand-1** on main; record `housekeeping_advisory.last_filed_at` / head so it does not re-fire. Prefer after main is green and product bags for the closed map are empty (or operator overrides). Detail: [`mind-cycle.md`](references/mind-cycle.md).

### 5. Sleep / wake / backoff

See [`mind-cycle.md`](references/mind-cycle.md). Most wakes should be no-ops.

### 6. Retire

- Empty tasking + no next map package → stop loop or long backoff
- Operator may stop schedulers when camp is idle for hours
- Wind-down procedure: [`runtime-config.md`](references/runtime-config.md)

## Fail-fast wake (summary)

Most 5–10m wakes must **exit in seconds** on *sensors/ops*. Resolve **Mind mode** first (operator engagement + `turns_since_operator_message`). Cheap sensors next; sleep when fingerprint/panes unchanged and no starvation/error/open-tasking wake is required. In **autonomous** mode, thin ops **and** compact report. In **interactive** mode, ops stay fail-fast but the **chat report is rich** so the watching operator sees the camp. Do not unbounded-block on `mailspace watch` during fail-fast cycles.

Use **absorb** (bookkeeping) vs **accept** (integration bar — not full code review). Correctness reviews **main after merge**. Report templates by mode: [`mind-cycle.md`](references/mind-cycle.md).

## Multi-agent shared workspace

1. **Hard ban:** do not erase uncommitted work outside your allowed scope with destructive git or bulk overwrite.
2. **Strong guidance:** do not freeze on unclassified dirt — open the diff, class A/B/C, clear mechanical dirt same turn.

### Never (destructive — hard bans)

- `stash` / `reset` / `restore` / `clean` / force-push to “make room”
- Polish or rewrite another agent’s mid-flight semantic WIP
- Overwrite foreign paths with write tools just because the tree looks messy

### Always (when dirt blocks you)

```text
list paths → open diff → class A / B / C → act or pivot same turn
```

On unexpected dirt **outside** scope: do not erase — list, classify if blocking, work around or escalate. Sub-agents escalate to parent; parent escalates true ambiguity to the operator **after** filing a need with a default.

## Project overlay contract

**This skill is the portable process.** Camp files bind instances and may add product process. Prefer not to redefine bag-vs-gate, absorb vs integration-accept, don't-get-stuck, or **Harness alignment** without a recorded reason.

| Lives in skill | Lives in project overlay |
| --- | --- |
| Roles, bag rules, dual channel, fleet axes (+ host) | Concrete Hand roster, cwds, model ids, **ssh targets** |
| Harness alignment + preferred models (updated over time) | Live `mind.agent` / `agent_model` / `agent_launch`; Head launches |
| Theme vs unit, merge clock, base-update *policy* | Campaign maps, product Status, validation commands |
| Head loops (head-correctness = post-main review), cycle kinds, modes | Role-prompt paths, absolute tool binaries **per host** |
| Baseline field meanings; watch cursor; `pending_merges` states | Fat historical ledger rows, wind-up snapshots |
| Pane classes, reinit contract, wind-down; **`FLEET_CYCLE` prefix** | Scheduler prompt path, durable interval task id |
| Remote Hand/Head *transport* (SSH + tmux) | Real hostnames, keys, remote PATH wrappers |
| Generic `scripts/codex-reinit.sh` | Camp `PROJECT`/`FLEET` paths; copy/symlink **on Hand host** |

Typical camp file kinds (names/layout camp-local):

```text
fleet config           # roster + runtime + tooling + preferred models
Mind cycle baseline    # sensors + debt + mode counters + operator_recap
Mind scheduler overlay # must start wakes with FLEET_CYCLE …
Head role prompts      # head-strategist / head-correctness / head-purity
scripts/codex-reinit   # skill copy or symlink; env PROJECT + FLEET
project Agents.md      # product + multi-agent process
```

**Desktop Mind:** Mind may be a desktop app (e.g. Claude Code) while Hands stay in terminal/tmux **local or remote**. Same rule: Mind is the operator conversation, not a `reviewer` pane. Pair with remote slots: [`ssh-remote.md`](references/ssh-remote.md).

Schema detail: [`runtime-config.md`](references/runtime-config.md).

## Anti-patterns (compact)

### Bag and gates

- Mind as game warden (stage licenses, GO/NO-GO) or blocking a Hand on missing GO with no residual
- Encoding severity as queue kind (implementable merge blocker filed as `need`)
- Sleeping with empty product tasking while the map has unblocked next work
- Filing to retired identities (`hunter-N`, bare `correctness`, `reviewer`) when `hand-N` / `head-*` / `mind` are canonical; packet merges / unbounded spine on hand-2+
- Heads owning product tasking or merge queues; thrashing head-strategist assign while a report is outstanding

### Dual channel and process

- Relying on completion mail or idle pane alone
- Policy essays through tmux
- Mixed Hand harness under one Mind without explicit temporary exception
- Forcing Heads onto Mind’s harness “for uniformity”
- Stacking Codex `HAND WAKE` lines instead of reinit; `exec codex` / fragile `exec grok`
- Packet Hand with cwd still on main; unquoted `--deny` globs in zsh
- Treating local `tmux` as if it sees remote sessions; reinit on the wrong host
- Unbounded `mailspace watch` on every fail-fast cycle; using IMAP watch as the board sensor

### Integration and honesty

- Packet-green as consumer-green without pin ancestry
- “Compiler residual” when the class is integration lag
- Theme merge that creates durable red main
- Interrupting dirty hand-1 for a merge; Mind merging packets; skipping watch-scope drift
- Accepting “complete” when evidence is static/manual but claim is product-run, without saying so
- Writing “absorb” when you mean **accept**

### Hygiene and multi-agent workspace

- Combining `/compact` with assignment, or new Grok session for every theme when compact would suffice
- Skipping end-of-unit polish, or polishing foreign dirty
- Mind running full `$polish` or `$housekeeping` itself, or filing unbounded polish tasks every quiet cycle
- Filing `$housekeeping` after routine main lands or every thorough cycle (inflection-only)
- Treating polish-advisory **score** as a bug verdict or merge blocker
- Destructive git cleanup of unexpected dirt
- Status-only dirt freeze without A/B/C classification
- Treating class A (fmt/layout) as permanent foreign WIP
- Topic monogamy under blockage; silent wait for confirmation never filed
- Dumping or deeply inspecting every wake while bag/trees/panes unchanged
- Autonomous Mind deep-planning every cycle “because the model can”; treating board mail as operator engagement for mode purposes
- Skipping `turns_since_operator_message` / staying interactive forever after one early chat
- Treating FLEET_CYCLE-only payload as proof of operator silence while ignoring human chat between fires
- **Compact one-line FLEET_CYCLE reports while `mind_mode=interactive`** (operator is watching — use rich status)
- Novel-length autonomous cycle reports when a one-liner would do
- Mind acting as peer code reviewer of every packet (head-correctness owns post-main review)
- Freezing on class A formatter dirt without opening the diff
- Waiting on head-strategist for a reversible default instead of deciding now
- Scheduled wakes without a leading `FLEET_CYCLE` prefix
- Treating strong guidance as a hard ban that forbids progress
- **Reviewer / gatherer identity** as Mind: dedicated `reviewer` mail+tmux slot, shell inject into a “Mind pane,” or dual Mind processes

## Related skills

- `$mail` — Vivi project mailspace CLI (task/need/want/mail, watch, thread); not the fleet process
- `$polish` — end-of-unit per-file improvement; Mind uses `scripts/suggest-polish-files.py` for post-main advisory routing
- `$housekeeping` — full multi-phase repo maintenance; Mind files only at **major inflection** (campaign end / large merge / stage closeout)
- `$correctness` — behavioral bug / invariant audits (tool for Hand or head-correctness)
- `$cleanliness` — structure/complexity scans (pairs with head-purity work)
- `$factory` — multi-phase implementation when the Hand executes a large unit
- `$campaign` / `$delivery` — map and delivery packages the Hand drains
- `$executive-team` — broader role cast; fleet is the tasking bag-loop subset
