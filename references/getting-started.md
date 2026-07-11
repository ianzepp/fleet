# Getting started with `$fleet`

**Audience:** you just installed this skill (or received a copy of the package) and want a working fleet.

**Not every-cycle reading.** After the fleet is armed, operate from `SKILL.md` + surface-specific references. For vocabulary/orientation later, see [`fleet-guide.md`](fleet-guide.md).

---

## What you are setting up

A **fleet** is dual-channel multi-agent work on one project root:

| Channel | Truth of… | Tool |
| --- | --- | --- |
| **Board** | Work (tasks, needs, wants, mail) | **Vivi** project mailspace (`.vivi/`) |
| **Panes** | Process (alive / idle / error) | **tmux** (Hands / Heads / steward) |

**Mind** is the operator’s current agent session (this chat) — not a tmux pane. Mind files work on the board and wakes panes with short pointers.

There is **no board fallback without Vivi**. If `vivi` is missing or broken, fleet tasking, status, watch, and steward pages cannot run. Install Vivi first; do not invent a second board protocol.

---

## Dependencies

### Required (hard)

| Dependency | Why | Min / notes |
| --- | --- | --- |
| **Vivi** (`vivi` CLI) | **Only** supported board / mailspace. Tasking bag, identities, watch, done mail. | **≥ 4.6** recommended (watch + thread). Current docs exercise **4.7+**. |
| **bash** | Skill shell helpers (`steward`, `doorbell`, `codex-reinit`, `env.sh`) | **3.2+** (macOS stock OK). Not `sh`; not zsh-as-script. |
| **Python 3** | Cycle helpers (`fleet-sensors`, `fleet-baseline`, …) | **≥ 3.9** |
| **A project root** | Durability boundary: `.vivi/` under the repo/worktree you are fleeting | Writable directory |

### Strongly recommended (process plane)

| Dependency | Why |
| --- | --- |
| **tmux** | Hand/Head/steward panes; doorbell, capture, reinit |
| **git** | HEAD / dirty sensors, merge clock honesty |
| **An agent harness** for Hands (same family as Mind) | e.g. Grok, Codex — see `roles-and-harness.md` |

Without tmux you can still use Vivi as a board, but you cannot run the dual-channel fleet process this skill describes.

### Optional

| Dependency | Why |
| --- | --- |
| Companion skills (`$polish`, `$housekeeping`, …) | Richer Hand hygiene; missing → [`companion-fallbacks.md`](companion-fallbacks.md) |
| Alternate Head harness (e.g. Pi) | Second-party review / research |
| External email account in Vivi | Steward dead-man **page** only; board `operator@` works without it |

---

## Install Vivi (do this first)

Vivi is distributed as the **Vivarium** project. The CLI binary is named **`vivi`**.

### macOS — Homebrew (preferred)

```bash
brew install ianzepp/tap/vivarium
vivi --version
```

### macOS or Linux — curl installer

```bash
curl -fsSL https://raw.githubusercontent.com/ianzepp/vivarium/main/install.sh | bash
# ensure install location is on PATH (often ~/.local/bin or ~/.cargo/bin)
vivi --version
```

### From source (developers)

```bash
git clone https://github.com/ianzepp/vivarium.git
cd vivarium
cargo install --path .
vivi --version
```

### Verify Vivi is usable for fleets

```bash
command -v vivi
vivi --version          # want 4.6+ (prefer 4.7+)
vivi mailspace --help   # must show init / status / watch / identity
```

**Fleet does not substitute another board.** If these fail, stop and fix the install before arming identities or writing `fleet.json`.

Upstream install detail: [vivarium README — Install](https://github.com/ianzepp/vivarium#install).

---

## Install / place this skill

How you attach skills depends on the agent client (Grok, Claude, Codex, …). Outcomes that matter:

1. The **`$fleet` / fleet skill directory** is loadable (contains `SKILL.md`, `references/`, `scripts/`).
2. Scripts are executable and findable:

```bash
SK=<path-to-this-skill>/scripts   # e.g. …/skills/fleet/scripts
ls "$SK/steward.sh" "$SK/fleet-sensors.py" "$SK/lib/env.sh"
bash "$SK/smoke-portability.sh"   # env + compile check (optional --project later)
```

Portability notes (PATH, Python, bash): [`runtime-config.md`](runtime-config.md) § Portability.

---

## Check the rest of the host

```bash
bash --version          # or /bin/bash --version on macOS
python3 --version       # ≥ 3.9
command -v tmux && tmux -V
command -v git
```

Optional env overrides if tools live outside PATH:

```bash
export VIVI_BIN="$(command -v vivi)"
export TMUX_BIN="$(command -v tmux)"
export PYTHON_BIN="$(command -v python3)"
```

---

## First fleet on a project (minimal arm)

Pick a **project root** (git repo or worktree). All board state lives under `$ROOT/.vivi/`.

### 1. Initialize the mailspace

```bash
ROOT=/path/to/your/project
cd "$ROOT"

vivi mailspace init --project "$ROOT"
```

### 2. Add canonical identities

```bash
# Board / human (no tmux)
vivi mailspace identity add mind --project "$ROOT"
vivi mailspace identity add operator --project "$ROOT"

# Hands (workers)
vivi mailspace identity add hand-1 --project "$ROOT"
# vivi mailspace identity add hand-2 --project "$ROOT"   # if multi-hand

# Heads (advisors) — add when you will use them
vivi mailspace identity add head-ceo --project "$ROOT"
vivi mailspace identity add head-cto --project "$ROOT"
vivi mailspace identity add head-cxo --project "$ROOT"

vivi mailspace identity list --project "$ROOT"
vivi mailspace status --project "$ROOT"
```

### 3. Create a tiny fleet overlay

Create `$ROOT/.vivi/fleet.json` (minimal single-host shape):

```json
{
  "version": 1,
  "project": "/path/to/your/project",
  "mailspace": "your-project-name",
  "mind_inbox": "mind",
  "operator_inbox": "operator",
  "default_hand": "hand-1",
  "mind": {
    "agent": "grok"
  },
  "hands": {
    "hand-1": {
      "mail_identity": "hand-1",
      "tmux_session": "hand-1",
      "tmux_target": "hand-1:1.1",
      "cwd": "/path/to/your/project",
      "agent": "grok",
      "agent_launch": "grok --always-approve",
      "merges_to_main": true,
      "wake_enabled": true,
      "wake_mode": "tmux_send_keys",
      "min_seconds_between_wakes": 180
    }
  },
  "steward": {
    "enabled": false
  }
}
```

Adjust `agent` / `agent_launch` / `cwd` to your harness and checkout. Full schema: [`runtime-config.md`](runtime-config.md).

Optional baseline (Mind will create/update this in cycles):

```bash
echo '{}' > "$ROOT/.vivi/mind-baseline.json"
```

### 4. Start a Hand pane (process plane)

```bash
# single-fleet host: session name == role
tmux new-session -d -s hand-1 -c "$ROOT"
tmux send-keys -t hand-1:1.1 -l -- 'grok --always-approve'   # or your agent_launch
tmux send-keys -t hand-1:1.1 Enter
# attach to watch: tmux attach -t hand-1
```

### 5. Smoke the board + sensors

```bash
vivi mailspace status --project "$ROOT"

# file a test task To hand-1
vivi task send --project "$ROOT" \
  --from mind --to hand-1 \
  --subject 'BOOT: show bag and reply done when idle' \
  --body 'Smoke task. done-when: you have listed open bag and confirmed identity hand-1.'

SK=<path-to-this-skill>/scripts
python3 "$SK/fleet-sensors.py" --project "$ROOT" --text
bash "$SK/smoke-portability.sh" --project "$ROOT"
```

### 6. Act as Mind (this session)

1. Load **`$fleet`** (`SKILL.md`).
2. Treat **this conversation** as Mind.
3. File real map work as **tasks** To `hand-1` (done-when in Vivi).
4. Wake with a **pointer only** when the pane is idle + bag open:

```bash
"$SK/fleet-doorbell.sh" --project "$ROOT" hand-1
```

5. When you schedule cycles, prefix wakes with `FLEET_CYCLE project=$ROOT …` (see `mind-cycle.md`).
6. If you enable steward later: `steward.enabled=true` + `scripts/steward.sh arm --project $ROOT`.

---

## “Is it working?” checklist

| Check | Command / signal |
| --- | --- |
| Vivi on PATH | `vivi --version` |
| Mailspace exists | `vivi mailspace status --project $ROOT` shows identities |
| Identities present | `mind`, `operator`, `hand-1` (and any Heads you use) |
| fleet.json valid | Hands have `tmux_target` + `cwd` + `agent_launch` |
| Pane up | `tmux has-session -t hand-1` (or your target session) |
| Sensors | `fleet-sensors.py --project $ROOT --text` exits 0 or 2 (partial), not 1 |
| Tasking | Open task shows for `hand-1`; doorbell or reinit starts work |

---

## Common first-hour failures

| Symptom | Fix |
| --- | --- |
| `vivi: command not found` | Install Vivi (Homebrew or curl above); fix PATH |
| `vivi` old / no `mailspace watch` | Upgrade to **≥ 4.6** (`brew upgrade` or re-run install.sh) |
| Sensors: `vivi_missing` / board empty | PATH or wrong `--project` |
| Doorbell: `refused: no session` | Create tmux session / fix `tmux_target` |
| Doorbell: `refused: pane is running` | Wait; do not stack wakes |
| Hand works wrong tree | Align `cwd` with `tmux` pane path / rehome |
| Two “Minds” fighting | One operator TUI per fleet; no fake mind tmux |

---

## What to read next

| When | Load |
| --- | --- |
| Orientation / vocabulary | [`fleet-guide.md`](fleet-guide.md) |
| Operating as Mind | parent [`SKILL.md`](../SKILL.md) |
| Board + pane ops | [`dual-channel.md`](dual-channel.md) |
| Cycle / modes / reports | [`mind-cycle.md`](mind-cycle.md) |
| Filing work | [`tasking.md`](tasking.md) |
| Roles / harness | [`roles-and-harness.md`](roles-and-harness.md) |
| Dead-man | [`dead-man.md`](dead-man.md) |
| Schema / wind-down | [`runtime-config.md`](runtime-config.md) |
| Multi-fleet | [`multi-fleet.md`](multi-fleet.md) |

**Do not** load every reference every cycle. Arm once with this file + `SKILL.md`; open others when the surface hits you.
