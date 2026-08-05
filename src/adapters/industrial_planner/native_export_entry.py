"""Operator-facing entry point for producing a native IndustrialPlanner document.

The exporter (`export_blueprint`) writes the v1 intermediate representation and
nothing else.  Lowering that IR into the document the upstream application
actually reads (`schemaVersion: 4`) happens here, in a separate step, driven by
this module::

    python -m src.adapters.industrial_planner.native_export_entry \\
        <v1_blueprint.json> -o <native.blueprint.json>

The split is not stylistic.  `export_blueprint`, `mapping_registry` and the
package `__init__` are close-kernel sealed sources pinned by
`scripts/check_p1_2_proof_obligations.py`: wiring the lowering into the export
bundle would put `native_document` and `native_validator` inside the kernel's
import-time closure, so every later change to the native chain would drag a full
P1.2 reseal behind it.  Keeping the chain downstream of the exporter buys that
freedom, and costs one explicit command - the native document is not written
alongside the bundle.

The output bytes are canonical: `indent=2`, `ensure_ascii=False`, sorted keys,
one trailing newline.  Sorted keys make the document diffable against the
upstream converter's output, which is how the lowering was validated in the
first place.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping, Sequence

from src.adapters.industrial_planner.native_document import lower_v1_blueprint_to_native
from src.adapters.industrial_planner.native_validator import validate_native_blueprint_document

INDUSTRIAL_PLANNER_NATIVE_BLUEPRINT_FILENAME = "industrial_planner.native.blueprint.json"


@dataclass(frozen=True)
class NativeExportResult:
    """A lowered, validated native document plus everything the caller may report."""

    document: dict[str, Any]
    validation_report: dict[str, Any]
    warnings: tuple[str, ...]
    output_path: Path | None = None


def build_native_blueprint_export(
    v1_blueprint: Mapping[str, Any],
    *,
    document_id: str | None = None,
    created_at: str | None = None,
) -> NativeExportResult:
    """Lower a v1 blueprint and validate the result, raising on an invalid document."""

    lowering = lower_v1_blueprint_to_native(
        v1_blueprint,
        document_id=document_id,
        created_at=created_at,
    )
    report = validate_native_blueprint_document(lowering.document)
    if not report.is_valid:
        raise ValueError(
            "industrial planner native blueprint document failed validation: "
            + "; ".join(report.errors)
        )
    return NativeExportResult(
        document=lowering.document,
        validation_report=report.to_dict(),
        warnings=tuple(lowering.warnings),
    )


def render_native_blueprint_json(document: Mapping[str, Any]) -> str:
    """Serialise a native document into the canonical on-disk form."""

    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def export_native_blueprint(
    *,
    v1_blueprint_path: Path,
    output_path: Path | None = None,
    document_id: str | None = None,
    created_at: str | None = None,
) -> NativeExportResult:
    """Read a v1 blueprint from disk, lower it, validate it and write the native document.

    `output_path` defaults to `INDUSTRIAL_PLANNER_NATIVE_BLUEPRINT_FILENAME` next
    to the input.  Nothing is written unless validation passed.
    """

    v1_blueprint = json.loads(Path(v1_blueprint_path).read_text(encoding="utf-8"))
    if not isinstance(v1_blueprint, Mapping):
        raise ValueError(f"native export: {v1_blueprint_path} does not contain a JSON object")

    result = build_native_blueprint_export(
        v1_blueprint,
        document_id=document_id,
        created_at=created_at,
    )

    resolved_output = (
        Path(output_path)
        if output_path is not None
        else Path(v1_blueprint_path).parent / INDUSTRIAL_PLANNER_NATIVE_BLUEPRINT_FILENAME
    )
    _atomic_write_text(resolved_output, render_native_blueprint_json(result.document))
    return NativeExportResult(
        document=result.document,
        validation_report=result.validation_report,
        warnings=result.warnings,
        output_path=resolved_output,
    )


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.adapters.industrial_planner.native_export_entry",
        description=(
            "Lower an exported v1 IndustrialPlanner blueprint into the native "
            "(schemaVersion 4) document the upstream application reads."
        ),
    )
    parser.add_argument("v1_blueprint", type=Path, help="path to the v1 blueprint JSON")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "where to write the native document; defaults to "
            f"{INDUSTRIAL_PLANNER_NATIVE_BLUEPRINT_FILENAME} next to the input"
        ),
    )
    parser.add_argument(
        "--document-id",
        default=None,
        help="override the native blueprintId (defaults to the v1 blueprint id)",
    )
    parser.add_argument(
        "--created-at",
        default=None,
        help="override createdAt/updatedAt (defaults to the v1 blueprint createdAt)",
    )
    args = parser.parse_args(argv)

    result = export_native_blueprint(
        v1_blueprint_path=args.v1_blueprint,
        output_path=args.output,
        document_id=args.document_id,
        created_at=args.created_at,
    )
    assert result.output_path is not None
    print(f"wrote {result.output_path}")
    print(f"entities={len(result.document['entities'])} slotLinks={len(result.document['slotLinks'])}")
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through `python -m`
    raise SystemExit(main())
