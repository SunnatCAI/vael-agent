"""``vael flow`` - validate and run flow documents on this machine.

Flows are the documents the CyberAI flow editor saves, so one drawn there runs here and the other way
round. See ``flow_engine`` (rules) and ``flow_runner`` (execution).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from vael_cli import flow_engine as fe
from vael_cli import flow_runner as fr

STARTER = {
    "schemaVersion": 1,
    "name": "My first flow",
    "nodes": [
        {"id": "start", "type": "start", "position": {"x": 0, "y": 0}, "data": {"inputKeys": "topic"}},
        {"id": "ask", "type": "vael", "position": {"x": 240, "y": 0},
         "data": {"prompt": "Explain {{input.topic}} in three short sentences."}},
    ],
    "edges": [
        {"id": "e1", "source": "start", "target": "ask", "sourceHandle": None, "targetHandle": None},
    ],
}


def _load(path: str) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except OSError as err:
        raise SystemExit(f"Cannot read {path}: {err.strerror or err}") from None
    except ValueError as err:
        raise SystemExit(f"{path} is not valid JSON: {err}") from None


def _parse_inputs(pairs: Optional[List[str]], raw_json: Optional[str]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    if raw_json:
        try:
            parsed = json.loads(raw_json)
        except ValueError as err:
            raise SystemExit(f"--input-json is not valid JSON: {err}") from None
        if not isinstance(parsed, dict):
            raise SystemExit("--input-json must be a JSON object.")
        values.update(parsed)
    for pair in pairs or []:
        key, eq, value = pair.partition("=")
        if not eq or not key.strip():
            raise SystemExit(f"--input expects key=value, got {pair!r}.")
        values[key.strip()] = value
    return values


def _cmd_validate(args) -> int:
    doc = _load(args.file)
    try:
        fe.validate_document(doc, fr.KNOWN_KINDS)
    except fe.FlowError as err:
        print(f"Not runnable: {args.file}")
        for issue in err.issues or [str(err)]:
            print(f"  - {issue}")
        return 1
    local_only = sorted({n["type"] for n in doc["nodes"] if n["type"] in ("telegram", "pc")})
    print(f"OK: {doc['name']} ({len(doc['nodes'])} nodes, {len(doc['edges'])} edges)")
    if local_only:
        print(f"Note: {', '.join(local_only)} nodes only run inside CyberAI, not with `vael flow run`.")
    return 0


def _cmd_run(args) -> int:
    doc = _load(args.file)
    flow_input = _parse_inputs(args.input, args.input_json)

    def show(step: fr.StepRecord) -> None:
        if args.json:
            return
        mark = "ok " if step.ok else "ERR"
        where = f" [{step.loop_index}]" if step.loop_index is not None else ""
        print(f"  {mark} {step.node_id}{where} ({step.kind}) {step.ms}ms", file=sys.stderr)

    try:
        result = fr.run_flow(doc, flow_input=flow_input, toolsets=args.toolsets, timeout_s=args.timeout, on_step=show)
    except fe.FlowError as err:
        print(f"Not runnable: {err}", file=sys.stderr)
        for issue in err.issues[1:]:
            print(f"  - {issue}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    elif result.ok:
        last = result.last_output
        text = last if isinstance(last, str) else json.dumps(last, ensure_ascii=False, indent=2)
        print(text)
    else:
        print(f"Run failed - {result.error}", file=sys.stderr)
    return 0 if result.ok else 1


def _cmd_new(args) -> int:
    target = Path(args.file)
    if target.exists() and not args.force:
        print(f"{target} already exists (use --force to overwrite).", file=sys.stderr)
        return 1
    doc = dict(STARTER)
    if args.name:
        doc["name"] = args.name
    target.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {target}. Edit it, then: vael flow validate {target}")
    return 0


_ACTIONS = {"validate": _cmd_validate, "run": _cmd_run, "new": _cmd_new}


def flow_command(args) -> int:
    action = getattr(args, "flow_command", None)
    handler = _ACTIONS.get(action or "")
    if handler is None:
        print("Usage: vael flow {new,validate,run} ...", file=sys.stderr)
        return 2
    return handler(args)
