# Head loops (advisors)

Load when running **head-ceo** / **head-cto** / **head-cxo**, or triaging Head mail as Mind.

**Cast + personas:** [`heads/cast.md`](heads/cast.md), [`heads/personas/`](heads/personas/). Load persona only when assigning that Head for depth — not every FLEET_CYCLE.

| Hard rule | |
| --- | --- |
| Not product lanes | No keep-screen-moving refill with map packages |
| No merge | Never own `pending_merges` |
| Harness | Prefer **Pi + GLM 5.2 (high/xhigh)** — one-shot assign→report |
| Identity | `head-*` (mail + tmux when armed) |
| Reports | **To: mind** (board only) |

See `roles-and-harness.md`.

## head-ceo research loop (mail; every Mind cycle, fail-fast)

1. Sensors: head-ceo mail (or Mind inbox for `head-ceo report:`) + baseline `head_ceo.*`
2. `awaiting_report` + no report → **do not re-assign**; note in flight; continue hands
3. Report arrived → absorb; optional triage to Hand tasks/needs; `awaiting_report=false`
4. Not awaiting + ready for new question → **clean-slate reinit + one assign**:
   1. File assignment mail **To: head-ceo** first (handle exists)
   2. Quit/kill agent; **fresh** launch from fleet `head-ceo.agent_launch` — not continue old chat
   3. Bootstrap pointer: role prompt path, show assign handle, research, report **To: mind**, idle
   4. `awaiting_report=true`; record `last_reinit_at` + assign handle
5. Prefer mail for body; short tmux pointer after reinit OK
6. Reports 5–10+ min — **do not thrash** while outstanding

### Assignment quality (anti-fragile)

Advises ownership, sequencing, seams, gate honesty, misprioritization, **side-lane capacity** — not driving product or racing the bag.

| Who | Job |
| --- | --- |
| **Mind** | Dole work; pack capacity; record est vs actual calibration |
| **head-ceo** | Side-lane **bucket** with effort + est_tokens; sequencing/vision — not bag drain |
| **Hands** | Execute assigned targets only |

Mind needs no head-ceo permission for obvious next spine unit. head-ceo does not file Hand tasks or own empty-bag refill.

### Side-lane / hand-2+ capacity bucket

When hand-2+ exists, reports should routinely include:

```text
## Side-lane candidates (hand-2+ if available)
- [ ] <bounded package / theme>
      why off-main: …
      seams vs hand-1 spine: …
      packet scope: …
      effort: S|M|L|XL
      est_tokens: ~N
      est_basis: one line
- [ ] …
## Do not parallelize
- <items that must stay on hand-1 / main>
## If all Hands busy
- hold / next priority after current spine
```

| `effort` | Shape | Rough `est_tokens` |
| --- | --- | --- |
| **S** | One crate/file family, clear done-when | ~50k–150k |
| **M** | Multi-file feature, normal validate | ~150k–400k |
| **L** | Multi-crate / multi-unit theme, fix loops likely | ~400k–1M |
| **XL** | Campaign-scale packet | ~1M+ (prefer split; say why) |

Bands = **routing hints**. Prefer ranges; uncertain → estimate high. **Do not omit cost** on side-lane buckets.

| Good bucket items | Bad |
| --- | --- |
| Independent factory goals, long packets, bounded one-shots off hot files, post-theme base-update planning | “whatever is free,” unbounded main spine, merge-to-main, same P0 as hand-1, makework polish |

### Mind: absorb bucket + cost calibration

1. Absorb into `side_lane_candidates[]` with `effort`/`est_tokens`/`est_basis`
2. Pick/file when hand-2 idle+empty; match size to free capacity + recent calibration
3. Bound → `status:bound`, `filed_handle`, `filed_at`
4. On Hand done/theme absorb → record actuals when known (`actual_source=harness|mind_estimate|unavailable`). Codex often → `unavailable` — do not invent numbers
5. Append `cost_calibration[]` `{est, actual_tokens?, actual_source, delta_ratio?, models, …}` — omit `delta_ratio` if actual unknown
6. Bias later picks with recent deltas — inform, don’t hard-block
7. Stale candidates: re-ask or drop — no thrash every quiet cycle

**head-ceo** owns estimates. **Mind** owns actuals + calibration.

| File questions about… | Do not make *core* question… |
| --- | --- |
| Who owns which seam; what hand-2+ could parallelize | “Is handle X open right now?” |
| Real stage/gate vs static overclaim | Minute-by-minute merge queue alone |
| Theme vs unit cadence; fake board deps | Assumptions mid-flight unit is done/not |
| Conditionals (“if red → …; if green → …”) | A single HEAD SHA as durable law |
| Side-lane bucket vs spine | “Fill hand-2 bag now with task Y” as if head-ceo were Mind |

**Assigns:** (1) structural question first (hours-stable) (2) optional live snapshot labeled ephemeral (3) conditionals over “do X now because bag empty” (4) Mind acts on live bag; head-ceo informs how to think + coherent parallel work (5) multi-hand: prefer “durable hand-2+ bucket **with effort + est_tokens**?”

**Stale assign duty:** re-read live evidence; one-line correction; answer structural question anyway.

## head-cto auditor loop (self-directed) — **owns code review**

Identity: `head-cto`. Subject: `head-cto:`. Persona: CTO. Fleet **code-review** Head — Mind does **not** peer-review every Hand WIP. Hands own ship quality.

**Surface: main after merge** (not continuous multi-worktree juggling). Cross-theme bugs often appear only on shared main. Bugs on main → task To owning Hand (hand-1 for spine, or packet owner if still assigned).

1. Sensors: has-session; pane class; Mind inbox for reports; **main HEAD/dirty**
2. Session **down** → recreate + role-prompt bootstrap (unless operator paused)
3. New report → absorb; triage task/need **To owning Hand**; doorbell if idle; baseline `head_cto.last_report_*`; optional chat brief
4. **Do not** assign every cycle. Soft-wake only if stuck idle long, no recent mail — pointer + role path
5. Never map-refill as product lane
6. Do **not** act as merge GO/NO-GO or block hand-1 merges awaiting stamp

## head-cxo auditor loop (self-directed) — **complexity / purity**

Identity: `head-cxo`. Subject: `head-cxo:`. Persona: [`heads/personas/cxo.md`](heads/personas/cxo.md). Prefer **compact between passes** — not clean-slate every report.

**CXO ≠ operator voice.** Mind owns operator recap/email. head-cxo audits **shape debt** only. Complexity hardens execution → idiot-proof structure (`heads/cast.md`).

1. Sensors: has-session; pane class; report mail
2. Down → recreate + role bootstrap
3. New report → absorb; triage simplify/design To owning Hand (prefer over drive-by mid-unit rewrites); doorbell if idle + targets ready
4. Optional soft focus mail (`head-cxo assign: <area>`) — not every cycle
5. Soft-wake: compact keep identity+role+lens → next pass; clean-slate only if compact fails, confused, or operator asks
6. Never map-refill. ≠ head-cto (bugs) or head-ceo (priority / clean-slate-per-assign)
7. Never draft operator email or act as second Mind pane
