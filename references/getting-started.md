# Getting started with `$fleet`

**Audience:** skill installed (or received); need a working fleet.

**Not every-cycle reading.** After attach, operate from `SKILL.md` + surface-specific references. Vocabulary: [`fleet-guide.md`](fleet-guide.md). Multi-fleet: [`multi-fleet.md`](multi-fleet.md).

## Which case are you in?

| Case | You have… | You need… | Jump to |
| --- | --- | --- | --- |
| **0 — First exposure** | Skill loaded; **no** attachable fleet visible | Operator briefing (what / how / next) | [§ First exposure](#0-first-exposure--no-fleet-to-attach) |
| **1 — Install** | Skill only | Host tools (especially **Vivi**) | [§ Install dependencies](#1-install-dependencies) |
| **2 — Initialize project** | Dependencies OK; project has no fleet yet | Vivi mailspace + fleet tracking files + first panes | [§ Initialize a project](#2-initialize-a-project) |
| **3 — Attach Mind** | Fleet already exists (`.vivi/` mailspace, board, maybe panes) | This session becomes Mind for that fleet | [§ Attach Mind to an existing fleet](#3-attach-mind-to-an-existing-fleet) |

Brand-new machine: **0 → 1 → 2 → 3** (brief first if the human just loaded the skill). Returning operator, new chat with a known fleet: **3 only**.

## 0. First exposure — no fleet to attach

**When (Mind detects this):** skill just loaded (or cold-loaded) and **none** of these are true:

- Operator named a project/`$ROOT` that has a Vivi mailspace (`$ROOT/.vivi/`)
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
2. Initialize a project (mailspace + role records + hand-1 pane) → case 2
3. Attach this session as Mind and cycle         → case 3
Day-to-day after attach: SKILL.md + surface refs; FLEET_CYCLE wakes the loop

Suggested next steps
- Pick the project root you want to fleet (path)
- If `vivi` missing: install Vivi (case 1)
- If no `.vivi/` mailspace yet: initialize that root (case 2)
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
**Fleet** = one project root + its `.vivi/` mailspace (durability boundary).

**No board without Vivi.** Do not invent a second tasking protocol if `vivi` is missing.

| Path | Role |
| --- | --- |
| `$ROOT/.vivi/` | Vivi mailspace root (sqlite board, identities, role records, blobs) |
| Vivi role records | Roster: Hands/Heads, `tmux_target`, capacity, harness, steward, focus |
| `$ROOT/.vivi/mind-baseline.json` | Cycle counters, fingerprints, mode, `mind_session` lock, recap |
| `$ROOT/.vivi/mind-watch.cursor` | Optional mailspace watch watermark |
| `$ROOT/.vivi/steward.rearm` / `steward.log` | Optional dead-man bookkeeping when steward used |

## 1. Install dependencies

### Required (hard)

| Dependency | Why | Min / notes |
| --- | --- | --- |
| **Vivi** (`vivi` CLI) | **Only** supported board | **≥ 6.4** |
| **bash** | Shell helpers (`scripts/lib/env.sh`, Python fleet scripts) | **3.2+** (not `sh` / not zsh-as-script) |
| **Python 3** | Cycle helpers | **≥ 3.9** |
| **Project root** | Where `.vivi/` lives | Writable directory |

### Strongly recommended

| Dependency | Why |
| --- | --- |
| **tmux** | Hand/Head/steward process plane |
| **git** | HEAD / dirty sensors |
| **Pi harness** for Mind, Hands, and Heads | Provider/model selected per role — `roles-and-harness.md` |

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
vivi --version          # want 6.4+
vivi mailspace --help
```

### Place this skill + host check

```bash
SK=<path-to-this-skill>/scripts
ls "$SK/fleet-sensors.py" "$SK/lib/env.sh"
bash --version; python3 --version   # ≥ 3.9
command -v tmux && tmux -V; command -v git
```

Optional: `VIVI_BIN`, `TMUX_BIN`, `PYTHON_BIN`. Portability: [`runtime-config.md`](runtime-config.md). Deps green → **case 2** or **case 3**.

## 2. Initialize a project

**When:** deps installed; `$ROOT` has no usable fleet (no mailspace).  
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

### 2.3 Add canonical roles

`vivi role add` creates the identity and its role record in one step. Pass
`--kind`/`--harness` (and `--provider`/`--model`/`--thinking` if you know them
up front); tune them later with `vivi role set`. It errors if the name already
exists, so re-running it on a role you already added is a loud signal to use
`vivi role set` instead.

```bash
vivi role add mind --project "$ROOT" --kind mind
vivi role add operator --project "$ROOT"                  # thin inbox: human escalations only
vivi role add hand-1 --project "$ROOT" --kind hand --harness tmux
# vivi role add hand-2 --project "$ROOT" --kind hand --harness tmux   # multi-hand later
vivi role add head-ceo --project "$ROOT" --kind head --harness subagent
vivi role add head-cto --project "$ROOT" --kind head --harness subagent
vivi role add head-cxo --project "$ROOT" --kind head --harness subagent
vivi role list --project "$ROOT"
```

`vivi mailspace identity add` remains as a thin-identity alias (no role
metadata) for mailboxes that are not agent seats.

| Identity | Role |
| --- | --- |
| `mind` | Fleet board (To: Mind); process = operator TUI |
| `operator` | Human escalations only (not status spam) |
| `hand-N` | Workers |
| `head-*` | Advisors (optional until needed) |

### 2.4 Configure role runtime bindings

Roster, capacity, harness, and steward live on the Vivi role record (created in
§2.3). Set the operational bindings each role needs to launch.

Recommended new-fleet shape: **session-per-fleet**. The tmux session is the
`fleet_id`, and each role gets a tmux window named after the role. This keeps
new repo families, copied fleets, and multi-fleet hosts from colliding.

```bash
# session-per-fleet: tmux_session == fleet_id; tmux_window == role
vivi role set mind --project "$ROOT" --harness pi

vivi role set hand-1 --project "$ROOT" \
  --tmux-session myfleet --tmux-window hand-1 --tmux-target 'myfleet:hand-1.1' \
  --cwd "$ROOT" --wake-mode tmux_send_keys --min-seconds-between-wakes 180

# auditor-1 is not in the canonical list above; add it in one step, then bind:
vivi role add auditor-1 --project "$ROOT" --kind hand --harness tmux --label auditor
vivi role set auditor-1 --project "$ROOT" \
  --tmux-session myfleet --tmux-window auditor-1 --tmux-target 'myfleet:auditor-1.1' \
  --cwd "$ROOT" --assignment-mode new --wake-mode tmux_send_keys \
  --min-seconds-between-wakes 180 \
  --note 'review Hand; assignments explicitly invoke $auditor; reports To mind'

vivi role list --project "$ROOT"
```

**Posture:** set growth / standby / dormant on the fleet config (the `fleet-posture.py` helper is removed; set `fleet_posture.mode` directly on the baseline or Vivi config). `growth` ships the map; `standby` / `dormant` = on-call or paused. Detail: [`posture.md`](posture.md).

Multi-fleet `tmux_layout`: [`runtime-config.md`](runtime-config.md), [`multi-fleet.md`](multi-fleet.md).

### Set capacity on Vivi roles

Capacity (provider/model/thinking) and charter live on the Vivi role record. The canonical roles are already created in one step above (§2.3); tune their capacity and charter here:

```bash
vivi role set hand-1 --project "$ROOT" --provider openai-codex --model gpt-5.5 --thinking medium
vivi role charter set hand-1 --project "$ROOT" --body 'You are a fleet product Hand. Execute assigned work, commit, report To mind.'

vivi role set auditor-1 --project "$ROOT" --provider openai-codex --model gpt-5.5 --thinking high
```

Legacy single-fleet targets (`tmux_session == role`, for example
`hand-1:1.1`) remain supported for existing one-off fleets. Do not choose that
layout for a new fleet unless the operator explicitly wants the old shape.

**Required (or created on first cycle):** `$ROOT/.vivi/mind-baseline.json`

```bash
printf '%s\n' '{}' > "$ROOT/.vivi/mind-baseline.json"
```

Optional later: watch cursor (auto-created by sensors), steward files (when `steward.enabled`).

### 2.5 Start process panes

```bash
# session-per-fleet: session name == fleet_id; window name == role
tmux new-session -d -s myfleet -n hand-1 -c "$ROOT"
# Launch command is constructed from the Vivi role capacity (provider/model/thinking) + harness
tmux send-keys -t myfleet:hand-1.1 Enter
# optional: tmux attach -t myfleet
```

Heads and steward panes can wait until enabled.

### 2.5a Cold clone / recovery note

Fresh clones do not preserve the other machine's file mtimes. When recovering
recent decisions or docs from a repo family, use git history before filesystem
timestamps:

```bash
git log --since '24 hours ago' --name-only --format='%h %cI %s'
git log --since '6 hours ago' --all -- <path-or-doc-dir>
```

If a discussed document is not in history or on a pushed branch, treat it as
unrecovered rather than reconstructing it from memory.

### 2.6 Smoke the board

```bash
vivi mailspace status --project "$ROOT"

vivi task send --project "$ROOT" \
  --from mind --to hand-1 \
  --subject 'BOOT: confirm identity and open bag' \
  --body 'Smoke task. done-when: listed open bag as hand-1 and confirmed cwd.'

SK=<path-to-this-skill>/scripts
python3 "$SK/fleet-sensors.py" --project "$ROOT" --text
```

### 2.7 Next step

Project **initialized**. Open operator agent session → **[case 3 — Attach Mind](#3-attach-mind-to-an-existing-fleet)**.

## 3. Attach Mind to an existing fleet

**When:** `$ROOT/.vivi/` mailspace (and usually role records) already exist. New operator chat, resume after compact, or taking over ops.  
**Goal:** this conversation becomes the **Mind session**.

Do **not** create a second Mind tmux pane. Do **not** re-init mailspace unless intentionally rebuilding the board.

### 3.1 Confirm the fleet is real

```bash
ROOT=/path/to/existing/fleet/project

test -d "$ROOT/.vivi" || { echo "missing .vivi/ mailspace — use case 2"; exit 1; }
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
| `lane_reconcile_candidate_<hand>` | Old dedicated binding needs campaign/task/Git truth reconciliation before wake or release |

### 3.2 Load process (this session)

1. Load **`$fleet`** (`SKILL.md`). **Cold** (empty context / post-`/compact` without recap): also load [`fleet-guide.md`](fleet-guide.md) once for vocab + SKILL tokens table. Hot cycle: SKILL alone if state in context.
2. State the attach explicitly:

```text
Attaching Mind to fleet project=$ROOT
```

3. **You are Mind** for this fleet until detach / wind-down / session end.
4. Before waking stopped dedicated lanes, disposition any lane reconciliation
   candidates through [`mind-cycle.md`](mind-cycle.md) § Campaign truth and lane
   lifecycle. Resume does not make an old open task current again.

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
- `waiting_for_input` / `completed` + open bag → doorbell via `tmux send-keys`. Codex uses a longer submit-settle delay.
- `down` / `error_*` → recreate pane or runtime ladder — do not assume init case 2.

```bash
# tmux backend — pointer doorbell:
tmux send-keys -t "<tmux_target>" "HAND WAKE hand-1. Task <hex>. Load charter and task from Vivi." Enter

# vivi-pty backend:
vivi-pty --project "$ROOT" terminal write <session-id> "HAND WAKE hand-1. Task <hex>." --enter

# Codex recovery (if a tmux doorbell sticks): recreate the pane/session directly.
```

### 3.6 Steward is OFF by default (operator opt-in)

**Do not arm steward on attach or when starting `/loop`.** Dead-man is optional,
and the steward implementation is currently paused (`steward.sh` was removed; a
Vivi-native steward is pending). Until it exists, steward cannot be armed.

Only if the operator **explicitly** wants steward **for this fleet** (when an
implementation exists):

1. Enable steward on the Vivi steward config (targets/notify as needed).
2. Operator asks to arm **this** fleet (not implied by multi-fleet siblings).
3. Arm via the future steward command (not available today).

Otherwise leave `enabled: false` and never attempt to arm/rearm. Detail: [`dead-man.md`](dead-man.md).

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
# steward rearm is not implemented today (steward.sh removed; Vivi-native steward pending)
```

Mode / reports: [`mind-cycle.md`](mind-cycle.md).

### 3.8 Detach (when you stop being Mind)

Same turn as you stop supervising — use the baseline script, never hand-edit:

```bash
# Clear mind_session and mark mind_loop.state=detached
python3 "$SK/fleet-baseline.py" bump -p "$ROOT" \
  -s 'detach' --acted --detach

# steward disarm is not implemented today; nothing to disarm.
```

Leaving without detach while steward armed would trip after grace once a steward implementation exists. Today steward cannot be armed, so there is no trip path. Recovery for future trips: clear tripped baseline state + re-attach (this case again).

Wind-down: [`runtime-config.md`](runtime-config.md). Multi-fleet attach set: [`multi-fleet.md`](multi-fleet.md).

### Attach checklist (copy)

```text
[ ] ROOT has .vivi/ mailspace
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
| Role records | Hands have `tmux_target`, `cwd` (operational only) |
| baseline | file exists; get via `fleet-baseline.py get -p $ROOT` |
| Pane | `tmux has-session` for the session in `tmux_target` |
| Sensors | `fleet-sensors.py --text` exit 0 or 2 (partial), not 1 |
| Mind attach | You can name `$ROOT`, bag state, and pane class without re-init |

## Common failures

| Symptom | Case | Fix |
| --- | --- | --- |
| `vivi: command not found` | 1 | Install Vivi; fix PATH |
| Old vivi / no `mailspace watch` | 1 | Upgrade ≥ 6.4 |
| No `.vivi/` / empty board | 2 | `mailspace init` + identities |
| Missing role records | 2 | Add roles + bindings via `vivi role add` / `vivi role set` |
| Sensors `vivi_missing` | 1–3 | PATH / wrong `--project` |
| Doorbell `no session` | 2–3 | Create tmux session; fix `tmux_target` |
| Doorbell `running` | 3 | Wait; do not stack wakes |
| Two Minds / lock conflict | 3 | One session per fleet; takeover only if authorized |
| Steward trip after chat died | 3 | Clear tripped baseline state + re-attach; disarm next time (when steward implementation exists) |
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
