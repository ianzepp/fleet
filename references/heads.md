# Head loops (advisors)

Load when running strategist / correctness / purity, or triaging Head mail as Mind.

Heads are **not** product lanes. Do not keep-screen-moving refill them with map packages. They never merge and never own `pending_merges`. Prefer **Pi + GLM 5.2 (high or xhigh)** for all advisors — one-shot assign→report, second-party opinion. See `roles-and-harness.md`.

## Strategist research loop (mail; every Mind cycle, fail-fast)

1. Sensors: mail list for strategist (or Mind inbox for `strategist report:`) + baseline `strategist.*`
2. If `strategist.awaiting_report` and no new report yet → **do not re-assign**; note “strategist in flight”; continue hunters
3. If a **strategist report** arrived → absorb; optional triage to Hand tasks/needs; set `awaiting_report=false`
4. If **not** awaiting and ready for a new question → **clean-slate reinit + one assign**:
   1. File assignment mail **To: strategist** first (handle exists)
   2. Reinit strategist process: quit/kill current agent, **fresh** launch from fleet `strategist.agent_launch` in fleet cwd — not “continue old chat”
   3. Bootstrap pointer only: role prompt path, show assign handle, research, report via board To Mind, idle
   4. Set `awaiting_report=true`; record `last_reinit_at` + assign handle
5. Prefer mail for assignment body; short tmux pointer after reinit is OK
6. Reports may take 5–10+ minutes — **do not thrash** while outstanding

### Strategist assignment quality (anti-fragile)

Strategist advises ownership, sequencing, seams, gate honesty, misprioritization — **not** driving product and **not** racing the tasking bag.

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

**Strategist duty on stale assign:** re-read live evidence; one-line correction of stale premises; answer the structural question anyway.

## Correctness auditor loop (self-directed)

Identity/session separate from hunter-N. Typical subject prefix: `correctness:`.

1. Sensors: has-session; pane class; Mind inbox for correctness reports
2. Session **down** → recreate per fleet + role-prompt bootstrap (unless operator paused)
3. New report → **absorb**: triage into task/need **To owning Hand** when actionable; doorbell if idle; record `correctness.last_report_*`; optional chat brief (problem ¶ + action ¶)
4. **Do not** assign work every cycle. Soft-wake only if stuck idle long with no recent mail — pointer only to continue next pass + role path
5. Never map-refill correctness as a product lane

## Purity auditor loop (self-directed)

Identity/session separate. Typical subject prefix: `purity:`. Often same harness class as strategist. **Not** clean-slate every report. Prefer **compact between passes** so context stays small.

1. Sensors: has-session; pane class; purity report mail
2. Down → recreate per fleet + role bootstrap
3. New report → absorb; triage simplify/design targets To owning Hand (prefer over drive-by rewrites mid-product unit); doorbell if idle and targets ready
4. Optional soft focus mail (`purity assign: <area>`) — not required every cycle
5. Soft-wake hygiene: compact keep identity+role+lens, then next pass; clean-slate reinit only if compact fails, confused, or operator asks
6. Never map-refill purity. Do not confuse with correctness (bugs) or strategist (priority/ownership / clean-slate-per-assign)
