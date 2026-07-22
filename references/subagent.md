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
| Head consult = paste persona + poll pane | Head consult = spawn with charter pointer + task handle |
| Pane death, stuck prompts, wrong-host tmux | No pane to die |

## Thin boot pattern

Boot and report shape are fleet-wide — see [SKILL.md § Role communication contract](../SKILL.md#role-communication-contract). The parent delivers a thin pointer; the sub-agent loads charter, task, and bag from Vivi; results file through Vivi; only a short pointer returns.

Sub-agent specifics:

- Boot pointer is the spawn prompt (the first thing the sub-agent reads).
- Completion is the report signal — no polling, no doorbell, no pane inspection.
- Optional bag read at boot is useful when the role has multiple open items and should pick order itself.

## Capacity at spawn

The Mind normally knows a role's capacity because it set it. If the Mind does not know the provider, model, or thinking level for a role, inspect the role:

```bash
vivi role show <name> --project <root>
```

Map the capacity (provider/model/thinking) to the harness's available model slugs. The mapping is harness-specific. When no clean mapping exists, substitute the closest fit or pause to ask the operator — do not silently spawn on the wrong model class.

## Spawn → completion → verify flow

```text
1. Mind files task:        vivi task send --from mind --to <name> --subject '...' --body '...'
2. Mind spawns sub-agent:  thin boot with role + task handle
3. Sub-agent runs:         reads task, writes code, validates, reports
4. Sub-agent completes:    notification arrives to Mind
5. Mind verifies:          inspect diff, run tests, check commit
6. Mind closes task:       vivi task done <handle> --for <name> --note '...'
7. Mind files next unit    (if pipeline has more)
```

Step 4 is the key difference: the Mind does not poll. The sub-agent's completion
is the signal. Between spawns, the Mind can file other work, spawn other Hands,
or respond to the operator.

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
- Writes only to its assigned scope
- Reports independently when done
- Does not coordinate with peer sub-agents

Non-overlap rule: no shared files, modules, lockfiles, or generated artifacts.
If scopes collide, serialize or use a worktree.

## Long-running sub-agents

Sub-agents are not limited to one-shot tasks. A sub-agent can:
- Make dozens of tool calls across a long session
- Run builds, tests, linters, and fix cycles
- Write multiple commits if the unit requires it
- Consult Vivi mail and memos during execution

The parent does not interrupt a running sub-agent. Completion is the next
interaction point.

## Report-back pattern

Report shape is fleet-wide — see [SKILL.md § Role communication contract](../SKILL.md#role-communication-contract). The sub-agent files `vivi task done` + `vivi mail send` before returning, then returns a short pointer only. The detailed report lives in Vivi for audit.

## Head consultation via sub-agent

Heads are advisory, not implementers. A Head sub-agent uses the same boot shape as any role — charter + task pointer from Vivi — with one distinction: the charter encodes "advise only, do not implement, report To mind."

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
