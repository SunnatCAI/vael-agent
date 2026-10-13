"""Flow documents: templates, conditions and graph rules.

A flow is the document the CyberAI flow editor saves (``schemaVersion`` 1: ``nodes`` + ``edges``), so
a flow drawn there runs here and the other way round. Everything in this module is pure: no I/O, no
``eval``. ``flow_runner`` executes what this module validates and resolves.

Template and condition semantics match CyberAI's engine (``src/lib/flow/engine/``): a path that does
not exist is an error, never a silent empty string, and prototype-chain segments are refused.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set

SCHEMA_VERSION = 1
MAX_NODES = 200
MAX_EDGES = 400

ALLOWED_ROOTS = ("input", "steps", "run", "loop", "env")
ENV_ALLOWLIST = ("ENVIRONMENT", "FLOW_ID", "FLOW_NAME", "FLOW_RUN_ID", "LOOP_INDEX", "LOOP_ITEM")
_FORBIDDEN_SEGMENTS = frozenset({"__proto__", "constructor", "prototype"})
_MAX_PATH_SEGMENTS = 24
_MAX_PATH_DEPTH = 12
_MAX_TEMPLATE_CHARS = 8192
_MAX_RENDERED_CHARS = 32768
_NODE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_REF_RE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
_ONLY_REF_RE = re.compile(r"^\{\{\s*([^{}]+?)\s*\}\}$")


class ResolveError(Exception):
    """A template reference could not be resolved (unknown root, missing path, forbidden segment)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ExpressionError(Exception):
    """A condition could not be evaluated. ``code`` is ``syntax``, ``type`` or ``resolve``."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Scope:
    """What templates may read: the run input, finished steps, run facts and the loop context."""

    input: Dict[str, Any] = field(default_factory=dict)
    steps: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    run: Dict[str, Any] = field(default_factory=dict)
    loop: Optional[Dict[str, Any]] = None
    env: Dict[str, str] = field(default_factory=dict)


# --- templates -------------------------------------------------------------------------------------


def _segments(ref: str) -> List[str]:
    raw = ref.strip()
    if not raw:
        raise ResolveError("bad_syntax", "Empty template reference: {{}}.")
    parts: List[str] = []
    buffer = ""
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == ".":
            if buffer:
                parts.append(buffer)
                buffer = ""
            i += 1
            continue
        if ch == "[":
            if buffer:
                parts.append(buffer)
                buffer = ""
            close = raw.find("]", i)
            if close == -1:
                raise ResolveError("bad_syntax", f"Unclosed [ in {{{{{ref}}}}}.")
            index = raw[i + 1:close].strip()
            if not re.fullmatch(r"\d{1,6}", index):
                raise ResolveError("bad_syntax", f"Only numeric indexes are allowed: {{{{{ref}}}}}.")
            parts.append(index)
            i = close + 1
            if i < len(raw) and raw[i] == ".":
                i += 1
            continue
        buffer += ch
        i += 1
    if buffer:
        parts.append(buffer)
    if not parts:
        raise ResolveError("bad_syntax", f"Bad template path: {{{{{ref}}}}}.")
    if len(parts) > _MAX_PATH_SEGMENTS:
        raise ResolveError("too_deep", f"Path too long: {{{{{ref}}}}}.")
    for segment in parts:
        if segment in _FORBIDDEN_SEGMENTS:
            raise ResolveError("forbidden_segment", f"Refused segment {segment}: {{{{{ref}}}}}.")
    return parts


def _read(holder: Any, key: str) -> Any:
    if isinstance(holder, list):
        if key.isdigit() and int(key) < len(holder):
            return holder[int(key)]
    elif isinstance(holder, dict):
        if key in holder:
            return holder[key]
    raise KeyError(key)


def resolve_ref(ref: str, scope: Scope) -> Any:
    parts = _segments(ref)
    if len(parts) > _MAX_PATH_DEPTH:
        raise ResolveError("too_deep", f"Path depth limit: {{{{{ref}}}}}.")
    root = parts[0]
    if root not in ALLOWED_ROOTS:
        raise ResolveError(
            "unknown_root", f'Unknown template root "{root}" (allowed: {", ".join(ALLOWED_ROOTS)}): {{{{{ref}}}}}.')
    if root == "env":
        name = parts[1] if len(parts) > 1 else ""
        if name not in ENV_ALLOWLIST:
            raise ResolveError(
                "forbidden_segment", f"env.{name} is not allowed ({', '.join(ENV_ALLOWLIST)}): {{{{{ref}}}}}.")
        if name not in scope.env:
            raise ResolveError("missing_path", f"env.{name} is not set in this run.")
        return scope.env[name]
    if root == "loop":
        if scope.loop is None:
            raise ResolveError("missing_path", f"No loop context: {{{{{ref}}}}}.")
        current: Any = scope.loop
    else:
        current = getattr(scope, root)
    for segment in parts[1:]:
        try:
            current = _read(current, segment)
        except KeyError:
            raise ResolveError("missing_path", f"Not found: {{{{{ref}}}}}.") from None
    return current


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    return json.dumps(value, ensure_ascii=False)


def resolve_template(template: str, scope: Scope) -> Any:
    """A template that is one reference keeps the value's type; otherwise the references are spliced in."""
    if len(template) > _MAX_TEMPLATE_CHARS:
        raise ResolveError("too_large", f"Template is longer than {_MAX_TEMPLATE_CHARS} characters.")
    only = _ONLY_REF_RE.match(template.strip())
    if only:
        return resolve_ref(only.group(1), scope)
    out = _REF_RE.sub(lambda m: _stringify(resolve_ref(m.group(1), scope)), template)
    if len(out) > _MAX_RENDERED_CHARS:
        raise ResolveError("too_large", f"Result is longer than {_MAX_RENDERED_CHARS} characters.")
    return out


def list_refs(template: str) -> List[str]:
    return [m.group(1).strip() for m in _REF_RE.finditer(template)]


# --- conditions ------------------------------------------------------------------------------------

_OPERATORS = ("==", "!=", ">=", "<=", "contains", "&&", "||", ">", "<", "!", "(", ")")
_COMPARATORS = ("==", "!=", ">", "<", ">=", "<=", "contains")
_MAX_EXPRESSION_CHARS = 2000
_MAX_TOKENS = 256


def _tokenize(expression: str) -> List[tuple]:
    src = expression.strip()
    if len(src) > _MAX_EXPRESSION_CHARS:
        raise ExpressionError("syntax", "Expression is longer than 2000 characters.")
    tokens: List[tuple] = []
    i = 0
    while i < len(src):
        ch = src[i]
        if ch.isspace():
            i += 1
            continue
        if src.startswith("{{", i):
            end = src.find("}}", i + 2)
            if end == -1:
                raise ExpressionError("syntax", "Unclosed {{ ... }}.")
            tokens.append(("ref", src[i + 2:end]))
            i = end + 2
        elif ch in ("'", '"'):
            j, out = i + 1, ""
            while j < len(src) and src[j] != ch:
                if src[j] == "\\" and j + 1 < len(src):
                    out += src[j + 1]
                    j += 2
                    continue
                out += src[j]
                j += 1
            if j >= len(src):
                raise ExpressionError("syntax", "Unclosed quote.")
            tokens.append(("text", out))
            i = j + 1
        else:
            op = next((c for c in _OPERATORS if src.startswith(c, i)), None)
            if op:
                tokens.append(("lparen" if op == "(" else "rparen" if op == ")" else "op", op))
                i += len(op)
                continue
            j = i
            while j < len(src) and not re.match(r"[\s'\")(><=!]", src[j]) and src[j] != "{":
                j += 1
            if j == i:
                raise ExpressionError("syntax", f'Unexpected character: "{src[i]}".')
            word = src[i:j]
            tokens.append(("op", word) if word in ("and", "or", "not") else ("text", word))
            i = j
        if len(tokens) > _MAX_TOKENS:
            raise ExpressionError("syntax", "Expression has too many tokens.")
    return tokens


def _truthy(value: Any) -> bool:
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)


def _to_number(value: Any) -> float:
    try:
        return float(value) if not isinstance(value, str) else float(value.strip())
    except (TypeError, ValueError):
        raise ExpressionError("type", f"Cannot turn into a number: {str(value)[:60]}.") from None


def _equal(left: Any, right: Any) -> bool:
    if isinstance(left, (list, dict)) or isinstance(right, (list, dict)):
        return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)
    return _stringify(left) == _stringify(right)


def _compare(op: str, left: Any, right: Any) -> bool:
    if op == "==":
        return _equal(left, right)
    if op == "!=":
        return not _equal(left, right)
    if op == "contains":
        if isinstance(left, list):
            return any(_equal(item, right) for item in left)
        if isinstance(left, dict):
            return str(right) in left
        return _stringify(right) in _stringify(left)
    a, b = _to_number(left), _to_number(right)
    return {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]


def _literal(word: str) -> Any:
    lowered = word.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    if re.fullmatch(r"-?\d+(\.\d+)?", lowered):
        return float(lowered) if "." in lowered else int(lowered)
    return word


class _Parser:
    def __init__(self, tokens: Sequence[tuple], scope: Scope):
        self.tokens = tokens
        self.scope = scope
        self.i = 0

    def peek(self) -> Optional[tuple]:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def eat(self, *words: str) -> bool:
        tok = self.peek()
        if tok and tok[0] == "op" and tok[1] in words:
            self.i += 1
            return True
        return False

    def primary(self) -> Any:
        tok = self.peek()
        if not tok:
            raise ExpressionError("syntax", "Expression ended unexpectedly.")
        kind, value = tok
        if kind == "lparen":
            self.i += 1
            result = self.or_()
            close = self.peek()
            if not close or close[0] != "rparen":
                raise ExpressionError("syntax", "Parenthesis not closed.")
            self.i += 1
            return result
        if kind == "ref":
            self.i += 1
            try:
                return resolve_ref(value, self.scope)
            except ResolveError as err:
                raise ExpressionError("resolve", str(err)) from None
        if kind == "text":
            self.i += 1
            return _literal(value)
        if kind == "op" and value == "!":
            self.i += 1
            return not _truthy(self.primary())
        raise ExpressionError("syntax", f"Unexpected token: {kind}.")

    def comparison(self) -> Any:
        left = self.primary()
        tok = self.peek()
        if tok and tok[0] == "op" and tok[1] in _COMPARATORS:
            self.i += 1
            return _compare(tok[1], left, self.primary())
        return left

    def not_(self) -> Any:
        if self.eat("not", "!"):
            return not _truthy(self.not_())
        return self.comparison()

    def and_(self) -> Any:
        left = _truthy(self.not_())
        while self.eat("and", "&&"):
            right = _truthy(self.not_())
            left = left and right
        return left

    def or_(self) -> Any:
        left = _truthy(self.and_())
        while self.eat("or", "||"):
            right = _truthy(self.and_())
            left = left or right
        return left


def evaluate_expression(expression: str, scope: Scope) -> bool:
    tokens = _tokenize(expression)
    if not tokens:
        raise ExpressionError("syntax", "Expression is empty.")
    parser = _Parser(tokens, scope)
    value = parser.or_()
    if parser.i != len(tokens):
        raise ExpressionError("syntax", "Extra tokens at the end of the expression.")
    return _truthy(value)


# --- graph -----------------------------------------------------------------------------------------


class FlowError(Exception):
    """The flow document is not runnable. ``issues`` lists every problem found."""

    def __init__(self, message: str, issues: Optional[List[str]] = None):
        super().__init__(message)
        self.issues = issues or []


# Ports an edge may leave a node by; every other node has the single ``out`` port.
_SOURCE_PORTS = {"condition": ("true", "false"), "loop": ("loop", "exit")}


def port_of(edge: dict) -> str:
    return edge.get("sourceHandle") or "out"


def outgoing(edges: Sequence[dict], source: str, port: Optional[str] = None) -> List[str]:
    return [e["target"] for e in edges if e["source"] == source and (port is None or port_of(e) == port)]


def loop_body(loop_id: str, nodes: Sequence[dict], edges: Sequence[dict]) -> List[str]:
    """Nodes reached from a loop's ``loop`` port; the ``exit`` path is not part of the body."""
    by_id = {n["id"]: n for n in nodes}
    body: List[str] = []
    seen: Set[str] = {loop_id}
    queue = [e for e in edges if e["source"] == loop_id and port_of(e) == "loop"]
    while queue:
        edge = queue.pop(0)
        if edge["target"] in seen:
            continue
        seen.add(edge["target"])
        node = by_id.get(edge["target"])
        if node is None:
            continue
        body.append(edge["target"])
        if node["type"] == "loop":
            continue
        for nxt in edges:
            if nxt["source"] == edge["target"] and not (port_of(nxt) == "loop" and nxt["target"] != loop_id):
                queue.append(nxt)
    return body


def topological_order(nodes: Sequence[dict], edges: Sequence[dict]) -> List[str]:
    kinds = {n["id"]: n["type"] for n in nodes}
    effective = [e for e in edges if not (port_of(e) == "loop" and kinds.get(e["source"]) == "loop")]
    indegree = {n["id"]: 0 for n in nodes}
    for e in effective:
        if e["target"] in indegree:
            indegree[e["target"]] += 1
    queue = [n["id"] for n in nodes if indegree[n["id"]] == 0]
    order: List[str] = []
    while queue:
        current = queue.pop(0)
        order.append(current)
        for e in effective:
            if e["source"] == current and e["target"] in indegree:
                indegree[e["target"]] -= 1
                if indegree[e["target"]] == 0:
                    queue.append(e["target"])
    if len(order) != len(nodes):
        raise FlowError("Cycle found - no execution order exists.")
    return order


def validate_document(doc: Any, known_kinds: Sequence[str]) -> str:
    """Check a flow document and return the id of its start node, or raise ``FlowError`` listing every problem."""
    issues: List[str] = []
    if not isinstance(doc, dict):
        raise FlowError("A flow document must be a JSON object.", ["not an object"])
    if doc.get("schemaVersion") != SCHEMA_VERSION:
        issues.append(f"schemaVersion must be {SCHEMA_VERSION}.")
    if not isinstance(doc.get("name"), str) or not doc["name"].strip():
        issues.append("name is required.")
    nodes, edges = doc.get("nodes"), doc.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise FlowError("nodes and edges must be lists.", issues + ["nodes/edges are not lists"])
    if len(nodes) > MAX_NODES or len(edges) > MAX_EDGES:
        issues.append(f"Too large (max {MAX_NODES} nodes, {MAX_EDGES} edges).")
    ids: Set[str] = set()
    types_by_id: Dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict) or not _NODE_ID_RE.match(str(node.get("id", ""))):
            issues.append(f"Bad node id: {node.get('id') if isinstance(node, dict) else node!r}.")
            continue
        if node["id"] in ids:
            issues.append(f"Duplicate node id: {node['id']}.")
        ids.add(node["id"])
        types_by_id[node["id"]] = str(node.get("type"))
        if node.get("type") not in known_kinds:
            issues.append(f"Unknown node type {node.get('type')!r} ({node['id']}).")
    starts = [n for n in nodes if isinstance(n, dict) and n.get("type") == "start"]
    if not nodes:
        issues.append("The flow is empty - it needs a start node.")
    elif len(starts) != 1:
        issues.append(f"Exactly one start node is required (found {len(starts)}).")
    good_edges = []
    for edge in edges:
        if not isinstance(edge, dict) or edge.get("source") not in ids or edge.get("target") not in ids:
            issues.append(f"Edge points at a node that does not exist ({edge.get('id') if isinstance(edge, dict) else edge!r}).")
        elif edge["source"] == edge["target"]:
            issues.append(f"Node connects to itself: {edge['source']}.")
        else:
            allowed = _SOURCE_PORTS.get(types_by_id[edge["source"]], ("out",))
            if port_of(edge) not in allowed:
                issues.append(
                    f"Edge {edge.get('id', '?')} leaves {edge['source']} ({types_by_id[edge['source']]}) "
                    f"by port {port_of(edge)!r}; this node has {', '.join(allowed)}.")
            good_edges.append(edge)
    if starts and not issues:
        reached = {starts[0]["id"]}
        queue = [starts[0]["id"]]
        while queue:
            for target in outgoing(good_edges, queue.pop(0)):
                if target not in reached:
                    reached.add(target)
                    queue.append(target)
        for node in nodes:
            if node["id"] not in reached:
                issues.append(f'"{node["id"]}" cannot be reached from start.')
        loops = [n["id"] for n in nodes if n["type"] == "loop"]
        for loop_id in loops:
            if any(i in loops for i in loop_body(loop_id, nodes, good_edges)):
                issues.append(f'"{loop_id}" has another loop inside its body (nested loops are not supported).')
        if not issues:
            try:
                topological_order(nodes, good_edges)
            except FlowError as err:
                issues.append(str(err))
    if issues:
        raise FlowError(f"Flow is not runnable: {issues[0]}", issues)
    return starts[0]["id"]
