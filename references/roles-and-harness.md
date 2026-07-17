# Roles, axes, and harness

Arming a fleet, rebinding runtimes, Mind/Hand/Head duties.

## Roles

| Role | Typical identity | Job | Output |
| --- | --- | --- | --- |
| **Hand** | `hand-1`…`hand-N`, **`auditor-1` / `auditor-2`** | Implement product **or** run code review — same Hand category; duty differs by identity | Done + evidence, or `auditor-N report:` To `mind` |
| **Mind** | Board **`mind@…`** — **no tmux**; process = operator TUI | Survey product; **dole out** tasking; integrate; **triage audit need**; fleet ops; operator mail | Open tasks/needs; wake Hands (incl. auditors); merge queue |
| **Operator mail** | Board **`operator@…` only** — **no tmux** | Accrue human escalations while autonomous | Need/mail To human — **not** status |
| **Steward** | tmux **`steward`** (not Mind) | Dead-man: watch successful cycle ticks; trip → hold + page | `steward.sh` |
| **head-ceo** (Head) | `head-ceo` | **Strategist:** map health, sequencing, side-lane buckets | Mail To `mind` |
| **head-cto** (Head) | `head-cto` | **Gate honesty / architecture** — not the code-review Hand queue | Mail To `mind` |
| **head-cxo** (Head) | `head-cxo` | Complexity / purity | Mail To `mind` |

**CTO is a kind of Head; auditor is a kind of Hand** — not a fourth top-level class. Configure `auditor-1` / `auditor-2` under **`hands`** in `fleet.json` (`merges_to_main: false`, skill **`$auditor`**). Mind files and wakes; Heads advise; implementer Hands ship; auditor Hands review when assigned.

Prefer numbered hands (`hand-N`) over harness-named identities. Keep the product plane on Pi by default; Heads may use different Pi providers or models for independent review.

## Fleet axes (identity ≠ assignment ≠ runtime)

```text
hand-N  =  identity (mail + tmux)
              ├── assignment   focus / packet / cwd / merge rights
              └── runtime      harness + model + wake/reinit policy
```

| Axis | Meaning | Sticky? |
| --- | --- | --- |
| **Identity** | Who owns bag + pane (`hand-N`) | Session name while the slot exists |
| **Assignment** | What work that slot is on | Usually only hand-1 main + merge rights. hand-2+ transient |
| **Runtime** | Harness + model + wake/reinit | Hand harness follows Mind. Model within harness may rebind. Heads free |

Product law talks in H-numbers + current assignment. Ops read runtime from fleet (`agent`, `agent_launch`) and apply wake/reinit by harness, not H-number. Live bindings in **project fleet config**. Do not hardcode model strings into role tables as Hand identity.

## Harness alignment (Mind ↔ Hands vs Heads)

**Rule (one line):** default product-plane alignment (Hands share Mind’s harness); **documented fleet config exceptions win** — do not “normalize” a deliberate heterogeneous fleet.

### Why Hands follow Mind’s harness

The Mind is the **control plane** for the fleet. It has internal access to its own
systems instructions — the harness-level behavior, tooling surface, prompt
conventions, and agentic loop semantics — that shape how it formulates tasks,
describes done-when, and debugs Hand failures. When Hands share the same harness,
instructions the Mind writes are natively understood by the Hand without
translation or impedance mismatch.

A Hand on a different harness from its Mind must cope with instructions shaped
by a different agentic loop, tool-use conventions, and internal model of how
work gets done. This adds translation friction and increases miscommunication.
The product plane stays coherent when the control and execution planes use Pi.

**Exception:** This is a strong default, not a law. A documented fleet config
may temporarily select another supported harness when the operator has a
specific capacity or compatibility reason. The exception must be deliberate,
recorded, and removed when the constraint clears.

| Role | Harness policy | Model policy |
| --- | --- | --- |
| **Mind** | Source of truth for product harness *unless* fleet records a Hand exception | May change for capacity; Hands follow when aligned |
| **Hand** | **Same harness as Mind** by default | May differ within that harness (ladder) |
| **Head** | **Pi with a distinct provider and/or model when useful** | Independent advice without changing harness |
| **Hand (auditor-*)** | **Same harness as other Hands / Mind** | May use higher thinking; process is still `$auditor` |

Pi-aligned roles keep one wake/reinit/bootstrap surface. Heads diversify through provider, model, prompt, and role—not by changing the default harness.

**Documented exceptions (do not override without operator):**

| Exception | Why |
| --- | --- |
| Desktop-only Mind + Pi Hands | Desktop harness cannot run in tmux; Pi remains the managed pane harness |
| Operator-recorded temporary mixed Hands | Capacity/experiment — baseline note; re-align when quiet |

**Arm / rebind:**

1. On arm, set every Hand’s `agent` + `wake_mode` + reinit from Mind’s harness **unless** fleet already pins a different Hand `agent`.
2. If Mind changes harness, rebind Hands on next clean breakpoint — except documented exceptions.
3. Capacity on a Hand: step **same-harness** model ladder first. Do not flip Hand harness while Mind stays original unless operator records exception.
4. Capacity on Mind: prefer same-harness recovery; if Mind must move harness, rebind Hands or park Hands and recover Mind first.
5. Heads are **out of** this rule. Rebind a Head only for its own capacity or operator preference.

**Anti-pattern:** “H3 is always Codex” as permanent product law **or** forcing all Hands onto Mind’s harness when fleet.json already declares a valid exception. Assignment stays independent of harness.

## Preferred models by role

Default every managed role to the **Pi harness**. Live provider, model, and effort
remain project configuration (`provider`, `agent_model`, `agent_launch`, thinking
flags). Capacity ladders change Pi provider/model without inventing permanent
Hand identity from model strings.

### Product plane (Mind + Hands)

| Harness | Role | Preferred provider/model | Effort / thinking |
| --- | --- | --- | --- |
| **Pi** | **Mind** | operator-selected capable model | **medium** or higher |
| **Pi** | **Hand** | task-appropriate provider/model | **medium** or higher |
| **Pi** | **Hand** (local/discrete units) | `llama-router` / `ornith-35b-q8` | reasoning off |

| Note | Detail |
| --- | --- |
| Alignment | Mind and Hands use Pi; provider/model may differ by role or capacity. |
| Desktop Mind | When the interactive Mind is desktop-only, managed tmux Hands still use Pi. |
| Heads | Use Pi; vary provider, model, prompt, and role to preserve independent review. |
| Capacity | Step provider/model entries in `runtime_fallback`; do not change harness first. |

### Pi local Hands

Validated 2026-07-11 against `ornith-35b-q8` via local `llama-router` (`~/.pi/agent/models.json`), one-shot `--print` and persistent tmux TUI.

| Topic | Guidance |
| --- | --- |
| Scope | Discrete, well-specified units (write, run, self-verify); use a stronger Pi provider/model for ambiguous, multi-step, or long-context work |
| Wake | Plain `pi` (no `--print`) idles in tmux; `send-keys … Enter` wakes; context retained; `/compact` works when the session is large enough |
| Autonomy | Passive between wakes; the Mind supplies lifecycle pointers and checks completion |
| Slash surface | `/help` is model input rather than a guaranteed command; use documented Pi commands only |
| cwd | Pin by true process cwd, not preceding shell `cd` in a compound command. Prefer a subshell or `tmux new-session -c <cwd>`; verify on first use |
| Capacity | Stay on Pi and select a stronger provider/model when the unit needs deeper reasoning |

```bash
pi --provider llama-router --model ornith-35b-q8
pi --provider llama-router --model ornith-35b-q8 --print --no-session "<task>"
(cd /path/to/worktrees/<slug> && pi --provider llama-router --model ornith-35b-q8 …)
```

### Advisor plane (Heads — Pi harness, role-dependent models)

| Role | Harness | Preferred model | Effort / thinking |
| --- | --- | --- | --- |
| **head-ceo** (strategist) | **Pi**, zai | GLM 5.2 | **high** or **xhigh** |
| **head-cto** (code review, gate honesty) | **Pi**, zai | GLM 5.2 | **high** or **xhigh** |
| **head-cxo** (complexity, purity) | **Pi**, zai | GLM 5.2 | **high** or **xhigh** |
| Other Heads (CPO, COO, CSO, CFO, CMO) | **Pi**, zai | GLM 5.2 | **high** or **xhigh** |

Advisors are largely one-shot (assign → report). Use Pi with a deliberately distinct provider/model when independent review benefits from diversity.

```text
pi --provider zai --model glm-5.2 --thinking high   # or xhigh
```

## Harness launch reference

Each harness has a distinct CLI and configuration surface. The fleet `agent_launch`
field in fleet.json is the source of truth per slot; the tables below help
operators write that field. For model/effort changes at runtime, see
[`runtime-config.md`](runtime-config.md) § Model ladder.

### Principles

1. `agent_launch` in fleet.json wins for every slot — never hardcode model strings as identity.
2. Model changes step the configured **Pi provider/model ladder** first.
3. Heads use Pi; model and thinking effort vary by role.

### Codex CLI (explicit compatibility exception)

Binary: `codex` (resolve from PATH or Fleet's portable binary lookup; callers may override with an explicit launch command).
Config: `~/.codex/config.toml` (TOML). Model and effort are baked into the config
by default; override per-invocation via `-c key=value` or `--model`.

| Flag | Purpose | Fleet use |
| --- | --- | --- |
| `-m` / `--model <MODEL>` | Model ID (e.g. `gpt-5.6-luna`, `gpt-5.6-sol`) | Set `agent_model` |
| `-c` / `--config <key=value>` | Override config dotted path | Toggle effort without editing file |
| `-p` / `--profile <NAME>` | Layer a named profile on base config | Profile for different models |
| `-s` / `--sandbox <MODE>` | Sandbox mode | `danger-full-access` for Hands |
| `-C` / `--cd <DIR>` | Working directory | Packet cwd |
| `--enable` / `--disable <FEATURE>` | Toggle features | Fine-grained control |
| `--dangerously-bypass-approvals-and-sandbox` | Full trust mode | Automation only |
| `--oss` / `--local-provider <NAME>` | Use open-source provider | Local LM Studio / Ollama |

**Per-invocation model + effort:**
```bash
codex -m gpt-5.6-luna -c model_reasoning_effort=xhigh
```

**Non-interactive (headless):**
```bash
codex exec -m gpt-5.6-sol -c model_reasoning_effort=medium "<prompt>"
```

**Codex config for fleet Hands (typical):**
```toml
model = "gpt-5.6-luna"
model_reasoning_effort = "xhigh"
sandbox_mode = "danger-full-access"
approval_policy = "never"
```

### Pi CLI

Binary: `pi` (Node.js CLI, typically installed via npm). Config: `~/.pi/agent/settings.json`
(JSON) for defaults; `~/.pi/agent/models.json` (JSON) for the provider/model registry.
List available models: `pi --list-models [<search>]`.

| Flag | Purpose | Fleet use |
| --- | --- | --- |
| `--provider <NAME>` | Provider name (`zai`, `openrouter`, `openai-codex`, `llama-router`, `google`) | Routes to model backend |
| `--model <PATTERN>` | Model ID or glob pattern | Select model |
| `--thinking <LEVEL>` | Thinking level: `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` | **Primary effort control** |
| `--print` / `-p` | Non-interactive (one-shot) | Head assign → report |
| `--continue` / `--resume` | Continue / resume session | Multi-turn Heads |
| `--no-session` | Ephemeral (no session saved) | Stateless one-shot |
| `--approve` / `-a` | Trust project-local files | First-run automation |
| `--system-prompt <TEXT>` | Custom system prompt | Role definition |
| `--append-system-prompt <TEXT>` | Append to default prompt | Layer role on base |
| `--no-tools` / `-nt` | Disable all tools | Advisory Heads (read-only) |
| `--no-builtin-tools` / `-nbt` | Disable built-in tools only | Keep extension/custom tools |
| `--exclude-tools` / `-xt <TOOLS>` | Denylist specific tools | Restrict write access |
| `--list-models [<search>]` | Query available models | Discovery |

**Typical Head launch (zai provider, GLM 5.2):**
```bash
pi --provider zai --model glm-5.2 --thinking high
pi --provider zai --model glm-5.2 --thinking xhigh --no-tools
```

**head-cto (Codex model via openai-codex provider):**
```bash
pi --provider openai-codex --model gpt-5.5 --thinking high
# or via openrouter:
pi --provider openrouter --model openai/gpt-5.5 --thinking high
```

**One-shot advisory:**
```bash
pi --provider zai --model glm-5.2 --thinking high --print --no-session "<task>"
```

**Model discovery:** `~/.pi/agent/models.json` lists every provider and their
models with capabilities, context windows, and costs. The `~/.pi/agent/settings.json`
`enabledModels` array controls which models appear in the TUI model switcher.

### opencode CLI

Binary: `opencode` (resolve from PATH or Fleet's portable binary lookup; callers may override with an explicit launch command).
Config: `~/.config/opencode/opencode.jsonc` (JSON with comments) and project-local `AGENTS.md`.
List available models: `opencode models [<provider>]`.

| Flag | Purpose | Fleet use |
| --- | --- | --- |
| `--model` / `-m <provider/model>` | Model selector (e.g. `opencode/gpt-5.6-sol`) | Model selection |
| `--variant <LEVEL>` | Reasoning effort (provider-specific: `high`, `max`, `minimal`) | Effort control |
| `--auto` | Auto-approve all permissions (dangerous) | Unattended Hands |
| `--continue` / `-c` | Continue last session | Multi-turn work |
| `--dir <PATH>` | Working directory | Packet cwd |
| `--agent <NAME>` | Agent profile name | Custom role config |
| `--pure` | Run without plugins | Minimal mode |

**Non-interactive:**
```bash
opencode run --model opencode/gpt-5.6-sol --variant high "do this task"
```

**Headless server:**
```bash
opencode serve --port 4096
opencode run --model opencode/gpt-5.5 --attach http://localhost:4096 "task"
```

**Typical Hand startup (in tmux):**
```bash
opencode --model opencode/gpt-5.5 --auto
```

### Vivi (mailspace) CLI

Binary: `vivi` (Rust CLI, typically at `~/.cargo/bin/vivi`). Config: defined by
`--config <path>` or per-account file.

| Subcommand | Fleet use |
| --- | --- |
| `mailspace` | Create/manage project mailspace (`status`, `watch`, `identity`, …) |
| `mail` | Board mail (`send`, `list`, `show`, `thread`, `watch`, `reply`, …) |
| `task` | File/complete tasking (`list`, `show`, `done`, …) |
| `need` | Decision needs (`file`, `list`, `done`, …) |
| `want` | Wants (`file`, `promote`, …) |

### Config file discovery

Each harness stores configuration in a well-known directory. The tables below
list the default search paths (“`~`” resolves to the current user’s home directory).

**Codex:**
| File / Dir | Purpose |
| --- | --- |
| `~/.codex/config.toml` | Model, sandbox, approval policy, profiles |
| `~/.codex/rules/` | Custom rules loaded per session |
| `~/.codex/skills/` | Skill file discovery |
| `~/.codex/profiles/*.config.toml` | Named config profiles (referenced via `-p` / `--profile`) |

**Pi:**
| File / Dir | Purpose |
| --- | --- |
| `~/.pi/agent/settings.json` | Default provider, model, thinking level, enabled models |
| `~/.pi/agent/models.json` | Provider registry: API keys, base URLs, model list with costs and capabilities |
| `~/.pi/agent/sessions/` | Session storage (per-project) |

**opencode:**
| File / Dir | Purpose |
| --- | --- |
| `~/.config/opencode/opencode.jsonc` | Shell, basic preferences |
| `<project>/AGENTS.md` | Project-level agent rules |

**Vivi:**
| File / Dir | Purpose |
| --- | --- |
| `<project>/.vivi/` | Project mailspace database and fleet overlay |

### Model discovery by harness

| Harness | Command | Output |
| --- | --- | --- |
| **Codex** | Config file (`~/.codex/config.toml` `model` key) | Single default; profiles for alternates |
| **Pi** | `pi --list-models [<provider>]` | Provider-filtered table with context, max-out, thinking support, images |
| **opencode** | `opencode models [<provider>]` | Provider-filtered model list |

## Hand does

- Cheap intake; `show` only the chosen handle
- Drain open tasks/needs for **its** identity; validate; mark done with evidence
- Advance campaign/docs Status when stage criteria hold and residuals empty (Status must not overclaim — e.g. static checks ≠ GPU product run)
- **After product unit lands:** `$polish` on **changed source files from this unit only** — main skill **End-of-unit polish**
- Exit when tasking empty for focus **and** map has no next package (or operator pause) — not when Mind stamp missing
- Clean turn end: mark done; turn-end / **ready-to-merge** mail when useful
- **hand-2+ after unit:** clean commit + tasking done + turn-end; no invent main work or merge. Expect Mind refill same cycle when campaign still has work
- **hand-2+ after theme RTM:** wait only for **integration** (Mind review → merge via hand-1)
- **Don't get stuck:** classify dirt A/B/C; file needs same turn; **pivot** when one item blocks

## Mind does

- **Is the operator entry point:** human conversation **is** Mind (board = `mind@…` + **`operator@…`** — no tmux for either)
- Resolve **interaction mode** each cycle — main skill + `mind-cycle.md`
- Find missed work, Status overclaims, missing evidence; file **targets** with where / done-when / evidence bar (**to owning Hand**)
- **Integration absorb/accept** — *absorb = bookkeeping when something moved; accept = integration bar (not code review)* — canon [`mind-cycle.md`](mind-cycle.md); not deep peer review of every packet
- Stay quiet when fingerprint unchanged, panes healthy, no ops signal
- Each wake: cheap **fleet pane scan**; doorbell idle/done panes with open targets; use **Codex reinit** (`scripts/codex-reinit.sh`) only as fallback for stuck/down/error Codex sessions
- Residual → **task** to Hand; agent decision hold → **need**; **human** wall / problem / blocker / bug-guidance → **`operator@`** (`operator-mail.md`); **tmux pointer only**
- **Post-main polish advisory:** main git tip moves → `suggest-polish-files.py` (JSON, capped); scores ≥ threshold → bounded polish **task** — Mind does not run polish loop
- **Major-inflection housekeeping:** campaign end / large multi-theme merge / stage closeout / operator ask only — **one** `$housekeeping` **task** To hand-1; never after routine lands
- **Capacity packing:** when picking head-ceo side-lane buckets, use `effort` / `est_tokens` + recent `cost_calibration`
- **Cost calibration:** on Hand done for bound candidate, record actual vs est when known. If TUI does not surface usage (common for **Codex** interactive): `actual_tokens=null`, `actual_source=unavailable` (or `mind_estimate` if Mind ballparks). **Do not invent** token numbers.
- **Unstick half-dead dirt:** open the diff; class A mechanical → clear same turn; no multi-hour freeze
- **Autonomous:** thin ops; **decide now** on reversible defaults; head-ceo optional structure help, not permission gate; file **operator mail** when human needed; compact reports
- **Interactive:** full reasoning for operator; **rich FLEET_CYCLE reports**; maintain **operator_recap**; **present open operator@ list** on engagement
- **Steward:** default OFF; arm only when operator enables+asks per fleet; then `rearm` each successful cycle; **`disarm` when stopping if armed**; never treat steward as product Mind

## Mind does not

- Issue stage start/closeout GO/NO-GO as binding protocol
- Require multi-round mail before next map square
- **Own fleet code-review quality** (**head-cto on main after merge**)
- Run full `$polish` or `$housekeeping` itself; thrash polish every quiet cycle; fire housekeeping on routine main lands
- Steal Hand’s unit or rewrite WIP mid-flight (raise; don’t hijack unless operator asks)
- Treat status-only dirty as multi-cycle freeze without classification
- Require introspecting own model/reasoning tier to choose behavior
- Treat Hand/Head board mail or **FLEET_CYCLE-only** payload as operator engagement (human chat *between* fires still counts)
- Wait multiple cycles on head-ceo for a decision it can make with a default
- Treat strong guidance as a hard ban that freezes progress
- Run a dual Mind process (second ops TUI/pane)
- Create tmux for **`mind`** or **`operator`** (board inboxes only)
- File status / absorbs / “still running” To **`operator@`**

## head-cto does (Head)

- Prefer **main checkout** as review surface after themes/units land on main
- Self-directed bug / fail-closed / invariant audit; report `head-cto:` To Mind
- File or recommend **tasks** for implementable defects (Mind triages to owning Hand)
- Do **not** juggle every packet worktree as primary continuous review surface
- Do **not** act as merge GO/NO-GO; build-fast means some bugs reach main and get fixed there

## Heads do not

Approve/disapprove as a gate, race Mind on acceptance, merge to main, or own product tasking. **head-ceo** (strategist seat) proposes sequencing/ownership, map-health findings (inversions, false gates), and **side-lane (hand-2+) candidate buckets**; **head-cto** reviews main + technical gate honesty; **head-cxo** reports shape debt. Mind triages into the bag and coordinates live Hands. Proactivity scales with `fleet_posture` (see `fleet-posture.md`).
