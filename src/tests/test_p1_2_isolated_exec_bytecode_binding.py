"""P1.2 PYC-EXEC-DIGEST regressions for certified isolated children."""

from __future__ import annotations

import importlib._bootstrap_external as importlib_external
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import src.search.candidate_proof_replay as candidate_replay_module
import src.search.terminal_fixed_witness_capsule as capsule_module
from scripts import check_p1_2_proof_obligations


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _assert_hardened_argv(argv: list[str]) -> Path:
    isolated_index = argv.index("-I")
    no_bytecode_index = argv.index("-B")
    x_index = argv.index("-X")
    assert isolated_index < no_bytecode_index < x_index
    assert x_index + 1 < len(argv)
    prefix_arg = argv[x_index + 1]
    assert prefix_arg.startswith("pycache_prefix=")
    pycache_prefix = Path(prefix_arg.removeprefix("pycache_prefix="))
    assert pycache_prefix.is_dir()
    assert list(pycache_prefix.iterdir()) == []
    assert "__pycache__" not in pycache_prefix.parts
    assert not _is_relative_to(pycache_prefix, PROJECT_ROOT)
    return pycache_prefix


def test_candidate_replay_isolated_subprocess_uses_fresh_pycache_prefix(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured["prefix"] = _assert_hardened_argv(argv)
        request = json.loads(kwargs["input"])
        response = {"nonce": request["nonce"]}
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=json.dumps(response) + "\n",
            stderr="",
        )

    monkeypatch.setattr(candidate_replay_module.subprocess, "run", fake_run)

    candidate_replay_module._invoke_isolated_replay(
        project_root=tmp_path,
        expected_proofs={"1x1": {"candidate": {"key": "1x1", "w": 1, "h": 1, "area": 1}}},
    )

    assert "-B" in captured["argv"]
    assert not captured["prefix"].exists()


def test_fixed_witness_capsule_isolated_subprocess_uses_fresh_pycache_prefix(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured["prefix"] = _assert_hardened_argv(argv)
        request = json.loads(kwargs["input"])
        response = {"nonce": request["nonce"]}
        return subprocess.CompletedProcess(
            args=argv,
            returncode=0,
            stdout=json.dumps(response) + "\n",
            stderr="",
        )

    monkeypatch.setattr(capsule_module.subprocess, "run", fake_run)

    capsule_module._invoke_isolated_capsule(
        project_root=tmp_path,
        authority_state={},
        expected_artifact_hashes={},
        expected_source_digest="0" * 64,
        nonce="test-nonce",
    )

    assert "-B" in captured["argv"]
    assert not captured["prefix"].exists()


def test_isolated_replay_ignores_repo_pycache_bytecode_injection(tmp_path: Path) -> None:
    source_root = tmp_path / "repo"
    source_root.mkdir()
    module_path = source_root / "victim.py"
    source_bytes = b"VALUE = 'SOURCE'\n"
    module_path.write_bytes(source_bytes)
    stat = module_path.stat()

    pycache_dir = source_root / "__pycache__"
    pycache_dir.mkdir()
    cache_tag = sys.implementation.cache_tag
    assert cache_tag is not None
    pyc_path = pycache_dir / f"victim.{cache_tag}.pyc"
    evil_code = compile("VALUE = 'MALICIOUS'\n", str(module_path), "exec")
    pyc_path.write_bytes(
        importlib_external._code_to_timestamp_pyc(
            evil_code,
            int(stat.st_mtime),
            len(source_bytes),
        )
    )

    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(sys.argv[1]).resolve()))\n"
        "import victim\n"
        "print(victim.VALUE)\n"
    )
    unsafe = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(source_root)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert unsafe.returncode == 0, unsafe.stderr
    assert unsafe.stdout.strip() == "MALICIOUS"

    pycache_prefix = Path(tempfile.mkdtemp(prefix="zmd_test_pycache_prefix_"))
    try:
        hardened = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-X",
                f"pycache_prefix={pycache_prefix}",
                "-c",
                script,
                str(source_root),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert hardened.returncode == 0, hardened.stderr
        assert hardened.stdout.strip() == "SOURCE"
        assert list(pycache_prefix.rglob("*")) == []
    finally:
        shutil.rmtree(pycache_prefix, ignore_errors=True)


def test_p1_2_checker_rejects_isolated_exec_bytecode_binding_removal(
    tmp_path: Path,
) -> None:
    candidate_path = tmp_path / "candidate_proof_replay.py"
    candidate_source = check_p1_2_proof_obligations.CANDIDATE_PROOF_REPLAY_PATH.read_text(
        encoding="utf-8"
    )
    candidate_path.write_text(
        candidate_source.replace('                "-B",\n', "", 1),
        encoding="utf-8",
    )
    candidate_errors = check_p1_2_proof_obligations._check_isolated_exec_bytecode_binding_contract(
        candidate_replay_path=candidate_path,
    )
    assert any("candidate replay" in error and "-B" in error for error in candidate_errors)

    fake_executable_path = tmp_path / "candidate_proof_replay_fake_executable.py"
    fake_executable_path.write_text(
        candidate_source.replace("                str(executable),", '                "python",', 1),
        encoding="utf-8",
    )
    fake_executable_errors = (
        check_p1_2_proof_obligations._check_isolated_exec_bytecode_binding_contract(
            candidate_replay_path=fake_executable_path,
        )
    )
    assert (
        "candidate replay argv executable must be derived from sys.executable"
        in fake_executable_errors
    )

    fake_prefix_path = tmp_path / "candidate_proof_replay_fake_prefix.py"
    fake_prefix_path.write_text(
        candidate_source.replace(
            '                f"pycache_prefix={pycache_prefix_dir}",',
            '                "pycache_prefix=/tmp/not_mkdtemp",',
            1,
        ),
        encoding="utf-8",
    )
    fake_prefix_errors = (
        check_p1_2_proof_obligations._check_isolated_exec_bytecode_binding_contract(
            candidate_replay_path=fake_prefix_path,
        )
    )
    assert (
        "candidate replay pycache_prefix argv must use the tempfile.mkdtemp directory"
        in fake_prefix_errors
    )

    capsule_path = tmp_path / "terminal_fixed_witness_capsule.py"
    capsule_source = check_p1_2_proof_obligations.TERMINAL_FIXED_WITNESS_CAPSULE_PATH.read_text(
        encoding="utf-8"
    )
    capsule_path.write_text(
        capsule_source.replace('                f"pycache_prefix={pycache_prefix_dir}",\n', "", 1),
        encoding="utf-8",
    )
    assert capsule_path.exists()
    capsule_errors = check_p1_2_proof_obligations._check_isolated_exec_bytecode_binding_contract(
        candidate_replay_path=check_p1_2_proof_obligations.CANDIDATE_PROOF_REPLAY_PATH,
        terminal_capsule_path=capsule_path,
    )
    assert any("fixed-witness capsule" in error and "pycache_prefix" in error for error in capsule_errors)
