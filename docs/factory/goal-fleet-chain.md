# Goal: Fleet chain gate (`fleet.py`)

## Summary

A single Python CLI (`scripts/fleet.py`) that provides a fail-closed mechanical
gate over the Fleet communication chain. Work without a valid prepare → claim
→ settlement chain cannot advance Fleet state (admission, acceptance). This
turns the existing prose invariant — "no handle, no spawn; no durable report,
no gate advance" — into an enforced check rather than Mind discipline.

## Problem

Every Fleet protocol says Vivi handles are the communication authority, and no
gate may advance without a durable completion/report chain. But enforcement is
purely the Mind's judgment. Nothing prevents a Mind from:

- spawning without a filed Vivi handle;
- advancing a gate from a runtime/chat return alone;
- accepting work without a valid audit chain;
- or backfilling a task stub after spawn and presenting it as original routing.

`vivi trace` can *walk* the chain, and `task done --verdict/--repo/--tip` can
*record* structured receipts — but no helper *refuses to advance* when the
chain is absent. The gap is a missing mechanical layer between Vivi's
durable record and Fleet's gate decisions.

## Goals

- One CLI with four subcommands: `prepare`, `claim`, `settle`, `advance`.
- A frozen launch receipt (sidecar seal) that tamper-proofs the assignment at
  prepare time and accumulates claim and settlement entries.
- `advance` as a pure-read gate check that walks the Vivi trace and verifies
  the sidecar chain before returning a verdict.
- Fail-closed coupling: acceptance and admission recording calls `advance`
  internally; if the chain is invalid, the recording refuses.
- Shares `fleet_common.py` with existing fleet scripts; no new runtime
  dependency beyond Python 3.9+ and the `vivi` binary.

## Non-goals

- Controlling or intercepting the harness spawn itself. The harness may spawn
  anything; the gate makes unauthorized spawns incapable of producing valid
  Fleet work.
- Proving pre-spawn ordering without a harness timestamp or hook. A task
  created after spawn but before claim is externally indistinguishable; the
  hash seal detects post-prepare body mutation, not spawn timing.
- Verifying the actual model the harness ran. The helper validates the expected
  role binding from the Vivi record, not what the harness executed.
- Guaranteeing runtime IDs. They are operational metadata in the sidecar, not
  the durable accounting root.
- Semantic scope coherence judgment. The helper validates one pass, owner,
  scope, and done-when group structurally; whether several findings belong
  together remains Mind judgment.
- Replacing `vivi trace`. The helper *uses* trace to walk the chain; it does
  not duplicate the trace engine.
- A new MCP tool or plugin surface. This is a standalone script, same layer as
  `fleet-sensors.py` and `fleet-cycle-close.py`.

## Ground truth researched

| Source | Evidence |
| --- | --- |
| `SKILL.md` § Vivi-first communication invariant | "No handle, no spawn. No durable report, no gate advance." Currently prose only. |
| `SKILL.md` § Role communication contract | Boot + report shape; `vivi task show`, `task done --verdict/--repo/--tip`, `mail reply` as the durable edges. |
| `references/vivi.md` § Communication tracing | `vivi trace <handle> --json --max-depth N` walks captured, event, and inferred edges. Stable `TraceGraph` with `seed`, `nodes`, `edges`. |
| `references/vivi.md` § Command shapes | `task done --for <name> --verdict clean_pass --repo <repo> --tip <sha>` records structured receipts. |
| `references/wave-planning.md` | Most developed gate vocabulary: P1/P2/P3, intent gate, goal-reality + delivery-reality audits, finding disposition, admission receipt. Admission requires both audit receipts. |
| `references/planner-protocol.md` | Task acceptance requirements; refusal conditions; READY-gate enforcement. |
| `references/auditor-protocol.md` | Verdict types (`clean_pass`, `residual`, `block_ship`); report contract; clean-slate isolation. |
| `references/hand-protocol.md` | Task acceptance requirements; execution cycle; commit authority. |
| `scripts/fleet_common.py` | Shared helpers: `write_text_atomic`, `save_json`, `load_json`, `run_cmd`, `now_iso`, `resolve_fleet_file`, `resolve_role`, `add_fleet_scope_arguments`. Python 3.9+, zero third-party deps. |
| `scripts/fleet-cycle-close.py` | Disposition validation over sensor signals; `parse_dispositions`, `validate_dispositions`. Acceptance/admission are not currently cycle-close dispositions — they are Mind decisions recorded in Vivi. |
| `scripts/test_fleet_common.py` | Test pattern: `unittest`, temp dirs, `sys.path.insert` for import. |
| Commit `3b76e47` | "docs(fleet): make Vivi handles the communication authority" — established the prose invariant this goal mechanizes. |

## Constraints and invariants

| # | Invariant |
| --- | --- |
| 1 | **Single CLI.** `scripts/fleet.py <subcommand>`, not four separate scripts. The four stages are one state machine sharing one receipt format. |
| 2 | **Hybrid authority.** Vivi holds the chain edges (task, done, report, trace). The sidecar receipt (`.vivi/fleet/chain/<handle>.json`) holds the frozen hash, expected binding, and transition timestamps. `advance` cross-checks both. |
| 3 | **Tamper-evidence.** `prepare` freezes a SHA-256 of the assignment body. If the Mind edits the body after prepare, the hash mismatches on claim → hard fail, forcing re-prepare. |
| 4 | **Claim is a Vivi event.** Claim produces a lightweight `vivi mail reply` on the handle so the claim edge is visible in `vivi trace`, plus a sidecar entry. |
| 5 | **Settle verifies, doesn't replace.** Settle checks that `task done` and report mail exist in Vivi for the handle, then records the settlement in the sidecar. It does not substitute for the role's own `task done` + report. |
| 6 | **Advance is a pure read.** Idempotent. Returns verdict + structured JSON. Never mutates state. The fail-closed property comes from the *caller* (cycle-close or Mind protocol) refusing to proceed on nonzero exit. |
| 7 | **Fail-closed coupling for accept/admit.** Wherever acceptance or admission gets durably recorded, `advance` is called as a precondition. If advance fails, the recording refuses. |
| 8 | **Zero new dependencies.** Python 3.9+ stdlib + `vivi` binary + existing `fleet_common.py`. |
| 9 | **Sidecar is the only off-Vivi storage.** Everything else is a Vivi edge. The sidecar exists because Vivi cannot hold a cryptographic hash or a frozen binding snapshot. |
| 10 | **Idempotency.** `claim` is idempotent per (handle, role). `settle` fails on double-settle. `advance` is a pure read. `prepare` fails on re-prepare-after-claim. |

## Architecture direction

### Data flow

```text
Mind                         Spawned role              Gate check
─────                        ─────────────              ──────────
prepare ──→ sidecar receipt
  │         (hash, binding,
  │          scope, pass)
  │
  ├── boot prompt (thin pointer)
  │         ↓
  │         claim ──→ verifies receipt + Vivi task
  │         │         writes claim to sidecar
  │         │         files Vivi mail reply (trace edge)
  │         │
  │         [work]
  │         │
  │         settle ──→ verifies claim + task done + report
  │         │           writes settlement to sidecar
  │         ↓
  │         [return short pointer]
  │
advance ──→ walks Vivi trace + verifies sidecar chain
  │         returns verdict (pass/fail + evidence)
  │
  ├── if pass: record acceptance/admission
  └── if fail: refuse
```

### Sidecar receipt schema

```json
{
  "handle": "<vivi-handle>",
  "kind": "task",
  "role": "hand-1",
  "scope": "src/module/",
  "pass": "implement",
  "expected_role_binding": {
    "provider": "<provider>",
    "model": "<model-slug>",
    "harness": "subagent"
  },
  "assignment_body_hash": "sha256:<hex>",
  "prepared_at": "<iso-utc>",
  "prepared_by": "mind",
  "claim": {
    "role": "hand-1",
    "claimed_at": "<iso-utc>",
    "pid": "<pid-or-null>",
    "binding_verified": true
  },
  "settlement": {
    "settled_at": "<iso-utc>",
    "task_done_verified": true,
    "report_handle": "<vivi-mail-handle>",
    "git_repo": "<repo-or-null>",
    "git_tip": "<sha-or-null>",
    "verdict": "<verdict-or-null>",
    "scope_declared": "src/module/"
  }
}
```

### Subcommand contracts

| Subcommand | Caller | Mutates | Key Vivi calls |
| --- | --- | --- | --- |
| `prepare` | Mind | Sidecar receipt | `vivi task send` (creates assignment) |
| `claim` | Spawned role | Sidecar claim entry + Vivi mail reply | `vivi task show`, `vivi role show`, `vivi mail reply` |
| `settle` | Spawned role | Sidecar settlement entry | `vivi task show` (verify done), `vivi mail list/show` (verify report) |
| `advance` | Mind (or cycle-close) | Nothing (pure read) | `vivi trace`, `vivi task show` |

### Gate evidence schema (v1)

| Gate | Universal chain check | Additional evidence |
| --- | --- | --- |
| `admission` | prepare → claim → settle | P2 goal-reality + P3 delivery-reality audit receipts; no unresolved `block_ship` on required findings |
| `acceptance` | prepare → claim → settle | Audit-loop verdict: `clean_pass`, or `residual` with all findings dispositioned |

## Implementation shape

One delivery-sized unit. Four implementation stages inside:

1. **Foundation** — receipt schema, sidecar I/O (atomic read/write under `.vivi/fleet/chain/`), SHA-256 hashing, `fleet_common.py` additions.
2. **Spawn-side** — `prepare` + `claim` (the Mind → role handoff half).
3. **Complete-side** — `settle` + `advance` (the role → gate half).
4. **Coupling** — `fleet-cycle-close.py` integration for accept/admit gates; tests.

Tests use the existing `unittest` + temp-dir pattern from `test_fleet_common.py`, mocking `vivi` subprocess calls.

## Release posture

`defer-release` — this is a new mechanical layer internal to the fleet skill. No
user-visible behavior change until the Mind protocol is updated to use it. Ship
the script + tests; protocol doc updates are a follow-up delivery unit.

## Exit strategy

If the chain gate proves too rigid or the sidecar creates maintenance burden:
remove `scripts/fleet.py` and its tests; the prose invariants in `SKILL.md`
remain the fallback. The sidecar receipts under `.vivi/fleet/chain/` are
disposable — they are seals, not primary records. No migration needed.

## Acceptance criteria

1. `fleet prepare` creates a Vivi task, writes a sidecar receipt with a body
   hash, and prints a boot prompt containing the `fleet claim` command.
2. `fleet claim` verifies the receipt + Vivi task, writes the claim entry, files
   a Vivi mail reply, and exits 0. A second claim by the same role is idempotent;
   a claim by a different role fails.
3. `fleet settle` verifies the claim + task done + report mail, writes the
   settlement entry, and exits 0. Double-settle fails.
4. `fleet advance --gate admission --handle <h>` returns pass when the chain is
   valid and both audit receipts exist; returns fail with evidence when any link
   is missing.
5. `fleet advance --gate acceptance --handle <h>` returns pass when the chain is
   valid and the audit verdict is `clean_pass` or `residual` with dispositions.
6. Tampering with the Vivi task body after prepare causes claim to fail on hash
   mismatch.
7. All four subcommands share `fleet_common.py` and add no third-party
   dependency.
8. Tests cover: receipt round-trip, claim idempotency, settle verification,
   advance pass/fail for each gate, hash-tamper detection.

## Validation

```bash
# Unit tests (mock vivi subprocess)
python3 scripts/test_fleet_chain.py

# Manual smoke (requires a live vivi mailspace)
python3 scripts/fleet.py prepare --project <root> --to hand-1 --role-binding hand-1 \
  --pass implement --scope 'src/module/' --body 'test assignment'
python3 scripts/fleet.py claim --project <root> <handle> --role hand-1
python3 scripts/fleet.py settle --project <root> <handle> --role hand-1
python3 scripts/fleet.py advance --project <root> --gate acceptance --handle <handle>
```

## Open questions

| # | Question | Blocking? |
| --- | --- | --- |
| 1 | Does `vivi task show --json` return a `status` field that distinguishes open/done? Needed for claim's "remains open" check and settle's "task done" verification. | No — can fall back to checking `vivi task list --status done` if `show` lacks status. Verify during implementation. |
| 2 | What is the exact coupling point for accept/admit in cycle-close? Cycle-close dispositions are sensor signals, not acceptance decisions. May need a separate `--gate-check` flag or a standalone protocol gate. | No — delivery stage 4 resolves this. Leading option: `--accept <handle>` / `--admit <handle>` flags that call advance internally. |

## Stop conditions

- If `vivi trace --json` output shape is incompatible with the chain-walk logic
  (e.g., no stable edge types), stop and redesign the trace verification.
- If `vivi mail reply` cannot create a trace edge from a task handle (different
  handle namespaces), stop and find an alternative claim-edge mechanism.
- If the sidecar receipt format proves insufficient for the evidence schema,
  stop and revise before adding more gates.
