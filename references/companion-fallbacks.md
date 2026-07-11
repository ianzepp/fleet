# Companion skill fallbacks

When this skill is packaged **alone**, companion skills may be missing. Use
**these short theses** so Mind/Hands still behave correctly. Prefer the full
skill when it is installed (`$polish`, `$housekeeping`, etc.).

**Rule:** if a full skill is loadable, use it. If not, apply the fallback here
and state in evidence which fallback you used.

---

## Mail / board CLI (`$mail` / Vivi)

**Thesis:** Project mailspaces are the **board of record** for tasks/needs/wants/mail.
Not IMAP personal email.

**Fleet needs (commands):**

```bash
vivi mailspace status --project <root>
vivi task|need|want|mail list|show|send|done --project <root> --for <id>
vivi mailspace watch --for <id> --once --write-cursor --cursor-file <path>
vivi mailspace identity add|list --project <root>
```

**Kinds:** task = implementable; need = decision (default + options); want = non-blocking; mail = deliberation/status.

**External email (steward pages):** `vivi compose` → `vivi exec send` only when fleet preauthorizes (see `dead-man.md`). Otherwise use board `operator@` only.

---

## Polish (`$polish`)

**Thesis:** Improve **one primary source file at a time** after a product unit.
Correctness → structure → hygiene, only for that file and tightly coupled tests/docs.
Commit cohesive polish before the next file.

**Do:** serial per-file; unit-scoped primaries only.  
**Don't:** repo-wide cleanup, foreign WIP, unbounded architecture rewrites.

**Mind advisory (no full polish by Mind):** after main HEAD moves, rank churn:

```bash
python3 <path-to-this-skill>/scripts/suggest-polish-files.py --repo <main> --json --limit 15
```

File at most one Hand task for top files if score ≥ threshold (default 500). Scores are routing, not quality grades.

**Hand end-of-unit:** list primary sources this unit changed → polish those only → then mark task done.

---

## Housekeeping (`$housekeeping`)

**Thesis:** Multi-phase **repo maintenance** (refresh, lint/hygiene, tests, format, docs).
Very expensive — similar cost to a large delivery unit.

**Fleet:** Mind **files** one task To hand-1 only at **major inflection** (goal/campaign complete, large multi-theme merge, stage closeout, operator ask). Never after routine lands.

**Fallback process for Hand:**

1. Prefer repo/CI documented commands.
2. Do not destroy foreign dirty.
3. Hygiene: production/test boundary (no unwrap/panic in non-test prod code if repo bans them).
4. Run lint/test/format in the order the repo uses; fix mechanical failures; stop on product judgment.
5. Commit after each successful phase when the tree changed.
6. Report residual honestly.

---

## Correctness (`$correctness`)

**Thesis:** Hunt **behavioral bugs** — invariants, races, data-loss, fail-closed gaps.
Not style. Not “docs look fine.”

**Fleet:** Hands and **head-cto** use this lens. head-cto owns post-main review; Hands ship the best unit they can.

**Fallback process:**

1. Name the invariant or contract under test.
2. Prefer failing tests or reproduction over vibes.
3. Fix root cause; don’t weaken tests to green.
4. Cover the bug with a regression when feasible.
5. Report residual risk if scope was partial.

---

## Cleanliness (`$cleanliness`)

**Thesis:** Shape **structure** without changing intended behavior — size, boundaries,
dispatch, naming, comment quality, complexity.

**Fleet:** Pairs with **head-cxo** (complexity/purity). Hands may apply lightly during polish.

**Fallback process:** prefer extract helpers, guard clauses, clear modules; avoid drive-by architecture; no behavior change without tests.

---

## Campaign (`$campaign`)

**Thesis:** A **campaign artifact** routes multiple related tracks. It selects and
orders **campaign stages**; it does not implement code.

| Term | Meaning |
| --- | --- |
| Campaign artifact | Top-level routing document |
| Campaign stage | Lowers to delivery and/or factory work — not a code task |

**Fleet fallback:** if no campaign skill, treat `factory/` or repo goal docs as the **map**: current stage, next unblocked unit, stop conditions. Mind files Hand tasks from that map. Don’t invent GO/NO-GO gates.

---

## Delivery (`$delivery`)

**Thesis:** Compile messy intake into a **delivery spec** (plan only). Does not implement.

**Fleet fallback:** a task’s done-when + context **is** the mini-spec. Include: where, done-when, validation, out of scope. Mind writes that into Vivi task bodies.

---

## Factory (`$factory`)

**Thesis:** Execute multi-phase work: plan → implement → verify → review → commit, with
bounded autonomy and subagents when useful.

**Fleet fallback:** Hands implement **one open task** at a time with:

1. Show task / clarify done-when  
2. Implement in allowed scope  
3. Targeted validate  
4. End-of-unit polish (fallback above)  
5. Mark done + evidence To mind  
6. Next bag item or idle for Mind doorbell  

Mind owns bag refill, integration clock, and multi-hand packing — not a separate factory supervisor process.

---

## Map / goal docs (no skill required)

Prefer repo paths when present:

```text
factory/INDEX.md
factory/goals/*.md
GOAL.md, ROADMAP.md, docs/goals/
```

**Mind:** pick unblocked next unit; file task To Hand; absorb Status when criteria hold.  
**Hand:** update goal checkboxes/Status only for what this unit proved.

If no map exists, Mind files from operator intent or head-ceo sequencing, still as concrete tasks with done-when.

---

## Optional companions (brief)

| Missing skill | Fallback one-liner |
| --- | --- |
| **poker-face** | Re-read promises vs evidence; list unmet claims; no greenwashing |
| **bonsai** | Local readability/naming pass without behavior change |
| **red-green** | Fail a test first, then make it pass for serious coverage work |
| **zombie-docs** | Don’t trust docs; verify claims against code/tests |

---

## Packaging checklist

This skill directory is self-contained when it includes:

```text
SKILL.md
agents/
references/   # including this file, fleet-guide, multi-fleet-design
scripts/      # steward, codex-reinit, fleet-sensors, fleet-baseline, fleet-doorbell, suggest-polish-files
```

No required reads outside this directory.
