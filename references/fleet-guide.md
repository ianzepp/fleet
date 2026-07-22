# Fleet guide (first exposure)

**Audience:** human or LLM seeing multi-agent `$fleet` for the first time.  
**Cold attach / post-`/compact` order (matches SKILL):** (1) `SKILL.md` (2) this guide once for vocab (3) `getting-started.md` — §0 if no fleet visible (operator briefing), else §3 attach steps. Not every FLEET_CYCLE.

| Need | Go to |
| --- | --- |
| Install / init / re-attach | [`getting-started.md`](getting-started.md) |
| Operating law | `SKILL.md` + surface refs when *running* |

This guide = vocabulary and shape.

## What a fleet is

| Channel | Truth of… | Tool |
| --- | --- | --- |
| **Board / mail** | Work (tasks, needs, wants, status) | Project mailspace (e.g. Vivi) |
| **Panes** | Process (alive, idle, error) | tmux sessions |

Roles: **Mind / Head / Hand** — coordinator, advisors, workers.

```text
campaign / map
      │
      ▼
  MIND ──files targets──► tasking bag
      ▲                        │
      │                        ▼
      └── residuals ────── HAND clears one target

  Heads (head-ceo / head-cto / head-cxo) ──mail To: mind──► Mind triages
```

**Progress** = open tasking + honest map — not approval stamps or stage GO/NO-GO.

### Tokens

| Token | Means |
| --- | --- |
| **`HEAD`** / main tip | Git commit pointer — not the advisor role |
| **Head** / `head-*` | Advisor role — not git |
| **bag** | Open tasks+needs for an identity |
| **map** | Campaign/factory plan of packages |
| **unit** / **theme** / **packet** | Work size · multi-unit chunk · hand-2+ worktree |
| **RTM** | ready-to-merge mail signal |
| **absorb** / **accept** | Bookkeeping when moved / integration bar — canon [`mind-cycle.md`](mind-cycle.md) |
| **dirt A/B/C** | fmt · foreign semantic WIP · mixed hunks |

## Roles and identities

| Role | Job | Identity | tmux? |
| --- | --- | --- | --- |
| **Mind** | Fill bags, integrate, pane ops, cycle cadence | **`mind@…`** | **No** — operator’s current TUI |
| **Operator mail** | Human escalations while autonomous | **`operator@…`** | **No** — problems/blockers/guidance only |
| **Steward** | Dead-man: hold + page if Mind ticks stop | (watchdog) | Yes — **`steward`** (not Mind) |
| **Hand** | Execute one selected target | **`hand-1`…`hand-N`** | Yes (name = mail token) |
| **Head** | Advise; never own product bags | **`head-ceo`**, **`head-cto`**, **`head-cxo`** | Yes |

**Binding (Hands/Heads):** mail identity token == tmux session name.

**Mind and operator are not process slots.** No dual Mind; no tmux named `mind`/`operator`. `FLEET_CYCLE` runs **in the operator conversation**.

| Surface | Content |
| --- | --- |
| `operator@` | Action items for the human |
| `operator_recap` | Compact status of what moved |

On return: present operator mail list first.

**Steward:** **Default OFF.** Operator must enable + ask to arm **per fleet**. Loop ≠ steward. When armed: rearm after successful mini-cycles; trip → hold + operator@. Not a second Mind.

## Who does what

| Who | Does | Does not |
| --- | --- | --- |
| **Mind** | File/refill bags, wake/reinit, absorb (bookkeeping), branch/merge decisions, pack capacity; file/present **operator mail** | Peer-review every unit; run full `$polish`/`$housekeeping`; status To `operator@` |
| **operator@** | Accrue human problems/blockers/guidance | Status; Hand bag drain |
| **hand-N** | Execute assigned work; commit own work; validate; polish unit | Wait for GO mail; erase foreign WIP; touch another Hand's WIP |
| **head-ceo** | **Strategist:** map health, misprioritization, gate honesty; **side-lane buckets** (+ effort/token ballparks); posture-scaled | File Hand tasks; stamp GO/NO-GO |
| **head-cto** | **Gate honesty / architecture** | Own product tasking; block merges as license |
| **head-cxo** | Complexity / purity (not operator-facing) | Own product tasking; operator email |
| *optional* | `head-cpo` / `head-cso` / … (`heads/`) | Lazy Heads when needed |

**Multi-hand:** Mind **doles out** work. head-ceo **proposes** parallel hand-2+ candidates. Hands only execute assigned targets.

## Dual channel

- **Board** holds full done-when, evidence, To: ownership.
- **tmux** = **pointers only** (“show handle X; continue”).
- Runtime states: `starting`/`submitting`/`running` → no wake; `waiting_for_input`/`completed` + open bag → doorbell; `failed`/`stopped` → ops or reinit fallback.
- **opencode:** pane classification uses opencode's TUI markers (`Ask anything...` idle, `⬝` progress bar running, `▣` completed). Plain pointer doorbell with no submit-settle delay.

Mind, Hands, and Heads use **Pi by default**. Heads preserve independence through
provider/model, prompt, and role diversity; Codex and opencode remain documented
compatibility exceptions.

## Typical day (pattern)

1. **Arm** — identities, fleet config, baselines; Hands/Heads in tmux; Mind = this chat  
2. **Map focus** — campaign/factory goal names spine (+ optional side tracks)  
3. **Hands** — show one task; implement; validate; end-of-unit `$polish`; mark done  
4. **Mind cycles** — cheap sensors; act on signal; sleep when quiet  
5. **Scheduled wakes** — `FLEET_CYCLE …` (not human prose)  
6. **Mode** — engaged → **interactive**; silent cycles → **autonomous**; on return: **operator@** before recap  
7. **Integration** — Hands commit own work; Mind decides branch strategy at assignment; audit loop (implement → auditor → verify → accept) is the integration bar  
8. **Hygiene** — polish advisory after main lands; `$housekeeping` only at **major inflection**

**Keep screen moving (product only):** empty bag + map has unblocked **product** work = **starvation** → file next + wake. **Posture** (`growth` / `standby` / `dormant`): growth = aggressive Head research + expansion; standby = quiet Hands, Head **stewardship** (not expansion); dormant = Heads rare. Continuity doubt → head-ceo once, not thrash — [`posture.md`](posture.md).

**Don't get stuck:** name class (decision, dirt, pane, capacity); unstick or pivot same turn.

## Multi-hand

All Hands are equivalent floaters. The Mind picks any available Hand for each assignment. No Hand has a special integration role.

head-ceo **bucket**: parallel candidates by write scope; **effort** `S|M|L|XL` + **est_tokens**. Mind binds, files, records actual vs estimate.

Leaving hand-2 empty while map has a second unblocked track = Mind starvation of second lane.

## Tasking vocabulary

| Kind | Meaning |
| --- | --- |
| **task** | Implementable work with done-when (including defects) |
| **need** | Decision / authority — default + options |
| **want** | Non-blocking later idea |
| **mail** | Deliberation / status — not primary queue |

**To:** `hand-N`=work; `mind`=fleet board; `operator`=human escalations only.

Kind ≠ severity. Critical defects are still **tasks**.  
**Absorb** = bookkeeping when something moved. **Accept** = audit loop passed; review debt cleared — not full code review (assigned `auditor-N` Hand + `$auditor`).

## Fleet files

```text
Vivi role records        # roster, capacity, cwd, tmux bindings
.vivi/mind-baseline.json  # counters, debt, candidates, calibration
mailspace identities      # mind, hand-N, head-*
optional role prompts     # Head bootstraps
```

## Hard don’ts

1. **No second Mind** — no shell `send-keys` into fake Mind pane as control plane  
2. **No GO/NO-GO game warden** — residuals and empty bags, not stage licenses  
3. **No destructive git on foreign dirty** — classify A/B/C; never stash/reset/clean  
4. **No touching another Hand's WIP** — respect write-scope boundaries; Mind coordinates overlap  
5. **No Heads owning product bags** — advise; Mind files  
6. **No housekeeping after every land** — inflection only  
7. **No treating FLEET_CYCLE as operator silence** if human chatted between fires  
8. **No compact one-line status while interactive**

## Related skills

| Skill | Where |
| --- | --- |
| Board CLI (Vivi) | `companion-fallbacks.md` (Mail) |
| Polish / housekeeping / correctness | `companion-fallbacks.md` |
| Map / factory | `companion-fallbacks.md` (Campaign / Factory) |

## Get operational

1. [`getting-started.md`](getting-started.md) — Vivi, host, minimal fleet  
2. This guide once for vocabulary  
3. `$fleet` (`SKILL.md`) when arming / acting as Mind  
4. Open **references/** only as surface hits them  
5. Bind project overlay (identities + Vivi role records + map)  
6. Fail-fast cycles: sensors → act on signal → sleep when quiet  

## Design drafts (not ops process)

- [`multi-fleet-design.md`](multi-fleet-design.md) (design) + [`multi-fleet.md`](multi-fleet.md) (ops): session-attach; mini-cycle each fleet on `FLEET_CYCLE`; **tmux session=fleet / window=role** preferred multi-fleet hosts.
