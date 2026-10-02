#!/usr/bin/env python3
"""Check completed artifacts, produce compact totals, and hash all inputs."""
import hashlib
import json
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent
    round_dir = here.parent
    earlier = round_dir.parent / "第101-103轮"
    inputs = [*sorted((round_dir / "前提快照").glob("*.txt")),
              round_dir / "临时规则.md", earlier / "推导101H.md", earlier / "复核103H.md"]
    manifest = [{"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                 "bytes": p.stat().st_size, "lines": len(p.read_text().splitlines())}
                for p in inputs]
    (here / "inputs.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    blocks, graphs, histories, witnesses = [json.loads((here / f"{name}.json").read_text())
                                            for name in ("blocks", "graphs", "histories", "witnesses")]
    assert len(graphs["rows"]) == 5
    assert all(row["prefix_extrema_a"]["complete"] for row in graphs["rows"])
    assert all(row["transition_mismatches"] == 0 for row in graphs["rows"])
    assert all(row["state_mismatches"] == 0 for row in histories["rows"])
    # Independent arithmetic forms for the two displayed random-trial totals.
    runs_a = sum(row["runs"] for row in histories["rows"])
    runs_b = len([None for row in histories["rows"] for _ in range(row["runs"])])
    steps_a = sum(row["runs"] * row["steps_per_run"] for row in histories["rows"])
    steps_b = sum(sum(row["steps_per_run"] for _ in range(row["runs"]))
                  for row in histories["rows"])
    assert runs_a == runs_b and steps_a == steps_b
    main_blocks = [row for row in blocks["rows"] if row["k"] <= 6]
    summary = {"verdict": "未否证", "block_rows": blocks["rows"],
               "block_profiles_k2_to_6": sum(row["release_profiles"] for row in main_blocks),
               "block_orders_k2_to_6": sum(row["admissible_orders"] for row in main_blocks),
               "base_graph_states_k2_to_6": sum(row["base_states_a"] for row in graphs["rows"]),
               "base_graph_edges_k2_to_6": sum(row["base_edges"] for row in graphs["rows"]),
               "random_runs": runs_a, "random_steps_compared": steps_a,
               "random_modes": {}, "witness_words": [row["word"] for row in witnesses["cases"]]}
    for mode in ("retained", "mixed_clearing", "merger_priorities"):
        rows = [row for row in histories["rows"] if row["mode"] == mode]
        summary["random_modes"][mode] = {
            "runs": sum(row["runs"] for row in rows),
            "max_interval_difference": max(row["max_interval_difference"] for row in rows)}
    (here / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    hashes = []
    for p in sorted(here.iterdir()):
        if p.is_file() and p.name not in ("SHA256SUMS",):
            hashes.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    (here / "SHA256SUMS").write_text("\n".join(hashes) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
