from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

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


def test_l0_default_dependency_floor_manifest_auto_generates_to_configured_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path = tmp_path / "generated_manifest.json"
    monkeypatch.setattr(l0, "DEPENDENCY_FLOOR_MANIFEST_REL", str(manifest_path))
    source_root = Path(l0.__file__).resolve().parents[2]

    dependency_floor = l0._load_canonical_dependency_floor_manifest(source_root)

    assert manifest_path.is_file()
    assert Path(str(dependency_floor["floor_root"])).is_dir()
    assert dependency_floor["files"]


def test_l0_dependency_floor_blocks_floor_out_site_package_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    host_dependency_floor_manifest_path: Path,
) -> None:
    dependency_floor = l0._load_dependency_floor_manifest(host_dependency_floor_manifest_path)
    floor_root = Path(str(dependency_floor["floor_root"])).resolve()
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
