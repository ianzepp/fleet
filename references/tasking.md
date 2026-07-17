# Tasking bag

Filing targets, queue kind, multi-hand routing, Hand decision continuity.

Board CLI: [`vivi.md`](vivi.md). Install: `getting-started.md`.

## Board kinds

| Kind | Meaning |
| --- | --- |
| **task** | Implementable work with done condition (incl. defects, merge blockers) |
| **need** | Decision, authority, or missing external input that can change the work |
| **want** | Non-blocking later idea (optional polish that does **not** clear Mind’s post-main score threshold) |
| **mail** | Deliberation/status — not the primary queue |

**Work signal:** open tasks + open needs = actionable. Wants and unread mail are secondary.

## Queue kind is not severity

Choose kind by **what response is required**, then state severity in subject/body or priority. Never encode severity by turning an implementable defect into a `need`.

| Question | Route |
| --- | --- |
| Can the owner implement now from stated invariant + done-when? | **task** — even when critical, safety-sensitive, or merge-blocking |
| Must a **Hand or Mind** choose a path, grant authority, or resolve external dependency first? | **need** To that agent — default + options; pivot while waiting |
| Must the **human operator** choose, grant credentials/policy, or give bug-fix guidance? | **need or mail To `operator@`** — not mind board noise; [`operator-mail.md`](operator-mail.md) |
| Problem / critical blocker / bug needing human guidance while autonomous? | **operator@** (not status, not Hand done) |
| Safe to ship/merge without this improvement? | **want** |
| Mind post-main polish advisory cleared `score_threshold` for named files? | **task** To hand-1 (or owner) — `$polish` on those primaries only |
| Major inflection (campaign end / large merge / stage closeout) and no open housekeeping? | **task** To hand-1 — `$housekeeping` on main (expensive; one at a time) |
| No action requested (deliberation only)? | **mail** To relevant board identity — **not** To `operator` |

Urgency on the item, not kind. Needs-only bag may be treated as decision hold; misfiling defects there parks a healthy Hand.

When a need is answered: close/reply the decision; file resulting work as a **task**. Do not leave concrete work hidden inside a resolved need.

### To: routing

| To | Use for |
| --- | --- |
| **`hand-N`** | Product work the Hand drains (tasks/needs) |
| **`mind`** | Fleet board: done/evidence, Head reports, RTM, bag bookkeeping |
| **`operator`** | Human-only escalations: problems, critical blockers, bugs needing guidance |
| **Heads** | Assigns / research — reports come back To mind |

Never **task** To `operator`. Prefer subject prefixes `operator: problem|blocker|bug-guidance|need — …`.

During iterative review, consolidate findings from the same root cause + acceptance gate into one bounded task when they share owner and validation. Split when ownership, invariant, or done-when is genuinely independent.

## Tasking rules (replace gates)

| Old gate language | Prefer |
| --- | --- |
| stage closeout GO/NO-GO | tasking empty of stage residuals; Status reflects reality |
| “NO-GO next stage” | next stage not selected / no package — file charting work or leave planned |
| dual approval thrash | one tasking bag; Hand drains; Mind refills |

Hard stop for Hand: open tasks/needs for current assignment.  
Not a hard stop: missing Mind congratulations or “GO” mail.

## Multi-hand bags

- File targets **to a specific Hand** (`To: hand-1`), not broadcast
- One handle → one owner — do not put the same P1 on two hands
- Partition by focus (campaign track, repo, or package) when possible
- Legacy `codex` may remain readable during migration; **new** targets go to `hand-N`
- In multi-repo containers, prefer **hand-1** as the dedicated main/integration lane and **hand-2..hand-4** as floaters. This is a strong default, not a requirement: operator direction and fleet config can pin any hand differently.
- Floaters may run in parallel only when their writable repo/worktree scopes do not overlap. If two ready units touch the same repo, serialize them, choose a different repo for one floater, or record a dependency defer.
- A floater assignment is per unit/theme, not an identity promise. After a unit lands, Mind may refill that same hand from any non-overlapping ready repo lane.

| Role | Duty |
| --- | --- |
| **head-ceo** | Maintain / report **side-lane candidate bucket** with **effort + est_tokens** — bounded packages safe off main |
| **Mind** | Choose from bucket (or map) using size + calibration; bind packet; **file** tasks; wake/reinit; record actual vs est |
| **hand-2+** | Execute only assigned targets in packet cwd or assigned repo — never invent main spine |

Empty floater + no non-overlapping candidates and no map side track → operational pause (record why) **or** assign head-ceo “what should the floater pool run in parallel (with cost ballparks)?” — not silent multi-cycle empty while INDEX has a second unblocked goal.

**Estimates = head-ceo-owned; calibration = Mind-owned.** Hands do not invent token math. Optional: Hand turn-end notes harness usage **if the TUI surfaces it**. **Codex TUI** often has no reliable token counter → Mind writes `actual_source=unavailable` (or `mind_estimate`) — never fabricated `actual_tokens`.

## Stale task disposition

An old open task is not durable lane memory. When lane reconciliation proves it
no longer describes executable work, Mind must choose one explicit disposition:

| Reality | Board action |
| --- | --- |
| Work remains and is unblocked | Close/supersede the stale task with evidence; file a fresh bounded task and wake/rebind |
| Human/authority decision blocks work | File/link a `need`; close the executable task with the blocker handle in its note |
| Work is intentionally deferred | File/link a `want`; close the task as superseded by that want |
| Work completed | Mark done with commit/validation/integration evidence |
| Task premise is false or obsolete | Mark done with `obsolete`/`superseded` note and the authoritative replacement |

Never leave a task open merely to remember that a campaign or lane once
existed. Campaign/factory artifacts hold map truth; baseline holds lane state;
Vivi tasks hold currently executable work.

Vivi has no separate `superseded` task state. Close explicitly and preserve the
replacement in the event ledger:

```bash
vivi task done --project "$ROOT" --for <hand> <handle> \
  --note 'superseded by <task|need|want handle>: <reason and evidence>'
```

## Fleet priorities (main vs packet)

| Slot | Workspace role | Merge to main? |
| --- | --- | --- |
| **hand-1** | **Main checkout / integration lane** (sticky workspace role — not sticky model) | **Yes** — only hand-1 merges packet branches (when Mind assigns) |
| **hand-2..hand-4** | **Recommended floater pool** — dynamically assigned by repo/worktree; rehome when reassigned | **Never** — commits on assigned repo/packet branch; unit done → refill; theme → ready-to-merge |
| **hand-5+** | Fleet-specific extra capacity; follow explicit config/operator policy | Usually never, unless fleet config says otherwise |

1. File campaign spine and integration work to hand-1. Assign hand-2..hand-4 as floaters to bounded repo/worktree packets; never unbounded spine there. Packet↔hand bindings are **current assignment**, not permanent types.
2. **hand-1** runs while map has packages or residuals. Idle + empty = starvation: refill, queue merge, wake/reinit by **hand-1’s current runtime**. Quiet only when map and residual bag both empty.
3. **hand-2..hand-4** floaters never merge/rebase/delete packet worktrees or invent main work. After **unit**: mark done + turn-end; Mind refills the next non-overlapping map unit (or reassigns). After **theme** boundary: ready-to-merge mail; Mind owns merge clock.
4. Mind absorbs unit lands without merging; at theme accept creates `pending_merges` + merge task for hand-1.
5. At clean breakpoint, wake/reinit hand-1 for merge; defer while main mid-phase or dirty. Merge checks watch-scope drift and green-gate; absorb then accept as separate step.
6. **Runtime vs assignment:** assignment orthogonal to **model** within harness. **Hand harness is not free** — follows Mind. Rebind model/launch without renaming Hand or moving assignment; rebind Hand harness only when Mind’s harness changes or operator records exception.

### Idle empty tasking

Posture (`fleet_posture.mode`) gates whether empty bags are a problem — [`fleet-posture.md`](fleet-posture.md).

| Situation | Meaning | Mind action |
| --- | --- | --- |
| **Any hand-N** idle + empty + map has **unblocked product** unit + posture allows (`growth` or missing) | **Starvation** | File next target **same cycle** + wake/reinit |
| **Posture `standby` or `dormant`** + empty bags | **On-call / paused** | **Sleep** — do not invent work; quiet is success |
| **hand-N** idle + empty + packet `paused*` / baseline `operational_pauses` | **Operational pause** | Do **not** treat `starvation_candidate_*` alone as act — refill only when unpausing |
| **hand-1** idle + empty + `pending_merges` or spine residuals | Starvation | Merge task and/or next spine targets |
| **hand-2+** just finished a **unit** (not theme) | Not success-idle | Absorb/review; **refill** next **product** map unit (or reassign) |
| **hand-2..hand-4** idle + empty + ready work exists only in a repo already being written by another Hand | Valid dependency / write-scope pause | Do not stack overlapping work; choose a different ready repo, serialize, or record defer |
| **hand-2+** after **theme** RTM, empty, waiting merge | **Operational pause** | Review → accept → merge to h1; optional light pivot if map has unrelated **product** work |
| **growth** + empty bags + map empty / only makework / value unclear | **Continuity doubt** | **Do not invent polish**; sleep or one head-ceo continuity consult (continue vs pause) |
| **Operational pause only** | Allowed empty/hold | base-update wait · mid-unit · operator pause · map empty · hard upstream with need filed (prefer pivot) |
| Head “empty tasking” | N/A — no product tasking | Scan mail; soft-wake only if stuck; never map-refill |

**Ban:** invent work (including polish/HK loops) to keep Hands busy or to silence sensors.

Do not sleep merely because bags are empty **if** map still has unblocked **product** work (and posture allows). Do sleep when bags empty **and** no honest product next — check map, `pending_reviews`, `pending_merges`, then posture.

## Hand decision continuity

**Unsent questions do not exist.** Other agents only see the board and commits.

| Situation | Required action |
| --- | --- |
| Path / name / scope / order / ABI / package / stop (agent can default) | Same turn: **need or mail** to Mind with **default + options** |
| Path / policy / bug-fix **needs human** | **need/mail To `operator@`** (or To mind → Mind refiles operator); **pivot** |
| Filename / docs layout only | Campaign convention or default in the need; keep working |
| Waiting for a reply | **Switch targets** — do not freeze |
| Human-only wall | Send the need first, then switch targets |

**Never idle when other targets exist.** One blocked topic must not freeze the hunt:

1. Externalize if decision
2. Immediately select another open task/need or next map package
3. Sleep when actionable tasking empty **and** no honest next **product** map unit (or posture standby/dormant)

Second-best **product** progress beats zero. Context switch is required. Invented polish is not progress.

**Forbidden:** silent stall; “only this one thing until someone answers”; parking while other **product** tasking remains; treating private monologue as coordination; polish thrash for continuity.

## Board intake (list-first)

Paid path, after sensors:

```text
1. status counts
2. optional: mailspace watch --once (new events since cursor)
3. open task list for each active hand
4. open need list for each active hand
5. want list only if hunting polish by design
6. show only the selected handle
7. if multi-hop: vivi mail thread <handle> (or show’s thread context)
```

**Dump is audit**, not heartbeat. Prefer open-only dumps. CLI shapes: `companion-fallbacks.md`. Watch/thread: `dual-channel.md` (Vivi ≥ 4.6).
