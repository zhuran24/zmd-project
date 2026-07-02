"""Regression coverage for the locked V99 close-kernel runtime guard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.search.certified_artifact_contract import (
    LOCKED_P1_2_CHECKER_PROTECTED_CALLEES,
    LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS,
    LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256,
    LockedExactArtifactContractError,
    locked_p1_2_close_kernel_violation,
)
from src.search.exact_campaign import compute_exact_artifact_hashes


def _write(path: Path, text: str = "{}\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_locked_close_kernel_data(root: Path) -> str:
    """Seed a synthetic locked project so the runtime guard's presence and
    semantic-projection anchor checks pass, and return the checker relative path
    for the caller to populate.

    round-14 (C6/B1) grew ``LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS`` from
    (manifest, checker) to (manifest, strong-status allowlist, checker) and made
    the runtime guard reject a manifest whose declared ``semantic_projection_sha256``
    does not match the runtime-pinned digest.  The guard only reads that one
    declared field (it does not recompute the projection) and only requires the
    allowlist to be a regular file (its byte floor lives in the checker), so a
    minimal manifest carrying the pinned digest plus an empty allowlist file is
    sufficient to exercise the downstream checker-subprocess behaviours.
    """
    manifest_rel, allowlist_rel, checker_rel = LOCKED_P1_2_CLOSE_KERNEL_REQUIRED_PATHS
    _write(
        root / manifest_rel,
        json.dumps(
            {
                "semantic_projection_sha256": (
                    LOCKED_P1_2_CLOSE_KERNEL_SEMANTIC_PROJECTION_SHA256
                )
            }
        )
        + "\n",
    )
    _write(root / allowlist_rel)
    return checker_rel


def _valid_stub_checker_source(main_body: str) -> str:
    """Build a minimal checker source that satisfies the runtime guard's
    Finding-A parent-process AST anchor.

    round-15 (Finding A) added ``_locked_close_kernel_checker_ast_anchor_violation``
    which, before running the pinned checker subprocess, requires the checker to
    keep a canonical ``if __name__ == "__main__": raise SystemExit(main())``
    entrypoint, a closed-world module top level, and exactly one undecorated
    top-level ``FunctionDef`` for ``main`` and every protected callee (so a
    ``main``/callee rebind cannot silently gut the checker).  A bare
    ``raise SystemExit(n)`` stub no longer reaches the subprocess.  This helper
    emits a stub that passes the anchor; ``main``'s return value (from
    ``main_body``, a 4-space-indented function body) becomes the subprocess exit
    code, so the downstream subprocess/exit-code behaviours can still be exercised.
    """
    blocks = [f"def main() -> int:\n{main_body}"]
    for callee in sorted(LOCKED_P1_2_CHECKER_PROTECTED_CALLEES):
        blocks.append(f"def {callee}() -> list[str]:\n    return []")
    blocks.append('if __name__ == "__main__":\n    raise SystemExit(main())')
    return "\n\n\n".join(blocks) + "\n"


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
    checker_rel = _seed_locked_close_kernel_data(root)
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
    checker_rel = _seed_locked_close_kernel_data(root)
    _write(root / checker_rel, _valid_stub_checker_source("    return 7\n"))

    assert locked_p1_2_close_kernel_violation(root) == (
        "locked_p1_2_close_kernel_checker_rejected:7"
    )


def test_locked_close_kernel_checker_acceptance_allows_hashing_to_continue(
    tmp_path: Path,
) -> None:
    root = tmp_path / "locked_project"
    _write(root / "PROJECT_LOCK.md", "locked\n")
    checker_rel = _seed_locked_close_kernel_data(root)
    _write(root / checker_rel, _valid_stub_checker_source("    return 0\n"))

    assert locked_p1_2_close_kernel_violation(root) is None


def test_locked_close_kernel_rejects_checker_gutted_below_canonical_entrypoint(
    tmp_path: Path,
) -> None:
    """round-15 Finding A: a checker gutted to a bare ``raise SystemExit(0)`` stub
    (no canonical ``if __name__ == "__main__": raise SystemExit(main())`` entrypoint,
    no ``main``) is rejected by the parent-process AST anchor *before* the subprocess
    runs, so a stub that would exit 0 can no longer spoof acceptance.
    """
    root = tmp_path / "locked_project"
    _write(root / "PROJECT_LOCK.md", "locked\n")
    checker_rel = _seed_locked_close_kernel_data(root)
    _write(root / checker_rel, "raise SystemExit(0)\n")

    assert locked_p1_2_close_kernel_violation(root) == (
        "locked_p1_2_close_kernel_checker_entrypoint_invalid"
    )


def test_locked_close_kernel_rejects_import_time_class_body_main_rebind(
    tmp_path: Path,
) -> None:
    """The parent anchor must reject class-body executable code before the
    subprocess can import the checker and run a class body that swaps ``main``.
    """
    root = tmp_path / "locked_project"
    _write(root / "PROJECT_LOCK.md", "locked\n")
    checker_rel = _seed_locked_close_kernel_data(root)
    checker_source = "import sys\n\n" + _valid_stub_checker_source("    return 7\n")
    checker_source = checker_source.replace(
        '\n\nif __name__ == "__main__":\n',
        "\n_round18_modules = sys.modules\n"
        "class _Round18Probe:\n"
        "    _round18_modules[__name__].main = lambda: 0\n"
        '\nif __name__ == "__main__":\n',
        1,
    )
    _write(root / checker_rel, checker_source)

    violation = locked_p1_2_close_kernel_violation(root)

    assert violation is not None
    assert violation.startswith(
        "locked_p1_2_close_kernel_checker_top_level_disallowed:ClassDef"
    )


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
    checker_rel = _seed_locked_close_kernel_data(root)
    _write(root / checker_rel, _valid_stub_checker_source("    return 7\n"))
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
    checker_rel = _seed_locked_close_kernel_data(root)
    _write(root / checker_rel, _valid_stub_checker_source("    return 7\n"))
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
    checker_rel = _seed_locked_close_kernel_data(root)
    _write(
        root / checker_rel,
        _valid_stub_checker_source(
            "    import hashlib\n"
            "    expected = 'sitecustomize-forged-pass'\n"
            "    return 0 if hashlib.sha256(b'close-kernel').hexdigest() == expected else 7\n"
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
    checker_rel = _seed_locked_close_kernel_data(root)
    _write(root / checker_rel, _valid_stub_checker_source("    return 7\n"))

    monkeypatch.setattr(sys, "argv", ["-c"])
    monkeypatch.delattr(sys.modules["__main__"], "__file__", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert locked_p1_2_close_kernel_violation(root) == (
        "locked_p1_2_close_kernel_checker_rejected:7"
    )
