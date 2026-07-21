# Pi role wrappers (`pi-hand` / `pi-head`)

Fleet-specific launch helpers that sit in front of the Pi binary. They live in
the Fleet skill so Hand/Head launch policy is versioned with Fleet, not only as
ad-hoc `~/.local/bin` folklore.

| Wrapper | Path | Purpose |
| --- | --- | --- |
| **pi-hand** | `scripts/pi-hand` | Implementer Hands: **no extension discovery** |
| **pi-head** | `scripts/pi-head` | Advisor Heads: **no extensions** + **deny edit/write** |

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

Wrappers inject the right defaults so a Pi launch cannot forget extension/tool policy.

**Invariant (reinit / vivi_pty):** the launch command is constructed from the Vivi role record (harness + provider/model/thinking + kind). `fleet-runtime.py reinit` removes the session id and starts with desired argv — it must **not** `session.restart` a stale plain-`pi` binding.

## Hand (`pi-hand`)

```bash
# equivalent core behavior
pi --no-extensions --provider openai-codex --model … --approve
```

- Keeps **read / bash / edit / write** (and skills) so Hands can implement.
- Does **not** load installed extensions → no `fleet_attach`, no Mind widgets.
- Operators can still pass `-e /path/to/extension.ts` explicitly if needed.

## Head (`pi-head`)

```bash
pi --no-extensions --exclude-tools edit,write --provider … --approve
```

- No Fleet Mind extension.
- No built-in **edit** / **write** tools → harder to “just ship a fix” as a Head.
- **bash remains** (Heads need `rg`, `git log`, `cargo test` read-outs). This is
  not a full sandbox; Head policy still forbids product implementation and
  destructive git. Tighten later with a custom tool allowlist if Pi grows more
  mutators.

Optional env:

```bash
PI_HEAD_EXCLUDE_TOOLS=edit,write   # default
PI_BIN=/path/to/pi
PI_HAND_EXTRA='--offline'          # extra flags for either wrapper
PI_HEAD_EXTRA='--offline'
```

## Install convenience symlinks (optional)

Wrappers are runnable from the skill tree. Optional PATH hooks:

```bash
FLEET=/Users/ianzepp/work/ianzepp/fleet   # or ~/.agents/skills/fleet if linked
ln -sf "$FLEET/scripts/pi-hand" ~/.local/bin/pi-hand
ln -sf "$FLEET/scripts/pi-head" ~/.local/bin/pi-head
```

`pi-lite` (system-prompt from `~/AGENTS.md`) remains a separate concern; Hands
that need it can compose:

```bash
# if pi-lite is still desired for prompt only — prefer not nesting; set system
# prompt in launch or use pi-hand alone with project AGENTS.md discovery.
```

## Role capacity + wrapper selection

The runtime constructs the launch from the Vivi role record. Hands get `pi-hand`; Heads get `pi-head`; capacity flags come from the role:

```bash
vivi role set hand-1 --project <root> --harness tmux \
  --provider openai-codex --model gpt-5.5 --thinking medium
# runtime constructs: pi-hand --provider openai-codex --model gpt-5.5 --thinking medium --name hand-1 --approve
```

```bash
vivi role set head-cto --project <root> --harness tmux \
  --provider openai-codex --model gpt-5.5 --thinking high
# runtime constructs: pi-head --provider openai-codex --model gpt-5.5 --thinking high --name head-cto --approve
```

**Mind** sessions (Grok or Pi with Fleet UI) should **not** use `pi-hand` /
`pi-head`. Mind may load the extension explicitly:

```bash
pi -e /Users/ianzepp/work/ianzepp/fleet/pi/extensions/fleet.ts …
```

## Migration checklist

1. Set each Hand role's harness to `tmux` (or `vivi_pty`) on the Vivi role record.
2. Set each Head role's harness likewise.
3. Restart contaminated panes (`fleet-runtime restart --role … --force`).
4. Confirm status line is not `monitor:swarm` / Mind cycle chrome in Hand panes.

## Relationship to pi-lite

| Helper | Owner | Job |
| --- | --- | --- |
| `pi-lite` | host `~/.local/bin` | inject `~/AGENTS.md` as system prompt |
| `pi-hand` / `pi-head` | **Fleet skill** | role-shaped safety flags for Fleet |

Do not merge them into one opaque binary without documenting both jobs.
