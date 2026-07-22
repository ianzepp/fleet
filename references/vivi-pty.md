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

Sessions are configured on the Vivi role record for each Hand/Head role. Capacity
(provider/model/thinking) lives on the Vivi role record; the role record also
holds operational bindings:

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

## Runtime lifecycle

`fleet-runtime.py` (the backend-neutral helper) has been removed. vivi-pty
sessions are managed directly through the `vivi-pty` CLI:

```bash
vivi-pty --project <root> session list
vivi-pty --project <root> session start <session-id> -- <command...>
vivi-pty --project <root> session restart <session-id>
vivi-pty --project <root> session stop <session-id>
```

For vivi-pty roles:
- `session start` creates the configured session if absent or stopped
- `session restart` stops then starts through the PTY backend
- Stopped tombstones are restarted through `vivi-pty session restart`
- New sessions use the configured command array without shell evaluation

## Wake pattern

Doorbell through vivi-pty delivers the exact boot prompt emitted by `fleet
prepare`. See [`fleet-helper.md`](fleet-helper.md).

`fleet prepare` must succeed before the PTY write. Do not place new
authoritative instructions in the terminal or backfill Vivi afterward.

```bash
vivi-pty --project <root> terminal write faber-hand-1d \
  "<exact fleet prepare output>" \
  --enter
```

Or via the PTY backend directly:

```bash
vivi-pty --project <root> terminal write faber-hand-1d "<exact fleet prepare output>" --enter
```

The runtime backend is resolved from the Vivi role record (harness field).
Same channel split rules apply: the generated prompt is the only PTY payload.
Full instructions and scope are frozen in the prepared task; standing identity
and persona remain in the charter.

## assignment_mode

Same semantics as tmux ([`tmux.md`](tmux.md) § assignment_mode). The doorbell
helper applies the configured mode before the pointer. For vivi-pty:

| Mode | PTY behavior |
| --- | --- |
| `new` | Restart session (fresh PTY) |
| `compact` | Send `/compact` through PTY |
| `continue` | Pointer only |
| `restart` | `vivi-pty session restart` (optionally stop+start fresh) |

## Capacity rebind

Provider/model/thinking live on the Vivi role record. To change capacity:

```bash
vivi role set <name> --project <root> --provider <p> --model <m> --thinking <level>
```

The next session restart picks up the new values automatically. To propagate
sooner across multiple sessions, restart each role's session:

```bash
vivi-pty --project <root> session restart <session-id>
```

The Vivi role record holds only operational bindings (session id, cwd, merge rights) —
not capacity. The `fleet-runtime-rebind.py` helper has been removed; rebinds are
applied by restarting the affected sessions directly.
