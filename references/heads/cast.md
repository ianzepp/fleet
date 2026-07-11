# Head cast (fleet executive layer)

Load when arming Heads, writing role prompts, or renaming identities.  
**Personas** (depth): [`personas/`](personas/) — former `$executive-team` role bodies (fleet-adapted).  
**Loops** (process): [`../heads.md`](../heads.md) — assign → report, side-lane buckets, post-main review, purity.

## Canonical Head identities

| Identity | Persona file | Primary loop | Notes |
| --- | --- | --- | --- |
| **`head-ceo`** | [`personas/ceo.md`](personas/ceo.md) | Vision, priority, sequencing, **side-lane buckets** (+ effort/est_tokens) | **Replaces** `head-strategist` |
| **`head-cto`** | [`personas/cto.md`](personas/cto.md) | **Code review / bugs on main after merge** | **Replaces** `head-correctness` |
| **`head-cxo`** | [`personas/cxo.md`](personas/cxo.md) | **Complexity / purity** — unearned layers, shape debt | **Replaces** `head-purity`. **Not** operator-facing |
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
**head-cxo** is the shape/complexity auditor (classic purity loop).

## Legacy aliases (migration)

| Legacy | Canonical |
| --- | --- |
| `head-strategist`, bare `strategist`, camp `*-strategist` | **`head-ceo`** |
| `head-correctness`, bare `correctness`, camp `*-correctness` | **`head-cto`** |
| `head-purity`, bare `purity`, camp `*-purity` | **`head-cxo`** |

New fleets use **`head-ceo` / `head-cto` / `head-cxo`**. Live camps may keep old
session names until renamed; process law is the job, not the string.

## Harness

| Slot | Harness |
| --- | --- |
| Mind + Hands | Product harness (Mind’s family) |
| All Heads | Prefer **same alternate harness** as classic strategist (e.g. Pi + strong model) |

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

`$executive-team` is **archived**. Persona content lives here. Do not re-arm a
separate executive-team ops runtime; use fleet Heads.
