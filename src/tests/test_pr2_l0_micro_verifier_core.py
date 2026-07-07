from __future__ import annotations

import ast
import base64
import dataclasses
import hashlib
import json
import subprocess
import sys
import sysconfig
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.search import exact_campaign as exact_campaign_module
from src.search import pr2_l0_micro_verifier_core as l0
from src.search import pr2_l0_true_verifier_child as true_child
from scripts.generate_pr2_dependency_floor_manifest import build_manifest


def _import_roots(source: str) -> set[str]:
    roots: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def test_l0_stage1_ast_imports_are_stdlib_only() -> None:
    source_path = Path(l0.__file__).resolve()
    module_roots = _import_roots(source_path.read_text(encoding="utf-8"))
    bootstrap_roots = _import_roots(l0.CHILD_BOOTSTRAP_SOURCE)
    allowed = set(sys.stdlib_module_names) | {"__future__"}

    assert module_roots <= allowed
    assert bootstrap_roots <= allowed
    assert "src" not in module_roots | bootstrap_roots


def test_l0_round_trip_seals_through_snapshot_loader() -> None:
    verdict = l0.run_l0_micro_verifier_round_trip({"action": "ack"})

    assert verdict.status == l0.SEALED
    assert verdict.response["stage_trace"] == [
        "floor_verified",
        "loader_installed",
        "verifier_imported",
        "verifier_ran",
    ]


def test_l0_loader_ignores_sys_path_shadow(tmp_path: Path) -> None:
    shadow = tmp_path / "shadow" / "src" / "search"
    shadow.mkdir(parents=True)
    (shadow / "pr2_l0_trivial_child.py").write_text(
        "def verify(_request):\n"
        "    return {'verdict': 'REJECTED', 'nonce': 'shadow', 'reason': 'shadow'}\n",
        encoding="utf-8",
    )

    verdict = l0.run_l0_micro_verifier_round_trip(
        {"action": "ack"},
        poison_sys_path=shadow.parents[1],
    )

    assert verdict.status == l0.SEALED
    assert verdict.reason == "trivial_ack"


def test_l0_loader_rejects_tampered_project_snapshot_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_materialize = l0._materialize_snapshot

    def tampered_materialize(
        snapshot_root: Path,
        modules: object,
        *,
        source_root: Path,
    ) -> dict[str, dict[str, str]]:
        manifest = original_materialize(
            snapshot_root,
            modules,  # type: ignore[arg-type]
            source_root=source_root,
        )
        entry = manifest[l0.DEFAULT_VERIFIER_MODULE]
        (snapshot_root / entry["path"]).write_text(
            "def verify(request):\n"
            "    return {'verdict': 'SEALED', 'nonce': request['nonce'], 'reason': 'tampered'}\n",
            encoding="utf-8",
        )
        return manifest

    monkeypatch.setattr(l0, "_materialize_snapshot", tampered_materialize)

    verdict = l0.run_l0_micro_verifier_round_trip({"action": "ack"})

    assert verdict.status == l0.REJECTED
    assert verdict.reason == "response_floor_digest_mismatch"
    assert "manifest digest mismatch" in str(verdict.response.get("reason", ""))


def test_l0_child_invocation_uses_no_site_and_fresh_pycache(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        request = json.loads(str(kwargs["input"]))
        captured["argv"] = list(argv)
        captured["cwd"] = kwargs.get("cwd")
        captured["env"] = kwargs.get("env")
        response = {
            "schema_version": l0.SCHEMA_VERSION,
            "authority": l0.AUTHORITY,
            "nonce": request["nonce"],
            "floor_digest": request["floor_digest"],
            "verdict": l0.SEALED,
            "reason": "stubbed",
            "stage_trace": ["floor_verified", "loader_installed", "verifier_imported", "verifier_ran"],
            "verifier_module": request["verifier_module"],
            "domain": {},
        }
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(response) + "\n", stderr="")

    monkeypatch.setattr(l0.subprocess, "run", fake_run)

    verdict = l0.run_l0_micro_verifier_round_trip({"action": "ack"})

    assert verdict.status == l0.SEALED
    argv = captured["argv"]
    assert isinstance(argv, list)
    assert argv[1:5] == ["-I", "-S", "-B", "-X"]
    assert isinstance(argv[5], str) and argv[5].startswith("pycache_prefix=")
    assert captured["cwd"]


def test_l0_loader_rejects_snapshot_external_project_import() -> None:
    verdict = l0.run_l0_micro_verifier_round_trip(
        {"action": "probe_import", "module": "src.search.exact_campaign"}
    )

    assert verdict.status == l0.REJECTED


def test_l0_bootstrap_is_two_stage_ordered() -> None:
    verdict = l0.run_l0_micro_verifier_round_trip({"action": "ack"})

    assert verdict.status == l0.SEALED
    assert verdict.response["stage_trace"].index("floor_verified") < verdict.response[
        "stage_trace"
    ].index("loader_installed")
    assert verdict.response["stage_trace"].index("loader_installed") < verdict.response[
        "stage_trace"
    ].index("verifier_imported")


def test_l0_binary_nonce_verdicts_fail_closed() -> None:
    good = l0.run_l0_micro_verifier_round_trip({"action": "ack"})
    bad_nonce = l0.run_l0_micro_verifier_round_trip({"action": "wrong_nonce"})
    missing = l0.run_l0_micro_verifier_round_trip(
        {"action": "ack"},
        omit_snapshot_modules=(l0.DEFAULT_VERIFIER_MODULE,),
    )
    timeout = l0.run_l0_micro_verifier_round_trip(
        {"action": "sleep", "seconds": 2.0},
        timeout_seconds=0.1,
    )

    assert good.status == l0.SEALED
    assert bad_nonce.status == l0.REJECTED
    assert missing.status == l0.REJECTED
    assert timeout.status == l0.REJECTED
    assert {good.status, bad_nonce.status, missing.status, timeout.status} <= {
        l0.SEALED,
        l0.REJECTED,
    }


@pytest.mark.parametrize("text", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":1e400}'])
def test_l0_strict_json_rejects_duplicate_nan_and_overflow(text: str) -> None:
    with pytest.raises(ValueError):
        l0.loads_l0_strict_json(text)


def test_l0_strong_status_keys_include_certified_and_infeasible_only() -> None:
    authority_state = {
        "candidates": {
            "2x1": {"status": "INFEASIBLE"},
            "1x1": {"status": "CERTIFIED"},
            "3x1": {"status": "UNKNOWN"},
            "4x1": {"status": "UNPROVEN"},
        }
    }

    assert l0._strong_status_keys(authority_state) == ["1x1", "2x1"]


def test_l0_domain_response_requires_exact_strong_key_coverage() -> None:
    domain = {
        "schema_version": l0.SUPERVISOR_DOMAIN_SCHEMA_VERSION,
        "authority": l0.SUPERVISOR_DOMAIN_AUTHORITY,
        "nonce": "nonce",
        "verdict": l0.SEALED,
        "reason": "",
        "strong_keys": ["1x1"],
        "final_result": {},
        "terminal_frontier_evidence": {},
        "candidate_records": {},
        "final_result_digest": "a" * 64,
        "terminal_frontier_evidence_digest": "b" * 64,
        "candidate_records_digest": "c" * 64,
        "fixed_witness_publishable": True,
        "sink_replay_violations": {},
        "fixed_witness_violations": {},
        "tcb": {},
    }

    assert (
        l0._domain_response_violation(
            domain,
            nonce="nonce",
            strong_keys=["1x1", "2x1"],
            proposal_final_result_digest="a" * 64,
            proposal_evidence_digest="b" * 64,
            proposal_candidate_records_digest="c" * 64,
        )
        == "domain_strong_key_coverage_mismatch"
    )

    domain["strong_keys"] = ["1x1", "2x1"]
    for field_name, bad_value, expected in (
        ("terminal_frontier_evidence", [], "domain_terminal_frontier_evidence_invalid"),
        ("candidate_records", [], "domain_candidate_records_invalid"),
        ("sink_replay_violations", {"1x1": "boom"}, "domain_sink_replay_violations"),
        ("fixed_witness_violations", {"1x1": "boom"}, "domain_fixed_witness_violations"),
        ("fixed_witness_publishable", "yes", "domain_fixed_witness_not_publishable"),
        ("fixed_witness_publishable", False, "domain_fixed_witness_not_publishable"),
        ("candidate_records_digest", "d" * 64, "domain_candidate_records_digest_mismatch"),
    ):
        mutated = dict(domain)
        mutated[field_name] = bad_value
        assert (
            l0._domain_response_violation(
                mutated,
                nonce="nonce",
                strong_keys=["1x1", "2x1"],
                proposal_final_result_digest="a" * 64,
                proposal_evidence_digest="b" * 64,
                proposal_candidate_records_digest="c" * 64,
            )
            == expected
        )


def _payload_with_manifest_digest(payload: dict[str, object]) -> dict[str, object]:
    manifest = dict(payload)
    manifest["manifest_digest"] = hashlib.sha256(l0._canonical_bytes(payload)).hexdigest()
    return manifest


def _run_floor_probe_child(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    payload: dict[str, object],
    timeout_seconds: float = 60.0,
) -> l0.L0MicroVerdict:
    probe_module = "src.search._pr2_floor_probe_child"
    probe_path = tmp_path / "_pr2_floor_probe_child.py"
    probe_path.write_text(source, encoding="utf-8")
    true_child_path = Path(true_child.__file__).resolve()

    def snapshot_module_paths(
        *,
        source_root: Path,
        verifier_module: str,
        extra_snapshot_modules: object,
        omit_snapshot_modules: frozenset[str],
    ) -> dict[str, Path]:
        del source_root, extra_snapshot_modules, omit_snapshot_modules
        assert verifier_module == probe_module
        return {
            probe_module: probe_path,
            "src.search.pr2_l0_true_verifier_child": true_child_path,
        }

    monkeypatch.setattr(l0, "_snapshot_module_paths", snapshot_module_paths)
    return l0.run_l0_micro_verifier_round_trip(
        payload,
        verifier_module=probe_module,
        timeout_seconds=timeout_seconds,
    )


@pytest.fixture(scope="session")
def host_dependency_floor_manifest_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    manifest_path = tmp_path_factory.mktemp("pr2_dependency_floor") / "manifest.json"
    manifest = build_manifest()
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path


def test_l0_canonical_dependency_floor_manifest_missing_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(l0, "DEPENDENCY_FLOOR_MANIFEST_REL", "missing_floor.json")

    with pytest.raises(ValueError, match="expected regular file"):
        l0._load_canonical_dependency_floor_manifest(tmp_path)


def test_l0_canonical_dependency_floor_manifest_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "floor.json"
    manifest_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(l0, "DEPENDENCY_FLOOR_MANIFEST_REL", manifest_path.name)

    with pytest.raises(ValueError, match="canonical dependency floor manifest .* drift"):
        l0._load_canonical_dependency_floor_manifest(tmp_path)


def test_l0_canonical_dependency_floor_manifest_current_bytes_are_pinned() -> None:
    source_root = Path(l0.__file__).resolve().parents[2]
    manifest_path = source_root / l0.DEPENDENCY_FLOOR_MANIFEST_REL
    raw = manifest_path.read_bytes()

    assert len(raw) == l0.DEPENDENCY_FLOOR_MANIFEST_SIZE_BYTES
    assert hashlib.sha256(raw).hexdigest() == l0.DEPENDENCY_FLOOR_MANIFEST_SHA256


def test_l0_canonical_dependency_floor_manifest_loads_on_matching_host() -> None:
    source_root = Path(l0.__file__).resolve().parents[2]
    try:
        dependency_floor = l0._load_canonical_dependency_floor_manifest(source_root)
    except ValueError as exc:
        pytest.skip(f"canonical dependency floor does not match this host: {exc}")

    assert l0._dependency_floor_root(dependency_floor["floor_root"]) == Path(
        sysconfig.get_paths()["purelib"]
    ).resolve()
    assert dependency_floor["files"]


def test_l0_dependency_floor_blocks_floor_out_site_package_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    host_dependency_floor_manifest_path: Path,
) -> None:
    dependency_floor = l0._load_dependency_floor_manifest(host_dependency_floor_manifest_path)
    floor_root = l0._dependency_floor_root(dependency_floor["floor_root"])
    pytest_path = Path(pytest.__file__).resolve()
    pytest_path.relative_to(floor_root)
    assert "pytest" not in set(dependency_floor["allowed_top_level"])
    source = """
import sys
from src.search.pr2_l0_true_verifier_child import _install_third_party_floor


def verify(request):
    nonce = str(request.get("nonce", ""))
    payload = request["payload"]
    _install_third_party_floor(payload["dependency_floor"])
    sys.path.append(str(payload["poison_site_path"]))
    try:
        __import__(str(payload["blocked_module"]))
    except ModuleNotFoundError:
        return {"verdict": "SEALED", "nonce": nonce, "reason": "floor_out_import_blocked"}
    return {"verdict": "REJECTED", "nonce": nonce, "reason": "floor_out_import_allowed"}
"""

    verdict = _run_floor_probe_child(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        source=source,
        payload={
            "dependency_floor": dependency_floor,
            "blocked_module": "pytest",
            "poison_site_path": str(floor_root),
        },
    )

    assert verdict.status == l0.SEALED
    assert verdict.reason == "floor_out_import_blocked"


def test_l0_dependency_floor_supports_allowed_namespace_package_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    floor_root = tmp_path / "floor"
    package_file = floor_root / "google" / "protobuf" / "__init__.py"
    package_file.parent.mkdir(parents=True)
    package_source = b"VALUE = 'floor-only-namespace-package'\n"
    package_file.write_bytes(package_source)
    manifest = _payload_with_manifest_digest(
        {
            "schema_version": 1,
            "authority": "pr2_l0_dependency_floor_manifest_v1",
            "floor_root": str(floor_root),
            "allowed_top_level": ["google"],
            "files": {
                "google/protobuf/__init__.py": {
                    "sha256": hashlib.sha256(package_source).hexdigest(),
                    "size": len(package_source),
                }
            },
            "named_tcb": {
                "third_party_closure": {"google": "NAMED-TCB"},
            },
        }
    )
    source = """
from src.search.pr2_l0_true_verifier_child import _install_third_party_floor


def verify(request):
    nonce = str(request.get("nonce", ""))
    _install_third_party_floor(request["payload"]["dependency_floor"])
    import google.protobuf
    if google.protobuf.VALUE != "floor-only-namespace-package":
        return {"verdict": "REJECTED", "nonce": nonce, "reason": "namespace_wrong_module"}
    return {"verdict": "SEALED", "nonce": nonce, "reason": "namespace_import_allowed"}
"""

    verdict = _run_floor_probe_child(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        source=source,
        payload={"dependency_floor": manifest},
    )

    assert verdict.status == l0.SEALED
    assert verdict.reason == "namespace_import_allowed"


def test_l0_child_rejects_tampered_dependency_floor_python_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    floor_root = tmp_path / "floor"
    package_file = floor_root / "allowedpkg" / "__init__.py"
    package_file.parent.mkdir(parents=True)
    package_file.write_bytes(b"before")
    manifest = _payload_with_manifest_digest(
        {
            "schema_version": 1,
            "authority": "pr2_l0_dependency_floor_manifest_v1",
            "floor_root": str(floor_root),
            "allowed_top_level": ["allowedpkg"],
            "files": {
                "allowedpkg/__init__.py": {
                    "sha256": hashlib.sha256(b"before").hexdigest(),
                    "size": len(b"before"),
                }
            },
            "named_tcb": {
                "third_party_closure": {"allowedpkg": "NAMED-TCB"},
            },
        }
    )
    package_file.write_bytes(b"after")
    source = """
from src.search.pr2_l0_true_verifier_child import _install_third_party_floor


def verify(request):
    nonce = str(request.get("nonce", ""))
    _install_third_party_floor(request["payload"]["dependency_floor"])
    return {"verdict": "SEALED", "nonce": nonce, "reason": "floor_installed"}
"""

    verdict = _run_floor_probe_child(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        source=source,
        payload={"dependency_floor": manifest},
    )

    assert verdict.status == l0.REJECTED
    assert "dependency floor digest mismatch" in verdict.reason


def test_l0_child_rejects_load_time_toctou_same_path_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # B1 regression: the floor verifies every file's digest at INSTALL time, but a
    # same-path swap performed AFTER install and BEFORE import must still be caught
    # at LOAD time -- otherwise unverified Python code loads into the deciding
    # verifier (the historical false-CERTIFIED channel "mutated_same_path_loaded").
    floor_root = tmp_path / "floor"
    package_file = floor_root / "toctoupkg" / "__init__.py"
    package_file.parent.mkdir(parents=True)
    clean_source = b'VALUE = "clean"\n'
    package_file.write_bytes(clean_source)
    manifest = _payload_with_manifest_digest(
        {
            "schema_version": 1,
            "authority": "pr2_l0_dependency_floor_manifest_v1",
            "floor_root": str(floor_root),
            "allowed_top_level": ["toctoupkg"],
            "files": {
                "toctoupkg/__init__.py": {
                    "sha256": hashlib.sha256(clean_source).hexdigest(),
                    "size": len(clean_source),
                }
            },
            "named_tcb": {
                "third_party_closure": {"toctoupkg": "NAMED-TCB"},
            },
        }
    )
    source = """
import importlib
from pathlib import Path

from src.search.pr2_l0_true_verifier_child import _install_third_party_floor


def verify(request):
    nonce = str(request.get("nonce", ""))
    payload = request["payload"]
    _install_third_party_floor(payload["dependency_floor"])
    # install-time digest verified OK; swap the same path with unverified code now
    Path(str(payload["target_file"])).write_bytes(payload["mutated_source"].encode("utf-8"))
    try:
        importlib.import_module("toctoupkg")
    except ImportError as exc:
        if "load-time digest mismatch" in str(exc):
            return {"verdict": "SEALED", "nonce": nonce, "reason": "load_time_toctou_blocked"}
        return {"verdict": "REJECTED", "nonce": nonce, "reason": f"unexpected_import_error:{exc}"}
    return {"verdict": "REJECTED", "nonce": nonce, "reason": "mutated_same_path_loaded"}
"""

    verdict = _run_floor_probe_child(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        source=source,
        payload={
            "dependency_floor": manifest,
            "target_file": str(package_file),
            "mutated_source": 'VALUE = "evil"\n',
        },
    )

    assert verdict.status == l0.SEALED
    assert verdict.reason == "load_time_toctou_blocked"


def test_l0_supervisor_seal_request_rejects_caller_dependency_floor_override() -> None:
    # B2 regression: the durable mint must NOT accept a caller-selected dependency
    # floor manifest path -- that would let a caller substitute an attacker-chosen,
    # self-consistent floor (the "accepted_arbitrary_manifest_path" channel).  The
    # field must not exist on the request at all.
    field_names = {field.name for field in dataclasses.fields(l0.L0SupervisorSealRequest)}
    assert "dependency_manifest_path" not in field_names
    with pytest.raises(TypeError):
        l0.L0SupervisorSealRequest(
            project_root=Path("."),
            campaign_path=Path("."),
            marker_path=Path("."),
            expected_campaign_instance_id="0" * 32,
            dependency_manifest_path=Path("."),
        )


def test_l0_strong_proof_binding_rejects_campaign_path_mismatch(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    wrong_campaign_path = project_root / "other.json"
    base_proof = {
        "project_binding": {
            "project_root": str(project_root),
            "campaign_path": str(campaign_path),
        },
        "campaign_context": {
            "project_root": str(project_root),
            "campaign_path": str(campaign_path),
        },
    }
    authority_state = {
        "candidates": {
            "1x1": {
                "status": "CERTIFIED",
                "candidate_proof": {
                    **base_proof,
                    "project_binding": {
                        "project_root": str(project_root),
                        "campaign_path": str(wrong_campaign_path),
                    },
                    "campaign_context": {
                        "project_root": str(project_root),
                        "campaign_path": str(wrong_campaign_path),
                    },
                },
            }
        }
    }

    assert l0._strong_proof_binding_violation(
        authority_state=authority_state,
        strong_keys=["1x1"],
        project_root=project_root.resolve(),
        campaign_path=campaign_path.resolve(),
    ) == "candidate_sink_replay_campaign_binding_mismatch:1x1"

    for proof, expected in (
        (None, "candidate_sink_replay_proof_missing:1x1"),
        ({}, "candidate_sink_replay_project_binding_invalid:1x1"),
        (
            {
                **base_proof,
                "project_binding": {
                    "project_root": str(project_root),
                    "campaign_path": str(campaign_path),
                },
                "campaign_context": {},
            },
            "candidate_sink_replay_campaign_context_mismatch:1x1",
        ),
    ):
        authority_state["candidates"]["1x1"]["candidate_proof"] = proof
        assert (
            l0._strong_proof_binding_violation(
                authority_state=authority_state,
                strong_keys=["1x1"],
                project_root=project_root.resolve(),
                campaign_path=campaign_path.resolve(),
            )
            == expected
        )


def test_l0_dependency_floor_manifest_rejects_digest_mismatch(tmp_path: Path) -> None:
    floor_root = tmp_path / "floor"
    package_file = floor_root / "absl" / "__init__.py"
    package_file.parent.mkdir(parents=True)
    package_file.write_bytes(b"before")
    manifest = {
        "schema_version": 1,
        "authority": "pr2_l0_dependency_floor_manifest_v1",
        "floor_root": str(floor_root),
        "allowed_top_level": ["absl"],
        "files": {
            "absl/__init__.py": {
                "sha256": hashlib.sha256(b"before").hexdigest(),
                "size": len(b"before"),
            }
        },
        "named_tcb": {"third_party_closure": {"absl": "NAMED-TCB"}},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    package_file.write_bytes(b"after")

    with pytest.raises(ValueError, match="dependency floor digest mismatch"):
        l0._load_dependency_floor_manifest(manifest_path)


def test_l0_supervisor_certified_transition_promotes_declare_mode_to_strict() -> None:
    """PR2 #5 review hardening (BLOCK 1): the durable CERTIFIED transition must
    canonicalize declare_mode to the supervisor-owned strict terminal label, so a
    producer that ships declare_mode="best_effort" cannot end up with a durable
    final_status="CERTIFIED" state that fails its own terminal-evidence gate. The
    transition validator builds `expected` from the proposal and now forces
    declare_mode="strict"; a sealed state that kept best_effort must be a mismatch."""
    campaign_instance_id = "0" * 32
    proposal_state = {
        l0.CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
        "declare_mode": "best_effort",
        "final_status": l0.CANDIDATE_PROPOSED_STATUS,
        "final_result": {"search_status": l0.CANDIDATE_PROPOSED_STATUS},
        "last_stop_reason": {
            "reason": l0.TERMINAL_CERTIFIED_REASON,
            "status": l0.CANDIDATE_PROPOSED_STATUS,
            "updated_at": "2026-01-01T00:00:00Z",
        },
        l0.SUPERVISOR_PROPOSAL_STATE_KEY: {
            "schema_version": l0.SUPERVISOR_PROPOSAL_STATE_SCHEMA_VERSION,
            "authority": l0.PROPOSAL_READY_MARKER_AUTHORITY,
            "run_id": "run-1",
            l0.CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
        },
    }
    seal_record = {
        "proposal_run_id": "run-1",
        l0.CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
    }
    certified_state = dict(proposal_state)
    certified_state["final_status"] = "CERTIFIED"
    certified_state["declare_mode"] = "strict"
    certified_state["final_result"] = {"search_status": "CERTIFIED"}
    certified_state["last_stop_reason"] = {
        "reason": l0.TERMINAL_CERTIFIED_REASON,
        "status": "CERTIFIED",
        "updated_at": "2026-01-01T00:00:01Z",
    }
    certified_state["updated_at"] = "2026-01-01T00:00:01Z"
    certified_state.pop(l0.SUPERVISOR_PROPOSAL_STATE_KEY)
    certified_state[l0.SUPERVISOR_SEAL_STATE_KEY] = dict(seal_record)

    # producer declare_mode="best_effort" -> durable "strict" is the accepted transition
    assert (
        l0._supervisor_certified_transition_violation_l0(
            proposal_state=proposal_state,
            certified_state=certified_state,
            seal_record=seal_record,
        )
        is None
    )

    # a sealed state that persisted the producer's non-strict declare_mode is rejected
    regressed_state = dict(certified_state)
    regressed_state["declare_mode"] = "best_effort"
    assert (
        l0._supervisor_certified_transition_violation_l0(
            proposal_state=proposal_state,
            certified_state=regressed_state,
            seal_record=seal_record,
        )
        == "supervisor_seal_transition_mismatch"
    )


def test_l0_supervisor_seal_mints_strict_declare_mode_from_best_effort_proposal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    campaign_path = project_root / "data" / "checkpoints" / "exact_campaign_state.json"
    marker_path = campaign_path.with_name(f"{campaign_path.stem}.proposal_ready.json")
    campaign_path.parent.mkdir(parents=True)
    campaign_instance_id = "1" * 32
    run_id = "pr2-5-strict-mint"
    authority_state = {
        l0.CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
        "declare_mode": "best_effort",
        "final_status": l0.CANDIDATE_PROPOSED_STATUS,
        "final_result": {"search_status": l0.CANDIDATE_PROPOSED_STATUS},
        "terminal_frontier_evidence": {"candidate_generation": {"domain_authority": "test"}},
        "candidates": {},
        l0.SUPERVISOR_PROPOSAL_STATE_KEY: {
            "schema_version": l0.SUPERVISOR_PROPOSAL_STATE_SCHEMA_VERSION,
            "authority": l0.PROPOSAL_READY_MARKER_AUTHORITY,
            "run_id": run_id,
            l0.CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
        },
    }
    checkpoint_bytes = l0._atomic_json_bytes(authority_state)  # type: ignore[attr-defined]
    campaign_path.write_bytes(checkpoint_bytes)
    marker = {
        "schema_version": l0.PROPOSAL_READY_MARKER_SCHEMA_VERSION,
        "authority": l0.PROPOSAL_READY_MARKER_AUTHORITY,
        "run_id": run_id,
        "exit_code": 0,
        "checkpoint_sha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
        l0.CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
    }
    marker_path.write_bytes(l0._atomic_json_bytes(marker))  # type: ignore[attr-defined]

    monkeypatch.setattr(
        l0,
        "_load_canonical_dependency_floor_manifest",
        lambda _source_root: {"test_dependency_floor": True},
    )

    def sealed_child(payload: dict[str, object], **_kwargs: object) -> l0.L0MicroVerdict:
        child_authority = payload["authority_state"]
        assert isinstance(child_authority, dict)
        assert child_authority["declare_mode"] == "best_effort"
        certified_final_result = dict(child_authority["final_result"])  # type: ignore[arg-type]
        certified_final_result["search_status"] = "CERTIFIED"
        domain = {
            "schema_version": l0.SUPERVISOR_DOMAIN_SCHEMA_VERSION,
            "authority": l0.SUPERVISOR_DOMAIN_AUTHORITY,
            "nonce": "child-nonce",
            "verdict": l0.SEALED,
            "reason": "test-domain-sealed",
            "strong_keys": [],
            "final_result": certified_final_result,
            "terminal_frontier_evidence": dict(child_authority["terminal_frontier_evidence"]),  # type: ignore[arg-type]
            "candidate_records": {},
            "final_result_digest": payload["proposal_final_result_digest"],
            "terminal_frontier_evidence_digest": payload[
                "proposal_terminal_frontier_evidence_digest"
            ],
            "candidate_records_digest": payload["proposal_candidate_records_digest"],
            "fixed_witness_publishable": True,
            "sink_replay_violations": {},
            "fixed_witness_violations": {},
            "tcb": {"test": "stubbed_child"},
        }
        return l0.L0MicroVerdict(
            status=l0.SEALED,
            nonce="child-nonce",
            reason="domain_verified",
            floor_digest="f" * 64,
            response={"domain": domain},
        )

    monkeypatch.setattr(l0, "run_l0_micro_verifier_round_trip", sealed_child)

    verdict = l0.run_l0_supervisor_seal(
        l0.L0SupervisorSealRequest(
            project_root=project_root,
            campaign_path=campaign_path,
            marker_path=marker_path,
            expected_campaign_instance_id=campaign_instance_id,
        )
    )

    assert verdict.status == l0.SEALED, verdict.reason
    durable_state = json.loads(campaign_path.read_text(encoding="utf-8"))
    assert durable_state["declare_mode"] == "strict"
    assert durable_state["final_status"] == "CERTIFIED"
    assert durable_state["final_result"]["search_status"] == "CERTIFIED"
    assert l0.SUPERVISOR_PROPOSAL_STATE_KEY not in durable_state
    assert not marker_path.exists()


def test_l0_postwrite_state_violation_rejects_non_strict_declare_mode() -> None:
    disk_state = {"declare_mode": "best_effort"}
    expected_payload_sha = l0._certified_state_payload_sha256_l0(disk_state)  # type: ignore[attr-defined]

    assert (
        l0._postwrite_state_violation(  # type: ignore[attr-defined]
            disk_state,
            expected_domain={},
            expected_payload_sha=expected_payload_sha,
        )
        == "postwrite_declare_mode_not_strict"
    )


def test_exact_campaign_supervisor_transition_promotes_declare_mode_to_strict() -> None:
    campaign_instance_id = "2" * 32
    proposal_state = {
        exact_campaign_module.CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
        "declare_mode": "best_effort",
        "final_status": exact_campaign_module.CANDIDATE_PROPOSED_STATUS,
        "final_result": {"search_status": exact_campaign_module.CANDIDATE_PROPOSED_STATUS},
        "last_stop_reason": {
            "reason": exact_campaign_module.TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
            "status": exact_campaign_module.CANDIDATE_PROPOSED_STATUS,
            "updated_at": "2026-01-01T00:00:00Z",
        },
        exact_campaign_module.SUPERVISOR_PROPOSAL_STATE_KEY: {
            "schema_version": exact_campaign_module.SUPERVISOR_PROPOSAL_STATE_SCHEMA_VERSION,
            "authority": exact_campaign_module.PROPOSAL_READY_MARKER_AUTHORITY,
            "run_id": "run-1",
            exact_campaign_module.CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
        },
    }
    seal_record = {
        "proposal_run_id": "run-1",
        exact_campaign_module.CAMPAIGN_INSTANCE_ID_KEY: campaign_instance_id,
    }
    certified_state = dict(proposal_state)
    certified_state["final_status"] = "CERTIFIED"
    certified_state["declare_mode"] = "strict"
    certified_state["final_result"] = {"search_status": "CERTIFIED"}
    certified_state["last_stop_reason"] = {
        "reason": exact_campaign_module.TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        "status": "CERTIFIED",
        "updated_at": "2026-01-01T00:00:01Z",
    }
    certified_state["updated_at"] = "2026-01-01T00:00:02Z"
    certified_state.pop(exact_campaign_module.SUPERVISOR_PROPOSAL_STATE_KEY)
    certified_state[exact_campaign_module.SUPERVISOR_SEAL_STATE_KEY] = dict(seal_record)

    assert (
        exact_campaign_module._supervisor_certified_transition_violation(  # type: ignore[attr-defined]
            proposal_state=proposal_state,
            certified_state=certified_state,
            seal_record=seal_record,
        )
        is None
    )

    regressed_state = dict(certified_state)
    regressed_state["declare_mode"] = "best_effort"
    assert (
        exact_campaign_module._supervisor_certified_transition_violation(  # type: ignore[attr-defined]
            proposal_state=proposal_state,
            certified_state=regressed_state,
            seal_record=seal_record,
        )
        == "supervisor_seal_transition_mismatch"
    )


def test_true_verifier_child_precheck_receives_strict_certified_scratch_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.search import pr2_l0_artifact_core as artifact_core_module
    from src.search import pr2_l0_frontier_core as frontier_core_module

    candidate_generation = {"domain_authority": "test_child_precheck"}
    proposal_evidence = {"candidate_generation": candidate_generation}
    certified_evidence = {
        "candidate_generation": candidate_generation,
        "candidate_records": {},
        "final_result": {"search_status": "CERTIFIED"},
    }
    authority_state = {
        "final_result": {"search_status": l0.CANDIDATE_PROPOSED_STATUS},
        "final_status": l0.CANDIDATE_PROPOSED_STATUS,
        "terminal_frontier_evidence": proposal_evidence,
        "candidates": {},
        "supervisor_proposal": {"run_id": "producer-owned"},
    }
    certified_final_result = {"search_status": "CERTIFIED"}
    authority_bytes = json.dumps(
        authority_state,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    captured: dict[str, object] = {}

    monkeypatch.setattr(true_child, "_materialize_import_default_artifacts", lambda _root: None)
    monkeypatch.setattr(
        true_child,
        "_project_candidate_records_direct",
        lambda **_kwargs: ({}, {}),
    )
    monkeypatch.setattr(
        true_child,
        "_run_fixed_witness_direct",
        lambda **_kwargs: ({}, {}, SimpleNamespace(publishable=True)),
    )
    monkeypatch.setattr(
        frontier_core_module,
        "candidate_generation_kwargs",
        lambda _candidate_generation: {},
    )
    monkeypatch.setattr(frontier_core_module, "generate_candidate_sizes", lambda **_kwargs: [])
    monkeypatch.setattr(
        frontier_core_module,
        "build_terminal_frontier_evidence",
        lambda **_kwargs: certified_evidence,
    )

    def capture_precheck(state: object, *, project_root: Path) -> None:
        captured["state"] = state
        captured["project_root"] = project_root
        return None

    monkeypatch.setattr(
        artifact_core_module,
        "terminal_certified_final_result_project_precheck_violation",
        capture_precheck,
    )
    monkeypatch.setattr(
        artifact_core_module,
        "canonical_candidate_geometry_rederivation_violation",
        lambda *, project_root: None,
    )
    payload = {
        "action": "supervisor_domain",
        "schema_version": true_child.DOMAIN_SCHEMA_VERSION,
        "authority": true_child.DOMAIN_AUTHORITY,
        "project_root": str(tmp_path),
        "authority_state": authority_state,
        "authority_state_b64": base64.b64encode(authority_bytes).decode("ascii"),
        "strong_keys": [],
        "proposal_final_result_digest": true_child._canonical_digest(certified_final_result),  # type: ignore[attr-defined]
        "proposal_terminal_frontier_evidence_digest": true_child._canonical_digest(certified_evidence),  # type: ignore[attr-defined]
        "proposal_candidate_records_digest": true_child._canonical_digest({}),  # type: ignore[attr-defined]
        "dependency_floor": {"test": "unused-by-direct-call"},
    }

    domain = true_child._verify_supervisor_domain(payload, nonce="nonce")  # type: ignore[attr-defined]

    scratch_state = captured["state"]
    assert isinstance(scratch_state, dict)
    assert captured["project_root"] == tmp_path.resolve()
    assert scratch_state["final_status"] == "CERTIFIED"
    assert scratch_state["declare_mode"] == "strict"
    assert scratch_state["last_stop_reason"] == {
        "reason": exact_campaign_module.TERMINAL_FULL_FRONTIER_CERTIFIED_REASON,
        "status": "CERTIFIED",
    }
    assert "supervisor_proposal" not in scratch_state
    assert domain["verdict"] == true_child.SEALED


def test_true_verifier_child_verify_rejects_geometry_rederivation_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.search import pr2_l0_artifact_core as artifact_core_module
    from src.search import pr2_l0_frontier_core as frontier_core_module

    candidate_generation = {"domain_authority": "test_child_geometry_gate"}
    proposal_evidence = {"candidate_generation": candidate_generation}
    certified_evidence = {
        "candidate_generation": candidate_generation,
        "candidate_records": {},
        "final_result": {"search_status": "CERTIFIED"},
    }
    authority_state = {
        "final_result": {"search_status": l0.CANDIDATE_PROPOSED_STATUS},
        "final_status": l0.CANDIDATE_PROPOSED_STATUS,
        "terminal_frontier_evidence": proposal_evidence,
        "candidates": {},
        "supervisor_proposal": {"run_id": "producer-owned"},
    }
    certified_final_result = {"search_status": "CERTIFIED"}
    authority_bytes = json.dumps(
        authority_state,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    monkeypatch.setattr(true_child, "_install_third_party_floor", lambda _floor: None)
    monkeypatch.setattr(true_child, "_materialize_import_default_artifacts", lambda _root: None)
    monkeypatch.setattr(
        true_child,
        "_project_candidate_records_direct",
        lambda **_kwargs: ({}, {}),
    )
    monkeypatch.setattr(
        true_child,
        "_run_fixed_witness_direct",
        lambda **_kwargs: ({}, {}, SimpleNamespace(publishable=True)),
    )
    monkeypatch.setattr(
        frontier_core_module,
        "candidate_generation_kwargs",
        lambda _candidate_generation: {},
    )
    monkeypatch.setattr(frontier_core_module, "generate_candidate_sizes", lambda **_kwargs: [])
    monkeypatch.setattr(
        frontier_core_module,
        "build_terminal_frontier_evidence",
        lambda **_kwargs: certified_evidence,
    )
    monkeypatch.setattr(
        artifact_core_module,
        "terminal_certified_final_result_project_precheck_violation",
        lambda _state, *, project_root: None,
    )
    monkeypatch.setattr(
        artifact_core_module,
        "canonical_candidate_geometry_rederivation_violation",
        lambda *, project_root: "canonical_candidate_geometry_rederivation_mismatch",
    )
    payload = {
        "action": "supervisor_domain",
        "schema_version": true_child.DOMAIN_SCHEMA_VERSION,
        "authority": true_child.DOMAIN_AUTHORITY,
        "project_root": str(tmp_path),
        "authority_state": authority_state,
        "authority_state_b64": base64.b64encode(authority_bytes).decode("ascii"),
        "strong_keys": [],
        "proposal_final_result_digest": true_child._canonical_digest(certified_final_result),  # type: ignore[attr-defined]
        "proposal_terminal_frontier_evidence_digest": true_child._canonical_digest(certified_evidence),  # type: ignore[attr-defined]
        "proposal_candidate_records_digest": true_child._canonical_digest({}),  # type: ignore[attr-defined]
        "dependency_floor": {"test": "unused-by-patched-install"},
    }

    response = true_child.verify({"nonce": "nonce", "payload": payload})

    assert response["verdict"] == true_child.REJECTED
    assert (
        "terminal candidate geometry rederivation failed:"
        "canonical_candidate_geometry_rederivation_mismatch"
    ) in response["reason"]
