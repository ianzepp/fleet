# Multi-lane Mind and integration

Load for side lanes, theme merge, base-update, pin-relative done, and `pending_merges`.

## Multi-lane Mind (all hands every cycle)

Track **all active hands** every cycle; do not collapse maps into one spine.

**Live assignment table = fleet JSON** (`hands.*.packet` / `focus` / `cwd`). Do not treat a prose snapshot of “H2 always owns X” as law — read fleet live.

| Slot class | Workspace | Bag empty means |
| --- | --- | --- |
| **hand-1** | **main** (sticky) | starvation if main map next, pending_merges, or better open residuals |
| **hand-2+** | **current fleet assignment** | starvation if **that assignment’s** map still has unblocked next work — refill same cycle |

File targets **To the Hand that currently owns that assignment**. Never cross-file continuous work to the wrong slot.

## Theme → main (always via hand-1; theme cadence only)

Side-lane workers **never** merge to main. Mind owns the integration clock.

**Do not harass hand-1 with a merge every task unit.** Long continuous lanes merge at **theme boundaries**, not unit boundaries.

| Event | Mind action |
| --- | --- |
| Worker finishes a **unit** | **Absorb** + review; residual or next unit To: **same worker**; **no** merge task to h1 |
| Worker finishes a **theme** | ready-to-merge → review → **accept** → `pending_merges` → **merge task To: h1** at clean breakpoint |
| Operator forces mid-theme integrate | exception only when explicit |

**Theme (default):** one delivery-index major unit honestly closed **or** an operator-named theme. Not “tasking empty for an hour” alone.

### Theme-complete path

1. Worker signals **theme ready-to-merge** (theme name + tip + evidence) **or** Mind judges theme done after review
2. **Absorb** tip; light residual / evidence check since last main merge (not a GO stamp; not full code review)
3. **Integration accept** → `pending_merges` (slug, tip, base, theme, state `queued_for_hand1`) **or** residual To worker  
   (Deep code review is **head-correctness on main after** hand-1 merges)
4. File **one merge task To: hand-1** (slug, branch, base, tip, theme, validation, **watch-scope drift**)
5. Wake/reinit h1 only at **clean breakpoint** (by h1’s current runtime). Mid-spine → **queue**
6. After h1 merges: **absorb** main; **accept** merge; clear/update `pending_merges`; file next unit/theme To worker still assigned that lane (or reassign)
7. After theme on main: evaluate **main → side-lane base-update** (below)

Between themes: worker keeps committing on its branch; main stays free for spine — but the side lane must **periodically absorb green main**.

## Integration modes

1. **Bounded one-shot lane:** ready-to-merge when the whole assignment finishes → review → merge task to h1
2. **Long-term continuous lane:** merge only at **theme** boundaries. Units → absorb/review/next target only
3. Never ask hand-2+ to merge to main
4. Defer h1 wake while mid-spine phase / dirty main WIP
5. **Main → side-lane reverse sync is required policy** (not forever-diverge)

## Integration seams (pin-relative done)

A fix is **done relative to a pin**, not absolutely.

| Operation | Touches | Execute owner | When |
| --- | --- | --- | --- |
| **Theme merge** packet → main | main branch | **hand-1** only | Theme accept + clean breakpoint |
| **Base-update** main → packet | writable packet branch | **packet worker** | Green main + worker not mid-unit + lag/drift |
| **Pin refresh** | pinned/read-only member worktree (e.g. runtime pin) | **operator / Mind** | Product needs a main-only capability; worker must **not** self-bump worktrees |
| **Consumer re-verify** | product packet | that Hand | Only after `git merge-base --is-ancestor <fix-sha> <consumer-pin-HEAD>` |

**Misroute class:** filing a “compiler residual” To the origin Hand when the consumer is red because the fix is **not on their pin** — that is **integration lag**. Mind should queue merge/base-update/pin-refresh, not thrash re-verify.

Do not doorbell “DONE re-verify NOW” until the fix is reachable from the consumer’s tree. Prefer a need To Mind/operator for pin refresh over stacked wakes on a correctly blocked product Hand.

## Main → side-lane base-update (Mind-owned timing)

**Invariant:** continuous side lanes must not lag main indefinitely. Mind decides **when** to file base-update targets; workers execute when assigned.

Default method: **merge green main into the side branch** (merge commit). Prefer merge over rebase on multi-agent shared branches. Project may define directory layout for side lanes; this skill states **policy**, not a required filesystem convention.

### Green main gate (hard)

Only use a main tip as base-update source if that tip is **green** by project bar (formatter clean, lint green, targeted tests green — project-defined). Name the **exact green SHA** in the task. If main is red or unvalidated → wait or file main residual; do **not** refresh the side lane onto a known-broken tip. After base-update failure, default suspicion is merge interaction — not “main was already broken.”

### When to file (pick one; do not thrash)

| Trigger | Action |
| --- | --- |
| Theme merge just accepted on main | Prefer base-update when worker idle/clean |
| Side lane missing main commits on watch/write surface | File base-update before product that depends on those facts |
| Watch-scope drift / next theme merge would be painful | File base-update |
| Worker mid-flight intentional dirty WIP | **Defer** |
| Main not green | **Defer** |

One base-update task per lane when lag is real — not a new SHA every cycle.

### Task body

- **To:** side-lane worker
- Body: green main SHA + evidence + merge command into side branch + validate + turn-end
- Worker: resolve conflicts honestly; no force-push; no product scope expansion unless required for conflict resolution

## Post-theme residue vs pending merge

**Empty tasking + no `queued_for_hand1` does not mean tip is on main.** Continuous lanes often hold tens of unit/polish commits after a recorded theme merge. That is **post-theme residue**, not a merge queue item, until Mind defines the next theme seam (or operator forces integrate).

When assessing “is everything merged?”: re-check `git merge-base --is-ancestor <side-tip> <main-tip>` (and reverse lag), not only the `pending_merges` ledger.

## `pending_merges` states

```text
active | ready | reviewing | queued_for_hand1 | merged
| partial_merged | integrated_publish_pending | abandoned
```

| State | Meaning |
| --- | --- |
| `active` | Theme in flight on side lane |
| `ready` | Worker claims ready; not yet reviewing |
| `reviewing` | Mind review open |
| `queued_for_hand1` | Accepted; merge task exists or should |
| `merged` | On main and accepted as merge |
| `partial_merged` | Only part of the theme landed; residual debt remains |
| `integrated_publish_pending` | Integrated somewhere / publish or Status still open |
| `abandoned` | Explicitly dropped |

Ledger history may keep old `merged` rows; **live queue** is non-terminal states only.
