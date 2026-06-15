from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]")


def split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_text, body_text). Missing frontmatter yields ("", text)."""
    m = FM_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\").strip()


def _strip_inline_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for idx, char in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "#" and (idx == 0 or value[idx - 1].isspace()):
            return value[:idx].rstrip()
    return value.rstrip()


def _split_inline_items(value: str) -> list[str]:
    items: list[str] = []
    start = 0
    quote: str | None = None
    escaped = False
    depth = 0
    for idx, char in enumerate(value):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char in "[{(":
            depth += 1
        elif char in "]})":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            items.append(value[start:idx].strip())
            start = idx + 1
    items.append(value[start:].strip())
    return [item for item in items if item]


def _parse_scalar(value: str) -> Any:
    value = _strip_inline_comment(value).strip()
    if len(value) >= 2 and value[0] == "[" and value[-1] == "]":
        return [_parse_scalar(item) for item in _split_inline_items(value[1:-1])]
    if len(value) >= 2 and value[0] == "{" and value[-1] == "}":
        out: dict[str, Any] = {}
        for item in _split_inline_items(value[1:-1]):
            if ":" not in item:
                continue
            key, raw = item.split(":", 1)
            out[_unquote(key)] = _parse_scalar(raw)
        return out
    return _unquote(value)


def parse_frontmatter(frontmatter: str) -> dict[str, Any]:
    """Small, dependency-free parser for the simple frontmatter used here.

    It intentionally does not try to be a YAML implementation. It supports:
      key: scalar
      key:
        - list item
      key: [inline, list]
      key: {inline: map}

    Nested maps such as `metadata:` are preserved only for simple scalar children
    through flattened keys like `metadata.type` when possible.
    """
    data: dict[str, Any] = {}
    lines = frontmatter.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or raw.lstrip().startswith("#"):
            i += 1
            continue
        if raw.startswith((" ", "\t")):
            i += 1
            continue
        m = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*)$", raw)
        if not m:
            i += 1
            continue
        key, rest = m.group(1), m.group(2)
        if rest.strip():
            parsed = _parse_scalar(rest)
            data[key] = parsed
            if isinstance(parsed, dict):
                for nk, nv in parsed.items():
                    data[f"{key}.{nk}"] = nv
            i += 1
            continue

        # Collect an indented list or shallow nested scalars.
        i += 1
        list_items: list[Any] = []
        nested: dict[str, Any] = {}
        while i < len(lines):
            child = lines[i]
            if not child.strip():
                i += 1
                continue
            if not child.startswith((" ", "\t")):
                break
            stripped = child.strip()
            if stripped.startswith("- "):
                list_items.append(_parse_scalar(stripped[2:]))
            else:
                mm = re.match(r"^([A-Za-z0-9_.-]+):\s*(.*)$", stripped)
                if mm:
                    nested[mm.group(1)] = _parse_scalar(mm.group(2))
            i += 1
        if list_items:
            data[key] = list_items
        elif nested:
            data[key] = nested
            for nk, nv in nested.items():
                data[f"{key}.{nk}"] = nv
        else:
            data[key] = ""
    return data


def extract_wikilinks(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in WIKILINK_RE.finditer(text):
        slug = m.group(1).strip()
        if slug and slug not in seen:
            out.append(slug)
            seen.add(slug)
    return out


@dataclass(frozen=True)
class MarkdownNodeRaw:
    path: Path
    frontmatter: str
    body: str
    meta: dict[str, Any]
    body_start_line: int = 1


def read_markdown_node(path: Path) -> MarkdownNodeRaw:
    text = path.read_text(encoding="utf-8")
    front, body = split_frontmatter(text)
    m = FM_RE.match(text)
    body_start_line = text[:m.end()].count("\n") + 1 if m else 1
    return MarkdownNodeRaw(path=path, frontmatter=front, body=body, meta=parse_frontmatter(front), body_start_line=body_start_line)
