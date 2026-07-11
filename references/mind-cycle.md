# Mind cycle and fail-fast wake

Load for Mind interaction modes, wake loops, sensors, review, absorb/accept, and merge tasking.

## Mind interaction modes (cognitive budget)

Mind is the **operator-opened** harness conversation (desktop or terminal). Model/reasoning tier is operator setup; do **not** require self-detection of model id. Cognitive budget follows **interaction mode**.

### Counters (write every cycle)

| Field | Meaning |
| --- | --- |
| `quiet_streak` | Consecutive cycles with no actionable product signal (fingerprint quiet) |
| `turns_since_operator_message` | Mind **cycles** since the last human operator message in this Mind conversation |
| `mind_mode` | `autonomous` \| `interactive` (resolved this cycle) |
| `mind_mode_override` | optional sticky operator force (`ops_only` / `deep` / clear) |

**Operator message** = human prose in the Mind session (question, instruction, review request, design chat).

**Not** operator messages: scheduler/cycle boilerplate (“Mind cycle N…”, fail-fast overlay text), Hand/Head board mail, pane captures, or other agents’ mail.

### Resolve mode (before sensors expand)

```text
1. If mind_mode_override set → use it (ops_only→autonomous, deep→interactive)
2. Else if this turn’s user content is an operator message:
     turns_since_operator_message = 0
     mind_mode = interactive
3. Else:
     turns_since_operator_message += 1
     if turns_since_operator_message >= 3:
       mind_mode = autonomous
     else if prior mind_mode known:
       keep prior
     else:
       mind_mode = autonomous   # default when ambiguous / first fires
4. Write counters + mind_mode into baseline at end of cycle
```

**Threshold:** three or more Mind cycles without an operator message → **autonomous** until the next operator message (reset counter to 0).

| Mode | Cognitive budget | Output shape |
| --- | --- | --- |
| **Autonomous** | Limited reasoning **even if** high reasoning is available. Ops only: sensors, classify, file/wake/reinit, short absorb/accept, sleep. | One-line quiet or short table. No campaign essays. |
| **Interactive** | Full reasoning allowed for the operator exchange; still owns bag + panes. | Answer the human; may be longer. |

### Autonomous duties and escalation

In autonomous mode, Mind **still**:

- Runs cheap sensors and pane scan
- Refills starvation, doorbells/reinits by runtime
- Absorbs moved HEADs; files implementable residuals as **tasks**
- Uses **needs** for real decision holds (default + options), not monologue

In autonomous mode, Mind **does not**:

- Deep-plan strategy “because the model can”
- Write multi-page residual reviews on a quiet or lightly moved fingerprint
- Treat high reasoning availability as permission to expand context

When autonomous Mind hits structural judgment it cannot cheaply resolve:

| Class | Route |
| --- | --- |
| Sequencing / ownership / gate honesty / misprioritization | **Strategist** assign (or await outstanding report) |
| Implementable defect / residual | **task** To owning Hand |
| Human-only wall | **need** To operator (default + options); pivot other work |
| Pane/capacity/runtime | Fleet ops (reinit / ladder) — not a Head report |

### Interactive duties

Full reasoning for operator questions and instructions. May run a cheap fleet scan in the same turn. When the human goes silent, keep counting cycles; after **≥ 3** silent cycles, drop back to autonomous on subsequent wakes.

### Interaction with thorough cycles

Thorough/superficial cadence still applies. In **autonomous**, thorough stays **bounded and residual-shaped** (diff in scope → file tasks/needs); do not spend a full interactive design pass. In **interactive**, operator questions may expand beyond the thorough template.

## Fail-fast wake (context budget)

Long 5–10m loops only work if most wakes **exit in seconds**. Tokens/context are scarce — not wall clock. **Fail fast to sleep** when nothing moved. Resolve **mind_mode** first, then sensors.

### Cheap sensors (always first)

```text
0. Resolve mind_mode + update turns_since_operator_message / quiet_streak inputs
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

On **true quiet** sleep: bump `quiet_streak`, keep/update `turns_since_operator_message` and `mind_mode`, write baseline, **one-line** report  
(`quiet N; mode=autonomous|interactive; operator_silence=K; absorb/accept as accurate; panes ok; sleep`).  
No dump, no full campaign re-read, no harness matrix, no priority essay.

When the cycle **acted**, emit a **scannable summary**:

1. Headline: cycle N · mode · superficial|thorough · absorb/accept verbs accurate
2. Fleet snapshot: each Hand pane class + bag handles + one-clause status
3. Board moves: filed / done / merged handles
4. Head briefs when mail absorbed: 1 short ¶ problem + 1 short ¶ action
5. Pending debt if non-empty

Use **absorb** and **accept** accurately (never absorb when you mean accept).

Optional: thorough review every N cycles when the counter is divisible by N (e.g. `cycle % 3 == 0`); superficial otherwise — §§REDMIND§§s + mail + starvation only. Autonomous thorough = residuals only, not interactive design.

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

Never wake a `running` Hand merely because the bag is unchanged; Mind may review its dirty scope, but the implementation owns its active turn.

Deep work (full delivery re-read, full tests, dump) only on paid path — or when the operator asks.

## Mind cycle kinds

After cheap sensors, set `cycle = last_cycle + 1` (write at end of cycle). Cadence commonly **3–5 minutes** per fire.

| Kind | When | Work |
| --- | --- | --- |
| **Mail interrupt** | Always first | Permission / review / Q from hands or operator → answer **same wake** |
| **Thorough (paid)** | e.g. `cycle % 3 == 0` (remainder **0**, not 1) | Residual + code review of product changes since `last_thorough_fingerprint` |
| **Superficial** | other cycles | Red-flag scan + pane classes; sleep unless §§REDMIND§§, mail, starvation, or wake/ops |

### Superficial

Pane classes + cheap dirty/HEAD delta. If a Hand is mid-mod (dirty in their scope): quick red-flag scan; mail+pointer if needed. Sleep unless §§REDMIND§§, mail interrupt, starvation, or wake/ops.

### Thorough

Re-diff vs `last_thorough_fingerprint`. Unchanged → quiet thorough (still run pane scan). If moved: review product on **all fleet scopes** (main + each active side lane); file residuals **To owning hunter-N**; update thorough fingerprint.

### Sensors (always first — keep cheap)

```text
0. Resolve mind_mode (operator message? turns_since_operator_message? override?)
1. Read baseline + fleet config (pending_reviews, pending_merges, active lanes,
   quiet_streak, turns_since_operator_message, mind_mode)
2. Board status counts (vivi mailspace status)
3. Mind inbox top (advice / review / permission / advisor reports)
   # board mail ≠ operator message for mode purposes
4. Open tasks/needs for each hunter-N (legacy shared identity: list only if migrating;
   do not use legacy counts for quiet/wake/starvation)
5. Main HEAD + dirty for focus repos (project names the list)
6. Each active side lane: status -sb + HEAD + branch
7. Fleet pane scan (all hands + Heads if configured)
8. Optional: map Status line if HEAD moved
```

**Fingerprint:** fleet bags only + main HEADs/dirty + side-lane HEADs/dirty + pane classes + non-empty pending debt.

Do not parse board SQLite/blobs; use the CLI. Baseline may ignore handle prefixes for quiet detection.

### Chat summary (operator often has no live pane)

When the cycle **acted**:

1. **Headline** — `cycle N kind; mode=…; operator_silence=K; absorb/accept accurate; sleep|acted`
2. **Fleet snapshot** — each Hand + Heads: pane class, bag handles or empty, notable HEAD if moved, one-clause status
3. **Board moves** — absorbed / accepted / filed / woke (handles + subjects)
4. **Pending debt** — `pending_merges` / `pending_reviews` if non-empty
5. **Strategist status** — awaiting_report? assign handle? reinit this cycle?
6. **Strategist report brief** (new report absorbed) — 1 short ¶ problem + 1 short ¶ recommended Mind actions; optional stale-premise correction; no full paste
7. **Correctness / purity** status + brief when new report absorbed

Quiet true sleep may stay one-line (include `mode` + `operator_silence`). Prefer tables for the fleet snapshot.

## Proactive review (Mind)

Hands optimize for throughput; Mind optimizes for **invariant honesty**.

**When to open a review pass (bounded):**

- Thorough cycle (`cycle % N` / paid path), **or**
- Superficial cycle if: new HEAD on focus repos, **or** dirty product paths in a hunter’s allowed scope, **or** Status flip without evidence

In **autonomous** mode, keep the pass residual-shaped and short; escalate structural forks to strategist/needs rather than expanding into interactive design.

**How:**

1. Identify owner from fleet (main dirty → likely hunter-1; packet dirty → that packet’s worker; if ambiguous, say so in mail)
2. Diff only in-scope paths (`git diff`, packet branch log, key tests/claims)
3. Look for §§REDMIND§§s: fail-open, dual ABI/dialect, tests weaker than Status, scope bleed, silent env fakes, docs lying, **Status complete while evidence is only static/manual without saying so**
4. **Accept** (green): clear matching `pending_reviews` / advance packet toward merge; optional baseline note
5. **Red flag:** file a **task** **To: hunter-N** with where, why, done-when. Use a **need** only for real decision/authority/input hold; then tmux pointer e.g. `HAND WAKE hunter-2. Bag: show <handle>. vivi --for hunter-2. Continue.`
6. Do **not** paste the full review into tmux. Do **not** `git` cleanup foreign WIP

Mid-flight review is **advisory + residual**, not a stop stamp. For safety-critical implementable findings (data loss, auth, destructive scope), file a high-priority **task** with a fail-closed default and wake immediately. Use a **need** only when the safe fix requires a decision, authority, or external input.

**Status honesty (accept bar):** static checks, node contract tests, and “controlled manual browser/GPU inspection” are fine **if Status says so**. Reject **accept** when Status says complete/product-run but evidence is only static or env-faked.

## Absorb vs accept

| Term | Meaning | When | Quality bar |
| --- | --- | --- | --- |
| **Absorb** | Reconcile sensors into baseline/bag awareness: notice HEAD/done/Status, stop re-discovering, update fingerprints | Every cycle when something moved | Low — bookkeeping honesty |
| **Accept** | After code review, treat the unit/packet as good enough: clear review debt, allow map square closeout, unblock dependents, or queue merge to hunter-1 | Thorough or opportunistic review with evidence | High — invariants, tests vs claims, scope |

| Role | Says… |
| --- | --- |
| **Hand** | Delivered / task **done** (evidence) — never “absorb” or “accept” |
| **Mind** | **Absorb** always when moved; **accept** only after review |
| **Operator** | May force priority; day-to-day accept stays Mind |

**Anti-pattern:** writing “absorb” in a cycle line as if it meant **accept** (Status + subject only, then file next package as green).

Routing next target after absorb is fine **if** unreviewed work stays on `pending_reviews` until **accept** (or residuals are filed).

## Review debt

Maintain in fleet baseline (or fleet state):

```text
pending_reviews[]: { hunter, range or shas, paths, reason, since_cycle, status }
pending_merges[]:  {
  packet_slug, branch, worker, tip, base, theme?,
  state: active | ready | reviewing | queued_for_h1 | merged
       | partial_merged | integrated_publish_pending | abandoned
}
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

## Sensors: main + packets + fleet bags only

Cheap fingerprint should include:

1. Open tasks/needs for **each hunter-N** (not legacy `codex` for quiet/wake decisions — log codex only if migration still open)
2. Main HEADs + dirty for focus repos
3. **Each active packet:** `git -C worktrees/<slug>/<writable> status` + `rev-parse HEAD` + branch name
4. Pane class per Hand

Packet dirty counts as that worker’s mid-flight WIP (proactive review scope).

## Merge task body (to hunter-1)

When Mind **accepts** a packet, the merge task should name at least:

- packet slug + root path
- writable repo(s) + branch name(s)
- base checkpoint + expected tip
- preferred merge order
- validation commands / bar (**two-sided green:** packet RTM certified fmt+tests; merger re-checks green on main after merge)
- **watch-scope drift** before merge:  
  `git diff --name-only <base>..HEAD -- <watch-paths>`  
  Main often moves while the packet is open. Non-empty drift on watch paths → stop and report. Empty / only expected doc paths → proceed
- done-when: on main, green validation, note back to reviewer

| hunter-1 state | Action |
| --- | --- |
| Idle + empty tasking | File merge task + doorbell **now** |
| Running / dirty mid-phase | File or keep `queued_for_h1`; **do not** interrupt |
| Idle + other open targets | Merge may be higher priority than new spine work if packet is blocking; else queue |

After hunter-1 reports merge done: Mind **absorbs**, then **accepts** the main result (or files residual). Operator may retire worktrees later.

## Optional cadence backoff

Fail-fast is required. Interval backoff is **optional** for multi-hour idle:

| `quiet_streak` | Suggested interval |
| --- | --- |
| 0–2 | base (e.g. 5m) |
| 3–5 | 2× base |
| 6–10 | 4× / ~20–30m |
| 11+ | ~1h or sleep until operator/hunter signal |

Reset `quiet_streak` on real progress: new/changed tasking item, HEAD move, Status absorb, filed residual, completed unit, successful wake, or ops intervention.

Reset `turns_since_operator_message` only on a **human operator** message (not on product progress, board mail, or successful ops).

If the scheduler cannot change interval, still no-op cheaply each fire.

## Supervisor loops

Periodic Mind/scout only help while product moves, residuals are open, or fleet panes need liveness care. Empty tasking + flat trees + healthy idle panes → quiet or back off. Do not “keep the campaign alive” with restated plateaus after the Hand exited — restart hunter, select next map package, back off, or stop.
