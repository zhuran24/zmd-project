"""Regression coverage for the locked V99 close-kernel runtime guard."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.search.certified_artifact_contract import (
    LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS,
    LockedExactArtifactContractError,
    locked_p1_2_close_kernel_violation,
)
from src.search.exact_campaign import compute_exact_artifact_hashes


def _write(path: Path, text: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_locked_fresh_campaign_fails_before_self_sealing_without_close_kernel(
    tmp_path: Path,
) -> None:
    root = tmp_path / "locked_project"
    _write(root / "PROJECT_LOCK.md", "locked\n")

    with pytest.raises(
        LockedExactArtifactContractError,
        match=r"locked_p1_2_close_kernel_missing:data/proof_obligations/",
    ):
        compute_exact_artifact_hashes(root)


def test_locked_close_kernel_presence_guard_rejects_symlink_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "locked_project"
    _write(root / "PROJECT_LOCK.md", "locked\n")
    manifest_rel, checker_rel = LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS
    _write(root / manifest_rel)
    checker_target = tmp_path / "checker.py"
    _write(checker_target, "raise SystemExit(0)\n")
    checker_path = root / checker_rel
    checker_path.parent.mkdir(parents=True, exist_ok=True)
    checker_path.symlink_to(checker_target)

    assert locked_p1_2_close_kernel_violation(root) == (
        f"locked_p1_2_close_kernel_not_regular:{checker_rel}"
    )


def test_locked_close_kernel_checker_rejection_blocks_fresh_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "locked_project"
    _write(root / "PROJECT_LOCK.md", "locked\n")
    manifest_rel, checker_rel = LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS
    _write(root / manifest_rel)
    _write(root / checker_rel, "raise SystemExit(7)\n")

    assert locked_p1_2_close_kernel_violation(root) == (
        "locked_p1_2_close_kernel_checker_rejected:7"
    )


def test_locked_close_kernel_checker_acceptance_allows_hashing_to_continue(
    tmp_path: Path,
) -> None:
    root = tmp_path / "locked_project"
    _write(root / "PROJECT_LOCK.md", "locked\n")
    manifest_rel, checker_rel = LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS
    _write(root / manifest_rel)
    _write(root / checker_rel, "raise SystemExit(0)\n")

    assert locked_p1_2_close_kernel_violation(root) is None


def test_unlocked_toy_project_does_not_require_close_kernel_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "toy_project"
    root.mkdir()

    assert locked_p1_2_close_kernel_violation(root) is None


def test_locked_close_kernel_argv0_spoof_does_not_bypass_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forging ``sys.argv[0]`` to the checker path must NOT skip verification.

    There is no identity-based self-skip, so a launcher that claims
    ``argv[0]="<checker path>"`` while running other code still falls through to
    the pinned-checker subprocess.  A failing on-disk checker therefore yields a
    rejection rather than a spoofed pass.  Re-introducing an ``argv[0]``-keyed
    skip would make this test fail.
    """
    root = tmp_path / "locked_project"
    _write(root / "PROJECT_LOCK.md", "locked\n")
    manifest_rel, checker_rel = LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS
    _write(root / manifest_rel)
    _write(root / checker_rel, "raise SystemExit(7)\n")
    checker_path = (root / checker_rel).resolve()

    monkeypatch.setattr(sys, "argv", [str(checker_path), *sys.argv[1:]])

    assert locked_p1_2_close_kernel_violation(root) == (
        "locked_p1_2_close_kernel_checker_rejected:7"
    )


def test_locked_close_kernel_runs_subprocess_even_when_main_is_checker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No identity skip: even when ``__main__`` resolves to the checker path the
    pinned checker is still run in a subprocess.

    A failing on-disk checker yields a rejection, proving there is no
    ``__main__.__file__``-keyed (or any identity-keyed) bypass that would let a
    process assert "I am the checker" to skip the verification subprocess.
    """
    root = tmp_path / "locked_project"
    _write(root / "PROJECT_LOCK.md", "locked\n")
    manifest_rel, checker_rel = LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS
    _write(root / manifest_rel)
    _write(root / checker_rel, "raise SystemExit(7)\n")
    checker_path = (root / checker_rel).resolve()

    monkeypatch.setattr(sys.modules["__main__"], "__file__", str(checker_path), raising=False)

    assert locked_p1_2_close_kernel_violation(root) == (
        "locked_p1_2_close_kernel_checker_rejected:7"
    )


def test_locked_close_kernel_ignores_parent_sitecustomize_bypass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The checker subprocess must not inherit parent PYTHONPATH/sitecustomize."""

    root = tmp_path / "locked_project"
    _write(root / "PROJECT_LOCK.md", "locked\n")
    manifest_rel, checker_rel = LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS
    _write(root / manifest_rel)
    _write(
        root / checker_rel,
        (
            "import hashlib\n"
            "expected = 'sitecustomize-forged-pass'\n"
            "raise SystemExit(0 if hashlib.sha256(b'close-kernel').hexdigest() == expected else 7)\n"
        ),
    )
    poison = tmp_path / "poison"
    _write(
        poison / "sitecustomize.py",
        (
            "import hashlib\n"
            "class _ForgedHash:\n"
            "    def hexdigest(self):\n"
            "        return 'sitecustomize-forged-pass'\n"
            "hashlib.sha256 = lambda *args, **kwargs: _ForgedHash()\n"
        ),
    )
    monkeypatch.setenv("PYTHONPATH", str(poison))

    assert locked_p1_2_close_kernel_violation(root) == (
        "locked_p1_2_close_kernel_checker_rejected:7"
    )


def test_locked_close_kernel_identityless_process_modes_do_not_bypass_subprocess(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No file-backed ``__main__``, ``-c`` launchers, and frozen markers must not
    create a replacement identity skip.

    The guard has no process-identity bypass at all, so these interpreter shapes
    still execute the pinned checker subprocess and observe its rejection.
    """
    root = tmp_path / "locked_project"
    _write(root / "PROJECT_LOCK.md", "locked\n")
    manifest_rel, checker_rel = LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS
    _write(root / manifest_rel)
    _write(root / checker_rel, "raise SystemExit(7)\n")

    monkeypatch.setattr(sys, "argv", ["-c"])
    monkeypatch.delattr(sys.modules["__main__"], "__file__", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert locked_p1_2_close_kernel_violation(root) == (
        "locked_p1_2_close_kernel_checker_rejected:7"
    )
