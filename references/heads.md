# Head loops (advisors)

Load when running **head-ceo** / **head-cto** / **head-cxo**, or triaging Head mail as Mind.

**Cast + personas:** [`heads/cast.md`](heads/cast.md), [`heads/personas/`](heads/personas/).  
Load persona only when assigning that Head for depth — not every FLEET_CYCLE.  
**Posture dial:** [`fleet-posture.md`](fleet-posture.md) — Head proactivity kind/intensity.

| Hard rule | |
| --- | --- |
| Not product lanes | No keep-screen-moving refill with map packages |
| No merge | Never own `pending_merges` |
| Progress via priority picture | Advise To mind; Mind files Hands |
| Harness | Prefer **Pi** harness, model by role (CEO/CXO → GLM 5.2, CTO → Codex 5.5) — one-shot assign→report |
| Identity | `head-*` (mail + tmux when armed) |
| Reports | **To: mind** (board only) |

See `roles-and-harness.md`. Shared finding schema: [`heads/personas/shared-operating-rules.md`](heads/personas/shared-operating-rules.md).

## Cold-boot recovery / exec warm-up

Use this when a repo or laptop is freshly recovered and the executive context
was on another machine. The goal is to warm Heads on pushed direction, not to
re-decide the company from memory.

1. Add local identities first: `head-ceo`, `head-cto`, `head-cso` when used,
   and `head-cxo`.
2. Build one assignment file per Head under `.vivi/head-assignments/` with:
   persona path, shared operating rules, exact doc packet, and the instruction
   to report **To: mind** only.
3. Prefer session-per-fleet panes for new recovery fleets: tmux session =
   `fleet_id`, window = Head identity (`<fleet>:head-ceo.1`).
4. Launch each Head with the configured high-reasoning model/harness, then use
   a doorbell or short pointer to the Vivi assignment handle. Do not paste long
   briefing bodies into the TUI argv.
5. Heads may summarize and identify gaps, but they must not edit files, file
   Hand work, or invent unpublished documents. If a remembered concept is not
   in pushed git history, report it as unrecovered.

For cold clone evidence, search git history (`git log --since ... --name-only`)
before relying on filesystem mtimes. Fresh clones make "recent file" searches
misleading.

## Posture × Head duty (summary)

| Mode | head-ceo (strategist) | head-cto | head-cxo |
| --- | --- | --- | --- |
| **growth** | Map integrity + **expansion**; inversions; side-lanes | Bugs on main + gate honesty that unblocks | Shape debt that blocks packets / invents gates |
| **standby** | Stewardship: priority/status/opt of **current** product | Correctness / reliability | Complexity that hurts on-call risk |
| **dormant** | Rarely / assign-only | Rarely / assign-only | Rarely / assign-only |

### head-coo disaster-recovery cadence (opt-in)

Top-level `disaster_recovery` is default-off and independent of `executive_cadence.every_n_loops`. When enabled with tier `inventory`, `critical`, or `regulated_or_irreplaceable`, sensors may emit `head_due_coo_dr_freshness`, `head_due_coo_dr_analysis`, or `head_due_coo_dr_restore_drill` plus overdue variants after grace. Missing block, `enabled=false`, or `tier=off` is silent.

COO DR assignments are report-only: evidence, gaps, RPO/RTO/coverage status, restore-proof status, and recommended safe next step. COO never performs backup, restore, secret access, provider setup, spend, external contact, or destructive/live recovery. Policy/config is not evidence; one Git remote or a successful backup job is never restore proof. Existing COO DR assignments suppress duplicate assignment recommendations without hiding due state. Dormant fleets with explicit critical/regulated policy keep the obligation visible but assignment may remain paused.

### Cadence spacing (configurable)

**One dial:** `executive_cadence.every_n_loops` (default L = `mind_loop.interval_sec` = 300s).

| Value | Mode |
| --- | --- |
| **0** | On-call — no scheduled `head_due_*`; explicit Mind tasks only |
| **N ≥ 1** | Scheduled — due every `N × L` seconds |

Posture defaults when N omitted under legacy `enabled: true` (prefer explicit N):

| Mode | CTO | CXO | CEO | others |
| --- | --- | --- | --- | --- |
| growth | ×6 | ×12 | ×36 | 0 |
| standby | ×18 | ×36 | ×72 | 0 |
| dormant | paused | paused | paused | paused |

No `enabled` / `self_directed` peer knobs. Sensors pause scheduled sweeps on **dormant** only. Full semantics: [`fleet-posture.md`](fleet-posture.md).

---

## head-ceo research loop (strategist seat)

Identity: `head-ceo` (legacy: `strategist` / `head-strategist`). Persona: [`heads/personas/ceo.md`](heads/personas/ceo.md).

**Job:** Connect product tracks; research misprioritization, gate honesty, inefficiencies, incorrect paths; report so Mind refills well. **Not** bag drain, not second Mind, not executive-team chair.

### Fail-fast Mind cycle (assign path)

1. Sensors: head-ceo mail (or Mind inbox for `head-ceo report:`) + baseline `head_ceo.*`
2. `awaiting_report` + no report → **do not re-assign**; note in flight; continue hands
3. Report arrived → absorb (see below); `awaiting_report=false`
4. Not awaiting + ready for new question → apply role **`assignment_mode`** (often `new`) + one assign:
   1. File assignment mail **To: head-ceo** first (handle exists)
   2. Quit/kill agent; **fresh** launch from fleet `head-ceo.agent_launch`
   3. Bootstrap: role prompt path, show assign handle, research, report **To: mind**, idle
   4. `awaiting_report=true`; record `last_reinit_at` + assign handle
5. Prefer mail for body; short tmux pointer after reinit OK
6. Reports 5–10+ min — **do not thrash** while outstanding

### Map-health / cadence sweep (self-directed when due)

When sensors emit `head_due_ceo` (`every_n_loops >= 1` and interval elapsed) and posture allows:

| Posture | Assign flavor |
| --- | --- |
| **growth** | Map-health + expansion: inversions, false/unicorn gates, parallel chains, side-lane bucket, expansion candidates |
| **standby** | Stewardship only: priority stack, status, optimization/correctness of current product, wake_triggers — **no** new campaigns |
| **dormant** | Do **not** assign from cadence |

Example growth assign body:

```text
Map-health (growth): scan campaigns/queues/ledgers/board/git.
Hunt priority_inversion, unicorn_wait, false_gate, starved_producer, parallel chains.
Name producer work for any blocked consumer. Side-lane bucket with effort/est_tokens if hand-2+.
Expansion only if honest product surface. Report To mind@ (finding schema). No polish makework.
```

Example standby assign body:

```text
Stewardship (standby): priority/status of current product only.
Optimization, correctness, reliability, wake_trigger honesty.
Do not expand product surface or invent campaigns. Report To mind@.
```

### Absorb CEO findings (Mind)

| `kind` | Mind action (growth) | standby |
| --- | --- | --- |
| **priority_inversion** / **starved_producer** | Elevate producer packet same cycle when posture allows | Stewardship fix only if on-call relevant |
| **unicorn_wait** | File decision/selector packet or demote gate | Same if risk is live |
| **false_gate** | Reopen consumer with bounded unit | Prefer leave quiet unless value clear |
| **expansion_candidate** | File or park with cost | **Ignore** (wrong posture) |
| **stewardship** | Optional | Prefer act if cheap and real |
| **side_lane bucket** | Absorb `side_lane_candidates[]` | Usually skip new parallel product |

Never invent polish because a CEO report mentioned hygiene.

### Assignment quality (anti-fragile)

Advises ownership, sequencing, seams, **gate honesty**, **misprioritization**, **side-lane capacity** — not racing the bag.

| Who | Job |
| --- | --- |
| **Mind** | Dole work; pack capacity; record est vs actual calibration |
| **head-ceo** | Priority picture + side-lane **bucket** with effort + est_tokens — not bag drain |
| **Hands** | Execute assigned targets only |

Mind needs no head-ceo permission for obvious next spine unit. head-ceo does not file Hand tasks or own empty-bag refill.

### Continuity consult (continue vs pause)

When **posture is growth** (or missing) and bags are empty **and** the map is empty / only makework / Mind cannot name a **valuable product** next unit — **do not invent polish**. Assign **one** continuity question (respect `ceo_continuity_min_hours`).

```text
Continuity: keep shipping, standby/dormant, or wind-up?
- posture today + reason
- map state (empty / residuals / stage closed)
- bag counts
Answer: continue (≤N product units with effort/est_tokens) OR recommend standby|dormant|wind-up + wake triggers.
No polish makework. Report To mind@.
```

Standby/dormant fleets: **no** continuity spam — quiet is success. Detail: [`fleet-posture.md`](fleet-posture.md).

### Side-lane / hand-2+ capacity bucket

When hand-2+ exists and posture is **growth**, reports should routinely include:

```text
## Side-lane candidates (hand-2+ if available)
- [ ] <bounded package / theme>
      why off-main: …
      seams vs hand-1 spine: …
      packet scope: …
      effort: S|M|L|XL
      est_tokens: ~N
      est_basis: one line
- [ ] …
## Do not parallelize
- <items that must stay on hand-1 / main>
## If all Hands busy
- hold / next priority after current spine
```

| `effort` | Shape | Rough `est_tokens` |
| --- | --- | --- |
| **S** | One crate/file family, clear done-when | ~50k–150k |
| **M** | Multi-file feature, normal validate | ~150k–400k |
| **L** | Multi-crate / multi-unit theme, fix loops likely | ~400k–1M |
| **XL** | Campaign-scale packet | ~1M+ (prefer split; say why) |

Bands = **routing hints**. Prefer ranges; uncertain → estimate high. **Do not omit cost** on side-lane buckets.

| Good bucket items | Bad |
| --- | --- |
| Independent factory goals, long packets, path-disjoint residuals, post-theme base-update planning | “whatever is free,” merge-to-main, same P0 as hand-1, **makework polish**, continuity theater |

### Mind: absorb bucket + cost calibration

1. Absorb into `side_lane_candidates[]` with `effort`/`est_tokens`/`est_basis`
2. Pick/file when hand-2 idle+empty; match size to free capacity + recent calibration
3. Bound → `status:bound`, `filed_handle`, `filed_at`
4. On Hand done/theme absorb → record actuals when known (`actual_source=harness|mind_estimate|unavailable`). Codex often → `unavailable` — do not invent numbers
5. Append `cost_calibration[]` `{est, actual_tokens?, actual_source, delta_ratio?, models, …}` — omit `delta_ratio` if actual unknown
6. Bias later picks with recent deltas — inform, don’t hard-block
7. Stale candidates: re-ask or drop — no thrash every quiet cycle

**head-ceo** owns estimates. **Mind** owns actuals + calibration.

| File questions about… | Do not make *core* question… |
| --- | --- |
| Who owns which seam; what hand-2+ could parallelize | “Is handle X open right now?” |
| Real stage/gate vs static overclaim | Minute-by-minute merge queue alone |
| Theme vs unit cadence; fake board deps; **priority inversion** | Assumptions mid-flight unit is done/not |
| Conditionals (“if red → …; if green → …”) | A single HEAD SHA as durable law |
| Side-lane bucket vs spine | “Fill hand-2 bag now with task Y” as if head-ceo were Mind |

**Assigns:** (1) structural question first (hours-stable) (2) optional live snapshot labeled ephemeral (3) conditionals over “do X now because bag empty” (4) Mind acts on live bag; head-ceo informs how to think + coherent parallel work (5) multi-hand growth: prefer “durable hand-2+ bucket **with effort + est_tokens**?”

**Stale assign duty:** re-read live evidence; one-line correction; answer structural question anyway.

### Campaign truth and lane-retention consult

At normal `head-ceo` cadence, or when Mind presents a
`lane_reconcile_candidate_<hand>` signal, audit the bounded campaign/factory
artifacts named by that lane. Compare claimed status to Git, board completion,
validation, release, and deploy evidence. Report `control_plane_drift` using the
CEO persona schema and recommend `keep | park | release_candidate`.

Mind absorbs the report as follows:

1. Honest map + remaining stage → fresh task/rebind; no doc churn.
2. Stale map → one bounded `$zombie-docs` repair task to an implementation Hand.
3. Complete map + no residual → run lane release gates in `mind-cycle.md`.
4. Valid blocker/defer → park with owner, wake trigger, and review condition.

The Head never edits control-plane documents, dispositions Vivi tasks, stops a
runtime, or removes a worktree.

---

## head-cto advisor loop (self-directed) — **gate honesty + architecture**

> **Model note:** head-cto uses **Pi + zai + GLM 5.2** (high or xhigh), same
> as all Heads. The unified advisor plane keeps harness coherence. Dedicated
> code review runs on `auditor-N` Hands with `$auditor`.

Identity: `head-cto`. Subject: `head-cto:`. Persona: [`heads/personas/cto.md`](heads/personas/cto.md). Legacy: correctness.

Fleet **technical gate-honesty and architecture** Head. Mind does **not** peer-review every Hand WIP. Implementer Hands own ship quality; auditor Hands own assigned code review.

**Surface: claimed gates, producer facts, architectural boundaries, and technical sequencing.** Findings → advisory report To Mind; product work remains To owning Hands.

Code review is **not** this cadence. Low-risk `done` evidence may satisfy accept; risk or sampling causes Mind to file an `auditor-N` Hand task. If head-cto refuses or is not running, that is `deferred-valid` for gate/architecture advice only — Mind records it once and retries on cadence.

1. Sensors: has-session; pane class; Mind inbox for reports; cadence `head_due_cto` (gate honesty — code review is **Hand auditor-*** not this seat)
2. Session **down** → recreate + role-prompt bootstrap (unless operator/dormant paused)
3. New report → absorb; triage task/need **To owning Hand**; doorbell if idle; baseline `head_cto.last_report_*`
4. On map-gate findings: if `false_gate` / named producer fact, feed hand-1 or CEO map-health — do not freeze merges for a stamp
5. **Do not** assign every cycle. Soft-wake if stuck idle long; cadence assign uses posture lens
6. Never map-refill as product lane
7. Do **not** act as merge GO/NO-GO or block hand-1 merges awaiting stamp

---

## head-cxo auditor loop (self-directed) — **complexity / purity**

Identity: `head-cxo`. Subject: `head-cxo:`. Persona: [`heads/personas/cxo.md`](heads/personas/cxo.md). Legacy: purity. Prefer **`assignment_mode: compact`** between passes unless the fleet sets `new`/`restart`.

**CXO ≠ operator voice.** Mind owns operator recap/email. head-cxo audits **shape debt** (including gates invented by over-coupling).

1. Sensors: has-session; pane class; report mail; cadence `head_due_cxo`
2. Down → recreate + role bootstrap (unless dormant)
3. New report → absorb; triage simplify/design To owning Hand (prefer over drive-by mid-unit rewrites); doorbell if idle + targets ready
4. Optional soft focus mail (`head-cxo assign: <area>`) — not every cycle
5. Soft-wake: honor `assignment_mode` (`compact` keep identity+role+lens → next pass; `new`/`restart` only when configured or compact fails / confused / operator asks)
6. Never map-refill. ≠ head-cto (bugs) or head-ceo (priority / often `assignment_mode: new`)
7. Never draft operator email or act as second Mind pane
