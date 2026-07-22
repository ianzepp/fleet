# Remote Hands and Heads over SSH

Load when Hand/Head runs on a **different host** than Mind (SSH + remote tmux), or arming mixed local/remote fleet.

**Experimental strong guidance** — not host-specific. Any host with SSH, tmux, agent binary. Do not hardcode a server name into product law.

## Why

| Goal | Remote slots help |
| --- | --- |
| **Failure isolation** | Mind survives local tmux/shell death; remote panes keep running |
| **Token / machine budget** | Heavy Hands on server; Mind light on operator machine |
| **Compute / auth locality** | Work where checkout, GPU, or agent login lives |
| **Heads too** | head-ceo / head-cto / head-cxo same pattern as Hands |

**Process truth** = tmux on Hand/Head host. **Work truth** = Vivi against mailspace root that owns the bag.

## Axes (+ host)

```text
hand-N / head-*  =  identity (mail + remote tmux session name)
              ├── assignment   focus / packet / remote cwd / merge rights
              ├── runtime      harness + model + wake/reinit policy
              └── host         local | ssh target (where pane + cwd live)
```

| Field | Meaning |
| --- | --- |
| `host` | Omit/`"local"` = co-located. Non-local = remote. |
| `ssh` | e.g. `ssh -o BatchMode=yes user@host` |
| `tmux_session` / `tmux_target` | Session/pane **on that host** |
| `cwd` | Path **on that host** |
| `mailspace_project` | Optional. `vivi --project` root if ≠ Mind’s view |

**Binding:** mail identity token == tmux session name (on host running the pane).

## Dual channel when remote

| Concern | Where |
| --- | --- |
| Pane scan / capture | `ssh … 'tmux capture-pane -t <target> …'` |
| Doorbell | `ssh … 'tmux send-keys -t <target> -l -- "…"'` then Enter (the `fleet-doorbell.sh` helper is removed) |
| Codex prompt / recovery fallback | Exact `fleet prepare`/`prompt` output via `tmux send-keys` first; recreate the pane/session directly (the `codex-reinit.sh` helper is removed) for stuck/down/error recovery on the Hand host |
| Vivi bag / watch / thread | Host that can see board `.vivi/` |
| Git work | Remote `cwd` checkout / worktree |

Local `tmux` does not see remote sessions. No shared FS unless fleet mounts/syncs it.

## Mailspace coherence

One board of record per fleet:

| Option | When |
| --- | --- |
| **1. Remote owns `.vivi/`** | Prefer when Hand git root is remote. Mind: `ssh host 'vivi --project /remote/root …'` |
| **2. Shared/synced tree** | Both hosts same path (rare; document) |
| **3. Mind-local only** | Observation only; not valid for an active remote role because claim/settle cannot reach the ledger |

Watch/thread must hit the same SQLite ledger. Rsync is wrong-direction for live board.

## Ops recipes

### Arm remote Hand

```bash
SSH='ssh -o BatchMode=yes user@remote-host'
REMOTE_PATH='export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.nvm/versions/node/v24.15.0/bin:$PATH"'

$SSH "tmux has-session -t hand-N 2>/dev/null || \
  tmux new-session -d -s hand-N -c /path/on/remote -n main"
$SSH "$REMOTE_PATH; tmux send-keys -t hand-N:1.1 -l -- 'pi --provider <provider> --model <model> --approve' "
$SSH "tmux send-keys -t hand-N:1.1 Enter"
```

Discover real `tmux_target` once; store in fleet.

### Pane classify / wake

```bash
$SSH 'tmux capture-pane -t hand-N:1.1 -p -S -25'
# Run fleet prepare/prompt on the board-owning host, then send its exact output.
$SSH "tmux send-keys -t hand-N:1.1 -l -- '<exact generated prompt>'"
$SSH 'tmux send-keys -t hand-N:1.1 Enter'
```

The generated prompt's helper and project paths must be valid on the remote
host. Prefer running `fleet prepare` over SSH against the remote-owned
mailspace, then delivering that output in the same host context.

### Remote reinit fallback (Codex)

```bash
# Recreate the stuck Codex pane/session directly (codex-reinit.sh is removed):
$SSH "tmux kill-window -t hand-N:1 2>/dev/null; \
  tmux new-window -t hand-N -n main -c /path/on/remote"
$SSH "$REMOTE_PATH; tmux send-keys -t hand-N:1 -l -- 'codex --model <model> --dangerously-bypass-approvals-and-sandbox'"
$SSH 'tmux send-keys -t hand-N:1 Enter'
```

For normal remote wakes, run `fleet prepare` / `fleet prompt` where the shared
`.vivi` project and helper are available, then deliver the exact output with
remote `tmux send-keys`. Runtime recovery still uses plain tmux commands.

### Remote Head

Identity = session name; `agent=pi` (or fleet preference); clean-slate/reinit policy unchanged — transport is SSH.

## Fleet config via vivi role

Configure remote role capacity on Vivi role records:

```bash
# Remote Hand (tmux over SSH)
vivi role set hand-2 --project <root> \
  --harness tmux \
  --provider openai-codex --model gpt-5.5 --thinking medium

# Remote Head
vivi role set head-cto --project <root> \
  --harness pi \
  --provider zai --model glm-5.2 --thinking high
```

SSH connection details (`ssh -o BatchMode=yes remote.example`), tmux targets
(`hand-2:1.1`), and working directories are operational bindings the Mind
passes at assignment time or configures directly on the tmux backend — they
are not stored on the Vivi role record.

## Mind cycle with remote slots

Per remote slot (rate-limit; SSH RTT > local): (1) `$ssh tmux has-session` / capture / classify (2) open bag via **shared** mailspace (3) wake/reinit by **that slot’s runtime on that host**. Fail-fast: no long SSH monologue every quiet cycle; batch captures.

## Desktop Mind + remote Hands

Operator Mind in desktop app; product Hands (+ optional Heads) on remote tmux. Duties unchanged — only transport + `host` fields.

## Pitfalls

| Do | Don't |
| --- | --- |
| Host-scoped cwd + absolute remote binaries | Assume laptop PATH/`which` on remote |
| Verify first capture after arm | Trust fleet JSON without live pane |
| Reinit on Hand host | Kill local processes for a remote Hand |
| One mailspace board of record | Split truth across two `.vivi/` DBs |
| Prefer packet/remote for branch work first | Mind merge on remote before ready |

## Related

- Pane/wake + Vivi watch/thread: `dual-channel.md`
- Codex: exact generated Fleet prompt via `tmux send-keys`; fallback recovery by recreating the pane/session directly (helpers removed) + `runtime-config.md`
- Roles / desktop Mind: `roles-and-harness.md`
