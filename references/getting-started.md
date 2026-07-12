# Getting started with `$fleet`

**Audience:** skill installed (or received); need a working fleet.

**Not every-cycle reading.** After attach, operate from `SKILL.md` + surface-specific references. Vocabulary: [`fleet-guide.md`](fleet-guide.md). Multi-fleet: [`multi-fleet.md`](multi-fleet.md).

## Which case are you in?

| Case | You have… | You need… | Jump to |
| --- | --- | --- | --- |
| **0 — First exposure** | Skill loaded; **no** attachable fleet visible | Operator briefing (what / how / next) | [§ First exposure](#0-first-exposure--no-fleet-to-attach) |
| **1 — Install** | Skill only | Host tools (especially **Vivi**) | [§ Install dependencies](#1-install-dependencies) |
| **2 — Initialize project** | Dependencies OK; project has no fleet yet | Vivi mailspace + fleet tracking files + first panes | [§ Initialize a project](#2-initialize-a-project) |
| **3 — Attach Mind** | Fleet already exists (`.vivi/fleet.json`, board, maybe panes) | This session becomes Mind for that fleet | [§ Attach Mind to an existing fleet](#3-attach-mind-to-an-existing-fleet) |

Brand-new machine: **0 → 1 → 2 → 3** (brief first if the human just loaded the skill). Returning operator, new chat with a known fleet: **3 only**.

## 0. First exposure — no fleet to attach

**When (Mind detects this):** skill just loaded (or cold-loaded) and **none** of these are true:

- Operator named a project/`$ROOT` that has `$ROOT/.vivi/fleet.json`
- Cwd (or an obvious active project) has a usable fleet overlay
- Context already has a live attach set / `FLEET_CYCLE` fleet list
- Operator said “attach to …” / “run the fleet” with a path

**Do not** silently invent a fleet, re-init a random repo, or jump into dense cycle ops.  
**Do** reply to the **operator** with a short first-use briefing (below), then wait for their choice (or proceed only if they already asked to install/init a named root).

### What to tell the operator (template)

Output something in this shape — keep it short; link deeper sections rather than pasting the whole skill:

```text
$fleet — multi-agent project loops (Abbot Mind / Head / Hand)

What it is
- Mind = this chat (ops): file work, wake Hands, integrate — not a tmux pane
- Hands = worker panes (tmux) that clear the board bag
- Heads = advisors (research/review), not bag drain
- Dual channel: Vivi board = work truth; tmux = process truth
- One fleet = one project root + its .vivi/ overlay

How you use it
1. Install host deps (Vivi is hard-required)     → case 1
2. Initialize a project (mailspace + fleet.json + hand-1 pane) → case 2
3. Attach this session as Mind and cycle         → case 3
Day-to-day after attach: SKILL.md + surface refs; FLEET_CYCLE wakes the loop

Suggested next steps
- Pick the project root you want to fleet (path)
- If `vivi` missing: install Vivi (case 1)
- If no .vivi/fleet.json yet: initialize that root (case 2)
- If fleet already exists: attach Mind (case 3)
- Optional later: multi-hand, Heads, steward dead-man, multi-fleet attach

I will not create a fleet or attach until you name a root / case.
```

### Mind rules for case 0

| Do | Don't |
| --- | --- |
| Brief the human once when no fleet is visible | Pretend you are already Mid-cycle Mind for an unknown project |
| Ask for `$ROOT` or which case (1 / 2 / 3) | Dump every reference file into chat |
| After they pick a root, run the matching case | Run `mailspace init` without a chosen project |
| If they only want orientation, stop after the brief | Start FLEET_CYCLE / steward without an attach |

Once a real fleet is chosen and case 2 or 3 applies, leave this section — operate from `SKILL.md`.

## What a fleet is (30 seconds)

| Channel | Truth of… | Tool |
| --- | --- | --- |
| **Board** | Work (tasks, needs, wants, mail) | **Vivi** project mailspace under `$ROOT/.vivi/` |
| **Panes** | Process (alive / idle / error) | **tmux** (Hands / Heads / steward) |

**Mind** = operator’s current agent conversation — **not** a tmux pane.  
**Fleet** = one project root + its `.vivi/` overlay (durability boundary).

**No board without Vivi.** Do not invent a second tasking protocol if `vivi` is missing.

| Path | Role |
| --- | --- |
| `$ROOT/.vivi/` | Vivi mailspace root (sqlite board, identities, blobs) |
| `$ROOT/.vivi/fleet.json` | Roster: Hands/Heads, `tmux_target`, agents, steward, focus |
| `$ROOT/.vivi/mind-baseline.json` | Cycle counters, fingerprints, mode, `mind_session` lock, recap |
| `$ROOT/.vivi/mind-watch.cursor` | Optional mailspace watch watermark |
| `$ROOT/.vivi/steward.rearm` / `steward.log` | Optional dead-man bookkeeping when steward used |

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
| **Agent harness** for Hands (same family as Mind) | Grok, Codex, … — `roles-and-harness.md` |

Optional: companion skills → [`companion-fallbacks.md`](companion-fallbacks.md). External email → steward **pages** only; board `operator@` works without it.

### Install Vivi (before case 2)

Binary **`vivi`** (Vivarium). Upstream: [vivarium README — Install](https://github.com/ianzepp/vivarium#install).

```bash
# macOS Homebrew (preferred)
brew install ianzepp/tap/vivarium && vivi --version

# macOS/Linux curl
curl -fsSL https://raw.githubusercontent.com/ianzepp/vivarium/main/install.sh | bash
# ensure ~/.local/bin or install dir on PATH

# From source
git clone https://github.com/ianzepp/vivarium.git
cd vivarium && cargo install --path . && vivi --version

# Verify (stop if any fail — case 2/3 will not work)
command -v vivi
vivi --version          # want 4.6+ (prefer 4.7+)
vivi mailspace --help
```

### Place this skill + host check

```bash
SK=<path-to-this-skill>/scripts
ls "$SK/steward.sh" "$SK/fleet-sensors.py" "$SK/lib/env.sh"
bash "$SK/smoke-portability.sh"
bash --version; python3 --version   # ≥ 3.9
command -v tmux && tmux -V; command -v git
```

Optional: `VIVI_BIN`, `TMUX_BIN`, `PYTHON_BIN`. Portability: [`runtime-config.md`](runtime-config.md). Deps green → **case 2** or **case 3**.

## 2. Initialize a project

**When:** deps installed; `$ROOT` has no usable fleet (no mailspace, or no `fleet.json`).  
**Goal:** durable board + fleet tracking files + ≥1 Hand pane, ready for Mind attach.

### 2.1 Pick the root

```bash
ROOT=/path/to/your/project
cd "$ROOT"
# Prefer a git checkout or worktree you will actually work in
```

All fleet state under `$ROOT/.vivi/`.

### 2.2 Initialize the Vivi mailspace

```bash
vivi mailspace init --project "$ROOT"
vivi mailspace status --project "$ROOT"
```

### 2.3 Add canonical identities

```bash
vivi mailspace identity add mind --project "$ROOT"
vivi mailspace identity add operator --project "$ROOT"
vivi mailspace identity add hand-1 --project "$ROOT"
# vivi mailspace identity add hand-2 --project "$ROOT"   # multi-hand later
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
  "fleet_posture": {
    "mode": "growth",
    "reason": "campaign — use standby for on-call fleets (quiet is OK)",
    "wake_triggers": ["operator product task", "operator@ need"],
    "ceo_continuity_min_hours": 6
  },
  "steward": {
    "enabled": false,
    "note": "default OFF — operator must set enabled:true and ask to arm per fleet"
  }
}
```

**Posture:** `growth` ships the map; `standby` / `dormant` = on-call or paused (Vivi-shaped fleets). Detail: [`fleet-posture.md`](fleet-posture.md).

Replace paths, `agent` / `agent_launch`, and `cwd`. Full schema / multi-fleet `tmux_layout`: [`runtime-config.md`](runtime-config.md), [`multi-fleet.md`](multi-fleet.md).

**Required (or created on first cycle):** `$ROOT/.vivi/mind-baseline.json`

```bash
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

Heads and steward panes can wait until enabled.

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

Project **initialized**. Open operator agent session → **[case 3 — Attach Mind](#3-attach-mind-to-an-existing-fleet)**.

## 3. Attach Mind to an existing fleet

**When:** `$ROOT/.vivi/fleet.json` (and usually mailspace) already exist. New operator chat, resume after compact, or taking over ops.  
**Goal:** this conversation becomes the **Mind session**.

Do **not** create a second Mind tmux pane. Do **not** re-init mailspace unless intentionally rebuilding the board.

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

1. Load **`$fleet`** (`SKILL.md`). **Cold** (empty context / post-`/compact` without recap): also load [`fleet-guide.md`](fleet-guide.md) once for vocab + SKILL tokens table. Hot cycle: SKILL alone if state in context.
2. State the attach explicitly:

```text
Attaching Mind to fleet project=$ROOT
```

3. **You are Mind** for this fleet until detach / wind-down / session end.

### 3.3 Advisory `mind_session` lock

At most **one Mind session per fleet** (advisory — not a hard OS lock). On attach:

1. Read `$ROOT/.vivi/mind-baseline.json` → `mind_session` (use `fleet-baseline.py get`).
2. If locked by a **live foreign** session → refuse unless operator asks for **takeover**.
3. Write / refresh via the baseline script — never hand-edit:

```bash
SK=<path-to-this-skill>/scripts
python3 "$SK/fleet-baseline.py" bump -p "$ROOT" \
  -s 'attach: <short-label>' \
  --acted \
  --mind-session '<short-session-label>' \
  [--mind-host 'hostname'] \
  --recap 'Attached Mind session <label>'
```

This sets `mind_session`, `mind_loop.state=attached`, resets silence counters
(operator engaged), and writes a recap line — all in one safe call.

4. Verify the lock was written:

```bash
python3 "$SK/fleet-baseline.py" get -p "$ROOT" \
  | python3 -c "import json,sys; b=json.load(sys.stdin); print(b.get('mind_session')); print('state:', b.get('mind_loop',{}).get('state'))"
```

Forced takeover overwrites the advisory lock — only when operator confirms the other Mind is dead or yielded. Detail: [`multi-fleet.md`](multi-fleet.md) § Attach / detach.

### 3.4 Present operator mail and recap (if returning)

```bash
vivi mail list --for mind --project "$ROOT"       # From operator@ → mind (feedback)
vivi need list --for operator --project "$ROOT"
vivi mail list --for operator --project "$ROOT"   # To operator@ (human backlog)
```

If **operator→mind** mail or open/unread **To operator@** → present/absorb **first**, then status recap. Sensors flag `operator_to_mind` + `operator_mail`. Rules: [`operator-mail.md`](operator-mail.md).

### 3.5 Sense panes; rehome only if needed

- Prefer **`fleet-sensors.py --project $ROOT`** over hand-rolled dumps.
- `running` → do not wake.
- `idle_prompt` / `done_idle` + open bag → doorbell. Codex uses the helper's submit-settle delay.
- `down` / `error_*` → recreate pane or runtime ladder — do not assume init case 2.

```bash
"$SK/fleet-doorbell.sh" --project "$ROOT" hand-1 --handle <hex>

# Codex recovery only if the doorbell sticks:
# "$SK/codex-reinit.sh" doctor hand-1
# PROJECT="$ROOT" FLEET="$ROOT/.vivi/fleet.json" "$SK/codex-reinit.sh" reinit hand-1 --boot 'HAND WAKE …'
```

### 3.6 Steward is OFF by default (operator opt-in)

**Do not arm steward on attach or when starting `/loop`.** Dead-man is optional.

Only if the operator **explicitly** wants steward **for this fleet**:

1. Set `"steward": { "enabled": true, … }` in `fleet.json` (targets/notify as needed).
2. Operator asks to arm **this** fleet (not implied by multi-fleet siblings).
3. Then:

```bash
"$SK/steward.sh" arm --project "$ROOT"
```

Otherwise leave `enabled: false` and never call `arm` / `rearm`. Detail: [`dead-man.md`](dead-man.md).

### 3.7 Run cycles from this session

Scheduled or manual wakes must be recognizable as ops, not operator prose:

```text
# Single fleet
FLEET_CYCLE fleets=myfleet
# or: FLEET_CYCLE project=$ROOT

# Multi-fleet — slugs on first line; paths in body (not also=/also2=)
FLEET_CYCLE fleets=mgs,faber,nacht

Roots:
  mgs:   /path/to/minted-geek-swarm
  faber: /path/to/faberlang
  nacht: /path/to/nachtbagger
```

Each successful mini-cycle:

```bash
python3 "$SK/fleet-baseline.py" bump -p "$ROOT" -s '…' [--quiet|--acted] \
  --fingerprint-file /tmp/sensors.json
# "$SK/steward.sh" rearm --project "$ROOT"  # only if operator armed steward for this fleet
```

Mode / reports: [`mind-cycle.md`](mind-cycle.md).

### 3.8 Detach (when you stop being Mind)

Same turn as you stop supervising — use the baseline script, never hand-edit:

```bash
# Clear mind_session and mark mind_loop.state=detached
python3 "$SK/fleet-baseline.py" bump -p "$ROOT" \
  -s 'detach' --acted --detach

"$SK/steward.sh" disarm --project "$ROOT"   # if armed — avoid false trip
```

Leaving without detach while steward armed → steward **trips after grace** (correct failsafe). Recovery: `steward.sh clear` + re-attach (this case again).

Wind-down: [`runtime-config.md`](runtime-config.md). Multi-fleet attach set: [`multi-fleet.md`](multi-fleet.md).

### Attach checklist (copy)

```text
[ ] ROOT has .vivi/fleet.json
[ ] vivi mailspace status works
[ ] Load $fleet; this chat is Mind
[ ] mind_session advisory lock claimed via `baseline.py bump --mind-session <label>` (or takeover authorized)
[ ] mind@ From operator@ + To operator@ listed; absorb op→mind first; then recap
[ ] fleet-sensors.py once; act only on signal
[ ] steward stays OFF unless operator enabled+asked for this fleet
[ ] FLEET_CYCLE project=$ROOT … for scheduled wakes (loop ≠ steward)
[ ] if steward was armed: disarm same turn when stopping
```

## “Is it working?” (case 2 and 3)

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

## What to read next

| When | Load |
| --- | --- |
| No fleet / first skill load | This file **§0** — brief operator; do not invent attach |
| Vocabulary / cold attach | [`fleet-guide.md`](fleet-guide.md) (+ SKILL tokens table) |
| Day-to-day Mind | parent [`SKILL.md`](../SKILL.md) |
| absorb vs accept (canon) | [`mind-cycle.md`](mind-cycle.md) |
| Board CLI (`vivi` commands) | [`vivi.md`](vivi.md) |
| Board + panes | [`dual-channel.md`](dual-channel.md) |
| Cycles / modes | [`mind-cycle.md`](mind-cycle.md) |
| Filing work | [`tasking.md`](tasking.md) |
| Attach multi-fleet | [`multi-fleet.md`](multi-fleet.md) |
| Dead-man | [`dead-man.md`](dead-man.md) |
| Schema | [`runtime-config.md`](runtime-config.md) |

**Do not** load every reference every cycle. Case **0** once when no fleet is visible; case 2 once per project; case 3 at each new Mind session; then thin ops.
