# Sub-agent execution runtime

Spawn Hands (and consult Heads) as sub-agents inside the parent runtime instead of
external panes. This is the default execution path for fleets on harnesses that
support sub-agent spawning (Grok Build, Codex, etc.).

Sub-agents run in the parent process, make multiple tool calls, and notify on
completion. No polling. No doorbell. No tmux pane to keep alive.

## Why sub-agent

| Tmux / vivi-pty | Sub-agent |
| --- | --- |
| Poll every 3–5m to check if work is done | Completion notification arrives immediately |
| Capacity rebind = kill pane, edit role record, relaunch | Capacity rebind = `vivi role set`; next spawn uses new values |
| Doorbell text into a pane; hope it lands | Direct spawn with thin boot context |
| Report lands in mail; Mind polls to find it | Report lands in Vivi (durable); short pointer returns to Mind |
| Head consult = paste persona + poll pane | Head consult = spawn with generated advisory prompt |
| Pane death, stuck prompts, wrong-host tmux | No pane to die |

## Generated boot pattern

Boot and report shape are fleet-wide — see
[`fleet-helper.md`](fleet-helper.md). The Mind spawns with the exact output of
`fleet prepare`; the role claims and settles through that helper.

**No handle, no spawn.** The Mind must create the Vivi assignment before the
sub-agent exists. Do not spawn with full instructions and backfill a task after
execution starts. A retroactive stub records a process deviation; it does not
reconstruct the missing assignment chain.

Sub-agent specifics:

- Boot pointer is the spawn prompt (the first thing the sub-agent reads).
- Completion notification wakes the Mind; the Fleet settlement is the durable
  completion record.
- Optional bag read is awareness only. One spawn executes the one handle named
  in its generated prompt; it does not aggregate other open items.

## Capacity at spawn

Before every spawn, inspect the role's live capacity:

```bash
vivi role show <name> --project <root>
```

Use the recorded harness, provider, model, and thinking level. Task shape may
justify a deliberate `vivi role set` rebind before spawn; it does not authorize
an invocation-only substitution. This is especially strict for Auditors:
configured model-family independence is part of the review contract, not an
optional capability preference.

Map the live capacity to the harness's available model slugs. The mapping is
harness-specific. When no clean mapping exists, pause or choose a correctly
bound role. Do not silently spawn on the wrong model class or provider.

## Spawn → completion → disposition flow

```text
1. Mind prepares:          fleet prepare ... → generated boot prompt
2. Mind spawns sub-agent:  exact generated prompt
3. Sub-agent runs:         fleet claim → execute → fleet settle
4. Sub-agent completes:    notification arrives to Mind
5. Mind reconciles:        settlement + commit receipt + declared scope
6. Mind routes:            dependent review/repair or fleet advance
7. Mind absorbs mail:      only after the report has a disposition
```

Step 4 is the key difference: the Mind does not poll. The sub-agent's completion
notification is the wake signal, not authority to advance. The Mind first
reconciles the prepared chain and settlement receipt.
Between spawns, the Mind can prepare other work, spawn other Hands, or respond to
the operator.

### Runtime receipt map

Record each spawn as `{vivi_handle -> runtime_id, role, resolved capacity}` in
the Mind's current process state. Capture the runtime id immediately from the
individual spawn result. Do not rely on a later aggregate wait to reconstruct
which runtime owned which assignment.

If the harness loses a runtime id or an aggregate wait returns `not_found`, use
the Vivi handle as the durable root and treat the missing runtime id as process
failure. Reconcile through Vivi task/mail state and explicit per-runtime events.
Do not infer completion from modified files, commits, or a batch summary alone.

## Parallel spawning

When the delivery doc produces N independent units with non-overlapping write
scopes, spawn N sub-agents in a single parent turn:

```text
spawn hand-1 → unit A (crates/radix-mir)
spawn hand-2 → unit B (crates/radix-hir)
spawn hand-4 → unit C (hosts/webgpu-browser)
```

Each sub-agent:
- Gets its own task handle
- Executes exactly that one bounded handle
- Writes only to its assigned scope
- Reports independently when done
- Does not coordinate with peer sub-agents

Non-overlap rule: no shared files, modules, lockfiles, or generated artifacts.
If scopes collide, serialize or use a worktree.

Spawn calls may be parallel, but the Mind must capture each returned runtime id
and bind it to its Vivi handle before waiting. When a harness's aggregate wait
loses ids, use individual event completion or per-id waits; do not make
filesystem forensics the completion protocol.

### Concurrent commits on a shared working tree

Disjoint file scopes do not make concurrent commits safe on a shared tree. Every Hand sees every peer's in-progress files and commits against one shared `.git/index`; whichever Hand commits captures whatever is staged, no matter who staged it. Trained-helpfulness has been observed to override "stage only your own files" — a Hand finishing first stages siblings it can see and commits peers' WIP. Protocol prose does not reliably prevent this.

| Parallel shape | Safe commit strategy |
| --- | --- |
| N Hands, N units, all commit, shared tree | **Partial commit** (below) |
| Same file hot, or long divergent branches | One worktree per Hand |
| Read-only / advisory sub-agents | Shared tree fine (no commits) |

**Partial-commit contract (the default for disjoint scopes).** Each Hand commits only its own scope by explicit pathspec:

```bash
git add -- <own scope>
git commit --only -m '…' -- <own scope>
```

`git commit --only -- <pathspec>` builds the commit from HEAD plus the named paths, **disregarding everything else staged in the shared index**. A peer's concurrently-staged files cannot be captured because they are not in the pathspec. Verified under adversarial timing: three concurrent Hands writing to one flat shared directory yielded three clean single-file commits with zero cross-contamination.

Requirements and limits:

- New files must be `git add`-ed first (`--only` rejects untracked pathspecs). The `add` touches the shared index; the `--only` commit ignores other entries there, so it stays safe.
- The pathspec is a single explicit argument the task/boot supplies verbatim — far more enforceable than "stage carefully." The commit's file list can be auto-checked against the write scope.
- Concurrent commits contend briefly on `.git/index.lock` / the ref; git serializes them. The loser retries with backoff (seconds) — not worktree-scale merge conflicts.
- Two Hands editing the **same** file is real overlap: serialize or use a worktree. Partial commit only separates disjoint scopes.

**Behavioral backstop:** never `git add -A`, never a bare directory add outside your scope.

## Long-running sub-agents

Sub-agents are not limited to one-shot tasks. A sub-agent can:
- Make dozens of tool calls across a long session
- Run builds, tests, linters, and fix cycles
- Write multiple commits if the unit requires it
- Consult Vivi mail and memos during execution

The parent does not interrupt a running sub-agent. Completion is the next
interaction point.

## Report-back pattern

Report shape is fleet-wide — see [`fleet-helper.md`](fleet-helper.md). Every
role calls `fleet settle`, then returns a short pointer only. The detailed
report lives on the prepared Vivi chain.

If the sub-agent returns details only in chat, the assignment is not durably
complete. The Mind sends it back to run `fleet settle`, or prepares a recovery
assignment / files a need with an honest process-deviation label if the
runtime can no longer resume. The Mind does not advance a planning gate, accept
implementation, or route a dependent task from the chat-only result.

## Head consultation via sub-agent

Heads are advisory, not implementers. A Head sub-agent uses the same generated
boot shape with `--pass advisory`. Its charter encodes "advise only"; it settles
findings on the prepared handle before returning.

Head sub-agents are cold-boot by design: no accumulated state, fresh context per question. The charter provides enough standing definition to make cold boot sufficient.

## Charter sufficiency

A charter is sufficient for cold boot when it encodes:

- Who the seat is (role, lens, report style)
- Process law that applies to every unit (lowering requirements, pedantic rules, scope bans)
- Report-back expectations (what evidence to include)
- What the seat does **not** do (non-goals)

If a sub-agent needs session-specific context that the charter does not cover,
either (a) extend the charter, or (b) include that context in the task body.
Do not rely on accumulated state from previous spawns.

## Backup loop for event-driven fleets

When using sub-agents as the primary runtime, the FLEET_CYCLE monitoring loop
becomes a backup, not the main driver:

| Concern | Driver |
| --- | --- |
| Task completion → file next unit | Sub-agent completion notification |
| Stuck sub-agent (spawned, no result after N minutes) | Backup loop detects and intervenes |
| Board staleness (open tasks with no progress) | Backup loop |
| Starvation patterns (hands idle across consecutive cycles) | Backup loop |
| Operator mail waiting for response | Backup loop or immediate |
| Turn-ending recovery (context filled, harness issue) | Backup loop restarts Mind |

Recommended cadence: **15–30 minutes**. The loop is insurance, not the engine.
Tighten only if sub-agents are getting stuck or the operator is engaged.

## When to choose sub-agent vs tmux vs vivi-pty

| Situation | Use |
| --- | --- |
| Default (harness supports sub-agents) | **Sub-agent** |
| Persistent interactive session needed (long debugging, REPL) | tmux or vivi-pty |
| Harness lacks sub-agent spawning | tmux or vivi-pty |
| Operator wants to watch a Hand work live | tmux |
| Remote host execution (SSH) | tmux on remote host |
| Head consultation (advisory, cold-boot) | **Sub-agent** |
| Parallel non-overlapping units | **Sub-agent** (spawn N) |

tmux and vivi-pty references: [`tmux.md`](tmux.md), [`vivi-pty.md`](vivi-pty.md).

For a bounded parallel wave, use [`wave-planning.md`](wave-planning.md) for
audited preparation and [`wave.md`](wave.md) for execution and aggregate
closeout. Backend mechanics remain here.
