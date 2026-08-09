#!/usr/bin/env python3
"""Validate the R-* price-tag delivery using only the Python standard library."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

EXPECTED_RULES_HASH = "5012845367e2a0e0b51938cc36a18f46fcdc8daccfa34639f96a05a67dc12a05"
EXPECTED_INSTANCES_HASH = "545b98c2b4f96643f1346b423edf2dc8e300a0c815b6cf821776ceed03cd4cd6"
R_IDS = [
    "R-BODY-IN-REGION",
    "R-FRONT-IN-REGION",
    "R-PORTAL-FIXED",
    "R-PAT-CONN",
    "R-POWER-LOCAL",
    "R-POLE-CAP",
    "R-HOLE-IN-REGION",
    "R-CORE-FRONT-RESERVE",
    "R-BOUNDARY-LAYOUT",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_report(root: Path) -> dict[str, Any]:
    report = (root / "RSTAR_PRICETAG_REPORT.md").read_text(encoding="utf-8")
    checks = {
        "nine_numbered_sections": all(report.count(f"### {i}.") == 1 for i in range(1, 10)),
        "nine_price_blocks": report.count("#### ① 价签") == 9,
        "nine_premise_blocks": report.count("#### ② 前提集") == 9,
        "nine_retreat_blocks": report.count("#### ③ 撤退线（含梯级）") == 9,
        "nine_experiment_blocks": report.count("#### ④ 判定实验") == 9,
        "authority_false_present": "`authority=false`" in report,
        "both_baseline_hashes_present": EXPECTED_RULES_HASH in report and EXPECTED_INSTANCES_HASH in report,
        "no_em_dash_in_authored_report": "—" not in report,
    }
    lines = report.splitlines()
    in_code = False
    untagged: list[int] = []
    for index, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped or stripped.startswith(("#", "|", ">")):
            continue
        if not stripped.endswith(("【已证明】", "【强论据】", "【猜测】")):
            untagged.append(index)
    checks["untagged_prose_lines"] = untagged
    if not all(v is True or v == [] for v in checks.values()):
        raise AssertionError(f"report validation failed: {checks}")
    return checks


def validate_theorem_patch(root: Path, source: Path) -> dict[str, Any]:
    original = load_json(source / "04_derived_theorems.json")
    patched = load_json(root / "04_derived_theorems.patched.json")
    patch = load_json(root / "patch_B_04_derived_theorems.merge.json")
    assert patch["authority"] is False and patch["ledger_effect"] == "none"
    assert patched["authority"] == original["authority"]
    assert patched["authority"]["is_authoritative"] is False
    assert patched["authority"]["ledger_effect"] == "none"
    original_by_id = {row["id"]: row for row in original["theorems"]}
    patched_by_id = {row["id"]: row for row in patched["theorems"]}
    fragments = {row["id"]: row for row in patch["fragments"]}
    assert list(fragments) == R_IDS
    for theorem_id, old in original_by_id.items():
        assert theorem_id in patched_by_id
        for key, value in old.items():
            assert patched_by_id[theorem_id][key] == value
    for theorem_id, fragment in fragments.items():
        for key, value in fragment.items():
            if key != "id":
                assert patched_by_id[theorem_id][key] == value
        assert EXPECTED_RULES_HASH in fragment["baseline_hashes"]
        assert EXPECTED_INSTANCES_HASH in fragment["baseline_hashes"]
    return {
        "original_theorem_count": len(original["theorems"]),
        "fragment_count": len(fragments),
        "original_fields_unchanged": True,
        "authority_unchanged": True,
    }


def parse_fenced_json(markdown: str) -> dict[str, Any]:
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", markdown, flags=re.S)
    if len(blocks) != 1:
        raise AssertionError(f"expected one fenced JSON block, got {len(blocks)}")
    return json.loads(blocks[0])


def validate_slack_patch(root: Path) -> dict[str, Any]:
    patch = load_json(root / "patch_C_03_slack_audit_rows.merge.json")
    assert patch["authority"] is False and patch["ledger_effect"] == "none"
    assert len(patch["unconditional_rows"]) == 2
    assert len(patch["g1_conditional_rows"]) == 5
    for row in patch["unconditional_rows"] + patch["g1_conditional_rows"]:
        hashes = row["基线哈希"]
        assert hashes["canonical_rules_sha256"] == EXPECTED_RULES_HASH
        assert hashes["mandatory_instances_sha256"] == EXPECTED_INSTANCES_HASH
        assert "【" in row["证据等级"]
    doc = parse_fenced_json((root / "03_slack_audit_table.patched.md").read_text(encoding="utf-8"))
    assert len(doc["unconditional_rows"]) == 7
    assert len(doc["g1_conditional_rows"]) == 11
    return {
        "new_unconditional_rows": 2,
        "new_g1_conditional_rows": 5,
        "patched_unconditional_total": 7,
        "patched_g1_total": 11,
    }


def validate_experiments(root: Path) -> dict[str, Any]:
    text = (root / "patch_D_experiment_specs.md").read_text(encoding="utf-8")
    checks = {
        "experiment_sections": text.count("## D") == 9,
        "proposition_blocks": text.count("### 被判定命题") == 9,
        "pseudocode_blocks": text.count("### 模型伪代码") == 9,
        "constant_tables": text.count("### 输入常量表") == 9,
        "budget_blocks": text.count("### 规模、预算与终止") == 9,
        "outcome_blocks": text.count("### 三种结果判读") == 9,
        "hashes_present": EXPECTED_RULES_HASH in text and EXPECTED_INSTANCES_HASH in text,
        "no_em_dash": "—" not in text,
    }
    if not all(checks.values()):
        raise AssertionError(checks)
    return checks


def validate_arithmetic(root: Path) -> dict[str, Any]:
    subprocess.run([sys.executable, str(root / "price_tag_arithmetic_audit.py")], check=True, stdout=subprocess.DEVNULL)
    result = load_json(root / "price_tag_arithmetic_results.json")
    assert result["baseline_hashes"]["rules/canonical_rules.json"] == EXPECTED_RULES_HASH
    assert result["baseline_hashes"]["data/preprocessed/mandatory_exact_instances.json"] == EXPECTED_INSTANCES_HASH
    assert result["body_and_front"]["mandatory_instance_pose_incidences"]["body_removed"] == 1_169_408
    assert result["body_and_front"]["mandatory_instance_pose_incidences"]["front_increment_removed"] == 386_560
    assert result["portal_and_core_masks"]["manufacturing_single_pose_domain"]["weighted_removed"] == 176_088
    assert result["portal_and_core_masks"]["core_front_overreserve_with_other_current_masks"]["pole_anchors_recovered"] == 8
    assert result["hole_rectangle_witness_domain"]["all_original_min_side_ge_6"] == 4_601_025
    assert result["boundary_layout"]["two_arm_nonoverlapping_geometric_arrangements"] == 47
    assert result["power_relation_domain"]["cross_region_incidences"] == 165_600
    return {
        "body_removed": 1_169_408,
        "front_increment_removed": 386_560,
        "portal_weighted_removed": 176_088,
        "core_pole_anchors_recovered": 8,
        "hole_witnesses_h0": 4_601_025,
        "boundary_arrangements": 47,
        "power_cross_region_relations": 165_600,
    }


def validate_applicator(root: Path, source: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp)
        first = base / "first"
        second_source = base / "second_source"
        second = base / "second"
        subprocess.run([
            sys.executable, str(root / "apply_price_tag_patches.py"),
            "--source-dir", str(source), "--patch-dir", str(root), "--output-dir", str(first),
        ], check=True, stdout=subprocess.DEVNULL)
        second_source.mkdir()
        (second_source / "03_slack_audit_table.md").write_bytes((first / "03_slack_audit_table.patched.md").read_bytes())
        (second_source / "04_derived_theorems.json").write_bytes((first / "04_derived_theorems.patched.json").read_bytes())
        subprocess.run([
            sys.executable, str(root / "apply_price_tag_patches.py"),
            "--source-dir", str(second_source), "--patch-dir", str(root), "--output-dir", str(second),
        ], check=True, stdout=subprocess.DEVNULL)
        assert (first / "03_slack_audit_table.patched.md").read_bytes() == (second / "03_slack_audit_table.patched.md").read_bytes()
        assert (first / "04_derived_theorems.patched.json").read_bytes() == (second / "04_derived_theorems.patched.json").read_bytes()
    return {"idempotent_byte_check": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delivery-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--source-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.delivery_dir.resolve()
    source = args.source_dir.resolve()
    results = {
        "schema": "w0_rstar_pricetag_delivery_validation_v1",
        "authority": False,
        "ledger_effect": "none",
        "report": validate_report(root),
        "theorem_patch": validate_theorem_patch(root, source),
        "slack_patch": validate_slack_patch(root),
        "experiments": validate_experiments(root),
        "arithmetic": validate_arithmetic(root),
        "applicator": validate_applicator(root, source),
    }
    files = {}
    for path in sorted(root.iterdir()):
        if path.is_file() and path.name not in {"validation_results.json", "MANIFEST.sha256"}:
            files[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    results["files"] = files
    out = root / "validation_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
