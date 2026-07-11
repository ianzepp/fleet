# Design: Multi-fleet Mind sessions (session-attach model)

**Status:** v2.1 — **process landed in `$fleet`** (2026-07-11); live topology migration optional/deferred  
**Date:** 2026-07-11 · **Skill:** `$fleet` · **Audience:** operator + reviewing agent/human  
**Skill entry:** [`multi-fleet.md`](multi-fleet.md)

---

## 1. Purpose

Model where:

- A **Mind session** (one operator TUI) **attaches to ≥1 fleets**.
- Multiple Mind sessions may coexist (local/remote), each with its own set, **if no fleet is dual-attached**.
- Mind session = **ephemeral join** — only place cross-fleet awareness lives; no durable global body.
- Persist **per fleet** in `<project>/.vivi/`. Fleet = durability boundary.

Review doc. **No skill rewrite required until accepted.**

### Terminology

**Fleet** = sole unit name: project root + `.vivi/` overlay. Prefer multi-fleet, fleet_id, session-per-fleet. Avoid camp, hunter-gatherer, pre-rename Head/Hand strings in process docs.

### What changed from v1

v1: single global Mind + one loop + on-disk roster + Mind-level baseline for all fleets.  
v2 drops that: Mind is transient; no roster, global baseline, cross-fleet disk index, attention modes, or budget/fairness scheduler. Cross-fleet state is in-session only, rebuilt from per-fleet baselines on attach. Still worth building per-fleet: tmux topology, script fixes, attach/detach protocol.

### What changed in v2.1 (operator lock)

| Topic | Decision |
| --- | --- |
| One FLEET_CYCLE | **Mini-cycle every supervised fleet** (full fail-fast each) |
| Durable ticks | Per-fleet `last_successful_cycle_at` / steward rearm |
| Attached set | Named on **`FLEET_CYCLE` topic line** (chat history = attach log) |
| Dual-attach race | **Do not over-engineer** — advisory lock enough |
| Vocabulary | **Fleet** only |

## 2. Goals and non-goals

### Goals

1. **Many terminals, disjoint fleets** — T1→A+B, T2→C; no clobber.
2. **No global files** — nothing authoritative outside a fleet's project dir.
3. **One Mind session per fleet** — block dual-Mind (rearm races, double operator-mail) without a global lock.
4. **Machine-safe process naming** — no tmux collisions when two fleets on one host both have `hand-1`.
5. **Preserve single-fleet simplicity** — one-fleet chat already is this model (set={one}); v2 makes multi-fleet explicit + protocol.
6. **Keep existing ops semantics** — bag vs gates, dual channel, steward, operator mail, fail-fast, mode-gated reporting.

### Non-goals

1. One Mind for every fleet everywhere.
2. Global roster / baseline / cross-fleet index on disk.
3. Auto-discover every `.vivi/` under home.
4. Shared Hands, boards, or cross-repo merge clocks.
5. Fleet modes (`full`/`watch`/`paused`), `max_fleets_per_fire`, `fairness`, `budget_ms` — attention = terminal layout, not a scheduler.
6. Global babysitter service.
7. ~~Design-only (implement later).~~ — **Skill process implemented**; live tmux topology migration still optional.

## 3. Vocabulary

| Term | Meaning |
| --- | --- |
| **Fleet** | Project root + overlay (`.vivi/fleet.json`, mailspace, baseline). Durability boundary. |
| **Mind session** | One operator TUI. Ephemeral. Attaches to a fleet set. Only cross-fleet state home. |
| **Attached set** | Fleets this Mind supervises. Named on each `FLEET_CYCLE` line; not an on-disk roster. |
| **Attach / detach** | Take over / release a fleet. Detach has steward consequences (§6.5). Visible via cycle topic line. |
| **Hand / Head** | Worker / advisor roles with mail + process slots, per fleet. |
| **Steward** | Per-fleet dead-man (completed-cycle ticks → hold + page). |
| **operator@** | Per-fleet human escalation inbox (not status). |
| **fleet_id** | Short alias = tmux session name on a host. Host-scoped, not globally registered. |
| **Mini-cycle** | One fleet’s fail-fast gather/act/rearm inside a multi-fleet `FLEET_CYCLE` fire. |

Metaphor: fleets = ships in different harbors; Mind = harbor master's desk that may watch several; desk closes → harbors keep logs. No worldwide registry.

## 4. Current state (as of 2026-07-11)

### 4.1 Control plane (today)

```text
Mind = operator TUI
  + optional mind@<mailspace>.local  (no tmux)
  + optional FLEET_CYCLE in same TUI, project=<root>
Hands / Heads / steward = mail + tmux slots, per fleet
```

Single-fleet is already session-attach with set of one. v2 generalizes to ≥1 + explicit attach/detach.

### 4.2 Dual channel (per fleet, unchanged)

| Channel | Truth of |
| --- | --- |
| **Vivi mailspace** | Work: tasks, needs, done, Head reports, operator mail |
| **tmux** | Process: alive/idle/running/error; pointer doorbells only |

**Binding (skill default):** `mail_identity == tmux_session` (Hands/Heads/steward only; mind+operator no tmux). Example: `hand-1@….local` → target `hand-1:1.1`.

### 4.3 Fleet overlay (per project, unchanged)

```text
<project>/.vivi/  # fleet.json · mind-baseline.json · mail.sqlite · steward.log · mind-watch.cursor
factory/          # product map
```

Mailspace project-local. **Two fleets never share a Vivi store.**

### 4.4 Mind cycle (single fleet, today)

`FLEET_CYCLE project=/path/to/one/fleet …` — fail-fast: mode → sensors → act on signal → quiet if fingerprint unchanged → rearm → (stop) disarm.

### 4.5 Steward / dead man (today, per fleet)

Fleet-local tmux `steward` + `scripts/steward.sh`. Mind **rearms** after every successful `FLEET_CYCLE`. Miss past grace → trip (baseline hold, **operator@**, optional email, soft-hold idle Hands). Already `--project` scoped — **no isolation redesign**.

### 4.6 Scaling limit (why this design exists)

Two fleets on one host with today's binding collide: both claim sessions `hand-1`, `hand-2`, …. Also: no explicit attach/detach (close → orphan/steward trip/ambiguous ownership); no cheap cross-fleet recap. Mailspaces need no redesign — process topology + session ownership do.

## 5. Problem statement

| # | Problem |
| --- | --- |
| P1 | **tmux session names collide** across fleets on one host (`hand-1`). |
| P2 | **No explicit attach/detach** — close orphans fleet or dual-Mind ambiguity. |
| P3 | **No cheap cross-fleet recap** without merging boards or a global file. |
| P4 | **Dual-Mind-on-one-fleet** → rearm races + double operator-mail. |
| P5 | **Scripts assume session name == role** (`soft_hold_hands`, `ensure_tmux_session`) — breaks under topology change. |

## 6. Proposed model

### 6.1 Mental model

```text
Mind S1 ──attach──► Fleet A ; Fleet B
Mind S2 ──attach──► Fleet C
  sets disjoint; no fleet in two sessions; no authoritative file outside fleet .vivi/
```

Mind = **ephemeral join**: holds cross-fleet view while alive. Ends → nothing global; fleet baselines still record what that Mind did. New Mind starts blind and re-sensors.

### 6.2 Invariant: at most one Mind session per fleet

> One Mind may attach to many fleets. No fleet may be attached to two Minds at once.

Replaces “Mind is *the* operator TUI” with **one Mind *per fleet***. Disjoint multi-Mind OK. Enforced via per-fleet baseline lock (§6.6) — no global lock.

### 6.3 Process topology (session per fleet, window per role)

**session = fleet_id · window = role · pane = agent process** (usually one pane/window)

```text
session mgs: windows hand-1, hand-2, head-ceo, steward → mgs:hand-1.1, …
session faber: window hand-1 → faber:hand-1.1
```

| Plane | Identity |
| --- | --- |
| Board (Vivi) | Role token `hand-1@<mailspace>.local` (unchanged) |
| Process (tmux) | `session:window` = `fleet_id:role` |

Same-host fleets both get `hand-1` **windows** without collision (`mgs:hand-1` vs `faber:hand-1`).

**Binding:** `mail_identity==role`; `tmux_session==fleet_id`; `tmux_window==role`; `tmux_target=={fleet_id}:{role}.1`.  
**Legacy** (until migrate): `mail_identity == tmux_session == hand-1`; `tmux_target == hand-1:1.1`.

#### Why session-per-fleet (not prefixed flat)

| | Prefixed (`mgs-hand-1`) | Session=fleet, window=role |
| --- | --- | --- |
| Collision-free | Yes | Yes |
| Attach / kill whole fleet | Many sessions / N kills | `attach -t mgs` / `kill-session -t mgs` |
| Mental model | Role-first | Fleet-first (harbor-then-ship) |

**Preference:** session-per-fleet + window-per-role.

#### Window vs pane / Head windows

**One pane per role window** — one process slot; `tmux_target` → exactly one pane. Viewing dashboards = separate non-slot `dashboard` window.  
**Lazy-create Heads** on first assign/bucket. Always-arming ceo/cto/cxo = 3 idle × N fleets.

### 6.4 Window naming is a `tmux_target` format change

Today `hand-1:1.1` = session `hand-1`, **window `1`**. Proposed `mgs:hand-1.1` = **named window** `hand-1`. Both valid tmux, but: parsers splitting on `:` expecting numeric window break (audit all); creation is `new-session -s mgs -n hand-1` then `new-window -t mgs -n hand-2`; fleet.json already has `tmux_target` — **format migration**, not schema add.

### 6.5 Attach / detach protocol

Attach = Mind takes steward rearm + cycle duty. **Detach is not free** — ungraceful close → steward trips after grace.

**Attach:**

1. Read `mind-baseline.json` → check `mind_session` lock (§6.6).
2. Locked under live foreign session → refuse, or require `--takeover`.
3. Write `mind_session = {label, host, pid, attached_at}`; `mind_loop.state = running`.
4. Loop schedule is independent of steward. Arm steward only if operator enabled+asked for that fleet.
5. Sensor; present baseline (op-mail, tripped?, headline) into cross-fleet recap.

**Detach:**

1. Stop filing new work; absorb in-flight into baseline.
2. `steward.sh disarm --project <fleet>` — **same turn** (no false trip).
3. `mind_loop.state = detached`; clear `mind_session` (or mark `detached_at`).
4. Leave Hands/Heads if mid-unit; else optional `tmux kill-session -t <fleet_id>`.

Mind end without detach = **orphan** → stewards trip after grace (correct failsafe). Recovery: `steward.sh clear` + reattach.

### 6.6 Per-fleet Mind-session lock (advisory)

In fleet `mind-baseline.json` (runtime, not config):

```json
"mind_session": {
  "label": "term1", "host": "pharos", "pid": 12345,
  "attached_at": "2026-07-11T14:02:00Z"
}
```

- **Advisory, not kernel mutex.** Job: prevent *accidental* dual-Mind.
- Attach while `running` + recent lock → warn; require `--takeover`.
- PID-liveness same-host only (hint). Remote: label + `attached_at`.
- Forced takeover overwrites; stale crash locks clear on takeover.

### 6.7 Computed cross-fleet recap (in-session only)

**No cross-fleet index file.** On attach or operator return, sweep each attached fleet’s baseline → table `(fleet | tripped? | op-mail | headline)`. **Computed, not stored.** Survives `/compact` via recap keep-list; new Mind re-sensors. Order: tripped → op-mail union → headlines. Trade: session-scoped sweeps (cheap for few fleets); standing global view out of scope (non-goal 2).

### 6.8 Multi-fleet FLEET_CYCLE (operator lock)

**One fire = mini-cycle every fleet under this Mind.**

```text
FLEET_CYCLE fleets=mgs,faber,orqa …   # names attached set
  for fleet in fleets:                # order as listed
    fail-fast mini-cycle → write last_successful_cycle_at; rearm --project <root>
  emit multi-fleet report (one line/block per fleet)
```

| Rule | Detail |
| --- | --- |
| **Coverage** | Every topic-line fleet every fire (no watch/paused scheduler) |
| **Durability** | Per-fleet tick/rearm — never a global tick |
| **Attached set** | Named on `FLEET_CYCLE` line (chat history = attach log) |
| **Cross-board** | Never file To A while processing B; always `--project` + that fleet’s `tmux_target` |
| **Steward** | Rearm only the fleet whose mini-cycle just completed |

Topic-line examples: `fleets=mgs,faber,orqa` → drop orqa → `fleets=mgs,faber`; single-fleet `project=/path/to/mgs` still valid. No on-disk roster — durable loop prompt (or injection first line) is source of truth; after `/compact`, next line re-states set. Changing set = §6.5 + edit line. Optional non-authoritative path map when line lists ids only.

### 6.9 Steward under multi-fleet (per fleet, unchanged)

| Property | Design |
| --- | --- |
| Count | **One steward per fleet** (window in fleet session; migrate off standalone session) |
| Tick / rearm | That fleet’s `last_successful_cycle_at` / after its mini-cycle |
| Trip / soft-hold | Pages **that fleet only**; soft-hold only **its** Hands |
| Detach | `disarm` (§6.5); else orphan → trip |

One Mind death taking two fleets → **two pages is correct severity**. No consolidated multi-fleet page (v1 withdrawn).

### 6.10 Reporting (in-session, mode-gated)

Existing modes only (autonomous thin / interactive rich):

```text
cycle 42 · fleets=mgs,faber
  mgs     acted: absorb … wake hand-2
  faber   sleep: bags empty panes running
```

Interactive = richer blocks; autonomous = compact. Operator-return → §6.7 recap.

### 6.11 Remote fleets

`fleet_id`/`tmux_session` **host-scoped**. Baseline + lock in fleet’s **local** project dir. Wake/capture/reinit on pane host (SSH-wrap). Collision = two fleets **same host** sharing `tmux_session`, not shared `fleet_id` across hosts.

### 6.12 fleet.json fields (proposed additions)

```json
{
  "fleet_id": "mgs",
  "tmux_layout": "session_per_fleet",
  "binding_rule": "mail_identity == tmux_window; tmux_session == fleet_id",
  "hands": {
    "hand-1": {
      "mail_identity": "hand-1",
      "tmux_session": "mgs", "tmux_window": "hand-1",
      "tmux_target": "mgs:hand-1.1"
    }
  },
  "steward": {
    "tmux_session": "mgs", "tmux_window": "steward",
    "tmux_target": "mgs:steward.1"
  }
}
```

`mind_session` lock is **not** here — runtime in `mind-baseline.json`.  
Scripts must prefer **`tmux_target`** over session-name==role.

### 6.13 Arm / kill UX

```bash
tmux attach -t mgs          # whole fleet
tmux kill-session -t mgs
tmux select-window -t mgs:hand-1
tmux send-keys -t mgs:hand-1.1 …
```

## 7. Alternatives considered

| Alternative | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| **v1: one Mind + roster + global baseline** | Single control plane; budget | Global files clobber; over-built | **Reject** |
| One Mind TUI per fleet (today) | Zero multi-fleet design | N terminals; no cross-fleet recap | OK, doesn't solve P3 |
| Prefixed flat sessions | Minimal script change | Noisy `tmux ls`; weak grouping | Acceptable fallback |
| Session=fleet, window=role | Clean multi-fleet | Live migrate; script updates | **Preferred** |
| Global steward service | Survives everything | Scope creep; multi-repo scan | Reject |
| Auto-discover under home | Convenient | False fleets; surprise ops | Reject |
| Shared board all fleets | One inbox | Cross-talk; breaks segregation | Reject |
| Attention modes + fairness | Explicit budget | Scheduler; not enforceable | **Reject** |
| Hard dual-attach CAS | Blocks attach races | Over-engineering | **Reject** — advisory lock enough |

## 8. Migration sketch (after acceptance)

Outline only. Decoupled; all per-fleet.

1. **Script fixes (required, topology-independent).**
   - `soft_hold_hands`: hardcodes `hand-1`/`hand-2` as **session names** → `${sess}:1.1`. Under session-per-fleet holds **silently no-op**. Rewrite to read each hand’s `tmux_target` from fleet.json.
   - `ensure_tmux_session`: uses `${sess}:1.1` not steward `tmux_target` — fix via fleet config.
   - Audit `codex-reinit.sh` + doorbell for same pattern.
2. **Topology.** New fleets day one; existing optional (step 4).
3. **Attach/detach + lock.** `mind_session` in baseline; `mind_loop.state = detached`; Mind procedure (± small helper).
4. **Existing fleet (e.g. MGS).** **Last**, only when idle, only after 1–3 proven non-prod. Don’t debug topology on the fleet you depend on.
5. **Validate.** Two fleets, both `hand-1` windows, no collision; Mind reports both without cross-board filing; detach disarms only that steward.

Rollback: unset `tmux_layout` → legacy. Session-attach itself is not a rupture — single-fleet already is it.

## 9. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Hold pointers no-op under new topology | §8 step 1 before any migrate |
| Parsers expect numeric windows | Audit; named windows valid tmux |
| Orphan on ungraceful close | Steward trip = correct failsafe; `clear` + reattach |
| Stale `mind_session` lock | Advisory; `--takeover` overwrites |
| Accidental dual-Mind | Attach checks lock; requires `--takeover` |
| Simultaneous dual-attach race | **Accept**; no CAS; last writer / operator |
| Cross-fleet recap lost on end | Deliberate; per-fleet baselines; re-sensor |
| Live agent mid-migrate | Idle windows only; or parallel session then cutover |
| Soft-hold wrong fleet | Soft-hold only tripped fleet’s Hand targets |

## 10. Open questions

1. **Mind-session identity:** operator `label`+host+pid+`attached_at` vs harness-derived? **Recommend former.**
2. **Stale lock recovery:** auto-clear dead pid (same-host) vs always `--takeover`? **Recommend explicit takeover.**
3. **Known-fleets hint:** non-authoritative `fleet_id`→path map? **Yes; not control plane.**
4. **Migrate MGS now?** **No** — scripts → new fleet → MGS last when idle.
5. **Attach behavior:** auto-present recap vs explicit `status`? **Recommend auto-present.**

**Closed (v2.1):** full mini-cycle per supervised fleet; fleets on `FLEET_CYCLE` line; dual-attach race ignored; vocabulary = fleet.  
(Window/pane + Head-lazy answered in §6.3. v1 roster/mode/fairness questions dissolved.)

## 11. Success criteria (when built)

1. Two fleets, one host, both `hand-1` **windows**, no collision.
2. Mind multi-attach reports each fleet; no cross-board filing.
3. One `FLEET_CYCLE` mini-cycles **every** topic-line fleet; separate rearm each.
4. Detach disarms only that steward.
5. Second Mind refused unless `--takeover` (advisory).
6. Close without detach → orphan steward trips after grace.
7. New Mind re-sensors from per-fleet baselines — no global file.
8. Legacy single-fleet topology works until opt-in.

## 12. Related skill surfaces (current)

| Path | Topic |
| --- | --- |
| `fleet/SKILL.md` | Roles, dual channel, modes, cycle |
| `fleet/references/dead-man.md` | Steward protocol |
| `fleet/references/operator-mail.md` | Human escalation |
| `fleet/references/dual-channel.md` | Vivi + tmux |
| `fleet/references/runtime-config.md` | fleet.json / baseline / wind-down |
| `fleet/references/ssh-remote.md` | Remote Hands/Heads |
| `fleet/scripts/steward.sh` | Arm/rearm/disarm/trip (needs §8 fixes) |
| `docs/fleet-guide.md` | First-exposure vocabulary |

## 13. Recommendation (author)

1. **Accept** session-attach: Mind = ephemeral join; fleet = durability; ≤1 Mind per fleet.
2. **Accept** tmux: session per fleet, window per role.
3. **Accept** multi-fleet cycle: full mini-cycle each supervised fleet; fleets on `FLEET_CYCLE` line; per-fleet ticks.
4. **Drop** v1 roster, global baseline, attention modes, fairness scheduler, consolidated paging.
5. **Keep** Vivi mailspaces, short role mail, per-fleet steward, per-fleet operator@.
6. **Vocabulary:** fleet only.
7. **Ship** §8 step 1 scripts first; topology + attach/detach next; live fleets last when idle.

## 14. Decision log

| Date | Decision | Notes |
| --- | --- | --- |
| 2026-07-11 | Draft v1 | Single Mind + loop + roster + global baseline |
| 2026-07-11 | Review | Decouple topology/scheduling; flag `soft_hold_hands`; `budget_ms` unenforceable |
| 2026-07-11 | Draft v2 session-attach | Drop roster/global/modes/budget; ephemeral Mind; one Mind/fleet; attach + advisory lock; computed recap |
| 2026-07-11 | Draft v2.1 operator locks | Mini-cycle all supervised; per-fleet ticks; fleets on topic line; dual-attach OOS; fleet vocabulary |
| 2026-07-11 | Skill implementation | `multi-fleet.md` + SKILL/refs; `steward.sh` uses `tmux_target`; live topology migrate not required |

---

*End of design draft v2.1 (skill-implemented process; topology migrate optional).*
