# Dead man / steward

Fleet-local **completed-cycle watchdog**. If Mind stops completing `FLEET_CYCLE` turns (loop timer dead, or every turn dies at hooks), something **outside the broken chat** holds the fleet and pages the human — not a second permanent Mind, not a global multi-repo service.

## Default: OFF (operator opt-in)

**Steward is disabled by default.** Arming a Mind loop / `FLEET_CYCLE` schedule does **not** arm steward.

| Require | Meaning |
| --- | --- |
| Vivi steward config → `enabled: true` | Operator chose this fleet may use dead-man |
| Operator says to arm steward **for that fleet** | Explicit turn on (not implied by attach/loop) |
| Then `steward.sh arm --project <root>` | Process + baseline armed |

Mind must **not** enable or arm steward proactively. Per-fleet only — enabling on mgs does not enable faber.

## Names

| Term | Meaning |
| --- | --- |
| **Dead man** | Arm / rearm / trip mechanism |
| **Steward** | tmux session + loop (`steward`) |
| **Mind** | Operator TUI only — sole product control plane when healthy |

**Steward is not Mind.** On trip: hold + notify. Does not own the map long-term or become dual merge authority.

## Problem

| Failure | Effect |
| --- | --- |
| Pi-owned Fleet loop dies | No more `FLEET_CYCLE` → fleet freezes |
| Hook / turn hard-abort | Loop fires but every turn dies before cycle end → **deadlock** |
| Mind session crash | No successful cycle ticks |

**Signal that matters:** end-of-**successful**-cycle tick — not process up / loop fired / turn started.

## Architecture

```text
Mind session (operator TUI) — may supervise one or more fleets
  │  every successful mini-cycle for fleet F:
  │     write F's last_successful_cycle_at + steward.sh rearm --project F
  │  on detach / stop-loop / wind-down: DISARM that fleet's steward same turn
  ▼
F/.vivi/mind-baseline.json   (+ optional F/.vivi/steward.rearm touch)
  ▲
  │  poll
tmux **target from the Vivi role record** (legacy steward:1.1 or mgs:steward.1)
  │  loop: sleep → check → trip?
  │
  on trip (this fleet only):
    baseline hold flag
    operator@ board mail
    optional external email page
    soft-hold idle Hands via their Vivi role `tmux_target` only
```

Steward is **not** a child of the Mind turn — Mind death does not kill it. Under **session-per-fleet**, steward is a **window** in the fleet session.

## Progress tick (Mind)

At **end** of every successful fail-fast cycle:

```text
mind_loop.last_successful_cycle_at = now
mind_loop.last_cycle = N
mind_loop.last_cycle_ok = true
# if steward armed for this fleet:
#   steward.last_rearm_at = now
#   touch $PROJECT/.vivi/steward.rearm
```

```bash
# only when steward is armed for this fleet:
scripts/steward.sh rearm --project <root>
```

**Do not** rearm only on turn start (masks hook death). Optional: rearm at **start and end** of long cycles so grace survives multi-minute acts. Skip all rearm when steward is disabled/unarmed.

## Arm / disarm

```bash
# only after operator enabled this fleet AND asked to arm:
steward.sh arm --project <root>
steward.sh disarm --project <root>  # required when stopping if it was armed
```

**Do not arm when:** loop-only / manual cycles; `steward.enabled` false or missing; operator silent on steward.

**Must disarm when (if armed):** operator stops `/loop` and will not run cycles; wind-down / `wound_up`; explicit “Mind: no schedule”; fleet intentionally idle for hours.

Leaving an **armed** steward without rearm → steward correctly assumes control-plane death and trips. Unarmed / disabled → no trip.

## Trip condition

```text
if steward.armed
   and mind_loop.state in (running, armed)   # not wound_up / disarmed
   and now - last_successful_cycle_at > grace_sec:
     TRIP once (dedupe)
```

Default `grace_sec`: `max(3 * interval_sec, 900)` (e.g. 5m cycle → 15m).

## Trip actions (hold protocol)

1. **Baseline:** `mind_loop.state = dead_man_tripped` (or keep `running` + `steward.tripped=true`); record `tripped_at`, last tick, note
2. **operator@:** one board item; subject `operator: problem — steward trip — <fleet>`
3. **External email** if `notify.external_email` + preauth
4. **Safe-stop:** do **not** kill `running` Hands; optional pointer to idle Hands with open bag: finish bag only, then idle; **no new map packages**
5. **Do not** merge, refill spine, or become permanent Mind
6. Stay armed-but-tripped until human/Mind **clear** + rearm or full disarm

### External email (Vivi)

```bash
vivi compose --account <account> --to <you@…> \
  --subject "[fleet steward] <fleet>: Mind ticks stopped — holding" \
  --body $'…' --html-body-auto
vivi exec send --account <account> path/to/draft.eml
```

**Policy exception (narrow):** `steward.notify.preauthorized_exec_send: true` for **this template only** — trip page to configured `to`. Not a general agent send license. Compose/exec: `companion-fallbacks.md` (Mail).

SMTP fail → still complete board + baseline; log error; do not block hold.  
**Dedupe:** ≤1 external page per `dedupe_hours` (default 6) per trip incident.

## Clear / recover

1. Read operator@ + baseline `steward` block  
2. Fix loop/hooks or start healthy Mind  
3. `steward.sh clear --project <root>`  
4. Successful cycle rearms; or `arm` if disarmed  
5. Resume product map  

## Fleet config

```json
"steward": {
  "enabled": true,
  "tmux_session": "steward",
  "tmux_window": "steward",
  "tmux_target": "steward:1.1",
  "grace_sec": 900,
  "poll_sec": 60,
  "mode": "hold",
  "script": null,
  "notify": {
    "operator_board": true,
    "external_email": true,
    "account": "personal-proton",
    "to": ["you@example.com"],
    "dedupe_hours": 6,
    "preauthorized_exec_send": true
  }
}
```

Session-per-fleet: `"tmux_session": "mgs", "tmux_window": "steward", "tmux_target": "mgs:steward.1"`.  
Soft-hold: script reads each hand’s `tmux_target` from its Vivi role record (never hardcode session==`hand-1`).

| Field | Notes |
| --- | --- |
| `mode` | `hold` (default) or `notify` (page only, no Hand pointers) |
| `grace_sec` | Missed successful-cycle threshold |
| `poll_sec` | Steward loop sleep |
| `notify.external_email` | Off unless configured |
| `preauthorized_exec_send` | Required true for steward `exec send` |

## Baseline fields

```text
mind_loop.last_successful_cycle_at
mind_loop.last_cycle_ok
mind_loop.interval_sec          # optional; default 300
steward:
  armed, armed_at, last_rearm_at
  tripped, tripped_at, last_trip_reason
  last_external_notify_at, last_external_error
  disarmed_at
```

## Script

```bash
scripts/steward.sh arm    --project <root>
scripts/steward.sh rearm  --project <root>
scripts/steward.sh disarm --project <root>
scripts/steward.sh status --project <root>
scripts/steward.sh check  --project <root>   # one-shot; may trip
scripts/steward.sh clear  --project <root>
```

Exit (`check` / trip path): `0` ok · `1` tripped this run · `2` config/error · `3` disarmed/inactive.

## Mind cycle integration

| Event | Mind action |
| --- | --- |
| Successful FLEET_CYCLE end | write `last_successful_cycle_at`; **`rearm` only if steward armed** |
| Long cycle start (optional) | early `rearm` only if steward armed |
| Stop loop / wind-down | `disarm` **same turn** if it was armed |
| Start loop alone | **do not** arm steward |
| Operator asks steward on **this** fleet | set `enabled: true` if needed, then `arm` |
| Steward missing while armed | recreate via `arm` |
| Engagement after silence | present operator@ (may include steward trip) |

## Anti-patterns

- Heartbeat only on turn start or loop inject  
- Steward as permanent second Mind / product bag owner  
- Global multi-fleet system scanning home for fleets  
- External email without fleet `to` + `preauthorized_exec_send`  
- Spamming external mail every poll after trip  
- Killing `running` Hands on trip  
- Leaving **armed** steward without `disarm` when stopping  
- Arming steward because a loop started (loop ≠ steward)  
- Enabling steward “for safety” without operator ask  
- Treating steward tmux as Mind process slot  

## Related

- [`operator-mail.md`](operator-mail.md) — human board inbox  
- [`mind-cycle.md`](mind-cycle.md) — modes, cycle end  
- [`runtime-config.md`](runtime-config.md) — wind-down disarm  
- External/board mail: `companion-fallbacks.md`  
