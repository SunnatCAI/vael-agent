"""``vael flow`` subcommand parser."""

from __future__ import annotations

from typing import Callable


def build_flow_parser(subparsers, *, cmd_flow: Callable) -> None:
    """Attach the ``flow`` subcommand (and its sub-actions) to ``subparsers``."""
    flow_parser = subparsers.add_parser(
        "flow",
        help="Validate and run flow documents (the CyberAI flow format)",
        description="Flows are node-and-edge documents, the same ones the CyberAI flow editor saves. "
                    "`vael` and `agent` nodes run this machine's VAEL Agent with your own keys.",
    )
    flow_sub = flow_parser.add_subparsers(dest="flow_command")

    new = flow_sub.add_parser("new", help="Write a starter flow file")
    new.add_argument("file", help="Where to write the flow JSON")
    new.add_argument("--name", help="Flow name")
    new.add_argument("--force", action="store_true", help="Overwrite an existing file")

    validate = flow_sub.add_parser("validate", help="Check a flow file without running it")
    validate.add_argument("file", help="Flow JSON file")

    run = flow_sub.add_parser("run", help="Run a flow on this machine")
    run.add_argument("file", help="Flow JSON file")
    run.add_argument("--input", action="append", metavar="KEY=VALUE", help="Run input; repeat for several")
    run.add_argument("--input-json", metavar="JSON", help="Run input as a JSON object")
    run.add_argument(
        "--toolsets", default="safe",
        help="Toolsets the vael/agent nodes may use (default: safe = web, vision, image generation; "
             "no terminal). Widen it only for flows you trust.")
    run.add_argument("--timeout", type=float, default=300.0, help="Whole-run time limit in seconds (default 300)")
    run.add_argument("--json", action="store_true", help="Print every step as JSON instead of the last output")

    flow_parser.set_defaults(func=cmd_flow)
