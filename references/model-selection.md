# Model selection (role + unit shape)

Generic guidance for choosing **provider / model / thinking effort** by **role
duty** and **unit shape**. Live bindings always win from the Vivi role record
(`vivi role show <name> --project <root>`). This file is process law for Mind
when **filing**, **rebinding**, or **capacity-stepping** — not a second source
of truth for which string is running.

**Do not** pin product marketing names or operator subscription details here.
Project overlays may name concrete models; the skill stays capability-class
based.

Companion: harness alignment and launch flags live in
[`roles-and-harness.md`](roles-and-harness.md). Capacity ladders:
[`runtime-config.md`](runtime-config.md).

---

## Thesis (one line)

**Cheap, well-scoped implement → strong independent audit → cheap targeted
repair.** Do not put the strongest / scarcest model on every Hand unit by
default.

Self-authored green tests are not sufficient evidence of readiness. Auditors
hunt **invariants and failure paths** (especially data safety, auth,
persistence, packaging law) — not “does the suite pass?”

---

## Capability classes (not brand names)

| Class | Role in the loop | Typical use |
| --- | --- | --- |
| **Volume implementer** | High throughput, low–medium thinking | Well-defined factory units after forge/delivery |
| **Design / high-judgment implementer** | Strong taste + decomposition | Ambiguous design, UX/voice, emotionally sensitive prose, fuzzy architecture |
| **Review / honesty** | Independent judgment, high thinking | Auditor Hands; release / law / claim-gate CTO notes |
| **Local / draft** | Zero or low marginal cost draft | Discrete well-specified units; always followed by strong audit when risk is real |
| **Break-glass** | Peak implement when cheap path fails | Stuck after audit+repair, P0 one-shot, or operator pin |

Mind maps project-configured models onto these classes. Multiple providers may
satisfy one class; the **Vivi role record** records which.

**Provider is part of the binding.** Project overlays must pair each model with
its correct provider (example: volume GLM-class models often require a specific
vendor provider id such as `zai` — never assume the default codex/openai
provider). A model string without the matching `provider` is a misconfiguration.

**Native harness vs provider.** Some design-class tools are **full harnesses**
(own CLI/agent loop), not a provider behind Pi. If the project overlay says a
slot runs **Kimi** (or another standalone coding agent), that means
`agent: kimi` (or the matching harness id) and the **vendor binary** — not
`agent: pi` with a Moonshot/Kimi model id. Do not fold a native agent into Pi
for roster uniformity.

---

## Unit tags (Mind labels when filing)

Tag each unit in the task body (or Mind memo) with one primary shape:

| Tag | Meaning | Default implementer class |
| --- | --- | --- |
| **`mechanical`** | Frozen goal, narrow write scope, clear done-when and validation commands | **Volume implementer** (low–medium thinking) |
| **`design`** | Product/API/UX shape, structure that users feel, campaign framing | **Design / high-judgment** |
| **`sensitive`** | User-facing voice, public docs tone, trust/safety wording | **Design / high-judgment** |
| **`ambiguous`** | Cannot yet freeze mid-tier contract without research | **Design / high-judgment** *or* Mind/forge first — do not dump raw ambiguity on volume |
| **`repair`** | Closed list of auditor findings + regression tests | **Same class as original implement** (usually volume) |

**Well-defined** means **Head lowering** (or an existing delivery unit / repair
list) already paid for thinking — not the implementer Hand inventing it:

- done-when + non-goals  
- exact write scope (repos/paths)  
- invariants (esp. data safety, packaging law)  
- validation commands  
- for multi-unit stages: durable `$delivery` doc + goal-check READY parent goal

**Law:** campaign goal → **Head lowers** (`$campaign`: goal-forge → goal-check →
`$delivery`) → Mind files Hands. Hands do not lower raw goals through factory.
Full pipeline: [`lowering.md`](lowering.md).

Volume implementers at low thinking **only** pay off when that packet quality
is real. Loose tickets recreate “green tests, high-severity miss.”

---

## Role routing

| Role | Default class | Thinking | Notes |
| --- | --- | --- | --- |
| **Implementer Hand** | Volume for `mechanical` / `repair`; design class for `design` / `sensitive` / hard `ambiguous` | Low–medium (volume); high (design) | Identity (`hand-N`) ≠ model. Rebind per unit when shape changes. |
| **Auditor Hand** | **Review / honesty** | **High** (default) | Spend quality budget here. Same harness as product Hands when alignment requires it; prefer model **independence** from the implementer when risk is high. Process remains **`$auditor`**. |
| **head-cto** | Review / honesty for claim-gates and architecture truth; design class when residual is taste/structure | High when used | **Not** the default code-review queue (auditors own that). |
| **head-ceo** | Design class for chapter/vision/**goal lowering**; volume OK for mechanical map hygiene | Medium–high | Default **lowering seat** when assigned (`goal-check` → delivery); advisory on cadence. |
| **head-cxo** / other Heads | Volume often enough; design class when purity is structural feel | Medium–high | Cadence-bound; not bag drain. |
| **Mind** | Operator-selected capable control-plane model | Medium+ | Tasking quality matters more than Hand brand. |

### Code review policy (unchanged process)

- Product Hands ship unit quality.  
- **Code review** → **`auditor-1` / `auditor-2`** + **`$auditor`**, not head-cto by default.  
- Mind triages: low-risk may accept implementer evidence; **risk / auth-persistence / packaging law / sample** → auditor.  
- **Never** universal review on every completion (quota and latency).  
- Prefer **fewer, deeper** auditor passes over every-unit skim.

### Repair loop

```text
implement (volume or design class)
  → auditor (review class, high) when risk/sample requires it
  → repair task: ranked findings only + regression tests (same implementer class)
  → re-audit on P0/P1 or sample — not “Hand said fixed”
```

Do not upgrade to design/break-glass for repair unless the fix is a **redesign**.

---

## Scarcity and capacity

Treat **review-class** and **design-class** capacity as scarce relative to volume:

1. Do not put review-class models on routine mechanical Hand units.  
2. Cap concurrent design-class Hands when project overlay says so.  
3. After design-class lands a contract, prefer volume for implementation.  
4. Capacity step: same-harness ladder first (`runtime_fallback`); do not flip
   harness to chase model marketing.  
5. Multi-fleet: share review-class budget across fleets — auditors outrank
   default implementers when capacity is tight.

Subscription or quota details are **operator overlay**, not skill text. The
portable rule is: **spend scarce high-judgment capacity on audit and design,
not on every factory grind.**

---

## Anti-patterns

| Anti-pattern | Why |
| --- | --- |
| Every Hand on the same high-end review-class model | Burns scarce capacity; experiment economics favor volume + audit |
| Volume implementer on open-ended design without forge | Ambiguity → unsafe defaults + overconfident tests |
| Auditor on low thinking / same blind-spot stack with no independence | Misses invariants implementer also missed |
| “109 green tests” as accept without invariant review | Known failure mode for data safety |
| Upgrade model for repair without ranked findings | Redesign theater; no regression focus |
| Hardcoding model strings as Hand identity | Axes: identity ≠ assignment ≠ runtime |
| Treating head-cto as universal code review | Auditors own review; CTO owns gate honesty |

---

## Mind checklist when filing a unit

1. Tag shape: `mechanical` | `design` | `sensitive` | `ambiguous` | `repair`.  
2. If not well-defined and shape is mechanical → **forge/delivery first**, or retag.  
3. Choose implementer class from the table; rebind Hand runtime if needed.  
4. Decide auditor: mandatory (risk) / sample / none (low-risk evidence).  
5. File auditor on **review-class @ high** when used.  
6. Repair stays on original implementer class unless redesign.  

Project-specific model names and thinking defaults: project overlay (e.g.
`.vivi/model-selection.md` or Agents.md pointer). Skill stays portable.
