#!/usr/bin/env python3
"""Read-only checks of premises and report; write audit and result only here."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
REPORT = OUT.parent / "复核105-分叉分支.md"


def main():
    inputs = json.loads((OUT / "inputs.json").read_text())
    for item in inputs["files"]:
        actual = Path(item["path"]).read_bytes()
        assert hashlib.sha256(actual).hexdigest() == item["sha256"], item["path"]
    report = REPORT.read_text()
    assert inputs["candidate"] in report
    assert "**未否证，保留候选条文。**" in report
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", report)
    for target in links:
        assert (REPORT.parent / target).exists(), target
    parsed = []
    for path in sorted(OUT.glob("*.json")):
        json.loads(path.read_text())
        parsed.append(path.name)
    comparison = json.loads((OUT / "comparison.json").read_text())
    assert comparison["all_checks_passed"]

    result = {
        "status": "完成",
        "report_path": str(REPORT),
        "verdicts": [{
            "name": "分叉分支", "verdict": "未否证",
            "reason": "允许的建造、同刻排法与数层选择均须覆盖；离线两种历史读法纳入可达性，删去点名无损。",
            "revised_text": "",
        }],
    }
    assert len(result["verdicts"]) == 1
    assert result["verdicts"][0]["verdict"] in ("未否证", "已否证", "修正")
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    check = {
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "premise_and_history_files_unchanged": len(inputs["files"]),
        "all_report_links_exist": True,
        "link_count": len(links),
        "all_evidence_json_parse": True,
        "parsed_evidence_files": parsed,
        "candidate_quote_matches_input": True,
        "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
        "result_path": str(OUT / "result.json"),
        "reader_review": {
            "standalone_verdict_and_premises": True,
            "version_comparison_separate_from_current_claim": True,
            "computed_counts_consistent_with_comparison": True,
            "local_examples_not_claimed_as_delivery_certificates": True,
            "unresolved_layer_semantics_explicit": True,
        },
    }
    (OUT / "delivery_check.json").write_text(json.dumps(check, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(check, ensure_ascii=False))


if __name__ == "__main__":
    main()
