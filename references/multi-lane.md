# Multi-lane Mind and branch integration

Load for parallel hand coordination, write-scope non-overlap, feature-branch integration, base-update, pin-relative done, and lane lifecycle.

## Multi-lane Mind (all hands every cycle)

Track **all active hands** every cycle. Do not collapse maps into one spine.

**Live assignment = Vivi role records and baseline** (`packet` / `focus` / `cwd`). Prose "H2 always owns X" is not law.

### Floater shape

All Hands are equivalent floaters. The Mind picks any available Hand for each assignment. See [SKILL.md § Commit authority and workflow](../SKILL.md#commit-authority-and-workflow).

Before filing a floater task:

1. Name the writable repo/worktree scope in the task body.
2. Check active Hand scopes; avoid parallel writes to the same repo unless the
   operator explicitly accepts the collision.
3. If all ready work overlaps, serialize or record a dependency defer instead
   of inventing makework.
4. After a floater finishes, absorb the unit and reassign from the queue/map;
   do not preserve the old repo binding by inertia.

| Slot | Workspace | Bag empty means |
| --- | --- | --- |
| **any hand-N** | **current assignment** (repo/crate/worktree) | starvation if any non-overlapping ready unit exists — refill same cycle; valid defer if only overlapping/dependent work remains |

File **To the Hand that owns that assignment**. Never cross-file continuous work.

## Branch integration

Most work lands on main because the Mind scopes non-overlapping work across repos and crates. Feature branches are the exception, used when scope is large or overlap risk is real. The Mind creates feature branches and worktrees; Hands commit to whatever branch they're assigned.

| Event | Mind action |
| --- | --- |
| Worker finishes **unit** on main | **Absorb** + review → auditor if risk; residual/next To: **same worker** |
| Worker finishes **unit** on feature branch | **Absorb** + review; worker keeps committing on the branch |
| Worker finishes **theme** on feature branch | Review → **accept** → Mind merges when ready (see [Integration decision](#integration-decision)) |
| Operator forces mid-theme integrate | Exception only when explicit |

**Theme (default):** one delivery-index major unit honestly closed **or** operator-named theme — not "tasking empty for an hour."

### Integration decision

When a feature branch is ready to merge:

1. Worker signals **theme ready-to-merge** (branch name + tip + evidence) **or** Mind judges done after review.
2. **Absorb** tip; light residual/evidence check (not GO stamp; not full code review).
3. **Accept** when audit loop passes (auditor verified).
4. Mind merges the branch to main at a clean breakpoint — Mind owns the merge decision, not a queue.
5. After merge: absorb main; next unit/theme To worker (or reassign).
6. Evaluate base-update for any other branches that lag main.

Between theme merges: workers keep committing on their assigned branches; the Mind tracks branch state through normal task/need flow.

## Dedicated lane lifecycle

A long campaign may bind one Hand to a worktree through `hands.<name>.lane` (or
legacy `packet`). Binding preserves ownership while work is active; it is not a
permanent reservation after the map closes.

```text
active -> stale_candidate -> reconciling -> active | parked | cooldown -> released
```

Sensors nominate `stale_bound`, `empty_retained`, or `resume_stale`; Mind alone
dispositions the lane. `parked` requires an owner and wake trigger. `released`
returns runtime capacity but never deletes a branch or worktree.

Canonical thresholds, evidence order, release gates, and worktree law:
[`mind-cycle.md`](mind-cycle.md) § Campaign truth and lane lifecycle. Config and
baseline fields: [`runtime-config.md`](runtime-config.md).

## Integration modes

| Mode | Rule |
| --- | --- |
| Bounded one-shot (on main) | Commit directly; no merge needed |
| Bounded one-shot (on feature branch) | Commit on branch → Mind merges when ready |
| Long-term continuous (feature branch) | Merge at **theme** boundaries; units → absorb/review/next only |
| Reverse sync | **main → feature-branch base-update required** (not forever-diverge) |

## Integration seams (pin-relative done)

A fix is **done relative to a pin**, not absolutely.

| Operation | Touches | Owner | When |
| --- | --- | --- | --- |
| **Theme merge** feature → main | main | **Mind** | Theme accept + clean breakpoint |
| **Base-update** main → feature | writable feature branch | **branch worker** | Green main + not mid-unit + lag/drift |
| **Pin refresh** | pinned/read-only worktree | **operator / Mind** | Product needs main-only capability; worker must **not** self-bump |
| **Consumer re-verify** | product branch | that Hand | Only after `git merge-base --is-ancestor <fix-sha> <consumer-pin-HEAD>` |

**Misroute:** residual To origin Hand when consumer red because fix **not on their pin** = **integration lag**. Queue merge/base-update/pin-refresh — don't thrash re-verify. No "DONE re-verify NOW" until fix reachable from consumer tree. Prefer need To Mind/operator for pin refresh over stacked wakes on a correctly blocked Hand.

## Main → feature-branch base-update

**Invariant:** continuous feature branches must not lag main indefinitely. Mind decides **when**; workers execute when assigned.

Default: **merge green main into feature branch** (merge commit > rebase on multi-agent shared branches). Skill states **policy**, not filesystem convention.

### Green main gate (hard)

Only base-update from a tip that is **green** by project bar (formatter, lint, targeted tests). Name **exact green SHA** in task. Red/unvalidated → wait or file main residual — **do not** refresh onto known-broken tip. After base-update failure, suspect merge interaction first — not "main was already broken."

### When to file (do not thrash)

| Trigger | Action |
| --- | --- |
| Theme merge just accepted on main | Prefer base-update when worker idle/clean |
| Feature branch missing main commits on watch/write surface | File before product depending on those facts |
| Watch-scope drift / next theme merge painful | File base-update |
| Worker mid-flight intentional dirty WIP | **Defer** |
| Main not green | **Defer** |

One base-update task per branch when lag is real — not a new SHA every cycle.

**Task body:** To branch worker; green main SHA + evidence + merge into feature branch + validate + turn-end. Worker: honest conflicts; no force-push; no product scope expansion unless required for conflicts.

## Post-theme residue vs pending merge

**Empty tasking on a feature branch ≠ branch merged to main.** Unit/polish commits after a recorded theme = **post-theme residue** until next theme seam (or operator forces integrate).

Assess with `git merge-base --is-ancestor <feature-tip> <main-tip>` (and reverse lag) to check whether the branch has been merged.
