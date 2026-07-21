# Goal lowering (planner → delivery → Hand)

**Invariant:** Product Hands implement **already-lowered** delivery units. They do
**not** absorb raw campaign goals and invent factory/delivery/architecture on
the fly.

Mind owns the **file clock**. One **planner** owns the **lowering** of a selected
campaign goal through planning skills into durable documents. Only those
documents become Hand tasks.

**Batch-ahead (required):** when a goal is defined (or selected for execution),
Mind runs it through lowering for a **horizon of phases/units immediately** —
not one phase at a time after each Hand close. Pre-work must exist before
implement need; idle Hands with an unlowered defined goal is a process failure.

---

## Forbidden path (the gap)

```text
campaign goal / stage bullet
  → Mind task To hand-N
  → Hand expected to goal-forge, goal-check, delivery, factory, and implement
```

That path dumps architectural judgment onto volume implementers (often low
thinking). Result: green self-authored tests, missing invariants, “model looks
dumb.”

### Also forbidden: just-in-time single-phase lower

```text
define goal
  → lower only phase 1
  → Hand completes phase 1
  → only then lower phase 2
  → … repeat
```

That path leaves the fleet quiet with no ready unit backlog. Definition time is
when planning pre-work happens, not when a Hand goes empty.

## Required path

```text
campaign map selects goal / stage
  → Mind assigns **lower** To one planner (default: planner-1)
       scope: whole goal readiness + delivery graph for a **horizon** of phases
       (default 3–5 phases/units of a longer goal — not only the next one)
  → Planner runs planning stack → durable artifacts on disk
       goal-forge (if goal not frozen)
       → goal-check → READY
       → $delivery → delivery spec + ordered unit graph for the horizon
  → Planner reports To mind: artifact paths, READY verdict, unit list, non-goals
  → Mind accepts lowering (or sends back with named gaps)
  → Mind files **mechanical** / **repair** tasks To Hands from the ready bag
       each task cites delivery unit id + path; mini-spec may quote done-when
  → Hands implement + polish; no re-architecture of the goal
  → While Hands drain the bag, Mind extends the horizon (next 3–5) before empty
```

| Actor | Owns | Does not |
| --- | --- | --- |
| **Mind** | Select what to lower; assign planner with horizon size; accept/reject; file Hand units from docs; merge clock; keep bag ahead of implement | Invent architecture inside Hand task bodies as a substitute for delivery; JIT single-phase lower after each Hand close |
| **Lowering planner** (one seat) | Goal readiness + delivery docs for the assigned goal **horizon** (multi-phase unit graph) | Product code; merge; filing Hand bags; unbounded multi-**goal** campaign lowers |
| **Implementer Hand** | Execute one delivery unit (or repair list) | Re-lower the campaign; rewrite architecture; open-ended factory on raw goals |
| **Auditor Hand** | Post-land invariant review | Planning / delivery authorship |
| **head-cto / head-cxo** | Gate honesty / purity (cadence, advisory) | Not a lowering seat; Heads are advisory-only |

---

## When lowering is mandatory

| Intake | Lower first? |
| --- | --- |
| New campaign stage / theme / North-Star slice with no READY goal + delivery | **Yes** — batch-ahead horizon, not only phase 1 |
| Goal defined / selected for execution; fewer than ~3 ready units remain ahead | **Yes** — horizon extension (overlap with implement) |
| Goal exists but stale or not goal-check READY | **Yes** (re-check / re-delivery for the horizon) |
| Delivery unit already on disk; Mind filing next slice from that graph | **No** — file Hand from existing unit |
| **`repair`** from auditor findings + regressions | **No** — findings *are* the spec |
| Pure merge / base-update / maid / housekeeping | **No** |
| True **design** / **sensitive** product shape (voice, IA users feel) | Lower may still produce contracts; **implement** design-class work on design Hand (e.g. hand-5) — not volume Hand guessing |

Starvation refill must **not** file raw campaign bullets To Hands. If the next map
item is unlowered → assign **lower** to a planner, not implement. Prefer that lower never
becomes starvation: horizon should already be on disk before Hands empty.

---

## Horizon (batch-ahead lowering)

| Rule | Detail |
| --- | --- |
| **Trigger** | Goal is **defined** or **selected for execution** — not “Hand needs the next phase” |
| **Default horizon** | **3–5** phases/units of a longer graph in one lower assignment |
| **Long goals** | A 10-phase goal does **not** require all ten lowered at once; lower the next horizon and extend before the bag goes empty |
| **Short goals** | If the whole goal is ≤ horizon size, lower the **entire** goal in one assignment |
| **Overlap** | Extend when remaining unstarted ready units drop toward **~1–2** (or half the last horizon is done) — while Hands still work |
| **Still one owner** | One Head, one goal (or coherent stage theme) per lower mail — multi-**phase** horizon is expected; multi-**goal** campaign dump is not |

Lowering is **planning pre-work**. Implement capacity is wasted when definition
already exists but no delivery units are ready.

---

## Lowering planner: write scope

Advisory Heads are normally report-only. The **lowering planner** is a Hand
with planning duty and an explicit write scope for **planning artifacts only**:

| May write | Must not write |
| --- | --- |
| `GOAL.md` / `factory/goals/*` / campaign-named goal docs | Product source (`src/`, runtime, CLI implement) |
| `$delivery` specs, stage graphs, unit checklists under `docs/factory/` or project convention | Packet product branches as implementer |
| Goal-check notes / READY verdict in-repo if project stores them | Hand tasks, merge, destroy foreign dirty |

If the project forbids planner writes entirely, the planner emits full artifact text in
the report and the Mind materializes to disk **before** filing Hands — same bar,
different scribe. Prefer planner-written planning files when git-backed docs are
the handoff.

**One goal (or coherent stage theme) per assignment** — with a **multi-phase
horizon** inside that goal. Do **not** ask the planner to lower the whole multi-goal
campaign in one mail. Do **not** restrict the assignment to a single phase when
the goal already has (or should have) a multi-phase delivery graph.

---

## Artifact bar (goal-check → delivery)

Lowering is incomplete until:

1. **Goal artifact** exists for the focused target.
2. **goal-check** (under `$campaign`) would return **`READY`** for consumer `delivery` or
   `factory` (end state, architecture locks, boundaries, acceptance, validation,
   implementation path — no material guessing).
3. **`$delivery`** produced a **delivery spec** with ordered units for the
   **horizon** (done-when, write scope, validation, non-goals per unit or stage).  
4. Report lists **paths** + **implementable unit ids** for the whole horizon
   Mind can file (not only “next unit”).

`NOT READY` → Mind does not file Hands; re-assign lower with named gaps or
return to goal-forge.

Skill detail: `$campaign` (sub-refs: `goal-forge`, `goal-check`), `$delivery`. Fallback if skills
missing: same structure in durable markdown; do not skip the bar.

---

## Mind filing from delivery

Each Hand **task** for product implement:

- Tag: usually `mechanical` (or `design` To design Hand when the *unit* is design).  
- Body: delivery unit id + path; done-when; write scope; invariants; validation.  
- **No** “see campaign GOAL and figure it out.”  
- Optional: one-line pointer to parent goal for context — delivery unit remains
  the authority for done-when.

Volume / low–medium thinking Hands are legal **only** after this bar. Loose
Mind mini-specs that re-encode architecture are not a substitute for delivery
docs on multi-unit stages.

---

## Interaction with Head duties

| Role | Relation to lowering |
| --- | --- |
| **head-ceo** | Advisory on cadence: map health, priority, side-lane candidates. May recommend goals for planning; does not own lowering. |
| **head-cto** | May refuse honesty of a lowered gate later; does not replace goal-check |
| **head-cxo** | May flag unearned complexity in a delivery shape; does not own lowering |

Cadence sweeps (map integrity, purity, gate honesty) are **advisory**. They are
not lowering and are not a required step in the production line. Lowering is
**assign-only** to a planner when Mind selects a goal/stage to execute — and at
selection time the assignment is **horizon batch-ahead**, not single-phase JIT.

---

## Anti-patterns

- Campaign → Hand “run factory on this goal”  
- Hand invents delivery graph inside the implement turn  
- Mind starvation-fills unlowered stages as implement tasks  
- **Just-in-time single-phase lower** (wait for Hand close before any next-phase pre-work)  
- Goal defined for days with zero ready delivery units while Hands sit idle  
- Lowering planner implements product code "while here"  
- Multiple planners lowering the same goal in parallel without a single owner  
- Filing Hands on `NOT READY` goals because a Hand is idle  
- Dumping an entire multi-goal campaign into one lower mail (horizon is multi-**phase**, not multi-**goal**)  

---

## Related

- [`model-selection.md`](model-selection.md) — well-defined packet; unit tags  
- [`tasking.md`](tasking.md) — board kinds; Hand vs need  
- [`companion-fallbacks.md`](companion-fallbacks.md) — campaign / delivery / factory theses  
- [`heads.md`](heads.md) — Head loops; lowering seat exception  
- Skills: `$campaign` (sub-refs: `goal-forge`, `goal-check`), `$delivery`, `$factory`
