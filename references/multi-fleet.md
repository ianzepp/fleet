# Multi-fleet Mind sessions (session-attach)

A **Mind session** (operator TUI) may supervise **one or more fleets**. Each fleet is the **durability boundary** (`.vivi/`, board, baseline, steward). Cross-fleet state lives only in the live Mind session; rebuild from per-fleet baselines.

Design: [`multi-fleet-design.md`](multi-fleet-design.md) (v2.1).

## Vocabulary

| Term | Meaning |
| --- | --- |
| **Fleet** | One project root + fleet overlay. Canonical unit. |
| **Mind session** | One operator conversation; ephemeral join over attached set |
| **Attached set** | Fleets this session supervises — named on each `FLEET_CYCLE` line |
| **fleet_id** | Short host-scoped id; preferred tmux session name under session-per-fleet |
| **Mini-cycle** | Fail-fast ops for **one** fleet inside a multi-fleet fire |

## Invariant

> A Mind session may attach to multiple fleets.  
> **No fleet may be attached to two Mind sessions at once** (advisory lock).

Multiple Mind sessions on one host OK when attached sets are **disjoint**.

## Dual channel binding

### Legacy (single-fleet, still valid)

```text
mail_identity == tmux_session token
tmux_target   == {role}:1.1
```

Example: mail `hand-1@…`, session `hand-1`, target `hand-1:1.1`.

### Session-per-fleet (preferred multi-fleet hosts)

```text
mail_identity  == role token (hand-1, head-ceo, steward, …)
tmux_session   == fleet_id
tmux_window    == role token
tmux_target    == {fleet_id}:{role}.1
```

Example: mail `hand-1@…`, session `mgs`, window `hand-1`, target `mgs:hand-1.1`.

**Ops always use `tmux_target` from fleet.json** — never assume session name == role.

| Layout field | fleet.json |
| --- | --- |
| `fleet_id` | short id (e.g. `mgs`) |
| `tmux_layout` | `legacy` \| `session_per_fleet` |
| per-slot `tmux_session`, `tmux_window`, `tmux_target` | required when not legacy |

Lazy Head windows: declare Heads in fleet.json; create tmux windows on first assign.

## FLEET_CYCLE (multi-fleet)

**One fire = mini-cycle every fleet under supervision.**

**First line = attach set (slugs).** Paths are **not** topic-line abbreviations — put them in the body.

```text
FLEET_CYCLE fleets=mgs,faber,nacht

Roots (slug → project path):
  mgs:   /path/to/minted-geek-swarm
  faber: /path/to/faberlang
  nacht: /path/to/nachtbagger
```

| Rule | Detail |
| --- | --- |
| Coverage | Every **slug** on the first line gets a full fail-fast mini-cycle |
| Paths | Body map, attach memory, or each fleet’s `fleet.json` → `project` — **not** `also=` / `also2=` invent-keys |
| Posture | **Per fleet** (`growth` / `standby` / `dormant`) — standby/dormant mini-cycles stay quiet; never invent work so every slug “looks busy” — [`fleet-posture.md`](fleet-posture.md) |
| Durability | Each fleet writes its **own** `last_successful_cycle_at` (+ `steward.sh rearm` **only if** that fleet’s steward is armed) |
| Isolation | Never file To fleet A while processing fleet B |
| Topic line | **Attached set log** — attach/detach by changing the slug list |
| Report | One line/block per fleet including `posture=…`; mode-gated richness |

Single-fleet: `FLEET_CYCLE fleets=mgs` or `FLEET_CYCLE project=/path/to/one/fleet …`

### Mini-cycle body (per fleet)

```text
1. Sensors: fleet-sensors.py --project $ROOT (includes posture)
2. If posture standby|dormant: absorb/operator@ only; no invent; quiet OK
3. Else act on signal: absorb, product starvation refill, wake/reinit that fleet only
4. Quiet if fingerprint unchanged / no valuable work
5. Write baseline last_successful_cycle_at; steward rearm only if armed
```

## Attach / detach

First-time single-fleet attach: [`getting-started.md`](getting-started.md) § 3.

| Action | Steps |
| --- | --- |
| **Attach** | Read baseline `mind_session` lock → refuse if live foreign unless `--takeover` → write `mind_session={label,host,pid?,attached_at}`; `mind_loop.state=running` → sensor; fold operator@/headline into recap. **Do not** arm steward unless operator explicitly enabled+asked for **that** fleet |
| **Detach** | Stop filing new work; honest in-flight in baseline → **`steward.sh disarm --project <fleet>` same turn** → `mind_loop.state=detached` (or wound_up); clear/stamp `mind_session` → optional leave Hands mid-unit; no kill foreign WIP |
| **Orphan** | Mind dies without detach → steward **trips after grace**. Recovery: `steward.sh clear` + reattach |

### Advisory lock (baseline)

```json
"mind_session": {
  "label": "term1",
  "host": "hostname",
  "pid": 12345,
  "attached_at": "…"
}
```

Advisory only — no hard mutex. Forced takeover overwrites.

## Cross-fleet recap (in-session only)

No global index. On attach or operator return:

```text
for fleet in attached_set:
  read fleet mind-baseline → op-mail count, steward tripped, headline, recap
present table: fleet | tripped | op-mail | headline
```

Order: tripped stewards → operator@ union → headlines.

## Steward

| Rule | Detail |
| --- | --- |
| Count | **One per fleet** (prefer window `steward` under fleet session when `session_per_fleet`) |
| Soft-hold | Only **that fleet’s** Hands (via each hand’s `tmux_target`) |
| Trip pages | That fleet only (board + optional external email) |

## Scripts

| Script | Rule |
| --- | --- |
| `steward.sh` | Read steward + hands `tmux_target` from fleet.json |
| `codex-reinit.sh` | Already resolves `tmux_target` per hand |
| Doorbell / capture | Always fleet.json `tmux_target` |

## Anti-patterns

- Global roster / global baseline as control plane
- Auto-scan home directories for fleets
- Shared board across fleets
- Soft-hold Hands of fleet B when A trips
- Dual Mind on one fleet without takeover
- Hardcoded `hand-1` as tmux session name in scripts
- Treating “fleet” as the canonical skill term for a project fleet

## Related

- [`dead-man.md`](dead-man.md) — steward protocol  
- [`mind-cycle.md`](mind-cycle.md) — modes, cycle prefix  
- [`runtime-config.md`](runtime-config.md) — fleet.json / baseline schema  
- [`dual-channel.md`](dual-channel.md) — panes and targets  
