# Fleet guide (first exposure)

**Audience:** a human or LLM seeing multi-agent `$fleet` for the first time — including someone who received a copy of the skill outside this repo.

**Install, init, or re-attach?** Use **[`getting-started.md`](getting-started.md)** (deps → initialize project → attach Mind). This guide is vocabulary and shape, not those procedures.

**Not the operating manual.** Full process law lives in `fleet/SKILL.md` and `fleet/references/`. Load those when *running* a fleet. This guide is for **orientation**: typical shape, vocabulary, and anti-patterns.

**Do not** treat this file as something Mind must re-read every cycle.

---

## What a fleet is

A **fleet** is a small multi-session coding setup:

| Channel | Truth of… | Typical tool |
| --- | --- | --- |
| **Board / mail** | Work (tasks, needs, wants, status) | Project mailspace (e.g. Vivi) |
| **Panes** | Process (alive, idle, error) | tmux sessions |

Roles follow the **Mind / Head / Hand** pattern (Abbot-style control plane): one coordinator, advisors, workers — not a free-for-all chat room.

```text
campaign / map
      │
      ▼
  MIND ──files targets──► tasking bag
      ▲                        │
      │                        ▼
      └── residuals ────── HAND clears one target

  Heads (head-ceo / head-cto / head-cxo) ──mail To: mind──► Mind triages
```

**Progress** = open tasking + an honest map — not approval stamps or stage GO/NO-GO.

---

## Canonical roles and identities

| Role | Job | Identity (new fleets) | tmux? |
| --- | --- | --- | --- |
| **Mind** | Ops: fill bags, integrate, pane ops, cycle cadence | **`mind@…`** fleet board | **No** — Mind is the **operator’s current TUI** |
| **Operator mail** | Human escalations while autonomous | **`operator@…`** | **No** — problems / blockers / guidance only (not status) |
| **Steward** | Dead-man: watch Mind cycle ticks; hold + page if freeze | (watchdog) | Yes — **`steward`** pane (not Mind) |
| **Hand** | Execute one selected target | **`hand-1` … `hand-N`** | Yes (name = mail token) |
| **Head** | Advise; never own product bags | **`head-ceo`**, **`head-cto`**, **`head-cxo`** | Yes |

**Binding rule (Hands/Heads):** mail identity token == tmux session name.

**Mind and operator are not fleet process slots.** Do not create dual Mind sessions or tmux named `mind` / `operator`. Scheduled loops (e.g. `FLEET_CYCLE`) run **in the operator conversation**, not via shell inject into a fake Mind pane.

**Operator mail vs recap:** `operator@` accrues **action items for the human** (incidents, unaddressed blockers, bugs that need fix guidance). `operator_recap` is compact **status** of what moved. On return, Mind presents the operator mail list first so you can work through issues.

**Steward / dead man:** a fleet-local tmux pane that requires Mind to **rearm** after every successful `FLEET_CYCLE`. If the Grok loop dies or turns abort before completing (hook deadlock), steward **holds** the fleet, files **operator@**, and may send a **preauthorized external email** page. Disarm when you stop the loop. Not a second Mind.

---

## Who does what (one sentence each)

| Who | Does | Does not |
| --- | --- | --- |
| **Mind** | File/refill bags, wake/reinit Hands, merge clock, absorb reports, capacity packing; file/present **operator mail** | Peer-review every packet; run full `$polish` / `$housekeeping` itself; status To `operator@` |
| **operator@** | Accrue human problems/blockers/guidance while away | Status updates; Hand bag drain |
| **hand-1** | Main checkout; spine work; **only** slot that merges packets → main | Wait for GO mail; erase foreign WIP |
| **hand-2+** | Packet/worktree lanes; unit → refill; theme → ready-to-merge | Merge to main; invent unbounded spine |
| **head-ceo** | Vision, sequencing, **side-lane candidate buckets** (+ effort/token ballparks) | File Hand tasks; stamp GO/NO-GO |
| **head-cto** | **Code review / bugs on main after merge** | Own product tasking; block merges as license |
| **head-cxo** | Complexity / purity (not operator-facing) | Own product tasking; operator email |
| *optional* | `head-cpo` / `head-cso` / … (personas under `fleet/references/heads/`) | Lazy Heads when needed |

**Multi-hand split:** Mind **doles out** work. head-ceo **proposes** what hand-2+ *could* run in parallel. Hands only execute assigned targets.

---

## Dual channel in practice

- **Vivi (or equivalent board)** holds full done-when, evidence, and To: ownership.
- **tmux** carries **pointers only** (“show handle X; continue”) — not policy essays.
- Pane classes (sketch): `running` → do not wake; `idle_prompt` + open bag → doorbell (Grok) or **reinit** (Codex); `error_*` / `down` → ops.

Hands should share **Mind’s product harness** (same agent family). Heads **prefer a different model/harness** for second-party opinion.

---

## Typical day (pattern, not a script)

1. **Arm** — mail identities, fleet config, baselines; Hands/Heads in tmux; Mind = this chat.
2. **Map focus** — campaign/factory goal names the current spine (and optional side tracks).
3. **Hands work** — show one task; implement; validate; end-of-unit `$polish` on changed sources; mark done.
4. **Mind cycles** — cheap sensors (bag, HEAD, panes); act only on signal; sleep when quiet.
5. **Scheduled wakes** — durable loops start with `FLEET_CYCLE …` so they are not mistaken for human operator prose.
6. **Mode** — if the human is engaged in this session, Mind stays **interactive** (richer status); after several silent cycles → **autonomous** (compact reports, thin ops). On return, present **operator@** list before status recap.
7. **Integration** — hand-2+ never merges; Mind accepts themes → merge task To hand-1 at a clean breakpoint.
8. **Hygiene** — cheap polish *advisory* after main lands; full `$housekeeping` only at **major inflection** (campaign end, large merge batch, stage closeout).

**Keep the screen moving:** empty bag + map still has unblocked work = **starvation** → Mind files next target and wakes the Hand. Empty because you truly paused = operational pause (say so).

**Don't get stuck:** name the class (decision, dirt, pane, capacity); unstick or pivot same turn — never multi-cycle “blocked” without new evidence.

---

## Multi-hand: what hand-2 is for

| hand-1 | hand-2+ |
| --- | --- |
| Main, merges, critical spine | Side lane / packet; parallel safe work |

head-ceo reports a **bucket** of side-lane candidates, each with:

- why safe off main  
- seams vs spine  
- **effort** `S|M|L|XL` and **est_tokens** (ballpark)  

Mind picks from the bucket, binds a packet, files tasks, and later records **actual vs estimate** so future packing accounts for model-to-model cost bias.

Leaving hand-2 empty for many cycles while the map has a second unblocked track is Mind starvation of the second lane — not “one worker is enough.”

---

## Tasking vocabulary (board)

| Kind | Meaning |
| --- | --- |
| **task** | Implementable work with done-when (including defects) |
| **need** | Decision / authority — include default + options |
| **want** | Non-blocking later idea |
| **mail** | Deliberation / status — not the primary queue |

**To:** `hand-N` = work; `mind` = fleet board; `operator` = human escalations only.

Queue kind is **not** severity. Critical defects are still **tasks**.

Absorb vs accept: **absorb** = bookkeeping when something moved; **accept** = good enough to clear review debt or queue merge — **not** full code review (that is head-cto on main).

---

## Fleet files (project overlay)

The skill is portable process. A project usually adds:

```text
.vivi/fleet.json          # roster, agents, cwd, hosts
.vivi/mind-baseline.json  # cycle counters, debt, candidates, calibration
mailspace identities      # mind, hand-N, head-*
optional role prompts     # Head bootstraps
```

Exact paths and product map (factory/campaign) are fleet-local.

---

## Hard “don’ts” (share these early)

1. **No second Mind** — no second Mind process; no shell `send-keys` into a fake Mind pane as the control plane.  
2. **No GO/NO-GO game warden** — residuals and empty bags, not stage licenses.  
3. **No destructive git on foreign dirty** — classify A/B/C; never stash/reset/clean to “make room.”  
4. **No packet merge from hand-2+** — only hand-1 merges to main.  
5. **No Heads owning product bags** — they advise; Mind files.  
6. **No housekeeping after every land** — inflection only; polish is the cheap post-main backstop.  
7. **No treating FLEET_CYCLE as operator silence** while the human chatted between fires — count session history.  
8. **No compact one-line status while interactive** — operator is watching; report richly.

---

## Related skills (often paired)

| Skill | Role in a fleet |
| --- | --- |
| Board CLI (Vivi) | `companion-fallbacks.md` (Mail) |
| Polish / housekeeping / correctness | `companion-fallbacks.md` |
| Map / factory execution | `companion-fallbacks.md` (Campaign / Factory) |

---

## How to get operational

1. **[`getting-started.md`](getting-started.md)** — install **Vivi**, check host, arm a minimal fleet.  
2. Read this guide once for vocabulary.  
3. Load **`$fleet`** (`fleet/SKILL.md`) when arming or acting as Mind.  
4. Open **references/** only as the surface hits them (tasking, dual-channel, mind-cycle, heads, multi-lane, runtime-config, ssh-remote).  
5. Bind a real project overlay (identities + fleet JSON + map).  
6. Prefer fail-fast cycles: sensors first, act on signal, sleep when quiet.

---

## Design drafts (not operational process)

- **[Multi-fleet Mind sessions](multi-fleet-design.md)** (design) + **`$fleet` `references/multi-fleet.md`** (ops): session-attach; mini-cycle each fleet on the `FLEET_CYCLE` line; **tmux session = fleet / window = role** preferred for multi-fleet hosts.
