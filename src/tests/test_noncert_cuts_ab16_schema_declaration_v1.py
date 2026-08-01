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


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


DECLARATION = _load("noncert_cuts_ab16_schema_declaration_v1_tested", DECLARATION_PATH)


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
        "cohort_count": 5,
        "cohort_names": (
            "bootstrap_retry",
            "baseline",
            "organic_execution",
            "resource_lifecycle",
            "replay_terminal",
        ),
        "schema_count": 44,
        "status": "PASS",
    }
    assert len(DECLARATION.ORDERED_ACTIVE_SCHEMAS) == len(DECLARATION.ACTIVE_SCHEMA_SET) == 44


def test_declaration_exactly_covers_surviving_source_discriminators() -> None:
    assert _surviving_source_schemas() == DECLARATION.ACTIVE_SCHEMA_SET


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
        "cohort_count": 5,
        "cohort_names": [
            "bootstrap_retry",
            "baseline",
            "organic_execution",
            "resource_lifecycle",
            "replay_terminal",
        ],
        "schema_count": 44,
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
