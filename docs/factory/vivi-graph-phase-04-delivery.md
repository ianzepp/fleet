# Delivery Spec: Fleet companion — prepare --node

## Unit

Let `fleet.py prepare --node <graph>:<source-id>` bind ready Vivi work-graph
nodes into the existing prepare → claim → settle chain without encoding Fleet
roles in Vivi.

## Requirements

1. `prepare --node graph:source-id` resolves the node via
   `vivi graph ready graph --json`; topology remains on the Mermaid `graph show`
   surface.
2. Refuse blocked, active, terminal, or missing nodes.
3. Create the role task as today; record `graph_node` on the receipt.
4. `claim` after success calls `vivi graph activate <node> --task <handle>`.
5. `settle` does **not** auto-complete the graph node (disposition remains
   explicit).
6. Tests cover ready prepare+claim path and blocked prepare refusal.

## Repo

`~/work/ianzepp/fleet` only. Vivarium already provides activate/ready/show.
