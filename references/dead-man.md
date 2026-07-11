# Dead man / steward

Fleet-local **completed-cycle watchdog**. Goal: if Mind stops completing
`FLEET_CYCLE` turns (loop timer dead, or every turn dies at hooks), something
**outside the broken chat** brings the fleet to a **safe hold** and pages the
human — not a second permanent Mind, not a global multi-repo service.

## Names

| Term | Meaning |
| --- | --- |
| **Dead man** | The arm / rearm / trip mechanism |
| **Steward** | tmux session + loop that implements it (`steward`) |
| **Mind** | Operator TUI only — still the only product control plane when healthy |

**Steward is not Mind.** On trip it holds and notifies; it does not own the map
long-term or become a dual merge authority.

## Problem (why this exists)

| Failure | What happens |
| --- | --- |
| Grok `/loop` timer dies | No more `FLEET_CYCLE` injections → fleet freezes |
| Hook / turn hard-abort | Loop may still fire, but every turn dies before cycle end → **deadlock** |
| Mind session crash | Same: no successful cycle ticks |

**Signal that matters:** end-of-**successful**-cycle tick — not “process up”, not
“loop fired”, not “turn started”.

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
tmux **target from fleet.json** (legacy steward:1.1 or mgs:steward.1)
  │  loop: sleep → check → trip?
  │
  on trip (this fleet only):
    baseline hold flag
    operator@ board mail
    optional external email page
    soft-hold idle Hands via fleet.json hand tmux_targets only
```

Steward is **not** a child of the Mind turn — Mind death does not kill it.  
Under **session-per-fleet**, steward is a **window** in the fleet session.

## Progress tick (Mind)

At the **end** of every successful fail-fast cycle (acted or quiet sleep that
finished sensors/ops):

```text
mind_loop.last_successful_cycle_at = now
mind_loop.last_cycle = N
mind_loop.last_cycle_ok = true
steward.last_rearm_at = now
# optional: touch $PROJECT/.vivi/steward.rearm
```

Also run:

```bash
scripts/steward.sh rearm --project <root>
```

**Do not** rearm only on turn start (masks hook death). Optional: rearm at
**start and end** of long cycles so grace is not burned during multi-minute acts.

## Arm / disarm

### Arm (fleet running with scheduled Mind)

When `mind_loop.state → running` and a durable loop is armed:

```bash
steward.sh arm --project <root>
```

Creates/attaches tmux `steward`, starts the poll loop, sets
`steward.armed = true` in baseline.

### Disarm (required — avoid false fire)

Mind **must** disarm when:

- Operator stops `/loop` and will not run cycles
- Wind-down / `mind_loop.state → wound_up`
- Explicit “Mind: no schedule”
- Fleet intentionally idle for hours

```bash
steward.sh disarm --project <root>
```

If Mind leaves loop mode without disarm, steward will correctly assume control
plane death and trip.

## Trip condition

```text
if steward.armed
   and mind_loop.state in (running, armed)   # not wound_up / disarmed
   and now - last_successful_cycle_at > grace_sec:
     TRIP once (dedupe)
```

Default `grace_sec`: `max(3 * interval_sec, 900)` (e.g. 5m cycle → 15m).

## Trip actions (hold protocol)

1. **Baseline:** `mind_loop.state = dead_man_tripped` (or keep `running` +
   `steward.tripped = true`); record `steward.tripped_at`, last tick, note
2. **operator@:** one board item (need or mail), subject prefix
   `operator: problem — steward trip — <fleet>`
3. **External email** (if fleet `notify.external_email` + preauth): short page
4. **Safe-stop:** do **not** kill `running` Hands; optional pointer to
   idle Hands with open bag: finish open bag only, then idle; **no new map packages**
5. **Do not** merge, refill spine, or become permanent Mind
6. Stay armed-but-tripped until human/Mind **clear** + rearm or full disarm

### External email (Vivi)

Project mailspace is local-only. Off-box page uses IMAP/SMTP account:

```bash
vivi compose --account <account> --to <you@…> \
  --subject "[fleet steward] <fleet>: Mind ticks stopped — holding" \
  --body $'…' --html-body-auto
vivi exec send --account <account> path/to/draft.eml
```

**Policy exception (narrow):** fleet may set
`steward.notify.preauthorized_exec_send: true` for **this template only** —
trip page to configured `to` addresses. Not a general agent send license.
Compose/exec: `companion-fallbacks.md` (Mail section).

If SMTP fails: still complete board + baseline; log error; do not block hold.

**Dedupe:** at most one external page per `dedupe_hours` (default 6) per trip
incident.

## Clear / recover

Operator or new Mind session:

1. Read operator@ + baseline `steward` block  
2. Fix loop/hooks or start healthy Mind  
3. `steward.sh clear --project <root>` (clear trip flag)  
4. Successful cycle rearms; or `arm` again if disarmed  
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

Session-per-fleet example: `"tmux_session": "mgs", "tmux_window": "steward", "tmux_target": "mgs:steward.1"`.  
Soft-hold Hands: script reads each hand’s `tmux_target` from fleet.json (never hardcodes session==`hand-1`).

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
  armed                         # bool
  armed_at
  last_rearm_at
  tripped                       # bool
  tripped_at
  last_trip_reason
  last_external_notify_at
  last_external_error
  disarmed_at
```

## Script

```bash
# from fleet, or PROJECT=…
scripts/steward.sh arm    --project <root>
scripts/steward.sh rearm  --project <root>
scripts/steward.sh disarm --project <root>
scripts/steward.sh status --project <root>
scripts/steward.sh check  --project <root>   # one-shot; may trip
scripts/steward.sh clear  --project <root>   # clear trip after recovery
```

Exit codes (`check` / loop trip path): `0` ok · `1` tripped this run · `2` config/error · `3` disarmed/inactive.

## Mind cycle integration

| Event | Mind action |
| --- | --- |
| Successful FLEET_CYCLE end | `rearm` + write `last_successful_cycle_at` |
| Long cycle start (optional) | early `rearm` so grace survives multi-minute work |
| Stop loop / wind-down | `disarm` **same turn** |
| Arm fleet / start loop | `arm` if `steward.enabled` |
| Steward session missing while armed | recreate via `arm` (health-check) |
| Engagement after silence | present operator@ (may include steward trip) |

## Anti-patterns

- Heartbeat only on turn start or loop inject  
- Steward as permanent second Mind / product bag owner  
- Global multi-fleet system service scanning home directories for fleets  
- External email without fleet `to` + `preauthorized_exec_send`  
- Spamming external mail every poll after trip  
- Killing `running` Hands on trip  
- Leaving loop mode without `disarm`  
- Treating steward tmux as Mind process slot for operator chat  

## Related

- [`operator-mail.md`](operator-mail.md) — human board inbox  
- [`mind-cycle.md`](mind-cycle.md) — modes, cycle end  
- [`runtime-config.md`](runtime-config.md) — wind-down disarm  
- External/board mail: `companion-fallbacks.md`  
