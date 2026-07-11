# Operator mail

Durable **human inbox** for issues that accumulate while Mind runs **autonomous**
(or whenever the human is not in the loop). Distinct from the fleet board
(`mind@`) and from `operator_recap` (chat memory).

## Identity

| Field | Value |
| --- | --- |
| **Identity token** | `operator` |
| **Mail** | `operator@<mailspace>.local` |
| **tmux** | **none** (same class as `mind` — not a fleet process slot) |
| **Process** | Human operator, via the Mind TUI when they return |

Arm once per fleet:

```bash
vivi mailspace identity add operator --project <root>
```

Fleet overlay:

```json
{
  "operator_inbox": "operator",
  "operator_inbox_note": "Human-facing escalations only. Not status. No tmux."
}
```

Baseline (optional counters):

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

| File To `operator` when… | Do **not** file when… |
| --- | --- |
| A **problem happened** that Mind/Hands cannot safely auto-recover (auth hard-stop, fleet-wide harness death, data-loss risk) | Routine cycle status, absorbs, HEADs moved |
| A **critical blocker** remains unaddressed after Mind already decided/pivoted where possible | Open Hand tasks still draining normally |
| A **bug / defect** needs **explicit human guidance** on fix direction (product intent, security trade-off, external account) | Implementable defects with a clear residual → **task** To Hand |
| True **human-only wall** (credentials, policy, spend, external ticket) | Reversible defaults Mind should just take |

**Not** for:

- Status updates, “still running”, “cycle N quiet”
- Done/absorb bookkeeping (Hand → `mind`)
- Head advisory reports (Head → `mind`; Mind triages)
- head-cxo purity notes (not operator-facing)
- Everything that belongs in `operator_recap` only

## Split: mind vs operator vs recap vs need

| Surface | Audience | Content |
| --- | --- | --- |
| **`mind@`** | Mind (ops) | Hand done/evidence, Head reports, RTM, bag bookkeeping |
| **`operator@`** | Human | Problems, blockers, bugs needing guidance |
| **`operator_recap`** (baseline) | Mind → chat | Compact “what happened while you were gone” *status* |
| **task** To Hand | Hand | Implementable work with done-when |
| **need** To Hand / Mind | Agent | Decision for someone *on the board* |
| **need** To **operator** | Human | Decision wall that *is* operator mail |

`operator` is the **To:** for human escalations. Prefer:

| Situation | Kind To `operator` |
| --- | --- |
| Human must choose among options | **need** — default + options; Mind pivots other work |
| Incident / finding that needs eyes or policy | **mail** — subject prefix below; body = evidence + ask |
| Already implementable once human answers | After answer: file **task** To Hand; close the need |

Do **not** use **task** To `operator` (operator is not a Hand bag).

## Subject prefixes (strong guidance)

```text
operator: problem — <one line>
operator: blocker — <one line>
operator: bug-guidance — <one line>
operator: need — <one line>
```

Body always includes:

1. **What happened** (facts, handles, HEADs, pane class)
2. **Why human** (what Mind already tried / why default is unsafe)
3. **Ask** (decision, credential, guidance) + **default** if any
4. **Impact** if ignored (blocked path, risk)
5. **Related** bag items / map packages

## Who files

| Role | Files To `operator`? |
| --- | --- |
| **Mind** | **Yes** — primary filer during autonomous cycles |
| **Hand** | Prefer escalate To **`mind`** first; Mind refiles To `operator` if truly human. Hand may file **need** To `operator` only for hard human-only walls after externalizing (default + options), then **pivot** |
| **Heads** | **No** direct To `operator`. Reports stay To `mind`. Mind promotes a finding if it needs the human |

## When to file (Mind)

Same turn the wall is recognized — **do not** wait for the operator to return to “remember” it.

```text
1. Is it implementable without human intent? → task To Hand
2. Is a safe reversible default available? → decide now; recap note; no operator mail
3. Is it human-only / unsafe to default? → file To operator (need or mail); pivot
4. Already filed same issue? → do not spam; update/thread if material new evidence
```

**Dedup:** before filing, `vivi mail list --for operator` / open needs. Same subject class + same root cause → reply on thread or skip.

**Cap (guidance):** at most a few new operator items per cycle. Prefer one rich need over five status-shaped mails.

## Present on operator return

When Mind detects **engagement** (human prose, mode → interactive, “catch me up”, “what’s waiting”):

1. List **open/unread operator mail + open needs** To `operator` **before** or **with** the status recap
2. Present a short table the human can work through
3. For each item: summarize → wait for guidance → close/reply → file resulting **task** To Hand if any
4. Record `operator_mail.last_presented_at` + handles

```bash
vivi mailspace status --project <root>   # operator row if present
vivi mail list --for operator --project <root>
vivi need list --for operator --project <root>   # if fleet uses needs to operator
```

**Chat shape (interactive):**

```text
## Operator mail (N waiting)
| # | kind | handle | subject | age |
| - | need | abc1234 | operator: need — … | 2h |
| - | mail | def5678 | operator: problem — … | 40m |

Work through #1 first? (or: “skip for now / clear noise”)
```

If **N = 0**: say so once; do not invent items. Then normal recap / cycle status.

**Catch-up order (strong guidance):**

1. Operator mail (action required)
2. `operator_recap` (what moved)
3. Live bag / pane / HEAD (current ops)

## Autonomous interaction

In autonomous mode Mind still **files** To `operator` when rules match. It does **not**:

- Wait multi-cycle for a reply before pivoting other work
- Dump operator items into the compact one-line cycle report (optional one-token hint: `+op-mail:N` if N>0)
- Confuse operator mail with success metrics

In interactive mode after silence, **always** surface the list if non-empty.

## Anti-patterns

- Status To `operator` (“Gap2 done”, “still running”)
- Flooding one problem every cycle without new evidence
- Using `mind@` as the human backlog (board noise buries escalations)
- Filing implementable bugs as operator mail instead of Hand **tasks**
- Heads mailing the human directly (cxo especially)
- Treating operator mail as a second Mind process or tmux slot
- Freezing the fleet empty-handed because operator mail is open (pivot)

## Related: steward trip

When the **steward** dead man trips (Mind cycle ticks stopped), it files
**operator@** and may send external email. That is a first-class human page —
present it with other operator mail on return. See [`dead-man.md`](dead-man.md).

## Arm checklist

- [ ] `vivi mailspace identity add operator --project <root>`
- [ ] `operator_inbox` in fleet config
- [ ] Mind knows: human walls → `operator`; status → recap / mind board
- [ ] Return path: present operator list on engagement
