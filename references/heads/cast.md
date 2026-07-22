# Head cast (fleet advisor layer)

Load when arming Heads, writing role prompts, or renaming identities.  
**Personas** (depth): [`personas/`](personas/).  
**Loops** (process): [`../heads.md`](../heads.md) — prepare → claim → settle, map-health, side-lane buckets, post-main review, purity.
**Posture:** [`../posture.md`](../posture.md) — growth / standby / dormant dial for Head proactivity.

These seats continue the camp **strategist / correctness / purity** advisors. They are **not** a free-standing `$executive-team` board of directors.

## Canonical Head identities

| Identity | Persona file | Primary loop | Legacy |
| --- | --- | --- | --- |
| **`head-ceo`** | [`personas/ceo.md`](personas/ceo.md) | **Strategist:** map health, misprioritization, gate honesty, expansion (growth) / stewardship (standby), **side-lane buckets** (+ effort/est_tokens) | `strategist`, `head-strategist` |
| **`head-cto`** | [`personas/cto.md`](personas/cto.md) | **Gate honesty / architecture** (not default code-review queue — that is **Hand** `auditor-1/2` + `$auditor`) | `correctness`, `head-correctness` |
| **`head-cxo`** | [`personas/cxo.md`](personas/cxo.md) | **Purity:** unearned complexity / shape debt (incl. gates invented by coupling) | `purity`, `head-purity` |
| **`head-cpo`** | [`personas/cpo.md`](personas/cpo.md) | Product direction, requirements | Usually on-call (`every_n_loops: 0`) |
| **`head-coo`** | [`personas/coo.md`](personas/coo.md) | Ops readiness / verification; optional DR stewardship when `disaster_recovery` enabled | Usually on-call; never performs backup/restore |
| **`head-cso`** | [`personas/cso.md`](personas/cso.md) | Security / privacy / abuse | Usually on-call (`every_n_loops: 0`); schedule or task during deploy windows |
| **`head-cfo`** | [`personas/cfo.md`](personas/cfo.md) | Cost, effort, sustainability (on demand) | Pairs with cost calibration |
| **`head-cmo`** | [`personas/cmo.md`](personas/cmo.md) | Positioning / audience (on demand) | Lazy |
| **`head-founders`** | [`personas/founders.md`](personas/founders.md) | **Founders Council** portfolio sponsor: experiment series health; continue/reshape/park/kill; parent-cycle clock | Label: `founders-council`; mail often `founders-council@` |

**Default armed Heads** (coding fleet): `head-ceo` + `head-cto` + optional **`head-cxo`**.  
When the workspace runs experiment series under `experiments/`, also arm **`head-founders`** (`every_n_loops: 4` sponsor force-check).  
**Code-review Hands** (under `hands`, not a new class): **`auditor-1` / `auditor-2`** + `$auditor`.  
Other Heads: mail identity + pane only when Mind assigns them.

### CEO = strategist (not org-chart CEO)

`head-ceo` is the **priority / sequencing / map-research** seat. Job language is camp **strategist**: connect tracks, catch inverted priorities, name producer work for blocked consumers, propose parallel work with costs. It is **not** Proton daily-summary automation or “create tasks for the CTO” theater — Mind prepares Hands from CEO settlements.

### CXO = purity (not operator voice)

In fleet, **CXO ≠ external/operator communications.** That is **Mind** (human TUI + recap / interactive reports).

**Why purity on CXO:** the **XO executes**. Hands (and delivery path) are the execution surface. Unearned complexity, excess layers, muddy modules make execution slower, riskier, less idiot-proof. head-cxo has a **direct interest** in product shape simple enough that work stays executable — not in speaking for the operator.

## Harness

| Slot | Harness | Preferred model |
| --- | --- | --- |
| Mind + Hands | Product harness (Mind’s family) | — |
| All Heads | **Pi**, zai (lightweight, advisory-only) | **GLM 5.2** (all roles; high or xhigh) |

## Load rules (token budget)

| Situation | Load |
| --- | --- |
| Thin FLEET_CYCLE | Main skill only — not full personas |
| Assign head-ceo | `heads.md` + `personas/ceo.md` (+ shared rules if depth) |
| Assign head-cto | `heads.md` + `personas/cto.md` |
| Assign head-cxo | `heads.md` purity loop + `personas/cxo.md` |
| Rare head-cso etc. | Persona + shared rules for that assign only |

## Mind vs Heads (operator surface)

| Mind | Heads |
| --- | --- |
| **Is** the operator conversation | Never operator-facing email or dual Mind |
| FLEET_CYCLE, prepare/wake roles, merge clock | Advise To: mind only |
| Interactive rich status / recap for human | Reports for Mind triage |

## Archived skill

Persona content lives here. Do not re-arm a separate executive-team ops runtime; use fleet Heads.
