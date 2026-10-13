"""``vael flow``: CyberAI flow documents run on this machine.

The document format, template rules and condition rules are shared with CyberAI's engine, so these tests
pin the behaviour a flow drawn there depends on: typed references, errors for missing paths, branching,
loops, and that nothing reaches the network or the terminal unasked.
"""

from __future__ import annotations

import argparse
import json

import pytest

from vael_cli import flow as flow_cli
from vael_cli import flow_engine as fe
from vael_cli import flow_runner as fr


def node(node_id, kind, **data):
    return {"id": node_id, "type": kind, "position": {"x": 0, "y": 0}, "data": data}


def edge(source, target, handle=None):
    return {"id": f"{source}-{target}-{handle or 'out'}", "source": source, "target": target,
            "sourceHandle": handle, "targetHandle": None}


def doc(nodes, edges, name="t"):
    return {"schemaVersion": 1, "name": name, "nodes": nodes, "edges": edges}


class FakeAgent:
    def __init__(self, reply="done"):
        self.reply = reply
        self.calls = []

    def __call__(self, prompt, model, provider, toolsets):
        self.calls.append({"prompt": prompt, "model": model, "provider": provider, "toolsets": toolsets})
        return self.reply


def scope(**kw):
    return fe.Scope(**kw)


# --- templates and conditions ------------------------------------------------------------------------


def test_a_template_that_is_one_reference_keeps_its_type():
    s = scope(steps={"a": {"ok": True, "output": {"items": [1, 2]}}})
    assert fe.resolve_template("{{ steps.a.output.items }}", s) == [1, 2]
    assert fe.resolve_template("n={{steps.a.output.items[1]}}", s) == "n=2"


@pytest.mark.parametrize("ref", ["input.missing", "steps.nope.output", "loop.item", "env.AES_MASTER_KEY",
                                 "input.__proto__", "input.constructor", "secrets.key", "input[x]"])
def test_a_reference_that_cannot_be_resolved_is_an_error_not_an_empty_string(ref):
    with pytest.raises(fe.ResolveError):
        fe.resolve_template("{{" + ref + "}}", scope())


def test_env_exposes_only_the_allowlisted_run_facts():
    s = scope(env={"FLOW_NAME": "demo"})
    assert fe.resolve_template("{{env.FLOW_NAME}}", s) == "demo"


@pytest.mark.parametrize("expression,expected", [
    ("{{input.n}} > 2", True), ("{{input.n}} <= 2", False), ("{{input.s}} contains 'ell'", True),
    ("{{input.s}} == 'hello' and not {{input.n}} < 1", True), ("{{input.n}} == 5 or false", True),
    ("({{input.n}} > 9 || {{input.n}} == 5) && true", True), ("{{input.empty}}", False),
])
def test_conditions(expression, expected):
    s = scope(input={"n": 5, "s": "hello", "empty": ""})
    assert fe.evaluate_expression(expression, s) is expected


@pytest.mark.parametrize("expression", ["", "{{input.n}} >", "(true", "{{input.nope}} == 1", "'unclosed"])
def test_a_broken_condition_is_an_error_not_false(expression):
    with pytest.raises(fe.ExpressionError):
        fe.evaluate_expression(expression, scope(input={"n": 1}))


# --- the graph ---------------------------------------------------------------------------------------


def test_validation_names_every_problem():
    bad = doc([node("a", "action"), node("b", "bogus")], [edge("a", "ghost")])
    with pytest.raises(fe.FlowError) as err:
        fe.validate_document(bad, fr.KNOWN_KINDS)
    text = " ".join(err.value.issues)
    assert "Unknown node type" in text and "start node" in text and "does not exist" in text


def test_a_cycle_outside_a_loop_is_refused():
    cyclic = doc([node("s", "start"), node("a", "action"), node("b", "action")],
                 [edge("s", "a"), edge("a", "b"), edge("b", "a")])
    with pytest.raises(fe.FlowError) as err:
        fe.validate_document(cyclic, fr.KNOWN_KINDS)
    assert "Cycle" in str(err.value)


def test_a_node_nothing_leads_to_is_refused():
    lonely = doc([node("s", "start"), node("x", "action")], [])
    with pytest.raises(fe.FlowError) as err:
        fe.validate_document(lonely, fr.KNOWN_KINDS)
    assert "cannot be reached" in str(err.value)


# --- running -----------------------------------------------------------------------------------------


def run(document, agent=None, **kw):
    return fr.run_flow(document, agent_runner=agent or FakeAgent(), sleep=lambda s: None, **kw)


def test_input_flows_through_a_transform_into_the_agent():
    agent = FakeAgent("short answer")
    document = doc(
        [node("s", "start", inputKeys="topic"),
         node("t", "transform", mapping="Explain {{input.topic}} briefly"),
         node("v", "vael", prompt="{{steps.t.output.text}}")],
        [edge("s", "t"), edge("t", "v")])
    result = run(document, agent, flow_input={"topic": "DNS"})
    assert result.ok
    assert agent.calls[0]["prompt"] == "Explain DNS briefly"
    assert result.last_output["text"] == "short answer"


def test_the_agent_gets_no_terminal_unless_the_person_asks_for_it():
    agent = FakeAgent()
    document = doc([node("s", "start"), node("a", "agent", task="do it")], [edge("s", "a")])
    run(document, agent)
    assert agent.calls[0]["toolsets"] == "safe"
    run(document, agent, toolsets="web,file")
    assert agent.calls[1]["toolsets"] == "web,file"


def test_a_condition_follows_only_the_branch_it_chose():
    agent = FakeAgent("yes-branch")
    document = doc(
        [node("s", "start"), node("c", "condition", expression="{{input.go}} == 'yes'"),
         node("t", "vael", prompt="true branch"), node("f", "vael", prompt="false branch")],
        [edge("s", "c"), edge("c", "t", "true"), edge("c", "f", "false")])
    run(document, agent, flow_input={"go": "yes"})
    run(document, agent, flow_input={"go": "no"})
    assert [c["prompt"] for c in agent.calls] == ["true branch", "false branch"]


def test_a_loop_runs_its_body_for_each_item_then_continues_from_exit():
    agent = FakeAgent("ok")
    document = doc(
        [node("s", "start"), node("l", "loop", items='["a","b","c"]'),
         node("body", "vael", prompt="item {{loop.item}} #{{loop.index0}}"),
         node("after", "vael", prompt="finished")],
        [edge("s", "l"), edge("l", "body", "loop"), edge("body", "l"), edge("l", "after", "exit")])
    result = run(document, agent)
    assert result.ok, result.error
    assert [c["prompt"] for c in agent.calls] == ["item a #1", "item b #2", "item c #3", "finished"]


def test_a_failing_node_stops_the_run_and_says_why():
    agent = FakeAgent()
    document = doc(
        [node("s", "start"), node("t", "transform", mapping="{{input.missing}}"), node("v", "vael", prompt="x")],
        [edge("s", "t"), edge("t", "v")])
    result = run(document, agent)
    assert not result.ok and "template_unresolved" in result.error and "t (transform)" in result.error
    assert agent.calls == []
    assert [s.ok for s in result.steps] == [True, False]


def test_nodes_that_need_cyberai_fail_with_that_reason():
    document = doc([node("s", "start"), node("p", "pc", flowName="x", timeoutMs=1000)], [edge("s", "p")])
    result = run(document)
    assert not result.ok and "not_supported_locally" in result.error


def test_http_to_a_private_address_is_blocked_before_any_request():
    called = []
    document = doc([node("s", "start"), node("h", "http", url="http://127.0.0.1:8080/admin", method="GET")],
                   [edge("s", "h")])
    result = run(document, fetch=lambda *a: called.append(a))
    assert not result.ok and "blocked" in result.error and called == []


def test_http_refuses_credential_headers_and_parses_json():
    document = doc([node("s", "start"),
                    node("h", "http", url="https://example.com/x", method="GET", headers='{"Authorization": "Bearer k"}')],
                   [edge("s", "h")])
    assert "not allowed" in run(document, fetch=lambda *a: (200, b"{}")).error
    ok_doc = doc([node("s", "start"), node("h", "http", url="https://example.com/x", method="GET")], [edge("s", "h")])
    result = run(ok_doc, fetch=lambda *a: (200, b'{"a": 1}'))
    assert result.ok and result.last_output == {"status": 200, "json": {"a": 1}}


def test_the_step_limit_stops_a_runaway_run():
    nodes = [node("s", "start")] + [node(f"n{i}", "action", action="noop") for i in range(fr.MAX_STEPS + 5)]
    ids = ["s"] + [n["id"] for n in nodes[1:]]
    result = run(doc(nodes, [edge(a, b) for a, b in zip(ids, ids[1:])]))
    assert not result.ok and "max_steps" in result.error


def test_a_disabled_node_is_skipped():
    agent = FakeAgent()
    off = node("v", "vael", prompt="never")
    off["disabled"] = True
    result = run(doc([node("s", "start"), off], [edge("s", "v")]), agent)
    assert result.ok and agent.calls == []


# --- the command -------------------------------------------------------------------------------------


def args(**kw):
    base = dict(flow_command="run", file="", input=None, input_json=None, toolsets="safe", timeout=30.0,
                json=False, name=None, force=False)
    base.update(kw)
    return argparse.Namespace(**base)


def test_new_then_validate_round_trips(tmp_path, capsys):
    target = tmp_path / "f.json"
    assert flow_cli.flow_command(args(flow_command="new", file=str(target), name="Digest")) == 0
    assert json.loads(target.read_text(encoding="utf-8"))["name"] == "Digest"
    assert flow_cli.flow_command(args(flow_command="validate", file=str(target))) == 0
    assert "OK: Digest" in capsys.readouterr().out


def test_new_does_not_overwrite_without_force(tmp_path):
    target = tmp_path / "f.json"
    target.write_text("keep", encoding="utf-8")
    assert flow_cli.flow_command(args(flow_command="new", file=str(target))) == 1
    assert target.read_text(encoding="utf-8") == "keep"


def test_validate_exits_non_zero_and_lists_problems(tmp_path, capsys):
    target = tmp_path / "bad.json"
    target.write_text(json.dumps(doc([node("a", "action")], [])), encoding="utf-8")
    assert flow_cli.flow_command(args(flow_command="validate", file=str(target))) == 1
    assert "start node" in capsys.readouterr().out


def test_input_pairs_must_be_key_value():
    with pytest.raises(SystemExit):
        flow_cli._parse_inputs(["novalue"], None)
    assert flow_cli._parse_inputs(["a=1", "b=x=y"], '{"c": 2}') == {"c": 2, "a": "1", "b": "x=y"}


def test_the_flow_command_is_registered_on_the_cli():
    from vael_cli.main import _BUILTIN_SUBCOMMANDS

    assert "flow" in _BUILTIN_SUBCOMMANDS
