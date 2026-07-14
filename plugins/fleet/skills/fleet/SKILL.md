---
name: fleet
description: Operate the canonical Mind/Head/Hand Fleet system from Codex using Fleet MCP tools and compact dashboard output.
---

# Codex Fleet adapter

The canonical Fleet policy is the repository-level `SKILL.md` in the Fleet
source tree. This plugin is an adapter for Codex: it exposes the existing
Fleet scripts through MCP and adds a Codex-friendly dashboard result. It must
not create a second Fleet control plane.

## Operating rules

- Attach explicitly before acting as Mind. A monitor is read-only.
- Treat `fleet_preflight` and `fleet_dashboard` as observation; they do not
  wake roles, file work, or change Fleet state.
- Route mutations through the MCP tools, which call the canonical scripts.
  Do not edit `.vivi/fleet.json`, `mind-baseline.json`, or runtime state by
  hand.
- A sensor signal needs a disposition: acted, delegated, escalated,
  deferred-valid, or sleep-valid.
- Preserve the Fleet invariants around Mind ownership, operator escalation,
  posture, runtime truth, and cycle continuity from the canonical Fleet skill.
- Never treat a dashboard as Fleet truth. Refresh sensors before consequential
  operations.

## Tool routing

- `fleet_attach` / `fleet_detach`: claim or release Mind ownership, or create
  a read-only monitor attachment.
- `fleet_preflight`: collect validation, baseline, sensors, posture, runtime,
  loop, and recommendations.
- `fleet_sensors`, `fleet_board`, `fleet_runtime`: inspect one operational
  surface without inventing state.
- `fleet_dashboard`: render the compact Codex conversation dashboard from the
  latest canonical observations. This is the supported UI fallback for the
  Pi widget; it is not a persistent Codex shell panel.
- `fleet_loop`, `fleet_posture`, `fleet_runtime_action`, and
  `fleet_cycle_close`: perform the corresponding canonical operations when
  the user has authorized them and the required target or summary is explicit.

Always pass the Fleet project root. If the user has not identified one, inspect
the current workspace for `.vivi/fleet.json` before asking for a path.

## UI boundary

The plugin can provide structured dashboard output inside a Codex task. It
cannot register a native desktop widget, status chip, slash command, or host
lifecycle listener. Keep the dashboard data model provider-neutral so an Apps
SDK UI can be added later without changing Fleet operations.
