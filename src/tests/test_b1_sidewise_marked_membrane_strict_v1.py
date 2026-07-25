from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = Path("/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721")
RESEARCH = ROOT / "docs/research/b1_sidewise_marked_membrane_strict_20260724"
STRICT = SOURCE_ROOT / "docs/research/cleanroom_rederivation_20260718" / "strict/external/problem_instance.json"
RUN = ROOT / ".artifacts/track_b_b1_sidewise_marked_membrane_strict_20260724" / "run-20260723T161302Z-SMM2"


def load(name: str):
    path = RESEARCH / name
    module_name = f"_test_sidewise_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def strict_payload() -> dict:
    return json.loads(STRICT.read_bytes())


def file_id(path: Path) -> dict:
    raw = path.read_bytes()
    return {
        "path": str(path.absolute()),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "mode_octal": f"{path.stat().st_mode & 0o7777:04o}",
    }


def require_authority_run() -> None:
    if not RUN.is_dir():
        pytest.skip("no local no-overwrite authority run")


def test_primary_strict_entity_budget_and_band_delta() -> None:
    primary = load("recompute_entity_endpoint_budget_v1.py")
    results = primary._derive(strict_payload())
    assert results["marked_entity_budget"]["entity_census"] == {
        "0": 170,
        "1": 89,
        "2": 3,
        "3": 4,
    }
    assert results["marked_entity_budget"]["top_eight"] == [
        3,
        3,
        3,
        3,
        2,
        2,
        2,
        1,
    ]
    assert results["marked_entity_budget"]["top_eight_sum"] == 19
    assert results["ceiling_exclusion"] == {
        "dimensions": [[22, 54], [54, 22]],
        "combined_inside_cap": 209,
        "outside_incidence_floor": 529,
        "outside_access_cell_floor": 133,
        "rectangle_plus_outside_cells": 1321,
        "available_cell_cap": 1320,
        "excluded": True,
    }
    assert results["band_composition"]["old_band_count"] == 2084
    assert results["band_composition"]["candidate_band_count"] == 2086
    assert results["band_composition"]["new_ceiling_orientations"] == [
        [22, 54],
        [54, 22],
    ]


def test_independent_v1_failure_is_real_and_v2_partition_repairs_only_generic_io() -> None:
    independent = load("verify_entity_endpoint_budget_independent_v1.py")
    data = strict_payload()
    with pytest.raises(
        independent.IndependentError,
        match="flat operation-instance join mismatch",
    ):
        independent.derive_flat(data)
    group_ids = {group["id"] for group in data["operation_groups"]}
    corrected = copy.deepcopy(data)
    generic = []
    for row in corrected["required_instances"]:
        if row.get("operation") not in group_ids:
            generic.append((row["template"], row["operation"]))
            row.pop("operation")
    assert len(generic) == 47
    assert {template for template, _ in generic} == {
        "boundary_storage_port",
        "protocol_core",
    }
    assert {operation for _, operation in generic} == {"generic_io"}
    results = independent.derive_flat(corrected)
    assert results["top_eight"] == [3, 3, 3, 3, 2, 2, 2, 1]
    assert results["combined_inside_cap"] == 209


def test_translation_rederives_strict_math_and_complete_band() -> None:
    translation = load("verify_ceiling_exclusion_translation_v1.py")
    facts = translation.derive_strict(strict_payload())
    assert facts["required_body_area"] == 3544
    assert facts["active_terminals"] == 628
    assert facts["total_marks"] == 110
    assert facts["top_eight_sum"] == 19
    assert facts["combined_inside_cap"] == 209
    assert facts["total_required_cells"] == 1321
    assert facts["old_band_count"] == 2084
    assert facts["candidate_band_count"] == 2086
    assert facts["band_delta"] == [[22, 54], [54, 22]]


def test_opb_is_transparent_and_constraint_mutations_fail() -> None:
    encoder = load("ceiling_exclusion_pb_encoder_v1.py")
    translation = load("verify_ceiling_exclusion_translation_v1.py")
    formula = encoder.render_formula()
    assert len(formula) == 283
    assert hashlib.sha256(formula).hexdigest() == ("d4b79cd76c80d23e509ad09b1d2e7fa02fa337049f40459ab803f0fc55a4d865")
    parsed = translation.parse_formula(formula)
    assert parsed["constraint_multiset_exact"] is True
    with pytest.raises(translation.TranslationError):
        translation.parse_formula(formula.replace(b"-1 x2 >= 0 ;", b"+1 x2 >= 0 ;"))
    with pytest.raises(translation.TranslationError):
        translation.parse_formula(formula.rsplit(b"-1 x2 >= 0 ;\n", 1)[0])


def test_variable_map_locks_ceil_and_tie_break_arithmetic() -> None:
    encoder = load("ceiling_exclusion_pb_encoder_v1.py")
    mapping = encoder.variable_map()
    assert [row["width"] for row in mapping["variables"]] == [22, 54]
    assert [row["height"] for row in mapping["variables"]] == [54, 22]
    assert {row["coefficient"] for row in mapping["variables"]} == {-1}
    assert all(row["outside_incidence_floor"] == 529 for row in mapping["variables"])
    assert all(row["outside_cell_floor"] == 133 for row in mapping["variables"])
    assert all(row["total_required_cells"] == 1321 for row in mapping["variables"])


def test_resume_runner_is_byte_snapshotted_not_path_imported() -> None:
    source = (RESEARCH / "resume_authority_v1.py").read_text()
    assert "same_fd_snapshot_compile_exec" in source
    assert "compile(raw, str(FORMAL_RUNNER)" in source
    assert "spec_from_file_location" not in source
    require_authority_run()
    resume = json.loads((RUN / "resume-a001/authority.json").read_bytes())
    runner = resume["upstream_runner_authority"]["runner"]
    assert runner["size_bytes"] == 169658
    assert runner["mode_octal"] == "0644"
    assert runner["sha256"] == ("869f6bd6bcab88c73a989a68e288e8ac68eb026e7791e976e2289de7285dd24f")
    assert resume["upstream_formal_replay"]["status"] == "VERIFIED"


def test_geometry_joint_mutations_fail_closed() -> None:
    require_authority_run()
    builder = load("build_geometry_adversarial_verdict_v1.py")
    authority = json.loads((RUN / "geometry-authority-a002/authority.json").read_bytes())
    primary_path = RUN / "recomputations-a002/primary.json"
    independent_path = RUN / "recomputations-a002/independent.json"
    primary = json.loads(primary_path.read_bytes())
    independent = json.loads(independent_path.read_bytes())
    tool_identity = file_id(RESEARCH / "build_geometry_adversarial_verdict_v1.py")
    with pytest.raises(builder.VerdictError, match="top-eight"):
        mutated = copy.deepcopy(independent)
        mutated["results"]["top_eight"][-1] = 2
        builder.build_verdict(
            authority,
            file_id(RUN / "geometry-authority-a002/authority.json"),
            primary,
            file_id(primary_path),
            mutated,
            file_id(independent_path),
            tool_identity,
        )
    with pytest.raises(builder.VerdictError, match="ceiling arithmetic"):
        mutated = copy.deepcopy(independent)
        mutated["results"]["combined_inside_cap"] = 210
        builder.build_verdict(
            authority,
            file_id(RUN / "geometry-authority-a002/authority.json"),
            primary,
            file_id(primary_path),
            mutated,
            file_id(independent_path),
            tool_identity,
        )


def test_formal_resource_contract_and_incomplete_closeout_are_exact() -> None:
    require_authority_run()
    internal = json.loads((RUN / "formal-a001/internal_formal_receipt.json").read_bytes())
    launch = json.loads((RUN / "launch-a001/launch_receipt.json").read_bytes())
    closeout = json.loads((RUN / "closeout-a001/closeout.json").read_bytes())
    assert internal["status"] == "VERIFIED"
    assert internal["proof_status"] == "VERIFIED UNSATISFIABLE"
    assert internal["verifier"]["status_lines"] == ["s VERIFIED UNSATISFIABLE"]
    assert internal["proof"]["size_bytes"] == 137
    assert internal["proof"]["sha256"] == ("48dec7cbb9ee0aebd8bc6f1a34b1e2b4024f85c80159d5fb82207bc6bf0286aa")
    expected = {
        "MemoryHigh": str(35 * 1024**3),
        "MemoryMax": str(39 * 1024**3),
        "MemorySwapMax": str(16 * 1024**3),
        "OOMPolicy": "continue",
        "KillMode": "control-group",
        "SendSIGKILL": "yes",
    }
    assert {
        key: value["value"] for key, value in internal["resource_contract"]["start"]["properties"].items()
    } == expected
    assert launch["status"] == "FAIL_CLOSED"
    assert closeout["status"] == "FORMAL_AUTHORITY_INCOMPLETE"
    assert closeout["upper_bound_update_authorized"] is False
    assert closeout["ledger"] == {"upper": [1188, 22], "lower": "absent"}
    assert not (RUN / "final-a001").exists()


def test_artifact_hashes_and_no_overwrite_history() -> None:
    require_authority_run()
    expected = {
        "geometry-authority-a001/authority.json": (
            4131,
            "65971b88694964e0b0fd9d4c68c0e352cbbb20256a0cc44794c3a00bb210ce6a",
        ),
        "recomputations-a001/primary.json": (
            4008,
            "5b42ee69a79f44646ac849a6e707382bb502b038fe6a60c97d02a10eb158d3d1",
        ),
        "geometry-authority-a002/authority.json": (
            6297,
            "c2f66f798362d68c74fa6e58d23d8f038a26d24230e5ad65817508763249bdaf",
        ),
        "geometry-admission-a002/admission.json": (
            3075,
            "abb67f2334756a22650457b3a066d32b48b7d5f8918406b53f4f4140ec3fbfdc",
        ),
        "translation-a001/translation_gate.json": (
            5356,
            "e2146c2f1e4ded7bb080e7cb29c55d506a16ba778f69a64e492422ca99b8aa67",
        ),
        "closeout-a001/closeout.json": (
            5877,
            "35f87223990b72cf2d77581f2718603cc8f620b97ce044fc502fc368ecec47b9",
        ),
    }
    for relative, (size, digest) in expected.items():
        raw = (RUN / relative).read_bytes()
        assert len(raw) == size
        assert hashlib.sha256(raw).hexdigest() == digest
