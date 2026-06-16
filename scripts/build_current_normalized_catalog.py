"""Build a NormalizedCatalog payload from current repository rules."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.interchange.normalized_catalog import build_catalog_from_rules_payload
from src.search.exact_campaign import atomic_write_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Build NormalizedCatalog from rules/canonical_rules.json")
    parser.add_argument(
        "--rules",
        default="rules/canonical_rules.json",
        help="Source rules JSON path.",
    )
    parser.add_argument(
        "--output",
        default="data/solutions/current_rules.normalized_catalog.json",
        help="Output JSON path.",
    )
    args = parser.parse_args()

    rules_path = Path(args.rules)
    rules_payload = json.loads(rules_path.read_text(encoding="utf-8"))
    payload = build_catalog_from_rules_payload(rules_payload)
    atomic_write_json(Path(args.output), payload)
    print(f"normalized catalog written: {args.output}")


if __name__ == "__main__":
    main()
