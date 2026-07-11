# Roles, axes, and harness

Arming a fleet, rebinding runtimes, Mind/Hand/Head duties.

## Roles

| Role | Typical identity | Job | Output |
| --- | --- | --- | --- |
| **Hand** | `hand-1`…`hand-N` | Take a **selected target** and finish it | Done tasks/needs + evidence; optional turn-end mail To `mind` |
| **Mind** | Board **`mind@…`** — **no tmux**; process = operator TUI | Survey product; **dole out** tasking; integrate; fleet ops; pick from head-ceo buckets; **track est vs actual cost**; file/present **operator mail** | Open tasks/needs; pane scan; wake/reinit; merge queue; `cost_calibration` |
| **Operator mail** | Board **`operator@…` only** — **no tmux** | Accrue human escalations while autonomous | Need/mail To human; presented on return — **not** status |
| **Steward** | tmux **`steward`** (not Mind) | Dead-man: watch successful cycle ticks; trip → hold + page | `steward.sh`; operator@ + optional external email |
| **head-ceo** (Head) | `head-ceo` | **Strategist:** map health, misprioritization, gate honesty, sequencing; **hand-2+ buckets with effort + est_tokens** (growth expansion / standby stewardship) | Mail `head-ceo report:` To `mind` |
| **head-cto** (Head) | `head-cto` | **Code review / bug hunt on main after merge** | Mail `head-cto:` To `mind` |
| **head-cxo** (Head) | `head-cxo` | Self-directed complexity / purity audit (**not** operator voice) | Mail `head-cxo:` To `mind` |

One Mind owns the tasking bag and integration clock: **Mind files and wakes; Heads advise.** Heads never merge, never keep product tasking “full,” never stamp GO/NO-GO. **head-ceo** proposes **what hand-2+ could work on**; Mind decides when to bind a packet and file. Reports To: **mind**; Mind triages into hand-N tasks/needs.

Prefer numbered hands (`hand-N`) over shared `codex`. Prefer heterogeneous Head runtimes; keep Hand harness aligned with Mind.

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

| Role | Harness policy | Model policy |
| --- | --- | --- |
| **Mind** | Source of truth for product harness *unless* fleet records a Hand exception | May change for capacity; Hands follow when aligned |
| **Hand** | **Same harness as Mind** by default | May differ within that harness (ladder) |
| **Head** | **Prefer a different harness and/or model** | Independence is a feature |

Same-harness Hands keep one wake/reinit/bootstrap surface. Heads diversify to challenge the product plane. Default Heads: **Pi + GLM 5.2 (high/xhigh)**.

**Documented exceptions (do not override without operator):**

| Exception | Why |
| --- | --- |
| Desktop Claude Mind + Grok/Pi Hands | No desktop harness in tmux — Hands cannot match Mind |
| Pi Hand under desktop Mind | Local discrete units; zero API cost |
| Operator-recorded temporary mixed Hands | Capacity/experiment — baseline note; re-align when quiet |

**Arm / rebind:**

1. On arm, set every Hand’s `agent` + `wake_mode` + reinit from Mind’s harness **unless** fleet already pins a different Hand `agent`.
2. If Mind changes harness, rebind Hands on next clean breakpoint — except documented exceptions.
3. Capacity on a Hand: step **same-harness** model ladder first. Do not flip Hand harness while Mind stays original unless operator records exception.
4. Capacity on Mind: prefer same-harness recovery; if Mind must move harness, rebind Hands or park Hands and recover Mind first.
5. Heads are **out of** this rule. Rebind a Head only for its own capacity or operator preference.

**Anti-pattern:** “H3 is always Codex” as permanent product law **or** forcing all Hands onto Mind’s harness when fleet.json already declares a valid exception. Assignment stays independent of harness.

## Preferred models by role

Default arm preferences. Live ids in project fleet config (`agent_model`, `agent_launch`, effort flags). Capacity ladders step same-harness; they do not invent permanent Hand identity from model strings.

### Product plane (Mind + Hands — one harness family)

| Product harness | Role | Preferred model | Effort / thinking |
| --- | --- | --- | --- |
| **Grok** | **Mind** | Grok 4.5 | harness default |
| **Grok** | **Hand** | Grok 4.5 | harness default |
| **Codex** | **Mind** | `gpt-5.6-sol` | **medium** |
| **Codex** | **Hand** | `gpt-5.6-luna` | **xhigh** |
| **Claude Code (desktop)** | **Mind** | Sonnet 5 | app default |
| **Grok** | **Hand** (under desktop Mind) | Grok 4.5 | harness default |
| **Pi (`llama-router`)** | **Hand** (under desktop Mind, local/discrete units) | `ornith-35b-q8` | reasoning off |

| Note | Detail |
| --- | --- |
| Grok | Mind and Hand share model class (Grok 4.5) and harness |
| Codex | Mind/Hand may differ within family (sol/medium vs luna/xhigh); harness stays Codex |
| Claude desktop Mind | **Declared exception to Harness alignment** (experimental). No local CLI for tmux pane → Hands cannot match Mind harness. Treat **Grok as fleet Hand harness**: desktop Mind files tasking + reads panes; Grok Hands use normal Grok wake without tmux-resident Mind |
| Why desktop Mind | (1) **token budget** — deep/interactive Mind off product Hand harness; (2) **failure isolation** — tmux/shell death ≠ Mind death. Combine with remote Hands/Heads (`ssh-remote.md`). Expect learning/tweaks |
| Codex under desktop Mind | Only if Grok capacity exhausted — use doorbell-first Codex wake; reinit remains fallback |
| Heads | Still **Pi + GLM 5.2** regardless of Mind harness |
| Pi local Hand | Validated alternate for desktop-Mind when fully local + discrete/bounded units — see Pi-as-Hand |
| Capacity | Start at primaries, step models in `runtime_fallback` (do not flip product harness first) |

### Pi-as-Hand (local models)

Validated 2026-07-11 against `ornith-35b-q8` via local `llama-router` (`~/.pi/agent/models.json`), one-shot `--print` and persistent tmux TUI.

| Topic | Guidance |
| --- | --- |
| Scope | Discrete, well-specified units (write, run, self-verify). Not a Grok/Codex substitute for ambiguous / multi-step / long-context spine |
| Wake | Same doorbell as Grok: plain `pi` (no `--print`) idles in tmux; `send-keys … Enter` wakes; context retained; `/compact` works (errors only on too-small session) |
| Autonomy | No built-in agentic loop. Passive between wakes like Grok. Codex uses doorbell-first wake with reinit fallback |
| Slash surface | `/help` not recognized (goes to model as text). Do not assume Grok command parity beyond tested commands |
| cwd | Pin by true process cwd, not preceding shell `cd` in compound command. Prefer subshell or `tmux new-session -c <cwd>`. Verify on first use in new packet |
| Cost | Fully local, zero marginal API. Step back to Grok/Codex if unit needs real multi-step reasoning |

```bash
pi --provider llama-router --model ornith-35b-q8
pi --provider llama-router --model ornith-35b-q8 --print --no-session "<task>"
(cd /path/to/worktrees/<slug> && pi --provider llama-router --model ornith-35b-q8 …)
```

### Advisor plane (Heads — prefer Pi)

| Role | Harness | Preferred model | Effort / thinking |
| --- | --- | --- | --- |
| **head-ceo** / **head-cto** / **head-cxo** | **Pi** | GLM 5.2 | **high** or **xhigh** |

Advisors are largely one-shot (assign → report). Prefer Pi even when Mind is Grok or Codex.

```text
pi --provider zai --model glm-5.2 --thinking high   # or xhigh
```

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
