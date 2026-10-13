---
name: agent-flows
description: Build n8n-style flows and teams of cooperating agents.
version: 1.0.0
author: Sunnatilla, VAEL Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  vael:
    tags: [flows, automation, orchestration, multi-agent, cyberai]
    category: autonomous-ai-agents
    related_skills: [vael-agent, dynamic-workflow]
---

# Agent Flows Skill

Build automations as flow documents and run them with `vael flow`, or split a job across several
agents that hand work to each other. It does not solve CyberAI challenges: for those you mentor.

## When to Use

- The user wants a repeatable automation: "every time X, do A then B, and branch on the result".
- The user already has a flow from the CyberAI flow editor and wants it run on this machine.
- A job is too big for one agent and splits into parts, or needs a manager that checks the parts.

## Prerequisites

- A flow is JSON in the CyberAI flow format; `vael flow new` writes a valid starter.
- `vael` and `agent` nodes run this machine's VAEL Agent with the user's own keys.
- Teams of agents: the `kanban` toolset is only active inside a worker the dispatcher spawned; use
  `terminal` with `vael kanban ...` from a normal session.

## How to Run

Write the file with `write_file`, then check and run it with `terminal`:

```bash
vael flow new digest.json --name "Daily digest"
vael flow validate digest.json
vael flow run digest.json --input topic=DNS
```

`validate` lists every problem at once. `run` prints each step on stderr and the last output on stdout;
add `--json` for every step.

## Quick Reference

Document: `{"schemaVersion": 1, "name": "...", "nodes": [...], "edges": [...]}`. A node is
`{"id", "type", "position": {"x", "y"}, "data": {...}}`; an edge is
`{"id", "source", "target", "sourceHandle", "targetHandle"}` with handles `null` for the normal path.

| Node | `data` | Ports out |
|------|--------|-----------|
| `start` | `inputKeys` (names that must be in the input) | `out` |
| `action` | `action` = `noop`, `log` or `set`; `message` (`key=value; key2=value2` for `set`) | `out` |
| `transform` | `mapping` (text or a template) | `out` |
| `vael` | `prompt`, optional `model`, `provider` | `out` |
| `agent` | `task` | `out` |
| `condition` | `expression` | `true`, `false` |
| `loop` | `items` (JSON array or a reference), `maxIterations` (max 20) | `loop` (body), `exit` |
| `delay` | `durationMs` (max 30000) | `out` |
| `http` | `url`, `method`, `headers` (JSON text), `body` | `out` |

References: `{{input.key}}`, `{{steps.<nodeId>.output.<path>}}`, `{{loop.item}}`, `{{loop.index0}}`.
A path that does not exist is an error.
`telegram` and `pc` nodes only run inside CyberAI.

Teams of agents:

- `delegate_task` for parts that finish inside this session.
- `vael kanban swarm "<goal>" --worker PROFILE:TITLE --verifier PROFILE --synthesizer PROFILE` for
  parallel workers, then a verifier, then a writer; they share notes on the root card.
- `vael peer dm <peer> "<message>"` to hand work to an agent on another machine.

## Procedure

1. Ask what starts the flow and what the end result is; name the inputs.
2. Draw the path as nodes and edges; keep ids short (`start`, `fetch`, `check`).
3. Write the file, run `vael flow validate`, fix everything it lists, then run it with real input.
4. Give flows that use `vael` or `agent` nodes the narrowest toolset: the default is `safe` (no
   terminal). Pass `--toolsets` only when the user asks and the flow is theirs.
5. For a team, make one card per part with a clear result; the verifier checks the result against the
   goal and the synthesizer writes the answer. Say who plays the manager.

## Pitfalls

- A flow is not a script: no code node exists, so use `agent` for anything that needs thinking.
- A `condition` needs both branches connected, or the missing one ends the run quietly.
- Do not paste secrets into a flow; `http` refuses credential headers on purpose.
- CyberAI CTF challenges (flags look like `CYBERAI{...}`): explain the technique and give a hint, never the
  solution or a flag. A flow or team must not be built to solve one.

## Verification

`vael flow validate <file>` prints `OK` and the node count, and a run with real input ends with the
output the user expects and no `ERR` step.
