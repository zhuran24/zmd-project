from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
AB16_RESEARCH = ROOT / "docs/research/noncert_cuts_ab16_20260724"
DECLARATION_PATH = AB16_RESEARCH / "ab16_schema_declaration_v1.py"
GATE1_AUTHORITY_PATH = (
    ROOT
    / "docs/research/noncert_cuts_ab_trust_gate1_v4_20260724"
    / "campaign_authority_v4.py"
)


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


DECLARATION = _load("noncert_cuts_ab16_schema_declaration_v1_tested", DECLARATION_PATH)
GATE1_AUTHORITY = _load("noncert_cuts_gate1_v4_authority_for_ab16_schema_test", GATE1_AUTHORITY_PATH)


def _projection() -> dict[str, list[str]]:
    return {name: list(schemas) for name, schemas in DECLARATION.SCHEMA_COHORTS}


def _surviving_source_schemas() -> set[str]:
    schemas: set[str] = set()
    for path in sorted(AB16_RESEARCH.glob("*.py")):
        if path == DECLARATION_PATH:
            continue
        tree = ast.parse(path.read_bytes(), filename=str(path))
        schemas.update(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and DECLARATION.SCHEMA_LITERAL_RE.fullmatch(node.value) is not None
        )
    return schemas


def test_self_check_reports_the_closed_surviving_cohort() -> None:
    assert DECLARATION.self_check() == {
        "cohort_count": 6,
        "cohort_names": (
            "bootstrap_retry",
            "baseline",
            "organic_execution",
            "resource_lifecycle",
            "replay_terminal",
            "gate1_owned_reference",
        ),
        "schema_count": 49,
        "status": "PASS",
    }
    assert len(DECLARATION.ORDERED_ACTIVE_SCHEMAS) == len(DECLARATION.ACTIVE_SCHEMA_SET) == 49


def test_declaration_exactly_covers_surviving_source_discriminators() -> None:
    local_schemas = _surviving_source_schemas()
    assert local_schemas == DECLARATION.AB16_OWNED_SCHEMA_SET
    assert local_schemas.isdisjoint(DECLARATION.GATE1_OWNED_REFERENCE_SCHEMA_SET)
    assert (
        local_schemas | DECLARATION.GATE1_OWNED_REFERENCE_SCHEMA_SET
        == DECLARATION.ACTIVE_SCHEMA_SET
    )


def test_gate1_owned_reference_matches_its_read_only_owner() -> None:
    assert DECLARATION.SCHEMA_COHORT_OWNER_BY_NAME == {
        "bootstrap_retry": "ab16",
        "baseline": "ab16",
        "organic_execution": "ab16",
        "resource_lifecycle": "ab16",
        "replay_terminal": "ab16",
        "gate1_owned_reference": "gate1_v4",
    }
    assert DECLARATION.GATE1_OWNED_REFERENCE_SCHEMAS == (
        GATE1_AUTHORITY.CONTINUATION_SCHEMA,
    )
    assert DECLARATION.GATE1_OWNED_REFERENCE_SCHEMA_SET == frozenset(
        {GATE1_AUTHORITY.CONTINUATION_SCHEMA}
    )


def test_fixed_assignment_replay_declaration_is_v2_only() -> None:
    fixed_assignment_schemas = tuple(
        schema
        for schema in DECLARATION.ORDERED_ACTIVE_SCHEMAS
        if schema.startswith("noncert-cuts-ab16-fixed-assignment-replay-v")
    )
    assert fixed_assignment_schemas == ("noncert-cuts-ab16-fixed-assignment-replay-v2",)
    assert DECLARATION.schema_cohort_for(fixed_assignment_schemas[0]) == "baseline"
    with pytest.raises(DECLARATION.SchemaDeclarationError, match="unknown schema version"):
        DECLARATION.schema_cohort_for("noncert-cuts-ab16-fixed-assignment-replay-v1")


def test_terminal_classification_declaration_is_v2_only() -> None:
    terminal_classification_schemas = tuple(
        schema
        for schema in DECLARATION.ORDERED_ACTIVE_SCHEMAS
        if schema.startswith("noncert-cuts-ab16-terminal-classification-v")
    )
    assert terminal_classification_schemas == (
        "noncert-cuts-ab16-terminal-classification-v2",
    )
    assert DECLARATION.schema_cohort_for(terminal_classification_schemas[0]) == "replay_terminal"
    with pytest.raises(DECLARATION.SchemaDeclarationError, match="unknown schema version"):
        DECLARATION.schema_cohort_for("noncert-cuts-ab16-terminal-classification-v1")


def test_exact_projection_and_cli_self_check_pass() -> None:
    projection = _projection()
    assert DECLARATION.validate_schema_projection(projection) == {
        name: tuple(schemas) for name, schemas in projection.items()
    }
    completed = subprocess.run(
        (sys.executable, str(DECLARATION_PATH)),
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "cohort_count": 6,
        "cohort_names": [
            "bootstrap_retry",
            "baseline",
            "organic_execution",
            "resource_lifecycle",
            "replay_terminal",
            "gate1_owned_reference",
        ],
        "schema_count": 49,
        "status": "PASS",
    }


def test_projection_rejects_duplicate_discriminator() -> None:
    projection = _projection()
    projection["baseline"][1] = projection["baseline"][0]
    with pytest.raises(DECLARATION.SchemaDeclarationError, match="duplicate discriminator"):
        DECLARATION.validate_schema_projection(projection)


def test_projection_rejects_unknown_version() -> None:
    projection = _projection()
    projection["organic_execution"][0] = re.sub(r"-v[0-9]+$", "-v999", projection["organic_execution"][0])
    with pytest.raises(DECLARATION.SchemaDeclarationError, match="unknown schema version"):
        DECLARATION.validate_schema_projection(projection)


def test_projection_rejects_cross_cohort_mixing() -> None:
    projection = _projection()
    projection["baseline"][0] = projection["resource_lifecycle"][0]
    with pytest.raises(DECLARATION.SchemaDeclarationError, match="cross-cohort schema mixing"):
        DECLARATION.validate_schema_projection(projection)


@pytest.mark.parametrize("mutation", ["omission", "order"])
def test_projection_rejects_omission_or_order_drift(mutation: str) -> None:
    projection = _projection()
    if mutation == "omission":
        projection["replay_terminal"].pop()
    else:
        projection["replay_terminal"][:2] = reversed(projection["replay_terminal"][:2])
    with pytest.raises(DECLARATION.SchemaDeclarationError, match="omission or order drift"):
        DECLARATION.validate_schema_projection(projection)


def test_projection_rejects_unknown_cohort_and_schema() -> None:
    projection = _projection()
    projection["unknown"] = []
    with pytest.raises(DECLARATION.SchemaDeclarationError, match="exact cohort key set"):
        DECLARATION.validate_schema_projection(projection)
    with pytest.raises(DECLARATION.SchemaDeclarationError, match="unknown schema discriminator"):
        DECLARATION.schema_cohort_for("noncert-cuts-ab16-not-a-real-record-v1")
