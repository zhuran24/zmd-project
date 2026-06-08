from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_phase_review_gate


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = PROJECT_ROOT / "data" / "review_gates" / "phase_1_2_spike_close.json"


def _current_review_package(package: str = "zmd_99.7z") -> dict:
    return {
        "package": package,
        "archive_name": package,
        "archive_sha256": "a" * 64,
        "archive_size_bytes": 123456,
        "source_head": "b" * 40,
        "source_list_identity": "chatgpt-project-source:zmd_99.7z",
    }


def _write_review_evidence(
    fake_root: Path,
    package: str,
    *,
    current_package: dict | None = None,
    filename: str | None = None,
    nonce: str | None = None,
) -> str:
    rel = Path("docs") / "research" / (filename or f"{package}.md")
    path = fake_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Review evidence for {package}", "", f"Package: {package}"]
    if current_package is not None:
        lines.extend(
            [
                f"Archive name: {current_package['archive_name']}",
                f"Archive sha256: {current_package['archive_sha256']}",
                f"Archive size_bytes: {current_package['archive_size_bytes']}",
                f"Source HEAD: {current_package['source_head']}",
                f"Source list identity: {current_package['source_list_identity']}",
            ]
        )
    if nonce is not None:
        lines.append(f"Review nonce: {nonce}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rel.as_posix()


def _payload_for_fake_root(fake_root: Path) -> dict:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["required_doc_markers"] = []
    payload["source_boundaries"] = []
    for entry in payload["review_history"]:
        entry["evidence_paths"] = [_write_review_evidence(fake_root, entry["package"])]
    payload["last_reset"]["evidence_paths"] = [
        _write_review_evidence(fake_root, payload["last_reset"]["review_package"])
    ]
    return payload


def _payload_with_minimal_review_evidence(fake_root: Path) -> dict:
    payload = _payload_for_fake_root(fake_root)
    payload["required_doc_markers"] = []
    payload["source_boundaries"] = []
    return payload


def _append_three_clean_reviews(fake_root: Path, payload: dict, *, prefix: str) -> None:
    current_package = _current_review_package()
    payload["current_review_package"] = current_package
    for index in range(3):
        package = current_package["package"]
        payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [
                    _write_review_evidence(
                        fake_root,
                        package,
                        current_package=current_package,
                        filename=f"{prefix}_{index + 1}.md",
                        nonce=f"{prefix}_{index + 1}",
                    )
                ],
            }
        )


def _mark_payload_closed_ready(payload: dict) -> None:
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True


def _init_git_repo_with_head(root: Path, *, content: str) -> str:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True, text=True)
    (root / "tracked.txt").write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "user.name=Test User",
            "commit",
            "-m",
            content.strip() or "seed",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def test_phase_review_gate_manifest_is_consistent() -> None:
    summary, errors = check_phase_review_gate.check_gate(GATE_PATH)

    assert errors == []
    assert "phase_1_2_spike_close" in summary
    assert "clean=0/3" in summary
    assert "next_allowed=False" in summary


def test_require_ready_fails_while_phase_1_2_is_not_closed() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_phase_review_gate.py",
            "--require-ready",
            "phase_1_2_spike_close",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "phase_1_2_spike_close is not ready" in result.stdout
    assert "clean=0/3" in result.stdout


def test_validator_rejects_premature_next_phase_entry(tmp_path: Path) -> None:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["next_phase_entry"]["allowed"] = True
    bad_gate = tmp_path / "bad_gate.json"
    bad_gate.write_text(json.dumps(payload), encoding="utf-8")

    summary, errors = check_phase_review_gate.check_gate(bad_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("must not allow next phase entry" in error for error in errors)


def test_validator_rejects_premature_source_boundary_implementation(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    source_path = fake_root / "src" / "cuts" / "lifecycle.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "def step_8_apply_to_master(cut, master_model):\n    return None\n",
        encoding="utf-8",
    )

    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["last_reset"]["evidence_paths"] = []
    for entry in payload["review_history"]:
        entry["evidence_paths"] = []
    payload["required_doc_markers"] = []
    gate_path = fake_root / "phase_gate.json"
    gate_path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(gate_path)

    assert "phase_1_2_spike_close" in summary
    assert any("source boundary no longer fail-closed" in error for error in errors)


def test_validator_rejects_stale_last_reset_when_later_reset_history_exists(tmp_path: Path) -> None:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["review_history"].append(
        {
            "package": "v999_non_clean_probe",
            "review_type": "independent_full_external",
            "outcome": "major_soundness_findings_found",
            "clean": False,
            "major_or_soundness_findings": 1,
            "resets_counter": True,
            "evidence_paths": [],
        }
    )
    stale_gate = tmp_path / "stale_reset_gate.json"
    stale_gate.write_text(json.dumps(payload), encoding="utf-8")

    summary, errors = check_phase_review_gate.check_gate(stale_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("last_reset.review_package must match the latest resetting" in error for error in errors)


def test_validator_rejects_fake_closed_gate_without_post_reset_clean_reviews(tmp_path: Path) -> None:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    fake_gate = tmp_path / "fake_closed_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("review_history-derived" in error for error in errors)


def test_validator_rejects_fake_clean_reviews_without_evidence(tmp_path: Path) -> None:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    for index in range(3):
        payload["review_history"].append(
            {
                "package": f"v33_clean_full_review_{index + 1}",
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [],
            }
        )
    fake_gate = tmp_path / "fake_clean_reviews_without_evidence.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("evidence_paths must contain at least one" in error for error in errors)


def test_validator_rejects_fake_clean_reviews_with_nonreview_evidence(tmp_path: Path) -> None:
    payload = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    for index in range(3):
        payload["review_history"].append(
            {
                "package": f"v35_fake_clean_{index + 1}",
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": ["README.md"],
            }
        )
    fake_gate = tmp_path / "fake_clean_reviews_with_nonreview_evidence.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("review/research artifact" in error for error in errors)
    assert any("must match review package" in error for error in errors)


def test_validator_rejects_reused_clean_review_evidence(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    shared_evidence = _write_review_evidence(fake_root, "v35_clean_shared")
    for index in range(3):
        payload["review_history"].append(
            {
                "package": "v35_clean_shared",
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [shared_evidence],
            }
        )
    fake_gate = fake_root / "fake_reused_clean_evidence.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("reuses clean-review evidence path" in error for error in errors)


def test_validator_rejects_reused_clean_review_evidence_path_aliases(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    packages = [
        "v36_same_file_clean_one",
        "v36_same_file_clean_two",
        "v36_same_file_clean_three",
    ]
    shared_rel = Path("docs") / "research" / "v36_shared_clean_review.md"
    shared_path = fake_root / shared_rel
    shared_path.parent.mkdir(parents=True, exist_ok=True)
    shared_path.write_text(
        "# Shared review evidence\n\n" + "\n".join(f"Package: {package}" for package in packages),
        encoding="utf-8",
    )
    evidence_aliases = [
        "docs/research/v36_shared_clean_review.md",
        "./docs/research/v36_shared_clean_review.md",
        "docs/research/./v36_shared_clean_review.md",
    ]
    for package, evidence_path in zip(packages, evidence_aliases, strict=True):
        payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_path],
            }
        )
    fake_gate = fake_root / "fake_reused_clean_evidence_aliases.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("evidence path must use canonical spelling" in error for error in errors)


def test_validator_rejects_directory_evidence_even_when_path_matches_package(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    for index in range(3):
        package = f"v36_directory_clean_{index + 1}"
        evidence_path = Path("docs") / "research" / package
        (fake_root / evidence_path).mkdir(parents=True, exist_ok=True)
        payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_path.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_directory_evidence.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("evidence path must be a regular file" in error for error in errors)


def test_validator_rejects_clean_reviews_reusing_reset_evidence_and_package(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    reset_entries = [entry for entry in payload["review_history"] if entry["resets_counter"]]
    for entry in reset_entries[-3:]:
        payload["review_history"].append(
            {
                "package": entry["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": list(entry["evidence_paths"]),
            }
        )
    fake_gate = fake_root / "fake_reset_evidence_as_clean.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("reuses reset-review package" in error for error in errors)
    assert any("reuses reset-review evidence path" in error for error in errors)


def test_require_ready_rejects_duplicate_gate_ids(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    gate_dir = fake_root / "data" / "review_gates"
    gate_dir.mkdir(parents=True)
    blocked_payload = _payload_for_fake_root(fake_root)
    ready_payload = json.loads(json.dumps(blocked_payload))
    ready_payload["status"] = "closed"
    ready_payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    ready_payload["counters"]["remaining_clean_full_reviews"] = 0
    ready_payload["next_phase_entry"]["allowed"] = True
    for index in range(3):
        package = f"v36_duplicate_gate_clean_{index + 1}"
        ready_payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [_write_review_evidence(fake_root, package)],
            }
        )
    blocked_gate = gate_dir / "00_real_blocked.json"
    ready_gate = gate_dir / "99_fake_ready_duplicate.json"
    blocked_gate.write_text(json.dumps(blocked_payload), encoding="utf-8")
    ready_gate.write_text(json.dumps(ready_payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    duplicate_errors = check_phase_review_gate._check_unique_gate_ids([blocked_gate, ready_gate])

    assert any("duplicate gate_id" in error for error in duplicate_errors)
    with pytest.raises(check_phase_review_gate.GateError, match="duplicate gate_id"):
        check_phase_review_gate._check_required_ready(
            [blocked_gate, ready_gate],
            ["phase_1_2_spike_close"],
        )


def test_validator_rejects_hardlinked_clean_review_evidence(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    packages = [
        "v37_hardlink_clean_one",
        "v37_hardlink_clean_two",
        "v37_hardlink_clean_three",
    ]
    base_rel = Path("docs") / "research" / "v37_hardlink_clean_1.md"
    base_path = fake_root / base_rel
    base_path.parent.mkdir(parents=True, exist_ok=True)
    base_path.write_text(
        "# Shared hardlinked clean review evidence\n\n" + "\n".join(f"Package: {package}" for package in packages),
        encoding="utf-8",
    )
    evidence_paths = [base_rel.as_posix()]
    for index in (2, 3):
        linked_rel = Path("docs") / "research" / f"v37_hardlink_clean_{index}.md"
        linked_path = fake_root / linked_rel
        try:
            os.link(base_path, linked_path)
        except OSError as exc:
            pytest.skip(f"hardlinks are not available in this test filesystem: {exc}")
        evidence_paths.append(linked_rel.as_posix())
    for package, evidence_path in zip(packages, evidence_paths, strict=True):
        payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_path],
            }
        )
    fake_gate = fake_root / "fake_hardlinked_clean_evidence.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("reuses clean-review physical evidence file" in error for error in errors)


def test_validator_rejects_copied_clean_review_evidence_content(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    packages = [
        "v37_copied_content_clean_one",
        "v37_copied_content_clean_two",
        "v37_copied_content_clean_three",
    ]
    evidence_body = "# Copied clean review evidence\n\n" + "\n".join(f"Package: {package}" for package in packages)
    for index, package in enumerate(packages, start=1):
        evidence_rel = Path("docs") / "research" / f"v37_copied_content_clean_{index}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(evidence_body, encoding="utf-8")
        payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_copied_content_clean_evidence.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("reuses clean-review evidence content" in error for error in errors)


def test_validator_rejects_clean_review_evidence_bound_only_by_filename(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    packages = [
        "v37_filename_only_clean_one",
        "v37_filename_only_clean_two",
        "v37_filename_only_clean_three",
    ]
    for index, package in enumerate(packages, start=1):
        evidence_rel = Path("docs") / "research" / f"{package}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            f"# Generic clean review evidence {index}\n\nNo package binding in the body.\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_filename_only_evidence.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("must match review package" in error for error in errors)


def test_validator_rejects_package_token_only_clean_review_evidence(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    packages = [
        "v37_token_probe_1",
        "v37_token_probe_2",
        "v37_token_probe_3",
    ]
    for index, package in enumerate(packages, start=1):
        evidence_rel = Path("docs") / "research" / f"{package}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Token-level evidence body\n\n"
            f"This body mentions v37 token probe but omits the exact package suffix. Unique nonce {index}.\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_token_only_evidence.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("must match review package" in error for error in errors)


def test_validator_rejects_clean_reviews_without_current_package_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    for index in range(3):
        package = f"zmd_14.7z_shadow_clean_{index + 1}"
        payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [_write_review_evidence(fake_root, package)],
            }
        )
    fake_gate = fake_root / "fake_clean_without_current_package.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("clean review requires current_review_package identity" in error for error in errors)


def test_validator_rejects_clean_review_package_that_differs_from_current_package(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    for index in range(3):
        package = f"zmd_99.7z_shadow_clean_{index + 1}"
        payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [
                    _write_review_evidence(
                        fake_root,
                        package,
                        filename=f"shadow_package_{index + 1}.md",
                        nonce=f"shadow-{index + 1}",
                    )
                ],
            }
        )
    fake_gate = fake_root / "fake_clean_package_mismatch.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("package must exactly match current_review_package.package" in error for error in errors)
    assert any("missing current package metadata: archive_sha256" in error for error in errors)


def test_validator_rejects_body_only_current_package_binding(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"body_only_current_package_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Body-only clean review claim\n\n"
            f"Package: {current_package['package']}\n"
            "Archive sha256: NOT PROVIDED\n"
            "Archive size_bytes: NOT PROVIDED\n"
            "This evidence intentionally omits source HEAD and source-list identity.\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_body_only_current_package.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("current package metadata archive_sha256" in error for error in errors)
    assert any("current package metadata archive_size_bytes" in error for error in errors)
    assert any("missing current package metadata: source_head" in error for error in errors)


def test_phase_gate_json_loader_rejects_duplicate_current_package_keys(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    fake_root.mkdir(parents=True)
    fake_gate = fake_root / "duplicate_current_package_key_gate.json"
    fake_gate.write_text(
        '{"schema_version": 1, "gate_id": "phase_1_2_spike_close", '
        '"current_review_package": {"package": "zmd_99.7z", "package": "zmd_100.7z"}}',
        encoding="utf-8",
    )

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(check_phase_review_gate.GateError, match="duplicate JSON object key: package"):
        check_phase_review_gate.load_gate(fake_gate)


def test_phase_gate_json_loader_rejects_duplicate_keys(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    fake_root.mkdir(parents=True)
    fake_gate = fake_root / "duplicate_key_gate.json"
    fake_gate.write_text(
        '{"schema_version": 1, "gate_id": "phase_1_2_spike_close", '
        '"status": "blocked_pending_clean_reviews", "status": "closed"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(check_phase_review_gate.GateError, match="duplicate JSON object key: status"):
        check_phase_review_gate.load_gate(fake_gate)


def test_validator_rejects_current_package_archive_name_package_canonical_collision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("zmd_997z")
    payload["current_review_package"]["archive_name"] = "zmd_99.7z"
    fake_gate = fake_root / "fake_current_package_archive_collision.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="package must exactly match archive_name",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_clean_review_history_package_canonical_collision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        payload["review_history"].append(
            {
                "package": "zmd_997z",
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [
                    _write_review_evidence(
                        fake_root,
                        current_package["package"],
                        current_package=current_package,
                        filename=f"history_package_collision_{index + 1}.md",
                        nonce=f"history-collision-{index + 1}",
                    )
                ],
            }
        )
    fake_gate = fake_root / "fake_history_package_collision.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("package must exactly match current_review_package.package" in error for error in errors)


def test_validator_rejects_current_package_source_head_mismatch_with_git_head(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    fake_root.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=fake_root, check=True, capture_output=True, text=True)
    (fake_root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=fake_root, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "user.name=Test User",
            "commit",
            "-m",
            "seed",
        ],
        cwd=fake_root,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("zmd_99.7z")
    payload["current_review_package"]["source_head"] = "0" * 40
    fake_gate = fake_root / "fake_source_head_mismatch.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="source_head must match project git HEAD",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_placeholder_source_list_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("zmd_99.7z")
    payload["current_review_package"]["source_list_identity"] = "NOT PROVIDED"
    fake_gate = fake_root / "fake_placeholder_source_list_identity.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="source_list_identity must not be a placeholder",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_major_outcome_alias_without_reset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_with_minimal_review_evidence(fake_root)
    _mark_payload_closed_ready(payload)
    payload["review_history"].append(
        {
            "package": "v39_hidden_major_alias",
            "review_type": "independent_full_external",
            "outcome": "major-soundness-findings-found",
            "clean": False,
            "major_or_soundness_findings": 0,
            "resets_counter": False,
            "evidence_paths": [],
        }
    )
    _append_three_clean_reviews(fake_root, payload, prefix="v39_clean_after_major_alias")
    fake_gate = fake_root / "fake_hidden_major_alias_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("outcome must use canonical spelling" in error for error in errors)
    assert any("requires a positive major_or_soundness_findings count" in error for error in errors)
    assert any("does not reset counter" in error for error in errors)


def test_validator_rejects_unknown_review_history_outcome(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_with_minimal_review_evidence(fake_root)
    _mark_payload_closed_ready(payload)
    payload["review_history"].append(
        {
            "package": "v39_unknown_outcome",
            "review_type": "independent_full_external",
            "outcome": "soundness_findings_found",
            "clean": False,
            "major_or_soundness_findings": 0,
            "resets_counter": False,
            "evidence_paths": [],
        }
    )
    _append_three_clean_reviews(fake_root, payload, prefix="v39_clean_after_unknown_outcome")
    fake_gate = fake_root / "fake_unknown_outcome_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("unsupported outcome" in error for error in errors)


def test_validator_rejects_review_history_major_findings_alias_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    current_package = _current_review_package()
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        package = current_package["package"]
        entry = {
            "package": package,
            "review_type": "independent_full_external",
            "outcome": "clean",
            "clean": True,
            "major_or_soundness_findings": 0,
            "resets_counter": False,
            "evidence_paths": [
                _write_review_evidence(
                    fake_root,
                    package,
                    current_package=current_package,
                    filename=f"major_alias_clean_review_{index + 1}.md",
                    nonce=f"major-alias-{index + 1}",
                )
            ],
        }
        if index == 0:
            entry["major_findings"] = 1
        payload["review_history"].append(entry)
    fake_gate = fake_root / "fake_review_history_major_alias_key.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any(
        "key 'major_findings' conflicts with canonical key 'major_or_soundness_findings'" in error
        for error in errors
    )


def test_validator_rejects_conflicting_current_package_metadata_after_read_prefix(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"truncated_conflict_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Clean review metadata prefix\n"
            f"Package: {current_package['package']}\n"
            f"Archive name: {current_package['archive_name']}\n"
            f"Archive sha256: {current_package['archive_sha256']}\n"
            f"Archive size_bytes: {current_package['archive_size_bytes']}\n"
            f"Source HEAD: {current_package['source_head']}\n"
            f"Source list identity: {current_package['source_list_identity']}\n"
            f"Review nonce: {index}\n" + ("x" * 210_000) + "\nArchive sha256: " + ("0" * 64) + "\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_truncated_conflict_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("duplicate evidence metadata key 'archive_sha256'" in error for error in errors)


def test_validator_rejects_archive_sha256_hyphen_alias_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"sha_hyphen_conflict_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Clean review metadata prefix\n"
            "Archive SHA-256: " + ("0" * 64) + "\n"
            f"Package: {current_package['package']}\n"
            f"Archive name: {current_package['archive_name']}\n"
            f"Archive sha256: {current_package['archive_sha256']}\n"
            f"Archive size_bytes: {current_package['archive_size_bytes']}\n"
            f"Source HEAD: {current_package['source_head']}\n"
            f"Source list identity: {current_package['source_list_identity']}\n"
            f"Review nonce: {index}\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_sha_hyphen_conflict_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("duplicate evidence metadata key 'archive_sha256'" in error for error in errors)



def test_validator_rejects_missing_resets_counter_on_clean_review(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_with_minimal_review_evidence(fake_root)
    _mark_payload_closed_ready(payload)
    _append_three_clean_reviews(fake_root, payload, prefix="v40_missing_resets_counter")
    for entry in payload["review_history"][-3:]:
        entry.pop("resets_counter")
    fake_gate = fake_root / "fake_missing_resets_counter_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("resets_counter is required" in error for error in errors)


def test_validator_rejects_current_package_archive_name_trailing_space(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("zmd_99.7z")
    payload["current_review_package"]["archive_name"] = "zmd_99.7z "
    fake_gate = fake_root / "fake_archive_name_trailing_space.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="archive_name must not contain leading or trailing whitespace",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_current_package_path_like_archive_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("review/zmd_99.7z")
    fake_gate = fake_root / "fake_path_like_archive_name.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="path-free ASCII .7z archive basename",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_current_package_unicode_archive_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("zmd_99\u200b.7z")
    fake_gate = fake_root / "fake_unicode_archive_name.json"
    fake_gate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="path-free ASCII .7z archive basename",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_fullwidth_colon_metadata_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"fullwidth_colon_conflict_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Clean review metadata prefix\n"
            "Archive SHA-256： " + ("0" * 64) + "\n"
            f"Package: {current_package['package']}\n"
            f"Archive name: {current_package['archive_name']}\n"
            f"Archive sha256: {current_package['archive_sha256']}\n"
            f"Archive size_bytes: {current_package['archive_size_bytes']}\n"
            f"Source HEAD: {current_package['source_head']}\n"
            f"Source list identity: {current_package['source_list_identity']}\n"
            f"Review nonce: {index}\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_fullwidth_colon_conflict_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("must use ASCII colon delimiter" in error for error in errors)


def test_validator_rejects_semantic_placeholder_source_list_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("zmd_99.7z")
    payload["current_review_package"]["source_list_identity"] = "the source list is not provided"
    fake_gate = fake_root / "fake_semantic_placeholder_source_list_identity.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="source_list_identity must not be a placeholder",
    ):
        check_phase_review_gate.check_gate(fake_gate)

def test_validator_rejects_omitted_source_list_identity_placeholder(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("zmd_99.7z")
    payload["current_review_package"]["source_list_identity"] = "source list omitted"
    fake_gate = fake_root / "fake_omitted_source_list_identity.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="source_list_identity must not be a placeholder",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_current_package_json_alias_key_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("zmd_99.7z")
    payload["current_review_package"]["archive-name"] = "zmd_16.7z"
    fake_gate = fake_root / "fake_current_package_alias_key_conflict.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="current_review_package key 'archive-name' conflicts with canonical key 'archive_name'",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_windows_reserved_archive_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("CON.7z")
    fake_gate = fake_root / "fake_windows_reserved_archive_name.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="path-free ASCII .7z archive basename",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_unicode_colon_metadata_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"unicode_colon_conflict_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Clean review metadata prefix\n"
            "Package꞉ zmd_16.7z\n"
            "Archive SHA-256꞉ " + ("0" * 64) + "\n"
            f"Package: {current_package['package']}\n"
            f"Archive name: {current_package['archive_name']}\n"
            f"Archive sha256: {current_package['archive_sha256']}\n"
            f"Archive size_bytes: {current_package['archive_size_bytes']}\n"
            f"Source HEAD: {current_package['source_head']}\n"
            f"Source list identity: {current_package['source_list_identity']}\n"
            f"Review nonce: {index}\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_unicode_colon_conflict_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("must use ASCII colon delimiter" in error for error in errors)


def test_validator_rejects_unicode_normalized_metadata_key_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"unicode_key_conflict_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Clean review metadata prefix\n"
            "Ｐａｃｋａｇｅ: zmd_16.7z\n"
            "Ａｒｃｈｉｖｅ ＳＨＡ２５６: " + ("0" * 64) + "\n"
            f"Package: {current_package['package']}\n"
            f"Archive name: {current_package['archive_name']}\n"
            f"Archive sha256: {current_package['archive_sha256']}\n"
            f"Archive size_bytes: {current_package['archive_size_bytes']}\n"
            f"Source HEAD: {current_package['source_head']}\n"
            f"Source list identity: {current_package['source_list_identity']}\n"
            f"Review nonce: {index}\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_unicode_key_conflict_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("duplicate evidence metadata key 'package'" in error for error in errors)


def test_validator_rejects_confusable_metadata_key_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"confusable_key_conflict_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Clean review metadata prefix\n"
            "Аrchive SHA256: " + ("0" * 64) + "\n"  # Cyrillic capital letter A.
            f"Package: {current_package['package']}\n"
            f"Archive name: {current_package['archive_name']}\n"
            f"Archive sha256: {current_package['archive_sha256']}\n"
            f"Archive size_bytes: {current_package['archive_size_bytes']}\n"
            f"Source HEAD: {current_package['source_head']}\n"
            f"Source list identity: {current_package['source_list_identity']}\n"
            f"Review nonce: {index}\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_confusable_key_conflict_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("duplicate evidence metadata key 'archive_sha256'" in error for error in errors)


def test_validator_rejects_confusable_key_with_confusable_delimiter(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"confusable_key_delimiter_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Clean review metadata prefix\n"
            "Pаckage꞉ zmd_16.7z\n"  # Cyrillic small letter a + modifier letter colon.
            f"Package: {current_package['package']}\n"
            f"Archive name: {current_package['archive_name']}\n"
            f"Archive sha256: {current_package['archive_sha256']}\n"
            f"Archive size_bytes: {current_package['archive_size_bytes']}\n"
            f"Source HEAD: {current_package['source_head']}\n"
            f"Source list identity: {current_package['source_list_identity']}\n"
            f"Review nonce: {index}\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_confusable_key_delimiter_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("must use ASCII colon delimiter" in error for error in errors)


def test_validator_rejects_markdown_table_package_metadata_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"table_metadata_conflict_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Clean review metadata prefix\n"
            "| Archive SHA256 | Package |\n"
            "| --- | --- |\n"
            f"| {'0' * 64} | zmd_16.7z |\n"
            f"Package: {current_package['package']}\n"
            f"Archive name: {current_package['archive_name']}\n"
            f"Archive sha256: {current_package['archive_sha256']}\n"
            f"Archive size_bytes: {current_package['archive_size_bytes']}\n"
            f"Source HEAD: {current_package['source_head']}\n"
            f"Source list identity: {current_package['source_list_identity']}\n"
            f"Review nonce: {index}\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_table_metadata_conflict_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("not table syntax" in error for error in errors)


def test_validator_rejects_confusable_placeholder_source_list_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("zmd_99.7z")
    payload["current_review_package"]["source_list_identity"] = "source list оmitted"
    fake_gate = fake_root / "fake_confusable_source_list_identity.json"
    fake_gate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="source_list_identity must not be a placeholder",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_multilingual_placeholder_source_list_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("zmd_99.7z")
    payload["current_review_package"]["source_list_identity"] = "源列表未提供"
    fake_gate = fake_root / "fake_multilingual_source_list_identity.json"
    fake_gate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="source_list_identity must not be a placeholder",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_uses_project_git_head_despite_git_dir_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    real_head = _init_git_repo_with_head(fake_root, content="real project root\n")
    evil_root = tmp_path / "evil_repo"
    evil_head = _init_git_repo_with_head(evil_root, content="env override repo\n")
    assert real_head != evil_head

    current_package = _current_review_package("zmd_99.7z")
    current_package["source_head"] = evil_head
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    fake_gate = fake_root / "fake_git_env_source_head.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    monkeypatch.setenv("GIT_DIR", str(evil_root / ".git"))
    with pytest.raises(
        check_phase_review_gate.GateError,
        match=f"source_head must match project git HEAD {real_head}",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_uses_trusted_git_command_despite_path_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    real_head = _init_git_repo_with_head(fake_root, content="real project root\n")
    evil_head = "f" * 40
    fake_bin = tmp_path / "fake_bin"
    fake_bin.mkdir()
    fake_git = fake_bin / "git"
    fake_git.write_text(f"#!/bin/sh\nprintf '%s\\n' {evil_head}\n", encoding="utf-8")
    fake_git.chmod(0o755)

    current_package = _current_review_package("zmd_99.7z")
    current_package["source_head"] = evil_head
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    fake_gate = fake_root / "fake_path_git_source_head.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    monkeypatch.setenv("PATH", str(fake_bin) + os.pathsep + os.environ.get("PATH", ""))
    with pytest.raises(
        check_phase_review_gate.GateError,
        match=f"source_head must match project git HEAD {real_head}",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_git_head_that_is_not_a_commit_object(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    real_head = _init_git_repo_with_head(fake_root, content="real project root\n")
    invalid_head = "f" * 40
    assert real_head != invalid_head
    (fake_root / ".git" / "refs" / "heads" / "master").write_text(invalid_head + "\n", encoding="utf-8")

    current_package = _current_review_package("zmd_99.7z")
    current_package["source_head"] = invalid_head
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    fake_gate = fake_root / "fake_invalid_git_head.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="cannot determine project git HEAD",
    ):
        check_phase_review_gate.check_gate(fake_gate)



def test_validator_rejects_latin_extended_metadata_key_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"latin_extended_key_conflict_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Clean review metadata prefix\n"
            f"Archıve SHA256: {'0' * 64}\n"
            "Packaɡe: zmd_18.7z\n"
            f"Package: {current_package['package']}\n"
            f"Archive name: {current_package['archive_name']}\n"
            f"Archive sha256: {current_package['archive_sha256']}\n"
            f"Archive size_bytes: {current_package['archive_size_bytes']}\n"
            f"Source HEAD: {current_package['source_head']}\n"
            f"Source list identity: {current_package['source_list_identity']}\n"
            f"Review nonce: {index}\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_latin_extended_key_conflict_gate.json"
    fake_gate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("duplicate evidence metadata key" in error for error in errors)


def test_validator_rejects_html_table_package_metadata_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"html_table_metadata_conflict_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Clean review metadata prefix\n"
            f"<table><tr><th>Archive SHA256</th><td>{'0' * 64}</td></tr>"
            "<tr><th>Package</th><td>zmd_18.7z</td></tr></table>\n"
            f"Package: {current_package['package']}\n"
            f"Archive name: {current_package['archive_name']}\n"
            f"Archive sha256: {current_package['archive_sha256']}\n"
            f"Archive size_bytes: {current_package['archive_size_bytes']}\n"
            f"Source HEAD: {current_package['source_head']}\n"
            f"Source list identity: {current_package['source_list_identity']}\n"
            f"Review nonce: {index}\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_html_table_metadata_conflict_gate.json"
    fake_gate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("not HTML table syntax" in error for error in errors)


def test_validator_rejects_fullwidth_pipe_table_package_metadata_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    current_package = _current_review_package("zmd_99.7z")
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    _mark_payload_closed_ready(payload)
    for index in range(3):
        evidence_rel = Path("docs") / "research" / f"fullwidth_pipe_table_metadata_conflict_{index + 1}.md"
        evidence_path = fake_root / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            "# Clean review metadata prefix\n"
            "｜ Archive SHA256 ｜ Package ｜\n"
            "｜ --- ｜ --- ｜\n"
            f"｜ {'0' * 64} ｜ zmd_18.7z ｜\n"
            f"Package: {current_package['package']}\n"
            f"Archive name: {current_package['archive_name']}\n"
            f"Archive sha256: {current_package['archive_sha256']}\n"
            f"Archive size_bytes: {current_package['archive_size_bytes']}\n"
            f"Source HEAD: {current_package['source_head']}\n"
            f"Source list identity: {current_package['source_list_identity']}\n"
            f"Review nonce: {index}\n",
            encoding="utf-8",
        )
        payload["review_history"].append(
            {
                "package": current_package["package"],
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [evidence_rel.as_posix()],
            }
        )
    fake_gate = fake_root / "fake_fullwidth_pipe_table_metadata_conflict_gate.json"
    fake_gate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("not table syntax" in error for error in errors)


def test_validator_rejects_latin_extended_placeholder_source_list_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = _current_review_package("zmd_99.7z")
    payload["current_review_package"]["source_list_identity"] = "source list omıtted"
    fake_gate = fake_root / "fake_latin_extended_source_list_identity.json"
    fake_gate.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="source_list_identity must not be a placeholder",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_validator_rejects_git_replace_ref_backed_non_commit_head(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    real_head = _init_git_repo_with_head(fake_root, content="real project root\n")
    blob_head = subprocess.check_output(
        ["git", "hash-object", "-w", "tracked.txt"],
        cwd=fake_root,
        text=True,
    ).strip()
    assert real_head != blob_head
    (fake_root / ".git" / "refs" / "heads" / "master").write_text(blob_head + "\n", encoding="utf-8")
    subprocess.run(
        ["git", "update-ref", f"refs/replace/{blob_head}", real_head],
        cwd=fake_root,
        check=True,
        capture_output=True,
        text=True,
    )

    current_package = _current_review_package("zmd_99.7z")
    current_package["source_head"] = blob_head
    payload = _payload_for_fake_root(fake_root)
    payload["current_review_package"] = current_package
    fake_gate = fake_root / "fake_replace_ref_blob_head.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    with pytest.raises(
        check_phase_review_gate.GateError,
        match="cannot determine project git HEAD",
    ):
        check_phase_review_gate.check_gate(fake_gate)


def test_project_git_command_ignores_relative_defpath_entries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    trusted_bin = tmp_path / "trusted"
    trusted_bin.mkdir()
    fake_bin = tmp_path / "fake"
    fake_bin.mkdir()
    (fake_bin / "git").write_text("#!/bin/sh\nprintf '%s\\n' bad\n", encoding="utf-8")
    (fake_bin / "git").chmod(0o755)
    trusted_git = trusted_bin / "git"
    trusted_git.write_text("#!/bin/sh\nprintf '%s\\n' trusted\n", encoding="utf-8")
    trusted_git.chmod(0o755)

    monkeypatch.setattr(check_phase_review_gate.os, "name", "posix")
    monkeypatch.setattr(
        check_phase_review_gate.os,
        "defpath",
        os.pathsep.join([".", "relative-bin", str(fake_bin), str(trusted_bin)]),
    )
    captured_path: dict[str, str] = {}

    def fake_which(command: str, *, path: str | None = None) -> str | None:
        assert command == "git"
        assert path is not None
        captured_path["path"] = path
        return str(fake_bin / "git")

    monkeypatch.setattr(check_phase_review_gate.shutil, "which", fake_which)

    assert check_phase_review_gate._project_git_command() == str(fake_bin / "git")
    assert "." not in captured_path["path"].split(os.pathsep)
    assert "relative-bin" not in captured_path["path"].split(os.pathsep)
    assert "." not in check_phase_review_gate._project_git_env()["PATH"].split(os.pathsep)
    assert "relative-bin" not in check_phase_review_gate._project_git_env()["PATH"].split(os.pathsep)


def test_windows_project_git_command_uses_standard_git_paths_before_os_defpath(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_cwd = tmp_path / "cwd"
    fake_cwd.mkdir()
    (fake_cwd / "git.exe").write_text("fake", encoding="utf-8")
    trusted_git = tmp_path / "Git" / "cmd" / "git.exe"
    trusted_git.parent.mkdir(parents=True)
    trusted_git.write_text("trusted", encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate.os, "name", "nt")
    monkeypatch.setattr(check_phase_review_gate.os, "defpath", str(fake_cwd))
    monkeypatch.setattr(check_phase_review_gate, "WINDOWS_TRUSTED_GIT_COMMANDS", (trusted_git,))

    assert check_phase_review_gate._project_git_command() == str(trusted_git)
    assert str(fake_cwd) not in check_phase_review_gate._project_git_env()["PATH"].split(os.pathsep)
    assert check_phase_review_gate._project_git_env()["PATHEXT"] == ".EXE"

def test_validator_accepts_closed_gate_with_three_post_reset_clean_reviews(tmp_path: Path, monkeypatch) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_for_fake_root(fake_root)
    current_package = _current_review_package()
    payload["current_review_package"] = current_package
    payload["status"] = "closed"
    payload["counters"]["consecutive_clean_full_reviews_after_reset"] = 3
    payload["counters"]["remaining_clean_full_reviews"] = 0
    payload["next_phase_entry"]["allowed"] = True
    for index in range(3):
        package = current_package["package"]
        payload["review_history"].append(
            {
                "package": package,
                "review_type": "independent_full_external",
                "outcome": "clean",
                "clean": True,
                "major_or_soundness_findings": 0,
                "resets_counter": False,
                "evidence_paths": [
                    _write_review_evidence(
                        fake_root,
                        package,
                        current_package=current_package,
                        filename=f"v33_clean_full_review_{index + 1}.md",
                        nonce=f"v33-clean-{index + 1}",
                    )
                ],
            }
        )
    closed_gate = fake_root / "closed_gate.json"
    closed_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(closed_gate)

    assert "phase_1_2_spike_close" in summary
    assert errors == []


def test_validator_rejects_hidden_major_outcome_without_reset_even_with_later_clean_reviews(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_with_minimal_review_evidence(fake_root)
    _mark_payload_closed_ready(payload)
    payload["review_history"].append(
        {
            "package": "v38_hidden_major_outcome",
            "review_type": "independent_full_external",
            "outcome": "major_soundness_findings_found",
            "clean": False,
            "major_or_soundness_findings": 0,
            "resets_counter": False,
            "evidence_paths": [],
        }
    )
    _append_three_clean_reviews(fake_root, payload, prefix="v38_clean_after_hidden_major")
    fake_gate = fake_root / "fake_hidden_major_outcome_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("requires a positive major_or_soundness_findings count" in error for error in errors)
    assert any("does not reset counter" in error for error in errors)


def test_validator_rejects_negative_major_or_soundness_findings_count(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    payload = _payload_with_minimal_review_evidence(fake_root)
    _mark_payload_closed_ready(payload)
    payload["review_history"].append(
        {
            "package": "v38_negative_major_count",
            "review_type": "independent_full_external",
            "outcome": "major_soundness_findings_found",
            "clean": False,
            "major_or_soundness_findings": -1,
            "resets_counter": False,
            "evidence_paths": [],
        }
    )
    _append_three_clean_reviews(fake_root, payload, prefix="v38_clean_after_negative_major")
    fake_gate = fake_root / "fake_negative_major_gate.json"
    fake_gate.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setattr(check_phase_review_gate, "PROJECT_ROOT", fake_root)
    summary, errors = check_phase_review_gate.check_gate(fake_gate)

    assert "phase_1_2_spike_close" in summary
    assert any("major_or_soundness_findings cannot be negative" in error for error in errors)
    assert any("requires a positive major_or_soundness_findings count" in error for error in errors)
    assert any("does not reset counter" in error for error in errors)
