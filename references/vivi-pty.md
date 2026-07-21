# vivi-pty execution runtime

Project-scoped PTY session manager as a fleet execution backend. Uses structured
PTY diagnostics instead of tmux pane scraping for runtime state classification.
Use when the harness needs PTY sessions without tmux, or when the operator prefers
structured session lifecycle over raw pane management. For the default sub-agent
path, see [`subagent.md`](subagent.md).

## When to use vivi-pty

| Situation | Use vivi-pty |
| --- | --- |
| Harness lacks sub-agent spawning but needs structured sessions | Yes |
| PTY sessions without tmux dependency | Yes |
| Need structured session lifecycle (start/stop/inspect/remove) | Yes |
| Default fleet execution | No — prefer sub-agent |
| Need to watch work live | No — prefer tmux |

## Session lifecycle

vivi-pty manages sessions through a daemon (`vivi-ptyd`) with a JSON-RPC protocol.

```bash
# Daemon info
vivi-pty --project <root> info

# Session lifecycle
vivi-pty --project <root> session list
vivi-pty --project <root> session start <session-id> -- <command...>
vivi-pty --project <root> session inspect <session-id>
vivi-pty --project <root> session restart <session-id>
vivi-pty --project <root> session stop <session-id>
vivi-pty --project <root> session remove <session-id>
```

`remove` stops the session and drops the ID (no tombstone), allowing a new start
to rebind command/cwd for the same session_id.

## Terminal operations

Write to and inspect PTY sessions:

```bash
# Write text (literal)
vivi-pty --project <root> terminal write <session-id> "<text>"

# Write text + Enter
vivi-pty --project <root> terminal write <session-id> "<text>" --enter

# Snapshot current screen state
vivi-pty --project <root> terminal snapshot <session-id>

# Send special keys
vivi-pty --project <root> terminal key <session-id> <key>

# Resize
vivi-pty --project <root> terminal resize <session-id> <cols> <rows>
```

## Session configuration

Sessions are configured in fleet.json under each Hand/Head role. Capacity
(provider/model/thinking) lives on the Vivi role record; fleet.json holds
operational bindings only:

```json
{
  "hands": {
    "hand-1": {
      "mail_identity": "hand-1",
      "cwd": "/path/to/project",
      "vivi_pty_session": "fleet-hand-1-a"
    }
  }
}
```

```bash
vivi role set hand-1 --project <root> \
  --harness vivi_pty \
  --provider deepseek --model deepseek-v4-pro --thinking low
```

The PTY session ID convention is `fleet-<role>-<suffix>` (e.g. `faber-hand-1d`).
Session IDs are stable across restarts as long as the role binding does not change.

## Daemon management

The daemon listens on a Unix socket under the project `.vivi/` directory. If the
daemon becomes unresponsive or the protocol version is too old:

```bash
# Find the daemon PID
pgrep -f vivi-ptyd

# Kill stale daemon
kill <pid>

# Remove stale socket if present
rm <project>/.vivi/vivi-pty.sock

# Start fresh daemon (happens automatically on first session op)
vivi-pty --project <root> session list
```

Protocol version mismatches manifest as `method not found (-32601)` errors on
session operations. The fix is always: kill old daemon, remove stale socket,
let the first operation spawn a fresh one.

## Runtime state classification

vivi-pty uses structured diagnostics instead of pane scraping. Canonical states:

```text
starting | waiting_for_input | submitting | running | approval_required |
completed | failed | stopped | unknown
```

No backend-specific state aliases appear in sensor rows. `runtime_states` is the
role→state summary persisted in the baseline.

### Doorbell fail-closed

vivi-pty doorbell uses harness diagnostics, not text classification. It still
refuses non-input harness states. A `waiting_for_input` or `completed` session
with open tasking gets a pointer; other states are refused.

## fleet-runtime.py integration

`fleet-runtime.py` is backend-neutral and dispatches to vivi-pty when the role
binding uses PTY:

```bash
python3 scripts/fleet-runtime.py --project <root> --role hand-1 status
python3 scripts/fleet-runtime.py --project <root> --role hand-1 start
python3 scripts/fleet-runtime.py --project <root> --role hand-1 restart --boot 'HAND WAKE hand-1. Role hand-1. Task <handle>. Load charter and task from Vivi.'
python3 scripts/fleet-runtime.py --project <root> --role hand-1 stop
```

For Vivi-PTY roles:
- `start` creates the configured session if absent or stopped
- `restart` stops then starts through the PTY backend; optional `--boot` pointer
- Stopped tombstones are restarted through `vivi-pty session restart`
- New sessions use the configured command array without shell evaluation

## Wake pattern

Doorbell through vivi-pty delivers the thin boot pointer per [SKILL.md § Role communication contract](../SKILL.md#role-communication-contract). The role loads charter and task from Vivi; the PTY write is a thin pointer, not policy.

```bash
vivi-pty --project <root> terminal write faber-hand-1d \
  "HAND WAKE hand-1. Role hand-1. Task <handle>. Load charter and task from Vivi. Report via vivi task done + vivi mail send." \
  --enter
```

Or via the backend-neutral helper:

```bash
scripts/fleet-doorbell.sh --project <root> --fleet <fleet-id> --role hand-1 --handle <hex>
```

The helper resolves the runtime backend (tmux vs vivi-pty) from fleet.json and
dispatches accordingly. Same channel split rules apply: thin boot pointer only
in the PTY write — identity, role, task handle, one verb. Full instructions,
persona, and scope belong in Vivi (charter, task body, mail).

## assignment_mode

Same semantics as tmux ([`tmux.md`](tmux.md) § assignment_mode). The doorbell
helper applies the configured mode before the pointer. For vivi-pty:

| Mode | PTY behavior |
| --- | --- |
| `new` | Restart session (fresh PTY) |
| `compact` | Send `/compact` through PTY |
| `continue` | Pointer only |
| `restart` | `fleet-runtime.py restart --force` |

## Capacity rebind

Provider/model/thinking live on the Vivi role record. To change capacity:

```bash
vivi role set <name> --project <root> --provider <p> --model <m> --thinking <level>
```

The next session restart picks up the new values automatically. To propagate
sooner across multiple sessions:

```bash
python3 scripts/fleet-runtime-rebind.py --project <root> apply
python3 scripts/fleet-runtime.py --project <root> --role <name> restart
```

fleet.json holds only operational bindings (session id, cwd, merge rights) —
not capacity.
