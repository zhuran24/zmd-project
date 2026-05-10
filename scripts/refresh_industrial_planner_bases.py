"""Refresh the vendored IndustrialPlanner BASES snapshot from upstream GitHub.

Mechanical sync only:
- Fetches src/domain/registry.ts from hsyhhssyy/IndustrialPlanner.
- Extracts the BASES array (id, name, placeableSize, outerRing, tags) into JSON.
- Writes bases.json and updates SOURCE_METADATA.json.
- Does NOT auto-edit BORROWED_COMPONENTS.md / CHANGELOG.md / specs.

Usage:
    python scripts/refresh_industrial_planner_bases.py [--dry-run] [--commit SHA] [--branch BRANCH]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REPO = "hsyhhssyy/IndustrialPlanner"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}"
GITHUB_API_BASE = f"https://api.github.com/repos/{REPO}"
VENDORED_DIR = PROJECT_ROOT / "third_party_snapshots" / "industrial_planner" / "bases"
REGISTRY_PATH_IN_REPO = "src/domain/registry.ts"


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


def get_branch_commit(branch: str) -> str:
    data = json.loads(fetch_text(f"{GITHUB_API_BASE}/commits/{branch}"))
    return data["sha"]


def extract_bases(registry_ts: str) -> list[dict]:
    """Best-effort regex extractor for the BASES: BaseDef[] array.

    We do not want to ship a TypeScript parser in this repo. The extractor
    pulls only the fields we care about (id, name, placeableSize, outerRing,
    tags) and ignores foundationBuildings (which contain code expressions
    like Array.from(...)). If upstream changes the shape this will fail
    loudly and we re-tune the regex.
    """
    # Find the BASES = [ ... ] block.
    m = re.search(r"export\s+const\s+BASES\s*:\s*BaseDef\[\]\s*=\s*\[", registry_ts)
    if not m:
        raise RuntimeError("Could not locate `export const BASES: BaseDef[] = [` in registry.ts")
    start = m.end()

    # Walk forward tracking bracket depth to find matching ].
    depth = 1
    i = start
    in_string: str | None = None
    while i < len(registry_ts) and depth > 0:
        ch = registry_ts[i]
        if in_string is not None:
            if ch == "\\" and i + 1 < len(registry_ts):
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue
        if ch in ("'", '"', "`"):
            in_string = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                break
        i += 1
    if depth != 0:
        raise RuntimeError("Unbalanced brackets while scanning BASES array")
    bases_block = registry_ts[start:i]

    # Each base entry starts with "id:" and ends roughly at the closing brace
    # before the next "id:" or end of block. We split on top-level base entries.
    entries: list[dict] = []
    base_pattern = re.compile(
        r"id:\s*'([^']+)'.*?"
        r"name:\s*'([^']+)'.*?"
        r"placeableSize:\s*(\d+).*?"
        r"outerRing:\s*\{\s*top:\s*(\d+),\s*right:\s*(\d+),\s*bottom:\s*(\d+),\s*left:\s*(\d+)\s*\}.*?"
        r"tags:\s*\[([^\]]*)\]",
        re.DOTALL,
    )
    for match in base_pattern.finditer(bases_block):
        base_id, name, size, top, right, bottom, left, tags_raw = match.groups()
        tag_list = [t.strip().strip("'").strip('"') for t in tags_raw.split(",") if t.strip()]
        entries.append({
            "id": base_id,
            "name": name,
            "placeableSize": int(size),
            "outerRing": {
                "top": int(top),
                "right": int(right),
                "bottom": int(bottom),
                "left": int(left),
            },
            "tags": tag_list,
        })
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default="v2", help="Upstream branch (defaults to v2)")
    parser.add_argument("--commit", default=None, help="Specific commit SHA (overrides --branch)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report only, do not write")
    args = parser.parse_args()

    commit = args.commit or get_branch_commit(args.branch)
    print(f"Refreshing IndustrialPlanner BASES from commit {commit[:8]}...")

    metadata_path = VENDORED_DIR / "SOURCE_METADATA.json"
    bases_path = VENDORED_DIR / "bases.json"
    previous_metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}

    registry_url = f"{RAW_BASE}/{commit}/{REGISTRY_PATH_IN_REPO}"
    print(f"  Fetching {REGISTRY_PATH_IN_REPO}...")
    registry_ts = fetch_text(registry_url)

    bases = extract_bases(registry_ts)
    print(f"  Extracted {len(bases)} bases:")
    for b in bases:
        print(f"    {b['id']:35s} size={b['placeableSize']:3d} tags={b['tags']}")

    if args.dry_run:
        print(f"\n[dry-run] Would write {bases_path} and {metadata_path}")
        return 0

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    bases_payload = {
        "schema": "industrial-planner-bases-vendored/v0",
        "extracted_at": today,
        "extracted_from_commit": commit,
        "extracted_from_path": REGISTRY_PATH_IN_REPO,
        "extraction_note": (
            "Best-effort regex extraction of the BASES array. foundationBuildings "
            "are intentionally omitted because upstream uses code expressions "
            "(Array.from) that cannot be statically projected without a TS parser. "
            "Refresh via scripts/refresh_industrial_planner_bases.py."
        ),
        "bases": bases,
    }
    bases_path.parent.mkdir(parents=True, exist_ok=True)
    bases_path.write_text(json.dumps(bases_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    new_metadata: dict = {
        "source": REPO,
        "source_branch": args.branch,
        "source_commit": commit,
        "source_commit_note": (
            f"branch {args.branch} HEAD at refresh time via scripts/refresh_industrial_planner_bases.py"
        ),
        "observed_at": today,
        "source_license": "MIT",
        "vendored_paths": {
            "bases": "bases.json",
        },
        "upstream_paths": {
            "registry": REGISTRY_PATH_IN_REPO,
        },
        "observed_counts": {
            "bases": len(bases),
        },
        "extraction_method": "regex_field_subset",
    }
    if previous_metadata:
        new_metadata["previous_observed_at"] = previous_metadata.get("observed_at")
        new_metadata["previous_source_commit"] = previous_metadata.get("source_commit")
        new_metadata["previous_observed_counts"] = previous_metadata.get("observed_counts")

    metadata_path.write_text(
        json.dumps(new_metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\n=== Refresh report ===")
    prev_commit = previous_metadata.get("source_commit") or ""
    print(f"Commit: {prev_commit[:8] if prev_commit else '?'} -> {commit[:8]}")
    prev_count = (previous_metadata.get("observed_counts") or {}).get("bases")
    delta = f" ({len(bases) - prev_count:+d})" if isinstance(prev_count, int) else ""
    print(f"Base count: {prev_count if prev_count is not None else '?'} -> {len(bases)}{delta}")

    print(
        "\n[NOTICE] PROJECT_LOCK active scope is still valley4_protocol_core (70x70).\n"
        "Other bases (wuling_protocol_core 80x80, etc.) remain future_scope until\n"
        "an explicit scope-expansion review."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
