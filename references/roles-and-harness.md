# Roles, axes, and harness

Load when arming a fleet, rebinding runtimes, or clarifying Mind/Hand/Head duties.

## Roles

| Role | Typical identity | Job | Output |
| --- | --- | --- | --- |
| **Hand** | `hunter-1`…`hunter-N` (legacy: `codex`) | Take a **selected target** and finish it | Done tasks/needs + evidence; optional turn-end mail |
| **Mind** | `reviewer` | Survey product; fill tasking; review; integrate; fleet ops | Open tasks/needs; pane scan; wake/reinit; merge queue |
| **Strategist** (Head) | `strategist` | Ownership, sequencing, seams, gate honesty — not bag drain | Mail `strategist report:` To Mind |
| **Correctness** (Head) | `correctness` | Self-directed bug / fail-closed / invariant audit | Mail `correctness:` To Mind |
| **Purity** (Head) | `purity` | Self-directed unearned-complexity / excess-layer audit | Mail `purity:` To Mind |

One Mind owns the tasking bag and integration clock. Heads never merge, never keep product tasking “full,” and never stamp GO/NO-GO. They report To: Mind; Mind triages into hunter-N tasks/needs.

Prefer numbered hands (`hunter-N`) over a single shared `codex`. Prefer heterogeneous Head runtimes for second-party opinion; keep Hand harness aligned with Mind.

## Fleet axes (identity ≠ assignment ≠ runtime)

```text
hunter-N  =  identity (mail + tmux)
              ├── assignment   focus / packet / cwd / merge rights
              └── runtime      harness + model + wake/reinit policy
```

| Axis | Meaning | Sticky? |
| --- | --- | --- |
| **Identity** | Who owns bag + pane (`hunter-N`) | Session name while the slot exists |
| **Assignment** | What work that slot is on | Usually only hunter-1 main + merge rights. hunter-2+ assignments are transient |
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
- **Claude Code desktop as Mind is a declared exception to Harness alignment.** The desktop app has no local CLI for a tmux pane, so Hands cannot match Mind’s harness literally. Treat **Grok as the fleet’s one Hand harness** in this shape: desktop Mind files tasking and reads panes by hand; Grok Hands use normal Grok wake (`pointer doorbell`, `/compact`) without a tmux-resident Mind.
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
- **hunter-2+ after unit:** clean commit + tasking done + turn-end; do not invent main work or merge to main. Expect Mind to refill next map unit same cycle when the campaign still has work
- **hunter-2+ after theme ready-to-merge:** wait only for **integration** (Mind review → merge via hunter-1)
- **Don't get stuck:** classify dirt A/B/C; file needs same turn; **pivot** when one item blocks

## Mind does

- Find defects, missed work, Status lies, missing evidence
- File **targets** with where / done-when / evidence bar (**to the owning Hand**)
- **Own code review quality:** hands implement best-effort; Mind is the proactive reviewer (landed commits **and** in-flight WIP)
- Stay quiet when fingerprint unchanged, panes healthy, and no review signal
- Each wake: cheap **fleet pane scan** for liveness/errors; **Grok doorbell** or **Codex reinit** when idle/done with open targets
- Review finding → **task** to that Hand (finding + fix bar); **need** only for real decision/authority/input hold; **tmux pointer only** to that handle
- **Unstick half-dead dirt:** if same blocking paths age ≥2 cycles with no A/B/C class, open the diff; file claim/style/quarantine targets — do not restate “foreign dirty” forever

## Mind does not

- Issue stage start/closeout GO/NO-GO as binding protocol
- Require multi-round mail before the next map square
- Re-litigate completed units unless new residual targets appear
- Treat “no completion mail” alone as “still working” when the pane is idle or errored
- Steal the Hand’s unit or rewrite their WIP mid-flight (raise; don’t hijack unless operator asks)
- Treat status-only dirty as multi-cycle freeze without classification

## Heads do not

Approve/disapprove work, race Mind on acceptance, merge to main, or own product tasking. Strategist proposes sequencing/ownership; correctness and purity report defects/shape debt. Mind triages.
