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
| `agent_launch` | Command **on that host** (PATH if non-login SSH bare) |
| `mailspace_project` | Optional. `vivi --project` root if ≠ Mind’s view |

**Binding:** mail identity token == tmux session name (on host running the pane).

## Dual channel when remote

| Concern | Where |
| --- | --- |
| Pane scan / capture | `ssh … 'tmux capture-pane -t <target> …'` |
| Doorbell | `ssh … 'tmux send-keys -t <target> -l -- "…"'` then Enter |
| Codex doorbell / reinit fallback | `fleet-doorbell.sh` first; `scripts/codex-reinit.sh` **on Hand host** (or SSH-wrap) only for stuck/down/error recovery; remote `PROJECT`/`FLEET` |
| Vivi bag / watch / thread | Host that can see board `.vivi/` |
| Git work | Remote `cwd` checkout / worktree |

Local `tmux` does not see remote sessions. No shared FS unless fleet mounts/syncs it.

## Mailspace coherence

One board of record per fleet:

| Option | When |
| --- | --- |
| **1. Remote owns `.vivi/`** | Prefer when Hand git root is remote. Mind: `ssh host 'vivi --project /remote/root …'` |
| **2. Shared/synced tree** | Both hosts same path (rare; document) |
| **3. Mind-local only** | Hands implement from pointers — weaker if remote Hands need bag CLI |

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
$SSH "tmux send-keys -t hand-N:1.1 -l -- 'HAND WAKE hand-N. Bag: show <handle>. Continue.'"
$SSH 'tmux send-keys -t hand-N:1.1 Enter'
```

Same pointer-only rules as local dual-channel.

### Remote reinit fallback (Codex)

```bash
$SSH 'export PATH=…; /path/to/codex-reinit.sh heal --project /path/on/remote \
  --fleet-file /path/to/fleet.json --role hand-N'
```

For normal remote Codex wakes, use the same pointer doorbell with submit-settle on the Hand host. Copy/symlink `scripts/codex-reinit.sh` onto remote only for fallback recovery; laptop path may not exist there.

### Remote Head

Identity = session name; `agent=pi` (or fleet preference); clean-slate/reinit policy unchanged — transport is SSH.

## Fleet config sketch

```json
{
  "hands": {
    "hand-2": {
      "mail_identity": "hand-2",
      "host": "remote.example",
      "ssh": "ssh -o BatchMode=yes remote.example",
      "tmux_session": "hand-2",
      "tmux_target": "hand-2:1.1",
      "cwd": "/home/user/work/fleet",
      "agent": "codex",
      "agent_launch": "export PATH=…; codex",
      "merges_to_main": false,
      "wake_mode": "tmux_send_keys_via_ssh"
    }
  },
  "head-cto": {
    "mail_identity": "head-cto",
    "host": "remote.example",
    "ssh": "ssh -o BatchMode=yes remote.example",
    "agent": "pi",
    "cwd": "/home/user/work/fleet"
  }
}
```

Wrapper (`fleet-ssh hand-2 tmux …`) OK; skill cares about meanings.

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
| Prefer packet/remote for hand-2+ first | hand-1 merge-to-main on remote before ready |

## Related

- Pane/wake + Vivi watch/thread: `dual-channel.md`
- Codex: `fleet-doorbell.sh`; fallback `scripts/codex-reinit.sh` + `runtime-config.md`
- Roles / desktop Mind: `roles-and-harness.md`
