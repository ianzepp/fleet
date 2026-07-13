# Mind cycle and fail-fast wake

Modes, wake loops, sensors, review, absorb/accept, merge tasking.

## Mind interaction modes (strong guidance — not a hard ban)

Mind = operator-opened harness conversation. Model tier is operator setup — do **not** self-detect model id. Cognitive budget follows **interaction mode**. Do not freeze useful work for awkward counters.

### Scheduled cycle prefix

Every durable scheduler / loop injection **must** start with `FLEET_CYCLE`:

```text
# Single fleet
FLEET_CYCLE fleets=mgs
# or: FLEET_CYCLE project=<root>

# Multi-fleet — slugs only on the first line (attach log)
FLEET_CYCLE fleets=mgs,faber,nacht
```

**Paths belong in the body**, not invented topic-line keys:

```text
Roots:
  mgs:   /path/to/minted-geek-swarm
  faber: /path/to/faberlang
  nacht: /path/to/nachtbagger
```

First line `FLEET_CYCLE` ⇒ **not** operator message. Fix overlays that omit this.

**Multi-fleet:** one fire = fail-fast **mini-cycle per fleet**; each fleet writes own `last_successful_cycle_at` (+ steward rearm only if armed). [`multi-fleet.md`](multi-fleet.md).

### Counters (write every cycle)

| Field | Meaning |
| --- | --- |
| `quiet_streak` | Consecutive cycles, no actionable product signal |
| `turns_since_operator_message` | Mind cycles since last human operator message |
| `last_operator_message_at` | Cycle id / time of last operator prose |
| `mind_mode` | `autonomous` \| `interactive` (this cycle) |
| `mind_mode_override` | optional sticky force (`ops_only` / `deep` / clear) |
| `operator_recap` | Material **status** deltas since last operator message |
| `operator_mail` | Optional `operator@` counters — not status |

**Operator message** = human prose in Mind session. **Not:** `FLEET_CYCLE…` only, scheduler boilerplate, Hand/Head board mail, pane captures.

### Resolve mode (before sensors expand)

**Anti-bug:** `FLEET_CYCLE` means “this injection is not operator prose.” It does **not** mean “ignore human chat since last fire.”

**Hard never (both directions):**

```text
# A — force autonomous without engagement check
turns_since_operator_message += 1
if turns >= 3: mind_mode = autonomous

# B — force interactive forever (over-correct of A)
turns_since_operator_message = 0   # every FLEET_CYCLE, no human check
mind_mode = interactive
```

**A** ignores chat between fires. **B** (common over-fix) freezes silence at 0 so autonomous never arrives. **Resolve engagement first**, then either:

```bash
# engaged (human this turn or since last_operator_message_at)
fleet-baseline.py bump -p "$ROOT" -s '…' --acted --operator-engaged …

# not engaged (FLEET_CYCLE-only and no human since stamp)
fleet-baseline.py bump -p "$ROOT" -s '…' --acted …   # default: silence += 1
```

**Never** hand-edit `turns_since_operator_message` / `mind_mode` after bump.

```text
# Step 0 every cycle — substitute real session state; do not only inspect current payload

if mind_mode_override is set:
    mind_mode = autonomous if override == ops_only else interactive
    # sticky until cleared; still run sensors/ops below
else:
    # --- detect engagement ---
    if this_turn is human prose (not FLEET_CYCLE-only):
        engaged = true
        engagement_time = now
    elif session has human prose since last_operator_message_at
         (if null: since last_cycle_at, or any prior human turn this session)
         and that prose is not a FLEET_CYCLE injection:
        engaged = true
        engagement_time = time of that human message
    else:
        engaged = false

    if engaged:
        turns_since_operator_message = 0
        last_operator_message_at = engagement_time
        refresh operator_recap window from engagement_time
        present operator@ list if open/unread > 0   # operator-mail.md
        if this_turn is human prose:
            mind_mode = interactive
        else:
            # FLEET_CYCLE-only wake, but human spoke between fires
            mind_mode = interactive   # or keep prior interactive; silence stays 0
            # ops body may stay thin; do NOT treat as multi-cycle abandon
    else:
        turns_since_operator_message += 1
        append material events to operator_recap (short)
        if turns_since_operator_message >= 3:
            mind_mode = autonomous
        elif prior mind_mode is known:
            mind_mode = prior   # turns 1–2: operator may still be watching
        else:
            mind_mode = autonomous

# End of cycle (after sensors/ops): write counters + mind_mode + operator_recap to baseline
```

**Threshold:** ≥3 Mind cycles with **no human prose** → **autonomous** until next operator message.  
“Mind cycle” here means a turn where engagement stayed false end-to-end — **not** “we ran a FLEET_CYCLE while the operator was mid-conversation.”

| Mode | Cognitive budget | **Cycle report** |
| --- | --- | --- |
| **Autonomous** | Limited reasoning even if high available. Ops: sensors, classify, file/wake/reinit, short absorb/accept, sleep. **Decide now** on reversible defaults. | **Compact:** one-line quiet or short acted headline/table. Update `operator_recap` internally. |
| **Interactive** | Full reasoning for human exchanges; ops still fail-fast. | **Rich status every FLEET_CYCLE**. Sleep/in-flight multi-section, not one-liner. |

**Invariant:** report richness tracks `mind_mode`, not whether the cycle “acted.”

### Autonomous duties and escalation

| Still | Does not |
| --- | --- |
| Cheap sensors + pane scan | Deep-plan “because the model can” |
| Refill starvation; doorbells/reinits | Post-merge **code audit** (**head-cto on main**) |
| Absorb moved HEADs; residual **tasks** | Wait multi-cycle on head-ceo when safe default exists |
| **needs** for real decision holds (default + options) | Freeze on class A dirt without opening diff |
| Update **operator_recap** | Dump status into **operator@** |
| File **operator@** for problems/blockers/bug-guidance | Idle waiting for operator mail when other map targets exist |

| Escalation (cheapest first) | Route |
| --- | --- |
| Pane/capacity/runtime | Fleet ops (reinit / ladder) **now** |
| Class A dirt / obvious residual | Style-commit or **task** To Hand **now** |
| Implementable defect | **task** To owning Hand |
| Human-only wall / unsafe default / needs guidance | **need or mail To `operator@`** (default + options); **pivot** |
| Structural sequencing only (optional) | head-ceo assign — **do not block** product cycles; decide interim default |

Waiting several cycles for head-ceo “permission” is a rules-of-engagement failure.

**Interactive:** full reasoning for operator Q&A; same cheap ops + **rich cycle report**. After **≥ 3** silent cycles → autonomous. Turns 1–2 of silence: keep rich.

**Operator recap:** short material **status** list since `last_operator_message_at` (HEADs/merges, handles, pane ops, mode, debt). Re-seed after `/compact`. Interactive reports **surface** the delta.

### Operator mail (cheap cycle + present on return)

**Both directions every mini-cycle** — part of cheap sensors, not optional. [`operator-mail.md`](operator-mail.md).

| Signal | Meaning |
| --- | --- |
| `operator_to_mind` | **From operator@ → mind@** — absorb **first** (decisions/feedback from any session) |
| `operator_mail` | Open needs/unread **To operator@** — human backlog |

Prefer `fleet-sensors.py` (emits both + `op→mind` lines in `--text`).

```bash
vivi mail list --for mind --project <root>       # scan From: operator@
vivi mail list --for operator --project <root>
vivi need list --for operator --project <root>
```

On engagement / “catch me up” / sensors `operator_to_mind`: (1) **op→mind** absorb, (2) **To operator@** list, (3) **operator_recap**, (4) live bag / panes / HEAD. New op→mind this cycle → `--operator-engaged` on baseline bump.

CLI: [`vivi.md`](vivi.md). N>0 → work-through table. N=0 → say empty once. Autonomous: `+op-mail:N` / `+op→mind:N` on one-liner — never status spam To operator@.

### Steward rearm (every successful mini-cycle)

```bash
# Placeholders: <ROOT> <summary> — flags without <> are literals
# Silence: default bump does turns_since_operator_message += 1
# Only if human engaged: add --operator-engaged (resets silence + interactive)
python3 scripts/fleet-baseline.py bump -p <ROOT> -s '<summary>' \
  --quiet \
  --fingerprint-file /tmp/fleet-sensors.json
# or: --acted when board/ops moved
# or: --operator-engaged when human prose this turn / since last_operator_message_at
# Attach/detach: --mind-session <label> (sets mind_session lock + state=attached)
#                --detach (clears mind_session + state=detached)
# NEVER hand-edit mind-baseline.json. Use bump flags for all state transitions.
# only if steward enabled+armed for this fleet (default: skip):
# scripts/steward.sh rearm --project <ROOT>
```

| Also | When |
| --- | --- |
| `steward.sh arm` | **Only** after operator sets `steward.enabled` **and** asks to arm **this** fleet — not on attach/loop alone |
| `steward.sh rearm` | End of successful mini-cycle **if** that fleet’s steward is armed |
| `steward.sh disarm` | If armed: detach, stop loop, wind-down — **same turn** |
| `steward.sh clear` | After dead-man trip recovery |

Progress = **successful cycle completion for that fleet**, not inject or turn start. Multi-fleet: baseline bump **each** mini-cycled fleet; rearm only fleets with steward armed. [`dead-man.md`](dead-man.md), [`multi-fleet.md`](multi-fleet.md).

Thorough/superficial cadence still applies (`cycle % N == 0`). Autonomous thorough = residual-shaped — **not** peer review of every packet. **head-cto** reviews main after merge.

## Fail-fast wake (context budget)

Long 5–10m loops work only if most wakes **exit in seconds**. Tokens scarce. **Fail fast to sleep** when nothing moved. Resolve **mind_mode** first, then sensors.

### Cheap sensors (always first)

```bash
# Placeholders: SK, ROOT, hex — substitute before run
SK=/path/to/fleet/scripts
ROOT=/path/to/fleet/project

python3 $SK/fleet-sensors.py --project "$ROOT"
python3 $SK/fleet-sensors.py --project "$ROOT" --text
python3 $SK/fleet-sensors.py --project "$ROOT" --no-watch

# Doorbell for Grok/Pi/Codex; Codex helper path uses submit-settle
$SK/fleet-doorbell.sh --project "$ROOT" hand-1 --handle <hex> --note 'bag open'
# exit 0 sent · 1 refused (running|down|rate-limit) · 2 usage

python3 $SK/fleet-sensors.py --project "$ROOT" > /tmp/fleet-sensors.json
python3 $SK/fleet-baseline.py bump -p "$ROOT" -s 'sleep' --quiet \
  --fingerprint-file /tmp/fleet-sensors.json
# only if steward enabled+armed for this fleet (default: skip):
# $SK/steward.sh rearm --project "$ROOT"
```

| Helper | Job |
| --- | --- |
| `fleet-sensors.py` | Board status, optional watch, handles, pane classes, git tip/divergence/dirty paths, pending RTM integration lag, fingerprint, `signals[]`, `quiet_hint` |
| `fleet-doorbell.sh` | Resolve `tmux_target`; refuse running/down/rate-limit; pointer `send-keys` only; `last_hand_wake` |
| `fleet-baseline.py` | `get` / `bump` / `rearm-note` / `wound-up` — counters, mode silence, fingerprints, recap, `--mind-session` attach, `--detach` |

### Signal disposition gate

`sensors.signals[]` are obligations. Before sleep/report/baseline bump, each material signal must be `acted`, `delegated`, `escalated`, `deferred-valid`, or `sleep-valid` as defined in `SKILL.md`.

Examples: `operator_to_mind` must be absorbed first; `operator_mail` must be presented/carry-forwarded; `wake_candidate_*` must be doorbelled/reinit'd or validly deferred; `runtime_*_stopped|failed|approval_required` must be repaired, assigned to ops, or escalated; `starvation_candidate_*` in growth must trigger file+wake or executive refill/valid pause; repeated dirty blockers must be diff-classified A/B/C.

`mail_for_<role>` means new mail was addressed to a process role since the prior successful cycle. The cycle is the debounce boundary: if `mail_wake_candidate_<role>` is also present, doorbell that idle role immediately with the mail handle. Do not wait for an executive cadence interval. If the pane is running, leave it uninterrupted and carry the mail signal forward for the next idle cycle. Cadence controls unsolicited sweeps only; addressed work is demand-driven.

A compact autonomous report may summarize dispositions in one clause. An interactive report must surface unresolved non-quiet obligations until they are disposed.

**Sleep immediately** only after the disposition gate passes and when:

- fleet actionable fingerprint unchanged (hand-N only; ignore legacy codex)
- no relevant main/packet HEAD/dirty move
- no new mailspace watch hits (if using cursor)
- pane classes unchanged and not `error_*`
- not (hand-1 idle + empty + map/merge debt)
- not (idle + open tasking needing doorbell)
- not (empty tasking + map next = starvation unfilled)
- `pending_reviews` / `pending_merges` empty or explicitly deferred

On **true quiet:** bump `quiet_streak`, keep/update silence + `mind_mode`, write baseline, report by **mode**. Do not re-read full campaign for quiet autonomous wake.

Use **absorb** and **accept** accurately. Optional thorough every N cycles (`cycle % 3 == 0`); autonomous thorough = residuals only.

## Cycle report templates (mode-gated)

Choose from `mind_mode` after resolve. No autonomous one-liners while interactive.

### Autonomous — compact

```text
cycle N superficial|thorough; mode=autonomous; posture=…; operator_silence=K; sleep; panes ok
```

Acted (one short block max):

```text
cycle N …; mode=autonomous; acted — <one clause>
| slot | class | bag |
…tiny table optional…
debt: <one line if any>
```

No narrative. Keep `operator_recap` in baseline.

### Interactive — rich

1. **Headline** — cycle N · kind · mode=interactive · posture=growth|standby|dormant · silence=K · sleep|acted · one-clause why
2. **Fleet snapshot (table)** — each Hand + Heads: pane class, bag handles/subjects or empty, one-clause status
3. **Product / focus** — map focus, main HEAD (+ dirty), notable land/WIP
4. **Board moves** — absorbed / filed / woke / none
5. **Signal disposition** — unresolved non-quiet signals and their disposition (`acted`, `delegated`, `escalated`, `deferred-valid`); omit only when truly quiet
6. **Pending debt** — open P0s, merges, polish/housekeeping if non-empty
7. **Heads** — idle / report outstanding / none new
8. **Since you spoke** — 2–5 bullets from `operator_recap` when non-empty
9. **Next** — what next fire should see

Even **sleep** interactive uses this shape. **Not required:** full mail dumps, full campaign re-read, strategy essays, peer review of WIP.

| Report anti-pattern | Why |
| --- | --- |
| Interactive + one-line “sleep” | Operator cannot see WIP / debt / why idle |
| Autonomous + multi-page status every 5m | Burns context; nobody reading |
| “Thin ops” ⇒ “thin report” in interactive | Ops fail-fast; **report** stays rich when watching |

### Expand only on signal (paid path)

| Signal | Who | Action |
| --- | --- | --- |
| New/changed open task/need | Hand | show handle → work |
| Git tip / dirty product moved | Mind | bounded residual / Status-honesty (not full code review) |
| Hand mid-flight dirty | Mind | cheap red-flag; residuals → Vivi + pointer |
| Main tip moved after merge | Correctness / **head-cto** | post-main code review / bug hunt |
| Main tip moved (merge / feature land / spine unit) | Mind | **Post-main polish advisory** |
| **Major inflection** on main | Mind | **Housekeeping task** (expensive; not every land) |
| Same dirty paths block spine ≥2 cycles, no A/B/C note | Mind | **Open the diff**; classify; file; pivot |
| Map Status mtime changed | Either | skim Status; then bag |
| Tasking empty + next package selected | Hand / Mind | start or **refill** + wake/reinit |
| Head-role report mail | Mind | absorb; triage to hand-N when actionable |
| Approach / sequencing fork | head-ceo (or Mind) | one advisory report / note |
| Runtime `waiting_for_input` / `completed` + open tasking | Mind | doorbell |
| Theme finished + next target (**Grok**) | Mind | **theme-switch compact** then doorbell |
| Theme finished + next target (**Codex**) | Mind | doorbell; reinit only if stale/stuck |
| Pane `error_*` | Mind | ops intervene (model/retry/reinit) |
| Pane `down` | Mind | recreate session + agent; may need **new session** |

Never wake a `running` Hand merely because bag unchanged. Deep work only on paid path or operator ask.

## Mind cycle kinds

`cycle = last_cycle + 1` (write at end). Cadence commonly **3–5 minutes** per fire.

| Shape | Default cadence |
| --- | --- |
| **Manual / unscheduled Mind polling** | Sleep **≥ 60s** between unchanged checks |
| **Formal scheduled loop** | Start around **5 minutes**, then adapt to observed work density |

Grok supports formal scheduled loops. Codex as Mind: discrete cycles + shell `sleep` ≥ 60s. Fail-fast regardless. A scheduled cadence is a control setting, not a permanent promise: Mind should proactively replace the scheduler with a longer interval when repeated cycles are thin or unchanged, and with a shorter interval when reports, completions, decisions, or integration work accumulate faster than cycles can absorb them. Preserve the same loop goal and stop condition when replacing it, cancel the old scheduler, and report the new cadence in the next cycle summary.

| Kind | When | Work |
| --- | --- | --- |
| **Mail interrupt** | Always first | Permission / review / Q → answer **same wake** |
| **Thorough (paid)** | e.g. `cycle % 3 == 0` (remainder **0**) | Residual / Status-honesty since `last_thorough_fingerprint` |
| **Superficial** | other cycles | Red-flag + pane classes; sleep unless §§REDMIND§§, mail, starvation, or wake/ops |

**Superficial:** pane classes + cheap dirty/HEAD delta. Mid-mod Hand → quick red-flag; mail+pointer if needed.

**Thorough:** re-diff vs `last_thorough_fingerprint`. Unchanged → quiet thorough (still pane scan). Moved → all fleet scopes (main + side lanes); residuals **To owning hand-N**; update fingerprint.

### Sensors (full order — keep cheap)

Prefer `fleet-sensors.py`. Manual order when helpers unavailable:

```text
0. Resolve mind_mode
1. Baseline + fleet config (pending_reviews/merges, lanes, quiet_streak,
   turns_since, mind_mode, watch cursor)
2. Board status counts
3. Optional mailspace watch --once --write-cursor (Vivi ≥ 4.6)
4. Mind inbox top (board mail ≠ operator message; paid: mail thread)
5. Open tasks/needs per hand-N (not legacy codex for quiet/wake/starvation)
6. Main HEAD + dirty; each active side lane: status -sb + HEAD + branch
7. Fleet pane scan (SSH wrap when remote — ssh-remote.md)
8. Optional: map Status if HEAD moved
```

**Fingerprint:** per-hand bags + main HEADs/dirty + side-lane HEADs/dirty + pane classes + non-empty pending debt. Do not parse board SQLite. Baseline may ignore handle prefixes for quiet detection.

Chat reports: use mode-gated templates above. Interactive + Head report absorbed → 1 short ¶ problem + 1 short ¶ Mind actions (no full paste).

## Post-main polish advisory (Mind — cheap, strong guidance)

Hands own **end-of-unit polish**. After work **lands on main**, Mind runs **read-only score scan** and files bounded polish only when scores clear threshold. **Routing**, not quality verdict, not Mind running `$polish`.

**Run once** when main git tip moved vs `polish_advisory.last_scan_head` (or missing): packet/theme **merged**; spine unit **committed on main** + absorbed; operator polish ask.

**Do not** on pure quiet, packet-only tips never on main, or hand-1 mid-flight dirty on product. Prefer after absorb of clean main tip.

```bash
python3 <this-skill>/scripts/suggest-polish-files.py \
  --repo <main_checkout> \
  --json --limit 15
# optional: --path crates/foo
```

Ranks by churn since last polish commit (`polish(scope): …`, `Polish-Primary:` trailer, legacy). Fields: `path`, `score`, `commits_since_polish`, line churn, `last_polish`.

| Fleet key (`polish_advisory`) | Default | Meaning |
| --- | --- | --- |
| `score_threshold` | **500** | File polish only for `score >= threshold` |
| `max_files_per_task` | **3** | Cap primary files per task |
| `max_tasks_per_cycle` | **1** | Do not flood bag after one land |
| `script` | polish skill `scripts/suggest-polish-files.py` | Override path |

No polish history ⇒ very high scores. Raise threshold, scope `--path`, or one-time backlog triage — do not open 20 polish tasks in one cycle.

```text
1. Parse JSON; keep score >= threshold; sort desc
2. Drop paths already covered by open polish task
3. Take top max_files_per_task (≤ max_tasks_per_cycle tasks)
4. If none → record last_scan_head + top scores; no bag file
5. If some → **task** (not want) To hand-1 (or owning Hand if clearly that lane)
6. Done-when: $polish on listed primaries only; polish(scope) commits; evidence To mind
7. Doorbell/reinit only if idle+empty or this is next work — not if running product unit
8. Baseline: last_scan_head, last_scan_at, last_top[] {path, score}, last_filed_handle?
```

**Subject:** `polish advisory: <crate-or-area> (score ≥ T)`  
**Body:** primary file list + scores + “`$polish` serial per file; no repo-wide cleanup; skip if nothing useful.”

| Is | Is not |
| --- | --- |
| Cheap git-history metric + optional task | Mind peer-review or full `$polish` by Mind |
| Backstop when Hand polish slipped | Replacement for Hand end-of-unit polish |
| One bounded list after main moves | Every-cycle repo-wide thrash |
| Score = churn-since-polish routing | “High score means bug” |

**head-cto** = post-main **bugs**. **head-cxo** = excess-layer audits. Polish advisory = hygiene only.

## Major-inflection housekeeping (Mind — expensive, rare)

`$housekeeping` = full multi-phase maintenance. Cost ≈ large factory goal. **Inflection tax**, not post-land habit.

| Inflection | Signal |
| --- | --- |
| **Campaign / factory goal complete** | Map Status done; focus goal closed; bags empty for that hunt |
| **Large merge batch** | Multi-theme/packet merge or operator “integrate everything” — not single residual |
| **Stage / delivery closeout** | Stage flips complete; delivery graph node closed |
| **Operator ask** | Explicit “run housekeeping” / “hygiene pass on main” |

**Do not file:** ordinary main unit land (use polish advisory); every thorough/quiet streak; mid-spine with open product tasking; packet branch only (targets **main**); open housekeeping exists; same `last_filed_head` / campaign already filed.

```text
1. Classify: inflection? or routine land?
2. If routine → polish advisory only; skip housekeeping
3. If inflection:
   a. Prefer product bags for closed work empty (or operator override)
   b. Main clean enough (not mid dirty product unit)
   c. File ONE task To hand-1: subject "housekeeping: <campaign|merge|stage> on main"
   d. Body: run $housekeeping on <main_checkout>; phases per skill; stop on judgment;
      evidence To mind; do not expand into new product goals
   e. Doorbell only if hand-1 idle — never interrupt running product unit
   f. Baseline: last_filed_at, last_filed_head, last_reason, open_handle
```

**Default owner:** hand-1 (main). Never full housekeeping to packet hands. **Ordering:** product closeout residuals + merge green-gate first; then housekeeping. Polish advisory may still run on the land (cheap).

| Action | Relative cost | Cadence |
| --- | --- | --- |
| End-of-unit `$polish` (Hand) | Low–medium | Every product unit |
| Post-main polish advisory | Seconds (git history) | Main HEAD moves |
| `$housekeeping` | **Very high** | Major inflection only |
| Full factory goal | Very high | Map selection |

If unsure merge is “large,” **default no housekeeping**; file need with default “defer until campaign end.”

## Residual scan (Mind) — not peer code review

Hands: throughput + **own ship quality**. Mind: **bag honesty, Status honesty, integration**. Deep **code review** = **head-cto on main after merge**.

**When (bounded):** thorough (`cycle % N == 0` / paid), **or** superficial if new HEAD / dirty product / Status flip without evidence. Autonomous: residual-shaped, short; **decide now**; no head-ceo wait for reversible defaults.

1. Owner from fleet (main dirty → hand-1; packet dirty → that worker)
2. Diff only in-scope; cheap scan: Status lies, missing done marks, scope bleed, empty bag starvation
3. **Integration accept** (green enough): clear matching `pending_reviews` / advance packet toward merge when evidence + scope honest — not full audit
4. **Red flag residual:** **task** **To: hand-N**; **need** only for real decision hold; short tmux pointer
5. Do **not** paste essays into tmux. Do **not** `git` cleanup foreign WIP
6. Do **not** re-litigate style as multi-cycle freeze — class A clears same turn

Safety-critical implementable findings: high-priority **task** with fail-closed default; wake immediately.

**Status honesty bar:** static/manual evidence fine **if Status says so**. Reject accept when Status says complete/product-run but evidence is only static or env-faked without disclosure.

## Absorb vs accept (integration) — **canonical**

Other skill files only **link** here; do not invent alternate meanings.

| Term | Meaning | When | Quality bar |
| --- | --- | --- | --- |
| **Absorb** | Reconcile sensors into baseline/bag awareness (“something moved”) | Every cycle when product/board/pane signal moved | Low — bookkeeping honesty |
| **Accept** | Integration bar: unit/packet good enough to clear review debt, close map square, or **queue merge** | Thorough or opportunistic residual with honest evidence | Medium — tests/claims/scope honesty — **not** full code review |
| **Code review** | **head-cto** on **main after merge** | After land on main | High — bugs, fail-closed, multi-theme interactions |

| Role | Says… |
| --- | --- |
| **Hand** | Delivered / task **done** (evidence) — never “absorb” or “accept” |
| **Mind** | **Absorb** when moved; **integration accept** when evidence honest enough |
| **head-cto** | Post-main findings → Mind triages to tasks |
| **Operator** | May force priority |

**Anti-pattern:** treat absorb as accept; Mind multi-page code review of every packet while head-cto idles.

**Fixed phrase for other docs:** *absorb = bookkeeping when something moved; accept = integration bar (not code review) — mind-cycle.*

## Review debt

```text
pending_reviews[]: { hand, range or shas, paths, reason, since_cycle, status }
pending_merges[]:  {
  packet_slug, branch, worker, tip, base, theme?,
  state: active | ready | reviewing | queued_for_hand1 | merged
       | partial_merged | integrated_publish_pending | abandoned
}
```

| Event | Mind duty |
| --- | --- |
| Hand marks done / git tip jumps | **Absorb**; add `pending_reviews` if not yet **accepted** |
| Thorough or opportunistic review | **Accept** (clear debt) or file residuals; drain backlog |
| Packet ready-to-merge mail | **Absorb** → review → **accept** or residual → `queued_for_hand1` + merge task |
| Long-term packet unit (not theme) | **Absorb**/review; next target to worker; **no** merge task to h1 |
| hand-1 idle + empty + pending_merges queued | Prefer merge task doorbell **now** |
| hand-1 idle + empty + map still open | Refill targets **and** drain review/merge debt |
| hand-1 completes merge | **Absorb** merge on main → **accept** merge (or residual) |

## Merge task body (to hand-1)

When Mind **accepts** a packet, merge task names at least:

- packet slug + root path; writable repo(s) + branch name(s)
- base checkpoint + expected tip; preferred merge order
- validation commands / bar (**two-sided green:** packet RTM certified fmt+tests; merger re-checks green on main)
- **watch-scope drift** before merge:  
  `git diff --name-only <base>..HEAD -- <watch-paths>`  
  Non-empty drift on watch paths → stop and report. Empty / only expected docs → proceed
- done-when: on main, green validation, note back to Mind (task done + optional turn-end mail)

| hand-1 state | Action |
| --- | --- |
| Idle + empty tasking | File merge task + doorbell **now** |
| Running / dirty mid-phase | File or keep `queued_for_hand1`; **do not** interrupt |
| Idle + other open targets | Merge may beat new spine if packet blocking; else queue |

After hand-1 merge done: Mind **absorbs**, then **accepts** main result (or residual). Operator may retire worktrees later.

## Adaptive scheduled cadence

Fail-fast is required, but the interval should adapt in both directions. Mind owns cadence tuning for an operator-authorized loop and does not need a new operator decision for reversible interval changes.

| Signal | Cadence action |
| --- | --- |
| 2–3 cycles with little or no new evidence, unchanged running panes, or reports too thin to justify the context cost | Lengthen one step (for example 5m → 10m → 20m) |
| Work is healthy but naturally long-running | Hold or lengthen; do not poll deep work faster merely to appear active |
| Multiple completions, addressed reports, merge decisions, or wake candidates accumulate between fires | Shorten one step (for example 20m → 10m → 5m → 3m) |
| One cycle cannot disposition the arriving work without backlog | Shorten promptly until the backlog clears |
| All scoped reports or stop conditions are complete | Cancel the loop rather than backing it off indefinitely |

`quiet_streak` remains a useful backoff hint:

| `quiet_streak` | Suggested interval |
| --- | --- |
| 0–2 | base (commonly 5m) |
| 3–5 | 2× base |
| 6–10 | 4× / ~20–30m |
| 11+ | ~1h or stop when no continuing observation duty exists |

Use judgment rather than changing cadence on one anomalous fire. When adapting a scheduler: create the replacement with the same goal, roots, authority limits, and stop condition; cancel the superseded scheduler immediately; never leave duplicate loops active; record the new scheduler id and reason in the cycle summary and baseline. Do not shorten below 3 minutes for normal Fleet supervision. An urgent addressed-mail or runtime event is handled in the current cycle, not by waiting for a cadence adjustment.

Reset `quiet_streak` on real progress: new/changed tasking, HEAD move, Status absorb, filed residual, completed unit, successful wake, or ops intervention.

Reset `turns_since_operator_message` only on **human operator** message (not product progress, board mail, successful ops, or FLEET_CYCLE itself). FLEET_CYCLE-only wake still resets if **history since last cycle** has human prose.

If the scheduler implementation cannot change an interval in place, replace it atomically enough for supervision: create the new schedule, then cancel the old one in the same cycle. If replacement is unavailable, no-op cheaply and state the limitation.

## Supervisor loops

Periodic Mind/scout only help while product moves, residuals open, or panes need liveness. Empty tasking + flat trees + healthy idle panes → quiet or back off. Do not “keep the campaign alive” with restated plateaus after Hand exited — restart Hand, select next map package, back off, or stop.
