"""Aggregate LLVM branch counters across generic instantiations and both entry points."""
import json
import sys
from collections import defaultdict
from pathlib import Path

data = json.load(sys.stdin)["data"][0]
print("| Rust 源文件 | 已走分支方向 / 总数 | 零计数方向（行.列，T 真 / F 假） |")
print("|---|---:|---|")
for file in data["files"]:
    filename = Path(file["filename"])
    relative = filename.relative_to(Path.cwd() / "src")
    counts = defaultdict(lambda: [0, 0])
    for start, col, end, col_end, yes, no, *_ in file["branches"]:
        pair = counts[start, col, end, col_end]
        pair[0] += yes
        pair[1] += no
    holes = [f"{line}.{col}{side}" for (line, col, _, _), pair in sorted(counts.items())
             for side, n in zip("TF", pair) if not n]
    total = len(counts) * 2
    print(f"| {relative} | {total - len(holes)} / {total} | {'、'.join(holes) or '—'} |")
