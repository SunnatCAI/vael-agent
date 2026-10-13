"""Run a flow document on this machine.

``flow_engine`` validates and resolves; this module walks the graph and executes the nodes. One path at
a time from ``start``: a condition picks its ``true``/``false`` branch, a loop runs its body inline for
each item and then continues from ``exit``. A node that fails stops the run with the reason - nothing is
swallowed into an empty result.

The ``vael`` and ``agent`` nodes run the local VAEL Agent, so they use the user's own keys. Without an
explicit toolset they get ``safe`` (no terminal): a headless run has nobody to ask, so dangerous commands
are denied (or approved, if ``approvals.single_query_mode`` says so), and a flow gets terminal or file
access only when the person running it asks for it.
Nodes that need CyberAI itself (``telegram``, ``pc``) cannot run here and fail with that reason.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from vael_cli import flow_engine as fe

DEFAULT_TOOLSETS = "safe"
MAX_STEPS = 100
MAX_LOOP_ITERATIONS = 20
MAX_DELAY_S = 30.0
MAX_OUTPUT_CHARS = 32 * 1024
HTTP_TIMEOUT_S = 15
HTTP_MAX_BYTES = 64 * 1024
_FORBIDDEN_HEADERS = frozenset(
    {"authorization", "proxy-authorization", "cookie", "set-cookie", "host", "x-forwarded-for"})

KNOWN_KINDS = (
    "start", "action", "transform", "delay", "condition", "loop", "vael", "agent", "http", "telegram", "pc")

AgentRunner = Callable[[str, str, str, str], str]  # prompt, model, provider, toolsets -> reply


class StepFailure(Exception):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass
class StepRecord:
    node_id: str
    kind: str
    ok: bool
    output: Any = None
    reason: str = ""
    message: str = ""
    ms: int = 0
    loop_index: Optional[int] = None

    def as_dict(self) -> dict:
        data = {"node": self.node_id, "type": self.kind, "ok": self.ok, "ms": self.ms}
        if self.loop_index is not None:
            data["loopIndex"] = self.loop_index
        if self.ok:
            data["output"] = self.output
        else:
            data["error"] = {"reason": self.reason, "message": self.message}
        return data


@dataclass
class RunResult:
    ok: bool
    run_id: str
    steps: List[StepRecord] = field(default_factory=list)
    error: str = ""

    @property
    def last_output(self) -> Any:
        for step in reversed(self.steps):
            if step.ok:
                return step.output
        return None

    def as_dict(self) -> dict:
        return {"ok": self.ok, "runId": self.run_id, "error": self.error,
                "steps": [s.as_dict() for s in self.steps]}


def default_agent_runner(prompt: str, model: str, provider: str, toolsets: str) -> str:
    """Run one headless turn of the local VAEL Agent; the prompt goes in on stdin, never on the command line."""
    args = [sys.executable, "-X", "utf8", "-c", "from vael_cli.main import main; main()",
            "chat", "--query-file", "-", "--oneshot", "--quiet", "--source", "tool", "-t", toolsets]
    if model:
        args += ["-m", model]
    if provider:
        args += ["--provider", provider]
    try:
        done = subprocess.run(
            args, input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=600,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
    except subprocess.TimeoutExpired:
        raise StepFailure("timeout", "The VAEL Agent did not finish within 10 minutes.") from None
    reply = (done.stdout or "").strip()
    if done.returncode != 0 or not reply:
        tail = (done.stderr or "").strip()[-400:]
        raise StepFailure("upstream_error", f"VAEL Agent exited with code {done.returncode}. {tail}".strip())
    return reply


class Runner:
    def __init__(self, doc: dict, *, flow_input: Optional[Dict[str, Any]] = None,
                 agent_runner: AgentRunner = default_agent_runner, toolsets: str = DEFAULT_TOOLSETS,
                 timeout_s: float = 300.0, sleep: Callable[[float], None] = time.sleep,
                 fetch: Optional[Callable[..., Any]] = None,
                 on_step: Optional[Callable[[StepRecord], None]] = None):
        self.doc = doc
        self.nodes = {n["id"]: n for n in doc["nodes"]}
        self.edges = doc["edges"]
        self.agent_runner = agent_runner
        self.toolsets = toolsets
        self.sleep = sleep
        self.fetch = fetch or _fetch
        self.on_step = on_step
        self.deadline = time.monotonic() + max(1.0, timeout_s)
        self.run_id = f"run_{uuid.uuid4().hex[:12]}"
        self.result = RunResult(ok=False, run_id=self.run_id)
        self.scope = fe.Scope(
            input=dict(flow_input or {}),
            run={"id": self.run_id, "flowId": str(doc.get("id", "")), "flowName": doc["name"],
                 "startedAt": int(time.time())},
            env={"ENVIRONMENT": "local", "FLOW_ID": str(doc.get("id", "")), "FLOW_NAME": doc["name"],
                 "FLOW_RUN_ID": self.run_id},
        )

    # -- walking ------------------------------------------------------------------------------------

    def run(self) -> RunResult:
        start_id = fe.validate_document(self.doc, KNOWN_KINDS)
        try:
            current: Optional[str] = start_id
            while current is not None:
                outcome = self._run_node(current)
                node = self.nodes[current]
                if node["type"] == "loop":
                    exits = fe.outgoing(self.edges, current, "exit")
                    self._run_loop_body(node, outcome["items"])
                    current = exits[0] if exits else None
                elif node["type"] == "condition":
                    targets = fe.outgoing(self.edges, current, "true" if outcome["result"] else "false")
                    current = targets[0] if targets else None
                else:
                    targets = fe.outgoing(self.edges, current, "out")
                    current = targets[0] if targets else None
            self.result.ok = True
        except StepFailure as err:
            self.result.error = f"{err.reason}: {err.message}"
        return self.result

    def _run_loop_body(self, loop_node: dict, items: List[Any]) -> None:
        if self.scope.loop is not None:
            raise StepFailure("config_invalid", "Nested loops are not supported.")
        body = fe.loop_body(loop_node["id"], list(self.nodes.values()), self.edges)
        if not body:
            return
        try:
            order = fe.topological_order([self.nodes[i] for i in body], self.edges)
        except fe.FlowError:
            order = body
        try:
            for index, item in enumerate(items):
                self.scope.loop = {"index": index, "index0": index + 1, "item": item, "length": len(items)}
                self.scope.env["LOOP_INDEX"] = str(index + 1)
                self.scope.env["LOOP_ITEM"] = fe._stringify(item)[:2000]
                for node_id in order:
                    self._run_node(node_id, loop_index=index + 1)
        finally:
            self.scope.loop = None
            self.scope.env.pop("LOOP_INDEX", None)
            self.scope.env.pop("LOOP_ITEM", None)

    # -- one node -----------------------------------------------------------------------------------

    def _run_node(self, node_id: str, loop_index: Optional[int] = None) -> Any:
        node = self.nodes[node_id]
        kind = node["type"]
        if len(self.result.steps) >= MAX_STEPS:
            raise StepFailure("max_steps", f"Step limit ({MAX_STEPS}) reached - run stopped.")
        if time.monotonic() > self.deadline:
            raise StepFailure("run_timeout", "The run's time limit was reached.")
        started = time.monotonic()
        record = StepRecord(node_id=node_id, kind=kind, ok=False, loop_index=loop_index)
        if node.get("disabled") is True:
            record.ok, record.output = True, {"skipped": True}
            self.scope.steps[node_id] = {"ok": True, "output": record.output}
            self._finish(record, started)
            return {"result": True, "items": []} if kind in ("condition", "loop") else record.output
        try:
            handler = getattr(self, f"_do_{kind}", None)
            if handler is None:
                raise StepFailure("not_supported_locally", f'"{kind}" nodes need CyberAI itself - run this flow there.')
            config = self._config(kind, node.get("data") or {})
            output = handler(config)
        except fe.ResolveError as err:
            record.reason, record.message = "template_unresolved", str(err)
            self._fail(record, started)
        except fe.ExpressionError as err:
            record.reason = "template_unresolved" if err.code == "resolve" else "expression_invalid"
            record.message = str(err)
            self._fail(record, started)
        except StepFailure as err:
            record.reason, record.message = err.reason, err.message
            self._fail(record, started)
        except Exception as err:  # an executor must never end the run without a reason
            record.reason, record.message = "internal", f"{type(err).__name__}: {err}"[:300]
            self._fail(record, started)
        record.ok, record.output = True, output
        self.scope.steps[node_id] = {"ok": True, "output": _clip(output)}
        self._finish(record, started)
        return output

    def _fail(self, record: StepRecord, started: float) -> None:
        self.scope.steps[record.node_id] = {"ok": False, "output": None}
        self._finish(record, started)
        raise StepFailure(record.reason, f"{record.node_id} ({record.kind}): {record.message}")

    def _finish(self, record: StepRecord, started: float) -> None:
        record.ms = int((time.monotonic() - started) * 1000)
        self.result.steps.append(record)
        if self.on_step:
            self.on_step(record)

    _TEMPLATE_FIELDS = {
        "action": ("message",), "transform": ("mapping",), "loop": ("items",), "vael": ("prompt",),
        "agent": ("task",), "http": ("url", "body", "headers"),
    }

    def _config(self, kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
        config = dict(data)
        for key in self._TEMPLATE_FIELDS.get(kind, ()):
            if isinstance(config.get(key), str):
                config[key] = fe.resolve_template(config[key], self.scope)
        return config

    # -- executors ----------------------------------------------------------------------------------

    def _do_start(self, config: dict) -> Any:
        keys = [k for k in str(config.get("inputKeys", "")).replace(",", " ").split() if k]
        if not keys:
            return {"input": self.scope.input, "declaredKeys": []}
        missing = [k for k in keys if k not in self.scope.input]
        if missing:
            raise StepFailure("empty_input", f"Start needs these input keys: {', '.join(missing)}.")
        return {"input": {k: self.scope.input[k] for k in keys}, "declaredKeys": keys}

    def _do_action(self, config: dict) -> Any:
        action = str(config.get("action", "") or "noop").strip()
        if action == "noop":
            return {"action": "noop", "input": self.scope.input}
        if action == "log":
            return {"action": "log", "message": str(config.get("message", "log"))[:2000]}
        if action == "set":
            written: Dict[str, str] = {}
            for part in (p.strip() for p in str(config.get("message", "")).split(";")):
                if not part:
                    continue
                key, eq, value = part.partition("=")
                key = key.strip()
                if not fe._NODE_ID_RE.match(key) or key in fe._FORBIDDEN_SEGMENTS:
                    raise StepFailure("config_invalid", f'action set: bad key "{key[:40]}".')
                written[key] = (value.strip() if eq else "true")[:2000]
            if not written:
                raise StepFailure("config_invalid", "action set needs at least one key=value.")
            self.scope.input.update(written)
            return {"action": "set", "written": written}
        raise StepFailure("config_invalid", f'action "{action[:40]}" is not allowed (noop, log, set).')

    def _do_transform(self, config: dict) -> Any:
        mapping = config.get("mapping")
        if mapping is None:
            raise StepFailure("config_invalid", "transform: mapping is empty.")
        if isinstance(mapping, str):
            return {"text": mapping[:MAX_OUTPUT_CHARS]}
        return {"value": _clip(mapping)}

    def _do_delay(self, config: dict) -> Any:
        wanted = min(max(float(config.get("durationMs", 1000) or 0) / 1000.0, 0.0), MAX_DELAY_S)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise StepFailure("run_timeout", "The run's time limit was reached (delay).")
        wait = min(wanted, remaining)
        self.sleep(wait)
        return {"waitedMs": int(wait * 1000), "requestedMs": int(wanted * 1000)}

    def _do_condition(self, config: dict) -> Any:
        expression = str(config.get("expression", ""))
        return {"expression": expression, "result": fe.evaluate_expression(expression, self.scope)}

    def _do_loop(self, config: dict) -> Any:
        items = config.get("items")
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except ValueError:
                items = None
        if not isinstance(items, list):
            raise StepFailure("config_invalid", "loop: items must be a list (JSON array or a {{...}} reference).")
        if not items:
            raise StepFailure("empty_input", "loop: items is empty - nothing to repeat.")
        limit = min(max(int(config.get("maxIterations", 10) or 10), 1), MAX_LOOP_ITERATIONS)
        if len(items) > limit:
            raise StepFailure(
                "max_iterations", f"loop: {len(items)} items but the limit is {limit} (raise maxIterations, max {MAX_LOOP_ITERATIONS}).")
        return {"total": len(items), "iterations": len(items), "maxIterations": limit, "items": items}

    def _do_vael(self, config: dict) -> Any:
        prompt = str(config.get("prompt", ""))
        if not prompt.strip():
            raise StepFailure("config_invalid", "vael: prompt is empty.")
        text = self.agent_runner(prompt, str(config.get("model", "")), str(config.get("provider", "")), self.toolsets)
        return {"text": text[:MAX_OUTPUT_CHARS], "chars": len(text)}

    def _do_agent(self, config: dict) -> Any:
        task = str(config.get("task", ""))
        if not task.strip():
            raise StepFailure("config_invalid", "agent: task is empty.")
        text = self.agent_runner(task, "", "", self.toolsets)
        return {"output": text[:MAX_OUTPUT_CHARS]}

    def _do_http(self, config: dict) -> Any:
        from tools.url_safety import is_safe_url

        url = str(config.get("url", "")).strip()
        if not url:
            raise StepFailure("config_invalid", "http: url is empty.")
        if not is_safe_url(url):
            raise StepFailure("blocked", "http: the URL is blocked (localhost, private network or metadata address).")
        method = str(config.get("method", "POST")).upper()
        headers: Dict[str, str] = {}
        raw_headers = config.get("headers")
        if isinstance(raw_headers, str) and raw_headers.strip():
            try:
                parsed = json.loads(raw_headers)
            except ValueError:
                raise StepFailure("config_invalid", "http: headers must be a JSON object.") from None
            if not isinstance(parsed, dict):
                raise StepFailure("config_invalid", "http: headers must be a JSON object.")
            for key, value in parsed.items():
                if str(key).lower() in _FORBIDDEN_HEADERS:
                    raise StepFailure("blocked", f"http: header {key} is not allowed in a flow.")
                headers[str(key)] = str(value)
        body = config.get("body")
        data = None if method in ("GET", "DELETE") or not body else str(body).encode("utf-8")
        status, payload = self.fetch(url, method, headers, data)
        text = payload[:HTTP_MAX_BYTES].decode("utf-8", "replace")
        if status >= 400:
            raise StepFailure("upstream_error", f"http: {method} {url} answered {status}.")
        try:
            return {"status": status, "json": json.loads(text)}
        except ValueError:
            return {"status": status, "text": text[:4000]}

    def _do_telegram(self, config: dict) -> Any:
        raise StepFailure("not_supported_locally", "telegram nodes send through the CyberAI bot - run this flow in CyberAI.")

    def _do_pc(self, config: dict) -> Any:
        raise StepFailure("not_supported_locally", "pc nodes dispatch to a linked device through CyberAI - run this flow there.")


def _clip(value: Any) -> Any:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return {"note": "value is not JSON-serialisable"}
    if len(text) <= MAX_OUTPUT_CHARS:
        return value
    return {"truncated": True, "size": len(text), "preview": text[:2000]}


def _fetch(url: str, method: str, headers: Dict[str, str], data: Optional[bytes]) -> tuple:
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:  # noqa: S310 - guarded by is_safe_url
            return response.status, response.read(HTTP_MAX_BYTES + 1)
    except urllib.error.HTTPError as err:
        return err.code, err.read(HTTP_MAX_BYTES + 1)
    except (urllib.error.URLError, TimeoutError) as err:
        raise StepFailure("upstream_error", f"http: {err}") from None


def run_flow(doc: dict, **kwargs: Any) -> RunResult:
    return Runner(doc, **kwargs).run()
