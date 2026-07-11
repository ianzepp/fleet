# Roles, axes, and harness

Load when arming a fleet, rebinding runtimes, or clarifying Mind/Hand/Head duties.

## Roles

| Role | Typical identity | Job | Output |
| --- | --- | --- | --- |
| **Hand** | `hand-1`…`hand-N` (legacy: `hunter-N`, `codex`) | Take a **selected target** and finish it | Done tasks/needs + evidence; optional turn-end mail To `mind` |
| **Mind** | Board **`mind@…`** — **no tmux**; process = operator TUI | Survey product; **dole out** tasking; integrate; fleet ops; pick from strategist buckets; **track est vs actual cost**; file/present **operator mail** | Open tasks/needs; pane scan; wake/reinit; merge queue; `cost_calibration` |
| **Operator mail** | Board **`operator@…` only** — **no tmux** | Accrue human escalations (problems / blockers / guidance) while autonomous | Need/mail To human; presented on return — **not** status |
| **head-ceo** (Head) | `head-ceo` (legacy: head-strategist) | Vision, sequencing; **hand-2+ buckets with effort + est_tokens** | Mail `head-ceo report:` To `mind` |
| **head-cto** (Head) | `head-cto` (legacy: head-correctness) | **Code review / bug hunt on main after merge** | Mail `head-cto:` To `mind` |
| **head-cxo** (Head) | `head-cxo` (legacy: head-purity) | Self-directed complexity / purity audit (**not** operator voice) | Mail `head-cxo:` To `mind` |

One Mind owns the tasking bag and integration clock: **Mind files and wakes; Heads advise.** Heads never merge, never keep product tasking “full,” and never stamp GO/NO-GO. **head-strategist** proposes **what hand-2+ could work on** (side-lane bucket); Mind decides when to bind a packet and file. Reports To: **mind** (board); Mind triages into hand-N tasks/needs.

Prefer numbered hands (`hand-N`) over a single shared `codex`. Prefer heterogeneous Head runtimes for second-party opinion; keep Hand harness aligned with Mind.

## Fleet axes (identity ≠ assignment ≠ runtime)

```text
hand-N  =  identity (mail + tmux)
              ├── assignment   focus / packet / cwd / merge rights
              └── runtime      harness + model + wake/reinit policy
```

| Axis | Meaning | Sticky? |
| --- | --- | --- |
| **Identity** | Who owns bag + pane (`hand-N`) | Session name while the slot exists |
| **Assignment** | What work that slot is on | Usually only hand-1 main + merge rights. hand-2+ assignments are transient |
| **Runtime** | Harness + model + wake/reinit | Hand harness follows Mind. Model within harness may rebind. Heads may differ freely |

Product law talks in H-numbers + current assignment. Ops read runtime from fleet (`agent`, `agent_launch`) and apply wake/reinit by harness, not H-number. Live bindings belong in **project fleet config** (camp-local path — not a skill-mandated filename). Do not hardcode model strings into role tables as Hand identity.

## Harness alignment (Mind ↔ Hands vs Heads)

**Invariant — Hands share Mind’s harness.**
The Mind session’s agent harness is the product control plane. Every Hand should run that same harness family. Mixed Hand harnesses under one Mind create interoperability debt (wrong wake vs reinit, wrong bootstrap, wrong pane cues).

| Role | Harness policy | Model policy |
| --- | --- | --- |
| **Mind** | Source of truth for product harness | May change for capacity; Hands follow |
| **Hand** | **Same harness as Mind** by default | May differ within that harness (ladder) |
| **Head** | **Prefer a different harness and/or model** | Independence is a feature |

**Why Hands align:** Mind writes doorbells, reinit scripts, classify heuristics, and compact sequences for **one** product TUI.

**Why Heads diversify:** Heads challenge the product plane, not drain the bag. Different model (and preferably harness) reduces correlated blind spots. Default: **Pi + GLM 5.2 (high/xhigh)** — see Preferred models.

**Arm / rebind rules:**

1. On arm, set every Hand’s `agent` + `wake_mode` + reinit policy from Mind’s current harness (`mind.agent` / live Mind session).
2. If Mind changes harness, rebind Hands on the next clean breakpoint — do not leave a permanent mixed Hand fleet.
3. Capacity on a Hand: step the **same-harness** model ladder first. Do not flip Hand harness while Mind stays on the original unless operator records a temporary exception.
4. Capacity on Mind: prefer same-harness recovery; if Mind must move harness, either rebind Hands or park Hands and recover Mind first.
5. Heads are **out of** this rule. Rebind a Head only for its own capacity or operator preference.

**Anti-pattern:** “H3 is always Codex” / “language spine is always Grok” as product law. Harness is ops binding from Mind, not permanent Hand identity. Assignment stays independent of harness.

## Preferred models by role

Default arm preferences. Live ids live in project fleet config (`agent_model`, `agent_launch`, effort flags). Capacity ladders step same-harness; they do not invent permanent Hand identity from model strings.

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

Notes:

- Under **Grok**, Mind and Hand share the same model class (Grok 4.5) and harness.
- Under **Codex**, Mind and Hand may differ within the family (sol/medium vs luna/xhigh); harness stays Codex.
- **Claude Code desktop as Mind is a declared exception to Harness alignment** (and an **experimental** control-plane shape). The desktop app has no local CLI for a tmux pane, so Hands cannot match Mind’s harness literally. Treat **Grok as the fleet’s one Hand harness** in this shape: desktop Mind files tasking and reads panes by hand; Grok Hands use normal Grok wake without a tmux-resident Mind.
- **Why desktop Mind exists (experiment):** (1) **token budget** — keep deep or interactive Mind work off the product Hand harness; (2) **failure isolation** — local tmux/shell death should not take Mind; Mind death should not take Hands. Combine with **remote Hands/Heads** (`ssh-remote.md`) for further isolation. Expect learning and camp-specific tweaks.
- Reserve **Codex** under desktop Mind only if Grok capacity is exhausted — reinit-after-unit assumes a scriptable Mind loop; a human Mind can do it but with more toil.
- Heads still default to **Pi + GLM 5.2** regardless of Mind harness.
- **Pi against local `llama-router` (`ornith-35b-q8`)** is a validated alternate Hand for desktop-Mind when work must stay fully local and units are discrete/bounded — see **Pi-as-Hand** below.
- Capacity ladders start at these primaries, then step models in fleet `runtime_fallback` (do not flip product harness first).

### Pi-as-Hand (local models)

Validated 2026-07-11 against `ornith-35b-q8` via local `llama-router` (`~/.pi/agent/models.json`), one-shot `--print` and persistent tmux TUI.

| Topic | Guidance |
| --- | --- |
| Scope | Capable on discrete, well-specified units (write, run, self-verify). Not a Grok/Codex substitute for ambiguous, multi-step, or long-context spine work. |
| Wake | Same doorbell pattern as Grok: plain `pi` (no `--print`) idles in tmux; `tmux send-keys … Enter` wakes; context retained across wakes; `/compact` works (errors only on too-small session). |
| Autonomy | No built-in agentic loop or reinit-after-unit. Passive between wakes like Grok. Codex alone has after-unit reinit. |
| Slash surface | `/help` is not recognized (goes to model as text). Do not assume Grok command parity beyond tested commands. |
| cwd | Pin by true process cwd, not a preceding shell `cd` in a compound command. Prefer subshell or `tmux new-session -c <cwd>`. Verify on first use in a new packet (`pwd` + relative marker file). |
| Cost | Fully local, zero marginal API cost. Step back to Grok/Codex if a unit needs real multi-step reasoning. |

```bash
# persistent Hand pane (preferred)
pi --provider llama-router --model ornith-35b-q8

# one-shot (no session retained)
pi --provider llama-router --model ornith-35b-q8 --print --no-session "<task>"

# cwd-safe launch
(cd /path/to/worktrees/<slug> && pi --provider llama-router --model ornith-35b-q8 …)
```

### Advisor plane (Heads — prefer Pi)

| Role | Harness | Preferred model | Effort / thinking |
| --- | --- | --- | --- |
| **Strategist** | **Pi** | GLM 5.2 | **high** or **xhigh** |
| **Correctness** | **Pi** | GLM 5.2 | **high** or **xhigh** |
| **Purity** | **Pi** | GLM 5.2 | **high** or **xhigh** |

Advisors are largely one-shot (assign → report). Pi fits that better than a long product TUI. Product Hands stay on Mind’s harness for continuous bag drain.

```text
pi --provider zai --model glm-5.2 --thinking high   # or xhigh
```

Heads need not match Mind’s product harness. Prefer Pi even when Mind is Grok or Codex.

## Hand does

- Cheap intake; `show` only the chosen handle
- Drain open tasks/needs for **its** identity; validate; mark done with evidence
- Advance campaign/docs Status when stage criteria hold and residuals for that stage are empty (Status must not overclaim — e.g. static checks ≠ GPU product run)
- **After a product unit lands:** run **`$polish`** on **changed source files from this unit only** — see main skill **End-of-unit polish**
- Exit when tasking empty for focus **and** map has no next package (or operator pause) — not when a Mind stamp is missing
- Clean turn end: mark done; send turn-end / **ready-to-merge** mail when useful
- **hand-2+ after unit:** clean commit + tasking done + turn-end; do not invent main work or merge to main. Expect Mind to refill next map unit same cycle when the campaign still has work
- **hand-2+ after theme ready-to-merge:** wait only for **integration** (Mind review → merge via hand-1)
- **Don't get stuck:** classify dirt A/B/C; file needs same turn; **pivot** when one item blocks

## Mind does

- **Is the operator entry point:** the conversation the human is in **is** Mind (not a `reviewer` Hand, not a second ops pane; board mail is `mind@…` + **`operator@…`** — no tmux for either)
- Resolve **interaction mode** each cycle (`turns_since_operator_message`, `mind_mode`, `FLEET_CYCLE` /loop) — see main skill + `mind-cycle.md`
- Find missed work, Status overclaims, missing evidence; file **targets** with where / done-when / evidence bar (**to the owning Hand**)
- **Integration absorb/accept** — bookkeeping and “good enough to merge/queue,” not deep peer code review of every packet
- Stay quiet when fingerprint unchanged, panes healthy, and no ops signal
- Each wake: cheap **fleet pane scan**; **Grok doorbell** or **Codex reinit** (prefer `scripts/codex-reinit.sh`) when idle/done with open targets
- Residual finding → **task** to Hand; agent decision hold → **need**; **human** wall / problem / blocker / bug-guidance → **`operator@`** (see `operator-mail.md`); **tmux pointer only**
- **Post-main polish advisory:** when main HEAD moves, run `$polish` `suggest-polish-files.py` (JSON, capped); if scores ≥ camp threshold, file a bounded polish **task** — Mind does not execute the polish loop
- **Major-inflection housekeeping:** only at campaign end / large multi-theme merge / stage closeout / operator ask — file **one** `$housekeeping` **task** To hand-1; never after routine lands
- **Capacity packing:** when picking from strategist side-lane buckets, use `effort` / `est_tokens` (and recent `cost_calibration` deltas) so free Hands take appropriate-sized work while spine Hands are long-running
- **Cost calibration:** on Hand done for a bound candidate, record actual tokens (harness if available, else Mind ballpark) vs strategist estimate; keep a short delta history
- **Unstick half-dead dirt:** open the diff; class A mechanical (fmt) → clear same turn; do not freeze for hours
- **Autonomous:** thin ops; **decide now** on reversible defaults; head-strategist is optional structure help, not a permission gate; file **operator mail** when human needed
- **Interactive:** full reasoning for operator; **rich FLEET_CYCLE reports** (not one-liners); maintain **operator_recap**; **present open operator@ list** on engagement
- **Autonomous:** compact cycle reports (one-line quiet / short acted; optional `+op-mail:N`)
- Keep operator recap buffer since `last_operator_message_at`

## Mind does not

- Issue stage start/closeout GO/NO-GO as binding protocol
- Require multi-round mail before the next map square
- **Own fleet code-review quality** (that is **head-cto on main after merge**)
- Run full `$polish` or `$housekeeping` itself; thrash polish every quiet cycle; fire housekeeping on routine main lands
- Steal the Hand’s unit or rewrite their WIP mid-flight (raise; don’t hijack unless operator asks)
- Treat status-only dirty as multi-cycle freeze without classification
- Require introspecting its own model/reasoning tier to choose behavior
- Treat Hand/Head board mail or a **FLEET_CYCLE-only** payload as operator engagement (human chat *between* fires still counts)
- Wait multiple cycles on head-ceo for a decision it can make with a default
- Treat strong guidance as a hard ban that freezes progress
- Run as a dedicated **`reviewer` / gatherer** mail+tmux identity (retired)
- Create tmux for **`mind`** or **`operator`** (board inboxes only)
- File status / absorbs / “still running” To **`operator@`**

## head-cto does (Head)

- Prefer **main checkout** as the review surface after themes/units land on main
- Self-directed bug / fail-closed / invariant audit; report `head-cto:` / `head-correctness:` To Mind
- File or recommend **tasks** for implementable defects (Mind triages to owning Hand)
- Do **not** try to juggle every packet worktree as the primary continuous review surface
- Do **not** act as merge GO/NO-GO; build-fast means some bugs reach main and get fixed there

## Heads do not

Approve/disapprove work as a gate, race Mind on acceptance, merge to main, or own product tasking. **head-ceo** proposes sequencing/ownership and **side-lane (hand-2+) candidate buckets**; **head-cto** reviews main; **head-cxo** reports shape debt. Mind triages into the bag and coordinates live Hands.
