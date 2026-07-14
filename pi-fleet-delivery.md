# Delivery: Pi Fleet extension foundation

## Interpreted Unit

Implement the first usable Pi Fleet package slice from `pi-fleet.md`: a repo-owned
extension that explicitly attaches Fleet roots, renders read-only status, exposes
canonical observation tools, and owns an internal cycle timer without duplicating
`fleet-loop.py`.

## Normalized Spec

- Source: `pi/extensions/fleet.ts`
- Package manifest: repository-root `package.json` with Pi extension manifest
- Operator docs: `pi/README.md`
- Attachment: current-directory candidate plus explicit `/fleet attach` and
  `/fleet detach`; attachment state is persisted only in Pi custom session entries
  and validated against each fleet's baseline.
- Observation: invoke `fleet-sensors.py`, `fleet-loop.py status`,
  `fleet-baseline.py`, and `verify-fleet-json.py`; never reimplement Fleet policy.
- Controls: internal `status/start/update/stop`, minimum 60 seconds, no steward
  action, refusal when an external helper loop is active.
- Wake: `FLEET_CYCLE fleets=...` followed by a root map; single-flight and
  follow-up delivery while Pi is busy.

## Repo-Aware Baseline

- Fleet scripts are Python 3.9+/macOS/Linux and accept project/fleet scope.
- `fleet-sensors.py --json` returns `fleet_id`, posture, role groups, integration,
  runtime, fingerprint, and signals.
- `fleet-baseline.py bump --mind-session LABEL` is the canonical attachment
  transition; `--detach` clears the advisory Mind lock.
- `fleet-loop.py status` reports the existing tmux-backed scheduler.
- Pi extensions support custom tools, commands, widgets/status, session entries,
  session lifecycle cleanup, `pi.exec`, and `pi.sendUserMessage`.

## Stage Graph

1. Package and extension source with attachment/session reconstruction.
2. Read-only sensor refresh and Fleet widget/status.
3. Internal loop lifecycle, duplicate-loop refusal, and FLEET_CYCLE wake.
4. Structured read-only tools and validation documentation.

## Implementation Work

One implementation workstream: `pi/extensions/fleet.ts`, `package.json`, and
`pi/README.md`. The Fleet scripts are integration dependencies and are not changed
in this phase.

## Checkpoints And Gates

- No publication or version release in this phase; release is deferred.
- Do not mutate a fleet except through explicit attach/detach commands.
- Do not start an internal loop if any attached root reports an active external
  `fleet-loop.py` process.
- Do not add steward, posture, doorbell, reinit, task-routing, or assignment
  mutations.

## Validation

- TypeScript/module load check with Pi's local extension loader.
- Direct Fleet helper smoke checks against a valid fleet fixture.
- Existing Fleet Python test suite and portability smoke.
- Manual candidate → attach → list → sensor tools → loop status/start/update/stop
  → detach flow; verify custom session entries restore on reload.

## Companion Skill Plan

- `fleet`: canonical helper and policy semantics.
- `correctness`: timer cleanup, attachment ownership, and duplicate-loop review.
- `housekeeping`: package/repository hygiene after implementation.
- `polish`: final pass over extension and package documentation.

## Open Questions

Deferred to a later phase: package root versus separate package repository,
mutation tool confirmation UX, per-fleet cadence, richer panel schema, and whether
candidate detection should be hidden by default. This phase uses the Fleet root
package manifest and shows a quiet candidate widget when present.
