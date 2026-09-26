#!/usr/bin/env python3
"""Independent input audit. Read only the nominated snapshot and candidate list."""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
SNAPSHOT = BASE / "前提快照"


def read_recipes():
    raw = (SNAPSHOT / "《明日方舟：终末地》游戏规则.txt").read_text()
    recipes = []
    machine = None
    for line_no, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if line_no < 78:
            continue
        if line and "→" not in line and line != "配方":
            machine = line
        if "→" not in line:
            continue
        left, right = line.split("→")
        result, duration = right.split("，")
        def terms(text):
            parsed = {}
            for term in text.split("＋"):
                match = re.fullmatch(r"\s*(\d+)\s+(\S+)\s*", term)
                assert match, term
                parsed[match[2]] = int(match[1])
            return parsed
        inputs, outputs = terms(left), terms(result)
        assert len(outputs) == 1
        d = int(re.fullmatch(r"\s*(\d+)\s+tick", duration)[1])
        recipes.append(dict(machine=machine, inputs=inputs, outputs=outputs,
                            duration=d, line=line_no))
    assert len(recipes) == 18
    return recipes


def main():
    paths = [SNAPSHOT / x for x in ("《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt")]
    paths.append(BASE / "修正版清单.json")
    entries = json.loads(paths[-1].read_text())
    assert len(entries) == 4
    assert all(x["kind"] == "充分条件" and x["group"] == "D" for x in entries)
    q = paths[2].read_text().splitlines()
    n_constraints = sum(line.lstrip().startswith("据：") for line in q)
    assert n_constraints == 77
    recipes = read_recipes()
    out = {
        "sha256": {str(p.relative_to(BASE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "constraints": n_constraints,
        "candidate_count": len(entries),
        "names": [x["name"] for x in entries],
        "identical_text_pairs": [[i, j] for i in range(4) for j in range(i+1, 4)
                                 if entries[i]["text"] == entries[j]["text"]],
        "recipes": recipes,
        "durations": sorted({r["duration"] for r in recipes}),
        "maximum_input_batch": max(a for r in recipes for a in r["inputs"].values()),
        "source_batch_sizes": sorted({next(iter(r["outputs"].values())) for r in recipes if r["duration"] == 1}),
        "minimum_input_lines": [dict(machine=r["machine"], line=r["line"], duration=r["duration"],
            lines={i: (a+r["duration"]-1)//r["duration"] for i, a in r["inputs"].items()}) for r in recipes],
    }
    (HERE / "inputs.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k not in ("recipes", "minimum_input_lines", "names")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
