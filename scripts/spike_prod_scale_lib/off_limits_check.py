"""Off-limits enforce — spike commits must not touch 8 critical path classes.

Per MERGER §5.1 state sandbox requirement:
- spike commit 集 (branch vs master) 任一 diff 落入以下 8 类路径即 FAIL.
- 此 check 既可在 commit hook 跑, 也可在 spike harness 启动时 self-check.

Off-limits 路径 (8 类):
1. ``PROJECT_LOCK.md`` (root)
2. ``rules/canonical_rules.json`` (consolidated truth)
3. ``data/preprocessed/`` 全 (mandatory_exact_instances / candidate_placements /
   generic_io_requirements / commodity_demands / 等等)
4. ``src/cuts/families/`` 9 family validator entry
5. ``docs/项目说明/`` 全 spec
6. ``CLAUDE.md`` (root)
7. ``src/cuts/lifecycle.py`` (主 step 函数, 跨家族 lifecycle 骨架)
8. ``src/cuts/replay.py`` (cross-session replay 主接口)
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List, Tuple


# Paths or prefixes that must not be touched in spike commits.
# Each entry is (kind, value):
#   - "exact": full path equality
#   - "prefix": path startswith
OFF_LIMITS: Tuple[Tuple[str, str], ...] = (
    ("exact",  "PROJECT_LOCK.md"),
    ("exact",  "rules/canonical_rules.json"),
    ("prefix", "data/preprocessed/"),
    ("prefix", "src/cuts/families/"),
    ("prefix", "docs/项目说明/"),
    ("exact",  "CLAUDE.md"),
    ("exact",  "src/cuts/lifecycle.py"),
    ("exact",  "src/cuts/replay.py"),
)


@dataclass
class OffLimitsViolation:
    path: str
    rule_kind: str
    rule_value: str


def _is_violation(path: str) -> Tuple[bool, str, str]:
    for kind, value in OFF_LIMITS:
        if kind == "exact" and path == value:
            return True, kind, value
        if kind == "prefix" and path.startswith(value):
            return True, kind, value
    return False, "", ""


def changed_files(base_ref: str = "master", head_ref: str = "HEAD") -> List[str]:
    """Return list of paths that differ between ``base_ref..head_ref``.

    Uses ``git diff --name-only`` (no triple-dot — we want symmetric diff
    of the spike branch tip vs master tip, including spike-side additions).
    Triple-dot ``base...head`` would also work; we keep ``base..head`` for
    clarity that the question is "what files are different now vs master".
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}..{head_ref}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def check_off_limits(base_ref: str = "master", head_ref: str = "HEAD") -> List[OffLimitsViolation]:
    """Return list of violations. Empty list = PASS."""
    violations: List[OffLimitsViolation] = []
    for path in changed_files(base_ref, head_ref):
        hit, kind, value = _is_violation(path)
        if hit:
            violations.append(OffLimitsViolation(path=path, rule_kind=kind, rule_value=value))
    return violations


def format_report(violations: List[OffLimitsViolation], base_ref: str, head_ref: str) -> str:
    if not violations:
        return f"off-limits PASS — 0 violations in {base_ref}..{head_ref}"
    lines = [f"off-limits FAIL — {len(violations)} violations in {base_ref}..{head_ref}:"]
    for v in violations:
        lines.append(f"  - {v.path}  (matched {v.rule_kind}={v.rule_value!r})")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    base = sys.argv[1] if len(sys.argv) > 1 else "master"
    head = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    vios = check_off_limits(base, head)
    print(format_report(vios, base, head))
    sys.exit(0 if not vios else 1)
