# Fleet

**Mind / Head / Hand multi-agent fleet management** — the Abbot role pattern on a
dual-channel workspace (Vivi board + tmux panes).

Fleet lets one **Mind** session supervise many **Hands** (workers that drain a work
bag one target at a time) and **Heads** (advisors that review and consult), all coordinated
through a Vivi mail/task board for work truth and tmux panes for process truth. It is built
for multi-agent project loops: fail-fast 5–10 minute wakes, starve-and-refill tasking,
post-merge review, and honest "sleep when there's no real work" discipline. It is *not* a
second acceptance gate, a code reviewer on every packet, or a personal IMAP client.

See [`SKILL.md`](SKILL.md) for the full process — roles, modes, tasking, lifecycle, bans,
and anti-patterns. Everything below is a map into that file and its references.

## Start here

- [`SKILL.md`](SKILL.md) — the skill: roles, identity, modes, tasking, lifecycle, anti-patterns
- [`references/getting-started.md`](references/getting-started.md) — install, init, and attach your first fleet
- [`references/fleet-guide.md`](references/fleet-guide.md) — first-exposure vocabulary and shape

## Core process

- [`references/mind-cycle.md`](references/mind-cycle.md) — Mind modes, fail-fast wake, sensors, absorb vs accept, merge tasking
- [`references/tasking.md`](references/tasking.md) — filing targets, queue kinds (task/need/want/mail), multi-hand routing
- [`references/dual-channel.md`](references/dual-channel.md) — Vivi + tmux pane ops, wake/reinit, theme switch
- [`references/vivi.md`](references/vivi.md) — the Vivi board CLI (file, list, watch, mark done)

## Roles

- [`references/roles-and-harness.md`](references/roles-and-harness.md) — Mind/Hand/Head duties, arming, rebinding runtimes
- [`references/heads.md`](references/heads.md) — advisor loops (head-ceo / head-cto / head-cxo)
- [`references/heads/cast.md`](references/heads/cast.md) — Head cast and persona pointers
- [`references/operator-mail.md`](references/operator-mail.md) — the `operator@` human escalation channel
- [`references/dead-man.md`](references/dead-man.md) — the steward completed-cycle watchdog (opt-in, off by default)

## Topology

- [`references/multi-fleet.md`](references/multi-fleet.md) — one Mind supervising many fleets (session-attach model)
- [`references/multi-lane.md`](references/multi-lane.md) — side lanes, theme merge, base-update, pending merges
- [`references/ssh-remote.md`](references/ssh-remote.md) — Hands and Heads on remote hosts
- [`references/fleet-posture.md`](references/fleet-posture.md) — growth / standby / dormant: when to sleep vs continue
- [`references/multi-fleet-design.md`](references/multi-fleet-design.md) — design archive for the session-attach model

## Config and fallbacks

- [`references/runtime-config.md`](references/runtime-config.md) — `fleet.json` / baseline schemas, capacity recovery, wind-up/down
- [`references/companion-fallbacks.md`](references/companion-fallbacks.md) — behavior theses when companion skills are absent

## Scripts

| Script | Purpose |
| --- | --- |
| [`scripts/fleet-sensors.py`](scripts/fleet-sensors.py) | Read fleet state (panes, mail, git tips) for a wake |
| [`scripts/fleet-baseline.py`](scripts/fleet-baseline.py) | Read / bump Mind counters and silence state |
| [`scripts/fleet-doorbell.sh`](scripts/fleet-doorbell.sh) | Pointer-only Hand/Head wake via `tmux_target` |
| [`scripts/codex-reinit.sh`](scripts/codex-reinit.sh) | Recover a stuck Codex Hand pane |
| [`scripts/steward.sh`](scripts/steward.sh) | Arm / rearm / disarm the dead-man watchdog |
| [`scripts/suggest-polish-files.py`](scripts/suggest-polish-files.py) | Rank files for a bounded polish task after main moves |
| [`scripts/verify-fleet-json.py`](scripts/verify-fleet-json.py) | Validate a fleet's `fleet.json` |
| [`scripts/smoke-portability.sh`](scripts/smoke-portability.sh) | Env + helper portability checks |

Head personas live under [`references/heads/personas/`](references/heads/personas/).
