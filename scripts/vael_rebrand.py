#!/usr/bin/env python3
"""Mechanical ``hermes`` -> ``vael`` rename over the tracked tree.

    python scripts/vael_rebrand.py            # dry run: counts only
    python scripts/vael_rebrand.py --apply    # rewrite contents, move paths
    python scripts/vael_rebrand.py --report DIR   # also write plan.tsv / residual.tsv

Re-run it after restoring files or merging upstream: on an already-renamed tree
the dry run reports zero planned renames and zero changed files, so any other
number is new ``hermes`` text. What deliberately keeps the old name is listed
in REBRANDING.md and encoded in ``PROTECT`` / ``keep_*`` below.

Casing: ``hermes`` -> ``vael``, ``HERMES`` -> ``VAEL``; ``Hermes`` becomes
``Vael`` when it touches an identifier character (``HermesCLI``) and ``VAEL``
when it stands alone as a word.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

# Files whose content is never rewritten.
KEEP_CONTENT_PREFIX = ("contributors/", "plugins/hermes-achievements/", "docs/ir2-mapping/")
KEEP_CONTENT_EXACT = {
    "LICENSE",
    "NOTICE",
    "REBRANDING.md",
    "docs/verification-log.md",
    "scripts/ir2-rollback.sh",
    "scripts/vael_rebrand.py",
}
# Vendored code keeps its own wording, but it must import the host's modules by their new names.
VENDORED_CODE_PREFIX = ("plugins/hermes-achievements/",)
VENDORED_HOST_API = re.compile(r"\b(hermes_constants|hermes_state|hermes_cli|get_hermes_home)\b")
# Paths that are never moved.
KEEP_PATH_PREFIX = ("contributors/", "plugins/hermes-achievements/", "plugin-catalog/", "docs/ir2-mapping/")
KEEP_PATH_BASENAME = {"openclaw_to_hermes.py"}

_URL_TAIL = r"[^\s\"'<>)`\\\]]*"
URL = re.compile(r"https?://([^/\s\"'<>)`\\\]]+)" + _URL_TAIL, re.I)
# Hosts we own or invent in tests: a URL on one of these is renamed like any other text.
LOCAL_HOST = re.compile(
    r"^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|host|\{.*|\$.*|.*example.*|.*\.test|.*\.local|.*\.invalid"
    r"|your-.*|.*hermes\.(cloud|fly\.dev|ai|dev|app|io|internal|lan))$",
    re.I,
)

# Spans matched here keep their text. Each entry is an external contract.
PROTECT = [
    # upstream hosts, repos, images
    re.compile(r"(?<![\w.-])[\w.-]{0,80}nousresearch\.(com|github\.io)" + _URL_TAIL, re.I),
    re.compile(r"(git@github\.com:|github:|ghcr\.io/|docker\.io/)?nousresearch[/.]hermes[\w.:/-]*", re.I),
    re.compile(r"Docs-hermes--agent\.nousresearch\.com"),
    re.compile(r"hermes-agent\.nousresearch\.\.\."),
    # Nous model family names
    re.compile(r"(?<![A-Za-z0-9_])(nous[-_/ ])?hermes(-[2-5](?![0-9])|[2-5](?=[:.-]))[\w.:-]*", re.I),
    re.compile(r"(?<![A-Za-z0-9_])Hermes [2-5](?![0-9])[\w.:-]*"),
    re.compile(r"nous[-_ ]hermes", re.I),
    re.compile(r"tool[-_]call[-_]parser[ =]+hermes", re.I),
    # code that recognises that model family by name
    re.compile(r"\"hermes\", \"llama\", \"mistral\""),
    re.compile(r"\"hermes\" (not )?in model_\w+"),
    re.compile(r"'gpt-5', 'hermes'\)"),
    # the bundled wake-word model still listens for this spoken phrase
    re.compile(r"hey hermes", re.I),
    # values derived from an upstream URL that stays untouched
    re.compile(r"\"NousResearch\" / \"hermes-agent\.git\""),
    re.compile(r"repositoryInfo\.project, 'hermes-agent'|repo: 'hermes-agent', provider: 'github'"),
    # third-party packages
    re.compile(r"hermes-(parser|estree|eslint)"),
    # KEEP-list identifiers referenced from code and docs
    re.compile(r"openclaw[_-]to[_-]hermes", re.I),
    re.compile(r"hermes-achievements|hermes_achievements", re.I),
    re.compile(r"requires_hermes"),
    # OAuth client IDs registered with third-party servers (Nous Portal, Honcho)
    re.compile(r"client[_-]?id[^\n]{0,80}?[\"'`=]hermes-(cli-vps|cli|agent)\b", re.I),
    re.compile(r"OAuth client \(default `hermes-agent`\)"),
]
# Third-party projects: a markdown link whose real, non-Nous URL keeps the name keeps its label too.
MD_LINK = re.compile(r"\[[^\]\n]*hermes[^\]\n]*\]\(https?://([^/\s)]+)[^)\s]*hermes[^)\s]*\)", re.I)

# Extra spans protected in one file only (keyed by its post-rename path).
FILE_PROTECT = {
    "optional-skills/security/godmode/scripts/auto_jailbreak.py": [
        re.compile(r"# Nous/Hermes models|^    \"hermes\": \{$|^        return \"hermes\"$", re.M),
    ],
}

HERMES = re.compile(r"hermes", re.I)
IDENT = re.compile(r"[A-Za-z0-9_]")


def keep_content(path: str) -> bool:
    if path in KEEP_CONTENT_EXACT or path.startswith(KEEP_CONTENT_PREFIX):
        return True
    return path.startswith("plugin-catalog/") and path.endswith((".yaml", ".yml"))


def keep_path(path: str) -> bool:
    return path.startswith(KEEP_PATH_PREFIX) or os.path.basename(path) in KEEP_PATH_BASENAME


def catalog_name_pattern(files: list[str]) -> re.Pattern[str] | None:
    """Catalog plugin names are install keys; a whole-token mention keeps its spelling."""
    stems = sorted(
        {
            Path(f).stem
            for f in files
            if f.startswith("plugin-catalog/") and f.endswith((".yaml", ".yml")) and "hermes" in Path(f).stem.lower()
        },
        key=len,
        reverse=True,
    )
    if not stems:
        return None
    return re.compile(r"(?<![\w-])(" + "|".join(re.escape(s) for s in stems) + r")(?![\w-])", re.I)


def protected_spans(text: str, patterns: list[re.Pattern[str]]) -> list[tuple[int, int]]:
    spans = [
        m.span()
        for m in URL.finditer(text)
        if "hermes" in m.group(0).lower() and not LOCAL_HOST.match(m.group(1).split(":")[0])
    ]
    spans.extend(
        m.span()
        for m in MD_LINK.finditer(text)
        if "nousresearch" not in m.group(0).lower() and not LOCAL_HOST.match(m.group(1).split(":")[0])
    )
    for pattern in patterns:
        spans.extend(m.span() for m in pattern.finditer(text) if "hermes" in m.group(0).lower())
    spans.sort()
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def transform(text: str, patterns: list[re.Pattern[str]], residual: Counter[str] | None = None) -> str:
    if "hermes" not in text.lower():
        return text
    spans = protected_spans(text, patterns)
    out: list[str] = []
    pos = span_index = 0
    for match in HERMES.finditer(text):
        start, end = match.span()
        while span_index < len(spans) and spans[span_index][1] <= start:
            span_index += 1
        if span_index < len(spans) and spans[span_index][0] <= start:
            if residual is not None:
                residual[text[spans[span_index][0] : spans[span_index][1]]] += 1
            continue
        word = match.group(0)
        if word == "hermes":
            new = "vael"
        elif word == "HERMES":
            new = "VAEL"
        elif word == "Hermes":
            before = text[start - 1] if start else ""
            after = text[end] if end < len(text) else ""
            new = "Vael" if IDENT.match(before) or IDENT.match(after) else "VAEL"
        else:  # odd casing: leave it for a human
            if residual is not None:
                residual[word] += 1
            continue
        out.extend((text[pos:start], new))
        pos = end
    out.append(text[pos:])
    return "".join(out)


def git_lines(repo: Path, *args: str) -> list[str]:
    raw = subprocess.run(["git", *args, "-z"], cwd=repo, capture_output=True, check=True).stdout
    return [item for item in raw.decode("utf-8").split("\0") if item]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--apply", action="store_true", help="rewrite files and move paths")
    parser.add_argument("--report", type=Path, help="directory for plan.tsv and residual.tsv")
    args = parser.parse_args()
    repo = args.repo.resolve()

    files = git_lines(repo, "ls-files")
    symlinks = {entry.split("\t", 1)[1] for entry in git_lines(repo, "ls-files", "-s") if entry.startswith("120000")}
    patterns = list(PROTECT)
    catalog = catalog_name_pattern(files)
    if catalog is not None:
        patterns.append(catalog)

    plan = {f: new for f in files if not keep_path(f) and (new := transform(f, patterns)) != f}
    targets = Counter(plan.values())
    untouched = {f.lower() for f in files if f not in plan}
    duplicates = [t for t, count in targets.items() if count > 1]
    clashes = [t for t in plan.values() if t.lower() in untouched]
    print(f"renames planned: {len(plan)}  duplicate targets: {len(duplicates)}  clashes: {len(clashes)}")
    if duplicates or clashes:
        print("refusing to continue: resolve the path collisions above first")
        return 1

    residual: Counter[str] = Counter()
    changed = 0
    for f in files:
        if f.startswith(VENDORED_CODE_PREFIX) and f.endswith(".py"):
            path = repo / f
            text = path.read_text(encoding="utf-8")
            new_text = VENDORED_HOST_API.sub(lambda m: m.group(0).replace("hermes", "vael"), text)
            if new_text != text:
                changed += 1
                if args.apply:
                    path.write_bytes(new_text.encode("utf-8"))
            continue
        if keep_content(f) or f in symlinks:
            continue
        path = repo / f
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\0" in raw[:8192] or b"hermes" not in raw.lower():
            continue
        try:
            text, encoding = raw.decode("utf-8"), "utf-8"
        except UnicodeDecodeError:
            text, encoding = raw.decode("latin-1"), "latin-1"
        new_text = transform(text, patterns + FILE_PROTECT.get(f, []), residual)
        if new_text != text:
            changed += 1
            if args.apply:
                path.write_bytes(new_text.encode(encoding))
    print(f"content files changed: {changed}  protected occurrences kept: {sum(residual.values())}")

    if args.report:
        args.report.mkdir(parents=True, exist_ok=True)
        (args.report / "plan.tsv").write_text(
            "\n".join(f"{old}\t{new}" for old, new in sorted(plan.items())), encoding="utf-8"
        )
        (args.report / "residual.tsv").write_text(
            "\n".join(f"{count}\t{token}" for token, count in residual.most_common()), encoding="utf-8"
        )

    if args.apply:
        # deepest paths first, so a directory never moves before its children
        for old in sorted(plan, key=lambda p: (-p.count("/"), p)):
            destination = repo / plan[old]
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(repo / old, destination)
        for parent in sorted({os.path.dirname(old) for old in plan}, key=lambda p: -p.count("/")):
            directory = repo / parent
            while directory != repo and directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
                directory = directory.parent
        print("applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
