"""binding PB sidecar — OPB-level witness checker（设计稿 v2 §5.2 第一段）.

只读 instance.opb + assignment，逐行独立验约束——不 import emitter 的约束
生成函数（唯一共享 = OPB 文法本身）。SAT witness 通过 → SIDE_SAT 升级为
DIVERGED_OPB_ONLY（canonical-level checker 落地前不升 DIVERGED_CANDIDATE）。
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

_TERM = re.compile(r"([+-]\d+) x(\d+)")
_ROW = re.compile(r"^(.*?)(>=|=)\s*(-?\d+)\s*;\s*$")


def parse_opb(opb_text: str) -> Tuple[int, List[Tuple[List[Tuple[int, int]], str, int]]]:
    """→ (n_variables, [(terms, op, rhs)])。terms=[(coef, var)]."""
    lines = opb_text.splitlines()
    if not lines or not lines[0].startswith("* #variable="):
        raise ValueError("missing OPB header")
    n_vars = int(re.search(r"#variable= (\d+)", lines[0]).group(1))
    rows = []
    for line in lines[1:]:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        m = _ROW.match(line)
        if not m:
            raise ValueError(f"unparseable OPB row: {line!r}")
        body, op, rhs = m.group(1), m.group(2), int(m.group(3))
        terms = [(int(c), int(v)) for c, v in _TERM.findall(body)]
        rows.append((terms, op, rhs))
    return n_vars, rows


def check_witness(opb_text: str, values: Dict[int, int]) -> Dict[str, object]:
    """witness 是否满足全部约束。返回 {ok, failed_rows, missing_vars}."""
    n_vars, rows = parse_opb(opb_text)
    missing = [v for v in range(1, n_vars + 1) if v not in values]
    failed: List[int] = []
    for idx, (terms, op, rhs) in enumerate(rows, start=1):
        lhs = sum(coef * values.get(var, 0) for coef, var in terms)
        ok = (lhs == rhs) if op == "=" else (lhs >= rhs)
        if not ok:
            failed.append(idx)
    return {"ok": not failed and not missing, "failed_rows": failed, "missing_vars": missing}
