# Fleet UI surface

The Codex plugin's supported UI surface is the structured result from the
`fleet_dashboard` MCP tool. It renders the same compact information as the Pi
panel—Mind/Monitor mode, posture, cycle, Hands, Heads, Vivi counts, signals,
and the last cycle summary—inside the task conversation.

Codex plugins do not expose a documented API for a persistent native sidebar,
status chip, or arbitrary desktop panel. The dashboard tool therefore keeps
the presentation model separate from Fleet operations. If an Apps SDK app is
registered later, it can consume the same structured payload without changing
the canonical scripts or Mind policy.
