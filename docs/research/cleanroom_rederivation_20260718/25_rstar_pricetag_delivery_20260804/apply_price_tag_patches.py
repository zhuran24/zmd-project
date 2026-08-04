#!/usr/bin/env python3
"""Apply the price-tag JSON additions without modifying source files.

Usage:
  python apply_price_tag_patches.py \
      --source-dir /path/to/rstar_pricetag \
      --patch-dir  /path/to/rstar_pricetag_delivery \
      --output-dir /path/to/output

The script is idempotent.  It refuses to overwrite an existing theorem field or
slack row when the existing value differs from the patch value.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_theorems(source: Path, patch_path: Path, output: Path) -> None:
    doc = load_json(source)
    patch = load_json(patch_path)
    if patch.get("do_not_modify_existing_fields") is not True:
        raise ValueError("theorem patch does not declare do_not_modify_existing_fields=true")

    by_id = {row["id"]: row for row in doc["theorems"]}
    for fragment in patch["fragments"]:
        theorem_id = fragment["id"]
        if theorem_id not in by_id:
            raise KeyError(f"theorem not found: {theorem_id}")
        target = by_id[theorem_id]
        for key, value in fragment.items():
            if key == "id":
                continue
            if key in target and target[key] != value:
                raise ValueError(f"refusing to overwrite {theorem_id}.{key}")
            target.setdefault(key, value)

    authority = doc.get("authority", {})
    if authority.get("is_authoritative") is not False or authority.get("ledger_effect") != "none":
        raise ValueError("authority/ledger guard failed")
    dump_json(output, doc)


def render_added_rows(unconditional: list[dict[str, Any]], conditional: list[dict[str, Any]]) -> str:
    def cell(row: dict[str, Any], *keys: str) -> str:
        for key in keys:
            if key in row:
                value = row[key]
                if isinstance(value, (dict, list)):
                    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                return str(value)
        return ""

    lines = [
        "",
        "## D. 本批价签精算新增行（由补丁脚本生成）",
        "",
        "> `authority=false`；这些行只补充审计口径，不登记界，不改变账本。",
        "",
        "### 无条件新增行",
        "",
        "| 账 | 容量 | 需求 | 余量 | 证据等级 |",
        "|---|---:|---:|---:|---|",
    ]
    for row in unconditional:
        lines.append(
            f"| {cell(row, '账')} | {cell(row, '容量')} | {cell(row, '需求')} | "
            f"{cell(row, '余量')} | {cell(row, '证据等级')} |"
        )
    lines.extend([
        "",
        "### G1 条件新增行",
        "",
        "| 账 | 容量 | 需求或需求下界 | 余量或余量上界 | 条件与证据 |",
        "|---|---:|---:|---:|---|",
    ])
    for row in conditional:
        condition = cell(row, "条件")
        evidence = cell(row, "证据等级")
        lines.append(
            f"| {cell(row, '账')} | {cell(row, '容量')} | {cell(row, '需求', '需求下界')} | "
            f"{cell(row, '余量', '余量上界')} | {condition}；{evidence} |"
        )
    return "\n".join(lines) + "\n"


def merge_slack(source: Path, patch_path: Path, output: Path) -> None:
    text = source.read_text(encoding="utf-8")
    patch = load_json(patch_path)
    if patch.get("authority") is not False or patch.get("ledger_effect") != "none":
        raise ValueError("slack patch authority/ledger guard failed")

    matches = list(re.finditer(r"```json\s*(\{.*?\})\s*```", text, flags=re.S))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one fenced JSON block, got {len(matches)}")
    match = matches[0]
    doc = json.loads(match.group(1))

    for key in ("unconditional_rows", "g1_conditional_rows"):
        existing = {row.get("账"): row for row in doc[key]}
        for row in patch[key]:
            account = row["账"]
            if account in existing and existing[account] != row:
                raise ValueError(f"refusing to overwrite slack row: {account}")
            if account not in existing:
                doc[key].append(row)
                existing[account] = row

    block = "```json\n" + json.dumps(doc, ensure_ascii=False, indent=2) + "\n```"
    merged = text[: match.start()] + block + text[match.end() :]
    if "## D. 本批价签精算新增行" not in merged:
        merged += render_added_rows(patch["unconditional_rows"], patch["g1_conditional_rows"])
    output.write_text(merged, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--patch-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    merge_theorems(
        args.source_dir / "04_derived_theorems.json",
        args.patch_dir / "patch_B_04_derived_theorems.merge.json",
        args.output_dir / "04_derived_theorems.patched.json",
    )
    merge_slack(
        args.source_dir / "03_slack_audit_table.md",
        args.patch_dir / "patch_C_03_slack_audit_rows.merge.json",
        args.output_dir / "03_slack_audit_table.patched.md",
    )
    print("patches applied without modifying source files")


if __name__ == "__main__":
    main()
