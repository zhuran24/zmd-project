"""Refresh the vendored endfield-calc snapshot from upstream GitHub.

Mechanical sync only:
- Fetches latest TypeScript catalog from JamboChen/endfield-calc.
- Rewrites SOURCE_METADATA.json with new version, commit, counts.
- Records previous observation as "previous_*" fields.
- Does NOT touch canonical_rules.json (PROJECT_LOCK gate).
- Does NOT auto-edit BORROWED_COMPONENTS.md / CHANGELOG.md / specs.

Usage:
    python scripts/refresh_endfield_calc_snapshot.py [--dry-run] [--commit SHA]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REPO = "JamboChen/endfield-calc"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}"
GITHUB_API_BASE = f"https://api.github.com/repos/{REPO}"
VENDORED_DIR = PROJECT_ROOT / "third_party_snapshots" / "endfield_calc" / "upstream_repository_fixture"

FILES_TO_FETCH = (
    "src/types/constants.ts",
    "src/data/facilities.ts",
    "src/data/recipes.ts",
    "src/data/items.ts",
    "package.json",
    "LICENSE",
    "README.md",
)


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def get_master_commit() -> str:
    data = json.loads(fetch_text(f"{GITHUB_API_BASE}/commits/master"))
    return data["sha"]


def parse_package_version(content: str) -> str:
    return json.loads(content)["version"]


def get_observed_counts(target_dir: Path) -> dict:
    from src.adapters.endfield_calc.snapshot_ingest import load_snapshot_source

    loaded = load_snapshot_source(target_dir, source_format="typescript")
    return {
        "items": len(loaded["items"]),
        "recipes": len(loaded["recipes"]),
        "facilities": len(loaded["facilities"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", default=None, help="Specific commit SHA (defaults to master HEAD)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report only, do not write")
    args = parser.parse_args()

    commit = args.commit or get_master_commit()
    print(f"Refreshing endfield-calc to commit {commit[:8]}...")

    metadata_path = VENDORED_DIR / "SOURCE_METADATA.json"
    previous_metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}

    fetched: dict[str, str] = {}
    for upstream_path in FILES_TO_FETCH:
        url = f"{RAW_BASE}/{commit}/{upstream_path}"
        print(f"  Fetching {upstream_path}...")
        fetched[upstream_path] = fetch_text(url)

    new_version = parse_package_version(fetched["package.json"])

    if args.dry_run:
        print(f"\n[dry-run] Would update vendored files to v{new_version} ({commit[:8]})")
        for upstream_path in fetched:
            print(f"  Would write: {VENDORED_DIR / upstream_path}")
        return 0

    for upstream_path, content in fetched.items():
        file_path = VENDORED_DIR / upstream_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    new_counts = get_observed_counts(VENDORED_DIR)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    new_metadata: dict = {
        "source": REPO,
        "source_version": new_version,
        "source_commit": commit,
        "source_commit_note": (
            "master HEAD at refresh time via scripts/refresh_endfield_calc_snapshot.py"
        ),
        "observed_at": today,
        "source_license": "MIT",
        "paths": {
            "items": "src/data/items.ts",
            "recipes": "src/data/recipes.ts",
            "facilities": "src/data/facilities.ts",
            "constants": "src/types/constants.ts",
        },
        "observed_counts": new_counts,
    }
    if previous_metadata:
        new_metadata["previous_observed_at"] = previous_metadata.get("observed_at")
        new_metadata["previous_source_version"] = previous_metadata.get("source_version")
        new_metadata["previous_source_commit"] = previous_metadata.get("source_commit")
        new_metadata["previous_observed_counts"] = previous_metadata.get("observed_counts")

    metadata_path.write_text(
        json.dumps(new_metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n=== Refresh report ===")
    prev_ver = previous_metadata.get("source_version", "?")
    prev_commit = previous_metadata.get("source_commit") or ""
    print(f"Version: {prev_ver} -> {new_version}")
    print(f"Commit:  {prev_commit[:8] if prev_commit else '?'} -> {commit[:8]}")
    print("\nObserved counts:")
    prev_counts = previous_metadata.get("observed_counts") or {}
    for key, value in new_counts.items():
        prev_val = prev_counts.get(key)
        delta = f" ({value - prev_val:+d})" if isinstance(prev_val, int) else ""
        print(f"  {key}: {prev_val if prev_val is not None else '?'} -> {value}{delta}")

    print(
        "\n[NOTICE] canonical_rules.json was NOT touched. If this refresh adds new\n"
        "recipes/facilities you want projected into the master model, manual review\n"
        "via PROJECT_LOCK gate is required to extend canonical_rules.json."
    )
    print(
        "\n[REMINDER] BORROWED_COMPONENTS.md / CHANGELOG.md / FILE_STATUS.md / specs\n"
        "still need a manual one-line entry for this refresh — they are not\n"
        "auto-edited because release-note phrasing is editorial."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
