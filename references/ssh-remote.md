# Remote Hands and Heads over SSH

Load when a Hand or Head runs on a **different host** than Mind (SSH + remote tmux), or when arming a mixed local/remote fleet.

**Experimental strong guidance** — not host-specific. Any reachable host with SSH, tmux, and the agent binary works. Do not hardcode a particular server name into product law.

## Why

| Goal | How remote slots help |
| --- | --- |
| **Failure isolation** | Mind (desktop or local CLI) survives local tmux/shell death; remote panes keep running |
| **Token / machine budget** | Heavy Hands on a server; Mind stays light on the operator machine |
| **Compute / auth locality** | Work where the checkout, GPU, or agent login already lives |
| **Heads too** | Strategist / correctness / purity may sit on remote tmux the same way Hands do |

Mind may be local CLI, desktop app, or even another host. **Process truth** is still tmux on the **Hand/Head host**; **work truth** is still Vivi against the **mailspace project root** that owns the bag.

## Axes (same three, plus host)

```text
hand-N / strategist / …  =  identity (mail + remote tmux session name)
              ├── assignment   focus / packet / remote cwd / merge rights
              ├── runtime      harness + model + wake/reinit policy
              └── host         local | ssh target (where pane + cwd live)
```

| Field (fleet JSON) | Meaning |
| --- | --- |
| `host` | Optional. Omit or `"local"` = co-located with Mind ops. Non-local = remote slot. |
| `ssh` | SSH invocation prefix, e.g. `ssh -o BatchMode=yes user@host` (or a wrapper script) |
| `tmux_session` / `tmux_target` | Session/pane **on that host** |
| `cwd` | Path **on that host** (not Mind’s laptop path) |
| `agent_launch` | Command run **on that host** (include PATH setup if non-login SSH is bare) |
| `mailspace_project` | Optional. Project root for `vivi --project` if different from Mind’s view of the tree |

**Binding rule still holds:** mail identity token == tmux session name (on the host that runs the pane).

## Dual channel when remote

| Concern | Where it runs |
| --- | --- |
| Pane scan / capture | `ssh … 'tmux capture-pane -t <target> …'` |
| Doorbell | `ssh … 'tmux send-keys -t <target> -l -- "…"'` then Enter |
| Codex reinit / heal | Run `scripts/codex-reinit.sh` **on the Hand host** (`PROJECT`/`FLEET` remote paths), or SSH-wrap it |
| Vivi bag / watch / thread | Against the **mailspace that owns the board** — usually `vivi --project <root>` on a host that can see that `.vivi/` |
| Git work | Remote `cwd` checkout / worktree on the Hand host |

Do not assume Mind’s local `tmux` sees remote sessions. Do not assume laptop and remote share one filesystem unless the camp deliberately mounts or syncs it.

## Mailspace coherence

One board of record per camp. Options:

1. **Remote project owns `.vivi/`** — Mind calls `ssh host 'vivi --project /remote/root …'` (or rsync is wrong-direction for live board).  
2. **Shared/synced tree** — both hosts see the same project path (rare; document it).  
3. **Mind-local mailspace only** — Hands never run `vivi` locally; Mind files/shows everything (Hands only implement from pointers) — weaker for remote Hands that need bag CLI.

Prefer (1) when the Hand’s git root is remote. **Watch and thread** must hit the same SQLite event ledger the camp uses.

## Ops recipes (generic)

### Arm a remote Hand

```bash
SSH='ssh -o BatchMode=yes user@remote-host'
# Ensure login-like PATH if non-interactive shells are bare
REMOTE_PATH='export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.nvm/versions/node/v24.15.0/bin:$PATH"'

$SSH "tmux has-session -t hand-N 2>/dev/null || \
  tmux new-session -d -s hand-N -c /path/on/remote -n main"
$SSH "$REMOTE_PATH; tmux send-keys -t hand-N:1.1 -l -- 'codex' "  # or grok / pi
$SSH "tmux send-keys -t hand-N:1.1 Enter"
```

Discover real `tmux_target` (base-index) once; store in fleet.

### Pane classify / wake

```bash
$SSH 'tmux capture-pane -t hand-N:1.1 -p -S -25'
$SSH "tmux send-keys -t hand-N:1.1 -l -- 'HAND WAKE hand-N. Bag: show <handle>. Continue.'"
$SSH 'tmux send-keys -t hand-N:1.1 Enter'
```

Same pointer-only content rules as local dual-channel.

### Remote reinit (Codex)

```bash
$SSH 'export PATH=…; PROJECT=/path/on/remote FLEET=/path/to/fleet.json \
  /path/to/codex-reinit.sh heal hand-N'
```

Copy or symlink skill `scripts/codex-reinit.sh` onto the remote host; do not assume Mind’s laptop path exists there.

### Remote Head

Same pattern: identity = session name (`strategist`, `correctness`, `purity`), `agent=pi` (or camp preference), clean-slate/reinit policy unchanged — only the transport is SSH.

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
      "cwd": "/home/user/work/camp",
      "agent": "codex",
      "agent_launch": "export PATH=…; codex",
      "merges_to_main": false,
      "wake_mode": "tmux_send_keys_via_ssh"
    }
  },
  "head-correctness": {
    "mail_identity": "head-correctness",
    "host": "remote.example",
    "ssh": "ssh -o BatchMode=yes remote.example",
    "agent": "pi",
    "cwd": "/home/user/work/camp"
  }
}
```

Camps may use a small wrapper (`fleet-ssh hand-2 tmux …`) instead of raw `ssh` strings. Skill cares about meanings, not the wrapper name.

## Mind cycle when some slots are remote

Cheap sensors still run every cycle; for each remote slot:

1. `$ssh tmux has-session` / capture / classify (rate-limit; SSH RTT costs more than local)
2. Open bag for that identity via the **shared** mailspace project
3. Wake/reinit by **that slot’s runtime on that host**

Fail-fast still applies: do not open a long SSH tunnel monologue every quiet cycle. Batch remote captures when possible.

## Desktop Mind + remote Hands

A natural experiment: operator Mind in a desktop app; all product Hands (and optional Heads) on remote tmux. Mind has no local Hand panes. Benefits: token split + isolation from both local tmux death and terminal death. Duties unchanged — only transport and `host` fields change.

## Pitfalls

| Do | Don't |
| --- | --- |
| Store **host-scoped** cwd and absolute remote binaries | Assume laptop PATH/`which` on remote |
| Verify first capture after arm | Trust fleet JSON without live pane path/command |
| Run reinit on the Hand host | Kill local processes for a remote Hand |
| One mailspace board of record | Split “truth” across two unrelated `.vivi/` DBs without a plan |
| Prefer packet/remote for hand-2+ first | Put hand-1 merge-to-main on remote before camp is ready |

## Related

- Pane/wake semantics: `dual-channel.md`
- Vivi watch/thread for Mind sensors: `dual-channel.md` (mailspace watch / thread)
- Codex script: `scripts/codex-reinit.sh` + `runtime-config.md`
- Roles / desktop Mind: `roles-and-harness.md`
