# Delivery spec: Fleet chain gate (`fleet.py`)

Source goal: [`goal-fleet-chain.md`](goal-fleet-chain.md)

## Interpreted Unit

One delivery-sized unit: a fail-closed chain-gate CLI (`scripts/fleet.py`)
with four subcommands — `prepare`, `claim`, `settle`, `advance` — plus
`fleet-cycle-close.py` coupling and tests. The unit is cohesive because the
four subcommands form one state machine: advance cannot be tested without
claim and settle; settle cannot be tested without claim; claim cannot be
tested without prepare.

## Normalized Spec

| Requirement | Detail |
| --- | --- |
| Language | Python 3.9+ stdlib only; shares `fleet_common.py` |
| CLI shape | `scripts/fleet.py <subcommand> [flags]` via argparse subparsers |
| Storage | Sidecar receipts at `.vivi/fleet/chain/<sanitized-handle>.json` |
| Vivi dependency | `vivi` binary; commands: `task send`, `task show`, `task list`, `role show`, `mail reply`, `mail list`, `mail show`, `trace` |
| Gates (v1) | `admission`, `acceptance` |
| Exit codes | 0 success · 1 chain/gate failure · 2 usage error |
| Output | Human-readable text by default; `--json` for machine consumption on `advance` |

## Repo-Aware Baseline

| File | Role | Current state |
| --- | --- | --- |
| `scripts/fleet_common.py` | Shared helpers; import target | Has `write_text_atomic`, `save_json`, `load_json`, `run_cmd`, `now_iso`, `resolve_fleet_file`, `resolve_role`, `add_fleet_scope_arguments`, `require_python`. Needs additions: SHA-256 hashing, sidecar path resolution. |
| `scripts/fleet-cycle-close.py` | Cycle close with disposition validation | Has `parse_dispositions`, `validate_dispositions` over sensor signals. Acceptance/admission are not currently cycle-close dispositions. Needs: optional `--gate-check` precondition. |
| `scripts/test_fleet_common.py` | Test pattern reference | `unittest`, temp dirs, `sys.path.insert`, no third-party test deps. Pattern to follow for `test_fleet_chain.py`. |
| `scripts/fleet.py` | New file — the CLI | Does not exist. |
| `scripts/test_fleet_chain.py` | New file — tests | Does not exist. |
| `SKILL.md` | Policy source of truth | Not modified in this unit. Protocol doc updates (boot prompt, report shape) are a follow-up delivery unit. |

Key vivi command shapes (from `references/vivi.md`):

```bash
vivi task send --project <root> --from mind --to <role> --subject '...' --body '...'     # → handle
vivi task show <handle> --project <root>                 # → task body, status
vivi task done <handle> --for <role> --note '...' --verdict clean_pass --repo <repo> --tip <sha>
vivi role show <role> --project <root>                   # → provider, model, harness
vivi mail reply <handle> --from <role> --body '...'      # → creates trace edge
vivi mail list --for mind --project <root>               # → mail handles
vivi trace <handle> --project <root> --json --max-depth 5 # → TraceGraph {seed, nodes, edges}
```

## Stage Graph

Four implementation stages, strictly ordered. Each stage is independently
testable but depends on the prior stage's output.

### Stage 1: Foundation

| Attribute | Value |
| --- | --- |
| **Write scope** | `scripts/fleet_common.py`, `scripts/fleet.py` |
| **Depends on** | nothing |
| **Done when** | receipt schema, sidecar I/O, and CLI skeleton compile and pass round-trip tests |

Add to `fleet_common.py`:

```python
def sha256_hex(text: str) -> str:
    """Return 'sha256:<hex>' for tamper-evidence sealing."""

def chain_dir(project: PathLike) -> Path:
    """Return project / '.vivi' / 'fleet' / 'chain'."""

def chain_receipt_path(project: PathLike, handle: str) -> Path:
    """Sanitize handle to a safe filename; return receipt path."""

def load_receipt(project: PathLike, handle: str) -> Optional[dict]:
    """Load sidecar JSON; return None if missing."""

def save_receipt(project: PathLike, handle: str, data: dict) -> None:
    """Atomic write via write_text_atomic."""
```

Create `scripts/fleet.py` skeleton:

```python
#!/usr/bin/env python3
"""Fleet chain gate: prepare → claim → settle → advance."""
# require_python(); argparse with subparsers; add_fleet_scope_arguments on each
```

Validation: `python3 -c "from fleet_common import sha256_hex, chain_receipt_path"`; receipt save/load round-trip in a temp dir.

### Stage 2: prepare + claim

| Attribute | Value |
| --- | --- |
| **Write scope** | `scripts/fleet.py` |
| **Depends on** | Stage 1 |
| **Done when** | prepare creates a valid receipt + boot prompt; claim verifies and records |

**`prepare`** subcommand:

```bash
fleet prepare --project <root> --to <role> --pass <pass> --scope <scope> \
  --subject '<subject>' --body '<body>' [--body-file <path>]
```

Steps:
1. Resolve role binding: `vivi role show <role> --project <root> --json` → extract provider, model, harness.
2. Create Vivi task: `vivi task send --project <root> --from mind --to <role> --subject '<subject>' --body '<body>'` → parse handle from stdout.
3. Hash the body: `sha256_hex(body)`.
4. Write sidecar receipt with: handle, kind, role, scope, pass, expected_role_binding, assignment_body_hash, prepared_at, prepared_by, claim=null, settlement=null.
5. Print boot prompt containing:
   - Role name
   - `fleet claim <handle> --role <role> --project <root>` as the first action
   - `fleet settle <handle> --role <role> --project <root>` as the pre-return action
   - The standard boot shape from SKILL.md § Role communication contract

**`claim`** subcommand:

```bash
fleet claim --project <root> <handle> --role <role>
```

Steps:
1. Load sidecar receipt; fail with clear error if not found.
2. Show Vivi task: `vivi task show <handle> --project <root>` → parse body and status.
3. Verify: task exists; task `to` field matches `--role`; task status is open; body hash matches sidecar `assignment_body_hash`.
4. Verify role binding: `vivi role show <role> --project <root>` → compare provider/model/harness against `expected_role_binding`.
5. Check sidecar: if `claim` is null → proceed; if `claim.role == --role` → idempotent success (print "already claimed by <role>"); if `claim.role != --role` → fail "claimed by <other-role>".
6. Write claim entry to sidecar: `{role, claimed_at, pid: os.getpid(), binding_verified: true}`.
7. File Vivi mail reply: `vivi mail reply <handle> --from <role> --body 'fleet: claimed at <timestamp>'` → creates a trace edge.
8. Print "Claimed <handle> as <role>".

Validation: mock `vivi` subprocess; test prepare creates receipt with correct hash; test claim succeeds on fresh receipt; test claim idempotent; test claim fails on wrong role; test claim fails on hash mismatch (body tampered).

### Stage 3: settle + advance

| Attribute | Value |
| --- | --- |
| **Write scope** | `scripts/fleet.py` |
| **Depends on** | Stage 2 |
| **Done when** | settle verifies and records; advance returns pass/fail for admission and acceptance |

**`settle`** subcommand:

```bash
fleet settle --project <root> <handle> --role <role> \
  [--repo <repo>] [--tip <sha>] [--verdict <verdict>] [--scope <scope>]
```

Steps:
1. Load sidecar; verify `claim` exists and `claim.role == --role`.
2. Fail if `settlement` is already populated (double-settle).
3. Verify task is done: `vivi task show <handle> --project <root>` → status must be `done`.
4. Verify report mail exists: `vivi mail list --for mind --project <root>` → find a mail `from <role>` whose body or subject references `<handle>`. Fallback: check `vivi trace <handle>` for a mail-reply edge from the role.
5. Record git receipts, verdict, scope from flags (optional — the role passes what it has).
6. Write settlement entry to sidecar: `{settled_at, task_done_verified, report_handle, git_repo, git_tip, verdict, scope_declared}`.
7. Print "Settled <handle>".

**`advance`** subcommand:

```bash
fleet advance --project <root> --gate <admission|acceptance> --handle <handle> [--json]
```

Steps (pure read — no mutation):
1. Load sidecar receipt; fail if not found.
2. Verify chain completeness: `prepare` fields present → `claim` populated → `settlement` populated. Any missing link → fail with named gap.
3. Cross-check sidecar hash against live Vivi task body: `vivi task show <handle>` → hash body → compare to `assignment_body_hash`. Mismatch → fail "assignment body mutated after prepare".
4. Walk Vivi trace: `vivi trace <handle> --project <root> --json --max-depth 5` → verify the trace contains:
   - A task-done edge (task lifecycle event).
   - A mail edge from the role to mind (report).
5. Gate-specific evidence:
   - **`acceptance`**: verify audit verdict. Check the trace for an auditor task done with `verdict` ∈ {`clean_pass`, `residual`}. If `residual`, verify each finding has a disposition. If no auditor edge → fail "no audit verdict in chain".
   - **`admission`**: verify both audit receipts. Check the trace for P2 goal-reality and P3 delivery-reality auditor edges with non-`block_ship` verdicts. If either missing → fail with named gap.
6. Return verdict:
   - Text mode: print `PASS` or `FAIL: <reasons>` and exit 0 or 1.
   - JSON mode: print `{"verdict": "pass"|"fail", "gate": "...", "handle": "...", "chain": {...}, "evidence": {...}, "gaps": [...]}`.

Validation: mock vivi subprocess; test advance pass with complete chain; test advance fail (missing claim); test advance fail (missing settle); test advance fail (hash mismatch); test advance acceptance pass (clean_pass); test advance acceptance fail (no audit); test advance admission pass (both audits); test advance admission fail (missing P3).

### Stage 4: Coupling + tests

| Attribute | Value |
| --- | --- |
| **Write scope** | `scripts/fleet-cycle-close.py`, `scripts/test_fleet_chain.py` |
| **Depends on** | Stage 3 |
| **Done when** | cycle-close gate-check works; full test suite passes |

**`fleet-cycle-close.py` coupling:**

Add a `--gate-check` flag (repeatable):

```bash
fleet-cycle-close.py --project <root> --acted --summary '...' \
  --disposition '<signal>=<kind>:<evidence>' \
  --gate-check acceptance:<handle> \
  --gate-check admission:<other-handle>
```

Behavior: before recording dispositions and bumping baseline, cycle-close runs each gate check by invoking `fleet.py advance --gate <gate> --handle <handle> --project <root> --json`. If any check exits nonzero, cycle-close exits 1 with the failing gate and reason. This makes cycle-close fail-closed: a cycle that records an acceptance cannot close if the chain is invalid.

This is separate from sensor dispositions — it is a cycle precondition, not a sensor signal.

**`scripts/test_fleet_chain.py`:**

Full test file using the `unittest` + temp-dir + mock-subprocess pattern from `test_fleet_common.py`. Test cases:

| Test | Verifies |
| --- | --- |
| `test_receipt_round_trip` | save_receipt → load_receipt preserves all fields |
| `test_prepare_creates_receipt` | prepare writes sidecar with correct hash + binding |
| `test_prepare_boot_prompt` | prepare output contains `fleet claim` command |
| `test_claim_succeeds` | claim on fresh receipt writes claim entry |
| `test_claim_idempotent` | second claim by same role succeeds without error |
| `test_claim_wrong_role_fails` | claim by different role fails |
| `test_claim_hash_mismatch_fails` | body mutated after prepare → claim fails |
| `test_claim_missing_receipt_fails` | claim on unknown handle fails |
| `test_settle_succeeds` | settle with valid claim + task done + report writes settlement |
| `test_settle_double_fails` | second settle on same handle fails |
| `test_settle_without_claim_fails` | settle before claim fails |
| `test_settle_task_not_done_fails` | settle when task status is open fails |
| `test_advance_acceptance_pass` | complete chain + clean_pass audit → pass |
| `test_advance_acceptance_no_audit_fails` | complete chain but no audit edge → fail |
| `test_advance_admission_pass` | complete chain + both audit receipts → pass |
| `test_advance_admission_missing_p3_fails` | only P2 audit → fail |
| `test_advance_missing_claim_fails` | no claim in sidecar → fail |
| `test_advance_missing_settle_fails` | no settlement in sidecar → fail |
| `test_advance_hash_mismatch_fails` | body mutated → fail |
| `test_advance_json_output` | `--json` produces valid structured output |

Mock strategy: monkeypatch `fleet_common.run_cmd` to return canned vivi JSON output. No live vivi dependency in tests.

## Implementation Work

One workstream, four sequential stages. No parallelism — each stage depends on the prior. One implementer.

| Stage | Files touched | Estimated effort |
| --- | --- | --- |
| 1 Foundation | `fleet_common.py` (+~30 lines), `fleet.py` (new, ~40 line skeleton) | Small |
| 2 prepare + claim | `fleet.py` (+~150 lines) | Medium |
| 3 settle + advance | `fleet.py` (+~200 lines) | Medium |
| 4 Coupling + tests | `fleet-cycle-close.py` (+~30 lines), `test_fleet_chain.py` (new, ~300 lines) | Medium |

## Checkpoints and Gates

| Checkpoint | After stage | Gate |
| --- | --- | --- |
| Foundation compiles | 1 | `python3 -c "import fleet_common, fleet"` in temp venv |
| Spawn-side works | 2 | Mock-vivi prepare + claim test passes |
| Complete-side works | 3 | Mock-vivi settle + advance test passes for both gates |
| Full suite green | 4 | `python3 scripts/test_fleet_chain.py` all pass; cycle-close `--gate-check` integration test passes |

**Batching:** one batch. The four stages are one state machine; splitting into separate delivery units would create untestable fragments.

**Release posture:** `defer-release`. The script ships but protocol docs (`SKILL.md`, role protocols) are not updated in this unit. A follow-up delivery unit updates the boot prompt shape, report contract, and Mind protocol to reference `fleet claim` / `fleet settle` / `fleet advance`.

## Validation

```bash
# Unit tests (no vivi dependency)
python3 scripts/test_fleet_chain.py

# Import check
python3 -c "import sys; sys.path.insert(0, 'scripts'); import fleet"

# Existing tests still pass (no regressions in fleet_common)
python3 scripts/test_fleet_common.py
python3 scripts/test_fleet_cycle_close.py

# Manual smoke (requires live vivi mailspace)
python3 scripts/fleet.py prepare --project /tmp/test-fleet --to hand-1 \
  --pass implement --scope 'src/module/' --subject 'test' --body 'test assignment'
# → prints handle + boot prompt
python3 scripts/fleet.py claim --project /tmp/test-fleet <handle> --role hand-1
python3 scripts/fleet.py settle --project /tmp/test-fleet <handle> --role hand-1
python3 scripts/fleet.py advance --project /tmp/test-fleet --gate acceptance --handle <handle> --json
```

## Companion Skill Plan

| Skill | When |
| --- | --- |
| `$polish` | After stage 4, single pass over `fleet.py` and `fleet_common.py` additions |
| `$housekeeping` | Not needed — no existing docs reference `fleet.py` yet |
| `$zombie-docs` | Follow-up unit: verify protocol docs match the new script surface |

## Open Questions

| # | Question | Resolution path |
| --- | --- | --- |
| 1 | Does `vivi task show` output include a `status` field (open/done)? | Verify during stage 2. Fallback: `vivi task list --status done --for <role>` and check if handle appears. |
| 2 | Does `vivi mail reply` on a task handle create a visible trace edge? | Verify during stage 2. Fallback: `vivi mail send --from <role> --to mind --subject 'Re: ...' --body 'fleet: claimed'` with `--reply-to <handle>`. |
| 3 | How does `vivi trace --json` represent task-done and mail-reply edges? | Verify during stage 3. The `TraceGraph.edges` array should have typed edges; map the types to the checks advance needs. |
| 4 | Is `--gate-check` the right name for the cycle-close coupling? | Decide during stage 4. Alternatives: `--accept <handle>`, `--admit <handle>`, `--chain-gate <gate>:<handle>`. |
