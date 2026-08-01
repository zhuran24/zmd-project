from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "docs/research/b1_sidewise_marked_membrane_fresh_authority_20260727"
B0 = Path("/home/zhuran24/zmd-pj-codex-baselines/track-b-b0-1190-20260721")
B1 = Path("/home/zhuran24/zmd-pj-codex-baselines/track-b-b1-sidewise-membrane-20260724")
SMM2 = (
    B1
    / ".artifacts/track_b_b1_sidewise_marked_membrane_strict_20260724"
    / "run-20260723T161302Z-SMM2"
)
HISTORICAL_PATHS = {
    "old_r4_receipt": (
        B0
        / ".artifacts/track_b_b1_r4_1188_22_pb_20260723"
        / "formal-a001-20260723T091800Z-398f8725"
        / "authority_receipt.json"
    ),
    "geometry_admission": SMM2 / "geometry-admission-a002/admission.json",
    "strict_instance": (
        B0
        / "docs/research/cleanroom_rederivation_20260718"
        / "strict/external/problem_instance.json"
    ),
    "formula": SMM2 / "build-a001/formula.opb",
    "variable_map": SMM2 / "build-a001/variable_map.json",
}


def load_gate():
    sys.path.insert(0, str(RESEARCH))
    path = RESEARCH / "verify_smm4_composition_v1.py"
    spec = importlib.util.spec_from_file_location("_test_smm4_composition", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require_history() -> None:
    missing = [str(path) for path in HISTORICAL_PATHS.values() if not path.is_file()]
    if missing:
        pytest.skip(f"SMM4 immutable history is unavailable: {missing}")


def historical_inputs(gate):
    require_history()
    raw_inputs = {}
    identities = {}
    pins = {}
    for name, path in HISTORICAL_PATHS.items():
        raw_inputs[name], identities[name] = gate.snapshot_regular(path, name)
        pins[name] = {
            "identity": identities[name],
            "content_projection": gate.canonical_content_projection(identities[name], name),
        }
    return raw_inputs, identities, pins


def test_complete_composition_is_local_admission_only() -> None:
    gate = load_gate()
    raw_inputs, identities, pins = historical_inputs(gate)
    report = gate.verify_composition(raw_inputs, identities, pins)
    assert report["status"] == "PASS"
    assert report["decision"] == "LOCAL_UPPER_RECOVERY_INPUT_ADMITTED"
    assert report["formal_attempt_admitted"] is True
    assert report["upper_bound_update_authorized"] is False
    assert report["old_r4_authority"]["upper_bound_update_authorized"] is True
    assert report["independent_band_composition"] == {
        "grid": {"width": 70, "height": 70},
        "objective": {
            "kind": "max_lex_area_min_side",
            "body_cells_only": True,
            "minimum_side": 6,
        },
        "old_upper": [1188, 22],
        "old_band_count": 2084,
        "candidate_upper": [1188, 18],
        "candidate_band_count": 2086,
        "delta_orientations": [[22, 54], [54, 22]],
        "old_delta_disjoint": True,
        "old_union_delta_equals_candidate": True,
    }
    assert report["claim_boundary"]["ledger_upper_remains"] == [1188, 22]
    assert report["claim_boundary"]["lower_remains"] == "absent"
    assert report["claim_boundary"]["whole_instance_infeasibility"] is False


def test_old_r4_receipt_must_be_verified_authorized_complete_band_semantics() -> None:
    gate = load_gate()
    raw_inputs, _, _ = historical_inputs(gate)
    receipt = gate.strict_json(raw_inputs["old_r4_receipt"], "old R4 receipt")
    assert gate.verify_old_r4_receipt(receipt)["proof_status"] == "VERIFIED UNSATISFIABLE"
    for field, value in (
        ("status", "FAILED"),
        ("upper_bound_update_authorized", False),
        ("production_certified", True),
        ("semantics", "local_delta_only"),
    ):
        mutated = copy.deepcopy(receipt)
        mutated[field] = value
        with pytest.raises(gate.CompositionError):
            gate.verify_old_r4_receipt(mutated)
    mutated = copy.deepcopy(receipt)
    mutated["unexpected"] = True
    with pytest.raises(gate.CompositionError, match="key set"):
        gate.verify_old_r4_receipt(mutated)


def test_band_is_reenumerated_from_strict_grid_and_objective() -> None:
    gate = load_gate()
    raw_inputs, _, _ = historical_inputs(gate)
    instance = gate.strict_json(raw_inputs["strict_instance"], "strict instance")
    bands = gate.derive_bands(instance)
    assert bands["old_band_count"] == 2084
    assert bands["candidate_band_count"] == 2086
    assert bands["delta_orientations"] == [[22, 54], [54, 22]]
    assert bands["old_union_delta_equals_candidate"] is True
    for mutation in (
        lambda value: value["grid"].__setitem__("width", 69),
        lambda value: value["objective"].__setitem__("minimum_side", 7),
        lambda value: value["objective"].__setitem__("kind", "area_only"),
        lambda value: value["objective"].__setitem__("extra", True),
    ):
        changed = copy.deepcopy(instance)
        mutation(changed)
        with pytest.raises(gate.CompositionError):
            gate.derive_bands(changed)


def test_geometry_admission_and_smm209_arithmetic_are_exact() -> None:
    gate = load_gate()
    raw_inputs, _, _ = historical_inputs(gate)
    admission = gate.strict_json(raw_inputs["geometry_admission"], "geometry admission")
    facts = gate.verify_geometry_admission(admission)
    assert facts["combined_inside_cap"] == 209
    assert facts["outside_incidence_floor"] == 529
    assert facts["outside_cell_floor"] == 133
    assert facts["total_required_cells"] == 1321
    assert facts["available_cell_cap"] == 1320
    changed = copy.deepcopy(admission)
    changed["established"]["smm_209_necessary_bound"] = False
    with pytest.raises(gate.CompositionError, match="theorem set"):
        gate.verify_geometry_admission(changed)
    changed = copy.deepcopy(admission)
    changed["established"]["unknown_theorem"] = True
    with pytest.raises(gate.CompositionError, match="key set"):
        gate.verify_geometry_admission(changed)


def test_variable_mapping_and_two_selector_opb_are_exact() -> None:
    gate = load_gate()
    raw_inputs, _, _ = historical_inputs(gate)
    mapping = gate.strict_json(raw_inputs["variable_map"], "variable map")
    assert gate.verify_variable_map(mapping) == {
        "x1": [22, 54],
        "x2": [54, 22],
        "mapping_exact": True,
    }
    formula = raw_inputs["formula"]
    parsed = gate.parse_formula(formula)
    assert parsed["exact_one"] == "+1 x1 +1 x2 = 1"
    assert parsed["forbid_x1"] == "-1 x1 >= 0"
    assert parsed["forbid_x2"] == "-1 x2 >= 0"
    changed_map = copy.deepcopy(mapping)
    changed_map["variables"][0]["height"] = 53
    with pytest.raises(gate.CompositionError, match="mapping"):
        gate.verify_variable_map(changed_map)
    for changed_formula in (
        formula.replace(b"-1 x2 >= 0 ;", b"+1 x2 >= 0 ;"),
        formula.rsplit(b"-1 x2 >= 0 ;\n", 1)[0],
    ):
        with pytest.raises(gate.CompositionError):
            gate.parse_formula(changed_formula)


def test_full7_projection_pins_reject_missing_extra_and_drift() -> None:
    gate = load_gate()
    raw_inputs, identities, pins = historical_inputs(gate)
    changed = copy.deepcopy(pins)
    changed["formula"]["content_projection"]["sha256"] = "0" * 64
    with pytest.raises(gate.IdentityContractError, match="disagrees"):
        gate.verify_composition(raw_inputs, identities, changed)
    changed = copy.deepcopy(pins)
    changed["formula"]["identity"]["extra"] = "ignored"
    with pytest.raises(gate.IdentityContractError, match="unexpected"):
        gate.verify_composition(raw_inputs, identities, changed)
    changed = copy.deepcopy(pins)
    del changed["formula"]["content_projection"]["mode_octal"]
    with pytest.raises(gate.IdentityContractError, match="missing"):
        gate.verify_composition(raw_inputs, identities, changed)
    changed_identities = copy.deepcopy(identities)
    changed_identities["formula"]["inode"] += 1
    with pytest.raises(gate.IdentityContractError, match="inode drifted"):
        gate.verify_composition(raw_inputs, changed_identities, pins)
    changed_identities = copy.deepcopy(identities)
    changed_identities["formula"]["path"] += ".alias"
    with pytest.raises(gate.IdentityContractError, match="path drifted"):
        gate.verify_composition(raw_inputs, changed_identities, pins)


def test_historical_content_anchor_cannot_be_replaced_by_self_consistent_pin() -> None:
    gate = load_gate()
    raw_inputs, identities, pins = historical_inputs(gate)
    changed_raw = dict(raw_inputs)
    changed_raw["formula"] = raw_inputs["formula"].replace(b"-1 x2 >= 0 ;", b"+1 x2 >= 0 ;")
    changed_identities = copy.deepcopy(identities)
    changed_identities["formula"]["size_bytes"] = len(changed_raw["formula"])
    changed_identities["formula"]["sha256"] = gate.sha256(changed_raw["formula"])
    changed_pins = copy.deepcopy(pins)
    changed_pins["formula"] = {
        "identity": changed_identities["formula"],
        "content_projection": gate.canonical_content_projection(changed_identities["formula"], "formula"),
    }
    with pytest.raises(gate.CompositionError, match="historical content anchor"):
        gate.verify_composition(changed_raw, changed_identities, changed_pins)


def test_pins_schema_and_cli_output_are_no_overwrite(tmp_path: Path) -> None:
    gate = load_gate()
    require_history()
    copied_paths = {}
    raw_inputs = {}
    identities = {}
    pin_inputs = {}
    for name, source in HISTORICAL_PATHS.items():
        target = tmp_path / source.name
        if target in copied_paths.values():
            target = tmp_path / f"{name}-{source.name}"
        shutil.copyfile(source, target)
        target.chmod(0o644)
        copied_paths[name] = target
        raw_inputs[name], identities[name] = gate.snapshot_regular(target, name)
        pin_inputs[name] = {
            "identity": identities[name],
            "content_projection": gate.canonical_content_projection(identities[name], name),
        }
    pins_path = tmp_path / "composition-pins.json"
    pins_path.write_bytes(
        gate.json_bytes(
            {
                "schema_version": gate.PINS_SCHEMA,
                "inputs": pin_inputs,
            }
        )
    )
    output = tmp_path / "composition-gate.json"
    arguments = [
        "--pins",
        str(pins_path),
        "--old-r4-receipt",
        str(copied_paths["old_r4_receipt"]),
        "--geometry-admission",
        str(copied_paths["geometry_admission"]),
        "--strict-instance",
        str(copied_paths["strict_instance"]),
        "--formula",
        str(copied_paths["formula"]),
        "--variable-map",
        str(copied_paths["variable_map"]),
        "--output",
        str(output),
    ]
    assert gate.main(arguments) == 0
    report = json.loads(output.read_bytes())
    assert report["formal_attempt_admitted"] is True
    assert report["upper_bound_update_authorized"] is False
    assert gate.main(arguments) == 2


def test_pins_parser_rejects_unknown_inputs_and_duplicate_json_keys() -> None:
    gate = load_gate()
    _, identities, pin_inputs = historical_inputs(gate)
    payload = {
        "schema_version": gate.PINS_SCHEMA,
        "inputs": pin_inputs,
    }
    assert set(gate.parse_pins(gate.json_bytes(payload))) == set(gate.INPUT_NAMES)
    changed = copy.deepcopy(payload)
    changed["inputs"]["unknown"] = changed["inputs"]["formula"]
    with pytest.raises(gate.CompositionError, match="key set"):
        gate.parse_pins(gate.json_bytes(changed))
    with pytest.raises(gate.CompositionError, match="duplicate JSON key"):
        gate.parse_pins(b'{"schema_version":"x","schema_version":"y","inputs":{}}')
    assert identities["formula"]["link_count"] == 1
