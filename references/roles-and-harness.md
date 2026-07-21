# Roles, axes, and harness

Arming a fleet, rebinding runtimes, Mind/Hand/Head duties.

## Execution harness values

| Harness | Meaning | Reference |
| --- | --- | --- |
| **`subagent`** (default) | Spawn in parent runtime; event-driven completion | [`subagent.md`](subagent.md) |
| **`tmux`** | External tmux pane; polled completion | [`tmux.md`](tmux.md) |
| **`vivi_pty`** | Structured PTY session; polled completion | [`vivi-pty.md`](vivi-pty.md) |
| **`pi`** | Pi TUI in tmux/PTY (legacy harness value; implies tmux or vivi_pty) | [`pi.md`](pi.md) |
| **`codex`** | Codex CLI in tmux (compatibility exception) | [`tmux.md`](tmux.md) |
| **`opencode`** | opencode CLI in tmux (compatibility exception) | [`tmux.md`](tmux.md) |
| **`kimi`** | Kimi Code CLI in tmux (compatibility exception) | [`tmux.md`](tmux.md) |

With Vivi 6.0+ roles, capacity (provider/model/thinking) lives on the role
record (`vivi role set`). The harness field on the role (or fleet.json `agent`)
determines execution backend. Sub-agent is the default for new fleets.

## Roles

| Role | Typical identity | Job | Output |
| --- | --- | --- | --- |
| **Hand** | `hand-1`…`hand-N`, **`auditor-1` / `auditor-2`** | Implement product **or** run code review — same Hand category; duty differs by identity | Done + evidence, or `auditor-N report:` To `mind` |
| **Mind** | Board **`mind@…`** — no external runtime; process = operator TUI | Survey product; **dole out** tasking; integrate; **triage audit need**; fleet ops; operator mail | Open tasks/needs; wake Hands (incl. auditors); merge queue |
| **Operator mail** | Board **`operator@…` only** — no external runtime | Accrue human escalations while autonomous | Need/mail To human — **not** status |
| **Steward** | optional runtime (not Mind) | Dead-man: watch successful cycle ticks; trip → hold + page | `steward.sh` |
| **head-ceo** (Head) | `head-ceo` | **Strategist:** map health, sequencing, side-lane buckets | Mail To `mind` |
| **head-cto** (Head) | `head-cto` | **Gate honesty / architecture** — not the code-review Hand queue | Mail To `mind` |
| **head-cxo** (Head) | `head-cxo` | Complexity / purity | Mail To `mind` |

**CTO is a kind of Head; auditor is a kind of Hand** — not a fourth top-level class. Configure `auditor-1` / `auditor-2` under **`hands`** in `fleet.json` (skill **`$auditor`**; auditor Hands review, never commit product code). Mind files and wakes; Heads advise; implementer Hands ship; auditor Hands review when assigned.

Prefer numbered hands (`hand-N`) over harness-named identities. Keep the product plane on Pi by default; Heads may use different Pi providers or models for independent review.

## Fleet axes (identity ≠ assignment ≠ runtime)

```text
hand-N  =  identity (mail + role)
              ├── assignment   focus / packet / cwd / merge rights
              └── runtime      harness + model + wake/reinit policy
```

| Axis | Meaning | Sticky? |
| --- | --- | --- |
| **Identity** | Who owns bag + role (`hand-N`) | Mail identity while the slot exists |
| **Assignment** | What work that slot is on | Transient; Mind assigns per unit |
| **Runtime** | Harness + model + wake/reinit | Hand harness follows Mind. Model within harness may rebind. Heads free |

Product law talks in H-numbers + current assignment. Ops read runtime capacity from the Vivi role record and apply wake/reinit by harness, not H-number. Fleet.json holds operational bindings only (tmux targets, cwd, wake mode). Do not hardcode model strings into role tables as Hand identity.

## Harness alignment (Mind ↔ Hands vs Heads)

**Rule (one line):** default product-plane alignment (Hands share Mind's harness); **documented fleet config exceptions win** — do not "normalize" a deliberate heterogeneous fleet.

### Why Hands follow Mind's harness

The Mind is the **control plane** for the fleet. It has internal access to its own
systems instructions — the harness-level behavior, tooling surface, prompt
conventions, and agentic loop semantics — that shape how it formulates tasks,
describes done-when, and debugs Hand failures. When Hands share the same harness,
instructions the Mind writes are natively understood by the Hand without
translation or impedance mismatch.

For **sub-agent** fleets, Hands inherently share the Mind's harness — they are
spawned inside the parent runtime. This is the strongest alignment.

For **tmux/PTY** fleets, Hands run in separate panes/sessions. Same-harness
alignment means same CLI (Pi, Codex, etc.) across Mind and Hands.

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
live on the Vivi role record (`vivi role set`). Capacity ladders change Pi
provider/model without inventing permanent Hand identity from model strings.

**Unit-shape routing and capability classes** (volume implement vs design vs
review/audit vs repair loop): see **[`model-selection.md`](model-selection.md)**.
That reference is the portable process law. The tables below are harness
defaults and examples — not “everyone on one high-end model.”

### Product plane (Mind + Hands)

| Harness | Role | Preferred provider/model | Effort / thinking |
| --- | --- | --- | --- |
| **Pi** | **Mind** | operator-selected capable model | **medium** or higher |
| **Pi** | **Hand** (implementer) | **task-shape appropriate** — volume class for `mechanical`/`repair`; design class for `design`/`sensitive`/hard `ambiguous` | **low–medium** (volume); **high** (design) — see [`model-selection.md`](model-selection.md) |
| **Pi** | **Hand** (auditor-*) | **review / honesty class** (independent of implementer when risk is high) | **high** default |
| **Pi** | **Hand** (local/discrete units) | `llama-router` / local draft class | reasoning off; strong audit when risk is real |

| Note | Detail |
| --- | --- |
| Alignment | Mind and Hands use Pi; provider/model may differ by role, unit shape, or capacity. |
| Desktop Mind | When the interactive Mind is desktop-only, managed tmux Hands still use Pi. |
| Heads | Use Pi; vary provider, model, prompt, and role to preserve independent review. |
| Capacity | Step provider/model entries in `runtime_fallback`; do not change harness first. |
| Thesis | Cheap well-scoped implement → strong independent audit → cheap repair. Do not default every implementer to the scarce review-class model. |

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

| Role | Harness | Preferred class | Effort / thinking |
| --- | --- | --- | --- |
| **head-ceo** (strategist) | **Pi** | Design / high-judgment when chapter is product taste; volume OK for mechanical map hygiene | **medium–high** |
| **head-cto** (gate honesty, architecture) | **Pi** | Review / honesty for claim-gates; design class when residual is structure/taste | **high** when used |
| **head-cxo** (complexity, purity) | **Pi** | Volume often enough; design class when purity is structural feel | **medium–high** |
| Other Heads (CPO, COO, CSO, CFO, CMO) | **Pi** | Role-fit; project overlay names models | **medium–high** |

Advisors are largely one-shot (assign → report). Use Pi with a deliberately distinct provider/model when independent review benefits from diversity. Concrete model strings are project overlay (`fleet.json` + optional `.vivi/model-selection.md`), not Hand identity.

```text
pi --provider zai --model glm-5.2 --thinking high   # or xhigh
```

## Harness launch reference

Each harness has a distinct CLI and configuration surface. Capacity (provider/model/thinking) lives on the Vivi role record; the tables below describe each harness's flags for reference. For model/effort changes at runtime, see [`runtime-config.md`](runtime-config.md) § Model ladder.

### Principles

1. Capacity on the Vivi role record wins — never hardcode model strings as identity.
2. Model changes step the configured **Pi provider/model ladder** first.
3. Heads use Pi; model and thinking effort vary by role.

### Codex CLI (explicit compatibility exception)

Binary: `codex` (resolve from PATH or Fleet's portable binary lookup; callers may override with an explicit launch command).
Config: `~/.codex/config.toml` (TOML). Model and effort are baked into the config
by default; override per-invocation via `-c key=value` or `--model`.

| Flag | Purpose | Fleet use |
| --- | --- | --- |
| `-m` / `--model <MODEL>` | Model ID (e.g. `gpt-5.6-luna`, `gpt-5.6-sol`) | Model on Vivi role |
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

### Kimi Code CLI (explicit compatibility exception)

Binary: `kimi`. Documentation: [Kimi Code CLI](https://moonshotai.github.io/kimi-code/).
Kimi uses a persistent TUI with `/new`, `/compact`, `/yolo`, `/auto`, and
`/permission` controls. Fleet uses the Vivi role capacity as the source of truth and a
longer tmux submit-settle delay because rapid injected text can otherwise leave
Enter in the multiline composer.

| Flag | Purpose | Fleet use |
| --- | --- | --- |
| `-m` / `--model <MODEL>` | Model alias | Model on Vivi role |
| `-y` / `--yolo` | Skip regular tool approvals | Unattended Hands only |
| `--auto` | Automatically handle approvals/questions | Alternative operator-selected automation mode |
| `-S` / `--session [ID]` | Resume a session | Manual recovery; normal Fleet continuity keeps the TUI resident |
| `-c` / `--continue` | Continue the cwd's prior session | Explicit recovery only |
| `-p` / `--prompt <TEXT>` | Non-interactive one-shot | Advisory or diagnostic use, not a resident Hand |

**Typical Hand startup (in tmux):**

```bash
kimi --yolo
```

Kimi pane evidence used by Fleet:

- idle: boxed `> ` composer with `K<n> thinking:` and `context:` status;
- running: rotating moon phase followed by `· Tip:`;
- approval: approve/reject candidate list and `↵ confirm`.

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

**Kimi:**
| File / Dir | Purpose |
| --- | --- |
| `~/.kimi-code/` | Default Kimi Code configuration, sessions, logs, and update cache |
| `<project>/.kimi-code/` | Optional project-local Kimi settings |

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
| **Kimi** | `kimi --help` and `/model` in the TUI | Configured aliases and interactive model selection |

## Hand does

- Cheap intake; `show` only the chosen handle
- Drain open tasks/needs for **its** identity; validate; mark done with evidence
- **Commit own work** on assigned branch — the Hand has the diff context; see [SKILL.md § Commit authority and workflow](../SKILL.md#commit-authority-and-workflow)
- Advance campaign/docs Status when stage criteria hold and residuals empty (Status must not overclaim — e.g. static checks ≠ GPU product run)
- **After product unit lands:** `$polish` on **changed source files from this unit only** — main skill **End-of-unit polish**
- Exit when tasking empty for focus **and** map has no next package (or operator pause) — not when Mind stamp missing
- Clean turn end: mark done; turn-end mail with commit SHA + report
- **After unit:** clean commit + tasking done + turn-end. Expect Mind refill same cycle when campaign still has work
- **After theme on feature branch:** signal ready-to-merge; wait for Mind merge decision
- **Don't get stuck:** classify dirt A/B/C; file needs same turn; **pivot** when one item blocks

## Mind does

- **Is the operator entry point:** human conversation **is** Mind (board = `mind@…` + **`operator@…`** — no tmux for either)
- Resolve **interaction mode** each cycle — main skill + `mind-cycle.md`
- Find missed work, Status overclaims, missing evidence; file **targets** with where / done-when / evidence bar (**to owning Hand**)
- **Integration absorb/accept** — *absorb = bookkeeping when something moved; accept = audit loop passed (not code review)* — canon [`mind-cycle.md`](mind-cycle.md); not deep peer review of every unit
- Stay quiet when fingerprint unchanged, panes healthy, no ops signal
- Each wake: cheap **runtime scan**; wake idle/done agents with open targets; use backend-specific reinit (see [`tmux.md`](tmux.md) or [`vivi-pty.md`](vivi-pty.md)) only as fallback for stuck/down/error sessions
- Residual → **task** to Hand; agent decision hold → **need**; **human** wall / problem / blocker / bug-guidance → **`operator@`** (`operator-mail.md`); **runtime pointer only**
- **Branch and merge decisions:** Mind decides branch strategy at assignment time (main vs feature vs worktree); Mind owns feature-branch merge decisions
- **Push decisions:** Mind decides when to push; default off for Railway-linked repos
- **Post-main polish advisory:** main git tip moves → `suggest-polish-files.py` (JSON, capped); scores ≥ threshold → bounded polish **task** — Mind does not run polish loop
- **Major-inflection housekeeping:** campaign end / large multi-theme merge / stage closeout / operator ask only — **one** `$housekeeping` **task**; never after routine lands
- **Capacity packing:** when picking head-ceo side-lane buckets, use `effort` / `est_tokens` + recent `cost_calibration`
- **Cost calibration:** on Hand done for bound candidate, record actual vs est when known. If TUI does not surface usage (common for **Codex** interactive): `actual_tokens=null`, `actual_source=unavailable` (or `mind_estimate` if Mind ballparks). **Do not invent** token numbers.
- **Unstick half-dead dirt:** open the diff; class A mechanical → clear same turn; no multi-hour freeze
- **Autonomous:** thin ops; **decide now** on reversible defaults; head-ceo optional structure help, not permission gate; file **operator mail** when human needed; compact reports
- **Interactive:** full reasoning for operator; **rich FLEET_CYCLE reports**; maintain **operator_recap**; **present open operator@ list** on engagement
- **Steward:** default OFF; arm only when operator enables+asks per fleet; then `rearm` each successful cycle; **`disarm` when stopping if armed**; never treat steward as product Mind

## Mind does not

- Issue stage start/closeout GO/NO-GO as binding protocol
- Require multi-round mail before next map square
- Perform deep code review itself; triage and assign **`auditor-N` Hands + `$auditor`**
- Run full `$polish` or `$housekeeping` itself; thrash polish every quiet cycle; fire housekeeping on routine main lands
- Steal Hand’s unit or rewrite WIP mid-flight (raise; don’t hijack unless operator asks)
- Treat status-only dirty as multi-cycle freeze without classification
- Require introspecting own model/reasoning tier to choose behavior
- Treat Hand/Head board mail or **FLEET_CYCLE-only** payload as operator engagement (human chat *between* fires still counts)
- Wait multiple cycles on head-ceo for a decision it can make with a default
- Treat strong guidance as a hard ban that freezes progress
- Run a dual Mind process (second ops TUI/pane)
- Create external runtime for **`mind`** or **`operator`** (board inboxes only)
- File status / absorbs / “still running” To **`operator@`**

## head-cto does (Head)

- Prefer **main checkout** as review surface after themes/units land on main
- Self-directed bug / fail-closed / invariant audit; report `head-cto:` To Mind
- File or recommend **tasks** for implementable defects (Mind triages to owning Hand)
- Do **not** juggle every packet worktree as primary continuous review surface
- Do **not** act as merge GO/NO-GO; build-fast means some bugs reach main and get fixed there

## Heads do not

Approve/disapprove as a gate, race Mind on acceptance, merge to main, or own product tasking. **head-ceo** (strategist seat) proposes sequencing/ownership, map-health findings (inversions, false gates), and **side-lane (hand-2+) candidate buckets**; **head-cto** reviews main + technical gate honesty; **head-cxo** reports shape debt. Mind triages into the bag and coordinates live Hands. Proactivity scales with `fleet_posture` (see `fleet-posture.md`).
