"""W0 G1: the charter, the theorem registry and the code must agree.

research-only.  A registry whose anchors do not resolve is decoration, and a
research line that can quietly acquire authority is a hazard.  These tests bind
the three together and pin the ledger discipline as text.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
G1_DIR = PROJECT_ROOT / "docs" / "research" / "w0_front_aware_20260803"
CHARTER = G1_DIR / "00_charter.md"
REGISTRY = G1_DIR / "derived_theorems.json"
TESTS_DIR = Path(__file__).resolve().parent
for _path in (str(PROJECT_ROOT), str(G1_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import g1_pattern_schema  # noqa: E402

pytestmark = pytest.mark.evidence

G1_SOURCES = sorted(G1_DIR.glob("*.py"))
G1_TESTS = sorted(TESTS_DIR.glob("test_w0_g1_*.py"))


def _registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _module_level_names(path: Path) -> set[str]:
    """Top-level constants, functions and classes, found without importing."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_registry_anchors_resolve_to_real_module_level_names() -> None:
    """[30] Every stage-A anchor exists, statically, in the module it names."""
    registry = _registry()
    checked = 0
    for entry in registry["theorems"]:
        anchor = entry["code_anchor"]
        if anchor is None:
            assert entry["stage"] != "A", entry["id"]
            continue
        module, _, symbol = anchor.rpartition(".")
        path = G1_DIR / f"{module}.py"
        if entry["stage"] == "A":
            assert path.exists(), f"{entry['id']} names a missing module {module}"
        if not path.exists():
            assert entry["stage"] != "A"
            continue
        assert symbol in _module_level_names(path), (
            f"{entry['id']} anchor {anchor} does not resolve"
        )
        checked += 1
    assert checked >= 15


def test_charter_and_registry_carry_the_same_ids() -> None:
    """[31a] The prose table and the machine mirror cannot drift apart."""
    registry = _registry()
    charter = CHARTER.read_text(encoding="utf-8")
    ids = [entry["id"] for entry in registry["theorems"]]
    assert len(ids) == len(set(ids))
    for theorem_id in ids:
        assert f"`{theorem_id}`" in charter, f"{theorem_id} missing from the charter"
    # And no charter-only id: every backticked T-/R-/H- token is registered.
    mentioned = set(re.findall(r"`([TRH]-[A-Z0-9-]+)`", charter))
    assert mentioned == set(ids), mentioned.symmetric_difference(ids)


#: The prose table writes the layer in Chinese; the JSON mirror writes it in the
#: registry's vocabulary.  This is the only place the two spellings meet.
_LAYER_BY_PROSE = {
    "精确语义": "exact_semantics",
    "必要投影": "necessary_projection",
    "带前件条件 cut": "condition_required_cut",
    "充分限制": "sufficient_restriction",
    "启发式": "heuristic",
}


def _charter_layer_column() -> dict[str, str]:
    """The ``层`` column of the charter's registry table, id -> registry layer.

    A row reads ``| `T-DEAD-BODY` | **必要投影** | G1 | anchor |``; the bold
    markers and the parenthetical qualifier after the layer name are commentary,
    the layer itself is the leading token.
    """
    prose: dict[str, str] = {}
    for line in CHARTER.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) < 6:
            continue
        match = re.fullmatch(r"`([TRH]-[A-Z0-9-]+)`", cells[1])
        if match is None:
            continue
        layer = cells[2].replace("**", "").split("（")[0].strip()
        assert layer in _LAYER_BY_PROSE, (match.group(1), cells[2])
        prose[match.group(1)] = _LAYER_BY_PROSE[layer]
    return prose


def test_the_charter_layer_column_matches_the_registry_layer_field() -> None:
    """[31d] The prose table's second column is bound to the JSON, not eyeballed.

    Every other pairing between the charter and the mirror is pinned; this one
    was maintained by hand, which is the state a registry is supposed to end.
    """
    prose = _charter_layer_column()
    registry = {entry["id"]: entry["layer"] for entry in _registry()["theorems"]}
    assert prose, "the charter table must still carry a layer column"
    assert prose == registry, {
        theorem_id: (prose.get(theorem_id), registry.get(theorem_id))
        for theorem_id in set(prose) ^ set(registry)
        | {key for key in set(prose) & set(registry) if prose[key] != registry[key]}
    }


def test_open_obligations_are_registered_in_both_places() -> None:
    """[31e] An unproved assumption the line depends on has to be visible.

    Capability is evaluated per body with no cross-body simultaneity check, which
    is sound for an INFEASIBLE (the model is more permissive than the rule) and
    unsound to carry into a PASS.  It is therefore registered as an obligation
    rather than left in a review thread.
    """
    registry = _registry()
    charter = CHARTER.read_text(encoding="utf-8")
    obligations = registry["open_obligations"]
    assert obligations, "the obligation list must not silently empty out"
    for entry in obligations:
        assert set(entry) == {
            "id",
            "statement",
            "affects",
            "effect_on_this_batch",
            "must_close_before",
            "closure_options",
        }, entry["id"]
        assert entry["id"] in charter, f"{entry['id']} is missing from the charter"
        assert entry["must_close_before"] == "any G1 PASS"
        assert len(entry["closure_options"]) >= 2
        for theorem_id in entry["affects"]:
            assert theorem_id in {row["id"] for row in registry["theorems"]}
    assert "O-FRONT-SIMULTANEITY" in {entry["id"] for entry in obligations}
    # The pole label and the computation have to agree: the bucket abstraction is
    # a relaxation, so it may not advertise itself as lossless.
    bucket = next(
        entry for entry in registry["theorems"] if entry["id"] == "T-CAPABILITY-BUCKET"
    )
    assert bucket["layer"] == "necessary_projection"
    assert "O-FRONT-SIMULTANEITY" in bucket["statement"]
    assert "necessary_projection" in registry["layer_notes"]


def test_registry_layers_are_the_four_layer_taxonomy() -> None:
    """[31b] Four layers plus exact semantics, and the empty layer is explained."""
    registry = _registry()
    layers = set(registry["layers"])
    assert layers == {
        "exact_semantics",
        "necessary_projection",
        "condition_required_cut",
        "sufficient_restriction",
        "heuristic",
    }
    used = {entry["layer"] for entry in registry["theorems"]}
    assert used <= layers
    assert "condition_required_cut" not in used
    assert "condition_required_cut" in registry["layer_notes"]
    assert "shadow-only" in registry["layer_notes"]["condition_required_cut"]


def test_charter_states_the_gate_order_and_ledger_discipline() -> None:
    """[31c] The section 0b passage and the two-ledger rule are on the page."""
    charter = CHARTER.read_text(encoding="utf-8")
    for needle in (
        "§0b v2.4",
        "U=(1188,18)",
        "L=absent",
        "G1 PASS 不登记任何下界",
        "dead_for_any_actual_class = 0",
        "shadow-only",
    ):
        assert needle in charter, needle
    # The four section-0b roles are each spelled out for all three gates.
    for role in ("① 切分", "② 住址", "③ 管线序", "④ 下游验证人"):
        assert role in charter, role
    for gate in ("G1", "G2", "G3"):
        assert gate in charter


def test_no_artifact_of_this_line_can_claim_authority() -> None:
    """[32, RED LINE] Every authority default is false, in code and in JSON."""
    assert g1_pattern_schema.RESEARCH_AUTHORITY == {
        "is_authoritative": False,
        "carries_bound": False,
        "ledger_effect": "none",
    }
    for path in list(G1_SOURCES) + list(G1_DIR.glob("*.json")):
        text = path.read_text(encoding="utf-8")
        for bad in (
            '"is_authoritative": true',
            '"carries_bound": true',
            '"is_authoritative": True',
            '"carries_bound": True',
        ):
            assert bad not in text, f"{path.name} sets {bad}"


def test_no_source_or_document_registers_a_lower_bound() -> None:
    """[32b, RED LINE] The only permitted reading of ``L =`` is ``absent``."""
    pattern = re.compile(r"(?<![A-Za-z0-9_])L\s*=\s*(\S+)")
    for path in list(G1_SOURCES) + list(G1_DIR.glob("*.json")) + [CHARTER, REGISTRY]:
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            assert match.group(1).startswith("absent"), (
                f"{path.name} writes {match.group(0)!r}; this line registers no bound"
            )


def _dotted_name(node: ast.AST) -> str:
    """Render an attribute chain (``pytest.mark.skip``) back to source text."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def test_no_skip_or_xfail_anywhere_in_the_line() -> None:
    """[33, RED LINE] A skipped test proves nothing; the batch forbids them.

    Matched on the syntax tree, not on text, so this file can name the forbidden
    constructs without tripping over itself.
    """
    banned = {"skip", "skipif", "xfail"}
    for path in list(G1_SOURCES) + list(G1_TESTS):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                dotted = _dotted_name(node)
                assert not (
                    dotted.startswith(("pytest.mark.", "pytest.", "unittest."))
                    and dotted.rsplit(".", 1)[-1] in banned
                ), f"{path.name} uses {dotted}"
    assert len(G1_TESTS) >= 6, "the G1 test set should not shrink silently"


def test_research_line_never_touches_the_certified_surface() -> None:
    """[33b] No import of the proof path from a research-only module."""
    forbidden_prefixes = (
        "src.search",
        "src.certified",
        "src.cuts",
        "src.campaign",
        "scripts",
    )
    for path in G1_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            if module and module.startswith(forbidden_prefixes):
                pytest.fail(f"{path.name} imports {module}")
