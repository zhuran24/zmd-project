#!/usr/bin/env python3
"""完整性批评-内核-2：对全部 v3 运行记录求 99 条轴的覆盖并集。

audit_round5.py 的 required 名单只覆盖 transfer./bridge./manufacturing. 等子集；
本脚本对每条轴取全部记录中的最好状态，列出从未 exercised 的轴。只读，不写仓库文件。
"""
import collections, glob, json, sys
from pathlib import Path

BASE = Path("/home/zhuran24/zmd-research-fresh/求解器/数据/样例")
ORDER = ["exercised", "input_checked", "stop_not_triggered", "proof_pending", "not_exercised"]


def main():
    records = sorted(BASE.glob("*-运行记录-v3-kernel.json"))
    best, disp = {}, {}
    for path in records:
        data = json.loads(path.read_text())
        for row in data["uncovered_axes"]:
            axis, status = row["axis"], row["coverage_status"]
            disp[axis] = row["disposition"]
            if axis not in best or ORDER.index(status) < ORDER.index(best[axis]):
                best[axis] = status
    counts = collections.Counter(best.values())
    never = sorted((a, best[a], disp[a]) for a in best if best[a] != "exercised")
    result = {"schema": "critic2-axis-coverage-v1", "records": len(records), "axes": len(best),
              "counts": dict(counts),
              "not_exercised": [{"axis": a, "disposition": disp[a]} for a in sorted(best)
                                if best[a] == "not_exercised"],
              "never_exercised": [{"axis": a, "best_status": s, "disposition": d} for a, s, d in never]}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
