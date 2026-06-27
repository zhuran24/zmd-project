"""Safety isolation tests for the S2/S3 topology hint planners.

These modules are diagnostic, exploratory planners.  They must never be wired
into the certified solve path without a separate, measured, reviewed change, and
they must never be referenced by any proof-bearing module or registered as a
certified/close-kernel artifact.  This test pins those boundaries so an
accidental import or registration is caught immediately.
"""

from __future__ import annotations

from pathlib import Path

from scripts import preflight_gate
from src.search import exact_campaign

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

HINT_MODULE_NAMES = ("topology_binding_guidance", "topology_route_hint")

HINT_MODULE_PATHS = (
    "src/search/topology_binding_guidance.py",
    "src/search/topology_route_hint.py",
)

# The modules that own these names (excluded from the "who references them" scan).
OWNER_FILES = HINT_MODULE_PATHS


def _scanned_python_files() -> list[Path]:
    """Every non-test, non-owner Python file that could import a planner.

    Scans the WHOLE ``src/`` tree (not a hand-picked subset) plus ``main.py`` and
    ``scripts/`` — the entry point and gate/build scripts are real wiring surfaces.
    Excludes the planners' own files and the test tree (which legitimately name
    the modules).
    """

    files: list[Path] = []
    src_root = PROJECT_ROOT / "src"
    for path in src_root.rglob("*.py"):
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel in OWNER_FILES:
            continue
        if rel.startswith("src/tests/"):
            continue
        if "__pycache__" in rel:
            continue
        files.append(path)
    main_py = PROJECT_ROOT / "main.py"
    if main_py.exists():
        files.append(main_py)
    scripts_root = PROJECT_ROOT / "scripts"
    if scripts_root.exists():
        for path in scripts_root.rglob("*.py"):
            if "__pycache__" not in path.as_posix():
                files.append(path)
    return files


def test_hint_planners_are_not_imported_by_any_non_test_module() -> None:
    references: dict[str, list[str]] = {name: [] for name in HINT_MODULE_NAMES}
    scanned = _scanned_python_files()
    # Sanity: the scan must actually cover the high-risk leak surfaces.
    scanned_rels = {path.relative_to(PROJECT_ROOT).as_posix() for path in scanned}
    assert any(rel.startswith("src/preprocess/") for rel in scanned_rels), (
        "scan must cover src/preprocess (where the skeleton + frozen proof inputs live)"
    )
    assert any(rel.startswith("scripts/") for rel in scanned_rels)

    for path in scanned:
        text = path.read_text(encoding="utf-8")
        for name in HINT_MODULE_NAMES:
            if name in text:
                references[name].append(path.relative_to(PROJECT_ROOT).as_posix())
    assert references == {name: [] for name in HINT_MODULE_NAMES}, (
        f"topology hint planners are referenced by non-test modules: {references}"
    )


def test_hint_planners_are_not_wired_into_binding_or_routing() -> None:
    wire_targets = (
        "src/models/binding_subproblem.py",
        "src/models/routing_subproblem.py",
    )
    offenders: list[str] = []
    for rel in wire_targets:
        path = PROJECT_ROOT / rel
        assert path.exists(), f"expected wire-point module missing: {rel}"
        text = path.read_text(encoding="utf-8")
        if any(name in text for name in HINT_MODULE_NAMES):
            offenders.append(rel)
    assert offenders == [], f"hint planners wired without review: {offenders}"


def test_proof_bearing_modules_do_not_reference_hint_planners() -> None:
    proof_bearing_modules = (
        "src/search/exact_campaign.py",
        "src/search/outer_search.py",
        "src/search/certified_frontier.py",
        "src/search/certified_surface.py",
        "src/search/candidate_proof_replay.py",
        "src/cuts/lifecycle.py",
    )
    offenders: list[str] = []
    for rel in proof_bearing_modules:
        path = PROJECT_ROOT / rel
        # Fail closed: a renamed/moved proof-bearing module must break this guard
        # loudly, not turn it into a vacuous pass.
        assert path.exists(), f"expected proof-bearing module missing: {rel}"
        text = path.read_text(encoding="utf-8")
        if any(name in text for name in HINT_MODULE_NAMES):
            offenders.append(rel)
    assert offenders == [], f"proof-bearing module references hint planner: {offenders}"


def test_hint_planner_modules_are_not_registered_as_frozen_artifacts() -> None:
    for module_path in HINT_MODULE_PATHS:
        assert module_path not in preflight_gate.FROZEN_ARTIFACTS
        assert module_path not in preflight_gate.EXTERNAL_FROZEN_ARTIFACTS
        assert module_path not in exact_campaign.EXACT_HASH_FILES.values()
        assert module_path not in exact_campaign.OPTIONAL_EXACT_HASH_FILES.values()


def test_hint_planner_modules_are_not_registered_as_close_kernel_sinks() -> None:
    # The one registry that CAN pin a .py module is the close-kernel sink list /
    # strong-status write allowlist.  Assert the planners appear nowhere in either,
    # so they can never be "legitimised" as proof-bearing sinks without this test
    # turning red.
    registry_files = (
        "data/proof_obligations/p1_2_proof_obligations.json",
        "data/proof_obligations/strong_status_write_allowlist.json",
    )
    for rel in registry_files:
        path = PROJECT_ROOT / rel
        assert path.exists(), f"expected proof-obligation registry missing: {rel}"
        text = path.read_text(encoding="utf-8")
        for module_path in HINT_MODULE_PATHS:
            assert module_path not in text, f"{module_path} registered in {rel}"
        for module_name in HINT_MODULE_NAMES:
            assert module_name not in text, f"{module_name} registered in {rel}"
