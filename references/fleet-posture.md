# Fleet posture (continuity vs sleep)

**Audience:** Mind (multi-fleet or single). Not every quiet cycle — load when bags empty, map looks thin, or operator sets on-call fleets.

**Problem:** “Keep bags full / don’t get stuck” without a **value gate** → invent polish, thrash `$polish`/`$housekeeping`, burn tokens for the appearance of motion.

**Invariant:** Progress = honest product work (or an explicit pause). **Willing to sleep is success** when the charter says so.

## Posture modes

Stored on the fleet overlay (`fleet.json` → `fleet_posture`) and mirrored in baseline for recap.

| Mode | Intent | Empty bags + no real map unit | Head proactivity |
| --- | --- | --- | --- |
| **`growth`** (alias: `campaign`) | Ship a map; keep spine moving | Starvation refill **if** unblocked product unit exists; else continuity consult or sleep | **Aggressive:** map integrity + expansion, inversions, side-lanes |
| **`standby`** (alias: `on_call`) | On-call until field/operator need | **Quiet Hands is success** — do not invent product work | **Stewardship:** priority/status/opt/correctness of **current** product — not new campaigns |
| **`dormant`** | Explicit pause | Sensors/absorb only; no product filing; optional pane drop | **Rarely / never** — assign-only; cadence sweeps paused |

Examples: active campaign fleets → `growth`. Vivi-shaped “feature when I need it” → `standby`. Stage complete waiting on humans → `dormant` or wind-up.

**Hands vs Heads:** standby suppresses **Hand starvation refill** and polish theater. It does **not** mean “never run executives.” Dormant pauses **both** product filing and default executive cadence.

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

### Change posture safely

Use the posture helper instead of hand-editing the overlay:

```bash
python3 scripts/fleet-posture.py get --project <root>
python3 scripts/fleet-posture.py set --project <root> standby \
  --reason 'maintenance by default; assigned tasks and campaigns only'
python3 scripts/fleet-posture.py set --project <root> growth \
  --reason 'campaign <name> activated' \
  --wake-trigger 'operator task or need' \
  --wake-trigger 'named campaign unit accepted'
```

`set` preserves unspecified posture fields, stamps `since`, strictly validates a temporary candidate, and atomically replaces `fleet.json`. It does **not** wake roles, bump the baseline, run sensors, or arm the steward. The current or next Mind cycle observes the new source-of-truth posture and handles runtime consequences. Use `--json` for automation.

## Starvation vs makework (hard)

| May file (starvation) | Must **not** file as continuity |
| --- | --- |
| Map unit with clear product done-when | “Polish something” / drive-by cleanup |
| Honest residual on open goal | Second polish advisory same tip without new land |
| Feature branch ready for Mind merge decision | `$housekeeping` outside major inflection |
| Operator- or CEO-named product package | Empty-bag theater to silence sensors |

**Ban:** invent work (including polish/HK loops) to keep Hands busy or to clear `starvation_candidate_*`.

Hygiene remains: Hand end-of-unit polish; post-main polish advisory **once per tip** above threshold — not a treadmill.

## Mind decision tree (per fleet mini-cycle)

```text
1. Drain real signal: **operator→mind** + To operator@, absorb done/HEAD, open bags, reviews
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

## Heads by posture (strategist / correctness / purity)

`head-ceo` is the **strategist** seat (map research, misprioritization, gate honesty). Personas: [`heads/personas/`](heads/personas/). Loops: [`heads.md`](heads.md).

| Mode | head-ceo | head-cto | head-cxo | Cadence sweeps |
| --- | --- | --- | --- | --- |
| **growth** | Map-health + **expansion**; priority inversions; side-lane buckets | Bugs + technical gate honesty | Shape debt that blocks expansion | Due when head `every_n_loops >= 1` |
| **standby** | Stewardship only (priority/status/opt/correctness of current product) | Reliability / correctness of current product | Complexity that hurts on-call risk | Allowed (stewardship lens); not expansion |
| **dormant** | Assign-only | Assign-only | Assign-only | **Paused** by sensors |

### Executive cadence = one dial (`every_n_loops`)

One base tick: **`mind_loop.interval_sec`** (default **300** = 5m FLEET_CYCLE).

| `executive_cadence.every_n_loops` | Meaning |
| --- | --- |
| **`0`** | **On-call** — no `head_due_*` from schedule; Mind wakes only with an explicit task |
| **`N >= 1`** | **Scheduled** — sensors emit `head_due_*` every `N × mind_loop.interval_sec` |

```text
sweep_interval_sec = every_n_loops × mind_loop.interval_sec   # when every_n_loops >= 1
```

There is **no** separate `enabled` or `self_directed` flag. On-call vs scheduled **is** `every_n_loops`. When Mind wakes a scheduled Head, the assign is already “review/sweep mode” (persona + posture charter).

**Defaults** when `every_n_loops` is omitted and legacy `enabled: true` is set (or when migrating):

| Posture \ Head | head-cto | head-cxo | head-ceo | other heads |
| --- | --- | --- | --- | --- |
| **growth** | ×6 | ×12 | ×36 | on-call (0) |
| **standby** | ×18 | ×36 | ×72 | on-call (0) |
| **dormant** | paused | paused | paused | paused |

At default L=5m: growth ≈ **30m / 1h / 3h**; standby ≈ **1.5h / 3h / 6h**.

- Change **how often Mind ticks** → `mind_loop.interval_sec`.  
- Change **one Head’s schedule** → set that head’s `every_n_loops` (0 or N).  
- Prefer **explicit** `every_n_loops` on every Head in `fleet.json` so posture defaults are not a surprise.  
- Legacy `enabled: false` ≡ `every_n_loops: 0`. Legacy `enabled: true` without N uses the table above.  
- Legacy `self_directed` is **ignored** — remove it from overlays.  
- Sensors emit `sweep_every_n_loops`, `mind_loop_interval_sec`, `sweep_interval`, `sweep_enabled` (`every_n_loops >= 1`).

**Ban:** expansion candidates or new campaign surface while posture is standby/dormant.  
**Ban:** “paused pending facts” CEO reports with no named producer packet (unicorn ban — shared rules).

## head-ceo continuity consult

Not every quiet cycle. Not side-lane bucket spam. Distinct from **map-health cadence** (which runs on interval when enabled).

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

**Executive cadence:**

| Mode | `starvation_candidate_*` | Head `sweep_due` / `head_due_*` | Spacing |
| --- | --- | --- | --- |
| growth | Normal | When cadence enabled + interval elapsed | CTO×6 · CXO×12 · CEO×36 × L |
| standby | Suppressed | **Still allowed** (stewardship); `sweep_mode=stewardship` | CTO×18 · CXO×36 · CEO×72 × L |
| dormant | Suppressed | **Paused** (`sweep_paused`); assign-only | — |

`L` = `mind_loop.interval_sec` (default 300). Spacing shown is the posture default; override per head via `executive_cadence.every_n_loops`.

## Anti-patterns

- Polish/HK as continuity fuel  
- Filing wants/tasks with no map unit or operator intent  
- head-ceo continuity every quiet cycle on standby fleets  
- head-ceo **expansion** assigns while posture is standby/dormant  
- Treating `starvation_candidate` as mandatory act  
- Multi-fleet “fairness” busywork on quiet fleets  
- Pausing **all** Head sweeps on standby (stewardship Heads should still run when cadence is on)  
- Confusing dormant with steward trip or wound_up (related but distinct)

## Related

| Topic | Path |
| --- | --- |
| Starvation table | [`tasking.md`](tasking.md) |
| CEO loops | [`heads.md`](heads.md) |
| Wind-up | [`runtime-config.md`](runtime-config.md) |
| Multi-fleet mini-cycle | [`multi-fleet.md`](multi-fleet.md) |
| Cycle reports | [`mind-cycle.md`](mind-cycle.md) |
