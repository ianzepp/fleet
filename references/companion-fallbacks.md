# Companion skill fallbacks

When packaged **alone**, companions may be missing. Use these theses so Mind/Hands still behave. Prefer full skill when installed.

**Rule:** full skill loadable → use it. Else apply fallback + state which fallback in evidence.

## Mail / board CLI (`$mail` / Vivi)

**Hard dependency:** `$fleet` requires **`vivi` CLI**. No board fallback if missing — install first ([`getting-started.md`](getting-started.md)). Optional `$mail` skill ≠ binary.

**Command card:** full normal-cycle set in **[`vivi.md`](vivi.md)** — use instead of re-scanning help every action.

**Thesis:** Project mailspaces = **board of record** (tasks/needs/wants/mail). Not IMAP personal email.

```bash
vivi mailspace status --project <root>
vivi task|need|want|mail list|show|send|done --project <root> --for <id>
vivi mailspace watch --for <id> --once --write-cursor --cursor-file <path>
vivi mailspace identity add|list --project <root>
vivi mail thread <handle> --project <root>
```

**Kinds:** task=implementable; need=decision (default+options); want=non-blocking; mail=deliberation/status.

**External email (steward pages):** `vivi compose` → `vivi exec send` only when fleet preauthorizes (`dead-man.md`). Else board `operator@` only.

## Polish (`$polish`)

**Thesis:** One primary source file at a time after a product unit. Correctness → structure → hygiene for that file + tightly coupled tests/docs. Commit before next file.

| Do | Don't |
| --- | --- |
| Serial per-file; unit-scoped primaries | Repo-wide cleanup, foreign WIP, unbounded rewrites |

**Mind advisory** (no full polish by Mind) after main HEAD moves:

```bash
python3 <path-to-this-skill>/scripts/suggest-polish-files.py --repo <main> --json --limit 15
```

≤1 Hand task if score ≥ threshold (default 500). Scores = routing, not quality grades.

**Hand end-of-unit:** polish primaries this unit changed → mark done.

## Housekeeping (`$housekeeping`)

**Thesis:** Multi-phase **repo maintenance** (refresh, lint, tests, format, docs). Cost ≈ large delivery unit.

**Fleet:** Mind prepares one `implement` assignment To hand-1 only at **major inflection** (campaign complete, large multi-theme merge, stage closeout, operator ask). Never after routine lands.

**Hand fallback:** (1) prefer repo/CI commands (2) no destroy foreign dirty (3) prod/test boundary hygiene (4) lint/test/format in repo order; fix mechanical; stop on product judgment (5) commit after each successful phase (6) report residual honestly.

## Correctness (`$correctness`)

**Thesis:** Behavioral bugs — invariants, races, data-loss, fail-closed. Not style.

**Fleet:** Implementer Hands ship; **Hand auditor-1/2** (`$auditor`) for code review when Mind triages risk/sample. **head-cto** for gate honesty only.

**Fallback:** name invariant → failing test/repro → fix root cause (no weaken tests) → regression if feasible → residual risk if partial.

## Cleanliness (`$cleanliness`)

**Thesis:** Shape structure without changing intended behavior (size, boundaries, dispatch, naming, complexity).

**Fleet:** pairs with **head-cxo**. Hands may apply lightly during polish.

**Fallback:** extract helpers, guard clauses, clear modules; no drive-by architecture; no behavior change without tests.

## Campaign (`$campaign`)

**Thesis:** Routes related tracks; selects/orders **stages**; does not implement.

| Term | Meaning |
| --- | --- |
| Campaign artifact | Top-level routing document |
| Campaign stage | **Must be lowered** (planner: goal-check → delivery) before Hand implement — not a code task |

**Fallback:** treat `factory/` or goal docs as **map** (current stage, next unblocked unit, stop conditions). Mind prepares Hand assignments **only from lowered units**. No invent GO/NO-GO.

## Goal check / goal-forge (`$campaign` sub-references)

**Thesis:** Prove a goal is mid-tier implementable (READY) before delivery/factory. Forge freezes fuzzy intent first.

**Fleet:** **Lowering planner** (planner-N) owns this on assign — not the product Hand. See [`lowering.md`](lowering.md).

**Fallback:** durable goal markdown with end state, architecture locks, non-goals, acceptance, validation, first touch path; explicit READY/NOT READY.

## Delivery (`$delivery`)

**Thesis:** Compile intake into a **delivery spec** (plan only). Does not implement.

**Fleet:** produced by the **lowering planner** after goal-check READY. Mind prepares Hands from delivery **unit ids**, not from raw campaign prose.

**Fallback (single residual only):** task done-when + context = mini-spec (where, done-when, validation, out of scope). **Not** a substitute for multi-unit stage lowering.

## Factory (`$factory`)

**Thesis:** plan → implement → verify → review → commit **inside one already-scoped delivery unit**; bounded autonomy + subagents when useful.

**Hand fallback (one open task):** show task → implement in scope → targeted validate → end-of-unit polish → mark done + evidence To mind → next bag item or idle for doorbell.

Hands do **not** re-open campaign-level architecture or invent a delivery graph for an unlowered goal. Mind owns bag refill, integration clock, multi-hand packing — not a separate factory supervisor.

## Map / goal docs

```text
factory/INDEX.md
factory/goals/*.md
GOAL.md, ROADMAP.md, docs/goals/
docs/factory/*  (delivery specs after lowering)
```

**Mind:** if next stage unlowered → prepare the appropriate planner pass; if a delivery unit exists → prepare a Hand `implement` assignment citing path/id.
**Hand:** update goal checkboxes/Status only for what this unit proved.

No map → Planner lowers from operator intent, or Mind prepares only a single well-defined residual that already meets the mini-spec bar.

## Optional companions

| Missing skill | Fallback one-liner |
| --- | --- |
| **poker-face** | Re-read promises vs evidence; list unmet claims; no greenwashing |
| **bonsai** | Local readability/naming pass without behavior change |
| **red-green** | Fail a test first, then make it pass |
| **zombie-docs** | Don’t trust docs; verify against code/tests |

## Packaging checklist

Self-contained when includes:

```text
SKILL.md
agents/
references/   # including this file, fleet-guide, multi-fleet-design
scripts/      # cycle helpers + lib/env.sh + fleet_common.py
```

No required reads outside this directory.
