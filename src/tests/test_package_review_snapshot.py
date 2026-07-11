from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
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


def _git_out(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ).stdout.strip()


def test_package_review_snapshot_default_targeted_tests_exist() -> None:
    for rel_path in package_review_snapshot.DEFAULT_TARGETED_TESTS:
        assert (PROJECT_ROOT / rel_path).exists(), rel_path


def test_package_review_snapshot_excludes_agent_memory_and_review_packets() -> None:
    cases = {
        "docs/external_review/old_packet.md": "old_review_packet_path",
        "notes/review_request.md": "prompt_like_path",
        "archives/pr1.7z": "archive_path",
        # Tool runtime config / live scratch stay excluded (transient, not reviewed docs).
        ".claude/settings.local.json": "excluded_package_prefix",
        "cc_context/scratch.md": "excluded_package_prefix",
    }
    for rel_path, reason in cases.items():
        assert package_review_snapshot._package_exclusion_reason(rel_path) == reason

    # Owner ruling 2026-07-12: agent instruction files and the two persistent memory
    # subsystems are REVIEWABLE surface (repo contents exportable by default; genuinely
    # sensitive material never enters the repo). Pin the inclusion so a future "helpful"
    # re-exclusion is a visible decision, not a silent regression.
    for rel_path in (
        "AGENTS.md",
        "docs/sub/CLAUDE.md",
        "cc_memory/memory.db",
        "cc_memory/exports/MEMORY.md",
        "cc_memory_vnext/cards/deliberate-insider-hardening-deferred-to-release.md",
        "cc_memory_vnext/.index/frame.json",
    ):
        assert package_review_snapshot._package_exclusion_reason(rel_path) is None

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
    # regression: a legit source .py with review/packet in its path must NOT be content-sniffed as a
    # prompt, even when it embeds marker strings as test data. The package's own test was wrongly
    # excluded this way, dropping obligation-required symbols from the snapshot and failing the build.
    assert package_review_snapshot._package_exclusion_reason(
        "src/tests/test_package_review_snapshot.py",
        b"assert 'Package SHA256' in body  # exercises the 'review request' prompt marker",
    ) is None
    assert package_review_snapshot._package_exclusion_reason(
        "scripts/phase3b/b5a/build_review_packet.py",
        b"def build():  # source module that builds a phase3b review packet",
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
    # Owner ruling 2026-07-12: agent instruction files are reviewable surface.
    assert "AGENTS.md" in inventory_paths
    assert "AGENTS.md" not in excluded_paths
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


def test_package_review_snapshot_records_renamed_dirty_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "package_review_snapshot.py").write_text("print('package')\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "original.txt").write_text("committed docs\n", encoding="utf-8")
    (repo / "src").mkdir()
    _commit_all(repo)

    _git(repo, "mv", "docs/original.txt", "src/renamed.py")

    status_entries = package_review_snapshot._git_status_entries(repo)
    provenance = package_review_snapshot._git_commit_metadata(repo, "HEAD")

    assert status_entries == [
        {"status": "R ", "path": "src/renamed.py", "orig_path": "docs/original.txt"}
    ]
    assert provenance["working_tree_dirty"] is True
    assert provenance["dirty_paths"] == ["docs/original.txt", "src/renamed.py"]
    assert provenance["dirty_guarded_paths"] == ["src/renamed.py"]
    assert provenance["dirty_changes_included"] is False


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


def test_package_review_snapshot_ref_move_after_resolve_keeps_packaged_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression pin for the resolve-once TOCTOU contract in build_package(): the caller-supplied
    # (possibly mutable) treeish is resolved to an immutable commit ONCE, and that same resolved
    # commit must feed provenance, the manifest treeish field, and tree materialization. A ref that
    # moves inside the window between provenance resolution and materialization must not split the
    # archived bytes from the recorded packaged_commit.
    try:
        package_review_snapshot._find_7z()
    except Exception:
        pytest.skip("7z is required for the packaging TOCTOU regression test")

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "package_review_snapshot.py").write_text("print('package')\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("VALUE = 'committed'\n", encoding="utf-8")
    sentinel = repo / Path(*str(package_review_snapshot.PROJECT_DOC_SENTINEL).split("/"))
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("sentinel\n", encoding="utf-8")
    _commit_all(repo)
    _git(repo, "checkout", "-b", "movable")
    resolved = _git_out(repo, "rev-parse", "--verify", "movable^{commit}")
    committed_app_sha = hashlib.sha256(b"VALUE = 'committed'\n").hexdigest()

    captured: dict[str, object] = {}
    real_materialize = package_review_snapshot._materialize_tree

    def _move_ref_then_materialize(repo_root: Path, destination: Path, treeish: str):
        # The concurrent ref move lands exactly inside the historical TOCTOU window: after
        # build_package() resolved provenance, before bytes are archived.
        (repo / "src" / "app.py").write_text("VALUE = 'after ref move'\n", encoding="utf-8")
        _git(repo, "add", ".")
        _git(repo, "commit", "-m", "concurrent ref move")
        inventory, excluded = real_materialize(repo_root, destination, treeish)
        captured["treeish"] = treeish
        captured["inventory"] = inventory
        return inventory, excluded

    def _fake_selftests(stage_root: Path, *, skip_tests: bool) -> list[dict[str, object]]:
        assert skip_tests is True
        env = {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        return [
            {
                "kind": "proof_checker",
                "command": [sys.executable, "scripts/check_p1_2_proof_obligations.py"],
                "exit_code": 0,
                "summary": "proof obligations OK",
                "env": env,
            },
            {
                "kind": "targeted_pytest",
                "command": [
                    sys.executable,
                    "-m",
                    "pytest",
                    *package_review_snapshot.DEFAULT_TARGETED_TESTS,
                    "-q",
                ],
                "skipped": True,
                "skip_reason": "--skip-tests",
                "env": env,
            },
        ]

    monkeypatch.setattr(package_review_snapshot, "_materialize_tree", _move_ref_then_materialize)
    monkeypatch.setattr(package_review_snapshot, "_run_review_selftests", _fake_selftests)
    monkeypatch.chdir(repo)

    args = package_review_snapshot.parse_args(
        [
            "--treeish",
            "movable",
            "--output-dir",
            str(tmp_path / "out"),
            "--name",
            "toctou_regression.7z",
            "--skip-tests",
        ]
    )
    assert package_review_snapshot.build_package(args) == 0

    moved = _git_out(repo, "rev-parse", "--verify", "movable^{commit}")
    assert moved != resolved  # the ref really moved inside the window

    # Materialization must have been fed the resolved immutable commit, not the mutable ref name,
    # and the archived bytes must be the pre-move commit's bytes.
    assert captured["treeish"] == resolved
    by_path = {str(item["path"]): item for item in captured["inventory"]}
    assert by_path["src/app.py"]["content_sha256"] == committed_app_sha

    manifest = json.loads(
        (tmp_path / "out" / "toctou_regression.7z.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["treeish"] == resolved
    assert manifest["provenance"]["packaged_commit"] == resolved
