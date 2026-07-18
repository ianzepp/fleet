# Goal lowering (Head → delivery → Hand)

**Invariant:** Product Hands implement **already-lowered** delivery units. They do
**not** absorb raw campaign goals and invent factory/delivery/architecture on
the fly.

Mind owns the **file clock**. One Head owns the **lowering** of a selected
campaign goal (or stage) through planning skills into durable documents. Only
those documents become Hand tasks.

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

## Required path

```text
campaign map selects goal / stage
  → Mind assigns **lower** To one Head (default: head-ceo; fleet may pin another)
  → Head runs planning stack → durable artifacts on disk
       goal-forge (if goal not frozen)
       → goal-check → READY
       → $delivery → delivery spec + unit graph
  → Head reports To mind: artifact paths, READY verdict, unit list, non-goals
  → Mind accepts lowering (or sends back with named gaps)
  → Mind files **mechanical** / **repair** tasks To Hands
       each task cites delivery unit id + path; mini-spec may quote done-when
  → Hands implement + polish; no re-architecture of the goal
```

| Actor | Owns | Does not |
| --- | --- | --- |
| **Mind** | Select what to lower; assign Head; accept/reject; file Hand units from docs; merge clock | Invent architecture inside Hand task bodies as a substitute for delivery |
| **Lowering Head** (one seat) | Goal readiness + delivery docs for the assigned goal/stage | Product code; merge; filing Hand bags; unbounded multi-goal lowers |
| **Implementer Hand** | Execute one delivery unit (or repair list) | Re-lower the campaign; rewrite architecture; open-ended factory on raw goals |
| **Auditor Hand** | Post-land invariant review | Planning / delivery authorship |
| **head-cto / head-cxo** | Gate honesty / purity (cadence) | Default lowering seat (unless fleet pins them) |

---

## When lowering is mandatory

| Intake | Lower first? |
| --- | --- |
| New campaign stage / theme / North-Star slice with no READY goal + delivery | **Yes** |
| Goal exists but stale or not goal-check READY | **Yes** (re-check / re-delivery) |
| Delivery unit already on disk; Mind filing next slice from that graph | **No** — file Hand from existing unit |
| **`repair`** from auditor findings + regressions | **No** — findings *are* the spec |
| Pure merge / base-update / maid / housekeeping | **No** |
| True **design** / **sensitive** product shape (voice, IA users feel) | Lower may still produce contracts; **implement** design-class work on design Hand (e.g. hand-5) — not volume Hand guessing |

Starvation refill must **not** file raw campaign bullets To Hands. If the next map
item is unlowered → assign **lower**, not implement.

---

## Lowering Head: write scope exception

Advisory Heads are normally report-only. The **lowering seat** is an explicit
exception for **planning artifacts only**:

| May write | Must not write |
| --- | --- |
| `GOAL.md` / `factory/goals/*` / campaign-named goal docs | Product source (`src/`, runtime, CLI implement) |
| `$delivery` specs, stage graphs, unit checklists under `docs/factory/` or project convention | Packet product branches as implementer |
| Goal-check notes / READY verdict in-repo if project stores them | Hand tasks, merge, destroy foreign dirty |

If the project forbids Head writes entirely, Head emits full artifact text in
the report and Mind materializes to disk **before** filing Hands — same bar,
different scribe. Prefer Head-written planning files when git-backed docs are
the handoff.

**One goal/stage per assignment.** Do not ask the Head to lower the whole
campaign in one mail.

---

## Artifact bar (goal-check → delivery)

Lowering is incomplete until:

1. **Goal artifact** exists for the focused target.  
2. **`$goal-check`** would return **`READY`** for consumer `delivery` or
   `factory` (end state, architecture locks, boundaries, acceptance, validation,
   implementation path — no material guessing).  
3. **`$delivery`** produced a **delivery spec** with ordered units (done-when,
   write scope, validation, non-goals per unit or stage).  
4. Report lists **paths** + **first implementable unit ids** Mind can file.

`NOT READY` → Mind does not file Hands; re-assign lower with named gaps or
return to goal-forge.

Skill detail: `$goal-check`, `$goal-forge`, `$delivery`. Fallback if skills
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

## Interaction with other Head duties

| Role | Relation to lowering |
| --- | --- |
| **head-ceo** | Default **lowering seat** when fleet does not pin another; also map health / side-lane bucket (advisory) |
| **head-cto** | May refuse honesty of a lowered gate later; does not replace goal-check |
| **head-cxo** | May flag unearned complexity in a delivery shape; does not own default lower |

Cadence sweeps (map integrity, purity, gate honesty) are **not** automatic
lowering. Lowering is **assign-only** when Mind selects a stage to execute.

---

## Anti-patterns

- Campaign → Hand “run factory on this goal”  
- Hand invents delivery graph inside the implement turn  
- Mind starvation-fills unlowered stages as implement tasks  
- Lowering Head implements product code “while here”  
- Multiple Heads lowering the same goal in parallel without a single owner  
- Filing Hands on `NOT READY` goals because a Hand is idle  

---

## Related

- [`model-selection.md`](model-selection.md) — well-defined packet; unit tags  
- [`tasking.md`](tasking.md) — board kinds; Hand vs need  
- [`companion-fallbacks.md`](companion-fallbacks.md) — campaign / delivery / factory theses  
- [`heads.md`](heads.md) — Head loops; lowering seat exception  
- Skills: `$goal-forge`, `$goal-check`, `$delivery`, `$factory`, `$campaign`
