# Multi-lane Mind and integration

Load for side lanes, theme merge, base-update, pin-relative done, `pending_merges`.

## Multi-lane Mind (all hands every cycle)

Track **all active hands** every cycle. Do not collapse maps into one spine.

**Live assignment = fleet JSON** (`hands.*.packet` / `focus` / `cwd`). Prose “H2 always owns X” is not law.

| Slot | Workspace | Bag empty means |
| --- | --- | --- |
| **hand-1** | **main** (sticky) | starvation if main map next, pending_merges, or better open residuals |
| **hand-2+** | **current fleet assignment** | starvation if **that assignment’s** map has unblocked next — refill same cycle |

File **To the Hand that owns that assignment**. Never cross-file continuous work.

## Theme → main (always via hand-1; theme cadence)

Side-lane workers **never** merge to main. Mind owns integration clock. Long continuous lanes merge at **theme boundaries**, not every unit.

| Event | Mind action |
| --- | --- |
| Worker finishes **unit** | **Absorb** + review; residual/next To: **same worker**; **no** merge to h1 |
| Worker finishes **theme** | ready-to-merge → review → **accept** → `pending_merges` → **merge task To: h1** at clean breakpoint |
| Operator forces mid-theme integrate | exception only when explicit |

**Theme (default):** one delivery-index major unit honestly closed **or** operator-named theme — not “tasking empty for an hour.”

### Theme-complete path

1. Worker signals **theme ready-to-merge** (name + tip + evidence) **or** Mind judges done after review  
2. **Absorb** tip; light residual/evidence since last main merge (not GO stamp; not full code review)  
3. **Integration accept** → `pending_merges` (slug, tip, base, theme, `queued_for_hand1`) **or** residual To worker  
   (Deep review = **head-cto on main after** hand-1 merges)  
4. File **one merge task To: hand-1** (slug, branch, base, tip, theme, validation, **watch-scope drift**)  
5. Wake/reinit h1 only at **clean breakpoint**. Mid-spine → **queue**  
6. After h1 merges: **absorb** main; **accept** merge; clear/update `pending_merges`; next unit/theme To worker (or reassign)  
7. After theme on main: evaluate **main → side-lane base-update**

Between themes: worker keeps committing; main free for spine; side lane must **periodically absorb green main**.

## Integration modes

| Mode | Rule |
| --- | --- |
| Bounded one-shot | ready-to-merge when assignment finishes → review → merge to h1 |
| Long-term continuous | merge only at **theme** boundaries; units → absorb/review/next only |
| hand-2+ | never merge to main |
| h1 wake | defer while mid-spine / dirty main WIP |
| Reverse sync | **main → side-lane base-update required** (not forever-diverge) |

## Integration seams (pin-relative done)

A fix is **done relative to a pin**, not absolutely.

| Operation | Touches | Owner | When |
| --- | --- | --- | --- |
| **Theme merge** packet → main | main | **hand-1** only | Theme accept + clean breakpoint |
| **Base-update** main → packet | writable packet branch | **packet worker** | Green main + not mid-unit + lag/drift |
| **Pin refresh** | pinned/read-only worktree | **operator / Mind** | Product needs main-only capability; worker must **not** self-bump |
| **Consumer re-verify** | product packet | that Hand | Only after `git merge-base --is-ancestor <fix-sha> <consumer-pin-HEAD>` |

**Misroute:** residual To origin Hand when consumer red because fix **not on their pin** = **integration lag**. Queue merge/base-update/pin-refresh — don’t thrash re-verify. No “DONE re-verify NOW” until fix reachable from consumer tree. Prefer need To Mind/operator for pin refresh over stacked wakes on a correctly blocked Hand.

## Main → side-lane base-update

**Invariant:** continuous side lanes must not lag main indefinitely. Mind decides **when**; workers execute when assigned.

Default: **merge green main into side branch** (merge commit > rebase on multi-agent shared branches). Skill states **policy**, not filesystem convention.

### Green main gate (hard)

Only base-update from a tip that is **green** by project bar (formatter, lint, targeted tests). Name **exact green SHA** in task. Red/unvalidated → wait or file main residual — **do not** refresh onto known-broken tip. After base-update failure, suspect merge interaction first — not “main was already broken.”

### When to file (do not thrash)

| Trigger | Action |
| --- | --- |
| Theme merge just accepted on main | Prefer base-update when worker idle/clean |
| Side lane missing main commits on watch/write surface | File before product depending on those facts |
| Watch-scope drift / next theme merge painful | File base-update |
| Worker mid-flight intentional dirty WIP | **Defer** |
| Main not green | **Defer** |

One base-update task per lane when lag is real — not a new SHA every cycle.

**Task body:** To side-lane worker; green main SHA + evidence + merge into side branch + validate + turn-end. Worker: honest conflicts; no force-push; no product scope expansion unless required for conflicts.

## Post-theme residue vs pending merge

**Empty tasking + no `queued_for_hand1` ≠ tip on main.** Unit/polish commits after a recorded theme merge = **post-theme residue** until next theme seam (or operator forces integrate).

Assess with `git merge-base --is-ancestor <side-tip> <main-tip>` (and reverse lag), not only `pending_merges`.

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
| `partial_merged` | Part of theme landed; residual debt |
| `integrated_publish_pending` | Integrated; publish/Status still open |
| `abandoned` | Explicitly dropped |

Ledger may keep old `merged` rows; **live queue** = non-terminal states only.
