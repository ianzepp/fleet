# Design: Multi-fleet Mind sessions (session-attach model)

**Status:** v2.1 — **process landed in `$fleet` skill** (2026-07-11); live fleet topology migration optional / deferred  
**Date:** 2026-07-11  
**Skill:** `$fleet`  
**Audience:** operator + reviewing agent / human  
**Skill entry:** [`multi-fleet.md`](multi-fleet.md)

---

## 1. Purpose

Describe a model in which:

- A **Mind session** (one operator TUI / conversation) **attaches to a selected set of fleets** (one or more).
- Multiple Mind sessions may coexist on the same host or across hosts, each with its own attached set, **as long as no fleet is attached to two Mind sessions at once**.
- The Mind session is an **ephemeral join** — the only place cross-fleet awareness lives. It has no durable global body.
- Everything that must **persist** persists **per fleet**, in that fleet's `<project>/.vivi/`. The fleet is the durability boundary.

This document is for review. **No skill rewrite is required until accepted.**

### Terminology

**Fleet** is the only unit name: one project root + `.vivi/` overlay. Use multi-fleet, fleet_id, session-per-fleet. Do not use camp, hunter-gatherer, or pre-rename Head/Hand identity strings in process docs.

### What changed from v1

v1 proposed a single global Mind + one loop + an on-disk roster + a Mind-level baseline managing all fleets. v2 drops all of that. The Mind session is transient; there is no roster file, no global baseline, no cross-fleet index on disk, no fleet attention modes, no budget/fairness scheduler. Cross-fleet state is in-session only and rebuilt from per-fleet baselines on attach. What remains worth building is per-fleet: the tmux topology, a few script fixes, and an explicit attach/detach protocol.

### What changed in v2.1 (operator lock)

| Topic | Decision |
| --- | --- |
| One FLEET_CYCLE | **Scan all fleets under supervision** (full fail-fast mini-cycle each) |
| Durable ticks | Each fleet writes its **own** `last_successful_cycle_at` / steward rearm |
| Attached set visibility | List fleets on the **`FLEET_CYCLE` subject/topic line** (chat history = attach/detach log) |
| Dual-attach race | **Do not over-engineer** — edge case; advisory lock is enough |
| Vocabulary | **Fleet** only |

## 2. Goals and non-goals

### Goals

1. **Many terminals, disjoint fleets** — terminal 1 attaches to fleets A+B; terminal 2 attaches to fleet C; neither clobbers the other.
2. **No global files** — nothing authoritative lives outside a fleet's own project directory.
3. **One Mind session per fleet** — prevent accidental dual-Mind-on-one-fleet (steward rearm races, double operator-mail presentation) without a global lock.
4. **Machine-safe process naming** — no tmux collisions when two fleets on one host both have a `hand-1`.
5. **Preserve single-fleet simplicity** — today's one-fleet-per-conversation operation is already this model with attached-set = {one fleet}; v2 just makes multi-fleet explicit and adds the protocol.
6. **Keep existing ops semantics** — bag vs gates, dual channel, steward dead-man, operator mail, fail-fast cycles, mode-gated reporting.

### Non-goals

1. A single Mind that manages every fleet everywhere.
2. A global roster, global baseline, or cross-fleet index file on disk.
3. Auto-discovery of every `.vivi/` under the home directory.
4. Shared Hands, shared boards, or cross-repo merge clocks.
5. Fleet modes (`full`/`watch`/`paused`), `max_fleets_per_fire`, `fairness`, or `budget_ms` — attention budget is the operator's terminal layout, not a scheduler.
6. A global system service that babysits all fleets.
7. ~~Implementing the change in this document (design only).~~ — **Skill process implemented**; migrating existing fleets’ tmux topology remains optional.

## 3. Vocabulary

| Term | Meaning |
| --- | --- |
| **Fleet** | One project root with a fleet overlay (`.vivi/fleet.json`, mailspace, baseline). The durability boundary. Canonical term. |
| **Mind session** | One operator TUI / conversation. Ephemeral. Attaches to a set of fleets. The only place cross-fleet state lives. |
| **Attached set** | The fleets a given Mind session is currently supervising. Named on each `FLEET_CYCLE` line; not a global on-disk roster. |
| **Attach / detach** | Mind session takes over / releases a fleet. Detach has steward consequences (see §6.5). Visible by changing the cycle topic line. |
| **Hand / Head** | Worker / advisor roles with mail + process slots, per fleet. |
| **Steward** | Per-fleet dead-man watchdog (completed-cycle ticks → hold + page). |
| **operator@** | Per-fleet human escalation inbox (not status). |
| **fleet_id** | Short alias for a fleet; equals its tmux session name on a host. Host-scoped, not globally registered. |
| **Mini-cycle** | One fleet’s fail-fast gather/act/rearm inside a multi-fleet `FLEET_CYCLE` fire. |

Metaphor: fleets are ships in different harbors. A Mind session is a harbor master's desk that may watch several harbors at once; when the desk closes, the harbors keep their own logs. There is no worldwide harbor registry.

## 4. Current state (as of 2026-07-11)

### 4.1 Control plane (today)

```text
Mind = operator TUI (this conversation)
  + optional board identity mind@<mailspace>.local  (no tmux)
  + optional scheduled FLEET_CYCLE in the same TUI, project=<root>

Hands / Heads / steward = mail + tmux process slots, per fleet
```

Today's single-fleet operation is **already** the session-attach model with an attached set of one. v2 generalizes the set to ≥1 and makes attach/detach explicit.

### 4.2 Dual channel (per fleet, unchanged)

| Channel | Truth of |
| --- | --- |
| **Vivi project mailspace** | Work: tasks, needs, done, Head reports, operator mail |
| **tmux** | Process: alive / idle / running / error; pointer doorbells only |

**Binding rule (current skill default):**

```text
mail_identity == tmux_session token
(Hands / Heads / steward only; mind + operator have no tmux)
```

Example:

```text
mail:  hand-1@minted-geek-swarm.local
tmux:  session hand-1, target hand-1:1.1
```

### 4.3 Fleet overlay (per project, unchanged)

```text
<project>/
  .vivi/
    fleet.json           # roster of hands/heads, models, cwd, tmux_*
    mind-baseline.json   # cycle counters, fingerprints, steward state, mind_session lock
    mail.sqlite          # board of record for this mailspace only
    steward.log          # dead-man log
    mind-watch.cursor
  factory/               # product map (fleet-specific)
```

Mailspace domain is project-local. **Two fleets never share a Vivi store.** Board isolation is already solved and stays per fleet.

### 4.4 Mind cycle (single fleet, today)

```text
FLEET_CYCLE project=/path/to/one/fleet …
```

Fail-fast path: resolve mode → cheap sensors → act only on signal → quiet if fingerprint unchanged → steward rearm → (on stop) steward disarm.

### 4.5 Steward / dead man (today, per fleet)

- Fleet-local tmux session `steward` + `scripts/steward.sh`.
- Mind **rearms** after every successful `FLEET_CYCLE`.
- Miss past grace → trip: baseline hold, **operator@**, optional preauthorized external email, soft-hold pointers to idle Hands.
- Already `--project` scoped. **Already per-fleet — no redesign needed for isolation.**

### 4.6 Scaling limit (why this design exists)

If the operator runs **two fleets on one host** with today's binding:

```text
Fleet A: tmux sessions hand-1, hand-2, head-ceo, steward
Fleet B: tmux sessions hand-1, hand-2, …   ← COLLISION
```

Also: there is no explicit attach/detach, so closing a terminal orphans the fleet (steward trips) or leaves it ambiguously owned. And there is no cheap cross-fleet recap when one Mind session watches several fleets.

Mailspaces do **not** need redesign. Process topology and session ownership do.

## 5. Problem statement

| # | Problem |
| --- | --- |
| P1 | **tmux session names collide** across fleets on one host when both use `hand-1`. |
| P2 | **No explicit attach/detach** — closing a terminal orphans the fleet (steward trips) or leaves dual-Mind ambiguity. |
| P3 | **No cheap cross-fleet recap** when one Mind session watches several fleets, without merging boards or writing a global file. |
| P4 | **Accidental dual-Mind-on-one-fleet** causes steward rearm races and double operator-mail presentation. |
| P5 | **Scripts assume session name == role** (`steward.sh` `soft_hold_hands`, `ensure_tmux_session`), which breaks under any topology change. |

## 6. Proposed model

### 6.1 Mental model

```text
Mind session S1 (terminal 1) ──attach──► Fleet A ; Fleet B
Mind session S2 (terminal 2) ──attach──► Fleet C

  S1 and S2 coexist: attached sets {A,B} and {C} are disjoint.
  No fleet appears in two sessions.
  No file outside any fleet's <project>/.vivi/ is authoritative.
```

A Mind session is the **ephemeral join**: while alive it holds the cross-fleet view (which fleets, their headlines, their operator mail). When it ends, nothing global remains — each fleet's baseline still records what that Mind did. A new Mind session starts blind and re-sensors.

### 6.2 Invariant: at most one Mind session per fleet

> A single Mind session may attach to multiple fleets. No fleet may be attached to two Mind sessions at once.

This replaces the skill's old "Mind is *the* operator TUI" (one Mind total) with the actual invariant: **one Mind *per fleet***. Multiple Mind sessions are fine for disjoint fleets. Enforced per-fleet via a session lock in the fleet's own baseline (§6.6) — no global lock file.

### 6.3 Process topology (session per fleet, window per role)

**tmux session = fleet_id**
**tmux window = role**
**tmux pane = agent process** (usually one pane per window)

```text
session mgs
  window hand-1     → target mgs:hand-1.1
  window hand-2     → target mgs:hand-2.1
  window head-ceo   → target mgs:head-ceo.1
  window steward    → target mgs:steward.1

session faber
  window hand-1     → target faber:hand-1.1
  …
```

| Plane | Identity |
| --- | --- |
| Board (Vivi) | Short role token: `hand-1@<mailspace>.local` (unchanged) |
| Process (tmux) | `session:window` = `fleet_id:role` |

Two fleets on one host both have a `hand-1` **window** — no collision, because they live in different sessions (`mgs:hand-1` vs `faber:hand-1`).

**Proposed binding rule (multi-fleet-aware):**

```text
mail_identity     == role token (hand-1, head-ceo, …)   # fleet-local board
tmux_session      == fleet_id                            # host-scoped
tmux_window       == role token                         # within session
tmux_target       == {fleet_id}:{role}.1                 # ops address
```

Single-fleet **legacy topology** (still allowed until a fleet migrates):

```text
mail_identity == tmux_session == hand-1
tmux_target   == hand-1:1.1
```

#### Why session-per-fleet (not prefixed flat sessions)

| | Prefixed sessions (`mgs-hand-1`) | Session = fleet, window = role |
| --- | --- | --- |
| Collision-free | Yes | Yes |
| `tmux attach` whole fleet | Many sessions | `attach -t mgs` |
| Kill whole fleet | N kills | `kill-session -t mgs` |
| Operator mental model | Role-first | Fleet-first |
| Matches "harbor then ship" | Weak | Strong |

**Preference:** session-per-fleet + window-per-role.

#### Window vs pane (decision)

**One pane per role window.** Keeps the binding rule unambiguous: one process slot per role, `tmux_target` points at exactly one pane. If an operator wants a multi-pane dashboard for viewing, it is a separate `dashboard` window that is **not** a process slot and not addressable as a role. Do not mix panes into role windows.

#### Head windows (decision)

**Lazy-create on first assign.** Declare available Heads in fleet.json, but do not arm their windows until first Mind assign or first bucket request. Always-arming head-ceo/cto/cxo means 3 idle advisor windows per fleet × N fleets; footprint should track actual use.

### 6.4 Window naming is a `tmux_target` format change

Today `tmux_target: "hand-1:1.1"` means session `hand-1`, **window `1`** (numbered). The proposed form `mgs:hand-1.1` uses a **named window** `hand-1`. Both are valid tmux, but:

- Any script that **splits `tmux_target` on `:` expecting a numeric window** breaks. Audit every parser.
- **Creation commands change.** `new-session -s mgs` yields window `1`; the first role window needs `new-session -s mgs -n hand-1`, subsequent ones `new-window -t mgs -n hand-2`.
- The fleet.json schema already has `tmux_target` per hand, so the new form is **representable today** — this is a format migration, not a schema addition.

### 6.5 Attach / detach protocol

Attaching a fleet means a Mind session takes over steward rearm and cycle responsibility for it. **Detaching is not free** — an ungraceful close leaves the fleet's steward to trip after grace.

**Attach (fleet → Mind session):**

1. Read `<fleet>/.vivi/mind-baseline.json` → check `mind_session` lock (§6.6).
2. If locked under a live foreign session → refuse, or require explicit `--takeover`.
3. Write `mind_session = {label, host, pid, attached_at}`; set `mind_loop.state = running`.
4. If fleet has a scheduled loop: `steward.sh arm --project <fleet>` (only if not already armed by a prior session you're replacing via takeover).
5. Sensor the fleet; present its baseline view (operator mail, tripped?, headline) into the session's cross-fleet recap.

**Detach (Mind session → fleet):**

1. Stop filing new work to this fleet; absorb/record any in-flight state into its baseline.
2. `steward.sh disarm --project <fleet>` — **same turn**, so the dead man does not false-trip.
3. Set `mind_loop.state = detached`; clear `mind_session` (or mark `detached_at`).
4. Leave Hands/Heads alive if mid-unit (operator may reattach); otherwise optional `tmux kill-session -t <fleet_id>`.

A Mind session ending without detaching its fleets is the **orphan** case: those fleets' stewards trip after grace. That is the correct failsafe — it signals "Mind died without orderly detach." Recovery is `steward.sh clear` + reattach from a new session.

### 6.6 Per-fleet Mind-session lock (advisory)

Lives in the fleet's own `mind-baseline.json` (runtime state, not config):

```json
"mind_session": {
  "label": "term1",
  "host": "pharos",
  "pid": 12345,
  "attached_at": "2026-07-11T14:02:00Z"
}
```

- **Advisory, not a kernel mutex.** Mind sessions are human-driven; a hard cross-process lock is fragile. The lock's job is to prevent *accidental* dual-Mind-on-one-fleet.
- On attach, if `mind_loop.state == running` and `mind_session` is present and recent → warn and require `--takeover` to proceed.
- PID-liveness check only works same-host; treat it as a hint. For remote Mind sessions, the label + `attached_at` is the only signal.
- Forced takeover overwrites the lock. A stale lock from a crashed session is cleared on takeover (same as any per-fleet recovery).

### 6.7 Computed cross-fleet recap (in-session only)

There is **no cross-fleet index file.** On attach or on operator return, a Mind session builds the cross-fleet view by reading each attached fleet's baseline:

```text
for fleet in attached_set:
  read <fleet>/.vivi/mind-baseline.json
    → operator_mail.open_count, steward.tripped, last_cycle, headline, operator_recap
present combined table (fleet | tripped? | op-mail | headline)
```

- **Computed, not stored.** Survives `/compact` via the session's recap keep-list (already in the skill). A *new* Mind session starts blind and re-sensors from per-fleet baselines.
- Tripped stewards are presented first; then operator mail union across attached fleets; then per-fleet headlines.
- This is a **deliberate trade**: cross-fleet queries are session-scoped sweeps, not global lookups. For a few fleets this is a cheap sensor pass. If the operator wants a standing global view, that is out of scope (non-goal 2) — attach a session and sweep.

### 6.8 Multi-fleet FLEET_CYCLE (operator lock)

**One cycle fire = scan every fleet under this Mind session’s supervision.**

```text
FLEET_CYCLE fleets=mgs,faber,orqa project_roots=…   # topic line names the attached set
  for fleet in fleets:                                 # order: as listed on the line
    fail-fast mini-cycle for fleet only
      sensors → act on signal → quiet if unchanged
      write fleet's mind-baseline last_successful_cycle_at
      steward.sh rearm --project <that fleet root>
  emit multi-fleet report (one line/block per fleet)
```

| Rule | Detail |
| --- | --- |
| **Coverage** | All fleets on the cycle topic line get a mini-cycle every fire (no watch/paused scheduler) |
| **Durability** | Each fleet stores its **own** `last_successful_cycle_at` / rearm — never a global tick |
| **Attached set** | **Named on the `FLEET_CYCLE` line** so attach/detach is visible in chat history |
| **Cross-board** | Never file To fleet A’s bag while processing fleet B; always `--project` + that fleet’s `tmux_target` |
| **Steward** | Rearm only the fleet whose mini-cycle just completed |

#### Topic line as attach log

```text
# supervising three fleets
FLEET_CYCLE fleets=mgs,faber,orqa …

# detach orqa (edit loop prompt / next fire)
FLEET_CYCLE fleets=mgs,faber …

# single-fleet (today’s shape; still valid)
FLEET_CYCLE project=/path/to/mgs …
```

No on-disk roster is required. The **durable loop prompt** (or each injection’s first line) is the source of truth for “what am I supervising?” After `/compact`, the next `FLEET_CYCLE` line re-states the set. Changing the set = attach/detach protocol (§6.5) plus updating the line.

Optional path map (not control plane): shell aliases or a non-authoritative hint file from `fleet_id` → project root, if the topic line lists ids only.

### 6.9 Steward under multi-fleet (per fleet, unchanged)

| Property | Design |
| --- | --- |
| Count | **One steward per fleet** (window `steward` in that fleet's session; migrate off standalone session `steward`) |
| Tick | That fleet's `last_successful_cycle_at` |
| Rearm | After that fleet's mini-cycle succeeds |
| Trip | Pages **that fleet only** — per-fleet paging is correct because the fleet is the persistence boundary |
| Soft-hold | Only **that fleet’s** Hands — never soft-hold another attached fleet |
| Detach | `steward.sh disarm` on detach (§6.5); otherwise orphan → trip |

If one Mind session dies and takes down the two fleets attached to it, **two pages for two tripped fleets is the right severity signal**, not a bug to dedupe. There is no consolidated multi-fleet page (v1's consolidated paging is withdrawn).

### 6.10 Reporting (in-session, mode-gated)

Reporting follows the **existing** Mind interaction modes (autonomous thin / interactive rich) from the skill — no new mode machinery. A Mind session with multiple attached fleets emits one report per cycle covering each attached fleet:

```text
cycle 42 · fleets=mgs,faber
  mgs     acted: absorb … wake hand-2
  faber   sleep: bags empty panes running
```

Interactive sessions get richer per-fleet blocks; autonomous stays compact. Operator-return presents the computed cross-fleet recap (§6.7).

### 6.11 Remote fleets

A Mind session may attach to a fleet whose Hands/Heads are on a remote host. Rules:

- `fleet_id` / `tmux_session` is **host-scoped** — the same `fleet_id` on a remote host is fine (tmux namespaces are per-host).
- The fleet's baseline and `mind_session` lock live in the fleet's **local** project dir (the board is local even when hands are remote).
- Wake/capture/reinit run on the host that owns the pane (SSH-wrap or remote script), unchanged from the existing remote-Hands design.
- The collision to avoid is two fleets **on the same host** sharing a `tmux_session`, not two fleets sharing a `fleet_id` across hosts.

### 6.12 fleet.json fields (proposed additions)

```json
{
  "fleet_id": "mgs",
  "tmux_layout": "session_per_fleet",
  "binding_rule": "mail_identity == tmux_window; tmux_session == fleet_id",
  "hands": {
    "hand-1": {
      "mail_identity": "hand-1",
      "tmux_session": "mgs",
      "tmux_window": "hand-1",
      "tmux_target": "mgs:hand-1.1"
    }
  },
  "steward": {
    "tmux_session": "mgs",
    "tmux_window": "steward",
    "tmux_target": "mgs:steward.1"
  }
}
```

The `mind_session` lock does **not** live here — it is runtime state in `mind-baseline.json`.

Scripts (`steward.sh`, `codex-reinit.sh`, doorbell) must prefer **`tmux_target`** over assuming session name == role.

### 6.13 Arm / kill UX

```bash
# whole fleet process group
tmux attach -t mgs
tmux kill-session -t mgs

# one role
tmux select-window -t mgs:hand-1
tmux send-keys -t mgs:hand-1.1 …
```

## 7. Alternatives considered

| Alternative | Pros | Cons | Verdict |
| --- | --- | --- | --- |
| **v1: one Mind, one loop, on-disk roster + global baseline** | Single control plane; explicit budget | Global files clobber across terminals; over-engineered for one operator | **Reject** (this doc replaces it) |
| One Mind TUI per fleet (today, N terminals) | Zero multi-fleet design | N terminals to manage; no cross-fleet recap when wanted | Acceptable, but doesn't solve P3 |
| Prefixed flat sessions (`mgs-hand-1`) | Minimal script change | Noisy `tmux ls`; weak fleet grouping | Acceptable fallback |
| Session = fleet, window = role | Clean multi-fleet; attach per fleet | Migration of live fleets; script updates | **Preferred** |
| Global steward service | Survives everything | Scope creep; multi-repo scan risk | Reject |
| Auto-discover fleets under home trees | Convenient | False fleets; surprise ops | Reject |
| Shared board for all fleets | One inbox | Cross-talk; breaks segregation | Reject |
| Attention modes + budget/fairness scheduler | Explicit attention budget | Scheduler machinery; budget not enforceable | **Reject** (attention = terminal layout + which fleets are on the cycle line) |
| Hard dual-attach mutex / CAS | Would prevent simultaneous attach races | Over-engineering for an edge case | **Reject** — advisory lock + operator awareness is enough |

## 8. Migration sketch (after acceptance)

Not to execute now — outline only. Decoupled; all per-fleet.

1. **Script fixes (required, independent of topology).**
   - `steward.sh` `soft_hold_hands`: currently hardcodes `hand-1`/`hand-2` as **session names** and targets `${sess}:1.1`. Under session-per-fleet these `has-session` checks fail and **hold pointers silently no-op on every trip.** Rewrite to read each hand's `tmux_target` from fleet.json.
   - `steward.sh` `ensure_tmux_session`: targets `${sess}:1.1` for its own pane instead of reading the steward `tmux_target`. Fix to use fleet config.
   - Audit `codex-reinit.sh` and the doorbell path for the same hardcoded-session pattern.
2. **Topology (session-per-fleet).** New fleets use it from day one. Existing fleets migrate optionally (see step 4).
3. **Attach/detach protocol + lock.** Add `mind_session` to the baseline schema; add `mind_loop.state = detached`; implement attach/detach as a Mind procedure (and optionally a small helper).
4. **Existing fleet (e.g. MGS).** Migrate **last**, only when idle, and only after steps 1–3 are proven on a non-production fleet. Don't debug topology on the fleet you depend on.
5. **Validation.** Two fleets on one host both run a `hand-1` window without tmux collision; a Mind session attaches to both and reports both without cross-board filing; detaching one disarms only that fleet's steward.

Rollback: a fleet with `tmux_layout` unset keeps the legacy topology. The session-attach model itself is not a rupture — today's single-fleet operation already is it.

## 9. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| `steward.sh` hold pointers silently no-op under new topology | Script fix step 1 (§8); required before any fleet migrates |
| `tmux_target` parsers expecting numeric windows | Audit all parsers; named windows are valid tmux |
| Orphaned fleet on ungraceful terminal close | Steward trips after grace — correct failsafe; recovery is `clear` + reattach |
| Stale `mind_session` lock from crashed session | Advisory lock; forced `--takeover` overwrites |
| Accidental dual-Mind-on-one-fleet | Attach checks the lock; warns and requires `--takeover` |
| Simultaneous dual-attach race | **Accept** as edge case; do not build CAS; last writer / operator resolves |
| Cross-fleet recap lost on session end | Deliberate; per-fleet baselines persist; new session re-sensors |
| Live agent mid-migrate | Migrate only idle windows; or new session parallel then cut over |
| Soft-hold wrong fleet on trip | Soft-hold only Hands belonging to the tripped fleet’s targets |

## 10. Open questions

1. **Mind-session identity:** stable id for the lock — operator-chosen `label` + host + pid + `attached_at`, or derive from the harness? Recommend the former (lightweight, human-readable).
2. **Stale lock recovery:** auto-detect dead pid (same-host only) and auto-clear, or always require explicit `--takeover`? Recommend explicit takeover; auto-clear is a nice-to-have.
3. **Known-fleets hint:** non-authoritative `fleet_id` → project path map (shell aliases / hint file) when the cycle line lists ids only? Recommend yes; **not** control plane.
4. **Migrate MGS immediately?** No — scripts first, new fleet second, MGS last when idle (§8 step 4).
5. **Attach behavior:** auto-sensor + present recap on attach, or require an explicit `status` command? Recommend auto-present (matches operator-return UX).

**Closed (v2.1 operator):** multi-fleet cycle = full mini-cycle per supervised fleet; fleets on `FLEET_CYCLE` line; dual-attach race ignored; vocabulary = fleet not fleet.

(Carryover window/pane and Head-lazy from v1 are answered in §6.3. v1's roster-location, default-mode, and fairness questions are dissolved by this model.)

## 11. Success criteria (when built)

1. Two fleets on one host both run a `hand-1` **window** without tmux collision.
2. A Mind session attaches to multiple fleets and reports each without cross-board filing.
3. One `FLEET_CYCLE` fire mini-cycles **every** fleet on its topic line and rearms each fleet’s steward separately.
4. Detaching a fleet (drop from topic line + detach protocol) disarms only that fleet’s steward.
5. A second Mind session attaching to an already-attached fleet is refused unless `--takeover` (best-effort advisory).
6. Closing a terminal without detach → the orphaned fleet's steward trips after grace (correct failsafe).
7. A new Mind session re-sensors attached fleets from their per-fleet baselines — no global file needed.
8. Single-fleet legacy topology still works until opt-in.

## 12. Related skill surfaces (current)

| Path | Topic |
| --- | --- |
| `fleet/SKILL.md` | Roles, dual channel, modes, cycle |
| `fleet/references/dead-man.md` | Steward protocol |
| `fleet/references/operator-mail.md` | Human escalation inbox |
| `fleet/references/dual-channel.md` | Vivi + tmux |
| `fleet/references/runtime-config.md` | fleet.json / baseline / wind-down |
| `fleet/references/ssh-remote.md` | Remote Hands/Heads |
| `fleet/scripts/steward.sh` | Arm / rearm / disarm / trip (needs §8 fixes) |
| `docs/fleet-guide.md` | First-exposure vocabulary |

## 13. Recommendation (author)

1. **Accept** the session-attach model: Mind session = ephemeral join; fleet = durability boundary; at most one Mind session per fleet.
2. **Accept** tmux topology = session per fleet, window per role.
3. **Accept** multi-fleet cycle = full mini-cycle per supervised fleet; fleets listed on `FLEET_CYCLE` line; per-fleet success ticks.
4. **Drop** v1's roster, global baseline, attention modes, budget/fairness scheduler, and consolidated paging.
5. **Keep** Vivi mailspaces, short role mail identities, per-fleet steward, and per-fleet operator@ unchanged.
6. **Vocabulary:** fleet only.
7. **Ship** script fixes (§8 step 1) first; topology and attach/detach protocol after; migrate live fleets last and only when idle.

## 14. Decision log

| Date | Decision | Notes |
| --- | --- | --- |
| 2026-07-11 | Draft v1 opened | Single Mind + one loop + roster + global baseline; second opinion requested |
| 2026-07-11 | Review: decouple topology/scheduling; flag steward script regressions | Session-per-fleet vs prefixed; `soft_hold_hands` hardcoding; `budget_ms` not enforceable |
| 2026-07-11 | Draft v2: session-attach model | Drop roster/global-baseline/modes/budget; Mind session = ephemeral join; fleet = durability boundary; one Mind session per fleet; attach/detach protocol + advisory per-fleet lock; computed cross-fleet recap |
| 2026-07-11 | Draft v2.1 operator locks | One cycle = mini-cycle all supervised fleets; per-fleet `last_successful_cycle_at`; fleets on `FLEET_CYCLE` topic line; dual-attach race out of scope; **fleet** not **fleet** (skill rewrite later) |
| 2026-07-11 | Skill implementation | `references/multi-fleet.md`; SKILL + mind-cycle/dual-channel/dead-man/runtime-config; `steward.sh` uses fleet.json `tmux_target` + hand targets; codex-reinit already target-based. Live topology migration not required. |

---

*End of design draft v2.1 (skill-implemented process; topology migrate optional).*
