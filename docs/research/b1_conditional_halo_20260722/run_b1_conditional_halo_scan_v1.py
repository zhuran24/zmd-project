#!/usr/bin/env python3
"""Run one paired B1 conditional-halo diagnostic case fail-closed.

The control and treatment models must already pass both the per-case paired
translation gate and the 512-case translation admission.  An arm can close as
SAT only through a separately produced
``b1_conditional_halo_sat_assignment_check_v1`` record whose independent
checker is byte-bound here.  Otherwise the formal
fallback may establish only ``VERIFIED_UNSAT`` through the pinned
RoundingSat-to-VeriPB chain.

The runner is intentionally one paired case at a time.  It holds the common
prod-scale singleton lock while a formal child may exist, rechecks the live
disk reservation before every proof-writing arm, applies the exact
35/39/16-GiB cgroup contract, recursively manifests the run, and never imports
encoder semantics.  A low-disk preflight produces an explicit ``NO_GO``
record before checking or spawning formal tools.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import errno
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from typing import Any, BinaryIO


RUN_SCHEMA = "b1_conditional_halo_pair_run_v1"
RESOURCE_SCHEMA = "b1_conditional_halo_resource_monitor_v1"
CORPUS_SCHEMA = "b1_conditional_halo_diagnostic_corpus_v1"
GEOMETRY_ADMISSION_SCHEMA = "b1_conditional_halo_geometry_admission_v1"
MODEL_SCHEMA = "b1_conditional_halo_fixed_rectangle_model_v1"
META_SCHEMA = "b1_conditional_halo_fixed_rectangle_metadata_v1"
VAR_MAP_SCHEMA = "b1_conditional_halo_fixed_rectangle_var_map_v1"
TRANSLATION_GATE_SCHEMA = "b1_conditional_halo_translation_gate_v1"
TRANSLATION_ADMISSION_SCHEMA = "b1_conditional_halo_translation_admission_v1"
CHECKED_SAT_SCHEMA = "b1_conditional_halo_sat_assignment_check_v1"

FORMAL_PROOF_LIMIT_BYTES = 5_000_000_000
FORMAL_MIN_FREE_BYTES = 10_737_418_240
FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES = FORMAL_PROOF_LIMIT_BYTES + FORMAL_MIN_FREE_BYTES
FORMAL_SOLVER_TIME_LIMIT_SECONDS = 3_600.0
FORMAL_SOLVER_WALL_TIMEOUT_SECONDS = 3_900.0
FORMAL_VERIFIER_WALL_TIMEOUT_SECONDS = 3_600.0
FORMAL_MONITOR_INTERVAL_SECONDS = 1.0

EXPECTED_MEMORY_HIGH = 35 * 1024**3
EXPECTED_MEMORY_MAX = 39 * 1024**3
EXPECTED_SWAP_MAX = 16 * 1024**3
EXPECTED_OOM_POLICY = "continue"
EXPECTED_KILL_MODE = "control-group"
EXPECTED_SEND_SIGKILL = "yes"

EXPECTED_PYTHON_PATH = Path("/home/zhuran24/zmd-pj-codex/.venv-uvbolt-backup/bin/python3.13")
EXPECTED_ROUNDINGSAT_PATH = Path("/home/zhuran24/tools/roundingsat/build/roundingsat")
EXPECTED_ROUNDINGSAT_REPO = Path("/home/zhuran24/tools/roundingsat")
EXPECTED_ROUNDINGSAT_SHA256 = "08bb2542bcf09d99366f35e6fcfc7c79e002eca360ab9da027944c719fa3f8bf"
EXPECTED_ROUNDINGSAT_REVISION = "d4edbf7908a9bb951fd181940919e0f3ac7ab1ee"
EXPECTED_VERIPB_PATH = Path("/home/zhuran24/.cargo/bin/veripb")
EXPECTED_VERIPB_SHA256 = "a0c72df075b924af3b698ae808f86d3b55067168534397a0cc3d49594777b971"
EXPECTED_VERIPB_VERSION = "3.0.2"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = PROJECT_ROOT / ".artifacts" / "track_b_b1_conditional_halo_20260722"
SINGLETON_LOCK_NAME = "zmd_pj_prod_scale_solver.lock"
MANIFEST_NAME = "SHA256SUMS.recursive"
RUN_RECORD_NAME = "pair_run.json"
SAT_CHECKER_NAME = "check_b1_conditional_halo_sat_assignment_v1.py"
UNCHANGED_BOUND = [1190, 34]

ERROR_MARKER = re.compile(
    r"(?:^|\b)(?:error|fatal|exception|traceback|panic|panicked|failed|unsupported|"
    r"verification failed|checking error|invalid proof)(?:\b|:)",
    re.IGNORECASE,
)
OOM_EVENT_KEYS = frozenset({"oom", "oom_kill", "oom_group_kill"})


class ScanError(RuntimeError):
    """A paired-run input, resource, or execution contract failed closed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise ScanError("invalid_json", f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise ScanError("invalid_json", f"non-finite JSON number forbidden: {value}")


def _load(path: Path, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(
            path.resolve(strict=True).read_text(encoding="utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_constant,
        )
    except ScanError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ScanError("invalid_json", f"cannot load {label}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ScanError("invalid_json", f"{label} root must be an object")
    return payload


def _array(value: Any, label: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ScanError("schema_mismatch", f"{label} must be an array")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _record(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ScanError("missing_input", f"not a regular provenance file: {resolved}")
    return {
        "path": _display(resolved, root),
        "sha256": _sha256(resolved),
        "size_bytes": resolved.stat().st_size,
    }


def _record_path(value: Any, root: Path, label: str) -> Path:
    if not isinstance(value, Mapping) or set(value) != {"path", "sha256", "size_bytes"}:
        raise ScanError("provenance_mismatch", f"{label} is not an exact file record")
    raw = value.get("path")
    if type(raw) is not str or not raw:
        raise ScanError("provenance_mismatch", f"{label}.path malformed")
    candidate = Path(raw)
    path = candidate if candidate.is_absolute() else root / candidate
    try:
        actual = _record(path, root)
    except OSError as exc:
        raise ScanError("provenance_mismatch", f"cannot resolve {label}: {exc}") from exc
    if actual != dict(value):
        raise ScanError("provenance_mismatch", f"{label} is stale")
    return path.resolve(strict=True)


def _exclusive_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def _exclusive_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(payload)


def _exclusive_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def _append_jsonl(path: Path, payload: Any) -> None:
    encoded = (json.dumps(payload, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC, 0o600)
    try:
        if os.write(descriptor, encoded) != len(encoded):
            raise ScanError("telemetry_write_failure", "short telemetry write")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _pass_gate(path: Path, root: Path, schema: str, label: str) -> tuple[Mapping[str, Any], dict[str, Any]]:
    value = _load(path, label)
    checks = value.get("checks")
    if (
        value.get("schema_version") != schema
        or value.get("status") != "PASS"
        or value.get("corpus_errors") != []
        or not isinstance(checks, Mapping)
        or not checks
        or any(result is not True for result in checks.values())
    ):
        raise ScanError("gate_failure", f"{label} is not a corpus-clean all-true PASS")
    return value, _record(path, root)


def _record_occurs(value: Any, wanted: Mapping[str, Any]) -> bool:
    if isinstance(value, Mapping):
        if dict(value) == dict(wanted):
            return True
        return any(_record_occurs(child, wanted) for child in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_record_occurs(child, wanted) for child in value)
    return False


def _parse_constraint(line: str) -> str:
    match = re.fullmatch(r"\s*(.*?)\s+(=|>=)\s+(-?[0-9]+)\s*;\s*", line)
    if match is None:
        raise ScanError("opb_parse_failure", f"malformed OPB constraint: {line!r}")
    terms_raw, relation, rhs_raw = match.groups()
    tokens = terms_raw.split()
    if not tokens or len(tokens) % 2:
        raise ScanError("opb_parse_failure", "malformed OPB term list")
    terms: Counter[int] = Counter()
    for index in range(0, len(tokens), 2):
        coefficient_raw, variable_raw = tokens[index : index + 2]
        if re.fullmatch(r"[+-]?[0-9]+", coefficient_raw) is None or re.fullmatch(r"x[1-9][0-9]*", variable_raw) is None:
            raise ScanError("opb_parse_failure", "noncanonical OPB coefficient/variable token")
        terms[int(variable_raw[1:])] += int(coefficient_raw)
    canonical = tuple(sorted((variable, coefficient) for variable, coefficient in terms.items() if coefficient))
    if not canonical:
        raise ScanError("opb_parse_failure", "empty canonical OPB constraint")
    return json.dumps(
        {"terms": canonical, "relation": relation, "rhs": int(rhs_raw)},
        sort_keys=True,
        separators=(",", ":"),
    )


def _opb(path: Path) -> tuple[Counter[str], dict[str, int]]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ScanError("opb_parse_failure", f"cannot read OPB: {exc}") from exc
    if not lines:
        raise ScanError("opb_parse_failure", "empty OPB")
    header = re.fullmatch(
        r"\* #variable= ([0-9]+) #constraint= ([0-9]+) #equal= ([0-9]+) intsize= 64",
        lines[0],
    )
    if header is None:
        raise ScanError("opb_parse_failure", "OPB header is not exact")
    constraints = Counter(_parse_constraint(line) for line in lines[1:] if line and not line.startswith("*"))
    counts = {
        "variables": int(header.group(1)),
        "constraints": int(header.group(2)),
        "equal": int(header.group(3)),
    }
    if sum(constraints.values()) != counts["constraints"]:
        raise ScanError("opb_parse_failure", "OPB header constraint count mismatch")
    return constraints, counts


def _corpus(path: Path, root: Path, case_index: int) -> tuple[Mapping[str, Any], dict[str, Any], Mapping[str, Any]]:
    corpus = _load(path, "diagnostic corpus")
    cases = _array(corpus.get("cases"), "corpus.cases")
    if (
        corpus.get("schema_version") != CORPUS_SCHEMA
        or corpus.get("status") != "PASS"
        or corpus.get("manifest_state") != "BUILT_BEFORE_RESULTS"
        or corpus.get("solver_results_included") is not False
        or corpus.get("case_count") != 512
        or len(cases) != 512
        or corpus.get("corpus_errors") != []
        or not 0 <= case_index < 512
    ):
        raise ScanError("corpus_failure", "diagnostic corpus contract drifted")
    pair_ids: set[str] = set()
    transpose_groups: dict[str, set[str]] = {}
    for index, raw in enumerate(cases):
        if not isinstance(raw, Mapping):
            raise ScanError("corpus_failure", f"corpus case {index} is not an object")
        pair_id = raw.get("pair_id")
        group_id = raw.get("transpose_group_id")
        variant = raw.get("variant")
        if type(pair_id) is not str or not pair_id or pair_id in pair_ids:
            raise ScanError("corpus_failure", "corpus pair_id values are not 512 unique identities")
        if type(group_id) is not str or not group_id or variant not in {"original", "transpose"}:
            raise ScanError("corpus_failure", "corpus transpose-group identity is malformed")
        pair_ids.add(pair_id)
        transpose_groups.setdefault(group_id, set()).add(str(variant))
    if (
        len(pair_ids) != 512
        or len(transpose_groups) != 256
        or any(variants != {"original", "transpose"} for variants in transpose_groups.values())
    ):
        raise ScanError("corpus_failure", "corpus is not 512 unique pairs in 256 transpose groups")
    case = cases[case_index]
    if (
        not isinstance(case, Mapping)
        or case.get("case_index") != case_index
        or case.get("case_id") != f"case_{case_index:03d}"
    ):
        raise ScanError("corpus_failure", "selected corpus case identity/order drifted")
    return corpus, _record(path, root), case


def _geometry_admission(path: Path, root: Path) -> tuple[Mapping[str, Any], dict[str, Any]]:
    admission = _load(path, "geometry admission")
    checks = admission.get("checks")
    if not isinstance(checks, Sequence) or isinstance(checks, (str, bytes)) or not checks:
        raise ScanError("geometry_gate_failure", "geometry admission checks must be a nonempty list")
    check_ids: set[str] = set()
    for index, raw in enumerate(checks):
        if not isinstance(raw, Mapping) or set(raw) != {"id", "status"}:
            raise ScanError("geometry_gate_failure", f"geometry check {index} is malformed")
        check_id = raw.get("id")
        if type(check_id) is not str or not check_id or check_id in check_ids or raw.get("status") != "PASS":
            raise ScanError("geometry_gate_failure", f"geometry check {index} is duplicate or non-PASS")
        check_ids.add(check_id)
    halo = admission.get("conditional_halo")
    if (
        admission.get("schema_version") != GEOMETRY_ADMISSION_SCHEMA
        or admission.get("status") != "PASS"
        or admission.get("corpus_errors") != []
        or admission.get("scope") != "geometry_only_pre_encoder"
        or not isinstance(halo, Mapping)
        or halo.get("rhs_original") != 3325
        or halo.get("rhs_doubled") != 6650
        or halo.get("quantifier") != "all_selected_poles"
    ):
        raise ScanError("geometry_gate_failure", "geometry admission claim/scope drifted")
    return admission, _record(path, root)


def _metadata(
    path: Path,
    opb_path: Path,
    var_map_path: Path,
    root: Path,
    arm: str,
    case: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, Any]]:
    meta = _load(path, f"{arm} metadata")
    if (
        meta.get("schema_version") != META_SCHEMA
        or meta.get("status") != "PASS"
        or meta.get("model_schema_version") != MODEL_SCHEMA
        or meta.get("variable_map_schema_version") != VAR_MAP_SCHEMA
        or meta.get("arm") != arm
        or meta.get("model_scope") != "diagnostic_fixed_pattern"
        or meta.get("case") != dict(case)
        or meta.get("proof_status") != "build_only_no_solver_or_proof_no_sat_or_unsat_claim"
    ):
        raise ScanError("schema_mismatch", f"{arm} metadata contract drifted")
    outputs = meta.get("outputs")
    if not isinstance(outputs, Mapping) or set(outputs) != {"opb", "var_map", "metadata"}:
        raise ScanError("provenance_mismatch", f"{arm} metadata output set drifted")
    if outputs.get("opb") != _record(opb_path, root) or outputs.get("var_map") != _record(var_map_path, root):
        raise ScanError("provenance_mismatch", f"{arm} metadata output records are stale")
    self_record = outputs.get("metadata")
    if not isinstance(self_record, Mapping) or set(self_record) != {"path"}:
        raise ScanError("provenance_mismatch", f"{arm} metadata self record malformed")
    raw_self_path = self_record.get("path")
    if type(raw_self_path) is not str:
        raise ScanError("provenance_mismatch", f"{arm} metadata self path malformed")
    self_path = Path(raw_self_path)
    if not self_path.is_absolute():
        self_path = root / self_path
    if self_path.resolve(strict=True) != path.resolve(strict=True):
        raise ScanError("provenance_mismatch", f"{arm} metadata self path mismatch")
    paired = meta.get("paired_diff")
    if not isinstance(paired, Mapping) or dict(paired) != {
        "conditional_halo_rhs2": 6650,
        "control_to_treatment": "append exactly one conditional_halo constraint",
        "prepruning_by_halo": False,
    }:
        raise ScanError("paired_attribution_failure", f"{arm} metadata paired-diff contract drifted")
    return meta, _record(path, root)


def _var_map(path: Path, case: Mapping[str, Any]) -> tuple[Mapping[str, Any], str]:
    value = _load(path, "variable map")
    paired = value.get("paired_generation_sha256")
    if (
        value.get("schema_version") != VAR_MAP_SCHEMA
        or value.get("status") != "PASS"
        or value.get("model_schema_version") != MODEL_SCHEMA
        or value.get("model_scope") != "diagnostic_fixed_pattern"
        or value.get("strict_instance_sha256") != "e08a163336edf73e1b5c866034a73662a98870bbcd90a8bba4e8f7b32fca849c"
        or value.get("case") != dict(case)
        or value.get("variable_count") != 4841
        or type(paired) is not str
        or re.fullmatch(r"[0-9a-f]{64}", paired) is None
    ):
        raise ScanError("schema_mismatch", "variable-map contract drifted")
    variables = _array(value.get("variables"), "variable_map.variables")
    if len(variables) != 4841:
        raise ScanError("schema_mismatch", "variable map is not dense")
    return value, str(paired)


def _translation_admission(
    path: Path,
    root: Path,
    case_index: int,
    case: Mapping[str, Any],
    paired_sha: str,
    corpus_record: Mapping[str, Any],
    geometry_record: Mapping[str, Any],
    gate_record: Mapping[str, Any],
    paired_records: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Any], dict[str, Any]]:
    admission, record = _pass_gate(path, root, TRANSLATION_ADMISSION_SCHEMA, "translation admission")
    if (
        admission.get("case_index") != case_index
        or admission.get("case_id") != case.get("case_id")
        or admission.get("pair_id") != case.get("pair_id")
        or admission.get("transpose_group_id") != case.get("transpose_group_id")
        or admission.get("model_scope") != "diagnostic_fixed_pattern"
        or admission.get("paired_generation_sha256") != paired_sha
        or admission.get("proof_status") != "translation_admission_only_no_solver_or_proof_no_sat_or_unsat_claim"
    ):
        raise ScanError("translation_admission_failure", "translation admission pair/scope boundary drifted")
    inputs = admission.get("inputs")
    if not isinstance(inputs, Mapping) or set(inputs) != {
        "geometry_admission",
        "corpus_manifest",
        "control_opb",
        "control_metadata",
        "control_var_map",
        "treatment_opb",
        "treatment_metadata",
        "treatment_var_map",
        "translation_gate",
        "encoder_canaries",
    }:
        raise ScanError("translation_admission_failure", "translation admission input role set drifted")
    expected = {
        "geometry_admission": geometry_record,
        "corpus_manifest": corpus_record,
        "translation_gate": gate_record,
        **paired_records,
    }
    if any(inputs.get(role) != wanted for role, wanted in expected.items()):
        raise ScanError("translation_admission_failure", "translation admission paired input binding drifted")
    _record_path(inputs.get("encoder_canaries"), root, "translation_admission.inputs.encoder_canaries")
    return admission, record


def _paired_gate(
    path: Path,
    root: Path,
    case_index: int,
    case: Mapping[str, Any],
    paired_sha: str,
    expected_inputs: Mapping[str, Mapping[str, Any]],
    added_constraint: str,
) -> tuple[Mapping[str, Any], dict[str, Any]]:
    gate, record = _pass_gate(path, root, TRANSLATION_GATE_SCHEMA, "paired translation gate")
    gate_case = {
        key: case[key]
        for key in (
            "w",
            "h",
            "x",
            "y",
            "delta",
            "a_delta",
            "e_delta",
            "canonical_utf8",
            "rank_hash_sha256",
            "case_index",
            "case_id",
            "pair_id",
            "transpose_group_id",
            "base_rank",
            "variant",
        )
    }
    if (
        gate.get("case_index") != case_index
        or gate.get("model_scope") != "diagnostic_fixed_pattern"
        or gate.get("case") != gate_case
        or gate.get("paired_generation_sha256") != paired_sha
        or gate.get("inputs") != dict(expected_inputs)
        or gate.get("missing") != []
        or gate.get("unexpected") != []
    ):
        raise ScanError("translation_gate_failure", "paired translation gate identity/input closure drifted")
    paired_diff = gate.get("paired_diff")
    if not isinstance(paired_diff, Mapping) or dict(paired_diff) != {
        "added": [added_constraint],
        "exactly_one_conditional_halo": True,
        "removed": [],
    }:
        raise ScanError("paired_attribution_failure", "translation gate does not attest the exact one-row diff")
    proof_status = gate.get("proof_status")
    if type(proof_status) is not str or "no_solver" not in proof_status or "no" not in proof_status:
        raise ScanError("translation_gate_failure", "translation gate proof-status boundary drifted")
    return gate, record


def _validate_inputs(args: argparse.Namespace) -> dict[str, Any]:
    root = args.project_root.resolve(strict=True)
    if root != PROJECT_ROOT.resolve(strict=True):
        raise ScanError("project_root_mismatch", "--project-root must identify this isolated worktree")
    raw_paths = {
        "corpus": args.corpus,
        "geometry_admission": args.geometry_admission,
        "translation_admission": args.translation_admission,
        "translation_gate": args.translation_gate,
        "control_opb": args.control_opb,
        "control_metadata": args.control_meta,
        "control_var_map": args.control_var_map,
        "treatment_opb": args.treatment_opb,
        "treatment_metadata": args.treatment_meta,
        "treatment_var_map": args.treatment_var_map,
    }
    try:
        paths = {key: value.resolve(strict=True) for key, value in raw_paths.items()}
    except OSError as exc:
        raise ScanError("missing_input", f"cannot resolve paired input: {exc}") from exc
    if any(not path.is_file() for path in paths.values()):
        raise ScanError("missing_input", "every paired input must be a regular file")
    _, corpus_record, case = _corpus(paths["corpus"], root, args.case_index)
    _, geometry_record = _geometry_admission(paths["geometry_admission"], root)
    control_map, control_sha = _var_map(paths["control_var_map"], case)
    treatment_map, treatment_sha = _var_map(paths["treatment_var_map"], case)
    if control_sha != treatment_sha or control_map != treatment_map:
        raise ScanError("paired_attribution_failure", "control/treatment variable maps are not identical")
    control_meta, control_meta_record = _metadata(
        paths["control_metadata"], paths["control_opb"], paths["control_var_map"], root, "control", case
    )
    treatment_meta, treatment_meta_record = _metadata(
        paths["treatment_metadata"], paths["treatment_opb"], paths["treatment_var_map"], root, "treatment", case
    )
    if (
        control_meta.get("paired_generation_sha256") != control_sha
        or treatment_meta.get("paired_generation_sha256") != control_sha
    ):
        raise ScanError("paired_attribution_failure", "metadata paired-generation identity mismatch")
    control_constraints, control_header = _opb(paths["control_opb"])
    treatment_constraints, treatment_header = _opb(paths["treatment_opb"])
    added = treatment_constraints - control_constraints
    removed = control_constraints - treatment_constraints
    if sum(added.values()) != 1 or removed or treatment_header["constraints"] != control_header["constraints"] + 1:
        raise ScanError("paired_attribution_failure", "parsed OPBs do not differ by exactly one treatment row")
    added_constraint = next(iter(added))
    decoded_added = json.loads(added_constraint)
    if (
        decoded_added.get("relation") != ">="
        or decoded_added.get("rhs") != 6650
        or any(coefficient <= 0 for _, coefficient in decoded_added.get("terms", []))
    ):
        raise ScanError("paired_attribution_failure", "the sole treatment row is not the positive 6650 halo row")
    provisional_inputs = {
        "geometry_admission": geometry_record,
        "corpus_manifest": corpus_record,
        "control_opb": _record(paths["control_opb"], root),
        "control_metadata": control_meta_record,
        "control_var_map": _record(paths["control_var_map"], root),
        "treatment_opb": _record(paths["treatment_opb"], root),
        "treatment_metadata": treatment_meta_record,
        "treatment_var_map": _record(paths["treatment_var_map"], root),
    }
    gate_probe = _load(paths["translation_gate"], "paired translation gate")
    gate_inputs = gate_probe.get("inputs")
    if not isinstance(gate_inputs, Mapping):
        raise ScanError("translation_gate_failure", "paired translation gate input map is missing")
    for inherited_role in ("stencil", "r1_translation_gate"):
        inherited = gate_inputs.get(inherited_role)
        _record_path(inherited, root, f"translation_gate.inputs.{inherited_role}")
        provisional_inputs[inherited_role] = dict(inherited)
    gate, gate_record = _paired_gate(
        paths["translation_gate"],
        root,
        args.case_index,
        case,
        control_sha,
        provisional_inputs,
        added_constraint,
    )
    _, admission_record = _translation_admission(
        paths["translation_admission"],
        root,
        args.case_index,
        case,
        control_sha,
        corpus_record,
        geometry_record,
        gate_record,
        {
            role: provisional_inputs[role]
            for role in (
                "control_opb",
                "control_metadata",
                "control_var_map",
                "treatment_opb",
                "treatment_metadata",
                "treatment_var_map",
            )
        },
    )
    return {
        "root": root,
        "paths": paths,
        "case": dict(case),
        "case_index": args.case_index,
        "case_id": case["case_id"],
        "pair_id": case["pair_id"],
        "transpose_group_id": case["transpose_group_id"],
        "paired_generation_sha256": control_sha,
        "records": {
            **provisional_inputs,
            "translation_gate": gate_record,
            "translation_admission": admission_record,
        },
        "gate": gate,
        "added_constraint": added_constraint,
        "headers": {"control": control_header, "treatment": treatment_header},
    }


def _validate_checked_sat(
    path: Path,
    arm: str,
    context: Mapping[str, Any],
) -> tuple[Mapping[str, Any], dict[str, Any], dict[str, Path]]:
    root = context["root"]
    value = _load(path, f"{arm} checked-SAT record")
    expected_model = {
        "opb": context["records"][f"{arm}_opb"],
        "metadata": context["records"][f"{arm}_metadata"],
        "var_map": context["records"][f"{arm}_var_map"],
    }
    semantic = value.get("semantic_checks")
    if (
        value.get("schema_version") != CHECKED_SAT_SCHEMA
        or value.get("status") != "PASS"
        or value.get("assignment_status") != "CHECKED_SAT"
        or value.get("arm") != arm
        or value.get("model_scope") != "diagnostic_fixed_pattern"
        or value.get("case_index") != context["case_index"]
        or value.get("paired_generation_sha256") != context["paired_generation_sha256"]
        or value.get("model") != expected_model
        or not isinstance(semantic, Mapping)
        or set(semantic)
        != {
            "full_original_variables",
            "selected_delta",
            "selected_count",
            "actual_p",
            "r1_count_lhs",
            "pole_rectangle_conflicts",
            "pole_pair_overlaps",
            "pattern_pole_conflicts",
            "halo_lhs2",
            "halo_rhs2",
        }
        or semantic.get("full_original_variables") != 4841
        or type(semantic.get("selected_delta")) is not int
        or not 0 <= semantic["selected_delta"] < 47
        or type(semantic.get("selected_count")) is not int
        or semantic.get("selected_count") != semantic.get("actual_p")
        or not 9 <= semantic["actual_p"] <= 41
        or type(semantic.get("r1_count_lhs")) is not int
        or semantic["r1_count_lhs"] > 1320
        or any(
            semantic.get(key) != 0
            for key in ("pole_rectangle_conflicts", "pole_pair_overlaps", "pattern_pole_conflicts")
        )
        or type(semantic.get("halo_lhs2")) is not int
        or (arm == "treatment" and (semantic.get("halo_rhs2") != 6650 or semantic["halo_lhs2"] < 6650))
        or (arm == "control" and semantic.get("halo_rhs2") is not None)
    ):
        raise ScanError("checked_sat_failure", f"{arm} checked-SAT contract is not an exact all-true PASS")
    bound_paths = {
        "assignment": _record_path(value.get("assignment"), root, f"{arm} checked_sat.assignment"),
        "checker": _record_path(value.get("checker_source"), root, f"{arm} checked_sat.checker_source"),
    }
    expected_checker = Path(__file__).with_name(SAT_CHECKER_NAME).resolve(strict=True)
    if bound_paths["checker"] != expected_checker or value.get("assignment_sha256") != _sha256(
        bound_paths["assignment"]
    ):
        raise ScanError("checked_sat_failure", f"{arm} checked-SAT checker/assignment binding drifted")
    if semantic.get("selected_delta") != context["case"].get("delta"):
        raise ScanError("checked_sat_failure", f"{arm} checked-SAT selected diagnostic pattern drifted")
    return value, _record(path, root), bound_paths


def _copy(
    path: Path,
    destination: Path,
    root: Path,
    expected: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Snapshot one regular file with no overwrite and an exact byte pin.

    Same-filesystem snapshots use a no-overwrite hard link to keep the fixed
    512-case corpus within its disk budget.  EXDEV falls back to an exclusive
    byte copy.  The caller must include the returned record in the protected
    manifest set; pre-seal source/copy revalidation then prevents a mutated
    hard link from being silently resealed under new bytes.
    """

    try:
        source_stat = path.lstat()
    except OSError as exc:
        raise ScanError("artifact_snapshot_failure", f"cannot stat snapshot source {path}: {exc}") from exc
    if not stat.S_ISREG(source_stat.st_mode):
        raise ScanError("artifact_snapshot_failure", f"snapshot source is not a regular file: {path}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(destination):
        raise ScanError("artifact_snapshot_failure", f"snapshot destination already exists: {destination}")
    try:
        os.link(path, destination, follow_symlinks=False)
        hard_linked = True
    except FileExistsError as exc:
        raise ScanError("artifact_snapshot_failure", f"snapshot destination already exists: {destination}") from exc
    except OSError as exc:
        if exc.errno != errno.EXDEV:
            raise ScanError("artifact_snapshot_failure", f"cannot hard-link snapshot {path}: {exc}") from exc
        hard_linked = False
        try:
            with path.open("rb") as source, destination.open("xb") as target:
                opened_stat = os.fstat(source.fileno())
                if not stat.S_ISREG(opened_stat.st_mode) or (opened_stat.st_dev, opened_stat.st_ino) != (
                    source_stat.st_dev,
                    source_stat.st_ino,
                ):
                    raise ScanError("artifact_snapshot_failure", f"snapshot source identity drifted: {path}")
                shutil.copyfileobj(source, target, length=1024 * 1024)
        except FileExistsError as copy_exc:
            raise ScanError(
                "artifact_snapshot_failure", f"snapshot destination already exists: {destination}"
            ) from copy_exc
        except ScanError:
            raise
        except OSError as copy_exc:
            raise ScanError(
                "artifact_snapshot_failure", f"cannot exclusively copy cross-device snapshot {path}: {copy_exc}"
            ) from copy_exc

    try:
        current_source_stat = path.lstat()
        destination_stat = destination.lstat()
    except OSError as exc:
        raise ScanError("artifact_snapshot_failure", f"cannot restat completed snapshot {path}: {exc}") from exc
    if (
        not stat.S_ISREG(current_source_stat.st_mode)
        or not stat.S_ISREG(destination_stat.st_mode)
        or (current_source_stat.st_dev, current_source_stat.st_ino) != (source_stat.st_dev, source_stat.st_ino)
    ):
        raise ScanError("artifact_snapshot_failure", f"snapshot file identity drifted for {path}")
    if hard_linked and (destination_stat.st_dev, destination_stat.st_ino) != (
        source_stat.st_dev,
        source_stat.st_ino,
    ):
        raise ScanError("artifact_snapshot_failure", f"same-filesystem snapshot is not a hard link: {destination}")

    record = _record(destination, root)
    source_record = _record(path, root)
    if expected is not None and source_record != dict(expected):
        raise ScanError("artifact_source_drift", f"source bytes drifted before snapshot completed: {path}")
    if (
        record["sha256"] != source_record["sha256"]
        or record["size_bytes"] != source_record["size_bytes"]
        or record["size_bytes"] != current_source_stat.st_size
    ):
        raise ScanError("artifact_copy_drift", f"copied bytes drifted for {path}")
    return record


def _snapshot_inputs(context: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    copies: dict[str, Any] = {}
    inputs_dir = output_dir / "inputs"
    root = context["root"]
    for role, expected in context["records"].items():
        path = _record_path(expected, root, f"inputs.{role}")
        suffix = "".join(path.suffixes) or ".bin"
        copies[role] = _copy(path, inputs_dir / f"{role}{suffix}", root, expected)
    return copies


def _snapshot_checked_sat(
    arm: str,
    source: Path,
    record: Mapping[str, Any],
    bound_paths: Mapping[str, Path],
    output_dir: Path,
    root: Path,
) -> dict[str, Any]:
    destination = output_dir / "arms" / arm / "checked_sat"
    source_record = _record(source, root)
    copied = {"record": _copy(source, destination / "checked_sat.json", root, source_record)}
    for role, path in bound_paths.items():
        suffix = "".join(path.suffixes) or ".bin"
        expected = record["assignment"] if role == "assignment" else record["checker_source"]
        copied[role] = _copy(path, destination / f"{role}{suffix}", root, expected)
    return {
        "source": source_record,
        "copied": copied,
        "validated_schema": record.get("schema_version"),
    }


def _same_bytes(first: Mapping[str, Any], second: Mapping[str, Any]) -> bool:
    return first.get("sha256") == second.get("sha256") and first.get("size_bytes") == second.get("size_bytes")


def _revalidate_before_manifest(
    context: Mapping[str, Any],
    copied_inputs: Mapping[str, Any],
    checked: Mapping[str, tuple[Mapping[str, Any], dict[str, Any], dict[str, Path]] | None],
    arms: Mapping[str, Any],
) -> dict[str, Any]:
    """Recheck every source and detached snapshot immediately before sealing."""

    root = context["root"]
    if set(copied_inputs) != set(context["records"]):
        raise ScanError("artifact_copy_drift", "input snapshot role set drifted before manifest seal")
    for role, expected in context["records"].items():
        _record_path(expected, root, f"pre_seal.inputs.{role}")
        copied_path = _record_path(copied_inputs[role], root, f"pre_seal.input_copies.{role}")
        if not _same_bytes(expected, _record(copied_path, root)):
            raise ScanError("artifact_copy_drift", f"input snapshot bytes drifted before seal: {role}")

    checked_roles: list[str] = []
    hard_link_roles: list[str] = []
    for role, expected in context["records"].items():
        source = _record_path(expected, root, f"pre_seal.hard_link_source.{role}")
        copied = _record_path(copied_inputs[role], root, f"pre_seal.hard_link_copy.{role}")
        if (source.stat().st_dev, source.stat().st_ino) == (copied.stat().st_dev, copied.stat().st_ino):
            hard_link_roles.append(f"input.{role}")
    for arm in ("control", "treatment"):
        initial = checked.get(arm)
        if initial is None:
            continue
        value, source_record, bound_paths = initial
        current_value, current_record, current_paths = _validate_checked_sat(
            _record_path(source_record, root, f"pre_seal.{arm}.checked_sat_source"), arm, context
        )
        if current_value != value or current_record != source_record or current_paths != bound_paths:
            raise ScanError("checked_sat_failure", f"{arm} checked-SAT source changed before seal")
        snapshot = arms.get(arm, {}).get("checked_sat")
        copied = snapshot.get("copied") if isinstance(snapshot, Mapping) else None
        if not isinstance(copied, Mapping) or set(copied) != {"record", "assignment", "checker"}:
            raise ScanError("checked_sat_failure", f"{arm} checked-SAT snapshot is incomplete")
        expected_by_role = {
            "record": source_record,
            "assignment": value["assignment"],
            "checker": value["checker_source"],
        }
        for role, expected in expected_by_role.items():
            copied_path = _record_path(copied[role], root, f"pre_seal.{arm}.copied.{role}")
            if not _same_bytes(expected, _record(copied_path, root)):
                raise ScanError("checked_sat_failure", f"{arm} copied checked-SAT {role} drifted before seal")
            checked_roles.append(f"{arm}.{role}")
            source_path = _record_path(expected, root, f"pre_seal.{arm}.source.{role}")
            if (source_path.stat().st_dev, source_path.stat().st_ino) == (
                copied_path.stat().st_dev,
                copied_path.stat().st_ino,
            ):
                hard_link_roles.append(f"{arm}.{role}")
    return {
        "status": "PASS",
        "source_input_roles": sorted(context["records"]),
        "input_copy_roles": sorted(copied_inputs),
        "checked_sat_copy_roles": checked_roles,
        "hard_link_snapshot_roles": sorted(hard_link_roles),
        "copy_strategy": "hard_link_same_filesystem_exclusive_copy_on_exdev",
    }


def _free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="ascii").strip()
    except OSError:
        return None


def _integer_map(raw: str | None) -> dict[str, int] | None:
    if raw is None:
        return None
    result: dict[str, int] = {}
    try:
        for line in raw.splitlines():
            key, value = line.split()
            result[key] = int(value)
    except (TypeError, ValueError):
        return None
    return result


def _event_deltas(before: Mapping[str, int] | None, after: Mapping[str, int] | None) -> dict[str, int] | None:
    if before is None or after is None or set(before) != set(after):
        return None
    return {key: after[key] - before[key] for key in sorted(before)}


def _proc_cgroup(pid: int) -> dict[str, Any]:
    try:
        raw = (Path("/proc") / str(pid) / "cgroup").read_text(encoding="ascii").strip()
    except OSError as exc:
        return {"pid": pid, "unified_path": None, "error": f"{type(exc).__name__}: {exc}"}
    unified = [line.split("::", 1)[1] for line in raw.splitlines() if "::" in line]
    return {"pid": pid, "raw": raw.splitlines(), "unified_path": unified[0] if len(unified) == 1 else None}


def _systemd_property(unit: str, name: str) -> dict[str, Any]:
    argv = ["systemctl", "--user", "show", unit, f"--property={name}", "--value"]
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"argv": argv, "exit_code": None, "value": None, "stderr": f"{type(exc).__name__}: {exc}"}
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "value": completed.stdout.strip() if completed.returncode == 0 else None,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _limit_allows(value: str | None, required: int) -> bool:
    return value == "max" or bool(type(value) is str and value.isdigit() and int(value) >= required)


def _cgroup_state(expected_unit: str | None, require: bool) -> dict[str, Any]:
    process = _proc_cgroup(os.getpid())
    relative = process.get("unified_path")
    directory = Path("/sys/fs/cgroup") / str(relative).lstrip("/") if isinstance(relative, str) else None
    leaf = {
        name: _read_text(directory / name) if directory is not None else None
        for name in ("memory.high", "memory.max", "memory.swap.max", "memory.current", "memory.peak")
    }
    events = _integer_map(_read_text(directory / "memory.events") if directory is not None else None)
    procs = _read_text(directory / "cgroup.procs") if directory is not None else None
    properties = {
        name: _systemd_property(expected_unit, name) if expected_unit else None
        for name in ("MemoryHigh", "MemoryMax", "MemorySwapMax", "OOMPolicy", "KillMode", "SendSIGKILL")
    }
    expected_properties = {
        "MemoryHigh": str(EXPECTED_MEMORY_HIGH),
        "MemoryMax": str(EXPECTED_MEMORY_MAX),
        "MemorySwapMax": str(EXPECTED_SWAP_MAX),
        "OOMPolicy": EXPECTED_OOM_POLICY,
        "KillMode": EXPECTED_KILL_MODE,
        "SendSIGKILL": EXPECTED_SEND_SIGKILL,
    }
    property_checks = {
        name: isinstance(properties[name], Mapping)
        and properties[name].get("exit_code") == 0
        and properties[name].get("value") == wanted
        for name, wanted in expected_properties.items()
    }
    ancestors: list[dict[str, Any]] = []
    if directory is not None:
        current = directory
        cgroup_root = Path("/sys/fs/cgroup")
        while current == cgroup_root or cgroup_root in current.parents:
            ancestors.append(
                {
                    "path": str(current),
                    "memory_high": _read_text(current / "memory.high"),
                    "memory_max": _read_text(current / "memory.max"),
                    "memory_swap_max": _read_text(current / "memory.swap.max"),
                }
            )
            if current == cgroup_root:
                break
            current = current.parent
    ancestor_ok = bool(ancestors)
    for item in ancestors:
        limits = (item["memory_high"], item["memory_max"], item["memory_swap_max"])
        if item["path"] == "/sys/fs/cgroup" and limits == (None, None, None):
            continue
        ancestor_ok = ancestor_ok and all(
            _limit_allows(value, required)
            for value, required in zip(
                limits, (EXPECTED_MEMORY_HIGH, EXPECTED_MEMORY_MAX, EXPECTED_SWAP_MAX), strict=True
            )
        )
    checks = {
        "unified_cgroup_found": isinstance(relative, str),
        "expected_unit_is_cgroup_leaf": bool(
            expected_unit and isinstance(relative, str) and Path(relative).name == expected_unit
        ),
        "memory_high_exact": leaf["memory.high"] == str(EXPECTED_MEMORY_HIGH),
        "memory_max_exact": leaf["memory.max"] == str(EXPECTED_MEMORY_MAX),
        "memory_swap_max_exact": leaf["memory.swap.max"] == str(EXPECTED_SWAP_MAX),
        "memory_events_readable": events is not None,
        "systemd_memory_high_exact": property_checks["MemoryHigh"],
        "systemd_memory_max_exact": property_checks["MemoryMax"],
        "systemd_memory_swap_max_exact": property_checks["MemorySwapMax"],
        "oom_policy_exact": property_checks["OOMPolicy"],
        "kill_mode_exact": property_checks["KillMode"],
        "send_sigkill_exact": property_checks["SendSIGKILL"],
        "ancestor_limits_allow_contract": ancestor_ok,
    }
    result = {
        "required": require,
        "expected_systemd_unit": expected_unit,
        "self": process,
        "cgroup_path": relative,
        "cgroup_directory": str(directory) if directory is not None else None,
        "leaf_values": leaf,
        "memory_events": events,
        "cgroup_procs": procs.splitlines() if procs else [],
        "ancestor_limits": ancestors,
        "systemd_properties": properties,
        "checks": checks,
        "contract_pass": bool(expected_unit) and all(checks.values()),
    }
    if require and result["contract_pass"] is not True:
        raise ScanError("resource_contract_mismatch", f"exact cgroup contract failed: {checks}")
    return result


def _git(repo: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ScanError("tool_identity_drift", f"git identity query failed: {exc}") from exc
    return completed.stdout.rstrip("\n")


def _validate_runtime(args: argparse.Namespace, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    exact = {
        "proof_limit_bytes": FORMAL_PROOF_LIMIT_BYTES,
        "min_free_bytes": FORMAL_MIN_FREE_BYTES,
        "solver_time_limit": FORMAL_SOLVER_TIME_LIMIT_SECONDS,
        "solver_wall_timeout": FORMAL_SOLVER_WALL_TIMEOUT_SECONDS,
        "verifier_wall_timeout": FORMAL_VERIFIER_WALL_TIMEOUT_SECONDS,
        "monitor_interval": FORMAL_MONITOR_INTERVAL_SECONDS,
    }
    for name, wanted in exact.items():
        value = getattr(args, name)
        if isinstance(value, float) and not math.isfinite(value):
            raise ScanError("runtime_contract_mismatch", f"{name} must be finite")
        if value != wanted:
            raise ScanError("runtime_contract_mismatch", f"{name} must equal {wanted}")
    if Path(sys.executable).resolve() != EXPECTED_PYTHON_PATH.resolve(strict=True):
        raise ScanError("runtime_contract_mismatch", f"formal scan requires {EXPECTED_PYTHON_PATH}")
    if not args.require_cgroup_contract or not args.expected_systemd_unit:
        raise ScanError("resource_contract_mismatch", "formal scan requires exact cgroup options")
    paths = {
        "roundingsat": args.roundingsat.resolve(strict=True),
        "roundingsat_repo": args.roundingsat_repo.resolve(strict=True),
        "veripb": args.veripb.resolve(strict=True),
    }
    if paths["roundingsat"] != EXPECTED_ROUNDINGSAT_PATH.resolve(strict=True):
        raise ScanError("tool_identity_drift", "RoundingSat path drifted")
    if paths["roundingsat_repo"] != EXPECTED_ROUNDINGSAT_REPO.resolve(strict=True):
        raise ScanError("tool_identity_drift", "RoundingSat repository path drifted")
    if paths["veripb"] != EXPECTED_VERIPB_PATH.resolve(strict=True):
        raise ScanError("tool_identity_drift", "VeriPB path drifted")
    for name in ("roundingsat", "veripb"):
        if not paths[name].is_file() or not os.access(paths[name], os.X_OK):
            raise ScanError("tool_identity_drift", f"{name} is not executable")
    if _sha256(paths["roundingsat"]) != EXPECTED_ROUNDINGSAT_SHA256:
        raise ScanError("tool_identity_drift", "RoundingSat SHA-256 drifted")
    if _sha256(paths["veripb"]) != EXPECTED_VERIPB_SHA256:
        raise ScanError("tool_identity_drift", "VeriPB SHA-256 drifted")
    revision = _git(paths["roundingsat_repo"], "rev-parse", "HEAD")
    dirty = _git(paths["roundingsat_repo"], "status", "--porcelain=v1", "--untracked-files=normal")
    if revision != EXPECTED_ROUNDINGSAT_REVISION or dirty:
        raise ScanError("tool_identity_drift", "RoundingSat source revision is not pinned and clean")
    tools = {
        "python": _record(Path(sys.executable), root),
        "roundingsat": {
            "file": _record(paths["roundingsat"], root),
            "repository": {"path": str(paths["roundingsat_repo"]), "revision": revision, "dirty": False},
        },
        "veripb": {"file": _record(paths["veripb"], root), "expected_version": EXPECTED_VERIPB_VERSION},
    }
    cgroup = _cgroup_state(args.expected_systemd_unit, True)
    return tools, cgroup


def _process_group_exists(group: int) -> bool:
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _terminate_group(process: subprocess.Popen[Any]) -> bool:
    if _process_group_exists(process.pid):
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    if _process_group_exists(process.pid):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return False
    return not _process_group_exists(process.pid)


def _sample(
    telemetry: Path,
    output_dir: Path,
    phase: str,
    cgroup_dir: Path,
    proof: Path | None,
    active_pid: int | None,
) -> dict[str, Any]:
    sample = {
        "schema_version": RESOURCE_SCHEMA,
        "timestamp_utc": _utc_now(),
        "monotonic_seconds": time.monotonic(),
        "phase": phase,
        "free_bytes": _free_bytes(output_dir),
        "proof_size_bytes": proof.stat().st_size if proof is not None and proof.is_file() else None,
        "active_child": _proc_cgroup(active_pid) if active_pid is not None else None,
        "cgroup": {
            "memory_current": _read_text(cgroup_dir / "memory.current"),
            "memory_peak": _read_text(cgroup_dir / "memory.peak"),
            "memory_swap_current": _read_text(cgroup_dir / "memory.swap.current"),
            "memory_swap_peak": _read_text(cgroup_dir / "memory.swap.peak"),
            "memory_events": _integer_map(_read_text(cgroup_dir / "memory.events")),
            "cgroup_procs": (_read_text(cgroup_dir / "cgroup.procs") or "").splitlines(),
        },
    }
    _append_jsonl(telemetry, sample)
    return sample


def _run_child(
    command: list[str],
    stdout_path: Path,
    stderr_path: Path,
    output_dir: Path,
    telemetry: Path,
    cgroup_path: str,
    phase: str,
    wall_timeout: float,
    monitor_interval: float,
    min_free_bytes: int,
    proof: Path | None = None,
    proof_limit_bytes: int | None = None,
) -> dict[str, Any]:
    started_utc = _utc_now()
    started_ns = time.time_ns()
    started = time.monotonic()
    reason: str | None = None
    spawn_error: str | None = None
    process: subprocess.Popen[Any] | None = None
    process_group_clean = True
    completion_procs: list[str] = []
    cgroup_dir = Path("/sys/fs/cgroup") / cgroup_path.lstrip("/")
    with (
        stdout_path.open("x", encoding="utf-8", newline="\n") as stdout,
        stderr_path.open("x", encoding="utf-8", newline="\n") as stderr,
    ):
        try:
            try:
                process = subprocess.Popen(command, stdout=stdout, stderr=stderr, text=True, start_new_session=True)
            except OSError as exc:
                spawn_error = f"{type(exc).__name__}: {exc}"
            if process is not None:
                child_cgroup = _proc_cgroup(process.pid)
                if child_cgroup.get("unified_path") != cgroup_path:
                    reason = "child_cgroup_mismatch"
                    _terminate_group(process)
                while process.poll() is None:
                    sample = _sample(telemetry, output_dir, phase, cgroup_dir, proof, process.pid)
                    elapsed = time.monotonic() - started
                    current_proof = sample["proof_size_bytes"]
                    if sample["active_child"].get("unified_path") != cgroup_path:
                        reason = "child_cgroup_mismatch_during_run"
                    elif elapsed > wall_timeout:
                        reason = "wall_timeout"
                    elif sample["free_bytes"] < min_free_bytes:
                        reason = "disk_free_below_minimum"
                    elif (
                        proof_limit_bytes is not None
                        and current_proof is not None
                        and current_proof > proof_limit_bytes
                    ):
                        reason = "proof_size_limit_exceeded"
                    if reason is not None:
                        _terminate_group(process)
                        break
                    time.sleep(min(monitor_interval, max(0.01, wall_timeout - elapsed)))
                exit_code = process.wait()
                completion = _sample(telemetry, output_dir, f"{phase}_complete", cgroup_dir, proof, process.pid)
                completion_procs = completion["cgroup"]["cgroup_procs"]
                unexpected = {pid for pid in completion_procs if pid != str(os.getpid())}
                if reason is None and unexpected:
                    reason = "child_cgroup_not_clean_at_completion"
                elif reason is None and completion["free_bytes"] < min_free_bytes:
                    reason = "disk_free_below_minimum_at_completion"
                elif (
                    reason is None
                    and proof_limit_bytes is not None
                    and completion["proof_size_bytes"] is not None
                    and completion["proof_size_bytes"] > proof_limit_bytes
                ):
                    reason = "proof_size_limit_exceeded_at_completion"
            else:
                exit_code = None
                child_cgroup = None
        finally:
            if process is not None and _process_group_exists(process.pid):
                process_group_clean = _terminate_group(process)
    return {
        "argv": command,
        "started_at_utc": started_utc,
        "started_wall_time_ns": started_ns,
        "finished_at_utc": _utc_now(),
        "finished_wall_time_ns": time.time_ns(),
        "elapsed_seconds": time.monotonic() - started,
        "exit_code": exit_code,
        "termination_reason": reason,
        "timed_out": reason == "wall_timeout",
        "spawn_error": spawn_error,
        "child_cgroup": child_cgroup,
        "completion_cgroup_procs": completion_procs,
        "process_group_clean": process_group_clean,
        "stdout": _record(stdout_path, PROJECT_ROOT),
        "stderr": _record(stderr_path, PROJECT_ROOT),
    }


def _status_lines(*paths: Path) -> list[str]:
    result: list[str] = []
    for path in paths:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("s "):
                result.append(line.strip())
    return result


def _stdout_status_exact(stdout_path: Path, stderr_path: Path, expected: str) -> bool:
    return _status_lines(stdout_path) == [expected] and _status_lines(stderr_path) == []


def _error_markers(*paths: Path) -> list[str]:
    return [
        line.strip()
        for path in paths
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if ERROR_MARKER.search(line)
    ]


def _proof_tail(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        return {"nonempty": False, "complete": False, "conclusion_line": None, "end_line": None}
    with path.open("rb") as handle:
        handle.seek(max(0, path.stat().st_size - 65_536))
        lines = handle.read().decode("utf-8", errors="replace").splitlines()
    while lines and not lines[-1]:
        lines.pop()
    conclusion = lines[-2] if len(lines) >= 2 else None
    end = lines[-1] if lines else None
    return {
        "nonempty": True,
        "complete": bool(
            conclusion is not None
            and re.fullmatch(r"conclusion UNSAT : [1-9][0-9]*", conclusion)
            and end == "end pseudo-Boolean proof"
        ),
        "conclusion_line": conclusion,
        "end_line": end,
    }


def _formal_arm(
    arm: str,
    formula: Path,
    args: argparse.Namespace,
    context: Mapping[str, Any],
    output_dir: Path,
    tools: Mapping[str, Any],
    cgroup: Mapping[str, Any],
) -> dict[str, Any]:
    arm_dir = output_dir / "arms" / arm / "formal"
    arm_dir.mkdir(parents=True, exist_ok=False)
    telemetry = arm_dir / "resource_monitor.jsonl"
    proof = arm_dir / "roundingsat.proof.pbp"
    solver_stdout = arm_dir / "roundingsat.stdout.txt"
    solver_stderr = arm_dir / "roundingsat.stderr.txt"
    verifier_stdout = arm_dir / "veripb.stdout.txt"
    verifier_stderr = arm_dir / "veripb.stderr.txt"
    version_stdout = arm_dir / "veripb.version.stdout.txt"
    version_stderr = arm_dir / "veripb.version.stderr.txt"
    disk_before = _free_bytes(output_dir)
    if disk_before < FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES:
        return {
            "arm": arm,
            "paired_generation_sha256": context["paired_generation_sha256"],
            "terminal_status": "NO_GO",
            "disk_gate": {
                "decision": "NO_GO",
                "free_bytes": disk_before,
                "required_free_bytes": FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES,
                "proof_cap_bytes": FORMAL_PROOF_LIMIT_BYTES,
                "low_water_bytes": FORMAL_MIN_FREE_BYTES,
                "solver_spawned": False,
            },
            "failure_codes": ["disk_low_water_before_arm"],
            "claim": "none",
        }
    cgroup_path = cgroup.get("cgroup_path")
    if type(cgroup_path) is not str:
        raise ScanError("resource_contract_mismatch", "formal cgroup path missing")
    version = _run_child(
        [str(args.veripb.resolve(strict=True)), "--version"],
        version_stdout,
        version_stderr,
        output_dir,
        telemetry,
        cgroup_path,
        f"{arm}_veripb_version",
        30.0,
        args.monitor_interval,
        args.min_free_bytes,
    )
    version_ok = bool(
        version.get("exit_code") == 0
        and version.get("termination_reason") is None
        and version.get("process_group_clean") is True
        and version_stdout.read_text(encoding="utf-8").splitlines()
        == [f"Running VeriPB version {EXPECTED_VERIPB_VERSION}", f"veripb {EXPECTED_VERIPB_VERSION}"]
        and not version_stderr.read_text(encoding="utf-8")
    )
    if not version_ok:
        _exclusive_text(solver_stdout, "")
        _exclusive_text(solver_stderr, "")
        _exclusive_text(verifier_stdout, "")
        _exclusive_text(verifier_stderr, "")
        return {
            "arm": arm,
            "paired_generation_sha256": context["paired_generation_sha256"],
            "terminal_status": "ERROR",
            "disk_gate": {
                "decision": "GO",
                "free_bytes": disk_before,
                "required_free_bytes": FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES,
            },
            "tools": tools,
            "veripb_version": version,
            "failure_codes": ["veripb_version_mismatch"],
            "claim": "none",
        }
    formula_hash_before = _sha256(formula)
    solver = _run_child(
        [
            str(args.roundingsat.resolve(strict=True)),
            f"--proof-log={proof}",
            f"--time-limit={args.solver_time_limit:g}",
            str(formula),
        ],
        solver_stdout,
        solver_stderr,
        output_dir,
        telemetry,
        cgroup_path,
        f"{arm}_roundingsat",
        args.solver_wall_timeout,
        args.monitor_interval,
        args.min_free_bytes,
        proof,
        args.proof_limit_bytes,
    )
    statuses = _status_lines(solver_stdout, solver_stderr)
    errors = _error_markers(solver_stdout, solver_stderr)
    solver_clean = bool(
        solver.get("exit_code") in {0, 1}
        and solver.get("termination_reason") is None
        and solver.get("process_group_clean") is True
        and not errors
        and _sha256(formula) == formula_hash_before
    )
    if _stdout_status_exact(solver_stdout, solver_stderr, "s SATISFIABLE") and solver_clean:
        _exclusive_text(verifier_stdout, "")
        _exclusive_text(verifier_stderr, "")
        return {
            "arm": arm,
            "paired_generation_sha256": context["paired_generation_sha256"],
            "terminal_status": "SAT_UNCHECKED",
            "disk_gate": {
                "decision": "GO",
                "free_bytes": disk_before,
                "required_free_bytes": FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES,
            },
            "solver": solver,
            "solver_status_lines": statuses,
            "solver_error_markers": errors,
            "veripb_version": version,
            "failure_codes": ["formal_sat_requires_independent_checked_sat_record"],
            "claim": "none",
        }
    tail = _proof_tail(proof)
    proof_fresh = bool(proof.is_file() and proof.stat().st_mtime_ns >= solver["started_wall_time_ns"])
    if (
        not _stdout_status_exact(solver_stdout, solver_stderr, "s UNSATISFIABLE")
        or not solver_clean
        or not tail["complete"]
        or not proof_fresh
    ):
        _exclusive_text(verifier_stdout, "")
        _exclusive_text(verifier_stderr, "")
        return {
            "arm": arm,
            "paired_generation_sha256": context["paired_generation_sha256"],
            "terminal_status": "UNKNOWN",
            "disk_gate": {
                "decision": "GO",
                "free_bytes": disk_before,
                "required_free_bytes": FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES,
            },
            "solver": solver,
            "solver_status_lines": statuses,
            "solver_error_markers": errors,
            "proof_tail": tail,
            "proof_fresh": proof_fresh,
            "veripb_version": version,
            "failure_codes": ["solver_did_not_produce_fresh_complete_unsat_proof"],
            "claim": "none",
        }
    proof_hash_before = _sha256(proof)
    verifier = _run_child(
        [str(args.veripb.resolve(strict=True)), "--opb", "--stats", str(formula), str(proof)],
        verifier_stdout,
        verifier_stderr,
        output_dir,
        telemetry,
        cgroup_path,
        f"{arm}_veripb",
        args.verifier_wall_timeout,
        args.monitor_interval,
        args.min_free_bytes,
        proof,
        args.proof_limit_bytes,
    )
    verifier_statuses = _status_lines(verifier_stdout, verifier_stderr)
    verifier_errors = _error_markers(verifier_stdout, verifier_stderr)
    verified = bool(
        verifier.get("exit_code") == 0
        and verifier.get("termination_reason") is None
        and verifier.get("process_group_clean") is True
        and _stdout_status_exact(verifier_stdout, verifier_stderr, "s VERIFIED UNSATISFIABLE")
        and not verifier_errors
        and _sha256(formula) == formula_hash_before
        and _sha256(proof) == proof_hash_before
        and proof.stat().st_size <= args.proof_limit_bytes
        and _free_bytes(output_dir) >= args.min_free_bytes
    )
    return {
        "arm": arm,
        "paired_generation_sha256": context["paired_generation_sha256"],
        "terminal_status": "VERIFIED_UNSAT" if verified else "UNKNOWN",
        "disk_gate": {
            "decision": "GO",
            "free_bytes": disk_before,
            "required_free_bytes": FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES,
        },
        "solver": solver,
        "solver_status_lines": statuses,
        "solver_error_markers": errors,
        "proof": _record(proof, context["root"]),
        "proof_tail": tail,
        "proof_fresh": proof_fresh,
        "verifier": verifier,
        "verifier_status_lines": verifier_statuses,
        "verifier_error_markers": verifier_errors,
        "veripb_version": version,
        "hash_stability": {
            "formula": _sha256(formula) == formula_hash_before,
            "proof": _sha256(proof) == proof_hash_before,
        },
        "failure_codes": [] if verified else ["veripb_did_not_verify_unsat"],
        "claim": "given_relaxed_fixed_geometry_model_unsat" if verified else "none",
    }


def _attribution(control: str, treatment: str) -> tuple[str, str]:
    if (control, treatment) == ("CHECKED_SAT", "CHECKED_SAT"):
        return "treatment_survivor", "COMPLETE"
    if (control, treatment) == ("CHECKED_SAT", "VERIFIED_UNSAT"):
        return "halo_pruned", "COMPLETE"
    if (control, treatment) == ("VERIFIED_UNSAT", "VERIFIED_UNSAT"):
        return "control_pruned", "COMPLETE"
    if (control, treatment) == ("VERIFIED_UNSAT", "CHECKED_SAT"):
        return "monotonicity_contradiction", "FAIL"
    return "incomplete", "INCOMPLETE"


def _manifest(
    output_dir: Path,
    root: Path,
    protected_records: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    exclusions = {MANIFEST_NAME, RUN_RECORD_NAME}
    entries: dict[str, str] = {}
    for path in sorted(output_dir.rglob("*"), key=lambda item: item.relative_to(output_dir).as_posix()):
        relative = path.relative_to(output_dir).as_posix()
        pure = PurePosixPath(relative)
        if path.is_symlink():
            raise ScanError("artifact_manifest_failure", f"symlink forbidden: {relative}")
        if path.is_dir():
            continue
        if not path.is_file() or relative != pure.as_posix() or any(part in {"", ".", ".."} for part in pure.parts):
            raise ScanError("artifact_manifest_failure", f"non-regular/unsafe artifact: {relative}")
        if relative not in exclusions:
            entries[relative] = _sha256(path)
    if not entries:
        raise ScanError("artifact_manifest_failure", "recursive manifest is empty")
    protected_paths: list[tuple[str, Path, Mapping[str, Any]]] = []
    for index, expected in enumerate(protected_records):
        if not isinstance(expected, Mapping) or set(expected) != {"path", "sha256", "size_bytes"}:
            raise ScanError("artifact_manifest_failure", f"protected_snapshot[{index}] record malformed")
        raw = expected.get("path")
        if type(raw) is not str or not raw:
            raise ScanError("artifact_manifest_failure", f"protected_snapshot[{index}].path malformed")
        candidate = Path(raw)
        protected = (candidate if candidate.is_absolute() else root / candidate).resolve(strict=True)
        try:
            relative = protected.relative_to(output_dir).as_posix()
        except ValueError as exc:
            raise ScanError("artifact_manifest_failure", "protected snapshot escaped run directory") from exc
        if (
            relative not in entries
            or entries[relative] != expected.get("sha256")
            or protected.stat().st_size != expected.get("size_bytes")
        ):
            raise ScanError("artifact_copy_drift", f"protected snapshot changed while sealing: {relative}")
        protected_paths.append((relative, protected, expected))
    manifest_path = output_dir / MANIFEST_NAME
    _exclusive_text(manifest_path, "".join(f"{entries[name]}  {name}\n" for name in sorted(entries)))
    for relative, protected, expected in protected_paths:
        if _sha256(protected) != expected.get("sha256") or protected.stat().st_size != expected.get("size_bytes"):
            raise ScanError("artifact_copy_drift", f"protected snapshot changed after manifest write: {relative}")
    return {
        "file": _record(manifest_path, root),
        "entries": entries,
        "covered_files": sorted(entries),
        "excluded_to_avoid_hash_cycle": sorted(exclusions),
        "recursive": True,
    }


def _lock() -> tuple[BinaryIO, Path]:
    runtime_dir = Path("/run/user") / str(os.getuid())
    if not runtime_dir.is_dir():
        raise ScanError("singleton_lock_failure", f"runtime lock directory missing: {runtime_dir}")
    path = runtime_dir / SINGLETON_LOCK_NAME
    handle = path.open("a+b")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise ScanError("prod_scale_already_running", "another prod-scale solver owns the singleton lock") from exc
    return handle, path


def _arm_not_run(arm: str, context: Mapping[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        "arm": arm,
        "paired_generation_sha256": context["paired_generation_sha256"],
        "terminal_status": status,
        "failure_codes": [reason],
        "claim": "none",
    }


def _execute(
    args: argparse.Namespace, context: Mapping[str, Any], output_dir: Path, argv: list[str]
) -> tuple[dict[str, Any], int]:
    root = context["root"]
    copied_inputs = _snapshot_inputs(context, output_dir)
    checked: dict[str, tuple[Mapping[str, Any], dict[str, Any], dict[str, Path]] | None] = {}
    for arm, path in (("control", args.control_checked_sat), ("treatment", args.treatment_checked_sat)):
        checked[arm] = _validate_checked_sat(path.resolve(strict=True), arm, context) if path is not None else None
    arms: dict[str, Any] = {}
    for arm in ("control", "treatment"):
        if checked[arm] is not None:
            value, source_record, bound_paths = checked[arm]
            snapshot = _snapshot_checked_sat(
                arm, getattr(args, f"{arm}_checked_sat").resolve(strict=True), value, bound_paths, output_dir, root
            )
            if snapshot["source"] != source_record:
                raise ScanError("checked_sat_failure", f"{arm} checked-SAT source record drifted")
            arms[arm] = {
                "arm": arm,
                "paired_generation_sha256": context["paired_generation_sha256"],
                "terminal_status": "CHECKED_SAT",
                "checked_sat": snapshot,
                "failure_codes": [],
                "claim": "assignment_satisfies_relaxed_fixed_geometry_model",
            }

    unresolved = [arm for arm in ("control", "treatment") if arm not in arms]
    free = _free_bytes(output_dir)
    disk_gate = {
        "checked_at_utc": _utc_now(),
        "free_bytes": free,
        "required_free_bytes": FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES,
        "proof_cap_bytes": FORMAL_PROOF_LIMIT_BYTES,
        "low_water_bytes": FORMAL_MIN_FREE_BYTES,
        "decision": (
            "NOT_REQUIRED_CHECKED_SAT"
            if not unresolved
            else "GO"
            if free >= FORMAL_PREFLIGHT_REQUIRED_FREE_BYTES
            else "NO_GO"
        ),
        "unresolved_arms": unresolved,
        "formal_tool_checked": False,
        "formal_child_spawned": False,
    }
    tools: dict[str, Any] | None = None
    cgroup: dict[str, Any] | None = None
    cgroup_end: dict[str, Any] | None = None
    cgroup_event_deltas: dict[str, int] | None = None
    lock_record: dict[str, Any] | None = None
    if unresolved and disk_gate["decision"] == "NO_GO":
        for arm in unresolved:
            arms[arm] = _arm_not_run(arm, context, "NO_GO", "disk_low_water_preflight")
    elif unresolved and args.preflight_only:
        tools, cgroup = _validate_runtime(args, root)
        disk_gate["formal_tool_checked"] = True
        for arm in unresolved:
            arms[arm] = _arm_not_run(arm, context, "NOT_RUN", "preflight_only")
    elif unresolved:
        tools, cgroup = _validate_runtime(args, root)
        disk_gate["formal_tool_checked"] = True
        lock_handle, lock_path = _lock()
        lock_record = {"path": str(lock_path), "acquired": True, "pid": os.getpid()}
        try:
            for arm in unresolved:
                formula = context["paths"][f"{arm}_opb"]
                arms[arm] = _formal_arm(arm, formula, args, context, output_dir, tools, cgroup)
                disk_gate["formal_child_spawned"] = disk_gate["formal_child_spawned"] or (
                    arms[arm].get("terminal_status") != "NO_GO"
                )
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()
        cgroup_end = _cgroup_state(args.expected_systemd_unit, False)
        cgroup_event_deltas = _event_deltas(cgroup.get("memory_events"), cgroup_end.get("memory_events"))
        cgroup_stable = bool(
            cgroup_end.get("contract_pass") is True
            and cgroup_end.get("cgroup_path") == cgroup.get("cgroup_path")
            and cgroup_end.get("systemd_properties") == cgroup.get("systemd_properties")
        )
        oom_clean = bool(
            cgroup_event_deltas is not None and all(cgroup_event_deltas.get(key, 0) == 0 for key in OOM_EVENT_KEYS)
        )
        if not cgroup_stable or not oom_clean:
            code = "cgroup_contract_drift" if not cgroup_stable else "oom_cgroup_event"
            for arm in unresolved:
                if arms[arm].get("terminal_status") != "NO_GO":
                    arms[arm]["terminal_status"] = "ERROR"
                    arms[arm].setdefault("failure_codes", []).append(code)
                    arms[arm]["claim"] = "none"
    attribution, status = _attribution(arms["control"]["terminal_status"], arms["treatment"]["terminal_status"])
    if status == "INCOMPLETE" and disk_gate["decision"] == "NO_GO":
        status = "NO_GO"
    failures = sorted({code for arm in arms.values() for code in arm.get("failure_codes", [])})
    if attribution == "monotonicity_contradiction":
        failures.append("treatment_sat_while_control_unsat")
    started = {
        "schema_version": "b1_conditional_halo_pair_run_started_v1",
        "started_at_utc": _utc_now(),
        "argv": argv,
        "case_index": context["case_index"],
        "case_id": context["case_id"],
        "pair_id": context["pair_id"],
        "transpose_group_id": context["transpose_group_id"],
        "paired_generation_sha256": context["paired_generation_sha256"],
        "inputs": context["records"],
        "input_copies": copied_inputs,
        "claim_at_start": "none",
    }
    _exclusive_json(output_dir / "run_started.json", started)
    pre_manifest = {
        "schema_version": RUN_SCHEMA,
        "status": status,
        "case_index": context["case_index"],
        "case_id": context["case_id"],
        "pair_id": context["pair_id"],
        "transpose_group_id": context["transpose_group_id"],
        "case": context["case"],
        "paired_generation_sha256": context["paired_generation_sha256"],
        "model_scope": "diagnostic_fixed_pattern",
        "argv": argv,
        "runner_source": _record(Path(__file__), root),
        "inputs": context["records"],
        "input_copies": copied_inputs,
        "paired_diff": {
            "added_constraint": context["added_constraint"],
            "exactly_one_conditional_halo": True,
            "rhs_doubled": 6650,
        },
        "preflight": disk_gate,
        "resource_contract": {
            "MemoryHigh": EXPECTED_MEMORY_HIGH,
            "MemoryMax": EXPECTED_MEMORY_MAX,
            "MemorySwapMax": EXPECTED_SWAP_MAX,
            "OOMPolicy": EXPECTED_OOM_POLICY,
            "KillMode": EXPECTED_KILL_MODE,
            "SendSIGKILL": EXPECTED_SEND_SIGKILL,
            "cgroup": cgroup,
            "cgroup_end": cgroup_end,
            "memory_event_deltas": cgroup_event_deltas,
            "singleton_lock": lock_record,
        },
        "tools": tools,
        "arms": arms,
        "attribution": attribution,
        "failure_codes": failures,
        "bound_ledger": {
            "inherited_upper_bound": UNCHANGED_BOUND,
            "control_upper_bound": UNCHANGED_BOUND,
            "treatment_upper_bound": UNCHANGED_BOUND,
            "global_update_authorized": False,
        },
        "proof_status": (
            "paired_diagnostic_complete_no_global_upper_bound_upgrade"
            if status == "COMPLETE"
            else "incomplete_or_failed_no_claim"
        ),
        "mcp_ownership": {
            "mcp_processes_started_by_runner": [],
            "cleanup_required": False,
            "note": "runner invokes only pinned local proof tools and starts no MCP server",
        },
        "claim_boundary": [
            "fixed-geometry safe-relaxation diagnostic only",
            "SAT requires an independently checked complete assignment",
            "UNSAT requires a fresh RoundingSat proof accepted by VeriPB 3.0.2",
            "only control SAT plus treatment UNSAT attributes pruning to the halo row",
            "sample result does not lower U or establish full-band UNSAT",
            "does not prove a witness, attainability, routing feasibility, or global optimality",
            "research artifact; not production CERTIFIED evidence",
        ],
        "artifact_manifest": None,
    }
    pre_seal = _revalidate_before_manifest(context, copied_inputs, checked, arms)
    pre_manifest["pre_seal_revalidation"] = pre_seal
    protected = [*copied_inputs.values()]
    for arm in ("control", "treatment"):
        snapshot = arms[arm].get("checked_sat")
        if isinstance(snapshot, Mapping) and isinstance(snapshot.get("copied"), Mapping):
            protected.extend(snapshot["copied"].values())
    manifest = _manifest(output_dir, root, protected)
    pre_manifest["artifact_manifest"] = manifest
    _exclusive_json(output_dir / RUN_RECORD_NAME, pre_manifest)
    if status == "COMPLETE":
        return pre_manifest, 0
    if disk_gate["decision"] == "NO_GO":
        return pre_manifest, 3
    return pre_manifest, 1


def _failure_record(
    output_dir: Path,
    args: argparse.Namespace,
    error: ScanError,
    argv: list[str],
) -> dict[str, Any]:
    arms = {
        arm: {
            "arm": arm,
            "paired_generation_sha256": None,
            "terminal_status": "ERROR",
            "failure_codes": [error.code],
            "claim": "none",
        }
        for arm in ("control", "treatment")
    }
    payload = {
        "schema_version": RUN_SCHEMA,
        "status": "FAIL",
        "case_index": args.case_index,
        "case_id": f"case_{args.case_index:03d}" if 0 <= args.case_index < 512 else None,
        "pair_id": None,
        "transpose_group_id": None,
        "case": None,
        "paired_generation_sha256": None,
        "model_scope": "diagnostic_fixed_pattern",
        "argv": argv,
        "runner_source": _record(Path(__file__), PROJECT_ROOT),
        "inputs": {},
        "input_copies": {},
        "preflight": {"decision": "FAIL", "formal_child_spawned": False},
        "resource_contract": None,
        "tools": None,
        "arms": arms,
        "attribution": "incomplete",
        "failure_codes": [error.code],
        "error": f"{type(error).__name__}: {error}",
        "bound_ledger": {
            "inherited_upper_bound": UNCHANGED_BOUND,
            "control_upper_bound": UNCHANGED_BOUND,
            "treatment_upper_bound": UNCHANGED_BOUND,
            "global_update_authorized": False,
        },
        "proof_status": "failed_closed_no_claim",
        "mcp_ownership": {"mcp_processes_started_by_runner": [], "cleanup_required": False},
        "claim_boundary": ["runner failed closed; no SAT, UNSAT, pruning, or upper-bound claim is authorized"],
        "artifact_manifest": None,
    }
    _exclusive_json(output_dir / "runner_failure.json", {"code": error.code, "message": str(error)})
    payload["artifact_manifest"] = _manifest(output_dir, PROJECT_ROOT)
    _exclusive_json(output_dir / RUN_RECORD_NAME, payload)
    return payload


def _reserve_output(args: argparse.Namespace) -> Path:
    root = args.project_root.resolve(strict=True)
    if root != PROJECT_ROOT.resolve(strict=True):
        raise ScanError("project_root_mismatch", "--project-root must identify this isolated worktree")
    output = args.output_dir.resolve(strict=False)
    artifact_root = ARTIFACT_ROOT.resolve(strict=False)
    try:
        output.relative_to(artifact_root)
    except ValueError as exc:
        raise ScanError("output_path_invalid", f"--output-dir must be below {artifact_root}") from exc
    if output == artifact_root or output.exists():
        raise ScanError("output_exists", "output directory must be a new unique child of the B1 artifact root")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700, exist_ok=False)
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--case-index", type=int, required=True)
    parser.add_argument("--geometry-admission", type=Path, required=True)
    parser.add_argument("--translation-admission", type=Path, required=True)
    parser.add_argument("--translation-gate", type=Path, required=True)
    parser.add_argument("--control-opb", type=Path, required=True)
    parser.add_argument("--control-meta", type=Path, required=True)
    parser.add_argument("--control-var-map", type=Path, required=True)
    parser.add_argument("--treatment-opb", type=Path, required=True)
    parser.add_argument("--treatment-meta", type=Path, required=True)
    parser.add_argument("--treatment-var-map", type=Path, required=True)
    parser.add_argument("--control-checked-sat", type=Path)
    parser.add_argument("--treatment-checked-sat", type=Path)
    parser.add_argument("--roundingsat", type=Path, default=EXPECTED_ROUNDINGSAT_PATH)
    parser.add_argument("--roundingsat-repo", type=Path, default=EXPECTED_ROUNDINGSAT_REPO)
    parser.add_argument("--veripb", type=Path, default=EXPECTED_VERIPB_PATH)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--solver-time-limit", type=float, default=FORMAL_SOLVER_TIME_LIMIT_SECONDS)
    parser.add_argument("--solver-wall-timeout", type=float, default=FORMAL_SOLVER_WALL_TIMEOUT_SECONDS)
    parser.add_argument("--verifier-wall-timeout", type=float, default=FORMAL_VERIFIER_WALL_TIMEOUT_SECONDS)
    parser.add_argument("--proof-limit-bytes", type=int, default=FORMAL_PROOF_LIMIT_BYTES)
    parser.add_argument("--min-free-bytes", type=int, default=FORMAL_MIN_FREE_BYTES)
    parser.add_argument("--monitor-interval", type=float, default=FORMAL_MONITOR_INTERVAL_SECONDS)
    parser.add_argument("--expected-systemd-unit")
    parser.add_argument("--require-cgroup-contract", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    effective_argv = [str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)]
    try:
        output_dir = _reserve_output(args)
    except (ScanError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2
    try:
        context = _validate_inputs(args)
        record, exit_code = _execute(args, context, output_dir, effective_argv)
    except ScanError as exc:
        try:
            record = _failure_record(output_dir, args, exc, effective_argv)
        except (OSError, ScanError) as record_exc:
            print(f"FAIL: {exc}; additionally could not close failure record: {record_exc}", file=sys.stderr)
            return 2
        exit_code = 2
    except OSError as exc:
        wrapped = ScanError("io_failure", str(exc))
        try:
            record = _failure_record(output_dir, args, wrapped, effective_argv)
        except (OSError, ScanError) as record_exc:
            print(f"FAIL: {exc}; additionally could not close failure record: {record_exc}", file=sys.stderr)
            return 2
        exit_code = 2
    print(
        json.dumps(
            {
                "status": record["status"],
                "attribution": record["attribution"],
                "case_index": record["case_index"],
                "output_dir": str(output_dir),
            },
            sort_keys=True,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
