# Cold boot — rebuilding fleet memory when there is no Vivi history

Cold boot is what a Mind does to **understand an environment that has real
history but no institutional memory**, and to seed the memo set from durable
sources. It is not structural setup and it is not normal attach.

## When this applies

| Trigger | Example |
| --- | --- |
| **Lost Vivi store** | OS reinstall, new machine, migrated ops, corrupted DB — repo + git history survive, `.vivi/` memos do not |
| **First fleet management** | An existing codebase with READMEs, planning docs, and commit history is placed under fleet management for the first time |

Distinguish from:

- [`getting-started.md`](getting-started.md) — **structural setup on disk**:
  install, init the mailspace, add identities, start panes. Cold boot runs after
  (or alongside) that, to understand the environment.
- Normal cold-attach ([`getting-started.md`](getting-started.md) §3) — **loading
  an existing memo set**. Cold boot is what you do when that set is empty or thin.

Signal: the mailspace has no/thin memos, but the repo has real orientation docs,
planning artifacts, and commit history.

## Principle

Rebuild a **small seed memo set from durable sources**. Never try to "catch up"
by recording current cycles. The goal is a cold-boot context snapshot — the
handful of facts a future Mind needs to act — not a replay of history.

Transient cycle/routing state stays in loop-state/baseline, **never** in memos.
See `SKILL.md` § *Mind memory* and [`mind-cycle.md`](mind-cycle.md) § *Mind memo
checkpoint*.

## Durable sources to mine (priority order)

1. **Repo orientation** — root `README.md`, `AGENTS.md` / workspace docs, repo
   boundaries and tiers.
2. **Intent and plans** — `factory/INDEX.md`, `factory/goals/*`, campaign and
   delivery specs, `PLANNING.md` / roadmaps.
3. **Architecture and authority** — route maps, crate/repo seams, the authority
   model, the non-negotiable invariants.
4. **History** — recent `git log` subjects, active branches, last merge/deploy,
   per-repo `git status`.
5. **Decisions** — `DECISIONS`, `records/`, ADRs, archived notes.
6. **Surviving live state** — exported tasks/needs if any, outstanding operator
   mail.

## The seed memo set (mind)

Write **one memo per durable fact**, each a checklist line, not a paragraph:

- **Thesis/intent** — what this fleet is for; current posture.
- **Lanes and ownership** — which repo/Hand owns what; main vs packet lanes.
- **Invariants and authority model** — the non-negotiables (identity/state/
  agents/mail/files seams; binary-only boundaries; no-cross-tenant rules).
- **Active campaigns/goals** — what is in flight and the current critical path.
- **Intentional defers** — valid pauses and the reason.
- **Key decisions/defaults** — operator policy currently in force.

Aim for roughly **6–12 seed memos**. If you are writing 50+, you are recording,
not seeding. Heads seed their own lens memory (cto = correctness invariants,
ceo = map/strategy, cxo = shape/purity) the same way — one durable fact each.

## Good-enough test

From memos alone — no git, no chat — can you answer:

1. What is this fleet for?
2. What is in flight, and what is the critical path?
3. What is deferred, and why?
4. What are the invariants I must not violate?
5. Which lane/repo does each Hand own?

If yes → **stop seeding and start cycling.** If no → fill the specific gap, then
stop. Seeding is complete after a few cycles, not after a fixed memo count.

## Anti-patterns

- **Recording per-cycle dispatch/wake/queue state as memos** ("cycle N
  dispatched hand-1 task …"). That is loop state → baseline / `mind_loop` state,
  not memory.
- **Replaying recent commit history into memos.** `git log` already holds it.
- **"Catching up" by narrating your first cycles to yourself.** Seed once, then
  let the memo checkpoint rule govern future writes.
- **Paragraph memos.** One durable fact each; if it needs prose, write a doc and
  keep only the pointer as a memo.
- **Seeding Hands.** Memos are Mind/Head only; Hands are not a memory store.

## First cycle after seeding

Once the seed set exists, run a normal cycle. The memo checkpoint
([`mind-cycle.md`](mind-cycle.md)) decides any *additional* writes — and by the
durability test, almost nothing in a routine cycle qualifies. If you find
yourself memoizing the cycle you just ran, re-read the Principle above.

## Links

- `SKILL.md` — *Mind memory* invariant; *Role memory (memos)*; *Anti-patterns*.
- [`mind-cycle.md`](mind-cycle.md) — *Mind memo checkpoint*; *Absorb vs accept*;
  *Review debt*.
- [`getting-started.md`](getting-started.md) — structural setup (install, init,
  identities, panes).
