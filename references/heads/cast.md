# Head cast (fleet executive layer)

Load when arming Heads, writing role prompts, or renaming identities.  
**Personas** (depth): [`personas/`](personas/) — former `$executive-team` role bodies.  
**Loops** (process): [`../heads.md`](../heads.md) — assign → report, side-lane buckets, post-main review.

## Canonical Head identities

| Identity | Persona file | Primary loop | Notes |
| --- | --- | --- | --- |
| **`head-ceo`** | [`personas/ceo.md`](personas/ceo.md) | Vision, priority, sequencing, **side-lane buckets** (+ effort/est_tokens), camp-wide “what next” | **Replaces** default name `head-strategist` |
| **`head-cto`** | [`personas/cto.md`](personas/cto.md) | **Code review / bugs on main after merge**; fail-closed engineering quality | **Replaces** default name `head-correctness` |
| **`head-purity`** | (fleet loop only; optional persona later) | Unearned complexity / excess layers | Keep as Head; not a C-suite rename |
| **`head-cpo`** | [`personas/cpo.md`](personas/cpo.md) | Product direction, requirements (on demand) | Lazy — identity/tmux only when used |
| **`head-coo`** | [`personas/coo.md`](personas/coo.md) | Ops readiness / verification lens (on demand) | Do not confuse with Mind ops loop |
| **`head-cso`** | [`personas/cso.md`](personas/cso.md) | Security / privacy / abuse (on demand) | |
| **`head-cfo`** | [`personas/cfo.md`](personas/cfo.md) | Cost, effort, sustainability (on demand) | Pairs with token/cost calibration |
| **`head-cmo`** | [`personas/cmo.md`](personas/cmo.md) | Positioning / audience (on demand) | |
| **`head-cxo`** | [`personas/cxo.md`](personas/cxo.md) | Operator-facing prose drafts To mind (on demand) | Never a second Mind pane |

**Default armed Heads** for a coding fleet: `head-ceo` + `head-cto` (+ optional `head-purity`).  
Others: create mail identity and pane only when Mind assigns them.

## Legacy aliases (migration)

| Legacy | Canonical |
| --- | --- |
| `head-strategist`, bare `strategist`, camp `*-strategist` | **`head-ceo`** (same loop) |
| `head-correctness`, bare `correctness`, camp `*-correctness` | **`head-cto`** (same loop) |

New fleets and new docs use **`head-ceo` / `head-cto`**. Live camps may keep `mgs-strategist` session names until renamed; process law is the Head job, not the string.

## Harness

| Slot | Harness |
| --- | --- |
| Mind + Hands | Product harness (Mind’s family) |
| All Heads | Prefer **same alternate harness** as classic strategist (e.g. Pi + strong model) |

## Load rules (token budget)

| Situation | Load |
| --- | --- |
| Thin FLEET_CYCLE | Main skill only — not full personas |
| Assign head-ceo | `heads.md` + optional `personas/ceo.md` + shared rules if depth needed |
| Assign head-cto | `heads.md` correctness/CTO loop + optional `personas/cto.md` |
| Rare head-cso etc. | Persona file + shared rules for that assign only |

## Mind vs head-ceo

| Mind | head-ceo |
| --- | --- |
| Operator TUI; FLEET_CYCLE; file/wake Hands | Advise priority and side-lane buckets |
| Owns bags and merge clock | Does not fill Hand bags or merge |
| Continuous | Episodic assign → report |

## Archived skill

`$executive-team` is **archived**. Persona content lives here. Do not re-arm a separate executive-team ops runtime; use fleet Heads.
