# Tasking bag

Load when filing targets, choosing queue kind, multi-hand routing, or Hand decision continuity.

## Board kinds

Prefer a project coordination board (commonly Vivi project mailspace — see `$mail`).

| Kind | Meaning |
| --- | --- |
| **task** | Implementable work with a done condition, including defects and merge blockers |
| **need** | Decision, authority, or missing external input that can change the work |
| **want** | Non-blocking later idea (optional polish ideas that do **not** clear Mind’s post-main score threshold) |
| **mail** | Deliberation/status — not the primary queue |

**Work signal:** open tasks + open needs for the Hand = actionable work. Wants and unread mail are secondary.

## Queue kind is not severity

Choose kind by **what response is required**, then state severity in subject/body or priority metadata. Never encode severity by turning an implementable defect into a `need`.

| Question | Route |
| --- | --- |
| Can the owner implement this now from the stated invariant and done-when? | **task** — even when critical, safety-sensitive, or merge-blocking |
| Must someone choose a path, grant authority, supply input, or resolve an external dependency first? | **need** — include default + options; pivot while waiting |
| Is it safe to ship/merge without this improvement? | **want** |
| Did Mind’s post-main polish advisory clear `score_threshold` for named files? | **task** To hand-1 (or owner) — run `$polish` on those primaries only |
| Major inflection (campaign end / large merge / stage closeout) and no open housekeeping? | **task** To hand-1 — run `$housekeeping` on main (expensive; one at a time) |
| Is no action requested? | **mail** |

Put urgency on the item, not in its kind (e.g. `merge blocker: …`, `critical: …`, or the board priority field). A needs-only bag may be treated as a decision hold; misfiling defects there parks a healthy Hand.

When a need is answered: close/reply the decision item and file the resulting work as a **task**. Do not leave concrete work hidden inside a resolved need.

During iterative review, consolidate findings from the same root cause and acceptance gate into one bounded task when they share owner and validation. Split when ownership, invariant, or done-when is genuinely independent.

## Tasking rules (replace gates)

| Old gate language | Prefer |
| --- | --- |
| stage closeout GO/NO-GO | tasking empty of stage residuals; Status reflects reality |
| “NO-GO next stage” | next stage not selected / no package — file charting work or leave planned |
| dual approval thrash | one tasking bag; Hand drains; Mind refills |

Hard stop for Hand: open tasks/needs for the current assignment.  
Not a hard stop: missing Mind congratulations or “GO” mail.

## Multi-hand bags

- File targets **to a specific Hand** (`To: hand-1`), not broadcast
- One handle has one owner — do not put the same P1 on two hands
- Partition by focus (campaign track, repo, or package) when possible
- Legacy `codex` may remain readable during migration; **new** targets go to `hand-N`

**Who invents hand-2+ work vs who files it:**

| Role | Duty |
| --- | --- |
| **head-strategist** | Maintain / report a **side-lane candidate bucket** — bounded packages safe to run off main while hand-1 holds spine |
| **Mind** | Choose from that bucket (or map), bind packet, **file** tasks To hand-2+, wake/reinit, own merge clock when theme RTM |
| **hand-2+** | Execute only assigned targets in their packet cwd — never invent main spine |

Empty hand-2 + no candidates and no map side track → operational pause (record why) **or** assign strategist “what should hand-2 run in parallel?” — not silent multi-cycle empty while the INDEX has a second unblocked goal.

## Fleet priorities (main vs packet)

| Slot | Workspace role | Merge to main? |
| --- | --- | --- |
| **hand-1** | **Main checkout** (sticky workspace role — not sticky model) | **Yes** — only hand-1 merges packet branches into main (when Mind assigns it) |
| **hand-2+** | **Dynamically assigned** — usually worktree packets (`worktrees/<slug>/…`); rehome when reassigned | **Never** — commits on packet branch; unit done → refill; theme → ready-to-merge |

Rules:

1. File campaign spine to hand-1. Assign hand-2+ to operator-created worktree packets for bounded work; never put unbounded spine work there. Packet↔hand bindings are **current assignment**, not permanent types.
2. **hand-1** should run while its map has packages or residuals. Idle + empty is starvation: refill targets, queue a merge, wake/reinit by **hand-1’s current runtime**. Quiet only when map and residual bag are both empty.
3. **hand-2+** never merge/rebase/delete packet worktrees or invent main work. After a **unit**: mark done + turn-end; Mind refills next map unit (or reassigns). After a **theme** boundary: ready-to-merge mail; Mind owns merge clock.
4. Mind absorbs unit lands without merging; at theme accept creates `pending_merges` + merge task for hand-1.
5. At a clean breakpoint, wake/reinit hand-1 for merge; defer while main is mid-phase or dirty. Merge checks watch-scope drift and green-gate; absorb then accept as a separate step.
6. **Runtime vs assignment:** assignment (main vs packet) is orthogonal to **model** within a harness. **Hand harness is not free** — it follows Mind. Rebind model/launch without renaming the Hand or moving assignment; rebind Hand harness only when Mind’s harness changes or operator records an exception.

### Idle empty tasking (keep the screen moving)

| Situation | Meaning | Mind action |
| --- | --- | --- |
| **Any hand-N** idle + empty tasking + map has **unblocked** next unit | **Starvation** | File next target **same cycle** + wake/reinit |
| **hand-1** idle + empty + `pending_merges` or spine residuals | Starvation | Merge task and/or next spine targets |
| **hand-2+** just finished a **unit** (not theme) | Not success-idle | Absorb/review; **refill** next packet unit |
| **hand-2+** after **theme** ready-to-merge, empty, waiting merge | **Operational pause** | Review → accept → merge to h1; optional light pivot unit if map has unrelated work |
| **Operational pause only** | Allowed empty/hold | base-update wait · mid-unit · operator pause · map empty · hard upstream with need filed (prefer pivot if one exists) |
| Head “empty tasking” | N/A — no product tasking | Scan mail; soft-wake only if stuck; never map-refill |

Do not sleep merely because all **product** bags are empty; check the map, `pending_reviews`, and `pending_merges` first.

## Hand decision continuity

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

**Forbidden:** silent stall; “only this one thing until someone answers”; parking while other tasking items remain; treating private monologue as coordination.

## Board intake (list-first)

When on the **paid path**, after sensors fire:

```text
1. status counts
2. optional: mailspace watch --once (new events since cursor)
3. open task list for each active hand
4. open need list for each active hand
5. want list only if hunting polish by design
6. show only the selected handle
7. if exchange is multi-hop: vivi mail thread <handle> (or rely on show’s thread context)
```

**Dump is audit**, not the heartbeat. Prefer open-only dumps when needed. For Vivi CLI shapes, use `$mail`. Watch/thread detail for fleet: `dual-channel.md` (Vivi ≥ 4.6).

Product upgrades (board/brief/json):  
`~/work/ianzepp/vivarium/docs/mailspace-agent-control-plane-goal.md` and  
`~/work/ianzepp/vivarium/docs/release-v4.6.0.md`.
