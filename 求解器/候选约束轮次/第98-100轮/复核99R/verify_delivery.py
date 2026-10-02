#!/usr/bin/env python3
"""检查报告链接、结构化结论和归档文件是否相互一致。只写本目录。"""
from pathlib import Path
from hashlib import sha256
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REPORT = HERE.parent / "复核99R.md"


def main():
    text = REPORT.read_text()
    verdict = json.loads((HERE / "verdict.json").read_text())
    assert verdict["report_path"] == str(REPORT)
    assert len(verdict["verdicts"]) == 1
    v = verdict["verdicts"][0]
    assert set(v) == {"name", "verdict", "reason", "revised_text"}
    assert v["name"] == "分叉分支" and v["verdict"] == "未否证" and v["revised_text"] == ""
    assert "状态：复核完成" in text and "结论为**未否证**" in text
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    for link in links:
        assert (REPORT.parent / link).exists(), link
    comparison = json.loads((HERE / "comparison.json").read_text())
    assert comparison["status"] == "PASS"
    for entry in comparison["manifest"]:
        p = ROOT / entry["path"]
        assert sha256(p.read_bytes()).hexdigest() == entry["sha256"], str(p)
    assert not list(HERE.rglob("__pycache__"))
    receipt = {"status": "PASS", "report_sha256": sha256(REPORT.read_bytes()).hexdigest(),
               "verdict_sha256": sha256((HERE / "verdict.json").read_bytes()).hexdigest(),
               "comparison_sha256": sha256((HERE / "comparison.json").read_bytes()).hexdigest(),
               "local_links_checked": len(links), "input_and_evidence_hashes_current": True,
               "report_verdict_matches_json": True}
    (HERE / "delivery_check.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
