# Getting started with `$fleet`

**Audience:** you installed this skill (or received a copy) and need a working fleet.

**Not every-cycle reading.** After attach, operate from `SKILL.md` + surface-specific references. Vocabulary: [`fleet-guide.md`](fleet-guide.md). Multi-fleet detail: [`multi-fleet.md`](multi-fleet.md).

---

## Which case are you in?

| Case | You have… | You need… | Jump to |
| --- | --- | --- | --- |
| **1 — Install** | Skill only | Host tools (especially **Vivi**) | [§ Install dependencies](#1-install-dependencies) |
| **2 — Initialize project** | Dependencies OK; project has no fleet yet | Vivi mailspace + fleet tracking files + first panes | [§ Initialize a project](#2-initialize-a-project) |
| **3 — Attach Mind** | Fleet already exists (`.vivi/fleet.json`, board, maybe panes) | This session becomes Mind for that fleet | [§ Attach Mind to an existing fleet](#3-attach-mind-to-an-existing-fleet) |

Typical order for a brand-new machine: **1 → 2 → 3**.  
Returning operator opening a new chat: **3 only**.

---

## What a fleet is (30 seconds)

| Channel | Truth of… | Tool |
| --- | --- | --- |
| **Board** | Work (tasks, needs, wants, mail) | **Vivi** project mailspace under `$ROOT/.vivi/` |
| **Panes** | Process (alive / idle / error) | **tmux** (Hands / Heads / steward) |

**Mind** = the operator’s current agent conversation (this chat) — **not** a tmux pane.  
**Fleet** = one project root + its `.vivi/` overlay (durability boundary).

There is **no board without Vivi**. Do not invent a second tasking protocol if `vivi` is missing.

### Tracking files (project overlay)

| Path | Role |
| --- | --- |
| `$ROOT/.vivi/` | Vivi mailspace root (sqlite board, identities, blobs) |
| `$ROOT/.vivi/fleet.json` | Roster: Hands/Heads, `tmux_target`, agents, steward, focus |
| `$ROOT/.vivi/mind-baseline.json` | Cycle counters, fingerprints, mode, `mind_session` lock, recap |
| `$ROOT/.vivi/mind-watch.cursor` | Optional mailspace watch watermark (created by sensors/watch) |
| `$ROOT/.vivi/steward.rearm` / `steward.log` | Optional dead-man bookkeeping when steward is used |

---

## 1. Install dependencies

### Required (hard)

| Dependency | Why | Min / notes |
| --- | --- | --- |
| **Vivi** (`vivi` CLI) | **Only** supported board | **≥ 4.6** (prefer **4.7+**) |
| **bash** | Shell helpers (`steward`, `doorbell`, …) | **3.2+** (not `sh` / not zsh-as-script) |
| **Python 3** | Cycle helpers | **≥ 3.9** |
| **Project root** | Where `.vivi/` lives | Writable directory |

### Strongly recommended

| Dependency | Why |
| --- | --- |
| **tmux** | Hand/Head/steward process plane |
| **git** | HEAD / dirty sensors |
| **Agent harness** for Hands (same family as Mind) | Grok, Codex, … — see `roles-and-harness.md` |

### Optional

Companion skills (`$polish`, …) → [`companion-fallbacks.md`](companion-fallbacks.md) if missing.  
External email in Vivi → steward **pages** only; board `operator@` works without it.

### Install Vivi (do this before case 2)

Vivi is the **Vivarium** project; binary name is **`vivi`**.

**macOS — Homebrew (preferred):**

```bash
brew install ianzepp/tap/vivarium
vivi --version
```

**macOS or Linux — curl:**

```bash
curl -fsSL https://raw.githubusercontent.com/ianzepp/vivarium/main/install.sh | bash
# ensure ~/.local/bin or install dir is on PATH
vivi --version
```

**From source:**

```bash
git clone https://github.com/ianzepp/vivarium.git
cd vivarium && cargo install --path .
vivi --version
```

**Verify:**

```bash
command -v vivi
vivi --version          # want 4.6+ (prefer 4.7+)
vivi mailspace --help   # init / status / watch / identity
```

If these fail, **stop** — case 2 and 3 will not work.

Upstream: [vivarium README — Install](https://github.com/ianzepp/vivarium#install).

### Place this skill + host check

```bash
SK=<path-to-this-skill>/scripts   # directory with SKILL.md’s scripts/
ls "$SK/steward.sh" "$SK/fleet-sensors.py" "$SK/lib/env.sh"
bash "$SK/smoke-portability.sh"

bash --version          # or /bin/bash --version
python3 --version       # ≥ 3.9
command -v tmux && tmux -V
command -v git
```

Optional overrides: `VIVI_BIN`, `TMUX_BIN`, `PYTHON_BIN`.  
Portability: [`runtime-config.md`](runtime-config.md) § Portability.

When deps are green → **case 2** (new project) or **case 3** (fleet already on disk).

---

## 2. Initialize a project

**When:** dependencies are installed; `$ROOT` has no usable fleet yet (no mailspace, or no `fleet.json`).

**Goal:** durable board + fleet tracking files + at least one Hand pane, ready for Mind attach (case 3).

### 2.1 Pick the root

```bash
ROOT=/path/to/your/project
cd "$ROOT"
# Prefer a git checkout or worktree you will actually work in
```

All fleet state for this project is under `$ROOT/.vivi/`.

### 2.2 Initialize the Vivi mailspace

```bash
vivi mailspace init --project "$ROOT"
vivi mailspace status --project "$ROOT"
```

### 2.3 Add canonical identities

```bash
# Board + human (no tmux)
vivi mailspace identity add mind --project "$ROOT"
vivi mailspace identity add operator --project "$ROOT"

# Hands
vivi mailspace identity add hand-1 --project "$ROOT"
# vivi mailspace identity add hand-2 --project "$ROOT"   # multi-hand later

# Heads — add when you will use them
vivi mailspace identity add head-ceo --project "$ROOT"
vivi mailspace identity add head-cto --project "$ROOT"
vivi mailspace identity add head-cxo --project "$ROOT"

vivi mailspace identity list --project "$ROOT"
```

| Identity | Role |
| --- | --- |
| `mind` | Fleet board (To: Mind); process = operator TUI |
| `operator` | Human escalations only (not status spam) |
| `hand-N` | Workers |
| `head-*` | Advisors (optional until needed) |

### 2.4 Write fleet tracking files

**Required:** `$ROOT/.vivi/fleet.json` — roster and process binding.

Minimal **single-fleet host** shape (`tmux_session` == role):

```json
{
  "version": 1,
  "project": "/path/to/your/project",
  "mailspace": "your-project-name",
  "fleet_id": "myfleet",
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

Replace paths, `agent` / `agent_launch`, and `cwd` for your harness and checkout.  
Full schema and multi-fleet `tmux_layout`: [`runtime-config.md`](runtime-config.md), [`multi-fleet.md`](multi-fleet.md).

**Required (or created on first cycle):** `$ROOT/.vivi/mind-baseline.json`

```bash
# Seed empty baseline (Mind / fleet-baseline.py will flesh it out)
printf '%s\n' '{}' > "$ROOT/.vivi/mind-baseline.json"
```

Optional later: watch cursor (auto-created by sensors), steward files (when `steward.enabled`).

### 2.5 Start process panes

```bash
# single-fleet: session name == role (must match fleet.json tmux_target)
tmux new-session -d -s hand-1 -c "$ROOT"
tmux send-keys -t hand-1:1.1 -l -- 'grok --always-approve'   # = agent_launch
tmux send-keys -t hand-1:1.1 Enter
# optional: tmux attach -t hand-1
```

Heads and steward panes can wait until you enable them.

### 2.6 Smoke the board

```bash
vivi mailspace status --project "$ROOT"

vivi task send --project "$ROOT" \
  --from mind --to hand-1 \
  --subject 'BOOT: confirm identity and open bag' \
  --body 'Smoke task. done-when: listed open bag as hand-1 and confirmed cwd.'

SK=<path-to-this-skill>/scripts
python3 "$SK/fleet-sensors.py" --project "$ROOT" --text
bash "$SK/smoke-portability.sh" --project "$ROOT"
```

### 2.7 Next step

Project is **initialized**. Open (or continue in) an operator agent session and do **[case 3 — Attach Mind](#3-attach-mind-to-an-existing-fleet)**.

---

## 3. Attach Mind to an existing fleet

**When:** `$ROOT/.vivi/fleet.json` (and usually a mailspace) already exist. You opened a **new** operator chat, resumed after compact, or are taking over ops for this project.

**Goal:** this conversation becomes the **Mind session** for the fleet — load context, claim attach, sense, then cycle.

Do **not** create a second Mind tmux pane. Do **not** re-init the mailspace unless the board is intentionally being rebuilt.

### 3.1 Confirm the fleet is real

```bash
ROOT=/path/to/existing/fleet/project

test -f "$ROOT/.vivi/fleet.json" || { echo "missing fleet.json — use case 2"; exit 1; }
vivi mailspace status --project "$ROOT"
vivi mailspace identity list --project "$ROOT"

SK=<path-to-this-skill>/scripts
python3 "$SK/fleet-sensors.py" --project "$ROOT" --text
# or: python3 "$SK/fleet-baseline.py" get -p "$ROOT"
```

| Signal | Meaning |
| --- | --- |
| Status shows identities + bag counts | Board OK |
| Sensors report pane classes | Process plane visible |
| Baseline `mind_loop.state` / `wound_up` | Prior wind-down or mid-run |
| Baseline `mind_session` set | Another Mind may already be attached (advisory) |
| Baseline `steward.tripped` | Dead-man fired — recover before normal cycles |

### 3.2 Load process (this session)

In the operator agent chat:

1. Load **`$fleet`** (`SKILL.md`). Thin first turn: main skill + this file if attach is unclear; open other refs as surfaces hit.
2. State the attach explicitly (for history and for you):

```text
Attaching Mind to fleet project=$ROOT
```

3. **You are Mind** for this fleet until detach / wind-down / session end.

### 3.3 Advisory `mind_session` lock

At most **one Mind session per fleet** (advisory — not a hard OS lock). On attach:

1. Read `$ROOT/.vivi/mind-baseline.json` → `mind_session`.
2. If locked by a **live foreign** session → refuse unless the operator asks for **takeover**.
3. Write / refresh:

```json
"mind_session": {
  "label": "short-session-label",
  "host": "hostname",
  "attached_at": "2026-07-11T17:00:00Z"
}
```

4. Set `mind_loop.state` toward `running` when you will cycle (not if only inspecting).

Forced takeover overwrites the advisory lock — use only when the operator confirms the other Mind is dead or yielded. Detail: [`multi-fleet.md`](multi-fleet.md) § Attach / detach.

### 3.4 Present operator mail and recap (if returning)

```bash
vivi need list --for operator --project "$ROOT"
vivi mail list --for operator --project "$ROOT"
```

If any open/unread **operator@** items → present them **first**, then status recap from baseline `operator_recap` / last cycle summary. Rules: [`operator-mail.md`](operator-mail.md).

### 3.5 Sense panes; rehome only if needed

- Prefer **`fleet-sensors.py --project $ROOT`** over hand-rolled dumps.
- `running` → do not wake.
- `idle_prompt` / `done_idle` + open bag → doorbell (Grok) or reinit (Codex).
- `down` / `error_*` → recreate pane or runtime ladder — do not assume init case 2.

```bash
# pointer wake when idle + open tasking (Grok / Pi-style)
"$SK/fleet-doorbell.sh" --project "$ROOT" hand-1
```

### 3.6 Arm steward only if you will run a scheduled loop

```bash
# if fleet.json steward.enabled and you will FLEET_CYCLE on a timer:
"$SK/steward.sh" arm --project "$ROOT"
```

If you are only chatting / one-shot ops, leave steward disarmed or leave prior state alone until you decide.

### 3.7 Run cycles from this session

Scheduled or manual wakes must be recognizable as ops, not operator prose:

```text
# Single fleet
FLEET_CYCLE project=$ROOT

# Multi-fleet (list every fleet this Mind session supervises)
FLEET_CYCLE fleets=mgs,faber project=/path/mgs also=/path/faber
```

Each successful mini-cycle:

```bash
python3 "$SK/fleet-baseline.py" bump -p "$ROOT" -s '…' [--quiet|--acted] \
  --fingerprint-file /tmp/sensors.json
"$SK/steward.sh" rearm --project "$ROOT"    # if steward armed
```

Mode / reports: [`mind-cycle.md`](mind-cycle.md).

### 3.8 Detach (when you stop being Mind)

Same turn as you stop supervising:

```bash
"$SK/steward.sh" disarm --project "$ROOT"   # if it was armed — avoid false trip
# baseline: mind_loop.state = detached (or wound_up); clear or stamp mind_session
```

Leaving without detach while steward is armed → steward **trips after grace** (correct failsafe). Recovery: `steward.sh clear` + re-attach (this case again).

Wind-down (panes down, long idle): [`runtime-config.md`](runtime-config.md). Multi-fleet attach set: [`multi-fleet.md`](multi-fleet.md).

### Attach checklist (copy)

```text
[ ] ROOT has .vivi/fleet.json
[ ] vivi mailspace status works
[ ] Load $fleet; this chat is Mind
[ ] mind_session advisory lock claimed (or takeover authorized)
[ ] operator@ listed if N>0; then recap
[ ] fleet-sensors.py once; act only on signal
[ ] steward arm only if FLEET_CYCLE loop will run
[ ] FLEET_CYCLE project=$ROOT … for scheduled wakes
[ ] detach/disarm same turn when stopping
```

---

## “Is it working?” (both case 2 and 3)

| Check | Signal |
| --- | --- |
| Vivi | `vivi --version` |
| Mailspace | `vivi mailspace status --project $ROOT` shows identities |
| Identities | `mind`, `operator`, `hand-1` (+ Heads you use) |
| fleet.json | Hands have `tmux_target`, `cwd`, `agent_launch` |
| baseline | file exists; get via `fleet-baseline.py get -p $ROOT` |
| Pane | `tmux has-session` for the session in `tmux_target` |
| Sensors | `fleet-sensors.py --text` exit 0 or 2 (partial), not 1 |
| Mind attach | You can name `$ROOT`, bag state, and pane class without re-init |

---

## Common failures

| Symptom | Case | Fix |
| --- | --- | --- |
| `vivi: command not found` | 1 | Install Vivi; fix PATH |
| Old vivi / no `mailspace watch` | 1 | Upgrade ≥ 4.6 |
| No `.vivi/` / empty board | 2 | `mailspace init` + identities |
| Missing `fleet.json` | 2 | Write overlay (template above) |
| Sensors `vivi_missing` | 1–3 | PATH / wrong `--project` |
| Doorbell `no session` | 2–3 | Create tmux session; fix `tmux_target` |
| Doorbell `running` | 3 | Wait; do not stack wakes |
| Two Minds / lock conflict | 3 | One session per fleet; takeover only if authorized |
| Steward trip after chat died | 3 | `steward.sh clear` + re-attach; disarm next time |
| Re-ran `mailspace init` on live fleet | 3 | Avoid; restore from backup if board wiped |

---

## What to read next

| When | Load |
| --- | --- |
| Vocabulary | [`fleet-guide.md`](fleet-guide.md) |
| Day-to-day Mind | parent [`SKILL.md`](../SKILL.md) |
| Board + panes | [`dual-channel.md`](dual-channel.md) |
| Cycles / modes | [`mind-cycle.md`](mind-cycle.md) |
| Filing work | [`tasking.md`](tasking.md) |
| Attach multi-fleet | [`multi-fleet.md`](multi-fleet.md) |
| Dead-man | [`dead-man.md`](dead-man.md) |
| Schema | [`runtime-config.md`](runtime-config.md) |

**Do not** load every reference every cycle. Case 2 once per project; case 3 at each new Mind session; then thin ops.
