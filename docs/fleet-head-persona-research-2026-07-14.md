# Fleet Head Persona & Review-Lens Research

**Date:** 2026-07-14
**Scope:** `~/work/faberlang` (fleet `faber`) + `~/work/mintedgeek` (fleet `swarm`)
**Mode:** Read-only. No raw files touched; mail inspected via `vivi` CLI + read-only sqlite for subject-level mapping only.
**Corpus:** faber 8,526 messages (5 days, 2026-07-09→07-14); swarm 3,734 (3 days, 07-11→07-14). Head-originated reports sampled: faber CEO/CTO/CXO ~442; swarm CEO/CTO/CXO/CSO ~114. ~16 full report bodies read end-to-end.

---

## TL;DR

**The personas are high quality and the heads are, on the evidence, properly lensed.** This is not a "broken, rewrite it" situation — it is fine-tuning territory. Across both fleets the three armed advisors (CEO/CTO/CXO) plus the swarm CSO hold their lens under heavy volume and even under the strain of being asked strategic / company-thesis / billing-reality questions that sit outside the persona's *named* domain. The heads self-correct back to lens (CXO appends a "why this is a purity finding" note; CSO explicitly disclaims CTO/CXO territory; CTO answers a billing question as a code-trace gate-honesty exercise, not a business opinion).

There is **one concrete config bug** (swarm `head-cso` persona points at `cto.md`), **one stale-dualism** in faber (role-prompt.txt legacy vocabulary vs persona fleet vocabulary), and **two structural gaps** the personas don't name but the heads are already improvising well: (1) a strategic / operational-review mode that MGS grew into, and (2) the designed-but-underdocumented gate-honesty overlap between CEO/CTO/CXO.

---

## 1. What the persona architecture is

Source of truth: `~/work/ianzepp/fleet/references/heads/` — `cast.md`, `heads.md`, `personas/*.md`, `personas/shared-operating-rules.md`.

- **head-ceo** = *strategist seat*. Map health, misprioritization, gate honesty (priority angle), side-lane buckets with effort/est_tokens, expansion (growth) / stewardship (standby). NOT an org-chart CEO; NOT a second Mind.
- **head-cto** = *correctness seat*. Post-main code review, behavioral bugs, fail-closed policy, technical gate honesty (is a claimed gate real/hard/false? name the producer fact). NOT the product implementer; NOT merge GO/NO-GO.
- **head-cxo** = *purity seat* ("XO executes"). Unearned complexity, excess layers, muddy boundaries, **gates invented by over-coupling**. NOT operator/external voice (Mind owns that); NOT the bug head.
- **head-cso** = *security/privacy/abuse* (lazy). Authorized black-hat, tenant isolation, egress, abuse boundaries.
- **head-cpo/cmo/coo/cfo** = lazy on-demand lenses (product, positioning, ops, cost).

Shared finding-class vocabulary (`priority_inversion`, `starved_producer`, `unicorn_wait`, `false_gate`, `soft_gate`, `hard_gate`, `expansion_candidate`, `stewardship`, `clean_pass`) is the lingua franca all heads emit in their reports. The report contract (kind/posture/business_area/evidence/recommendation/confidence) is consistently followed.

**Harness policy update:** Minds, Hands, and Heads default to Pi. Faber uses `pi + zai + glm-5.2 high`; swarm uses `pi + openai-codex + gpt-5.5 high`. Advisor independence comes from provider, model, prompt, and role rather than changing harness.

---

## 2. Evidence: lens discipline is high

### Faber (coding-fleet, growth)

- **head-cto** `62deaba` — MIR Unit B matrix-kernel ABI: WGSL/Metal reject (fail-closed) vs llvm-text emit succeeds (fail-**open**). Severity P1, repro, suggested owner, explicit "Not claimed." Textbook behavioral/cross-target-honesty CTO lens. No purity drift.
- **head-cxo** `042c5d8` — "MIR/LLVM `llvm_abi` is an invented Unicorn gate." Maps 3-crate / 20-site inverted compiler→runtime dependency, names the **earned** part (versioned symbol contract, hosts/llvm separation) vs the **unearned** part (inverted dep, mis-naming, no parity guardrail), proposes a neutral leaf-crate + parity test, and *explicitly parks* adjacent cleanliness targets (`validate.rs` 3.3k-LOC fusion) as "a separate cleanliness target, not the gate." Disciplined purity lens on a question that superficially looks architectural.
- **head-cxo** `d58979d` — "90 runtime mori-aborts bypass compile-time `@ nondum` hub." Superficially a behavioral bug (runtime abort vs compile error), but CXO frames it as **unearned mechanism duplication** ("two ways to say 'not implemented'") and explicitly carves out "the deferred surface itself is earned — I am NOT challenging it." Holds lens on a borderline case.
- **head-ceo** `d1fe8da` — cadence map-health: live board re-verify (corrects stale bag list in-line), priority guidance, bounded next-units with effort/done-when/non-claims, then "no new assignment this instant" (anti-makework). Textbook strategist.

### Swarm (company-thesis + coding, growth→standby)

- **head-cso** `09bbe04` — Campaign C security gate: tenant isolation + outbound abuse per experiment. Opens with "This report owns the security/abuse enforcement layer. It does not duplicate the CTO runtime-contract/side-effect-gate work or the CXO common-vs-bespoke discipline." Explicit boundary acknowledgment — the cleanest lens discipline in the corpus.
- **head-cto** `18f7f3f` — "P-E4 billing reality — charge-today NO." Asked a billing/monetization question; answered it as a **technical code-trace** proving the payment chain is semantic-only (no provider SDK, no credentials, no webhook, no settlement ledger). Stayed on "is the technical plumbing real" (gate honesty), did not opine on business strategy. Clean.
- **head-cxo** `d83cf86` — core-capability matrix (13 domains). Could drift to CPO product territory; instead ends with a "## CXO shape note (why these are purity findings, not just feature requests)" reframing capability gaps as trust defects / regression-masquerading-as-feature / no-reconciliation-primitive. Self-aware lens defense.
- **head-cxo** `c923407` — company-thesis coherence: frames the thesis's central adjective ("agent-operated") as **unearned** (lifecycle is human-operated markdown, 0 runtime series refs), finds dual ledger / dual identity / no reconciliation primitive. Shape-debt lens applied to a strategy doc — legitimate when the finding is "the architecture doesn't earn the thesis's claim."
- **head-ceo** `5353747` — strategy discovery: "product/release shape is the gating uncertainty." Strategist lens (sequencing, what gates the next move).

### Cross-lens bleed scan (subject-level, both corpora)

| Fleet | Head | "foreign-lens" keyword hits / total | Verdict |
|---|---|---|---|
| faber | head-cto | 12 / 313 (~4%) purity/shape/layer/unearned | Almost all `claim-gate` / `fail-closed` — the **designed** gate-honesty overlap, not bleed |
| faber | head-cxo | 2 / 51 (~4%) correctness/bug/fail-closed | The one borderline case (`d58979d`) holds purity lens on inspection |
| faber | head-ceo | 5 / 78 (~6%) correctness/bug/purity | All contextual ("after correctness burst") — sequencing context, not bug review |
| swarm | head-cto | 2 / 31 purity/shape/coherence | Low; legitimate gate overlap |
| swarm | head-cxo | 0 / 23 behavioral; 8 / 23 "coherence" | The "coherence" mode is the thesis-review pattern (see Gap D) |
| swarm | head-ceo | 4 / 44 correctness/bug/purity/shape | Contextual |

**The bleed is low and almost entirely the designed gate-honesty overlap**, where CEO (priority of a gate), CTO (technical truth of a gate), and CXO (shape origin of a gate) all legitimately touch the same gate from different angles. The personas cross-reference this but don't codify the division sharply (see Gap B).

---

## 3. Gaps (surfaced, not decided — multiple paths offered where relevant)

### GAP A — [CONFIG BUG] swarm `head-cso` persona points at the wrong file

`~/work/mintedgeek/.vivi/fleet.json` → `head-cso.persona = .../personas/cto.md` (correctness/gate-honesty) instead of `.../personas/cso.md` (security/privacy/abuse).

- **Impact today: low** — the CSO is producing excellent, on-lens security work (`09bbe04`, black-hat BH-LLM-002) because the `notes` field + the per-assignment files carry the security framing. It is not currently mis-behaving.
- **Impact on cold-boot reinit: high** — if swarm is reinit'd from fleet.json persona path alone (e.g. another OS failure / machine migration, exactly the scenario 12h ago), the CSO would bootstrap against the CTO persona and lose its security lens until an assignment re-grounds it. This is precisely the fragility the user's OS-failure-recovery context exposes.
- **Fix:** one-line config edit: `head-cso.persona → .../personas/cso.md`. Faber already has this correct.

### GAP B — Faber role-prompt.txt files are stale-dualist vs the persona layer

Faber arms each head with **both** a `persona` (fleet skill, fleet vocabulary: hand-N, mind) **and** a `.vivi/*-role-prompt.txt` (legacy camp vocabulary: hunter-N, gatherer, reviewer, `To: reviewer`). MGS by contrast sets `role_prompt: null` and relies on persona + assignment files.

- The faber role-prompts still say "report **To: reviewer**" and "hunter-N (main/MIR), hunter-2 (HIR packet)" while `fleet.json` renamed identities to `head-cto`/`hand-1` and `head_report_inbox: reviewer`. The persona files say "To: mind."
- This creates a **dual truth on the report destination and the vocabulary**. In faber, `reviewer` *is* the gatherer/mind-adjacent inbox, so mail routes correctly today — but the role-prompt's mental model (hunter/gatherer/reviewer camp) is a generation behind the persona's (hand/head/mind fleet).
- **Risk:** a head clean-slate-reinit'd from the role-prompt.txt will speak in legacy vocabulary and may mis-address or mis-scope; the persona (loaded second, or not at all if the role-prompt is treated as primary) can contradict it.

**Paths:**
1. **Clean break (recommended):** drop faber's `*-role-prompt.txt` for the three armed heads and adopt MGS's pattern — `role_prompt: null`, persona + per-assignment files. This reduces the number of valid instruction sources from two to one (AGENTS.md § change-stance).
2. **Reconcile:** rewrite the role-prompts into fleet vocabulary (`hand-N`, `mind`, persona-aligned lens) and mark the persona as authoritative on conflict. More churn, keeps a local override seam.
3. **Leave:** acceptable while faber is mid-MIR-packet and heads are warm; but fix before any cold-boot reinit.

Note: faber's `head-ceo` role-prompt *does* carry one thing the persona doesn't — the "Durable expansion-cadence contract — Faber V1 release spine" (authority mail `cf9d244`). That contract is valuable project memory. If you take Path 1, migrate that spine contract into a `head-ceo` memo or a `head-assignments/` file so it survives the role-prompt removal.

### GAP C — Personas are coding-fleet-centric; swarm grew a strategic/operational-review mode they don't name

The persona docs (`ceo.md`/`cto.md`/`cxo.md`) are written around **code/map artifacts**: "post-main code review," "shape debt on product codebase," "map health, queues, git tips." Swarm's Mind has evolved a **strategic & operational review mode** where the same question is fanned out to multiple heads against *non-code* artifacts:

- Company-thesis coherence (`c923407`) → CXO
- Core-capability matrix (`d83cf86`) → CXO
- Billing-reality discovery (`18f7f3f`) → CTO
- Experiment-lifecycle governance / Campaign C → CEO + CTO + CXO + CSO each with a "requirements" tag
- Local-recovery sanity check (the 4 `head-assignments/2026-07-14-*` files) → each head gets a lens-sliced scope + evidence packet + report shape

The heads **improvise correctly** — every one re-grounds in lens (CXO's "shape note," CSO's boundary disclaimer, CTO's code-trace). But the persona docs don't *authorize or shape* this mode, so it relies on each head's individual discipline. The recovery assignment files (written by the Mind, not the personas) are actually doing the lens-slicing work the personas would otherwise own.

**Paths:**
1. **Name the mode in shared-operating-rules.md** — add a "Strategic / operational review lens" subsection per persona: how each lens applies to corporate docs, thesis, governance, capability matrices (e.g. CXO on a thesis = "does the architecture earn the thesis's central claims / are there duplicated truths / missing reconciliation primitives"; CTO on a capability claim = "is the plumbing real or semantic-only"; CEO on a thesis = "is the priority stack coherent with the operating model"). This makes the good behavior durable instead of personality-dependent.
2. **Keep it in the assignment layer** — leave personas code-centric and let the Mind's assignment files carry the lens slice (current state). Works while the Mind is disciplined; fragile if a future Mind is thinner.
3. **Add a `head-cpo`/`head-coo` arc** — some of the CXO "capability matrix" and CTO "billing reality" work is arguably CPO/CFO lens. Arming those lazy heads for the discovery program would let CXO/CTO stay narrower. Higher cost (more panes); only worth it if discovery programs are recurring.

### GAP D — CXO "coherence" mode is a quiet, mostly-healthy drift worth surfacing

8/23 swarm CXO subjects are "coherence" reviews of `corporate/` + thesis. These are legitimately shape/coherence (unearned seams, duplicated ledgers, missing primitives) and the CXO defends its lens each time. But "company-thesis coherence" is adjacent to CPO (product direction) and CEO (strategy) territory. Currently safe because the CXO is disciplined; if it ever stops appending the "why this is purity" note, it would silently drift into strategy.

**Path:** add one line to `cxo.md` naming "thesis / operating-model coherence (unearned claims, duplicated truths, missing reconciliation primitives)" as an explicit CXO mode, with the carve-out "product *direction* (who/what for) stays CPO; you audit whether the *shape earns the thesis's claims*." Cheap, hardens the boundary.

### GAP E — The gate-honesty overlap (CEO/CTO/CXO) is designed but under-documented

All three armed heads classify gates (`false_gate`/`unicorn_wait`/`hard_gate`/`soft_gate`). The bleed scan confirms they stay on their angle, but each persona mentions the others in only one line. A small shared table would harden it:

| Lens | Question on a gate |
|---|---|
| **head-ceo** | Is the gate on the critical path / is its *priority* correct? |
| **head-cto** | Is the gate technically *real* (hard/soft/false)? Name the producer fact. |
| **head-cxo** | Is the gate *invented by shape* (over-coupling, no parity guardrail)? |

Already de-facto true; making it explicit in `shared-operating-rules.md` costs near nothing and removes the last ambiguity a head might have when two could plausibly claim a finding.

---

## 4. What is working well — leave alone

- **Report contract & finding vocabulary** — uniformly emitted (`kind:`/`posture:`/`evidence:`/`recommendation:`/`confidence:`/`Not claimed`). Do not change.
- **CSO persona + assignment pairing** — the cleanest lens discipline in the corpus (explicit "does not duplicate CTO/CXO work"). Once the persona-path bug (Gap A) is fixed, it's a model for the others.
- **The recovery assignment pattern** (swarm `.vivi/head-assignments/`) — lens-sliced scope + evidence packet + hard constraints + report shape per head — is exemplary orchestration. Worth keeping as a template for any future multi-lens review.
- **CTO post-main-only discipline** — faber CTO explicitly does *not* re-enter hand WIP mid-flight ("h1 owns b867cfd — not re-entered"); swarm CTO sweeps main after lands. Matches `heads.md` law.
- **CXO compact-between-passes vs CEO clean-slate-per-assign** — both fleets observe the persona's differing context hygiene. Do not homogenize.
- **Multi-lens fan-out on one strategic question** (Campaign C / experiment lifecycle / recovery) — getting CEO+CTO+CXO+CSO cuts on the same question is a genuine strength, not a flaw. Keep; just name it (Gap C).

---

## 5. Recommended action priority

| # | Gap | Effort | Risk if deferred | Action |
|---|---|---|---|---|
| 1 | **A** — swarm head-cso persona path → cso.md | trivial | cold-boot loses security lens | fix now |
| 2 | **B** — faber role-prompt.txt dualism | medium | cold-boot vocabulary/addressing confusion | migrate to persona-only + preserve CEO spine contract as memo; do before next faber cold-boot |
| 3 | **D** — name CXO coherence mode in cxo.md | trivial | silent drift into strategy if discipline lapses | one-line add |
| 4 | **E** — gate-honesty per-lens table in shared rules | trivial | none today; hardens boundary | small table |
| 5 | **C** — strategic/operational review mode in personas | medium | relies on head discipline; fragile on thinner Minds | add subsection to shared-operating-rules per persona |

1 is a bug fix. 2 is a clean-break the user's own AGENTS.md favors (reduce valid paths, no shims). 3–5 are persona fine-tuning that hardens behavior the heads already show. None require touching the code or the live panes — all are doc/config edits, safe to stage and review before applying.

---

## 6. Method note

- Mail inspected via `vivi mail list/show` (sanctioned CLI) + read-only `sqlite3 -readonly` for aggregate subject/from/to counts only. No writes, no `exec`, no board mutation, no pane wakes. Both fleet monitors attached and detached cleanly.
- Sample is deep but not exhaustive: ~16 full bodies + full subject corpora for all armed heads + all recovery assignment files. Bleed scan is subject-keyword-level (a proxy; bodies were spot-checked where borderline).
- The OS-failure-recovery context is directly reflected: the swarm `head-assignments/2026-07-14-*` files *are* the post-recovery lens-slicing, and Gap A (wrong persona path) is exactly the class of bug that bites hardest on a cold-boot reinit after a machine swap.
