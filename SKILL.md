---
name: fleet
description: Multi-agent fleet management with Mind/Head/Hand roles (Abbot pattern) — Mind (ops) fills tasking, Hands (workers) clear work, Heads (advisors) research; Hands share Mind harness, Heads prefer alternate models/harnesses; dual-channel Vivi+tmux, multi-lane integration, runtime fallback, wind-down. Use for hunter-N fleets, codex reinit, keep-screen-moving, don't-get-stuck, long unattended Mind cycles.
---

# Fleet

**Roles follow Abbot’s Mind / Head / Hand pattern** (see `~/work/ianzepp/abbot/README.md`:
agent layer as roles running under one control plane). This skill applies that
pattern to a **multi-session fleet** (mail board + tmux panes), not to Abbot’s
in-process kernel.

| Role | Job | Typical callsign |
| --- | --- | --- |
| **Mind** | Ops / control loop: tasking, review, integrate, pane ops, cycle cadence | `reviewer` |
| **Head** | Advisory cognition: strategist, correctness, purity — research and reports, not bag drain | same as role name |
| **Hand** | Execution: take one open target, implement, validate, mark done | `hunter-1`…`hunter-N` (or other worker ids) |

Callsigns (`hunter-N`, `reviewer`) are **mail/tmux identities**. Skill vocabulary
is Mind / Head / Hand.

**Evolution:** formerly `$hunter-gatherer` (pair review → bag loop → multi-lane
tmux). Canonical skill name is **`$fleet`**.

**Invariant:** Mind fills the tasking bag; Hand empties the tasking bag. Progress
is **open tasking + campaign/map**, not approval stamps.

**Keep the screen moving:** empty tasking while the map still has unblocked next
work is **starvation**, not success. Operational pause is the exception.

**Don't get stuck:** freeze is the failure mode. Name why, get unstuck — never
status-only “blocked” for cycles without evidence.

**Harness alignment:** Hands run the **same agent harness as Mind** (ops
interoperability). Heads **prefer alternate harnesses/models** (second-party
opinion).

```text
campaign / focus map
        │
        ▼
   MIND ──files targets──► tasking bag (open tasks / needs)
        ▲                           │
        │                           ▼
        └──── residuals ────── HAND clears selected target
                 ▲
                 │ dual channel
        Vivi (truth of work) + tmux (truth of process)

   Heads (strategist / correctness / purity) ──mail To: Mind──► triage into tasking
```

## When To Use

- Project-local multi-agent loops (often Vivi mailspace identities)
- Factory/campaign work with a residual finder and an implementer
- Long recurring agent wakes (5–10m) that must **fail fast** when idle
- Reframing “reviewer approval” into residual tasks instead of stage licenses
- Fleet of Hand sessions bound to tmux panes (liveness + doorbell)

Do not use this skill for ordinary personal IMAP email (use `$mail`). Do not use
it to invent a second acceptance gate.

## Don't get stuck (universal law)

**Basic rule:** do not freeze. Progress on a second-best target beats zero
progress while “waiting.” Internal hesitation is not a board event — other
agents and the operator only see Vivi, commits, and the pane.

### When stuck — same turn

```text
1. Name it     path / handle / dirt / pane class / missing decision
2. Why         unsent decision · unclassified dirt · integration lag ·
               topic monogamy · dead process · capacity · real upstream wall
3. Unstick     match the class below — do not only restate “blocked”
4. Pivot       if one item stays blocked, work other open tasking/map targets NOW
```

| Stuck class | Unstick (do) | Don't |
| --- | --- | --- |
| Decision / name / scope / stop condition | File **need or mail** same turn with **default + options**; keep working or pivot | Silent wait for confirmation never sent |
| One tasking item awkward / deferred | Externalize if needed → **switch targets** | Topic monogamy while other targets exist |
| Uncommitted dirt on a path you need | **Open the diff** → classify A/B/C (below) → act | Status-only “foreign dirty → leave forever” |
| Integration lag (fix not on pin/main) | Queue merge / base-update / pin-refresh; pivot product | Thrash re-verify on correctly blocked consumer |
| Pane dead / capacity / stuck idle + open tasking | Wake / reinit / runtime fallback by fleet | Stack wakes; hope without ops |
| Hard human-only wall | Need filed + pivot other targets | Silent stall of the whole session |

**Only sleep** when the actionable bag for the focus is empty **and** the map
has no next unblocked unit — not because one item is awkward.

**Forbidden:** sitting idle for confirmation never filed; treating filename
uncertainty as a hard stop; parking the session on one uncertain item while
other open tasking items remain; assuming Mind/operator will poll private
monologue; repeating “dirty / blocked” across cycles without new evidence.

### Half-dead targets (dirt that rots)

Uncommitted changes that **block** a selected unit are **half-dead targets**, not
a permanent stop sign. They rot if status-only sensors keep saying “dirty” while
no agent opens the diff.

**Invariant:** “foreign dirty” means **do not erase**. It does **not** mean
“never look, never classify, freeze the spine for hours.”

| Class | What it usually is | Same-turn action |
| --- | --- | --- |
| **A — mechanical** | Formatter / pure layout after `git diff` (no semantic intent) | Style-commit in scope, or include with related work per formatter law. Not live multi-agent WIP. |
| **B — intentional other** | Another agent’s semantic WIP, docs/factory goals, deliberate partial | Work around, narrow scope, worktree, or escalate via Vivi. **Do not erase.** Record owner/guess + age. |
| **C — mixed** | Some hunks yours, some not | Stage/commit **only own safe hunks** when possible; leave the rest; continue other targets. |

**How to classify (cheap, mandatory before multi-cycle freeze):**

```text
git status -sb
git diff -- <path>          # or git diff -U0 for size
# optional: git log -1 -- <path>  and file mtime vs last commit
# pure whitespace/layout after a landed commit → usually class A
# real logic/docs mid-edit by another pane → class B
```

| Role | Dirt duty |
| --- | --- |
| **Hand** | Classify A/B/C before abandoning a unit for dirt. A → clear or style-commit. B → need/mail + **pivot**. C → own hunks only. Never destructive cleanup of B. |
| **Mind** | If the **same paths** block spine/packet for **≥2 cycles** with no classification in baseline/mail → **paid path: open the diff**, note class, file claim/quarantine need or style residual. Track `half_dead` age; escalate, don’t restate. |
| **Either** | Second-best map targets while dirt is B-held is success. Zero commits “waiting on dirt” while other targets exist is failure. |

Formatter law (global Agents.md) still applies: after inspect, formatter output is
intentional change to commit, not noise to freeze on.

## Roles

| Role | Typical identity | Job | Output |
| --- | --- | --- | --- |
| **Hand** | `hunter-1`, `hunter-2`, … (legacy: `codex`) | Take a **selected target** and finish it | Done tasks/needs + evidence; optional turn-end mail |
| **Mind** | `reviewer` | Survey product, docs, harnesses, claims; fill tasking; review; integrate; fleet ops | Open tasks/needs; pane scan; wake/reinit; merge queue |
| **Strategist** (optional advisor) | `strategist` | Ownership, sequencing, seams, gate honesty — **not** tasking drain | Mail `strategist report:` To Mind |
| **Correctness** (optional advisor) | `correctness` | Self-directed bug / fail-closed / invariant audit | Mail `correctness:` To Mind |
| **Purity** (optional advisor) | `purity` | Self-directed unearned-complexity / excess-layer audit (pragmatic) | Mail `purity:` To Mind |

Names are local labels. The **jobs** matter.

**One Mind owns the tasking bag and integration clock.** Heads **never** merge,
never keep product tasking “full,” and never stamp GO/NO-GO. They report To: Mind; Mind triages into hunter-N tasks/needs when actionable.

Prefer numbered hands (`hunter-N`) over a single shared `codex` when more than
one implementer process may run. Prefer **heterogeneous Head runtimes** for
second-party opinion; keep **Hand harness aligned with Mind** — see
**Harness alignment** and **Fleet axes**.

### Fleet axes (identity ≠ assignment ≠ runtime)

Hands are **slots**, not permanent job titles. Keep three bindings separate:

```text
hunter-N  =  identity (mail + tmux)
              ├── assignment   focus / packet / cwd / merge rights
              └── runtime      harness + model + wake/reinit policy
```

| Axis | Meaning | Sticky by pattern? |
| --- | --- | --- |
| **Identity** | Who owns bag + pane (`hunter-N`) | Session name while the slot exists |
| **Assignment** | What work that slot is on | **Usually only hunter-1 main + merge rights.** hunter-2+ assignments are **transient** (rehome when the map moves) |
| **Runtime** | Harness (grok/codex/pi/…) + model + wake/reinit policy | **Hand harness follows Mind** (below). Model within harness may rebind for capacity. Heads may differ freely. |

**Product law** talks in H-numbers + current assignment. **Ops** read runtime from
fleet (`agent`, `agent_launch`) and apply wake/reinit by harness, not by H-number.
Do not hardcode model strings into role tables as if they were Hand identity.
Live bindings belong in the **project fleet config** (path chosen by the camp
overlay — not a skill-mandated filename).

### Harness alignment (Mind ↔ Hands vs Heads)

**Invariant — Hands share Mind’s harness.**
The Mind session’s agent harness (`grok` / `codex` / …) is the **product control
plane**. Every Hand should run that **same harness family**. Grok knows how Grok
works; Codex knows how Codex works. Mixed Hand harnesses under one Mind create
interoperability debt: wrong wake vs reinit policy, wrong bootstrap shape, wrong
pane-class cues, and Mind ops that thrash the “other” TUI.

| Role | Harness policy | Model policy |
| --- | --- | --- |
| **Mind** | Source of truth for product harness | May change for capacity; Hands follow |
| **Hand** | **Same harness as Mind** by default | May differ within that harness (ladder) for capacity |
| **Head** (strategist / correctness / purity) | **Prefer a different harness and/or model** | Independence is a feature — second-party opinion |

**Why Hands align:** Mind writes doorbells, reinit scripts, classify heuristics, and
compact/theme-switch sequences for **one** product TUI. A Hand on another harness
is a second ops surface the Mind must keep correct under load.

**Why Heads diversify:** Heads exist to challenge the product plane, not to drain
the bag. A different model (and preferably a different harness) reduces correlated
blind spots. **Default: Pi + GLM 5.2 (high/xhigh)** for all Heads — see
**Preferred models by role**. One-shot assign→report fits Pi; continuous bag drain
stays on Mind’s product harness.

**Arm / rebind rules:**

1. On fleet arm, set every Hand’s `agent` + `wake_mode` + reinit policy from
   **Mind’s current harness** (fleet field e.g. `mind.agent` / gatherer runtime,
   or the live Mind session if fleet has not recorded it yet).
2. If Mind **changes harness** (operator or hard recovery), **rebind Hands** to
   that harness on the next clean breakpoint — do not leave a permanent mixed
   Hand fleet under the new Mind.
3. Capacity pressure on a Hand: step the **same-harness model ladder first**.
   Do **not** flip a Hand to another harness while Mind remains on the original
   unless the operator explicitly accepts a temporary exception (record in
   baseline; plan re-align).
4. Capacity pressure on Mind: prefer same-harness recovery; if Mind must move
   harness temporarily, either (a) rebind Hands to match, or (b) park Hands and
   recover Mind first — do not run a long dual-harness product plane “by accident.”
5. Heads are **out of** this alignment rule. Do not rebind Heads when Mind
   rebinds; rebind a Head only for its own capacity or operator preference.

**Anti-pattern:** “H3 is always Codex” / “language spine is always Grok” as
**product law**. Harness is ops binding derived from Mind, not a permanent
Hand identity. Assignment (main vs packet) stays independent of harness.

### Preferred models by role

These are **default arm preferences** for this operator’s fleet. Live ids still
belong in the **project fleet config** (`agent_model`, `agent_launch`,
effort/thinking flags). Capacity fallbacks step a same-harness ladder; they do
not invent a permanent Hand identity from model strings.

#### Product plane (Mind + Hands — one harness family)

| Product harness | Role | Preferred model | Effort / thinking |
| --- | --- | --- | --- |
| **Grok** | **Mind** | Grok 4.5 | harness default |
| **Grok** | **Hand** | Grok 4.5 | harness default |
| **Codex** | **Mind** | `gpt-5.6-sol` | **medium** |
| **Codex** | **Hand** | `gpt-5.6-luna` | **xhigh** |

Notes:

- Under **Grok**, Mind and Hand share the **same** model class (Grok 4.5) as well
  as the same harness — simpler ops and consistent review/implement dialect.
- Under **Codex**, Mind and Hand may differ **within** the family: sol/medium for
  Mind’s control-loop work; luna/xhigh for Hands’ implementation throughput.
  Harness stays Codex for both (**Harness alignment**).
- Ladders for capacity start at these primaries, then step to other same-harness
  models listed in fleet `runtime_fallback` (do not flip product harness first).

#### Advisor plane (Heads — prefer Pi entirely)

| Role | Harness | Preferred model | Effort / thinking |
| --- | --- | --- | --- |
| **Strategist** | **Pi** (preferred) | GLM 5.2 | **high** or **xhigh** |
| **Correctness** | **Pi** (preferred) | GLM 5.2 | **high** or **xhigh** |
| **Purity** | **Pi** (preferred) | GLM 5.2 | **high** or **xhigh** |

**Why Pi for Heads:** advisors are largely **one-shot** — Mind assigns a question,
the Head churns, returns a report, and is done (strategist: clean-slate reinit
per assign). Pi fits that assign→answer loop better than a long product TUI
session. Product Hands stay on Mind’s harness for continuous bag drain.

Default Head launch shape (ids may move; read fleet when launching):

```text
pi --provider zai --model glm-5.2 --thinking high   # or xhigh
```

Heads are **not** required to match Mind’s product harness. Prefer Pi even when
Mind is Grok or Codex.

### Hand does

- Cheap intake; `show` only the chosen handle
- Drain open tasks/needs for **its** identity; validate; mark done with evidence
- Advance campaign/docs Status when stage criteria hold and residuals for that
  stage are empty (Status must not overclaim — e.g. static checks ≠ GPU product run)
- **After a product unit lands** (especially small iterative units): run **`$polish`**
  on the **changed source files from this unit only** — see **End-of-unit polish**
- Exit when tasking empty for focus **and** map has no next package (or operator
  pause)—not when a Mind stamp is missing
- When a turn finishes cleanly: mark done on the tasking bag; send turn-end / **ready-to-merge**
  mail when useful (see templates below)
- **hunter-2+ after unit:** clean commit + tasking done + turn-end; **do not** invent
  main work or merge to main. Expect Mind to **refill next map unit** same cycle
  when the campaign still has work — not permanent idle.
- **hunter-2+ after theme ready-to-merge:** wait only for **integration** (Mind
  review → merge via hunter-1). That wait is operational, not “tasking empty = success.”
- **Don't get stuck:** classify dirt A/B/C; file needs same turn; **pivot** when
  one item blocks — see **Don't get stuck**

### Mind does

- Find defects, missed work, Status lies, missing evidence
- File **targets** with where / done-when / evidence bar (**to the owning Hand**)
- **Own code review quality** for the fleet: hands implement best-effort;
  Mind is the proactive reviewer (landed commits **and** in-flight WIP)
- Stay quiet when fingerprint unchanged, panes healthy, and no review signal
- On each wake: cheap **fleet pane scan** (tmux) for liveness/errors; **Grok
  doorbell** or **Codex reinit** when idle/done with open targets
- When review finds a §§REDMIND§§: file a concrete **task** to that Hand with
  finding + fix bar; use a **need** only for a real decision/authority/input
  hold; **tmux pointer only** to that handle (no essay in pane)
- **Unstick half-dead dirt:** if the same blocking paths age across cycles with
  no class A/B/C evidence, **open the diff** on paid path; file claim/style/
  quarantine targets — do not restate “foreign dirty” forever

### Mind does not

- Issue stage start/closeout GO/NO-GO as binding protocol
- Require multi-round mail before the next map square
- Re-litigate completed units unless new residual targets appear
- Treat “no completion mail” alone as “still working” when the pane is idle or errored
- Steal the Hand’s unit or rewrite their WIP mid-flight (raise; don’t hijack
  unless operator asks)
- Treat status-only dirty as a multi-cycle freeze without classification


### Heads do not

Approve/disapprove work, race the Mind on acceptance, merge to main, or own
product tasking. Strategist proposes sequencing/ownership; correctness and purity
report defects/shape debt. Mind triages.

## The tasking bag

Prefer a project coordination board (commonly Vivi project mailspace—see
`$mail` for CLI). Kinds:

| Kind | Meaning |
| --- | --- |
| **task** | Implementable work with a done condition, including defects and merge blockers |
| **need** | Decision, authority, or missing external input that can change the work |
| **want** | Non-blocking polish or later idea |
| **mail** | Deliberation/status—not the primary queue |

**Work signal:** open tasks + open needs for the Hand = actionable work.
Wants and unread mail are secondary.

### Queue kind is not severity

Choose the queue kind by **what response is required**, then state severity in
the subject/body or priority metadata. Never encode severity by turning an
implementable defect into a `need`.

| Question | Route |
| --- | --- |
| Can the owner implement this now from the stated invariant and done-when? | **task** — even when critical, safety-sensitive, or merge-blocking |
| Must someone choose a path, grant authority, supply input, or resolve an external dependency first? | **need** — include default + options; pivot while waiting |
| Is it safe to ship/merge without this improvement? | **want** |
| Is no action requested? | **mail** |

Put urgency on the item, not in its kind: for example, `merge blocker: …`,
`critical: …`, or the board's priority field. A needs-only bag may intentionally
be treated by automation as a decision hold; misfiling defects there can leave a
healthy Hand idle even though the work is implementable.

When a need is answered, close or reply to the decision item and file the
resulting implementation as a **task** to its owner. Do not leave concrete work
hidden inside a resolved need. During iterative review, consolidate findings
from the same root cause and acceptance gate into one bounded task when they
share owner and validation. Split items when ownership, invariant, or done-when
is genuinely independent—not for every newly failing test.

### Tasking rules (replace gates)

| Old gate language | Prefer |
| --- | --- |
| stage closeout GO/NO-GO | tasking empty of stage residuals; Status reflects reality |
| “NO-GO next stage” | next stage not selected / no package—file charting work or leave planned |
| dual approval thrash | one tasking bag; Hand drains; Mind refills |

Hard stop for hunter: open tasks/needs for the current hunt.  
Not a hard stop: missing Mind congratulations or “GO” mail.

### Multi-hand bags

- File targets **to a specific hunter** (`To: hunter-1`), not broadcast.
- One handle has one owner. Do not put the same P1 on two hands.
- Partition by focus (campaign track, repo, or package) when possible.
- Legacy single identity (`codex`) may remain readable during migration; **new**
  targets go to `hunter-N`.

### Fleet priorities (main vs packet)

| Slot | Workspace role | Merge to main? |
| --- | --- | --- |
| **hunter-1** | **Main checkout** (sticky workspace role — not sticky model) | **Yes** — only hunter-1 merges packet branches into main (when Mind assigns it) |
| **hunter-2+** | **Dynamically assigned** — usually worktree packets (`worktrees/<slug>/…`); rehome when reassigned | **Never** — commits on packet branch; unit done → refill; theme → ready-to-merge |

Rules:

1. File the campaign spine to hunter-1. Assign hunter-2+ to operator-created
   worktree packets for bounded work; never put unbounded spine work there.
   Packet↔hunter bindings are **current assignment**, not permanent types.
2. Hunter-1 should run while its map has packages or residuals. Idle + empty is
   a starvation signal: refill targets, queue a merge, and wake/reinit by **H1’s
   current runtime**. Quiet only when the map and residual bag are both empty.
3. Hunter-2+ never merge/rebase/delete packet worktrees or invent main work.
   After a **unit**: mark done + turn-end; Mind refills next map unit
   for that assignment (or reassigns the slot). After a **theme** boundary:
   ready-to-merge mail; Mind owns merge clock.
4. Mind absorbs unit lands without merging; at theme accept creates
   `pending_merges` + merge task for hunter-1.
5. At a clean breakpoint, wake/reinit hunter-1 for merge; defer while main is
   mid-phase or dirty. Merge work checks watch-scope drift, green-gate, and is
   absorbed then accepted as a separate step.
6. **Runtime vs assignment:** assignment (main vs packet) is orthogonal to
   **model** within a harness. **Hand harness is not free** — it follows Mind
   (**Harness alignment**). Rebind model/launch without renaming the Hand or
   moving the assignment; rebind Hand harness only when Mind’s harness changes
   or the operator records an exception.

#### Idle empty taskings (keep the screen moving)

| Situation | Meaning | Mind action |
| --- | --- | --- |
| **Any hunter-N** idle + empty tasking + map has **unblocked** next unit | **Starvation** | File next target **same cycle** + wake/reinit |
| **hunter-1** idle + empty + `pending_merges` or spine residuals | Starvation | Merge task and/or next spine targets |
| **hunter-2+** just finished a **unit** (not theme) | Not success-idle | Absorb/review; **refill** next packet unit |
| **hunter-2+** after **theme** ready-to-merge, tasking empty, waiting merge | **Operational pause** | Review → accept → merge to h1; optional light pivot unit if map has unrelated work |
| **Operational pause only** | Allowed empty/hold | base-update wait · mid-unit · operator pause · map empty · hard upstream with need filed (prefer pivot if one exists) |
| Head (strategist/correctness/purity) “empty tasking” | N/A — no product tasking | Scan mail; soft-wake only if stuck; never map-refill |

Do not sleep merely because all **product** bags are empty; check the map,
`pending_reviews`, and `pending_merges` first.

## Dual channel: Vivi + tmux

Vivi is the **board of record** (what work exists and is done).  
tmux is the **process layer** (whether the Hand process is alive, idle, or broken).

```text
                    ┌──────────────────────────┐
  product done ──►  │ Vivi: task/need done +   │  truth of work
                    │ optional turn-end mail   │
                    └──────────────────────────┘

                    ┌──────────────────────────┐
  every Mind    │ tmux capture-pane per    │  truth of process
  wake (cheap) ──►  │ hunter-N session         │
                    └──────────────────────────┘
```

| Concern | Prefer |
| --- | --- |
| “This unit is done; evidence is …” | Vivi tasking done (+ optional mail) |
| “Grok idle at prompt with open tasking” | tmux → **pointer doorbell** |
| “Codex done/idle at `›` with open tasking” | tmux → **reinit** (kill + fresh session + short bootstrap) — not stacked wakes |
| “Over capacity / connection failed / hung Waiting” | tmux → ops intervene (model change, retry, restart) |
| “No mail and no pane signal” | do not invent progress; sleep or escalate if bag stale |
| “Fix landed upstream; consumer still red” | Check **pin-relative done** before re-verify doorbell |

**Do not rely on completion mail alone.** Model overcapacity, disconnects, and
crashes prevent the Hand from sending mail. Mind must still see the pane.

**Do not treat idle pane alone as “done.”** Idle + empty tasking may be quiet; idle +
open tasking is a wake signal; idle after HEAD move without done-handles still needs
bag/Status honesty on thorough cycles.

### Binding rule

**Mail identity token == tmux session name.**

| Mail | tmux session | Typical pane target |
| --- | --- | --- |
| `hunter-1@…` | `hunter-1` | `hunter-1` or `hunter-1:1.1` (respect window base-index) |
| `hunter-2@…` | `hunter-2` | `hunter-2` |

Put the map in **project fleet config** (path is camp-local; do not hard-require
a skill-owned filename). Example shape:

```json
{
  "version": 1,
  "default_hunter": "hunter-1",
  "legacy_hunter_identity": "codex",
  "gatherer_identity": "reviewer",
  "mind": { "agent": "grok", "note": "Hands inherit this harness family" },
  "agent_policy": {
    "hands_follow_mind_harness": true,
    "heads_prefer_pi": true,
    "codex_reinit_after_kill": true
  },
  "preferred_models": {
    "grok": { "mind": "grok-4.5", "hand": "grok-4.5" },
    "codex": {
      "mind": { "model": "gpt-5.6-sol", "effort": "medium" },
      "hand": { "model": "gpt-5.6-luna", "effort": "xhigh" }
    },
    "head": { "agent": "pi", "model": "glm-5.2", "thinking": "high|xhigh" }
  },
  "hunters": {
    "hunter-1": {
      "mail_identity": "hunter-1",
      "tmux_session": "hunter-1",
      "tmux_target": "hunter-1:1.1",
      "cwd": "/path/to/project",
      "agent": "grok",
      "merges_to_main": true,
      "wake_enabled": true,
      "wake_mode": "tmux_send_keys",
      "min_seconds_between_wakes": 180
    },
    "hunter-3": {
      "mail_identity": "hunter-3",
      "tmux_session": "hunter-3",
      "agent": "grok",
      "wake_mode": "tmux_send_keys",
      "merges_to_main": false
    }
  },
  "strategist": { "mail_identity": "strategist", "agent": "pi" },
  "correctness": { "mail_identity": "correctness", "agent": "pi", "self_directed": true },
  "purity": { "mail_identity": "purity", "agent": "pi", "self_directed": true },
  "binding_rule": "mail_identity == tmux_session token"
}
```

Camp-specific durable law may live in a Mind/scheduler overlay prompt or
project `Agents.md` — treat that as an **overlay** on this skill when present.

Arm: `vivi mailspace identity add hunter-1 --project <root>` and
`tmux new-session -d -s hunter-1 -c <cwd>` (then start the agent).

### Pane scan (Mind, every cycle — keep cheap)

For each fleet hunter:

```text
1. tmux has-session -t <tmux_session>   → down | up
2. if up: tmux capture-pane -t <tmux_target> -p -S -80  (history for ops)
3. classify primarily on the **last ~15–25 lines** (avoid false
   `running` from earlier “Thought for” / completed-turn chrome in scrollback)
4. store last_pane_class + short fingerprint in baseline
```

| Class | Example pane cues | Mind action |
| --- | --- | --- |
| `down` | no session | recreate session + agent; Codex: reinit with bootstrap |
| `running` | current `Waiting for response` / live spinner / Codex streaming | sleep (do not wake/reinit) |
| `idle_prompt` | Grok `❯` ready; Codex `›` ready without finished-turn monologue | **Grok:** doorbell if open tasking. **Codex:** if open tasking, prefer **reinit** if session looks finished or stale |
| `done_idle` | Codex turn-end / “tasking empty” / “standing by” monologue then `›` | **Codex reinit** if open tasking or just filed targets; else refill or pause |
| `error_capacity` | over capacity, rate limit, 429 | ops: model change / retry / reinit |
| `error_connection` | connection failed, timeout, ECONNRESET | ops: retry / restart resume |
| `unknown` | unreadable TUI noise | record sample; do not thrash |

Grok TUI note: the prompt may show placeholder copy (“Build anything”) while idle.
Do not treat that as an in-flight user message. Prefer `Waiting for response` as the
only hard `running` signal unless a live spinner is visible in the **tail**.

Codex note: a `•` monologue followed by `›` is often an **answer that stopped**, not
a wait for the next tasking item. Stacking `HAND WAKE` lines is the failure mode.

Rate-limit wakes and ops interventions (`min_seconds_between_wakes`). Never
`send-keys` into `running` unless operator policy explicitly allows cancel+replace.

### Grok vs Codex (agent runtimes — keyed on fleet `agent`, not H-number)

Wake/reinit **behavior** is keyed on the pane’s `agent` harness. Under
**Harness alignment**, product Hands should all share **Mind’s** harness, so the
fleet usually runs **one** of these columns for Mind + Hands. Heads may use the
other column (or pi / another harness) on purpose.

| | **Grok** (`agent=grok`) | **Codex** (`agent=codex`) |
| --- | --- | --- |
| After unit + open tasking | Pointer **doorbell** | **Reinit** (kill process + fresh session + short bootstrap) |
| Theme switch same cwd | `/compact` then pointer | **Reinit** (do not rely on compact+wake) |
| Launch | Prefer plain `grok …` (not fragile `exec` if bad flags leave pane dead) | Plain `codex …` via fleet `agent_launch` — **never `exec codex`** (can drop the tmux session when process exits) |
| Bootstrap | Pointer: identity, handle, `vivi --for` | Same **short** bootstrap as first user message — no multi-paragraph Phase-hold novels in argv |

Hand harness tracks Mind (`mind.agent` / live Mind session), not a permanent
H-number label. Do not encode “H3 is always Codex” in product law. Model ids and
`agent_launch` stay in fleet JSON.

### Codex reinit-after-unit (when `agent=codex`)

**Policy:** when a Codex-runtime Hand is **done** and next target exists, **kill
Codex and start a fresh session**. One clean start — not five stacked wakes.

**When:** turn-end mail + next target; `done_idle` / long idle + open tasking; process
down; unblock (pin-refresh/merge) + open tasking with **current** one-line fact.

**When not:** `running` / mid-unit; tasking empty + operational pause only (refill
first if map has next); already reinited this Hand this cycle (unless died again).

**How:**

1. File next task/need **before** launch so a handle exists.
2. Kill **Codex children of pane_pid only** — leave tmux + shell. If session is
   gone: `tmux new-session -d -s hunter-N -c <packet-cwd>`.
3. Launch without `exec` using that Hand’s fleet **`agent_launch`** (model lives
   there — do not invent it from prose).
4. One short first message: identity, never merge main (if packet), `vivi --for hunter-N`,
   open handle(s), one verb, optional one-line unblock fact.
5. Enter once. Record `last_codex_reinit_at` in baseline.

### Doorbell (wake) protocol — primarily **Grok**

When `wake_enabled` and class is `idle_prompt` and Hand has open tasks/needs
(or Mind just filed targets / answered a blocking need) — **Grok default**:

```bash
tmux send-keys -t '<tmux_target>' -l -- '<pointer only>'
tmux send-keys -t '<tmux_target>' Enter
```

For **Codex**, use **reinit** (above) instead of stacking this doorbell after a unit.

#### Channel split (mandatory)

| Channel | Allowed content |
| --- | --- |
| **tmux send-keys** | **Tight pointers only** — identity token, where to look (handle / folder / doc path), one verb (“show and continue”). No essays, no policy dumps, no multi-paragraph rules. |
| **Vivi mail / task / need** | Full done-when, evidence bar, scope, approach, residuals |
| **Agents.md / factory goal / campaign** | Durable multi-agent law, architecture, stage criteria |

**Why:** long instructional payloads in shell/`send-keys` are noisy, easy to
false-positive safety hooks, and duplicate sources of truth. The Hand already
has `$fleet`, container Agents.md, and the tasking bag body.

Good tmux pointer (one short block):

```text
HAND WAKE hunter-1. Bag: show <handle>. vivi --project <root> --for hunter-1. Continue.
```

Or after filing mail:

```text
HAND WAKE hunter-2. Read inbox/mail <handle> then bag. Identity hunter-2. Continue.
```

Bad tmux content: full multi-agent policy, stage graphs, long defaults lists,
quoting forbidden git verbs as “don’t do X.”

Ops intervenes (model/retry) stay one-liners too; detail goes to Vivi if needed.

Record `last_hunter_wake_at`, reason, target in fleet baseline.

### tmux process ops (start / rehome / restart)

Mind and operators rehome hands when **cwd must match the workspace**
(main checkout vs `worktrees/<slug>/`). Prefer a clean Grok exit and restart in
the correct directory over fighting a TUI that was started elsewhere.

**Invariant:** fleet `cwd` / packet `root` (and `worker_cwd` once members exist)
should match `tmux display -p -t <target> '#{pane_current_path}'` (or
`list-panes … #{pane_current_path}`). A Hand assigned to a packet but running
from the project root will write and tool against the wrong tree.

#### Prefer rehome when

- hunter-2+ is reassigned to a new packet
- packet shell is prepared and the session still has main-checkout cwd
- operator wants a **clean baseline** in the packet (fresh Grok, no resume)
- session is `down` / process dead (recreate session + start agent)

Prefer **theme-switch `/compact`** (Grok) when cwd and identity are already
correct and only the conversation theme changes. **Codex:** reinit after unit
instead of compact+wake.

#### Packet rehome sequence (Grok TUI in tmux)

```text
1. Pane must be idle_prompt (not Waiting) unless operator allows cancel
2. Exit Grok cleanly: send /quit  (alias /exit)  — own turn, then Enter
3. Wait until pane_current_command is a shell (zsh/bash), not grok
4. Confirm or create session with correct -c:
     tmux new-session -d -s hunter-N -c <packet-or-main-cwd> -n main
   Respect window/pane base-index (often 1 → target hunter-N:1.1)
5. From shell already in the right cwd, start Grok (do not leave cwd wrong)
6. Verify: pane path == fleet cwd; command is grok; then short bootstrap doorbell
```

Example start line (adjust flags to the fleet’s usual policy):

```bash
# Pane shell is already in the packet root (tmux -c or prior cd).
# Quote every --deny pattern that contains * or shell metacharacters — zsh
# will glob unquoted Bash(sudo *) and fail with "missing delimiter for 'u'".
grok --sandbox off \
  --deny 'Bash(sudo *)' \
  --deny 'Bash(rm -rf /)' \
  --deny 'Bash(rm -rf ~)' \
  --deny 'Bash(rm -rf $HOME)' \
  --always-approve
```

Bootstrap after restart is still **pointer-only** (identity, packet slug,
`vivi --for`, “idle wait” / “show handle”). Full assignment stays in Vivi +
`PACKET.md`.

#### tmux / shell pitfalls (hard-won)

| Do | Don't |
| --- | --- |
| `tmux send-keys -t … -l -- '…'` for literal text | Rely on unescaped `*` in unquoted shell args |
| Single-quote each `--deny 'Bash(…*)'` for zsh | Paste deny lists without quotes into an interactive zsh |
| Prefer plain `grok …` / `codex …` so a failed launch leaves a shell | `exec grok` / **`exec codex`** — can leave the pane unusable or **destroy the tmux session** |
| Recreate with `tmux new-session -d -s hunter-N -c <cwd>` if session died | Assume the old session still exists after a bad restart |
| Match fleet `tmux_target` to real base-index (`1.1` vs `0.0`) | Hardcode wrong window/pane indices after recreate |
| Fresh Grok (no `--resume`) when rehoming to a new packet baseline | Blindly resume an old main-checkout session into a packet cwd |
| `--resume <id>` only when continuing the **same** workspace/theme is intentional | Resume across packet reassignment without operator intent |
| After start: check `#{pane_current_path}` and a short capture | Trust fleet JSON alone without verifying the live pane |

#### Session down / recreate

```bash
tmux has-session -t hunter-N || \
  tmux new-session -d -s hunter-N -c '<fleet cwd>' -n main
# then start agent as above; mail identity bootstrap if brand-new conversation
```

Record restarts in fleet baseline when useful (`last_hunter_restart_at`,
reason, cwd). Product state still lives in Vivi; process rehome is not a bag
event unless you also file/clear targets.

### Theme switch: `/compact` then continue (same session) — **Grok**

When a **Grok** Hand finishes one theme and will receive another in the same
session, prefer `/compact` plus a pointer wake: identity, cwd, and process
survive while finished detail is dropped. Start a new session only when the pane
is down, needs different model/flags, remains confused after compaction, or the
operator wants a clean slate.

**Codex:** after a unit with next target, **always reinit** (see Codex reinit) —
do not rely on compact+wake on a finished `›`.

Sequence (Grok):

1. File the next task/need first so its handle exists.
2. Require `idle_prompt`, then send `/compact` alone and wait for idle again.
3. Keep identity, `vivi --for`, main/packet role, and campaign in the compact
   instruction; drop finished implementation detail.
4. Send: `HAND WAKE hunter-N. Compact done. Show <handle>. Continue.`
5. Record compact/wake in the baseline when useful.

Never combine `/compact` and the new assignment in one keystroke or compact
without next target. High TUI context usage is only a hint, not a control-plane
field; fix dead or hung sessions instead of compacting them.

### Completion mail (optional but preferred when turn succeeds)

Short turn-end (any hunter):

```text
From: hunter-N → reviewer
Subject: hunter-N turn end: <one line>
Body: cleared <handle>|none · HEAD <sha>|dirty · tasking left: … · next: … · blocked: none|…
```

Bag `task done` / `need done` remains the primary durable signal even if this
mail is skipped.

### Ready-to-merge mail (hunter-2+ — preferred template)

High-signal handoff so Mind can **absorb** without reverse-engineering the
pane. Send when the packet unit is done, tree clean, worker stopped.

```text
From: hunter-2 → reviewer
Subject: hunter-2 turn end: ready-to-merge <packet-slug>

ready-to-merge packet <packet-slug>

## Cleared
task <handle> (<subject>)

## Facts
- slug: <packet-slug>
- branch: factory/<packet-slug>
- <repo> HEAD: <full sha> (<short>)
- base: <base checkpoint>
- product commit(s): <oneline list>
- tree: clean (worker stopped)

## Validation
- <commands and PASS/FAIL or honest skip>
- What evidence is static vs manual/env-gated (be explicit)

## Scope touched
- <paths within write scope only>

## Watch-scope drift
- none | <paths that moved on main vs base — or "not checked">

## Integration
Operator/main merges via hunter-1; this Hand does not merge to main.
```

Mind on receipt: **absorb** → review → **accept** or residual mail back to
worker → on accept set `pending_merges` state `queued_for_h1` and file merge
task to hunter-1 (or queue if h1 mid-phase). Optional short tmux to worker:
`Packet accepted. Merge with hunter-1. Wait.`

**Long-term continuous packets** (multi-theme HIR or multi-stage product packets):
do **not** file a merge to hunter-1 after every task unit. Prefer **theme-level**
ready-to-merge (major delivery unit, Stage N close, or operator-named theme).
Units → absorb/review/**refill next map unit** on the packet only; one merge
task per theme so the main-spine Hand is not drip-harassed.

Ready-to-merge **validation** should include at least: claimed tests **and**
`cargo fmt --check` (or project equivalent) on touched packet repos — so theme
merges do not **create** red main. Merger re-checks green on main after absorb.

## Integration seams (pin-relative done)

A fix is **done relative to a pin**, not absolutely.

| Operation | Touches | Execute owner | When |
| --- | --- | --- | --- |
| **Theme merge** packet → main | main branch | **hunter-1** only | Theme accept + clean breakpoint |
| **Base-update** main → packet | writable packet branch | **packet worker** | Green main + worker not mid-unit + lag/drift |
| **Pin refresh** | pinned/read-only member worktree (e.g. runtime pin) | **operator / Mind** | Product needs a main-only capability; worker must **not** self-bump worktrees |
| **Consumer re-verify** | product packet | that Hand | Only after `git merge-base --is-ancestor <fix-sha> <consumer-pin-HEAD>` |

**Misroute class:** filing a “compiler residual” To the origin Hand when the
consumer is red because the fix is **not on their pin** — that is **integration
lag**. Mind should queue merge/base-update/pin-refresh, not thrash re-verify.

Do not doorbell “DONE re-verify NOW” until the fix is reachable from the
consumer’s tree. Prefer a need To Mind/operator for pin refresh over stacked
wakes on a correctly blocked product hunter.

## Lifecycle

### 1. Arm

- Ensure a bag exists (mailspace identities, or equivalent board)
- Point Hand and Mind at the same project root and map (campaign/GOAL)
- Record **Mind’s harness** in fleet (`mind.agent`); bind every Hand’s `agent` /
  `wake_mode` / reinit policy to that harness (**Harness alignment**). Apply
  **Preferred models by role** (Grok 4.5 / Codex sol·medium Mind & luna·xhigh Hand;
  Heads → Pi + GLM 5.2 high/xhigh).
- Optional scout for approach-only advice
- Create tiny role baselines under the project (Mind cycle baseline + fleet
  config — paths are camp-local): `last_cycle`, `quiet_streak`,
  `last_actionable_fingerprint`, fleet pane classes, optional `repo_heads`

### 2. Select focus

- Campaign/map names the current stage or package
- Hand selects one open target (oldest, explicit priority, or map order)
- Do not wait for Mind stamp to start a selected map package

### 3. Gather

- Sensors: bag + HEADs/dirty + **pane classes**
- On paid path: scan what **moved**; file residuals to owning Hand
- Quiet when bag/HEAD fingerprint and pane classes unchanged (or only `running`)
- On idle+open tasking or error class: wake or ops intervene

### 4. Work (Hand)

- `show` one target; implement; validate
- **End-of-unit polish** on changed product source from this unit (`$polish`)
- Mark done with evidence; absorb Status into campaign/docs when criteria hold
- Next target from bag, or next map package, or sleep (idle at prompt is OK if
  Mind doorbell is armed)

### End-of-unit polish (Hand — iterative units)

Small Stage 4–style / residual batches leave churn that a full campaign polish
pass never sees. **Default after each product unit that touches implementation
source:** run `$polish` **before** tasking done / turn-end, scoped to this unit.

```text
implement + targeted validate
  → list primary source files changed by THIS unit (git status / diff vs pre-unit HEAD)
  → $polish those files only (serial per-file loop)
  → then tasking done + turn-end (+ ready-to-merge if packet)
```

| Do | Don't |
| --- | --- |
| Target **primary source** files this unit created or substantially edited | Repo-wide or package-wide polish “while here” |
| Include only **directly related** tests/docs as `$polish` allows | Polish foreign dirty / other agents’ WIP |
| Prefer product Rust/source over pure Status/docs-only deltas | Force polish commits when inspect finds no useful change |
| Note polish commits in turn-end when non-empty | Block the tasking bag on polish failures that are out of scope — residual them |

**File list (derive from the unit, not from suggest-polish-files defaults):**

```bash
# example: files changed since unit start SHA
git -C <repo> diff --name-only <pre-unit-sha>..HEAD
# keep primary source; drop lockfiles, generated, pure Status if no code change
```

Skip polish only when the unit was **docs-only / Status-only / merge-only** with
no implementation source, or the operator explicitly waives. Packet workers
polish **inside the packet worktree** on their branch before ready-to-merge.

Mind does **not** run polish for the Hand. Thorough review may note
missing polish as a residual if landed product source is clearly unpolished.

### 5. Sleep / wake / backoff

See **Fail-fast wake**. Most wakes should be no-ops.

### 6. Retire

- Empty tasking + no next map package → stop loop or long backoff
- Operator may stop schedulers when camp is idle for hours
- Do not keep supervisory essays alive as fake progress

## Fail-fast wake (context budget)

Long 5–10m loops only work if most wakes **exit in seconds**. Tokens/context
are scarce—not wall clock. **Fail fast to sleep** when nothing moved.

### Cheap sensors (always first)

```text
1. Board status counts (e.g. vivi mailspace status)
2. Open task + need lists per Hand identity (not dumps)
3. Optional light delta: git rev-parse HEAD, dirty count, map file mtime
4. Fleet: tmux has-session + short capture classify (if fleet configured)
```

Compare to baseline. **Sleep immediately** when:

- fleet actionable fingerprint unchanged (hunter-N only; ignore legacy codex for this)
- no relevant main/packet HEAD/dirty move
- pane classes unchanged and not `error_*`
- not (hunter-1 idle + empty + map/merge debt)
- not (idle + open tasking needing doorbell/**Codex reinit**)
- not (empty tasking + map next = starvation unfilled)
- `pending_reviews` / `pending_merges` empty or explicitly deferred this cycle

On **true quiet** sleep: bump `quiet_streak`, write baseline, **one-line** report  
(`quiet N; absorb/accept as accurate; panes ok; sleep`).  
No dump, no full campaign re-read, no harness matrix, no priority essay.

When the cycle **acted** (filed targets, absorb/accept, reinit, merge queue, advisor
triage), emit a **scannable summary** (not a novel):

1. Headline: cycle N · superficial|thorough · absorb/accept verbs accurate  
2. Fleet snapshot: each Hand pane class + bag handles + one-clause status  
3. Board moves: filed / done / merged handles  
4. Head briefs when mail absorbed: 1 short ¶ problem + 1 short ¶ action  
5. Pending debt if non-empty  

Cycle lines: use **absorb** and **accept** accurately (never absorb when you mean accept).

Optional: thorough review every N cycles (e.g. `cycle % 3 == 1`); superficial
otherwise — §§REDMIND§§s + mail + starvation only.

### Expand only on signal (paid path)

| Signal | Who | Action |
| --- | --- | --- |
| New/changed open task/need | Hand | show handle → work |
| HEAD/dirty product moved | Mind | bounded residual pass **and/or code review** |
| Hand mid-flight dirty (main or packet) | Mind | **proactive review** of WIP; §§REDMIND§§s → Vivi + short tmux pointer |
| Same dirty paths block spine ≥2 cycles, no A/B/C note | Mind | **Open the diff** (half-dead); classify; file style/claim/quarantine; pivot targets for Hand |
| Map Status mtime changed | Either | skim Status lines; then bag |
| Tasking empty + next package selected | Hand / Mind | start package or **refill** + wake/reinit |
| Head report mail | Mind | absorb; triage to hunter-N when actionable |
| Approach / sequencing fork | Strategist (or Mind) | one advisory report / note |
| Pane `idle_prompt` + open tasking (**Grok**) | Mind | doorbell wake |
| Pane `done_idle` / idle + open tasking (**Codex**) | Mind | **Codex reinit** |
| Theme finished + next target filed (**Grok**) | Mind | **theme-switch compact** then doorbell |
| Theme finished + next target filed (**Codex**) | Mind | **Codex reinit** |
| Pane `error_*` | Mind | ops intervene (model/retry/reinit) |
| Pane `down` | Mind | recreate session + agent; may need **new session** |

### Proactive review (Mind, any cycle with signal)

Hands optimize for throughput; Mind optimizes for **invariant honesty**.

**When to open a review pass (bounded, not full campaign re-read):**

- Thorough cycle (`cycle % N` / paid path), **or**
- Superficial cycle if: new HEAD on focus repos, **or** dirty product paths in a
  hunter’s allowed scope (main checkout **or** packet worktree), **or** Status
  flip without evidence.

**How:**

1. Identify owner from fleet (main dirty → likely hunter-1; packet dirty → that
   packet’s worker; if ambiguous, say so in mail).
2. Diff only in-scope paths (`git diff`, packet branch log, key tests/claims).
3. Look for §§REDMIND§§s: fail-open, dual ABI/dialect, tests weaker than Status,
   scope bleed into another hunter’s surface, silent env fakes, docs lying,
   **Status complete while evidence is only static/manual without saying so**.
4. **Accept** (green): clear matching `pending_reviews` / advance packet toward
   merge; optional baseline note. Prefer draining review debt on paid passes.
5. **Red flag:** file a **task** **To: hunter-N** with where, why, done-when for
   an implementable fix. Use a **need** only for a real decision/authority/input
   hold; then send a tmux pointer e.g.
   `HAND WAKE hunter-2. Bag: show <handle>. vivi --for hunter-2. Continue.`
6. Do **not** paste the full review into tmux. Do **not** `git` cleanup foreign WIP.

Mid-flight review is **advisory + residual**, not a stop stamp. For a
safety-critical implementable finding (data loss, auth, destructive scope),
file a high-priority **task** with a fail-closed default and wake immediately.
Use a **need** only when the safe fix actually requires a decision, authority,
or external input.

**Status honesty (accept bar):** static checks, node contract tests, and
“controlled manual browser/GPU inspection” are fine **if Status says so**.
Reject **accept** when Status says complete/product-run but evidence is only
static or env-faked.

### Absorb vs accept (Mind vocabulary)

Two different Mind actions — do not collapse them.

| Term | Meaning | When | Quality bar |
| --- | --- | --- | --- |
| **Absorb** | Reconcile sensors into baseline/bag awareness: notice HEAD/done/Status, stop re-discovering, update fingerprints | Every cycle when something moved | Low — bookkeeping honesty |
| **Accept** | After code review, treat the unit/packet as good enough: clear review debt, allow map square closeout, unblock dependents, or queue merge to hunter-1 | Thorough or opportunistic review pass with evidence | High — invariants, tests vs claims, scope |

| Role | Says… |
| --- | --- |
| **Hand** | Delivered / task **done** (evidence) — never “absorb” or “accept” |
| **Mind** | **Absorb** always when moved; **accept** only after review |
| **Operator** | May force priority; day-to-day accept stays Mind |

**Anti-pattern:** writing “absorb” in a cycle line as if it meant **accept**
(Status + subject only, then file next package as green).

Routing next target after absorb is fine **if** unreviewed work stays on
`pending_reviews` until **accept** (or residuals are filed). Example: absorb
ABI S2–3 bookkeeping, file B2, keep ABI on `pending_reviews` until accept.

### Review debt (do not route-as-accepted)

Maintain in fleet baseline (or fleet state):

```text
pending_reviews[]: { hunter, range or shas, paths, reason, since_cycle, status }
pending_merges[]:  {
  packet_slug, branch, worker, tip, base, theme?,
  state: active | ready | reviewing | queued_for_h1 | merged
       | partial_merged | integrated_publish_pending | abandoned
}
# see pending_merges states (extended) under Multi-lane Mind
```

| Event | Mind duty |
| --- | --- |
| Hand marks done / HEAD jumps on their scope | **Absorb**; add `pending_reviews` if not yet **accepted** |
| Thorough or opportunistic review pass | **Accept** (clear debt) or file residuals; drain backlog when possible |
| Packet ready-to-merge mail (theme or whole one-shot packet) | **Absorb** → review → **accept** or residual → state `queued_for_h1` + merge task |
| Long-term packet unit (not theme) | **Absorb**/review; next target to worker; **no** merge task to h1 |
| hunter-1 idle + empty + pending_merges queued | Prefer merge task doorbell **now** (clean breakpoint) |
| hunter-1 idle + empty + map still open | Refill targets **and** drain review/merge debt |
| hunter-1 completes merge | **Absorb** merge on main → **accept** merge (or residual) as its own step |

### Sensors: main + packets + fleet bags only

Cheap fingerprint should include:

1. Open tasks/needs for **each hunter-N** (not legacy `codex` for quiet/wake
   decisions — log codex only if migration still open)
2. Main HEADs + dirty for focus repos
3. **Each active packet:** `git -C worktrees/<slug>/<writable> status` +
   `rev-parse HEAD` + branch name
4. Pane class per Hand

Packet dirty counts as that worker’s mid-flight WIP (proactive review scope).

### Merge task body (to hunter-1)

When Mind **accepts** a packet, the merge task should name at least:

- packet slug + root path  
- writable repo(s) + branch name(s)  
- base checkpoint + expected tip  
- preferred merge order  
- validation commands / bar (**two-sided green:** packet RTM certified fmt+tests;
  merger re-checks green on main after merge — red main is a one-turn artifact)  
- **watch-scope drift** before merge:  
  `git diff --name-only <base>..HEAD -- <watch-paths>`  
  Main often moves (other units on spine) while the packet is open. Non-empty
  drift on watch paths → stop and report; do not force-merge through design
  conflict. Empty / only expected doc paths → proceed.  
- done-when: on main, green validation, note back to reviewer  

**When to doorbell hunter-1:**

| hunter-1 state | Action |
| --- | --- |
| Idle + empty tasking | File merge task + doorbell **now** |
| Running / dirty mid-phase | File or keep `queued_for_h1`; **do not** interrupt |
| Idle + other open targets | Merge may be higher priority than new spine work if packet is blocking; else queue |

After hunter-1 reports merge done: Mind **absorbs**, then **accepts** the
main result (or files residual). Operator may retire worktrees later.

Deep work (full delivery re-read, full tests, dump) only on paid path—or when
the operator asks.

Never wake a `running` Hand merely because the tasking bag is unchanged; Mind may
review its dirty scope, but the implementation owns its active turn.

### Optional cadence backoff

Fail-fast is required. Interval backoff is **optional** for multi-hour idle:

| `quiet_streak` | Suggested interval |
| --- | --- |
| 0–2 | base (e.g. 5m) |
| 3–5 | 2× base |
| 6–10 | 4× / ~20–30m |
| 11+ | ~1h or sleep until operator/hunter signal |

Reset `quiet_streak` on real progress: new/changed tasking item, HEAD move, Status
absorb, filed residual, completed unit, successful wake, or ops intervention.

If the scheduler cannot change interval, still no-op cheaply each fire.

## Board intake (list-first)

When on the **paid path**, after sensors fire:

```text
1. status counts
2. open task list for each active hunter
3. open need list for each active hunter
4. want list only if hunting polish by design
5. show only the selected handle
```

**Dump is audit**, not the heartbeat. Prefer open-only dumps when needed.
For Vivi command shapes, body send, and mailspace ops, use `$mail`.

Product upgrades (board/brief/json):  
`~/work/ianzepp/vivarium/docs/mailspace-agent-control-plane-goal.md`.

## Supervisor loops

Periodic Mind/scout only help while product moves, residuals are open, or
fleet panes need liveness care. Empty tasking + flat trees + healthy idle panes →
quiet or back off. Do not “keep the campaign alive” with restated plateaus after
the Hand exited—restart hunter, select next map package, back off, or stop.

## Anti-patterns

### Bag and gates
- Treating Mind as a game warden: stage licenses, GO/NO-GO stamps, or
  acceptance authority; or blocking a Hand on missing GO with no residual.
- Encoding severity as queue kind: filing an implementable merge blocker as a
  **need**, then leaving a needs-only Hand parked as if human input were required.
- Sleeping with empty product tasking while the map still has unblocked next work
  (“wait after unit / RTM” as default success).
- Treating wants as defects, or parsing board storage instead of using the CLI.
- Filing targets to retired identities when `hunter-N` is the default, or putting
  packet merges/unbounded spine work on hunter-2+.
- Letting Heads (strategist/correctness/purity) own product tasking or merge
  queues; thrashing strategist assign while a report is outstanding.

### Dual channel and process
- Relying on completion mail or an idle pane alone; use bag, HEAD/dirty state,
  and pane liveness together. Never wake a `running` pane without cancel policy.
- Sending policy essays through tmux; use Vivi, Agents, goals, and campaigns
  for durable detail, with tmux as a pointer-only doorbell.
- **Mixed Hand harness under one Mind** (e.g. Mind=Grok, some Hands=Codex)
  without an explicit temporary exception — violates **Harness alignment**.
- Treating Head harness diversity as a bug, or forcing Heads onto Mind’s
  harness “for uniformity” when second-party opinion is the point.
- **Stacking Codex `HAND WAKE` lines** on a finished `›` instead of **reinit**.
- **`exec codex` / fragile `exec grok`** that can leave the pane dead or
  **destroy the tmux session**.
- Multi-paragraph stale bootstrap in agent launch argv (Phase-hold novels).
- Running a packet Hand with **cwd still on main** (or path ≠ fleet
  packet root / worker_cwd); fix with rehome, not more doorbells.
- Unquoted `--deny` globs in zsh (`Bash(sudo *)`); wrong base-index after recreate.

### Integration and honesty
- Treating **packet-green as consumer-green** without pin ancestry
  (`merge-base --is-ancestor`); doorbelling false “DONE re-verify NOW.”
- Filing a **compiler residual** when the true class is **integration lag**
  (fix not on main / pin not refreshed).
- Theme merge that **creates durable red main** (no packet fmt/tests in RTM;
  no post-merge green check).
- Interrupting dirty hunter-1 for a merge, merging packets in the Mind, or
  skipping watch-scope drift and the separate absorb → accept sequence.
- Accepting “complete” when evidence is static/manual but the claim is a
  product run, without saying so in Status.
- Writing “absorb” when you mean **accept** (Status + subject only → next package green).

### Hygiene and multi-agent workspace
- Combining `/compact` with assignment, compacting without next target (Grok), or
  starting a new Grok session for every theme when compact would suffice.
- Skipping changed-file-only end-of-unit polish, or polishing **foreign dirty**
  / other agents’ WIP.
- **Destructive git cleanup** of unexpected dirt (`stash`, `reset`, `restore`,
  `clean`) — foreign uncommitted work is another agent’s in-progress unit.
- **Status-only dirt freeze:** repeating “foreign dirty / blocked” across cycles
  without `git diff` classification (A/B/C) or half-dead age escalation.
- Treating **class A** (fmt/layout after inspect) as permanent foreign WIP
  instead of style-commit / include per formatter law.
- Freezing the whole session on one blocked item while other bag/map targets exist
  (topic monogamy under blockage).
- Waiting silently for confirmation that was never filed as a need/mail.
- Dumping or deeply inspecting every wake, writing plateau essays, or running
  high-cadence turns while the tasking bag, trees, and panes are unchanged.

## Multi-agent shared workspace

Multiple agents often share one branch/worktree. Two laws hold at once:

1. **Do not erase** uncommitted work outside your allowed scope.
2. **Do not freeze** on unclassified dirt that blocks progress.

**Invariant (ownership):** changes you did not make in this session’s allowed
scope are **another agent’s work**, not dirt to remove with destructive git.

**Invariant (progress):** half-dead dirt is a target to **classify and unstick**, not
a multi-hour status-only wall. See **Don't get stuck** and class **A/B/C**.

### Never (destructive)

- `stash` / `reset` / `restore` / `clean` / force-push to “make room”
- Polish or rewrite another hunter’s mid-flight semantic WIP
- Overwrite foreign paths with write tools just because the tree looks messy

### Always (when dirt blocks you)

```text
list paths → open diff → class A / B / C → act or pivot same turn
```

| Class | Act |
| --- | --- |
| **A** mechanical/fmt | Commit or include after inspect (formatter law) |
| **B** intentional other | Work around / narrow / worktree / Vivi escalate — keep age visible |
| **C** mixed | Own hunks only when safe; leave rest; continue other targets |

On unexpected dirt **outside** scope: **do not erase** — list paths, classify if
it blocks you, work around or escalate. **Do** open the diff before multi-cycle
freeze. Sub-agents escalate out-of-scope dirt to the parent; parent escalates
true ambiguity to the operator **after** filing a need with a default.

## Project overlay contract

**This skill is the portable process.** Camp files bind instances and may add
product law. They must not redefine bag-vs-gate, absorb-vs-accept,
don't-get-stuck, or **Harness alignment** (Hands = Mind harness).

| Lives in skill | Lives in project overlay |
| --- | --- |
| Roles, bag rules, dual channel, fleet axes | Concrete Hand roster, cwds, model ids |
| **Harness alignment** + **Preferred models by role** | Live `mind.agent` / `agent_model` / `agent_launch`; Head Pi launches |
| Theme vs unit, merge clock, base-update *policy* | Campaign maps, product Status, validation commands |
| Head loops, cycle kinds, runtime fallback *structure* | Role-prompt paths, absolute tool binaries |
| Baseline *field meanings* and `pending_merges` states | Fat historical ledger rows, wind-up snapshots |
| Pane classes, reinit contract, wind-down procedure | Scheduler prompt path, durable 5m task id |

Recommended **kinds** of project files (names and directory layout are
camp-local — the skill does not mandate a particular roster filename):

```text
fleet config           # roster + runtime + tooling paths + preferred models
Mind cycle baseline    # cycle sensors + debt + advisor state
Mind scheduler overlay # thin camp process prompt when using a durable loop
Head role prompts      # strategist / correctness / purity
reinit helper (opt.)   # Codex (or other) reinit doctor/heal script
project Agents.md      # product + multi-agent law
```

Prefer absolute paths from fleet `tooling` over `which` every cycle (nvm/`pi`
often missing from bare Mind shells).

---

## Mind cycle kinds (promoted detail)

After cheap sensors, set `cycle = last_cycle + 1` (write at end of cycle).

| Kind | When | Work |
| --- | --- | --- |
| **Mail interrupt** | Always first | Permission / review / Q from hands or operator → answer **same wake** |
| **Thorough (paid)** | e.g. `cycle % 3 == 1` | Residual + code review of product changes since `last_thorough_fingerprint` |
| **Superficial** | other cycles | Red-flag scan + pane classes; sleep unless §§REDMIND§§, mail, starvation, or wake/ops |

Cadence is commonly **3–5 minutes** per fire. Prefer sleep unless something
substantive moved, mail needs a reply, or a pane needs wake/ops.

### Superficial

Pane classes + cheap dirty/HEAD delta. If a Hand is mid-mod (dirty in their
scope): quick red-flag scan; mail+pointer if needed. Sleep unless §§REDMIND§§,
mail interrupt, starvation, or wake/ops.

### Thorough

Re-diff vs `last_thorough_fingerprint`. Unchanged → quiet thorough (still run
pane scan). If moved: review product on **all fleet scopes** (main + each active
side lane); file residuals **To owning hunter-N**; update thorough fingerprint.

### Sensors (always first — keep cheap)

```text
1. Read baseline + fleet config (pending_reviews, pending_merges, active lanes)
2. Board status counts (vivi mailspace status)
3. Mind inbox top (advice / review / permission / advisor reports)
4. Open tasks/needs for each hunter-N (legacy shared identity: list only if migrating;
   do not use legacy counts for quiet/wake/starvation)
5. Main HEAD + dirty for focus repos (project names the list)
6. Each active side lane: status -sb + HEAD + branch
7. Fleet pane scan (all hands + Heads if configured)
8. Optional: map Status line if HEAD moved
```

**Fingerprint:** fleet bags only + main HEADs/dirty + side-lane HEADs/dirty +
pane classes + non-empty pending debt.

Do not parse board SQLite/blobs; use the CLI. Baseline may ignore handle
prefixes for quiet detection.

### Chat summary (operator often has no live pane)

When the cycle **acted**, emit more than a one-liner so the operator can follow
without attaching every tmux session:

1. **Headline** — `cycle N kind; absorb/accept accurate; sleep|acted`
2. **Fleet snapshot** — each Hand + Heads: pane class, bag handles or empty,
   notable HEAD if moved, one-clause status
3. **Board moves** — absorbed / accepted / filed / woke (handles + subjects)
4. **Pending debt** — `pending_merges` / `pending_reviews` if non-empty
5. **Strategist status** — awaiting_report? assign handle? reinit this cycle?
6. **Strategist report brief** (new report absorbed) — 1 short ¶ problem + 1 short
   ¶ recommended Mind actions; optional stale-premise correction; no full paste
7. **Correctness / purity** status + brief when new report absorbed

Quiet true sleep may stay one-line. Prefer tables for the fleet snapshot.
Use **absorb** and **accept** accurately.

---

## Head loops (advisors) (promoted detail)

Heads are **not** product lanes. Do not keep-screen-moving refill them with map
packages. They never merge and never own `pending_merges`. Prefer the **Pi**
harness with **GLM 5.2 (high or xhigh)** for all advisors — one-shot
assign→report, second-party opinion (**Preferred models by role**).

### Strategist research loop (mail; every Mind cycle, fail-fast)

1. Sensors: mail list for strategist (or Mind inbox for `strategist report:`)
   + baseline `strategist.*`
2. If `strategist.awaiting_report` and no new report yet → **do not re-assign**;
   note “strategist in flight”; continue hunters
3. If a **strategist report** arrived → absorb; optional triage to Hand tasks/needs;
   set `awaiting_report=false`
4. If **not** awaiting and ready for a new question → **clean-slate reinit + one assign**:
   1. File assignment mail **To: strategist** first (handle exists)
   2. Reinit strategist process: quit/kill current agent, **fresh** launch from
      fleet `strategist.agent_launch` in fleet cwd — not “continue old chat”
   3. Bootstrap pointer only: role prompt path, show assign handle, research,
      report via board To Mind, idle
   4. Set `awaiting_report=true`; record `last_reinit_at` + assign handle
5. Prefer mail for assignment body; short tmux pointer after reinit is OK
6. Reports may take 5–10+ minutes — **do not thrash** while outstanding

#### Strategist assignment quality (anti-fragile)

Strategist advises ownership, sequencing, seams, gate honesty, misprioritization —
**not** driving product and **not** racing the tasking bag.

**Avoid:** questions that die if a tasking item lands while you read mail.

| File questions about… | Do not make the *core* question… |
| --- | --- |
| Who owns which seam | “Is handle X open right now?” |
| Real stage/gate vs static-only overclaim | Minute-by-minute merge queue alone |
| Theme vs unit cadence; fake board deps | Assumptions mid-flight unit is done/not |
| Conditional paths (“if red → …; if green → …”) | A single HEAD SHA as durable law |

**How to write assigns:**

1. **Structural question first** (1–3 sentences that stay meaningful for hours)
2. **Optional live snapshot** second, labeled ephemeral; tell strategist to re-verify
3. Prefer **conditionals** over “do X now because bag is empty”
4. Mind still acts on live bag reality; strategist informs *how to think*

**Strategist duty on stale assign:** re-read live evidence; one-line correction of
stale premises; answer the structural question anyway.

### Correctness auditor loop (self-directed)

Identity/session separate from hunter-N. Typical subject prefix: `correctness:`.

1. Sensors: has-session; pane class; Mind inbox for correctness reports
2. Session **down** → recreate per fleet + role-prompt bootstrap (unless operator paused)
3. New report → **absorb**: triage into task/need **To owning Hand** when
   actionable; doorbell if idle; record `correctness.last_report_*`; optional
   chat brief (problem ¶ + action ¶)
4. **Do not** assign work every cycle. Soft-wake only if stuck idle long with no
   recent mail — pointer only to continue next pass + role path
5. Never map-refill correctness as a product lane

### Purity auditor loop (self-directed)

Identity/session separate. Typical subject prefix: `purity:`. Often same harness
class as strategist. **Not** clean-slate every report. Prefer **compact between
passes** so context stays small.

1. Sensors: has-session; pane class; purity report mail
2. Down → recreate per fleet + role bootstrap
3. New report → absorb; triage simplify/design targets To owning Hand (prefer over
   drive-by rewrites mid-product unit); doorbell if idle and targets ready
4. Optional soft focus mail (`purity assign: <area>`) — not required every cycle
5. Soft-wake hygiene: compact keep identity+role+lens, then next pass; clean-slate
   reinit only if compact fails, confused, or operator asks
6. Never map-refill purity. Do not confuse with correctness (bugs) or strategist
   (priority/ownership / clean-slate-per-assign)

---

## Multi-lane Mind (all hands every cycle)

Track **all active hands** every cycle; do not collapse maps into one spine.

**Live assignment table = fleet JSON** (`hands.*.packet` / `focus` / `cwd`).
Do not treat a prose snapshot of “H2 always owns X” as law — read fleet live.

| Slot class | Workspace | Bag empty means |
| --- | --- | --- |
| **hunter-1** | **main** (sticky) | starvation if main map next, pending_merges, or better open residuals |
| **hunter-2+** | **current fleet assignment** | starvation if **that assignment’s** map still has unblocked next work — refill same cycle |

File targets **To the Hand that currently owns that assignment**. Never cross-file
continuous work to the wrong slot.

### Theme → main (always via hunter-1; theme cadence only)

Side-lane workers **never** merge to main. Mind owns the integration clock.

**Do not harass hunter-1 with a merge every task unit.** Long continuous lanes
merge at **theme boundaries**, not unit boundaries.

| Event | Mind action |
| --- | --- |
| Worker finishes a **unit** | **Absorb** + review; residual or next unit To: **same worker**; **no** merge task to h1 |
| Worker finishes a **theme** | ready-to-merge → review → **accept** → `pending_merges` → **merge task To: h1** at clean breakpoint |
| Operator forces mid-theme integrate | exception only when explicit |

**Theme (default):** one delivery-index major unit honestly closed **or** an
operator-named theme. Not “tasking empty for an hour” alone.

#### Theme-complete path

1. Worker signals **theme ready-to-merge** (theme name + tip + evidence) **or**
   Mind judges theme done after review
2. **Absorb** tip; **code review** range since last main merge (not a GO stamp)
3. **Accept** → `pending_merges` (slug, tip, base, theme, state `queued_for_h1`)
   **or** residual To worker
4. File **one merge task To: hunter-1** (slug, branch, base, tip, theme,
   validation, **watch-scope drift**)
5. Wake/reinit h1 only at **clean breakpoint** (by h1’s current runtime). Mid-spine → **queue**
6. After h1 merges: **absorb** main; **accept** merge; clear/update `pending_merges`;
   file next unit/theme To worker still assigned that lane (or reassign)
7. After theme on main: evaluate **main → side-lane base-update** (below)

Between themes: worker keeps committing on its branch; main stays free for spine —
but the side lane must **periodically absorb green main**.

### Integration modes

1. **Bounded one-shot lane:** ready-to-merge when the whole assignment finishes →
   review → merge task to h1
2. **Long-term continuous lane:** merge only at **theme** boundaries. Units →
   absorb/review/next target only
3. Never ask hunter-2+ to merge to main
4. Defer h1 wake while mid-spine phase / dirty main WIP
5. **Main → side-lane reverse sync is required policy** (not forever-diverge)

### Main → side-lane base-update (Mind-owned timing)

**Invariant:** continuous side lanes must not lag main indefinitely. Mind
decides **when** to file base-update targets; workers execute when assigned.

Default method: **merge green main into the side branch** (merge commit). Prefer
merge over rebase on multi-agent shared branches.

(Project may define directory layout for side lanes; this skill states **policy**,
not a required filesystem convention.)

#### Green main gate (hard)

Only use a main tip as base-update source if that tip is **green** by project bar
(examples: formatter clean, lint green, targeted tests green). Name the **exact
green SHA** in the task. If main is red or unvalidated → wait or file main
residual; do **not** refresh the side lane onto a known-broken tip. After
base-update failure, default suspicion is merge interaction — not “main was already broken.”

#### When to file (pick one; do not thrash)

| Trigger | Action |
| --- | --- |
| Theme merge just accepted on main | Prefer base-update when worker idle/clean |
| Side lane missing main commits on watch/write surface | File base-update before product that depends on those facts |
| Watch-scope drift / next theme merge would be painful | File base-update |
| Worker mid-flight intentional dirty WIP | **Defer** |
| Main not green | **Defer** |

One base-update task per lane when lag is real — not a new SHA every cycle.

#### Task body

- **To:** side-lane worker
- Body: green main SHA + evidence + merge command into side branch + validate + turn-end
- Worker: resolve conflicts honestly; no force-push; no product scope expansion
  unless required for conflict resolution

### Post-theme residue vs pending merge

**Empty tasking + no `queued_for_h1` does not mean tip is on main.** Continuous lanes
often hold tens of unit/polish commits after a recorded theme merge. That is
**post-theme residue**, not a merge queue item, until Mind defines the next
theme seam (or operator forces integrate).

When assessing “is everything merged?”: re-check `git merge-base --is-ancestor
<side-tip> <main-tip>` (and reverse lag), not only the `pending_merges` ledger.

### `pending_merges` states (extended)

```text
active | ready | reviewing | queued_for_h1 | merged
| partial_merged | integrated_publish_pending | abandoned
```

| State | Meaning |
| --- | --- |
| `active` | Theme in flight on side lane |
| `ready` | Worker claims ready; not yet reviewing |
| `reviewing` | Mind review open |
| `queued_for_h1` | Accepted; merge task exists or should |
| `merged` | On main and accepted as merge |
| `partial_merged` | Only part of the theme landed; residual debt remains |
| `integrated_publish_pending` | Integrated somewhere / publish or Status still open |
| `abandoned` | Explicitly dropped |

Ledger history may keep old `merged` rows; **live queue** is non-terminal states only.

---

## Pane classes and actions (promoted detail)

Classify by **fleet `agent` for that pane**, not by H-number. Prefer **last ~15–25
lines** of capture (optional -80 for ops context). Prefer a project **classify
script** over ad-hoc greps when available (avoids false `error_connection` from
tool text like `timeout 1800 ./script`).

| Class | Cues | Mind action |
| --- | --- | --- |
| `running` | Streaming / Working / Waiting / live spinner — **wins over** error-looking tool output | Do not send-keys / reinit; may WIP-review dirty scope |
| `idle_prompt` | Ready prompt (`›` / `❯`) | See open tasking + runtime |
| `done_idle` | Turn-end / “tasking empty” / “standing by” monologue then ready (esp. Codex) | Finished unit — reinit if open tasking (Codex) |
| `trust_prompt` | Workspace trust UI (“Yes, continue”) | Reinit auto-accept or send accept once; not `running` |
| `error_capacity` | over capacity, rate limit, 429, usage limit | Runtime fallback ladder |
| `error_connection` | ECONNRESET, connection failed, *network* timeouts (not shell `timeout N`) | One same-model reinit; then capacity ladder |
| `down` | no tmux session | Recreate + fleet `agent_launch` in fleet cwd |
| `unknown` | unreadable noise | Record sample; do not thrash |

| Situation | Action |
| --- | --- |
| `idle_prompt`/`done_idle` + open tasking + **codex** | **Reinit** — not stacked wakes |
| `idle_prompt` + open tasking + **grok** | Pointer doorbell |
| `idle_prompt` + empty tasking + map has next unblocked unit | **Starvation** — file next target same cycle; then wake/reinit by runtime |
| `idle_prompt` + empty + operational pause only | Quiet OK; note reason |
| `idle_prompt` + empty after unit/theme accept | Not default quiet — absorb/accept → **refill** → wake/reinit |

Never wake on dirty-only mid-flight; never reinit `running` without FORCE policy.

---

## Runtime fallback (capacity / unavailability)

**Invariant:** assignment (H-number, side lane, merge rights) does **not** change
when a model is full. Only **runtime** rebinds (`agent_model`, `agent_launch`,
and only carefully `agent` / `wake_mode`). Source of truth: fleet
`runtime_fallback` + per-hunter fields + **Harness alignment**.

### Failure classes

| Class | Cues | First response |
| --- | --- | --- |
| **Capacity** | over capacity, rate limit, 429, usage limit, “try again later” | Step model ladder (**same harness as Mind** for Hands) |
| **Auth / quota hard stop** | account exhausted, login required | Park that harness; escalate operator; pivot other hands |
| **Connection** | ECONNRESET, disconnect | One same-model reinit; then capacity ladder |
| **Harness dead** | crash loop, session destroy | Recreate shell + launch; if loop → model ladder, then **Mind-aligned** harness recovery |

### Model ladder (structure; ids live in fleet)

Prefer staying on the **Mind-aligned product harness** while possible. Fleet
names an ordered ladder **per harness** (example shape only — do not invent ids
not in fleet):

```text
# defaults match Preferred models by role; fleet may extend
codex_model_ladder_mind:  [ gpt-5.6-sol@medium, … ]
codex_model_ladder_hand:  [ gpt-5.6-luna@xhigh, … ]
grok_model_ladder:        [ grok-4.5, … ]
head_pi_model:            [ glm-5.2@high, glm-5.2@xhigh, … ]
```

**When `error_capacity` on a Hand (or similar):**

1. Confirm not mid-successful `running` with real progress → wait
2. Advance that Hand’s `agent_model` one step **on the same harness**; rewrite `agent_launch`
3. **Reinit** (Codex) or doorbell after restart (Grok) with short bootstrap — not stacked wakes
4. Baseline `last_runtime_fallback` {hunter, from, to, reason, cycle, at}
5. **At most one model step per Hand per cycle** — do not spin the whole ladder
6. Ladder exhausted → park Hand or escalate; **do not** silently move the Hand to
   a different harness while Mind stays on the original (exception requires
   operator note + plan to re-align)

**Heads** may use their own ladder / alternate harness without waiting for Mind.

### Harness fallback (after model ladder exhausted)

**Hands** stay harness-aligned with Mind. Product harness flip is a **fleet-wide
Mind decision**, not a per-Hand convenience:

1. Exhaust same-harness model ladder on the affected Hand(s)
2. If Mind’s harness is fleet-dead: recover **Mind** (operator if needed), set
   new `mind.agent`, then rebind **all Hands** to that harness on clean breakpoints
3. Temporary single-Hand exception (operator only): record in baseline; still
   prefer re-align ASAP — mixed Hand harnesses under one Mind are debt
4. Heads may already be on alternate harnesses; leave them unless they fail too

Do **not** treat “flip H3 to pi while Mind stays Grok” as the default recovery.
That reintroduces the interoperability problem harness alignment avoids.

Harness flip for the product plane = update `mind.agent` + every Hand’s
`agent` + `agent_launch` + `wake_mode`, then clean launch. **Assignment unchanged.**

### Per-cycle budget (anti-thrash)

- Max **~2** capacity-driven model flips per cycle fleet-wide for product slots
- Product **harness** flips are rare (Mind-plane); do not burn the budget on them casually
- Normal reinit-after-unit does **not** count as fallback
- Never flip a `running` Hand for capacity unless pane shows hard capacity error
- Prefer flipping **idle/error** product slots first (model only, same harness)

### Mind / orchestrator hard limit — recovery

If the Mind session dies (hard quota / dead harness), it cannot self-heal
inside the dead session.

| Situation | What works | What does not |
| --- | --- | --- |
| Soft pressure | Keep product on **same-harness cheaper models**; shorten prose; skip nonessential Head wakes | Migrating Hands onto a different harness while Mind stays put; migrating all product onto a dying orchestrator |
| Session alive but tool errors | Fail-fast sleep; one-line baseline; next fire retries | Infinite retry same turn |
| **Hard stop** | **Operator recovery** (below) | Silent hope; thrashing hands without a live Mind |

**Operator recovery:**

1. Leave mid-unit product hands alone if still working
2. Start a **new Mind** session (same or temporary harness) in the project
3. Open `$fleet` + camp overlay; run **one** cycle or re-arm scheduler
4. Set/update `mind.agent` for the live Mind harness. If Mind harness changed,
   plan Hand rebind on clean breakpoints (**Harness alignment**)
5. Optional fleet note for temporary Mind runtime; revert later
6. Do **not** require product hands to stop for Mind recovery unless rebinding
   them to the new harness

**Scheduler honesty:** a durable interval task only helps if **some** session is
alive to execute it. Dead Mind → operator must reattach or run manually.

Always write fallbacks into baseline and fleet per-hunter runtime fields.

---

## Codex reinit production contract (promoted detail)

**Problem:** Codex after a unit parks at ready prompt and does not pull the next
tasking item. Stacked wake lines fail or keep **stale bootstrap** alive for hours.

**Policy:** when `agent=codex` is **done** and next work exists → **kill Codex +
fresh session + short bootstrap**. One clean start. Harness is a fleet binding,
not part of the H-number.

### When to reinit

1. Turn-end / ready-to-merge this cycle **and** bag has (or just received) next target
2. `done_idle` or long `idle_prompt` + **open tasking**
3. Process down + open tasking or need to stand by with current law
4. Unblock (pin-refresh, merge) + open tasking — reinit with **current** one-line fact

### When not

- `running` / mid-unit
- Tasking empty + operational pause only (refill first if map has next)
- Already reinited this Hand this cycle (unless died again)
- Fleet `agent` is not `codex`

### Prefer a project script

Camps often ship a reinit helper script (path is camp-local). Suggested commands:

| Command | Role |
| --- | --- |
| `doctor` / `doctor hunter-N` | Bag-aware health; no kill |
| `heal` / `heal hunter-N` | Auto-reinit slots that need it (idle/done/error + open tasking) |
| `snapshot` / `snapshot hunter-N` | Forensic dump (pane, board, fleet) |
| `classify` / `status` | Pane class / status |
| `reinit hunter-N --boot '…'` | One hunter; refuse if running unless FORCE |
| `reinit-all --boot-template '…{name}…'` | Sparingly; budget still applies |

Suggested exit codes (reinit): `0` ok · `1` hard fail · `2` **stuck_idle**
(ready but never Working) · `3` bad args. Doctor: `0` healthy · `1` unhealthy ·
`2` trust/stuck/starving. On reinit exit 2: one more reinit same cycle OK; if
still stuck next cycle → model ladder or snapshot + operator.

**Classify traps:** do not treat tool `timeout N cmd` or `error: test failed` as
`error_connection` when pane is live Working. Prefer doctor evidence over raw greps.

**Manual fallback** if script missing: kill agent children of pane only; leave
tmux+shell; launch without `exec` via fleet `agent_launch`; short bootstrap;
record `last_codex_reinit_at`.

**Forbidden:** multi-paragraph argv holds; stacking wakes on finished ready;
reinit `running` without FORCE; `exec codex`.

Mind default under thrash: **doctor then heal** over hand greps + stacked wakes.

---

## Fleet config schema (promoted detail)

Recommended keys (extend freely; skill cares about meanings):

```json
{
  "version": 1,
  "default_hunter": "hunter-1",
  "legacy_hunter_identity": "codex",
  "gatherer_identity": "reviewer",
  "binding_rule": "mail_identity == tmux_session token",
  "mind": {
    "agent": "grok",
    "agent_model": "grok-4.5",
    "note": "Product harness source of truth; Hands inherit agent family"
  },
  "agent_policy": {
    "hands_follow_mind_harness": true,
    "heads_prefer_pi": true
  },
  "preferred_models": {
    "grok": { "mind": "grok-4.5", "hand": "grok-4.5" },
    "codex": {
      "mind": { "model": "gpt-5.6-sol", "effort": "medium" },
      "hand": { "model": "gpt-5.6-luna", "effort": "xhigh" }
    },
    "head": { "agent": "pi", "model": "glm-5.2", "thinking": "high|xhigh" }
  },
  "tooling": {
    "pi": { "binary": "/abs/path/to/pi" },
    "codex": { "binary": "/abs/path/to/codex" },
    "grok": { "binary": "/abs/path/to/grok" },
    "vivi": { "binary": "/abs/path/to/vivi" }
  },
  "runtime_fallback": {
    "grok_model_ladder": ["grok-4.5"],
    "codex_model_ladder_mind": ["gpt-5.6-sol"],
    "codex_model_ladder_hand": ["gpt-5.6-luna"],
    "head_pi_model_ladder": ["glm-5.2"],
    "hand_harness_follows_mind": true,
    "heads_prefer_pi": true
  },
  "hunters": {
    "hunter-1": {
      "mail_identity": "hunter-1",
      "tmux_session": "hunter-1",
      "tmux_target": "hunter-1:1.1",
      "cwd": "/path/to/main",
      "agent": "grok",
      "agent_model": "grok-4.5",
      "agent_launch": "…",
      "merges_to_main": true,
      "assignment_sticky": true,
      "runtime_sticky": false,
      "wake_enabled": true,
      "wake_mode": "tmux_send_keys",
      "min_seconds_between_wakes": 180
    },
    "hunter-2": {
      "mail_identity": "hunter-2",
      "cwd": "/path/to/side-lane",
      "agent": "grok",
      "merges_to_main": false,
      "assignment_sticky": false,
      "packet": { "slug": "…", "branch": "…", "state": "assigned" }
    }
  },
  "strategist": {
    "mail_identity": "strategist",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "agent_launch": "pi --provider zai --model glm-5.2 --thinking high",
    "clean_slate_per_assignment": true,
    "role_prompt": "<camp-path>/strategist-role-prompt.txt"
  },
  "correctness": {
    "mail_identity": "correctness",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "self_directed": true
  },
  "purity": {
    "mail_identity": "purity",
    "agent": "pi",
    "agent_model": "glm-5.2",
    "thinking": "high",
    "self_directed": true
  }
}
```

**Never hardcode model strings as Hand identity.** Read `agent_launch` from fleet.
Hand `agent` should match `mind.agent` unless baseline records an operator exception.
Default model picks come from **Preferred models by role**; fleet may override for
capacity or experiment, then re-align when quiet.

---

## Baseline schema (promoted detail)

Maintain at least:

```text
last_cycle, last_cycle_at, last_cycle_kind, last_cycle_summary
quiet_streak
last_actionable_fingerprint   # fleet bags + heads/dirty + panes
pending_reviews[]
pending_merges[]
active_packets{} or active_lanes{}   # slug → head, branch, worker
last_thorough_cycle, last_thorough_fingerprint
hunter_fleet mirror / pane_classes
last_hunter_wake_*, last_codex_reinit_*, last_runtime_fallback
strategist.{awaiting_report, last_assign_handle, last_reinit_at}
correctness.last_report_*, purity.last_report_*
gatherer_loop.{state, handoff, …}   # armed | running | stopping | wound_up
half_dead[] optional                # path, class A/B/C, age_cycles, note
```

Ignore-lists for tasking noise may live in baseline (`ignore_bag_handles`,
`ignore_subjects_prefixes`) without deleting board history.

---

## Fleet wind-down and rearm (promoted detail)

Part of orderly camp shutdown (and of this skill's lifecycle **Retire**).

### When to wind down

- Operator requests wind-up / stop after N cycles
- Map empty + bags empty + no pending merge queue for a long quiet streak
- Orchestrator must stop but product residue can wait

### Procedure

1. **Stop filing new keep-screen-moving targets** unless operator wants one last drain
2. **Absorb** finished lands: note HEADs, light-accept recent ranges, update
   `pending_reviews` / `pending_merges` honesty (do not invent theme RTMs)
3. **Classify each slot:**
   - empty tasking + clean/idle → finished → eligible to drop pane
   - open product tasking mid-unit → **keep** or operator-stop with residual noted
   - open tasking is only human/env gate → treat as finished for wind-down; leave need open
4. **Drop panes** for finished hands and Heads (`tmux kill-session`); leave
   mid-product hands if operator wants residual drain
5. **Baseline** `gatherer_loop.state = wound_up` with: dropped/kept panes, tips,
   residual open handles, handoff for rearm
6. Optional pointer to kept hands: fleet wound up; continue bag or idle
7. Cancel or detach durable Mind scheduler if operator is stopping the loop

### What wind-down is not

- Not “all side tips are on main” (re-check ancestry separately)
- Not permission to `stash`/`reset` foreign dirt
- Not auto-closing open needs (env gates, operator decisions stay on the board)

### Rearm

1. Recreate tmux sessions from fleet (`cwd`, `agent_launch`)
2. Read baseline handoff + open taskings
3. Refill starvation if maps still have work
4. Set `gatherer_loop.state = armed|running`; clear or archive wind-up block
5. Optional strategist assign if structural debt remains (e.g. merge-order research)

---

## Hand decision continuity (promoted detail)

Applies to every Hand (and any implementer identity):

### Never block yourself on a decision

**Unsent questions do not exist.** Other agents only see the board and commits.

| Situation | Required action |
| --- | --- |
| Path / name / scope / order / ABI / package / stop | Same turn: **need or mail** to Mind with **default + options** |
| Filename / docs layout only | Campaign convention or default in the need; keep working |
| Waiting for a reply | **Switch targets** — do not freeze |
| Human-only wall | Send the need first, then switch targets |

### Never idle when other targets exist

One blocked topic must not freeze the hunt.

1. Externalize if decision
2. Immediately select another open task/need or next map package
3. Sleep only when actionable tasking empty **and** no next map package

Second-best progress beats zero. Context switch is required, not optional.

**Forbidden:** silent stall; “only this one thing until someone answers”; parking
while other tasking items remain; treating private monologue as coordination.

---

## Related skills

- `$mail` — Vivi project mailspace CLI (task/need/want/mail); not the process
- `$polish` — end-of-unit per-file improvement on **this unit’s** changed primary source
- `$correctness` — behavioral bug / invariant audits (advisor or Hand tool)
- `$cleanliness` — structure/complexity scans (pairs with purity-style work)
- `$factory` — multi-phase implementation when the Hand executes a large unit
- `$campaign` / `$delivery` — map and delivery packages the Hand drains
- `$executive-team` — broader role cast; fleet is the tasking bag-loop subset
