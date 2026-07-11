# Head loops (advisors)

Load when running **head-strategist** / **head-correctness** / **head-purity**, or triaging Head mail as Mind.

Heads are **not** product lanes. Do not keep-screen-moving refill them with map packages. They never merge and never own `pending_merges`. Prefer **Pi + GLM 5.2 (high or xhigh)** for all advisors — one-shot assign→report, second-party opinion. See `roles-and-harness.md`. Canonical identities: `head-*` (mail + tmux). Reports **To: mind** (board only).

## head-strategist research loop (mail; every Mind cycle, fail-fast)

1. Sensors: mail list for head-strategist (or Mind inbox for `head-strategist report:`) + baseline `head_strategist.*`
2. If `head_strategist.awaiting_report` and no new report yet → **do not re-assign**; note “head-strategist in flight”; continue hands
3. If a **head-strategist report** arrived → absorb; optional triage to Hand tasks/needs; set `awaiting_report=false`
4. If **not** awaiting and ready for a new question → **clean-slate reinit + one assign**:
   1. File assignment mail **To: head-strategist** first (handle exists)
   2. Reinit head-strategist process: quit/kill current agent, **fresh** launch from fleet `head-strategist.agent_launch` in fleet cwd — not “continue old chat”
   3. Bootstrap pointer only: role prompt path, show assign handle, research, report via board **To: mind**, idle
   4. Set `awaiting_report=true`; record `last_reinit_at` + assign handle
5. Prefer mail for assignment body; short tmux pointer after reinit is OK
6. Reports may take 5–10+ minutes — **do not thrash** while outstanding

### head-strategist assignment quality (anti-fragile)

head-strategist advises ownership, sequencing, seams, gate honesty, misprioritization, and **side-lane capacity** — **not** driving product and **not** racing the tasking bag.

**Division of labor (multi-hand):**

| Who | Job |
| --- | --- |
| **Mind** | Dole out work: file/refill bags, bind packets, wake/reinit, merge clock, live coordination |
| **head-strategist** | Name **what could** run in parallel — especially a **bucket of hand-2+ (side-lane) candidates** when capacity is free |
| **Hands** | Execute assigned targets only |

Mind does not need strategist permission to file an obvious next spine unit. Strategist does not file Hand tasks or own empty-bag refill.

### Side-lane / hand-2+ capacity bucket (strategist output)

When hand-2+ exists in the fleet, strategist reports should routinely include (or be assignable to answer):

```text
## Side-lane candidates (hand-2+ if available)
- [ ] <bounded package / theme> — why safe off main; seams vs hand-1 spine; suggested packet scope
- [ ] …
## Do not parallelize
- <items that must stay on hand-1 / main>
## If all Hands busy
- hold / next priority after current spine
```

**Good bucket items:** independent factory goals, long continuous packets, bounded one-shots that do not share hot files with the current main spine, post-theme base-update planning.  
**Bad bucket items:** “whatever is free,” unbounded main spine, merge-to-main, same P0 family hand-1 is on, makework polish.

Mind **absorbs** the bucket into baseline (`side_lane_candidates` / operator_recap), then **picks and files** when hand-2 is idle+empty (or binds a packet first). Stale candidates: re-ask strategist structurally, or drop when map supersedes — do not thrash assigns every quiet cycle.

**Avoid:** questions that die if a tasking item lands while you read mail.

| File questions about… | Do not make the *core* question… |
| --- | --- |
| Who owns which seam; what hand-2+ could run in parallel | “Is handle X open right now?” |
| Real stage/gate vs static-only overclaim | Minute-by-minute merge queue alone |
| Theme vs unit cadence; fake board deps | Assumptions mid-flight unit is done/not |
| Conditional paths (“if red → …; if green → …”) | A single HEAD SHA as durable law |
| Side-lane candidate bucket vs spine | “Fill hunter-2 bag now with task Y” as if strategist were Mind |

**How to write assigns:**

1. **Structural question first** (1–3 sentences that stay meaningful for hours)
2. **Optional live snapshot** second, labeled ephemeral; tell head-strategist to re-verify
3. Prefer **conditionals** over “do X now because bag is empty”
4. Mind still acts on live bag reality; head-strategist informs *how to think* and **what parallel work is coherent**
5. When multi-hand fleet: prefer periodic assign shape “given current spine focus, what is a durable hand-2+ bucket?” over pure sequencing trivia

**head-strategist duty on stale assign:** re-read live evidence; one-line correction of stale premises; answer the structural question anyway.

## head-correctness auditor loop (self-directed) — **owns code review**

Identity/session: `head-correctness` (mail + tmux). Typical subject prefix: `head-correctness:`.

**Ownership:** head-correctness is the fleet **code-review** Head. Mind does **not** peer-review every Hand WIP. Hands still own ship quality (implement, validate, polish).

**Surface: main after merge.** Prefer reviewing **main** (or the integration line products land on) **after** theme/unit merges — not continuous multi-worktree juggling. Cross-theme bugs often appear only once multiple themes share main; that is expected under build-fast / fail-fast. Bugs on main → tasks To the Hand that owns the fix (often hand-1 for spine, or the originating packet owner if still assigned).

1. Sensors: has-session; pane class; Mind inbox for head-correctness reports; **main HEAD/dirty** for focus repos
2. Session **down** → recreate per fleet + role-prompt bootstrap (unless operator paused)
3. New report → Mind **absorbs**: triage into task/need **To owning Hand** when actionable; doorbell if idle; record baseline `head_correctness.last_report_*`; optional chat brief (problem ¶ + action ¶)
4. **Do not** assign work every cycle. Soft-wake only if stuck idle long with no recent mail — pointer only to continue next pass + role path
5. Never map-refill head-correctness as a product lane
6. Do **not** act as merge GO/NO-GO or block hand-1 merges awaiting a head-correctness stamp

## head-purity auditor loop (self-directed)

Identity/session: `head-purity`. Typical subject prefix: `head-purity:`. Often same harness class as head-strategist. **Not** clean-slate every report. Prefer **compact between passes** so context stays small.

1. Sensors: has-session; pane class; head-purity report mail
2. Down → recreate per fleet + role bootstrap
3. New report → absorb; triage simplify/design targets To owning Hand (prefer over drive-by rewrites mid-product unit); doorbell if idle and targets ready
4. Optional soft focus mail (`head-purity assign: <area>`) — not required every cycle
5. Soft-wake hygiene: compact keep identity+role+lens, then next pass; clean-slate reinit only if compact fails, confused, or operator asks
6. Never map-refill head-purity. Do not confuse with head-correctness (bugs) or head-strategist (priority/ownership / clean-slate-per-assign)
