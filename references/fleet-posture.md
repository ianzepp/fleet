# Fleet posture (continuity vs sleep)

**Audience:** Mind (multi-fleet or single). Not every quiet cycle — load when bags empty, map looks thin, or operator sets on-call fleets.

**Problem:** “Keep bags full / don’t get stuck” without a **value gate** → invent polish, thrash `$polish`/`$housekeeping`, burn tokens for the appearance of motion.

**Invariant:** Progress = honest product work (or an explicit pause). **Willing to sleep is success** when the charter says so.

## Posture modes

Stored on the fleet overlay (`fleet.json` → `fleet_posture`) and mirrored in baseline for recap.

| Mode | Intent | Empty bags + no real map unit |
| --- | --- | --- |
| **`growth`** (alias: `campaign`) | Ship a map; keep spine moving | Starvation refill **if** unblocked product unit exists; else continuity consult or sleep |
| **`standby`** (alias: `on_call`) | On-call until field/operator need | **Quiet is success** — do not invent work |
| **`dormant`** | Explicit pause | Sensors/absorb only; no product filing; optional pane drop |

Examples: active campaign fleets → `growth`. Vivi-shaped “feature when I need it” → `standby`. Stage complete waiting on humans → `dormant` or wind-up.

**Orthogonal to:**

| Layer | Meaning |
| --- | --- |
| `mind_mode` | interactive / autonomous (operator engagement) |
| `mind_loop.state` | running / detached / wound_up (process lifecycle) |
| Hand operational pause | packet paused, merge wait, mid-unit |
| Steward | dead-man opt-in — not product posture |

## Schema

```json
"fleet_posture": {
  "mode": "growth",
  "reason": "one line — why this posture",
  "since": "2026-07-11T00:00:00Z",
  "wake_triggers": [
    "operator product task/need",
    "operator@ need with default",
    "named campaign unit accepted"
  ],
  "last_ceo_continuity_at": null,
  "ceo_continuity_min_hours": 6
}
```

| Field | Rule |
| --- | --- |
| `mode` | `growth` \| `standby` \| `dormant` (default **`growth`** if missing — campaign fleets) |
| `wake_triggers` | What moves standby/dormant → growth (operator text, board, external) |
| `ceo_continuity_min_hours` | Min gap between continuity CEO assigns (default 6) — no thrash |

Baseline may copy `mode` / `reason` for recap; fleet.json remains source of truth for charter.

## Starvation vs makework (hard)

| May file (starvation) | Must **not** file as continuity |
| --- | --- |
| Map unit with clear product done-when | “Polish something” / drive-by cleanup |
| Honest residual on open goal | Second polish advisory same tip without new land |
| pending_merges / spine residual | `$housekeeping` outside major inflection |
| Operator- or CEO-named product package | Empty-bag theater to silence sensors |

**Ban:** invent work (including polish/HK loops) to keep Hands busy or to clear `starvation_candidate_*`.

Hygiene remains: Hand end-of-unit polish; post-main polish advisory **once per tip** above threshold — not a treadmill.

## Mind decision tree (per fleet mini-cycle)

```text
1. Drain real signal: **operator→mind** + To operator@, absorb done/HEAD, open bags, pending_merges/reviews
2. Open product bag → wake (doorbell/reinit) as today — no invention
3. posture in {standby, dormant}:
     → do not starvation-file; sleep/quiet report; optional absorb only
4. posture growth (or missing → treat as growth):
     if honest unblocked map unit → file+wake
     elif map empty / only makework / doubt value →
         if continuity CEO not awaiting and gap ≥ ceo_continuity_min_hours:
             assign head-ceo: continue vs pause/dormant + optional units with costs
             default while waiting: sleep (no invent)
         else: sleep
5. Never file polish/HK solely because starvation_candidate fired
```

## head-ceo continuity consult

Not every quiet cycle. Not side-lane bucket spam.

**When (growth only):** map looks empty, only hygiene left, or Mind cannot name a valuable next unit.

**Assign (mail To head-ceo, clean slate):**

```text
Continuity: should this fleet keep shipping, pause (standby/dormant), or wind-up?
- Charter/posture today: <mode> — <reason>
- Map state: <empty | residual list | stage just closed>
- Bags: empty / open counts
Answer: continue (name ≤N product units with effort/est_tokens) OR recommend standby|dormant|wind-up with trigger conditions.
Do not invent polish makework. Report To mind@.
```

| Mind does | head-ceo does not |
| --- | --- |
| Decide / set posture / file real units | File Hand tasks |
| Sleep with default while awaiting report | Re-ask every FLEET_CYCLE |
| operator@ if posture change is human-only | Own empty-bag refill |

## Warm-up / cool-down

| Transition | How |
| --- | --- |
| standby/dormant → growth | Operator asks; or real product task/need lands; or Mind accepts named unit after CEO/operator |
| growth → standby/dormant | CEO recommends + Mind accepts; or operator sets posture; or empty map + long quiet with default=pause |
| Rearm panes | If wound_up: recreate from fleet.json; else leave idle panes |

Warm-up is not “fill polish.” First unit must be product-shaped.

## Multi-fleet

One `FLEET_CYCLE` mini-cycles every slug. **Per-fleet posture:**

- **growth** fleets: full act path  
- **standby/dormant** fleets: fail-fast quiet (seconds) — do not invent work so the multi-fleet table looks busy  

Report one line/block per fleet including `posture=…`.

## Sensors

When `fleet_posture.mode` ∈ {`standby`, `dormant`}, do **not** emit `starvation_candidate_*` (empty idle Hands are expected). Wake candidates for **open bags** still fire.

## Anti-patterns

- Polish/HK as continuity fuel  
- Filing wants/tasks with no map unit or operator intent  
- head-ceo continuity every quiet cycle on standby fleets  
- Treating `starvation_candidate` as mandatory act  
- Multi-fleet “fairness” busywork on quiet fleets  
- Confusing dormant with steward trip or wound_up (related but distinct)

## Related

| Topic | Path |
| --- | --- |
| Starvation table | [`tasking.md`](tasking.md) |
| CEO loops | [`heads.md`](heads.md) |
| Wind-up | [`runtime-config.md`](runtime-config.md) |
| Multi-fleet mini-cycle | [`multi-fleet.md`](multi-fleet.md) |
| Cycle reports | [`mind-cycle.md`](mind-cycle.md) |
