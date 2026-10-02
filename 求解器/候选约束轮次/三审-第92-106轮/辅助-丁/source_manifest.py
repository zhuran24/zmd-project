#!/usr/bin/env python3
"""记录本批实际依赖材料和独立复算产物的指纹。只写本目录。"""
from pathlib import Path
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROUNDS = OUT.parent.parent
sources = [
    "第107-109轮/前提快照/《明日方舟：终末地》游戏规则.txt",
    "第107-109轮/前提快照/求解任务.txt",
    "第107-109轮/前提快照/求解约束.txt",
    "第107-109轮/前提快照/求解充分条件.txt",
    "第107-109轮/临时规则.md",
    "第92-94轮/推导92E.md", "第92-94轮/复核93E.md", "第92-94轮/复核94E.md",
    "第92-94轮/推导92F.md", "第92-94轮/复核93F.md", "第92-94轮/复核94F.md",
    "第95-97轮/推导95M.md", "第95-97轮/复核96M.md", "第95-97轮/复核97M.md",
    "第95-97轮/推导95T.md", "第95-97轮/复核96T.md", "第95-97轮/复核97T.md",
    "第101-103轮/推导101H.md", "第101-103轮/复核102H.md", "第101-103轮/复核103H.md",
    "三审-第92-106轮/三审报告.md",
]


def describe(p):
    b = p.read_bytes()
    return dict(path=str(p), sha256=hashlib.sha256(b).hexdigest(), lines=len(b.decode().splitlines()), bytes=len(b))


def main():
    result = dict(sources=[describe(ROUNDS / p) for p in sources], evidence=[describe(OUT / p) for p in ("independent_checks.py", "independent_checks.json", "structure_startup_checks.py", "structure_startup_checks.json")])
    assert result["sources"][0]["lines"] == 115
    for filename, expected in (("求解约束.txt", 77), ("求解充分条件.txt", 11)):
        text = (ROUNDS / "第107-109轮/前提快照" / filename).read_text()
        count = sum(line.startswith("    据：") for line in text.splitlines())
        assert count == expected, (filename, count)
    result["inventory"] = dict(rule_lines=115, necessary_conditions=77, sufficient_conditions=11)
    (OUT / "source_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(status="PASS", source_files=len(sources), inventory=result["inventory"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
