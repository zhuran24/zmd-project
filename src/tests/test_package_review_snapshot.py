from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import package_review_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git is required for package review snapshot tests")
    _git(repo, "init")
    _git(repo, "config", "user.name", "Package Test")
    _git(repo, "config", "user.email", "package-test@example.invalid")


def _commit_all(repo: Path) -> None:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")


def test_package_review_snapshot_default_targeted_tests_exist() -> None:
    for rel_path in package_review_snapshot.DEFAULT_TARGETED_TESTS:
        assert (PROJECT_ROOT / rel_path).exists(), rel_path


def test_package_review_snapshot_excludes_agent_memory_and_review_packets() -> None:
    cases = {
        "AGENTS.md": "agent_instruction_file",
        "docs/sub/CLAUDE.md": "agent_instruction_file",
        "cc_memory/memory.db": "excluded_package_prefix",
        "docs/external_review/old_packet.md": "old_review_packet_path",
        "notes/review_request.md": "prompt_like_path",
        "archives/pr1.7z": "archive_path",
    }
    for rel_path, reason in cases.items():
        assert package_review_snapshot._package_exclusion_reason(rel_path) == reason

    assert (
        package_review_snapshot._package_exclusion_reason(
            "notes/review_notes.md",
            b"Please use the Sources tab and Package SHA256 line for this review request.",
        )
        == "prompt_like_content"
    )
    assert package_review_snapshot._package_exclusion_reason(
        "src/render/review_status.py",
        b"REVIEW_ANCHOR = 'not a prompt transcript'",
    ) is None


def test_package_review_snapshot_binds_commit_tree_and_dirty_state(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "package_review_snapshot.py").write_text("print('package')\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("VALUE = 'committed'\n", encoding="utf-8")
    (repo / "docs" / "项目说明").mkdir(parents=True)
    (repo / "docs" / "项目说明" / "soundness_gap_roadmap.md").write_text("sentinel\n", encoding="utf-8")
    (repo / "AGENTS.md").write_text("<INSTRUCTIONS>agent rules</INSTRUCTIONS>\n", encoding="utf-8")
    (repo / "cc_memory").mkdir()
    (repo / "cc_memory" / "memory.db").write_bytes(b"sqlite")
    (repo / "docs" / "external_review").mkdir()
    (repo / "docs" / "external_review" / "old.md").write_text("old review packet\n", encoding="utf-8")
    _commit_all(repo)

    (repo / "src" / "app.py").write_text("VALUE = 'dirty worktree'\n", encoding="utf-8")
    provenance = package_review_snapshot._git_commit_metadata(repo, "HEAD")

    assert provenance["packaged_equals_head"] is True
    assert provenance["working_tree_dirty"] is True
    assert provenance["dirty_guarded_paths"] == ["src/app.py"]
    assert provenance["dirty_changes_included"] is False

    destination = tmp_path / "stage"
    destination.mkdir()
    inventory, excluded = package_review_snapshot._materialize_tree(repo, destination, "HEAD")
    inventory_paths = {str(item["path"]) for item in inventory}
    excluded_paths = {item["path"]: item["reason"] for item in excluded}

    assert "src/app.py" in inventory_paths
    assert "AGENTS.md" not in inventory_paths
    assert excluded_paths["AGENTS.md"] == "agent_instruction_file"
    assert excluded_paths["cc_memory/memory.db"] == "excluded_package_prefix"
    assert excluded_paths["docs/external_review/old.md"] == "old_review_packet_path"
    assert (destination / "src" / "app.py").read_text(encoding="utf-8") == "VALUE = 'committed'\n"

    manifest = package_review_snapshot._build_embedded_manifest(
        repo_root=repo,
        treeish="HEAD",
        provenance=provenance,
        inventory=inventory,
        excluded=excluded,
        verification=[
            {
                "kind": "proof_checker",
                "command": ["python", "scripts/check_p1_2_proof_obligations.py"],
                "exit_code": 0,
                "summary": "proof obligations OK",
            },
            {
                "kind": "targeted_pytest",
                "command": ["python", "-m", "pytest", *package_review_snapshot.DEFAULT_TARGETED_TESTS, "-q"],
                "exit_code": 0,
                "summary": "284 passed",
                "env": {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
            }
        ],
        targeted_tests_skipped=False,
    )
    assert manifest["source"] == "committed_git_tree"
    assert manifest["inventory_sha256"] == package_review_snapshot._inventory_digest(inventory)


def test_package_review_snapshot_embedded_manifest_records_verification_receipt(tmp_path: Path) -> None:
    inventory = [
        {
            "path": "src/app.py",
            "mode": "100644",
            "git_blob_oid": "a" * 40,
            "size": 12,
            "content_sha256": "b" * 64,
        }
    ]
    verification = [
        {
            "kind": "proof_checker",
            "command": ["python", "scripts/check_p1_2_proof_obligations.py"],
            "exit_code": 0,
            "summary": "proof obligations OK",
        },
        {
            "kind": "targeted_pytest",
            "command": ["python", "-m", "pytest", *package_review_snapshot.DEFAULT_TARGETED_TESTS, "-q"],
            "exit_code": 0,
            "summary": "284 passed",
            "env": {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        },
    ]

    manifest = package_review_snapshot._build_embedded_manifest(
        repo_root=tmp_path,
        treeish="HEAD",
        provenance={"packaged_equals_head": True},
        inventory=inventory,
        excluded=[],
        verification=verification,
        targeted_tests_skipped=False,
    )

    assert manifest["targeted_tests_skipped"] is False
    assert manifest["verification"] == verification
    assert manifest["inventory_sha256"] == package_review_snapshot._inventory_digest(inventory)


def test_package_review_snapshot_skip_tests_marker_is_embedded(tmp_path: Path) -> None:
    skip_receipt = [
        {
            "kind": "proof_checker",
            "command": ["python", "scripts/check_p1_2_proof_obligations.py"],
            "exit_code": 0,
            "summary": "proof obligations OK",
        },
        {
            "kind": "targeted_pytest",
            "command": ["python", "-m", "pytest", *package_review_snapshot.DEFAULT_TARGETED_TESTS, "-q"],
            "skipped": True,
            "skip_reason": "--skip-tests",
            "env": {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        }
    ]

    manifest = package_review_snapshot._build_embedded_manifest(
        repo_root=tmp_path,
        treeish="HEAD",
        provenance={"packaged_equals_head": True},
        inventory=[],
        excluded=[],
        verification=skip_receipt,
        targeted_tests_skipped=True,
    )

    assert manifest["targeted_tests_skipped"] is True
    assert manifest["verification"][1]["skipped"] is True
    assert manifest["verification"][1]["skip_reason"] == "--skip-tests"

    with pytest.raises(RuntimeError, match="missing --skip-tests marker"):
        package_review_snapshot._build_embedded_manifest(
            repo_root=tmp_path,
            treeish="HEAD",
            provenance={"packaged_equals_head": True},
            inventory=[],
            excluded=[],
            verification=skip_receipt[:1],
            targeted_tests_skipped=True,
        )


def test_package_review_snapshot_rejects_partial_or_unhermetic_receipt() -> None:
    proof_ok = {
        "kind": "proof_checker",
        "command": ["python", "scripts/check_p1_2_proof_obligations.py"],
        "exit_code": 0,
        "summary": "proof obligations OK",
    }
    full_env = {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    # right shape but a partial command (single test file) is NOT acceptable proof
    partial = [
        proof_ok,
        {
            "kind": "targeted_pytest",
            "command": ["python", "-m", "pytest", "src/tests/test_delivery_manifest.py", "-q"],
            "exit_code": 0,
            "summary": "39 passed",
            "env": full_env,
        },
    ]
    with pytest.raises(RuntimeError, match="full DEFAULT_TARGETED_TESTS"):
        package_review_snapshot._validate_embedded_verification(partial, targeted_tests_skipped=False)
    # full command but missing hermetic plugin-autoload isolation is NOT acceptable proof
    unhermetic = [
        proof_ok,
        {
            "kind": "targeted_pytest",
            "command": ["python", "-m", "pytest", *package_review_snapshot.DEFAULT_TARGETED_TESTS, "-q"],
            "exit_code": 0,
            "summary": "284 passed",
        },
    ]
    with pytest.raises(RuntimeError, match="full DEFAULT_TARGETED_TESTS"):
        package_review_snapshot._validate_embedded_verification(unhermetic, targeted_tests_skipped=False)
    # forged: contains every required token but does not actually invoke pytest (python -c shim)
    forged_shim = [
        proof_ok,
        {
            "kind": "targeted_pytest",
            "command": [
                "python",
                "-c",
                "print('no tests')",
                "pytest",
                *package_review_snapshot.DEFAULT_TARGETED_TESTS,
                "-q",
            ],
            "exit_code": 0,
            "summary": "284 passed",
            "env": full_env,
        },
    ]
    with pytest.raises(RuntimeError, match="full DEFAULT_TARGETED_TESTS"):
        package_review_snapshot._validate_embedded_verification(forged_shim, targeted_tests_skipped=False)
    # --collect-only lists every path without running the tests
    collect_only = [
        proof_ok,
        {
            "kind": "targeted_pytest",
            "command": ["python", "-m", "pytest", *package_review_snapshot.DEFAULT_TARGETED_TESTS, "--collect-only"],
            "exit_code": 0,
            "summary": "collected 284",
            "env": full_env,
        },
    ]
    with pytest.raises(RuntimeError, match="full DEFAULT_TARGETED_TESTS"):
        package_review_snapshot._validate_embedded_verification(collect_only, targeted_tests_skipped=False)
    # the canonical full + hermetic receipt passes
    good = [
        proof_ok,
        {
            "kind": "targeted_pytest",
            "command": ["python", "-m", "pytest", *package_review_snapshot.DEFAULT_TARGETED_TESTS, "-q"],
            "exit_code": 0,
            "summary": "284 passed",
            "env": full_env,
        },
    ]
    package_review_snapshot._validate_embedded_verification(good, targeted_tests_skipped=False)


def test_package_review_snapshot_selftest_disables_pytest_plugin_autoload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seen_envs: list[dict[str, str]] = []

    def fake_run(
        args: list[str],
        *,
        cwd: Path,
        capture: bool = True,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        assert cwd == tmp_path
        assert capture is True
        assert env is not None
        seen_envs.append(dict(env))
        output = "39 passed\n" if "-m" in args else "proof obligations OK\n"
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=output)

    monkeypatch.setattr(package_review_snapshot, "_run", fake_run)

    receipt = package_review_snapshot._run_review_selftests(tmp_path, skip_tests=False)

    assert len(seen_envs) == 2
    assert {env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] for env in seen_envs} == {"1"}
    assert receipt[0]["kind"] == "proof_checker"
    assert receipt[1]["kind"] == "targeted_pytest"
    assert receipt[1]["env"] == {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
