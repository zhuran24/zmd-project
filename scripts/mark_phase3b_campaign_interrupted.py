from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.search.phase3b.campaign.repair import (
    mark_running_exact_campaign_candidates_interrupted,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mark RUNNING exact campaign candidates as UNKNOWN after an operator interruption."
    )
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--reason", default="operator_interrupted")
    parser.add_argument("--detail", default="")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = mark_running_exact_campaign_candidates_interrupted(
        Path(args.project_root).resolve(),
        reason=str(args.reason),
        detail=str(args.detail),
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
