# Mind cycle and fail-fast wake

Load for Mind interaction modes, wake loops, sensors, review, absorb/accept, and merge tasking.

## Mind interaction modes (strong guidance — not a hard ban)

Mind is the **operator-opened** harness conversation (desktop, terminal, or other). Model/reasoning tier is operator setup; do **not** require self-detection of model id. Cognitive budget follows **interaction mode**. Do not freeze useful work because a counter is awkward.

### Scheduled cycle prefix

Every durable scheduler / loop injection **must** start with:

```text
FLEET_CYCLE cycle=<N> project=<root>
```

Anything whose first line starts with `FLEET_CYCLE` is **not** an operator message. Fix camp overlays that omit this.

### Counters (write every cycle)

| Field | Meaning |
| --- | --- |
| `quiet_streak` | Consecutive cycles with no actionable product signal (fingerprint quiet) |
| `turns_since_operator_message` | Mind **cycles** since the last human operator message |
| `last_operator_message_at` | Cycle id / time of last operator prose |
| `mind_mode` | `autonomous` \| `interactive` (resolved this cycle) |
| `mind_mode_override` | optional sticky operator force (`ops_only` / `deep` / clear) |
| `operator_recap` | Compact bullet list of material changes since last operator message |

**Operator message** = human prose in the Mind session (question, instruction, review request, design chat, skill edits) — any human turn that is not a scheduled cycle injection.

**Not** operator messages: a wake whose payload is only `FLEET_CYCLE…`, other scheduler boilerplate, Hand/Head board mail, pane captures.

### Resolve mode (before sensors expand)

```text
1. If mind_mode_override set → use it (ops_only→autonomous, deep→interactive)

2. Detect engagement (do NOT only inspect the current FLEET_CYCLE payload):
   a. This turn’s user content is human prose (not FLEET_CYCLE-only) → engaged
   b. Else scan session history since last_operator_message_at
      (if null: since last_cycle_at, or “any prior human turn this session”):
      any human message that is not a FLEET_CYCLE injection → engaged
      (typical: operator asked a question between 5m loop fires)
   c. Else → not engaged

3. If engaged:
     turns_since_operator_message = 0
     last_operator_message_at = timestamp of that human message (prefer real time; else cycle id)
     mind_mode = interactive when this turn is human prose;
                 if this wake is FLEET_CYCLE-only but history engaged: keep silence=0,
                 prefer thin ops for the cycle body but do NOT treat as multi-cycle abandon
     refresh operator_recap window from that engagement point

4. If not engaged:
     turns_since_operator_message += 1
     append material events to operator_recap (short)
     if turns_since_operator_message >= 3:
       mind_mode = autonomous
     else if prior mind_mode known:
       keep prior   # turns 1–2: operator may still be watching
     else:
       mind_mode = autonomous

5. Write counters + mind_mode + operator_recap into baseline at end of cycle
```

**Anti-bug:** `FLEET_CYCLE` means “this injection is not operator prose.” It does **not** mean “ignore all human chat since the last fire.” Counting silence only from the current payload produced false `operator_silence=6` while the human was actively steering the camp between cycles.

**Threshold (guidance):** three or more Mind cycles **with no human prose in the session** → **autonomous** until the next operator message.

| Mode | Cognitive budget | **Cycle report output** |
| --- | --- | --- |
| **Autonomous** | Limited reasoning **even if** high reasoning is available. Ops: sensors, classify, file/wake/reinit, short absorb/integration-accept, sleep. **Decide now** on reversible defaults. | **Compact:** one-line quiet or short acted headline/table. Update `operator_recap` internally. |
| **Interactive** | Full reasoning for human exchanges; ops still fail-fast (no peer-review every packet). | **Rich status every FLEET_CYCLE** — operator is likely watching. Sleep/in-flight still gets multi-section status, not a one-liner. |

**Invariant:** report richness tracks `mind_mode`, not whether the cycle “acted.” Interactive + sleep-in-flight → rich. Autonomous + big absorb → still compact.

### Autonomous duties and escalation

In autonomous mode, Mind **still**:

- Runs cheap sensors and pane scan
- Refills starvation, doorbells/reinits by runtime
- Absorbs moved HEADs; files implementable residuals as **tasks**
- Uses **needs** for real decision holds (default + options), not monologue
- Updates **operator_recap** so a returning human is not amnesiac

In autonomous mode, Mind **does not**:

- Deep-plan strategy “because the model can”
- Act as post-merge **code audit** (that is **head-cto on main**)
- Wait multi-cycle on head-ceo when a safe default exists
- Freeze on class A formatter dirt without opening the diff

**Escalation ladder (cheapest first):**

| Class | Route |
| --- | --- |
| Pane/capacity/runtime | Fleet ops (reinit / ladder) **now** |
| Class A dirt / obvious residual | Style-commit or **task** To Hand **now** |
| Implementable defect | **task** To owning Hand |
| Human-only wall | **need** To operator (default + options); **pivot** other work — do not idle |
| Structural sequencing only (optional) | head-ceo assign — **do not block** product cycles waiting; decide interim default |

Waiting several cycles for head-ceo “permission” is a rules-of-engagement failure.

### Interactive duties

Full reasoning for operator questions and instructions. On **FLEET_CYCLE** while interactive: run the same cheap sensors/ops as autonomous, but emit a **rich cycle report** (below) so the operator can follow the camp without asking “what happened?”. When the human goes silent, keep counting cycles; after **≥ 3** silent cycles with no prose, drop back to autonomous (+ compact reports). Turns 1–2 of silence: they may still be monitoring — keep rich output.

### Operator recap buffer

Maintain a short list of **material** changes since `last_operator_message_at`: HEADs/merges, filed/done handles, pane ops, mode, open debt. Re-seed after `/compact`. On return phrases (“catch me up”, “what happened”, “summary”), answer from recap first. Interactive FLEET_CYCLE reports should **surface** the recap delta, not only store it.

### Interaction with thorough cycles

Thorough/superficial cadence still applies (`cycle % N == 0` for thorough). In **autonomous**, thorough is residual-shaped (diff in scope → file tasks/needs) — **not** peer code review of every packet. **head-cto** does deeper review on main after merge.

## Fail-fast wake (context budget)

Long 5–10m loops only work if most wakes **exit in seconds**. Tokens/context are scarce — not wall clock. **Fail fast to sleep** when nothing moved. Resolve **mind_mode** first, then sensors.

### Cheap sensors (always first)

```text
0. Resolve mind_mode + update turns_since_operator_message / quiet_streak inputs
1. Board status counts (e.g. vivi mailspace status)
2. Optional: vivi mailspace watch --for <Mind> --once --write-cursor (event ledger; not IMAP)
3. Open task + need lists per Hand identity (not dumps)
4. Optional light delta: git rev-parse HEAD, dirty count, map file mtime
5. Fleet: tmux has-session + short capture classify (local and/or via SSH — ssh-remote.md)
```

Compare to baseline. **Sleep immediately** when:

- fleet actionable fingerprint unchanged (hand-N only; ignore legacy codex for this)
- no relevant main/packet HEAD/dirty move
- no new mailspace watch hits (if using cursor)
- pane classes unchanged and not `error_*`
- not (hand-1 idle + empty + map/merge debt)
- not (idle + open tasking needing doorbell/**Codex reinit**)
- not (empty tasking + map next = starvation unfilled)
- `pending_reviews` / `pending_merges` empty or explicitly deferred this cycle

On **true quiet** sleep: bump `quiet_streak`, keep/update `turns_since_operator_message` and `mind_mode`, write baseline, then report by **mode** (next section). Sensors stay cheap either way — do not re-read the full campaign for a quiet autonomous wake.

Use **absorb** and **accept** accurately (never absorb when you mean accept).

Optional: thorough review every N cycles when the counter is divisible by N (e.g. `cycle % 3 == 0`); superficial otherwise. Autonomous thorough = residuals only, not interactive design.

## Cycle report templates (mode-gated)

**Choose template from `mind_mode` after resolve.** Do not use autonomous one-liners while interactive.

### Autonomous — compact (quiet or acted)

Quiet:

```text
cycle N superficial|thorough; mode=autonomous; operator_silence=K; sleep; panes ok
```

Acted (one short block max):

```text
cycle N …; mode=autonomous; acted — <one clause>
| slot | class | bag |
…tiny table optional…
debt: <one line if any>
```

No narrative paragraphs. No “what each agent is thinking.” Keep `operator_recap` updated in baseline for later catch-up.

### Interactive — rich (quiet, sleep-in-flight, or acted)

Always include enough that a watching operator understands camp state without asking:

1. **Headline** — cycle N · kind · mode=interactive · silence=K · sleep|acted · one-clause why
2. **Fleet snapshot (table)** — each Hand + Heads: pane class, bag handles/subjects or empty, one-clause status (e.g. “running P0-2 SES inbound, dirty delivery.rs”)
3. **Product / focus** — current map focus, main HEAD (+ dirty if any), notable land/WIP
4. **Board moves this cycle** — absorbed / filed / woke / none
5. **Pending debt** — open P0s, merges, polish/housekeeping notes if non-empty
6. **Heads** — idle / report outstanding / none new (brief)
7. **Since you spoke** — 2–5 bullets from `operator_recap` when non-empty (interactive only)
8. **Next** — what Mind expects next fire to see (e.g. “wait f175da0 done; then P0-3”)

Even **sleep** interactive reports use this shape (say “no board moves; h1 still running …”). Do not collapse to a single line while the operator is engaged.

**Not required in interactive FLEET_CYCLE:** full mail dumps, full campaign re-read, deep strategy essays, peer code review of WIP.

### Anti-patterns (report)

| Bad | Why |
| --- | --- |
| Interactive + one-line “sleep” | Operator cannot see WIP / debt / why idle |
| Autonomous + multi-page status every 5m | Burns context; nobody reading |
| Confusing “thin ops” with “thin report” in interactive | Ops stay fail-fast; **report** stays rich when watching |

### Expand only on signal (paid path)

| Signal | Who | Action |
| --- | --- | --- |
| New/changed open task/need | Hand | show handle → work |
| HEAD/dirty product moved | Mind | bounded residual / Status-honesty pass (not full code review) |
| Hand mid-flight dirty (main or packet) | Mind | cheap red-flag scan; obvious residuals → Vivi + pointer (not deep peer review) |
| Main moved after merge | Correctness | post-main code review / bug hunt (self-directed) |
| Main moved (merge / feature land / spine unit on main) | Mind | **Post-main polish advisory** (cheap score scan → optional polish **task**) — below |
| **Major inflection** on main (campaign end, large multi-theme merge, stage closeout) | Mind | **Housekeeping task** (expensive) — not polish; not every land — below |
| Same dirty paths block spine ≥2 cycles, no A/B/C note | Mind | **Open the diff** (half-dead); classify; file style/claim/quarantine; pivot targets for Hand |
| Map Status mtime changed | Either | skim Status lines; then bag |
| Tasking empty + next package selected | Hand / Mind | start package or **refill** + wake/reinit |
| Head report mail | Mind | absorb; triage to hand-N when actionable |
| Approach / sequencing fork | Strategist (or Mind) | one advisory report / note |
| Pane `idle_prompt` + open tasking (**Grok**) | Mind | doorbell wake |
| Pane `done_idle` / idle + open tasking (**Codex**) | Mind | **Codex reinit** |
| Theme finished + next target filed (**Grok**) | Mind | **theme-switch compact** then doorbell |
| Theme finished + next target filed (**Codex**) | Mind | **Codex reinit** |
| Pane `error_*` | Mind | ops intervene (model/retry/reinit) |
| Pane `down` | Mind | recreate session + agent; may need **new session** |

Never wake a `running` Hand merely because the bag is unchanged; Mind may review its dirty scope, but the implementation owns its active turn.

Deep work (full delivery re-read, full tests, dump) only on paid path — or when the operator asks.

## Mind cycle kinds

After cheap sensors, set `cycle = last_cycle + 1` (write at end of cycle). Cadence commonly **3–5 minutes** per fire.

### Cadence by execution shape

| Shape | Default cadence |
| --- | --- |
| **Manual / unscheduled Mind polling** | Sleep **at least 60 seconds** between unchanged checks. Shorter polling creates needless churn. |
| **Formal scheduled loop** | Fire every **3–5 minutes**: use ~3 minutes for fine-grained or fast-moving tasks and ~5 minutes for coarser work. |

Grok supports the formal scheduled-loop pattern. Codex does not currently provide that fleet pattern; when Codex is Mind, use discrete cycles separated by a shell `sleep` of at least 60 seconds. Keep each wake fail-fast regardless of cadence.

| Kind | When | Work |
| --- | --- | --- |
| **Mail interrupt** | Always first | Permission / review / Q from hands or operator → answer **same wake** |
| **Thorough (paid)** | e.g. `cycle % 3 == 0` (remainder **0**, not 1) | Residual / Status-honesty scan of product changes since `last_thorough_fingerprint` (not peer code review) |
| **Superficial** | other cycles | Red-flag scan + pane classes; sleep unless §§REDMIND§§, mail, starvation, or wake/ops |

### Superficial

Pane classes + cheap dirty/HEAD delta. If a Hand is mid-mod (dirty in their scope): quick red-flag scan; mail+pointer if needed. Sleep unless §§REDMIND§§, mail interrupt, starvation, or wake/ops.

### Thorough

Re-diff vs `last_thorough_fingerprint`. Unchanged → quiet thorough (still run pane scan). If moved: review product on **all fleet scopes** (main + each active side lane); file residuals **To owning hand-N**; update thorough fingerprint.

### Sensors (always first — keep cheap)

```text
0. Resolve mind_mode (operator message? turns_since_operator_message? override?)
1. Read baseline + fleet config (pending_reviews, pending_merges, active lanes,
   quiet_streak, turns_since_operator_message, mind_mode, watch cursor path)
2. Board status counts (vivi mailspace status)
3. Optional mailspace watch --once --write-cursor for Mind identity (Vivi ≥ 4.6)
4. Mind inbox top (advice / review / permission / advisor reports)
   # board mail ≠ operator message for mode purposes
   # paid path: vivi mail thread <handle> when lineage matters
5. Open tasks/needs for each hand-N (legacy shared identity: list only if migrating;
   do not use legacy counts for quiet/wake/starvation)
6. Main HEAD + dirty for focus repos (project names the list)
7. Each active side lane: status -sb + HEAD + branch (local or remote cwd)
8. Fleet pane scan (all hands + Heads; SSH wrap when host ≠ local — ssh-remote.md)
9. Optional: map Status line if HEAD moved
```

**Fingerprint:** fleet bags only + main HEADs/dirty + side-lane HEADs/dirty + pane classes + non-empty pending debt.

Do not parse board SQLite/blobs; use the CLI. Baseline may ignore handle prefixes for quiet detection.

### Chat summary (operator often has no live pane)

Use **Cycle report templates (mode-gated)** above. Summary:

| Mode | Quiet | Acted |
| --- | --- | --- |
| Autonomous | One line | Short headline (+ optional tiny table) |
| Interactive | Full rich template (fleet, focus, debt, recap, next) | Full rich template + board moves + Head briefs when absorbed |

When interactive and a Head report is absorbed: add 1 short ¶ problem + 1 short ¶ Mind actions (no full paste).

## Post-main polish advisory (Mind — cheap, strong guidance)

Hands still own **end-of-unit polish** on their changed sources. That slips. After work **lands on main**, Mind runs a **read-only score scan** and files bounded polish work only when scores clear a camp threshold. This is **routing**, not a quality verdict and not Mind doing `$polish` itself.

### When to run (paid, not every quiet cycle)

Run once when **main HEAD moved** this cycle relative to baseline `polish_advisory.last_scan_head` (or missing), for a focus repo:

- packet/theme **merged** to main
- spine / feature unit **committed on main** and absorbed as complete
- operator asked for a polish pass (then always allowed)

**Do not** run on pure quiet cycles, packet-only HEADs that never hit main, or when hand-1 main is mid-flight dirty on product work you are about to interrupt. Prefer after absorb of a clean main tip.

### How (cheap)

```bash
# path from $polish skill; camp may pin absolute path in fleet tooling
python3 ~/work/ianzepp/skills/polish/scripts/suggest-polish-files.py \
  --repo <main_checkout> \
  --json --limit 15
# optional: --path crates/foo for scoped landings
```

Script ranks tracked source by churn since last recognized polish commit (`polish(scope): …`, `Polish-Primary:` trailer, legacy forms). Output fields: `path`, `score`, `commits_since_polish`, line churn, `last_polish`.

| Camp key (fleet or baseline `polish_advisory`) | Default | Meaning |
| --- | --- | --- |
| `score_threshold` | **500** | File polish work only for paths with `score >= threshold` |
| `max_files_per_task` | **3** | Cap primary files in one task body |
| `max_tasks_per_cycle` | **1** | Do not flood the bag after one land |
| `script` | polish skill `scripts/suggest-polish-files.py` | Override path if needed |

Camps with **no polish history** score very high (large “never polished” penalty). Raise `score_threshold`, scope `--path`, or treat the first scan as a one-time backlog triage — do not open 20 polish tasks in one cycle.

### Act on scores

```text
1. Parse JSON; keep rows with score >= score_threshold; sort by score desc
2. Drop paths already covered by an open polish task (baseline open_polish_paths / bag subject match)
3. Take top max_files_per_task (at most max_tasks_per_cycle tasks)
4. If none → record last_scan_head + top scores in baseline; no bag file
5. If some → file a **task** (not want) To hand-1 (main checkout) — or owning Hand if path is clearly that lane’s package and still assigned
6. Done-when: run $polish on the listed primary files only; polish(scope) commits; evidence To mind
7. Doorbell/reinit only if that Hand is idle+empty or idle with this as next work — not if running product unit
8. Write baseline: last_scan_head, last_scan_at, last_top[] {path, score}, last_filed_handle?
```

**Task subject shape:** `polish advisory: <crate-or-area> (score ≥ T)`  
**Body:** explicit primary file list + scores + “`$polish` serial per file; no repo-wide cleanup; skip if inspect finds nothing useful.”

### What this is not

| Is | Is not |
| --- | --- |
| Cheap git-history metric + optional task | Mind peer-review or full `$polish` by Mind |
| Backstop when Hand end-of-unit polish slipped | Replacement for Hand polish on unit lands |
| One bounded list after main moves | Every-cycle repo-wide polish thrash |
| Score = churn-since-polish routing | “High score means bug” |

**head-cto** still owns post-main **bug** review. **head-cxo** still owns excess-layer audits. Polish advisory is ship-quality hygiene only.

## Major-inflection housekeeping (Mind — expensive, rare)

`$housekeeping` is a **full multi-phase** maintenance cycle (refresh, lint, hygiene ratchet, tests, format, docs). Cost is in the same league as a large factory goal. Treat it as an **inflection tax**, not a post-land habit.

### When to file (strong guidance)

| Inflection | Signal Mind can use |
| --- | --- |
| **Campaign / factory goal complete** | Map Status done; focus goal checkboxes closed; bags empty for that hunt |
| **Large merge batch** | Multi-theme or multi-packet merge to main, or operator-named “integrate everything” land — not a single residual commit |
| **Stage / delivery closeout** | Campaign stage flips complete; delivery graph node closed |
| **Operator ask** | Explicit “run housekeeping” / “hygiene pass on main” |

### When **not** to file

- Ordinary main unit land (use polish advisory instead)
- Every thorough cycle or every quiet streak
- Mid-spine with open product tasking (housekeeping will thrash the Hand off the map)
- Packet branch only (housekeeping targets **main checkout**)
- Open housekeeping task already exists (`housekeeping_advisory.open_handle`)
- Same `last_filed_head` / campaign id already filed (do not re-fire)

### How Mind acts

```text
1. Classify the event: inflection? or routine land?
2. If routine → polish advisory path only; skip housekeeping
3. If inflection:
   a. Prefer product bags for the closed work empty (or operator override)
   b. Main clean enough to host multi-phase work (not mid dirty product unit)
   c. File ONE task To hand-1: subject "housekeeping: <campaign|merge|stage> on main"
   d. Body: run $housekeeping on <main_checkout>; phases per skill; stop on judgment;
      evidence To mind; do not expand into new product goals
   e. Doorbell only if hand-1 idle — never interrupt a running product unit mid-turn
   f. Baseline: last_filed_at, last_filed_head, last_reason, open_handle
```

**Default owner:** hand-1 (main). Do not assign full housekeeping to packet hands.

**Ordering:** product closeout residuals and merge green-gate first; then housekeeping. Polish advisory may still run on the land (cheap); housekeeping is the coarse pass after the map chapter ends.

### Cost honesty

| Action | Relative cost | Cadence |
| --- | --- | --- |
| End-of-unit `$polish` (Hand) | Low–medium | Every product unit |
| Post-main polish advisory | Seconds (git history) | Main HEAD moves |
| `$housekeeping` | **Very high** | Major inflection only |
| Full factory goal | Very high | Map selection |

If unsure whether a merge is “large,” **default to no housekeeping** and file a need with default “defer until campaign end” — do not spend a Hand day on ambiguous “pretty big” lands.

## Residual scan (Mind) — not peer code review

Hands optimize for throughput and **own ship quality**. Mind optimizes for **bag honesty, Status honesty, and integration**. Deep **code review** is **head-cto on main after merge**.

**When to open a residual pass (bounded):**

- Thorough cycle (`cycle % N == 0` / paid path), **or**
- Superficial cycle if: new HEAD on focus repos, **or** dirty product paths, **or** Status flip without evidence

In **autonomous** mode, keep it residual-shaped and short; **decide now** on obvious residuals; do not wait on head-ceo for reversible defaults.

**How:**

1. Identify owner from fleet (main dirty → likely hand-1; packet dirty → that packet’s worker)
2. Diff only in-scope paths; cheap scan for Status lies, missing done marks, scope bleed, empty bag starvation
3. **Integration accept** (green enough): clear matching `pending_reviews` / advance packet toward merge when validation evidence and scope look honest — not a full audit
4. **Red flag residual:** file a **task** **To: hand-N**; **need** only for real decision hold; short tmux pointer
5. Do **not** paste essays into tmux. Do **not** `git` cleanup foreign WIP
6. Do **not** re-litigate style as multi-cycle freeze — class A dirt clears same turn

Safety-critical implementable findings (data loss, auth, destructive scope): high-priority **task** with fail-closed default and wake immediately.

**Status honesty (integration accept bar):** static checks and controlled manual evidence are fine **if Status says so**. Reject integration accept when Status says complete/product-run but evidence is only static or env-faked without disclosure.

## Absorb vs accept (integration)

| Term | Meaning | When | Quality bar |
| --- | --- | --- | --- |
| **Absorb** | Reconcile sensors into baseline/bag awareness | Every cycle when something moved | Low — bookkeeping honesty |
| **Accept** | Integration accept: unit/packet good enough to clear review debt, close map square, or queue merge to hand-1 | Thorough or opportunistic residual pass with honest evidence | Medium — tests/claims/scope honesty, not full code review |
| **Code review** | **head-cto** on **main after merge** | After land on main | High — bugs, fail-closed, multi-theme interactions |

| Role | Says… |
| --- | --- |
| **Hand** | Delivered / task **done** (evidence) — never “absorb” or “accept” |
| **Mind** | **Absorb** when moved; **integration accept** when evidence is honest enough to proceed |
| **head-cto** | Post-main review findings → Mind triages to tasks |
| **Operator** | May force priority |

**Anti-pattern:** writing “absorb” as if it meant accept; or Mind doing multi-page code review of every packet while head-cto idles.

## Review debt

Maintain in fleet baseline (or fleet state):

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
| Hand marks done / HEAD jumps on their scope | **Absorb**; add `pending_reviews` if not yet **accepted** |
| Thorough or opportunistic review pass | **Accept** (clear debt) or file residuals; drain backlog when possible |
| Packet ready-to-merge mail (theme or whole one-shot packet) | **Absorb** → review → **accept** or residual → state `queued_for_hand1` + merge task |
| Long-term packet unit (not theme) | **Absorb**/review; next target to worker; **no** merge task to h1 |
| hand-1 idle + empty + pending_merges queued | Prefer merge task doorbell **now** (clean breakpoint) |
| hand-1 idle + empty + map still open | Refill targets **and** drain review/merge debt |
| hand-1 completes merge | **Absorb** merge on main → **accept** merge (or residual) as its own step |

## Sensors: main + packets + fleet bags only

Cheap fingerprint should include:

1. Open tasks/needs for **each hand-N** (not legacy `codex` for quiet/wake decisions — log codex only if migration still open)
2. Main HEADs + dirty for focus repos
3. **Each active packet:** `git -C worktrees/<slug>/<writable> status` + `rev-parse HEAD` + branch name
4. Pane class per Hand

Packet dirty counts as that worker’s mid-flight WIP (residual-scan scope for Mind; not head-cto’s primary surface).

## Merge task body (to hand-1)

When Mind **accepts** a packet, the merge task should name at least:

- packet slug + root path
- writable repo(s) + branch name(s)
- base checkpoint + expected tip
- preferred merge order
- validation commands / bar (**two-sided green:** packet RTM certified fmt+tests; merger re-checks green on main after merge)
- **watch-scope drift** before merge:  
  `git diff --name-only <base>..HEAD -- <watch-paths>`  
  Main often moves while the packet is open. Non-empty drift on watch paths → stop and report. Empty / only expected doc paths → proceed
- done-when: on main, green validation, note back to Mind (task done + optional turn-end mail)

| hand-1 state | Action |
| --- | --- |
| Idle + empty tasking | File merge task + doorbell **now** |
| Running / dirty mid-phase | File or keep `queued_for_hand1`; **do not** interrupt |
| Idle + other open targets | Merge may be higher priority than new spine work if packet is blocking; else queue |

After hand-1 reports merge done: Mind **absorbs**, then **accepts** the main result (or files residual). Operator may retire worktrees later.

## Optional cadence backoff

Fail-fast is required. Interval backoff is **optional** for multi-hour idle:

| `quiet_streak` | Suggested interval |
| --- | --- |
| 0–2 | base (e.g. 5m) |
| 3–5 | 2× base |
| 6–10 | 4× / ~20–30m |
| 11+ | ~1h or sleep until operator/Hand signal |

Reset `quiet_streak` on real progress: new/changed tasking item, HEAD move, Status absorb, filed residual, completed unit, successful wake, or ops intervention.

Reset `turns_since_operator_message` only on a **human operator** message in the Mind session (not on product progress, board mail, successful ops, or FLEET_CYCLE itself). When the current wake is FLEET_CYCLE-only, still reset if **history since last cycle** contains human prose.

If the scheduler cannot change interval, still no-op cheaply each fire.

## Supervisor loops

Periodic Mind/scout only help while product moves, residuals are open, or fleet panes need liveness care. Empty tasking + flat trees + healthy idle panes → quiet or back off. Do not “keep the campaign alive” with restated plateaus after the Hand exited — restart Hand, select next map package, back off, or stop.
