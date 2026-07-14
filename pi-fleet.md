# Goal: Shareable Pi Fleet Mind Extension

## Summary

Build a shareable Pi extension package in the Fleet repository that gives a Pi Mind session an explicit, cohesive view and control surface for Fleet operations. The extension should attach only to fleet roots explicitly selected by the operator, expose canonical Fleet/Vivi/runtime observations, provide grouped helper tools, and replace the tmux-injected `fleet-loop.py` path with a session-owned internal loop when Pi is acting as Mind. It must preserve Pi's native footer metadata and remain a presentation/control extension rather than a second Fleet control plane.

## Problem

- Fleet supervision currently spans Vivi work truth, tmux/runtime process truth, helper scripts, scheduled cycles, and operator mail. That information is available, but not cohesively exposed inside Pi.
- There is no global manifest that records every fleet attached to a Mind. Attachment must therefore be explicit and session-scoped rather than inferred from a nonexistent global registry.
- `fleet-loop.py` is a useful fallback scheduler, but its tmux text injection is awkward when Pi itself is the active Mind harness.
- The Mind needs a safe way to start, inspect, adjust, and stop its Fleet cycle, and to receive timely notifications when Vivi/runtime signals change.
- The current Pi TUI work must not lose useful native metadata such as token/cache/cost/context/provider/model information.

## Goals

- Add a repo-owned Pi extension source under the Fleet repository.
- Package the extension so it can be loaded locally and shared/imported as a Pi package.
- Detect a candidate fleet only from the current working directory when `<cwd>/.vivi/fleet.json` exists; do not scan home directories or invent a global attachment manifest.
- Support explicit session-scoped attachment and detachment of one or more fleet roots.
- Support a separate Pi-local read-only monitor attachment that may observe fleets owned by other Mind sessions without claiming or overwriting ownership.
- Aggregate cycle summaries and current sensor state from multiple monitored fleets in the human panel.
- Validate fleet identity and runtime bindings through the canonical Fleet configuration/helpers.
- Expose an in-TUI Fleet panel showing attached fleets, posture, role/runtime status, task/need/mail signals, pending integration indicators, active loop state, and important sensor obligations.
- Preserve Pi's native footer and working indicator; add compact Fleet status through additive extension status/widget surfaces.
- Add explicit model-callable `fleet_attach`/`fleet_detach` operations for Mind or monitor mode, with takeover confirmation and monitor read-only isolation.
- Add read-only `fleet_preflight` and `fleet_prepare` operations for Fleet-specific operational orientation and launch assessment.
- Add grouped, structured tools for canonical Fleet sensors, board state, runtime state, and loop lifecycle.
- Provide an internal Pi-owned Fleet loop with `status`, `start`, `update`, and `stop` operations.
- Poll canonical Fleet sensors and wake the Mind with valid `FLEET_CYCLE` user messages when scheduled or material signals require attention.
- Avoid interrupting active work; queue cycle notifications as follow-ups when Pi is busy and prevent duplicate queued cycles.
- Keep mutation operations such as doorbells, runtime reinitialization, posture changes, task filing, and steward control explicitly gated and separate from read-only observation.
- Preserve the existing Fleet skill, references, scripts, and operational vocabulary as the source of truth rather than duplicating Fleet policy inside the extension.

## Non-goals

- Do not patch Pi core or replace Pi's built-in assistant-message/thinking renderer.
- Do not replace Pi's native footer with a reduced custom footer.
- Do not create a global manifest claiming which fleets a Mind is attached to.
- Do not auto-attach or take over a fleet merely because a `fleet.json` file is detected.
- Do not scan arbitrary home-directory paths for fleets.
- Do not treat monitor attachment as Mind attachment; monitors must never claim `mind_session`.
- Do not let monitor mode write `fleet.json`, `mind-baseline.json`, watch cursors, sensor history, or other Fleet state.
- Do not infer Fleet work truth from tmux pane text; use Vivi and canonical sensor output.
- Do not create duplicate loops when an external `fleet-loop.py` loop already exists.
- Do not automatically arm or rearm a steward.
- Do not make the extension a replacement Mind that performs signal dispositions, task routing, merge acceptance, or baseline policy independently of the Fleet process.
- Do not add wake/reinit/task-filing mutation actions to the first read-only panel milestone.
- Do not alter the existing compact Pi tool-row presentation as part of this Fleet extension goal except where an explicit integration need is discovered.
- Do not publish a package or change Fleet release/version policy without explicit authorization.

## Ground Truth Researched

- `/Users/ianzepp/work/ianzepp/fleet/SKILL.md`: Fleet identity, Mind/Head/Hand roles, explicit dual-channel truth, attachment/baseline rules, FLEET_CYCLE format, adaptive cadence, steward boundaries, signal dispositions, and multi-fleet invariants.
- `/Users/ianzepp/work/ianzepp/fleet/references/vivi.md`: canonical Vivi commands and scopes for board status, tasks, needs, mail, watch cursors, and role routing.
- `/Users/ianzepp/work/ianzepp/fleet/references/mind-cycle.md`: fail-fast sensor order, cycle modes, FLEET_CYCLE requirements, signal disposition gate, follow-up behavior, and cadence constraints.
- `/Users/ianzepp/work/ianzepp/fleet/references/multi-fleet.md`: attached-set semantics, no global index, session-scoped cross-fleet state, per-fleet baselines, and explicit `fleet.json` runtime bindings.
- `/Users/ianzepp/work/ianzepp/fleet/scripts/fleet-sensors.py`: canonical combined sensor surface for board/runtime/fleet signals; extension should invoke rather than reimplement it.
- `/Users/ianzepp/work/ianzepp/fleet/scripts/fleet-loop.py`: existing tmux-backed fallback loop and duplicate-loop state/stop behavior that the internal loop must not silently conflict with.
- `/Users/ianzepp/work/ianzepp/fleet/scripts/fleet-baseline.py`: canonical attach/detach/baseline transitions and advisory Mind-session lock.
- `/Users/ianzepp/work/ianzepp/fleet/scripts/fleet-resolve.py`: canonical project/fleet/role-to-runtime resolution boundary.
- `/Users/ianzepp/.nvm/versions/node/v24.15.0/lib/node_modules/@earendil-works/pi-coding-agent/docs/extensions.md`: `registerTool`, tool interception/results, session lifecycle, `setWidget`, `setStatus`, `ctx.ui.custom`, `pi.exec`, `pi.sendMessage`, and `pi.sendUserMessage` behavior.
- `/Users/ianzepp/.nvm/versions/node/v24.15.0/lib/node_modules/@earendil-works/pi-coding-agent/docs/packages.md`: Pi package manifests, local/git installation, conventional directories, peer dependencies, and package security requirements.
- `/Users/ianzepp/.nvm/versions/node/v24.15.0/lib/node_modules/@earendil-works/pi-coding-agent/dist/modes/interactive/components/footer.js.map`: native footer information set, including cwd/branch/session, token/cache/cost/context statistics, provider/model/thinking level, and extension statuses.
- `/Users/ianzepp/.nvm/versions/node/v24.15.0/lib/node_modules/@earendil-works/pi-coding-agent/dist/modes/interactive/interactive-mode.js`: native tool expansion defaults and TUI lifecycle seams; confirms that extension-level tool presentation is separate from core layout.
- `/Users/ianzepp/work/pi-agent-tui-design-handoff.md`: status/widget/watchers visual language, compact metadata, contextual chrome, and grayscale-first design constraints.
- User clarification in this session: explicit fleet attachment is preferred; current working directory detection is useful; no Pi source patching; Pi's useful metadata must remain visible; shared extension source should live with Fleet.

## Reference Packet

Before editing:

- `SKILL.md` and `references/mind-cycle.md`: preserve Mind duties, FLEET_CYCLE syntax, signal disposition, and cadence semantics.
- `references/multi-fleet.md`: implement attached-set state without a global manifest or cross-fleet control-plane invention.
- `references/vivi.md`: use correct project/identity flags and avoid personal IMAP commands.
- `scripts/fleet-sensors.py`, `scripts/fleet-baseline.py`, and `scripts/fleet-resolve.py`: canonical observation, attachment, and runtime-resolution seams.
- `scripts/fleet-loop.py`: detect/avoid duplicate external loop state and preserve fallback compatibility.
- Pi `docs/extensions.md`: verify extension API and session cleanup behavior before implementation.
- Pi `docs/packages.md`: verify package layout, manifest, install, and dependency behavior before packaging.
- `pi-agent-tui-design-handoff.md`: use the status/widget/panel design language without assuming pinned top chrome is available.
- `python3 scripts/fleet-sensors.py --project <root> --json`: integration fixture for observed sensor shape.
- `python3 scripts/fleet-baseline.py get -p <root>`: attachment/baseline evidence before attach/detach behavior is implemented.
- `python3 scripts/verify-fleet-json.py --project <root>`: fleet configuration validation where applicable.

## Constraints And Invariants

- **Explicit attachment:** an attached fleet is in the current Pi Mind session only after an operator-directed attach operation. A detected `.vivi/fleet.json` is merely a candidate until attached.
- **Monitor isolation:** a monitor registration is Pi-local session state only. It reads canonical config, baseline, and sensors with watch persistence disabled; it never emits `FLEET_CYCLE`, wakes a Mind, or performs a Fleet mutation.
- **Canonical identity:** use fleet project root plus `fleet_id` from `fleet.json`; never substitute a tmux session name or runtime target for fleet identity.
- **Dual-channel truth:** Vivi is work truth; configured tmux/Vivi-PTY runtime observations are process truth. The panel must show both without conflating them.
- **No global manifest:** do not create a global list of Mind-attached fleets. Rebuild each attached fleet from explicit session attachment plus its own baseline/configuration.
- **No duplicate loops:** internal and external loop state must be checked before start/update. Replacement must be atomic enough to leave at most one active scheduler for the attached set.
- **Loop cadence:** normal supervision must not shorten below the Fleet guidance minimum; default around five minutes and adapt only according to observed work density and stop conditions.
- **Single-flight wake:** one pending/running Fleet cycle per attached set. Polling and scheduled ticks must coalesce rather than stack follow-ups.
- **No interruption:** a running agent turn is not interrupted for routine Fleet polling; use a follow-up delivery path unless an explicitly approved urgent policy is added later.
- **Correct injection:** scheduled Mind wakes begin with the required `FLEET_CYCLE fleets=...` line and place root mappings in the body.
- **Disposition ownership:** the extension observes and wakes; Mind remains responsible for classifying signals as acted, delegated, escalated, deferred-valid, or sleep-valid.
- **Steward separation:** loop lifecycle is not steward lifecycle. The extension must not arm/rearm/disarm steward implicitly.
- **Session cleanup:** timers, child processes, file watchers, and pending polling resources start only after `session_start` and are closed idempotently on `session_shutdown`.
- **Native Pi context:** the extension must preserve Pi's native footer metadata and native working indicator; additive status/widget use is preferred over replacement.
- **Tool safety:** extension tools use fixed helper invocations and validated arguments, not arbitrary shell command strings supplied by the model.
- **Mutation gates:** doorbell, reinit, posture, assignment, baseline mutation, and steward actions require explicit policy/confirmation and are not part of the initial read-only panel milestone.
- **Package security:** extension code has full system access and must be reviewed before installation; package refs should be pinned for shared use.
- **Compatibility:** `fleet-loop.py` remains available for non-Pi Mind harnesses and as an explicit fallback; the Pi extension must not silently remove or alter it.

## Supporting Skills

- `fleet`: primary source of operational rules, helpers, identity, sensors, loops, and attachment semantics.
- `vivi`: use when implementing or validating board/mailspace command integration.
- `deploy`: use only if operating remote fleet hosts or runtime targets becomes part of a later slice.
- `docs`: use for package/extension README and operator documentation.
- `correctness`: review single-flight scheduling, attach/detach, timer cleanup, duplicate-loop prevention, and signal delivery.
- `security` / authorized security review: review shell argument handling, package installation trust, runtime mutation gates, and sensitive board/pane data exposure before enabling mutation tools.
- `housekeeping`: validate package/repo hygiene at a major inflection, not every small implementation step.

## Implementation Shape

- **Phase 1 — package and attachment foundation:** add a repo-owned Pi package/extension layout; support explicit `/fleet attach`, `/fleet detach`, `/fleet list`, and current-directory candidate detection; validate `fleet.json`; use canonical baseline attach/detach helpers; keep attachment state session-scoped.
- **Phase 2 — read-only sensors and panel:** invoke `fleet-sensors.py --json` for each attached fleet; normalize snapshots; render a compact Fleet widget and additive native-footer status; expose `/fleet refresh` and a detail overlay; show signal obligations without performing dispositions.
- **Phase 2b — monitor mode:** add `/fleet attach --monitor`, `/fleet monitor start/update/status/stop`, session-local monitor entries, baseline cycle-change detection, and aggregated human summaries. Use `fleet-sensors.py --no-watch`; do not claim Mind ownership or wake any LLM.
- **Phase 3 — internal loop:** implement `fleet_loop` status/start/update/stop; persist only the minimum loop state required by the live extension/session; enforce single-flight, cadence bounds, cleanup, and external-loop duplicate detection; generate valid FLEET_CYCLE payloads.
- **Phase 4 — proactive polling and Mind wake:** poll bounded sensor/watch surfaces; detect meaningful changes; coalesce notifications; wake the Mind with `pi.sendUserMessage` using follow-up delivery when busy; keep canonical sensor/baseline work in the Mind cycle.
- **Phase 5 — grouped read-only helper tools:** add model-callable `fleet_sensors`, `fleet_board`, and `fleet_runtime` tools with concise model-facing content and structured UI details; render compact tool output consistent with the current Pi Fleet visual pass.
- **Phase 6 — guarded mutations:** only after the read-only path is stable, add explicit confirmation-backed doorbell, runtime reinit, posture, task-routing, and other helper wrappers; validate exact Fleet bindings and report evidence.
- **Later:** package release/pinning, richer multi-fleet detail views, adaptive UI summaries, and optional action keybindings. Do not expand into a second Mind implementation.

## Release Posture

Decision: **defer release**.

- Local development should load the extension with `pi -e` or a local path first.
- A root `package.json` Pi manifest or an intentionally scoped package layout may be added only after the extension boundary is validated.
- Before sharing from git, pin a commit/tag, review full-system-access behavior, document required `vivi`/Python/Fleet prerequisites, and run package-install smoke tests.
- No npm publication, git tag, or package release is authorized by this goal alone.

## Exit Strategy

Decision: **included**.

- Disable/remove the Pi package or extension without modifying Fleet scripts or Fleet state.
- Stop the internal loop through `fleet_loop stop` or session shutdown.
- Detach each explicitly attached fleet through the canonical baseline helper.
- Preserve `fleet-loop.py` as the fallback for other harnesses.
- If polling or wake behavior becomes noisy, disable the poller while retaining read-only status tools/panel.
- If duplicate-loop detection is uncertain, fail closed and refuse to start rather than creating another scheduler.

## Acceptance Criteria

- A local Pi process can load the extension from the Fleet repository without modifying Pi core.
- The current working directory with `.vivi/fleet.json` is detected as a candidate but is not silently attached.
- An operator can explicitly attach and detach one or more valid fleet roots; invalid roots and foreign Mind attachments fail safely with actionable feedback.
- `/fleet list` and the panel show only the current session's explicitly attached fleets.
- Sensor snapshots come from canonical Fleet helpers and visibly distinguish Vivi/work signals from runtime/process signals.
- The panel and footer status add Fleet information without removing Pi's native token/cache/cost/context/provider/model metadata.
- `fleet_loop status/start/update/stop` works for the attached set, enforces cadence bounds, cleans up on session shutdown, and does not create duplicates alongside an active external loop.
- Generated cycle prompts use the correct `FLEET_CYCLE fleets=...` first line and root map body.
- Sensor polling coalesces events, does not stack duplicate follow-ups, and does not interrupt an active agent turn for routine work.
- Read-only helper tools return concise model-facing summaries, preserve structured details for UI rendering, and use validated canonical helper arguments.
- Mutation tools are absent or explicitly gated in the first milestone; no wake/reinit/steward/task-routing side effect occurs from read-only observation.
- The package can be loaded locally and, after packaging is authorized, installed from the Fleet repository using Pi's package mechanism.
- A monitor can observe a fleet whose baseline is owned by another Mind without changing any Fleet file or emitting a cycle prompt.
- Multiple monitors aggregate independently advancing cycle summaries in the human panel.
- The LLM can explicitly attach/detach Mind or monitor state through confirmation-aware tools.
- `fleet_preflight` and `fleet_prepare` return launch-relevant Fleet evidence without starting runtimes, waking agents, filing work, or changing posture.
- The existing Fleet skill/scripts continue to pass their relevant tests and smoke checks.

## Validation

- `python3 scripts/verify-fleet-json.py --project <root>` should validate each attached fleet configuration.
- `python3 scripts/fleet-sensors.py --project <root> --json` should produce parseable input for the panel/snapshot adapter.
- `python3 scripts/fleet-baseline.py get -p <root>` before and after attach/detach should show only the intended canonical transition.
- `python3 scripts/fleet-loop.py --project <root> status` should be checked before internal loop start; an active external loop must cause safe refusal or explicit replacement handling.
- `python3 scripts/smoke-portability.sh` and relevant Fleet tests should remain green.
- `pi -e /path/to/fleet/pi/extensions/fleet.ts --no-session` should start without extension load errors.
- Manual flow: detect current candidate → explicitly attach → view panel → start loop → inspect status → update cadence → stop loop → reload/new session → confirm timers and duplicate state are cleaned up.
- Manual flow: attach two explicit roots → verify one FLEET_CYCLE payload names both slugs and contains roots in the body → detach one → verify subsequent cycles cover only the remaining fleet.
- Manual flow: generate new Vivi/runtime sensor signal while Pi is idle and while Pi is streaming; verify one coalesced follow-up wake and no mid-turn interruption.
- Review check: inspect all subprocess arguments, output truncation, timer cleanup, failure paths, and native footer preservation before enabling any mutation action.
- Package check: install from a pinned local/git source in a clean Pi config directory, review loaded resources, and remove the package cleanly.

## Open Questions

- Should the first milestone support only `/fleet` commands and the panel, or should the model-callable `fleet_loop` tool be included immediately?
- Should current-directory candidate detection be visible only after `/fleet` is invoked, or should it appear quietly in the panel/status on session start?
- When a baseline reports a foreign live Mind attachment, should the extension offer only refusal, or a separately confirmed takeover path?
- Should polling run on every attached fleet at one shared cadence, or allow per-fleet cadence while still coalescing one Mind cycle?
- What sensor fields are stable enough to become the initial panel schema versus remaining an expandable raw-signal detail view?
- Should the root package manifest live at the Fleet repository root, or should the Pi package be a separately installable subproject/repository to avoid adding Node packaging metadata to the Fleet Python/shell repository?
- Which `vivi`/Python/runtime prerequisites should be checked at extension startup versus reported only when a command/tool is invoked?

## Stop Conditions

- Stop before implementation if the canonical Fleet helper or sensor schema changes materially and this goal has not been re-grounded.
- Stop if explicit attachment would require inventing a global manifest or silently taking over a foreign Mind session.
- Stop if internal loop behavior would create duplicate scheduling with `fleet-loop.py` or stack unbounded queued prompts.
- Stop if the extension would need to reimplement Mind dispositions, baseline policy, or steward semantics rather than invoking canonical helpers.
- Stop before adding mutation tools if confirmation, runtime-target resolution, or rollback behavior is not explicit and testable.
- Stop if preserving Pi's native footer/context requires replacing it with an incomplete custom implementation.
- Stop before package publication if dependency loading, full-system-access review, pinned references, or clean uninstall behavior is not validated.
- Stop and ask the operator if a design choice would change Fleet ownership, attachment authority, steward policy, or external side effects.
