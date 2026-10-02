#!/usr/bin/env python3
"""结构化交付、文件链接及证据指纹核验；不重新运行已通过的数值检查。"""
from pathlib import Path
import ast
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    result = json.loads((OUT / "result.json").read_text())
    assert set(result) == {"report_path", "items"}
    report = Path(result["report_path"])
    assert report == OUT.parent / "辅助-丁.md"
    text = report.read_text()
    assert len(result["items"]) == 9
    for n, item in zip(range(25, 34), result["items"]):
        assert set(item) == {"name", "final_version", "assessment", "note"}
        assert all(isinstance(v, str) and v for v in item.values())
        assert item["name"].startswith(str(n) + " ")
        assert item["assessment"] in {"可直接通过", "有疑点", "未做完"}
        assert "## " + item["name"] in text
    assert len(re.findall(r"^据：", text, flags=re.M)) == 9
    assert text.count("**整理条文**") == 9
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    for link in links:
        assert (report.parent / link).exists(), link
    for file in OUT.glob("*.py"):
        ast.parse(file.read_text(), filename=str(file))
    a = json.loads((OUT / "independent_checks.json").read_text())
    b = json.loads((OUT / "structure_startup_checks.json").read_text())
    assert a["status"] == b["status"] == "PASS"
    assert len(a["capacity_layers"]["capacity_cases"]) == 54
    assert a["capacity_layers"]["layer_case_count"] == 1024
    assert a["phases_segments"]["segment_case_count"] == 480
    assert a["seed_grinding"]["seed_species_phase_comparisons"] == 57120
    assert a["box"]["edge_count"] == 17
    assert b["order"]["complete_local_states"] == 77760
    assert b["order"]["order_comparisons"] == 1866240
    assert b["order"]["nontransport_cases"] == 256
    assert b["startup_inventory"]["directed_path_filling_cases"] == 6138
    assert b["startup_inventory"]["count"] == 5
    assert b["startup_structure"]["per_species_withdrawal_bound"] == 15031
    manifest = json.loads((OUT / "source_manifest.json").read_text())
    for row in manifest["sources"] + manifest["evidence"]:
        assert digest(Path(row["path"])) == row["sha256"], row["path"]
    delivery = dict(status="PASS", item_count=9, formal_clause_count=9, local_links_checked=len(links), numeric_files_status="PASS", source_fingerprints_unchanged=True, report_sha256=digest(report), result_sha256=digest(OUT / "result.json"), unresolved_items=[])
    (OUT / "delivery_check.json").write_text(json.dumps(delivery, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(delivery, ensure_ascii=False))


if __name__ == "__main__":
    main()
