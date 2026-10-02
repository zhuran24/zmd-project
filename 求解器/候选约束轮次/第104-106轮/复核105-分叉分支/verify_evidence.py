#!/usr/bin/env python3
"""Compare independently produced results, record exact premises and version diff."""
import difflib
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROUND = OUT.parent
ROUNDS = ROUND.parent

CANDIDATE = "分叉分支：一个元件有几个合资格的下游元件可供数层时，对每种单位建造次序得出的接通先后，都须覆盖临时规则允许的每一种数层选择，以及由此到达的循环态。同一单位建成时同一刻形成的几条通道，规则没有给出先后，每一种排法都要覆盖。不得用规则未给出的接通先后、选支对应办法排除不利组合。数层时不绕回自己；只有每一种允许的数法都绕回自己时，层数才仍无法确定。同一轴上相邻两个桥接器之间来回的通道不按成环处理。层数仍未定时，不得填入有利的数值，也不得只因未定就排除这个构型。"


def load(name):
    return json.loads((OUT / name).read_text())


def main():
    a = load("orders_forward.json")
    b = load("orders_reverse.json")
    assert a["cases"].keys() == b["cases"].keys()
    for key, item in a["cases"].items():
        for field, value in item.items():
            assert b["cases"][key][field] == value, (key, field)
    for key, item in a["examples"].items():
        for field, value in item.items():
            if field != "witness_builds":
                assert b["examples"][key][field] == value, (key, field)
        # Independently recheck every saved witness in both outputs.
        for source in (a, b):
            graph = source["examples"][key]
            for order_string, build in graph["witness_builds"].items():
                order = [int(x) for x in order_string.split(",") if x]
                constructed = set()
                remaining = list(order)
                for unit in build:
                    constructed.add(unit)
                    now = [eid for eid in remaining
                           if set(graph["edges"][eid]) <= constructed]
                    assert set(remaining[:len(now)]) == set(now)
                    remaining = remaining[len(now):]
                assert not remaining

    local_a, local_b = load("rule_checks_a.json"), load("rule_checks_b.json")
    assert local_a == local_b
    square = a["examples"]["square"]
    impossible = [0, 3, 1, 2]  # AB < CD < DA < BC, edge list is in the output.
    assert impossible not in square["orders"]
    counts = {name: item["realizable_orders"] for name, item in a["examples"].items()}
    summary = {
        "all_checks_passed": True,
        "simple_graph_cases": len(a["cases"]),
        "additional_multigraph_cases": 2,
        "all_exact_order_set_digests_equal": True,
        "all_strict_build_counts_equal": True,
        "named_order_counts": counts,
        "square_impossible_order": impossible,
        "square_impossible_order_names": ["AB", "CD", "DA", "BC"],
        "square_unrealizable_order_count": square["channel_permutations"] - square["realizable_orders"],
        "local_counts": local_a["counts"],
        "mineral_arithmetic": local_a["mineral_arithmetic"],
        "layer_cases": local_a["layers"],
        "polling_examples": local_a["examples"],
        "limits": "Local rule and combinatorial checks only; no full-layout or delivery certificate.",
    }
    (OUT / "comparison.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    source_files = list((ROUND / "前提快照").glob("*.txt")) + [
        ROUND / "临时规则.md",
        ROUNDS / "第95-97轮" / "推导95M.md",
        ROUNDS / "第95-97轮" / "复核97M.md",
        ROUNDS / "第98-100轮" / "复核100R.md",
    ]
    manifest = []
    for path in sorted(source_files):
        raw = path.read_bytes()
        text = raw.decode()
        manifest.append({"path": str(path), "bytes": len(raw),
                         "lines": len(text.splitlines()),
                         "basis_line_count": sum(line.startswith("    据：") for line in text.splitlines()),
                         "sha256": hashlib.sha256(raw).hexdigest(),
                         "text": text})
    (OUT / "inputs.json").write_text(json.dumps({"candidate": CANDIDATE, "files": manifest},
                                               ensure_ascii=False, indent=2) + "\n")

    previous_report = (ROUNDS / "第95-97轮" / "复核97M.md").read_text()
    old = next(line[2:] for line in previous_report.splitlines() if line.startswith("> 分叉分支："))
    report100 = (ROUNDS / "第98-100轮" / "复核100R.md").read_text()
    version100 = next(line[2:] for line in report100.splitlines() if line.startswith("> 分叉分支："))
    assert CANDIDATE == version100
    differences = [{"operation": op, "old": old[i:j], "new": CANDIDATE[k:l]}
                   for op, i, j, k, l in difflib.SequenceMatcher(None, old, CANDIDATE).get_opcodes()
                   if op != "equal"]
    exact_replacement = "；凡判定先后、轮询起点或取货级的接通时刻要用到这些先后，"
    assert old.replace(exact_replacement, "，") == CANDIDATE
    version_diff = {"candidate": CANDIDATE, "round97": old,
                    "candidate_equals_round100": True,
                    "exact_removed_text": exact_replacement, "replacement": "，",
                    "differences": differences}
    (OUT / "version_diff.json").write_text(json.dumps(version_diff, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
