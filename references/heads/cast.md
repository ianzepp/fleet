# Head cast (fleet executive layer)

Load when arming Heads, writing role prompts, or renaming identities.  
**Personas** (depth): [`personas/`](personas/).  
**Loops** (process): [`../heads.md`](../heads.md) — assign → report, side-lane buckets, post-main review, purity.

## Canonical Head identities

| Identity | Persona file | Primary loop | Notes |
| --- | --- | --- | --- |
| **`head-ceo`** | [`personas/ceo.md`](personas/ceo.md) | Vision, priority, sequencing, **side-lane buckets** (+ effort/est_tokens) | Default sequencing Head |
| **`head-cto`** | [`personas/cto.md`](personas/cto.md) | **Code review / bugs on main after merge** | Post-main review Head |
| **`head-cxo`** | [`personas/cxo.md`](personas/cxo.md) | **Complexity / purity** — unearned layers, shape debt | **Not** operator-facing |
| **`head-cpo`** | [`personas/cpo.md`](personas/cpo.md) | Product direction, requirements (on demand) | Lazy |
| **`head-coo`** | [`personas/coo.md`](personas/coo.md) | Ops readiness / verification lens (on demand) | Not Mind’s FLEET_CYCLE |
| **`head-cso`** | [`personas/cso.md`](personas/cso.md) | Security / privacy / abuse (on demand) | Lazy |
| **`head-cfo`** | [`personas/cfo.md`](personas/cfo.md) | Cost, effort, sustainability (on demand) | Pairs with cost calibration |
| **`head-cmo`** | [`personas/cmo.md`](personas/cmo.md) | Positioning / audience (on demand) | Lazy |

**Default armed Heads** for a coding fleet: `head-ceo` + `head-cto` + optional **`head-cxo`**.  
Others: mail identity + pane only when Mind assigns them.

### CXO = purity (not operator voice)

In fleet, **CXO does not mean external/operator communications.** That is **Mind**
(the human’s TUI + recap / interactive reports).

**Why purity sits on CXO:** the **XO executes**. Hands (and the fleet’s delivery
path) are the execution surface. Unearned complexity, excess layers, and muddy
modules make execution slower, riskier, and less idiot-proof. head-cxo therefore
has a **direct interest** in keeping the product shape simple enough that work
stays executable — not in speaking for the operator. Classic purity loop, org
title that owns the pain of complexity.

## Harness

| Slot | Harness |
| --- | --- |
| Mind + Hands | Product harness (Mind’s family) |
| All Heads | Prefer **same alternate harness** as classic head-ceo (e.g. Pi + strong model) |

## Load rules (token budget)

| Situation | Load |
| --- | --- |
| Thin FLEET_CYCLE | Main skill only — not full personas |
| Assign head-ceo | `heads.md` + optional `personas/ceo.md` |
| Assign head-cto | `heads.md` + optional `personas/cto.md` |
| Assign head-cxo | `heads.md` purity loop + optional `personas/cxo.md` |
| Rare head-cso etc. | Persona + shared rules for that assign only |

## Mind vs Heads (operator surface)

| Mind | Heads |
| --- | --- |
| **Is** the operator conversation | Never operator-facing email or dual Mind |
| FLEET_CYCLE, file/wake Hands, merge clock | Advise To: mind only |
| Interactive rich status / recap for human | Reports for Mind triage |

## Archived skill

Persona content lives here. Do not re-arm a
separate executive-team ops runtime; use fleet Heads.
