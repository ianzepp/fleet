---
name: fleet
description: Multi-agent fleet management with Mind/Head/Hand roles (Abbot pattern) — Mind session attaches to one or more fleets; Hands/Heads; steward dead-man; dual-channel Vivi+tmux; multi-fleet FLEET_CYCLE. Use for hand-N fleets, multi-fleet attach, codex reinit, steward arm/rearm/disarm.
---

# Fleet

Abbot **Mind / Head / Hand** roles on a **multi-session fleet** (Vivi board + tmux panes), not an in-process kernel.

| Role | Job | Identity |
| --- | --- | --- |
| **Mind** | Tasking, integrate, pane ops, cycles | Operator TUI + board **`mind@…`** (no tmux) |
| **Operator mail** | Human escalations | Board **`operator@…`** (no tmux) |
| **Head** | Advise / report — not bag drain | **`head-ceo` / `head-cto` / `head-cxo`** (+ optional org Heads) |
| **Hand** | Execute one target | **`hand-1`…`hand-N`** |

## Identity + binding

| Identity | Mail | tmux | Notes |
| --- | --- | --- | --- |
| **mind** | `mind@…` | none | Board To: Mind; process = this chat |
| **operator** | `operator@…` | none | Human only — [`operator-mail.md`](references/operator-mail.md) |
| **steward** | optional | `tmux_target` | Dead-man, not Mind — [`dead-man.md`](references/dead-man.md) |
| **hand-N** | `hand-N@…` | via `tmux_target` | `hand-1` merges to main |
| **head-*** | `head-*@…` | via `tmux_target` | ceo vision/buckets; cto post-main review; cxo purity (not operator-facing) |

| Layout | Binding |
| --- | --- |
| Single-fleet | `mail_identity == tmux_session`; target e.g. `hand-1:1.1` |
| Session-per-fleet | role mail; session=`fleet_id`; window=role; target e.g. `mgs:hand-1.1` |

**Ops always use fleet.json `tmux_target`.** No mind/operator tmux. No dual Mind process.  
**Fleet** = project root + `.vivi/`.

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
| **accept** | Integration bar (clear review debt / queue merge) — not code review | absorb; head-cto audit |
| **GO stamp** | Forbidden stage license / approval gate | Residual tasking |

Canon for absorb/accept: [`mind-cycle.md`](references/mind-cycle.md) § Absorb vs accept. Do not invent a third meaning.

| Invariant | Rule |
| --- | --- |
| Process | Mind fills bag; Hand empties. Progress = open tasking + map — not GO stamps |
| Multi-hand | Mind files/wakes/merges clock; head-ceo side-lane bucket (`effort`+`est_tokens`); Mind calibrates est vs actual |
| Starvation | Empty bag + unblocked map work → file+wake same cycle |
| Stuck | Freeze fails — name, unstick, pivot. No status-only blocked cycles |
| Harness | Hands = Mind harness; Heads prefer alternate |
| Quality | Hand ships unit quality; **head-cto** reviews **main after merge** — not Mind peer-review of every packet |
| Hygiene | Mind never runs `$polish`/`$housekeeping` itself |

| Mind hygiene | When | Action |
| --- | --- | --- |
| Polish advisory | Main **git `HEAD`** moved | Cheap ranker → ≤1 bounded `$polish` task if scores ≥ threshold |
| Housekeeping | Campaign end / large merge / stage closeout / operator | One `$housekeeping` task To hand-1 — never routine lands |
```text
map → MIND ─files→ bag → HAND clears target → residuals → MIND
       Vivi = work truth · tmux = process truth
Heads ─mail To mind→ triage · problems → operator@ · status → mind@ + recap
```

## When to use

Multi-agent project loops, factory/campaign residual+implementer, fail-fast 5–10m wakes, tmux Hands/Heads (local or SSH). **Not** personal IMAP (`$mail`); not a second acceptance gate.

## Hard bans vs guidance

| Kind | Examples |
| --- | --- |
| **Hard ban** | Destructive git on foreign dirt; erase other WIP; `exec` that kills pane session |
| **Guidance** | Mode, harness alignment, head-ceo, absorb/accept, merge cadence, models |
| **Not a ban** | “Might break autonomous” — if operator engaged or default safe, **act** |

**Decide now:** reversible default → take it. Human-only → `operator@` need/mail (default+options) + pivot.

## References

Core process here; detail in `references/` + `scripts/`.

| Context | Load |
| --- | --- |
| **Cold attach** (new session, empty context, post-`/compact` without recap) | This file + [`getting-started.md`](references/getting-started.md) §3 + [`fleet-guide.md`](references/fleet-guide.md) once for shape/vocab |
| **Hot cycle** (mode/counters/state already in context) | This file alone if quiet; open a ref when that surface hits |
| **Arm / first Mind turn on a live fleet** | This file + refs for surfaces you will touch this turn |

| Load when | Path |
| --- | --- |
| Install / init / attach | [`getting-started.md`](references/getting-started.md) |
| Vocab / shape (cold) | [`fleet-guide.md`](references/fleet-guide.md) |
| Roles / harness / models | [`roles-and-harness.md`](references/roles-and-harness.md) |
| Filing / starvation | [`tasking.md`](references/tasking.md) |
| Board CLI | [`vivi.md`](references/vivi.md) |
| Panes / wake / reinit | [`dual-channel.md`](references/dual-channel.md) |
| Modes / fail-fast / polish / HK / absorb·accept | [`mind-cycle.md`](references/mind-cycle.md) |
| operator@ | [`operator-mail.md`](references/operator-mail.md) |
| Steward | [`dead-man.md`](references/dead-man.md), [`scripts/steward.sh`](scripts/steward.sh) |
| Multi-fleet | [`multi-fleet.md`](references/multi-fleet.md) |
| Side lanes / merge | [`multi-lane.md`](references/multi-lane.md) |
| Heads | [`heads.md`](references/heads.md), [`heads/cast.md`](references/heads/cast.md) |
| Remote | [`ssh-remote.md`](references/ssh-remote.md) |
| Schema / ladders / wind-down | [`runtime-config.md`](references/runtime-config.md) |
| Missing companions | [`companion-fallbacks.md`](references/companion-fallbacks.md) |
| Sensors / baseline / doorbell | [`scripts/fleet-sensors.py`](scripts/fleet-sensors.py), [`fleet-baseline.py`](scripts/fleet-baseline.py), [`fleet-doorbell.sh`](scripts/fleet-doorbell.sh) |
| Codex pane | [`scripts/codex-reinit.sh`](scripts/codex-reinit.sh) |
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
Sleep only if bag empty **and** map has no next unblocked unit.

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
| Hand | Drain bag; validate; polish unit; ship quality | Wait for GO; merge to main (hand-2+); erase foreign WIP |
| Mind | File/wake/integrate/starve-refill; operator mail | GO stamps; steal unit; deep code review; mind/operator tmux |
| operator@ | Human escalations | Status; bag drain |
| head-cto | Post-main review | Own product bag; GO stamp |
| head-ceo | Vision; side-lane buckets | File Hand tasks; merge |
| head-cxo | Complexity/purity | Product bag; operator mail |

Identity ≠ assignment ≠ runtime. Detail: [`roles-and-harness.md`](references/roles-and-harness.md).

## Mind modes (guidance)

Job fixed; **budget** follows engagement (not model id). Write every cycle:

| Counter | Meaning |
| --- | --- |
| `quiet_streak` | Cycles with no product signal |
| `turns_since_operator_message` | Cycles since last **human** prose |
| `last_operator_message_at` | For recap window |

**Operator message** = human prose in this session. **Not:** `FLEET_CYCLE…` injections, board mail, pane captures.

### FLEET_CYCLE prefix (required)

```text
FLEET_CYCLE project=/path/to/fleet …
FLEET_CYCLE fleets=mgs,faber project=/path/mgs also=/path/faber …
```

Loop lives in the operator TUI — no fake Mind pane. Multi-fleet: mini-cycle **each** named fleet; own tick + `steward.sh rearm --project <root>`.  
**Bug:** `FLEET_CYCLE`-only payload ≠ silence — count human chat **between** fires.

```text
engaged = human prose this turn OR since last_operator_message_at (not FLEET_CYCLE)
if engaged: interactive; silence=0; present operator@ if N>0; refresh recap
else: silence += 1; silence≥3 → autonomous (else keep prior; turns 1–2 may still watch)
```

Override: `Mind: deep` / `Mind: ops only`.

| Mode | Budget | Report |
| --- | --- | --- |
| **Autonomous** (silence≥3) | Thin ops; decide-now defaults | Compact one-liner / short headline |
| **Interactive** | Full human reasoning; fail-fast ops | **Rich** every FLEET_CYCLE (even quiet) |

Report tracks **mode**, not acted/sleep alone. Templates: [`mind-cycle.md`](references/mind-cycle.md).

**Recap:** compact deltas since last operator (git tips, handles, panes, mode, debt). Re-seed after `/compact`.

### Multi-fleet / steward / operator@

| Topic | Rule |
| --- | --- |
| Multi-fleet | One Mind session may supervise many fleets; **one Mind per fleet** (advisory `mind_session`); fleets= on FLEET_CYCLE line; prefer session=`fleet_id` |
| Steward | Per-fleet success-tick watchdog. **rearm** every mini-cycle; **arm** with loop; **disarm** same turn on detach. Trip → hold + operator@ + optional email. Not second Mind |
| operator@ | Problems / blockers / bug-guidance / human walls only. On return: operator list **first**, then recap, then ops |

## Tasking (summary)

| Kind | Use |
| --- | --- |
| task | Implementable + done-when (incl. critical defects) |
| need | Decision — default+options |
| want | Non-blocking later |
| mail | Deliberation — not primary queue |

Kind ≠ severity. Hard stop = open tasks/needs. Not a stop = missing GO mail.  
hand-1 = main + merges; hand-2+ = packets, never main merge; unit done → refill; theme done → RTM mail.  
Starvation: empty product bag + map next → file+wake. [`tasking.md`](references/tasking.md)

## Dual channel (summary)

Vivi = work. tmux = process. Address = **`tmux_target`**.

| Pane class | Action |
| --- | --- |
| `running` | No wake |
| `idle_prompt` + open + Grok | Pointer doorbell |
| idle/done + open + Codex | **Reinit** (not stacked wakes) |
| empty + map next | Starve-file then wake |
| `error_*` / `down` | Ops / recreate |

Pointers only in tmux; done-when in Vivi. CLI: [`vivi.md`](references/vivi.md). Watch/thread: [`dual-channel.md`](references/dual-channel.md). Remote: [`ssh-remote.md`](references/ssh-remote.md).

| Vivi ≥4.6 | Use |
| --- | --- |
| `mailspace watch --once --write-cursor` | Cheap board events |
| `mail|task|need watch` | Filtered paid wait |
| `mail thread` | Multi-hop lineage |

## Remote (summary)

Host axis on slots: `host`, `ssh`, host-scoped cwd/tmux/launch. Wake/reinit **on Hand host**. One mailspace DB. [`ssh-remote.md`](references/ssh-remote.md)

## Lifecycle

1. **Arm/attach** — identities; harness; `tmux_target`; baseline counters; `mind_session`; steward arm if looping  
2. **Focus** — map package; Hand picks open target (no GO wait)  
3. **Gather** — `fleet-sensors.py`; quiet if fingerprint/panes unchanged; doorbell/reinit; end: `fleet-baseline.py bump` + `steward.sh rearm`  
4. **Hand work** — show → implement → validate → unit `$polish` → done → next/sleep  
5. **Sleep** — most wakes no-ops ([`mind-cycle.md`](references/mind-cycle.md))  
6. **Detach/wind-down** — `steward.sh disarm` same turn; drop idle panes  

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

Exit in seconds on sensors/ops. Mode first → sensors → sleep if quiet. Autonomous: thin ops + compact report. Interactive: fail-fast ops + **rich** report. No unbounded watch. **absorb ≠ accept** (bookkeeping vs integration bar) — [`mind-cycle.md`](references/mind-cycle.md). **head-cto** post-main code review.

## Shared workspace

**Ban:** destructive git / overwrite outside scope.  
**Guidance:** dirt blocks → diff → A/B/C → act or pivot same turn. Ambiguity → `operator@` with default.

## Overlay contract

Skill = portable process. Overlay = roster, paths, models, ssh, maps, Status.

```text
.vivi/fleet.json · mind-baseline.json · FLEET_CYCLE scheduler · Head prompts · Agents.md
```

```bash
# Placeholders: <skill> <root> <hex> — tokens without <> are literals (--text, rearm, …)
python3 <skill>/scripts/fleet-sensors.py --project <root> --text
python3 <skill>/scripts/fleet-sensors.py --project <root>   # JSON default
<skill>/scripts/fleet-doorbell.sh --project <root> hand-1 --handle <hex>
python3 <skill>/scripts/fleet-baseline.py bump -p <root> -s 'sleep' --quiet \
  --fingerprint-file /tmp/fleet-sensors.json
scripts/steward.sh rearm --project <root>
```

Desktop Mind OK; Hands stay terminal/tmux. Schema: [`runtime-config.md`](references/runtime-config.md).

## Anti-patterns

**Bag:** GO warden; severity-as-kind; sleep while map has work; dual Mind; Heads own bags; hand-2 empty while side track exists; wait on head-ceo for obvious spine; buckets without cost ballparks.  
**Process:** mail-only or pane-only truth; policy via tmux; mixed Hand harness; Codex wake stacks; wrong-host tmux; IMAP as bag sensor; unbounded watch.  
**Integrate:** packet-green≠consumer-green; “compiler residual” when integration lag; red theme merge; Mind merges packets; absorb-as-accept.  
**Hygiene/workspace:** skip unit polish / polish foreign; Mind runs polish/HK; HK every land; score as merge gate; destructive dirt cleanup; status-only dirt; topic monogamy; deep-plan every autonomous cycle; interactive forever; FLEET_CYCLE as silence; compact report while interactive; novel autonomous reports; head-ceo permission freeze; missing FLEET_CYCLE prefix; status→operator@; skip operator present-on-return; no steward disarm; steward as Mind; inject-only heartbeat; global roster scan; hardcode session=role when `tmux_target` set.

## Companions / first exposure

Missing skills → [`companion-fallbacks.md`](references/companion-fallbacks.md). Package is self-contained.  
First install/init/attach: [`getting-started.md`](references/getting-started.md). Vocab: [`fleet-guide.md`](references/fleet-guide.md). Design archive: [`multi-fleet-design.md`](references/multi-fleet-design.md). Personas: [`heads/cast.md`](references/heads/cast.md) — not every cycle.
