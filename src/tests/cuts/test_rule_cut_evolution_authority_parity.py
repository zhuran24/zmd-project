"""Authority-preservation contracts for the rule/cut evolution shadow batch.

These tests bind the authority-sensitive runtime surfaces to exact authorized
bytes.  Five production surfaces remain at the 398f872 baseline;
preflight_gate.py is pinned to its latest authorized successor (see the
succession chain above `_PROTECTED_SURFACE_SHA256` — this docstring had
previously gone stale at the 2026-08-03 successor while the chain moved on,
so the chain comment is the single authority now);
and PROJECT_LOCK.md is pinned to the owner-authored documentation-hygiene
successor described beside `_PROJECT_LOCK_SHA256`.  Historical W0 D6 protocol
artifacts retain their original lock digest as part of their frozen identity.
The new semantic/family specifications may be imported by tests and by one
another, but the existing runtime must not import them during this
non-authorizing batch.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
from collections.abc import Iterator
from pathlib import Path

from src.cuts.lifecycle import Cut, CutScope, OracleCert, step_3_serialize, step_4_deserialize
from src.cuts.replay import DiagnosticResult, ReplayContext, regression_sweep, replay_cut
from src.cuts.state_snapshot import ValidatedStateSnapshot, build_validated_state_snapshot
from src.cuts.store import CutStore, QuarantineReason
from src.cuts.typed_apply import apply_compiled_cut
from src.cuts.typed_platform import (
    CompiledCut,
    ConstraintPlan,
    CutEnvelope,
    CutProvenance,
    FrozenFamilyProof,
    PatternNogoodProof,
    ScopeManifest,
    cut_to_envelope_v1,
    validate_and_compile_cut,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_BASELINE_COMMIT = "398f8725c770f3c36408adebe9448a890ed886fe"

# Authority provenance for the live PROJECT_LOCK successor:
#
# * 105cd379... remains the frozen W0 D6 / AB16 protocol identity and is not
#   rewritten in historical research inputs or receipts.
# * owner-authored commit 94d5df036980cbd4ebd5c2a2986a3e44eaf245dc changed
#   PROJECT_LOCK.md only to repair its live-document date and move edit history
#   into CHANGELOG.md.  The accompanying independent facade-diff audit found no
#   exactness or certified-boundary movement.
# * the resulting live lock bytes are therefore an authorized successor, not a
#   replacement of the historical W0 protocol identity.
_PROJECT_LOCK_AUTHORIZED_SUCCESSOR_COMMIT = (
    "94d5df036980cbd4ebd5c2a2986a3e44eaf245dc"
)
_PROJECT_LOCK_SHA256 = "3361e81a3f1b31121c06b3861cb6663185e45daa367234f74d621180b9d76495"

# Historical hashes for the six pre-existing Python surfaces touched during
# the abandoned runtime-wiring attempt.  Five remain byte-identical to
# 398f872; the sole authorized preflight successor is overlaid below.
_BASELINE_SURFACE_SHA256 = {
    "scripts/preflight_gate.py": "3c5e938df409b33bd789091d4dc1bae945acda27d3481969b7b4699117c65677",
    "src/cuts/lifecycle.py": "9b944572c3bc787317a2e9bfaaf4e3ce472ba8fd953269772b24535bbef1ac1a",
    "src/cuts/replay.py": "50a03470b0f9ddea85bb9b8fce246e326fa10a870ea930c7ebbf0c025604feed",
    "src/cuts/store.py": "6266f86dd37f1ca9d6654cb8596ffbece47e420ff526ecb112be505b60870b37",
    "src/cuts/typed_platform.py": "cce881457c63647dbba58750e1c4884351a31987057ac72b9cd0aeecaf44b45b",
    "src/search/benders_loop.py": "edeb594621c5f5fed140785c75419946ead74403ea6f72c1937822e1e8dfd852",
}

# The authorized preflight successor is the interpreter self-check one
# (2026-08-09, 门禁解释器盲点): every lane starts its subprocesses with
# `sys.executable`, so whichever python launched the gate decides what the whole
# run actually inspects — and that was never checked.  Measured the same day:
# launched with the system interpreter, mypy / ruff / pytest each went red with
# ModuleNotFoundError and the gate never mentioned the interpreter, while the
# same tree under `.venv/bin/python` reported 7301 passed.  The dangerous case is
# the opposite one, a partially equipped interpreter that lets the gate finish
# green while inspecting something other than what the project requires — false
# green, same family as the spinning "无 staged 文件" OKs of a missing .git.  A new
# `[0/18]` step therefore fails closed on the pinned floor plus the modules each
# lane needs, and skips every later lane when it trips, since their red would say
# nothing about the tree.  The test is capability-based, not identity-based: CI
# and stripped review copies may legitimately use their own environment.  The
# authority is the owner's instruction of 2026-08-09; no existing step's
# behaviour, order or exit-code semantics changed.
# It supersedes the memory-lane retirement successor (2026-08-09,
# f342e4df58fbfeaac2f95646fd1ed204e1bdd115521d23562d05293687e38355), which was
# the one (2026-08-09, 记忆层整体移除待空白重建) where both memory subsystems and every hook
# were removed whole, so the lane's three registry constants — MEMORY_TEST_DIRS,
# MEMORY_SCOPE_PREFIXES, MEMORY_CARD_VERIFIER — are now empty and the lane
# retires itself rather than blocking on roots that were deliberately taken
# away.  This is the exit 9cf7600 specified for itself ("a genuine retirement
# has to edit MEMORY_TEST_DIRS first"), so the missing-root BLOCK is untouched
# and still fires for the accident it was built for: a deleted, renamed or
# half-checked-out root while the registry still names it.  An *empty* registry
# is the separate third case — the paperwork done rather than an accident — so
# it warns on every run instead of blocking, because live hooks are genuinely
# unguarded until the rebuild lands and 6b2fb40 built this lane precisely so
# that fact could not be silent.  The authority is the owner's instruction of
# 2026-08-09 (remove the memory systems and hooks, rebuild from blank); the
# change is memory-lane only, no proof-lane gate logic moved.
# It supersedes the memory-index closed-loop successor (2026-08-08,
# c81a4abc6d7dde56e49e2e71d90a0ee574e0adb4da194c386e31f86f2aa830ef), which was
# the one (2026-08-08, 单门牌化落地收尾) where the memory lane gained a
# `check-index` step between `zmem verify` and its pytest block — it
# byte-compares the file-layer
# `MEMORY.md` against what the cards compile to, warns (never blocks) on drift,
# and stays silent when the memory directory is absent (CI, stripped review
# copies).  The authority is the same memory-system meeting adjudication
# (.artifacts/memsys_meeting_20260808/FINAL_VERDICT.md §5b); the change is
# memory-lane additive only, advisory-only, no proof-lane gate logic moved.
# It supersedes the memory-card verify gate successor (2026-08-08,
# 0cd7b9112c244685f7d0dcf037a75c9eb435ca73e8867c57c6656777e714ac01), which was
# the memory-card verify gate one
# (2026-08-08, 记忆系统复查会议批③ M-21): check_memory_cards runs
# `zmem.py verify` inside the memory lane before its pytest block — a card
# error blocks, a missing verifier blocks, a stale-index line warns.  The
# authority is the memory-system meeting adjudication
# (.artifacts/memsys_meeting_20260808/FINAL_VERDICT.md §5 批③); the change is
# memory-lane additive only — no proof-lane gate logic moved.  It supersedes
# the canonical semantics-amendment freeze-ritual successor (2026-08-08,
# 8c2e5bf3cfa419b32e8f543b4d64c6fa687a290b3a703947f89318846735f3ef), which
# was itself the freeze-ritual batch where FROZEN_ARTIFACTS re-pins
# rules/canonical_rules.json after the semantics block gained the sorting-terminal
# theorem, the terminal-clause instance discharge, the protocol-box cache
# parameters, the conditional admission-port authority and the fifth/sixth
# model_stricter_faces entries.  Only the pinned digest moved; no gate logic
# changed.  It supersedes the axiom-kernel successor (2026-08-07,
# 468eb896857ff2546b97c0238d213d92d182a53c44cb19041ece3f5e2dda7846 — axiom kernel
# chapter plus the four-item amendment batch), which superseded the
# canonical-emptiness successor (2026-08-05, owner-adjudicated emptiness
# definition), which superseded the memory-lane additive successor (2026-08-03,
# 剪枝 v2 P2 — memory-layer pytest lane plus its blocking-on-missing-roots and
# per-run basetemp fixes), which in turn superseded 8292983's secret-scan
# timeout-scale successor.
#
# The authorized benders_loop successor is the strict empty-rectangle batch
# (2026-08-05): ghost cells join the routing occupancy set, and blocked ports
# attributed to the hole stop minting unconditional cuts.  The authority is the
# owner's empty-rectangle semantics adjudication of the same date, not the cut
# framework — nothing in the cut lifecycle wiring moved.
_PROTECTED_SURFACE_SHA256 = {
    **_BASELINE_SURFACE_SHA256,
    "scripts/preflight_gate.py": "1cecd1a6498aac4d7306e635c299429a11260f6df634a828a7d621da0e52dbfb",
    "src/search/benders_loop.py": "461fc6875ca16781c1d0d81720aee98747a3d2c984a4c1bf1afda4f384af1bc3",
}

_P1_2_SINK_SHA256 = {
    "src/cuts/lifecycle.py": "9b944572c3bc787317a2e9bfaaf4e3ce472ba8fd953269772b24535bbef1ac1a",
    "src/cuts/typed_platform.py": "cce881457c63647dbba58750e1c4884351a31987057ac72b9cd0aeecaf44b45b",
    "src/search/benders_loop.py": "461fc6875ca16781c1d0d81720aee98747a3d2c984a4c1bf1afda4f384af1bc3",
}

_WIRE_FIELDS = {
    Cut: (
        "cut_id",
        "family",
        "literals",
        "geometric_payload",
        "scope",
        "cert",
        "family_version",
        "validator_version",
        "payload_schema_version",
        "oracle_name",
        "oracle_cert_hash",
        "minimization_audit",
        "created_at",
        "iter_index",
        "is_quarantined",
        "quarantine_reason",
    ),
    CutScope: (
        "ghost_rect_id",
        "blocked_cells_hash",
        "exterior_blocks_hash",
        "source_digest",
        "artifact_hashes",
        "oracle_abstraction_version",
        "active_assumptions",
        "identity_preimage",
    ),
    OracleCert: ("cert_kind", "cert_payload", "cert_hash"),
    CutEnvelope: (
        "cut_id",
        "family",
        "family_schema_version",
        "proof_payload",
        "proof_hash",
        "scope",
        "provenance",
    ),
    ScopeManifest: (
        "scope_schema_version",
        "family",
        "ghost_policy",
        "ghost_rect_digest",
        "blocked_cells_digest",
        "exterior_blocks_digest",
        "source_digest",
        "dependency_hashes",
        "oracle_abstraction_version",
        "assumptions",
    ),
    CutProvenance: (
        "family_version",
        "validator_version",
        "oracle_name",
        "oracle_cert_hash",
        "created_at",
        "iter_index",
    ),
    ConstraintPlan: (
        "family",
        "schema_version",
        "semantic_fingerprint",
        "model_scope",
        "operation",
        "parameters",
        "digest",
    ),
    CompiledCut: (
        "cut_id",
        "proof_digest",
        "scope_digest",
        "snapshot_digest",
        "plan",
        "digest",
    ),
    FrozenFamilyProof: ("family", "schema_version"),
    PatternNogoodProof: (
        "family",
        "schema_version",
        "cert_kind",
        "sub_problem_oracle_name",
        "sub_problem_oracle_version",
        "forbidden_pose_pattern",
        "core_minimization",
    ),
    ValidatedStateSnapshot: (
        "source_digest",
        "artifact_hashes",
        "ghost",
        "blocked_cells_digest",
        "exterior_blocks_digest",
        "master_domain_projection",
        "shape_packing_hall_master_domain_projection",
        "power_hitting_set_master_domain_projection",
        "oracle_capabilities",
        "canonical_rules_source_present",
        "family_inputs",
        "groups",
        "cell_owner",
        "ghost_cells",
        "exterior_blocks",
        "digest",
    ),
    ReplayContext: ("snapshot", "registry", "legacy_state"),
    DiagnosticResult: ("family", "cut_id", "outcome", "detail"),
    CutStore: (
        "cuts",
        "by_cell_watcher",
        "by_group_watcher",
        "by_pose_watcher",
        "by_commodity_watcher",
        "by_region_watcher",
        "by_ghost_watcher",
        "quarantined",
        "held",
    ),
    QuarantineReason: ("reason_code", "detail", "iter_index"),
}

_PUBLIC_SIGNATURE_PARAMETERS = {
    ConstraintPlan: (
        "family",
        "schema_version",
        "semantic_fingerprint",
        "model_scope",
        "operation",
        "parameters",
    ),
    ValidatedStateSnapshot: (
        "source_digest",
        "artifact_hashes",
        "ghost",
        "blocked_cells_digest",
        "exterior_blocks_digest",
        "master_domain_projection",
        "shape_packing_hall_master_domain_projection",
        "power_hitting_set_master_domain_projection",
        "oracle_capabilities",
        "canonical_rules_source_present",
        "family_inputs",
        "groups",
        "cell_owner",
        "ghost_cells",
        "exterior_blocks",
        "digest",
        "_construction_token",
    ),
    cut_to_envelope_v1: ("cut",),
    validate_and_compile_cut: ("envelope", "snapshot", "registry"),
    build_validated_state_snapshot: ("state", "bundle"),
    step_3_serialize: ("cut",),
    step_4_deserialize: ("blob",),
    replay_cut: ("cut", "store", "context", "iter_index"),
    regression_sweep: ("store", "context", "iter_index"),
    CutStore.add_cut: (
        "self",
        "cut",
        "cell_keys",
        "group_keys",
        "pose_keys",
        "commodity_keys",
        "region_keys",
        "initial_state",
    ),
    CutStore.quarantine_cut: ("self", "cut_id", "reason"),
    apply_compiled_cut: ("compiled_cut", "master", "scope_binding"),
}

_SHADOW_MODULE_FILES = frozenset(
    {
        Path("src/cuts/family_specs.py"),
        Path("src/cuts/rejection_audit.py"),
        Path("src/cuts/rule_semantics.py"),
        Path("src/search/family_generation.py"),
    }
)
_FORBIDDEN_RUNTIME_IMPORTS = frozenset(
    {
        "src.cuts.family_specs",
        "src.cuts.rejection_audit",
        "src.cuts.rule_semantics",
        "src.search.family_generation",
        "src.tests",
    }
)
_FORBIDDEN_RELATIVE_IMPORT_NAMES = frozenset(
    {"family_specs", "rejection_audit", "rule_semantics", "family_generation", "tests"}
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iter_imported_modules(tree: ast.AST) -> Iterator[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            yield node.lineno, node.module or ""
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
            module_name = node.args[0].value
            if not isinstance(module_name, str):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                yield node.lineno, module_name
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "import_module":
                yield node.lineno, module_name


def _is_forbidden_runtime_import(module_name: str) -> bool:
    if module_name in _FORBIDDEN_RELATIVE_IMPORT_NAMES:
        return True
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in _FORBIDDEN_RUNTIME_IMPORTS
    )


def test_project_lock_matches_authorized_documentation_successor() -> None:
    assert _BASELINE_COMMIT == "398f8725c770f3c36408adebe9448a890ed886fe"
    assert _PROJECT_LOCK_AUTHORIZED_SUCCESSOR_COMMIT == (
        "94d5df036980cbd4ebd5c2a2986a3e44eaf245dc"
    )
    assert _sha256(_PROJECT_ROOT / "PROJECT_LOCK.md") == _PROJECT_LOCK_SHA256


def test_protected_surfaces_match_398f872_except_authorized_preflight_successor() -> None:
    actual = {
        relative_path: _sha256(_PROJECT_ROOT / relative_path)
        for relative_path in _PROTECTED_SURFACE_SHA256
    }
    assert actual == _PROTECTED_SURFACE_SHA256


def test_p1_2_manifest_and_registered_sink_bytes_remain_at_sealed_hashes() -> None:
    manifest_path = _PROJECT_ROOT / "data/proof_obligations/p1_2_proof_obligations.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sink_entries = {
        entry["path"]: entry
        for entry in manifest["close_kernel_contract"]["sink_files"]
        if entry["path"] in _P1_2_SINK_SHA256
    }

    assert set(sink_entries) == set(_P1_2_SINK_SHA256)
    for relative_path, expected_sha256 in _P1_2_SINK_SHA256.items():
        entry = sink_entries[relative_path]
        assert entry["source_sha256"] == expected_sha256
        assert entry["mutation_policy"] == "source_sha256_drift_reopens_p1_2_close_claim"
        assert _sha256(_PROJECT_ROOT / relative_path) == expected_sha256


def test_existing_wire_dataclass_fields_remain_exact() -> None:
    actual = {
        wire_type: tuple(field.name for field in dataclasses.fields(wire_type))
        for wire_type in _WIRE_FIELDS
    }
    assert actual == _WIRE_FIELDS
    assert all(
        "record_id" not in fields and "audit_record" not in fields
        for fields in actual.values()
    )


def test_public_entrypoint_signatures_do_not_gain_manifest_or_audit_parameters() -> None:
    actual = {
        entrypoint: tuple(inspect.signature(entrypoint).parameters)
        for entrypoint in _PUBLIC_SIGNATURE_PARAMETERS
    }
    assert actual == _PUBLIC_SIGNATURE_PARAMETERS
    for parameters in actual.values():
        assert not any("manifest" in name or "audit" in name or "record" in name for name in parameters)


def test_preexisting_production_does_not_import_shadow_or_test_only_modules() -> None:
    violations: list[str] = []
    production_paths = [
        path
        for path in sorted((_PROJECT_ROOT / "src").rglob("*.py"))
        if "tests" not in path.relative_to(_PROJECT_ROOT).parts
        and path.relative_to(_PROJECT_ROOT) not in _SHADOW_MODULE_FILES
    ]
    production_paths.append(_PROJECT_ROOT / "scripts/preflight_gate.py")

    for path in production_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for lineno, module_name in _iter_imported_modules(tree):
            if _is_forbidden_runtime_import(module_name):
                violations.append(f"{path.relative_to(_PROJECT_ROOT)}:{lineno}: {module_name}")

    assert violations == []
