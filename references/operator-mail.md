# Operator mail

Two directions. Both are **cheap-cycle** surfaces for Mind — not optional deep reads.

| Direction | Path | Meaning |
| --- | --- | --- |
| **To operator@** | mind/hands → human | Escalations waiting on the human (problems/blockers/needs) |
| **From operator@ → mind@** | human → Mind | Decisions / feedback / charter notes Mind must **absorb first** |

Distinct from `operator_recap` (chat memory of status while operator was away).

Human chat remains the natural interactive surface, but any operator statement
that changes Fleet scope, priority, policy, acceptance, or routing must be
recorded in Vivi before dependent role work starts. The Mind creates or replies
to the appropriate operator/mind handle and uses that handle as the primary
reference. Chat supports the record; it is not the only historical account.

## Identity

| Field | Value |
| --- | --- |
| **Identity token** | `operator` |
| **Mail** | `operator@<mailspace>.local` |
| **tmux** | **none** (same class as `mind` — not a process slot) |
| **Process** | Human operator (chat **or** board mail To mind) |

```bash
vivi mailspace identity add operator --project <root>
```

CLI list/send: [`vivi.md`](vivi.md).

```json
{
  "operator_inbox": "operator",
  "operator_inbox_note": "Human-facing escalations only. Not status. No tmux."
}
```

```json
{
  "operator_mail": {
    "identity": "operator",
    "open_count": 0,
    "last_filed_at": null,
    "last_presented_at": null,
    "last_presented_handles": []
  }
}
```

## Purpose

**Accrue work for the human**, not progress theatre.

| File To `operator` when… | Do **not** when… |
| --- | --- |
| **Problem** Mind/Hands cannot safely auto-recover (auth hard-stop, fleet-wide harness death, data-loss risk) | Routine cycle status, absorbs, HEADs moved |
| **Critical blocker** unaddressed after Mind already decided/pivoted | Open Hand tasks still draining |
| **Bug** needs **explicit human guidance** (product intent, security, external account) | Implementable defects with clear residual → **task** To Hand |
| True **human-only wall** (credentials, policy, spend, external ticket) | Reversible defaults Mind should take |

**Not for:** status; done/absorb (Hand → `mind`); Head reports (Head → `mind`); head-cxo purity notes; anything only in `operator_recap`.

## Surfaces

| Surface | Audience | Content |
| --- | --- | --- |
| **`mind@`** | Mind (ops) | Hand done/evidence, Head reports, RTM, bag bookkeeping **+ operator→mind decisions** |
| **`operator@`** | Human | Problems, blockers, bugs needing guidance (human backlog) |
| **`operator@` → `mind@`** | Mind | Operator feedback from another session/TUI — **same priority as human chat** |
| **`operator_recap`** | Mind → chat | Compact “what happened while gone” *status* |
| **task** To Hand | Hand | Implementable work with done-when |
| **need** To Hand/Mind | Agent | Decision for someone *on the board* |
| **need** To **operator** | Human | Decision wall that *is* operator mail |

### Cheap cycle (every FLEET_CYCLE mini-cycle — fail-fast)

`fleet-sensors.py` already covers this when you use it. Manual equivalent:

```bash
# 1) Escalations waiting on human
vivi need list --for operator --project "$ROOT"
vivi mail list --for operator --project "$ROOT"

# 2) Operator feedback To mind (do not skip — this is how operator mails Mind from another session)
vivi mail list --for mind --project "$ROOT"   # scan From: operator@
```

Sensors emit:

| Signal | Meaning |
| --- | --- |
| `operator_mail` | Open needs/unread **To operator@** (human backlog) |
| `operator_to_mind` | Mail **From operator@ To mind@** — **absorb before** Hand thrash / map refill |

**Order when either fires:** present/absorb **operator→mind** first (and open operator@ if N>0), then recap, then product ops.

**Engagement:** operator→mind board mail **counts as operator engagement** for mode (same as human prose in the Mind TUI) — reset silence via `fleet-baseline.py bump --operator-engaged` when new op→mind appears this cycle.

| Situation | Kind To `operator` |
| --- | --- |
| Human must choose among options | **need** — default + options; Mind pivots other work |
| Incident / finding needing eyes or policy | **mail** — subject prefix; body = evidence + ask |
| Implementable once human answers | After answer: **task** To Hand; close need |

Do **not** use **task** To `operator`.

## Subject prefixes

```text
operator: problem — <one line>
operator: blocker — <one line>
operator: bug-guidance — <one line>
operator: need — <one line>
```

Body: (1) **what happened** (facts, handles, HEADs, pane) (2) **why human** (tried / default unsafe) (3) **ask** + **default** (4) **impact** if ignored (5) **related** bag/map.

## Who files

| Role | To `operator`? |
| --- | --- |
| **Mind** | **Yes** — primary filer during autonomous cycles |
| **Hand** | Prefer To **`mind`** first; Mind refiles if truly human. Hand may file **need** To `operator` only for hard human-only walls (default + options), then **pivot** |
| **Heads** | **No**. Reports To `mind`. Mind promotes if human needed |

## When to file (Mind)

Same turn the wall is recognized — do not wait for operator return.

```text
1. Implementable without human intent? → task To Hand
2. Safe reversible default? → decide now; recap note; no operator mail
3. Human-only / unsafe to default? → file To operator (need or mail); pivot
4. Already filed same issue? → no spam; update/thread if material new evidence
```

**Dedup:** `vivi mail list --for operator` / open needs before filing. Same subject class + root cause → reply on thread or skip.  
**Cap:** few new operator items per cycle; prefer one rich need over five status-shaped mails.

## Present on operator return **or** operator→mind mail

On **engagement** (human prose, mode → interactive, “catch me up”, **or sensors `operator_to_mind`**):

1. **First:** mail **From operator@ To mind@** — summarize + absorb into posture/map/recap (decisions already made)
2. **Then:** open/unread **To operator@** needs/mail (still waiting on human)
3. Short tables human can work through
4. Per To-operator item: summarize → guidance → close/reply → file **task** To Hand if any
5. Record `operator_mail.last_presented_at` + handles; note absorbed op→mind handles in baseline/recap

```bash
vivi mailspace status --project <root>
vivi mail list --for mind --project <root>      # From operator@ first
vivi mail list --for operator --project <root>
vivi need list --for operator --project <root>
```

```text
## Operator mail (N waiting)
| # | kind | handle | subject | age |
| - | need | abc1234 | operator: need — … | 2h |
| - | mail | def5678 | operator: problem — … | 40m |

Work through #1 first? (or: “skip for now / clear noise”)
```

If **N=0**: say so once; no invent. Then normal recap.

**Catch-up order:** (1) operator mail (2) `operator_recap` (3) live bag/pane/HEAD.

## Autonomous interaction

Still **files** To `operator` when rules match. Does **not**: wait multi-cycle for reply before pivoting; dump items into one-line cycle report (optional `+op-mail:N`); confuse operator mail with success metrics.

Interactive after silence: **always** surface list if non-empty.

## Anti-patterns

- Status To `operator` (“Gap2 done”, “still running”)
- Flooding one problem every cycle without new evidence
- Using `mind@` as human backlog
- Filing implementable bugs as operator mail instead of Hand **tasks**
- Heads mailing human directly (cxo especially)
- Treating operator mail as second Mind process or tmux slot
- Freezing fleet empty-handed because operator mail is open (pivot)

## Related: steward trip

Steward dead-man trip files **operator@** (+ optional external email). First-class page — present with other operator mail. See [`dead-man.md`](dead-man.md).

## Arm checklist

- [ ] `vivi mailspace identity add operator --project <root>`
- [ ] `operator_inbox` in fleet config
- [ ] Mind: human walls → `operator`; status → recap / mind board
- [ ] Return path: present operator list on engagement
