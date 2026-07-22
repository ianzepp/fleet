# Pi role launch policy (Hands / Heads)

> **The `pi-hand` and `pi-head` wrapper scripts have been removed.** The
> role-shaped launch policy they encoded is still valid and is now applied by
> constructing the `pi` launch directly from the Vivi role record. This file
> records the policy so launch arguments stay versioned with Fleet.

Fleet-specific launch policy that sits in front of the Pi binary. The policy
lives in the Fleet skill so Hand/Head launch arguments are versioned with
Fleet, not only as ad-hoc `~/.local/bin` folklore.

| Role | Policy | Pi flags |
| --- | --- | --- |
| **Hand** (implementer) | **no extension discovery** | `pi --no-extensions …` |
| **Head** (advisor) | **no extensions** + **deny edit/write** | `pi --no-extensions --exclude-tools edit,write …` |

Related: [`pi.md`](pi.md) (Mind extension — load **only** in Mind sessions).

## Why

Hands have been loading the shareable **Fleet Pi extension** from global Pi
settings, then calling `fleet_attach` / running Mind loops inside Hand panes
(e.g. quay hand-2 contamination). That extension is for **Mind** sessions.

Pi already supports:

```text
--no-extensions, -ne     disable extension discovery (explicit -e still works)
--exclude-tools, -xt     denylist tools (edit, write, …)
--tools, -t              allowlist
--no-tools, -nt          disable all tools
```

Apply the right defaults in the launch argv so a Pi launch cannot forget
extension/tool policy. The removed wrappers did this automatically; now the
launch command (constructed from the Vivi role record) must carry the flags.

**Invariant (reinit / vivi_pty):** the launch command is constructed from the
Vivi role record (harness + provider/model/thinking + kind). Reinit removes the
session id and starts with the desired argv — it must **not** `session.restart`
a stale plain-`pi` binding. The `fleet-runtime.py` helper is removed; reinit is
done by recreating the session directly.

## Hand policy

```bash
# equivalent core behavior (formerly pi-hand)
pi --no-extensions --provider openai-codex --model … --approve
```

- Keeps **read / bash / edit / write** (and skills) so Hands can implement.
- Does **not** load installed extensions → no `fleet_attach`, no Mind widgets.
- Operators can still pass `-e /path/to/extension.ts` explicitly if needed.

## Head policy

```bash
# equivalent core behavior (formerly pi-head)
pi --no-extensions --exclude-tools edit,write --provider … --approve
```

- No Fleet Mind extension.
- No built-in **edit** / **write** tools → harder to “just ship a fix” as a Head.
- **bash remains** (Heads need `rg`, `git log`, `cargo test` read-outs). This is
  not a full sandbox; Head policy still forbids product implementation and
  destructive git. Tighten later with a custom tool allowlist if Pi grows more
  mutators.

Optional env (for hand-built launch commands):

```bash
PI_HEAD_EXCLUDE_TOOLS=edit,write   # default
PI_BIN=/path/to/pi
```

## Role capacity + policy selection

The launch command is constructed from the Vivi role record. Hands get the
Hand policy flags; Heads get the Head policy flags; capacity flags come from
the role:

```bash
vivi role set hand-1 --project <root> --harness tmux \
  --provider openai-codex --model gpt-5.5 --thinking medium
# launch: pi --no-extensions --provider openai-codex --model gpt-5.5 --thinking medium --name hand-1 --approve
```

```bash
vivi role set head-cto --project <root> --harness tmux \
  --provider zai --model glm-5.2 --thinking high
# launch: pi --no-extensions --exclude-tools edit,write --provider zai --model glm-5.2 --thinking high --name head-cto --approve
```

**Mind** sessions (Grok or Pi with Fleet UI) should **not** use the Hand/Head
policy flags. Mind may load the extension explicitly:

```bash
pi -e /Users/ianzepp/work/ianzepp/fleet/pi/extensions/fleet.ts …
```

## Migration checklist

1. Set each Hand role's harness to `tmux` (or `vivi_pty`) on the Vivi role record.
2. Set each Head role's harness likewise.
3. Restart contaminated panes by recreating the session directly.
4. Confirm status line is not `monitor:swarm` / Mind cycle chrome in Hand panes.

## Relationship to pi-lite

| Helper | Owner | Job |
| --- | --- | --- |
| `pi-lite` | host `~/.local/bin` | inject `~/AGENTS.md` as system prompt |
| Hand/Head policy flags | **Fleet skill** | role-shaped safety flags for Fleet (formerly `pi-hand` / `pi-head` wrappers) |

Do not merge them into one opaque binary without documenting both jobs.
