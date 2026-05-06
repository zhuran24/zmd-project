"""
Preflight gate — 提交前自动门禁检查。

用法：
    python scripts/preflight_gate.py              # 检查 staged changes
    python scripts/preflight_gate.py --full       # 全量检查（含 pytest）
    python scripts/preflight_gate.py --hook       # 作为 git pre-commit hook 运行

检查项：
    1. 冻结制品 hash 校验（canonical_rules, candidate_placements 等）
    2. 禁止路径写入检查（checkpoint, proof, blueprint）
    3. AI 安全合同检查（ai_accel 不碰 proof 路径）
    4. 精确/探索边界隔离检查
    5. pytest 测试（仅 --full 模式）

退出码：
    0 = 通过
    1 = 有硬阻塞问题
    2 = 通过但有警告
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = PROJECT_ROOT / "scripts" / "preflight_baseline.json"

FROZEN_ARTIFACTS = {
    "rules/canonical_rules.json": "8AC667A1BCE67FF9084701D18892F370E19D68CC9B5ACE44BD63C68B20D3D6EA",
    "data/preprocessed/candidate_placements.json": "D5E3911FC1BC7C0AB48D67B981D28E8090741B04884C475E78DC0E128CA4683F",
    "data/preprocessed/mandatory_exact_instances.json": "545B98C2B4F96643F1346B423EDF2DC8E300A0C815B6CF821776CEED03CD4CD6",
    "data/preprocessed/generic_io_requirements.json": "AD5125B50E607A7F3F3BF0B54FEA64F93EDF87CEDB62E8D24F5590E1C895C44E",
}

FORBIDDEN_STAGED_PATHS = [
    "data/checkpoints/",
    "data/blueprints/optimal_blueprint.json",
    "data/solutions/final_solution.json",
    "data/solutions/certified_delivery_manifest.json",
]

AI_MODULE_ROOT = "src/ai_accel"
AI_FORBIDDEN_PATH_REFS = [
    "data/checkpoints",
    "data/solutions",
    "data/blueprints",
]

AI_FORBIDDEN_FILE_OPS = [
    "open(",
    "write_text(",
    "write_bytes(",
    "Path(",
    "pathlib",
    "shutil",
]

EXPLORATORY_LEAK_PATTERNS = [
    "exploratory_optional_caps",
    "50 power poles",
    "10 storage boxes",
    "10 protocol storage",
    "50 power_pole",
    "10 protocol_storage_box",
]

EXACT_MODE_FILES = [
    "src/models/master_model.py",
    "src/models/exact_coordinate_master.py",
    "src/search/outer_search.py",
    "src/search/benders_loop.py",
    "src/search/exact_campaign.py",
    "src/search/exact_parallel_scheduler.py",
]


class GateResult:
    def __init__(self) -> None:
        self.blockers: list[str] = []
        self.warnings: list[str] = []
        self.passed: list[str] = []

    def block(self, msg: str) -> None:
        self.blockers.append(msg)
        print(f"  BLOCK  {msg}")

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        print(f"  WARN   {msg}")

    def ok(self, msg: str) -> None:
        self.passed.append(msg)
        print(f"  OK     {msg}")

    @property
    def exit_code(self) -> int:
        if self.blockers:
            return 1
        if self.warnings:
            return 2
        return 0

    def summary(self) -> str:
        parts = [f"{len(self.passed)} passed"]
        if self.warnings:
            parts.append(f"{len(self.warnings)} warnings")
        if self.blockers:
            parts.append(f"{len(self.blockers)} BLOCKED")
        return ", ".join(parts)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def get_staged_files() -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            return []
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except FileNotFoundError:
        return []


def check_frozen_artifacts(gate: GateResult) -> None:
    print("\n[1/5] 冻结制品 hash 校验")
    for rel_path, expected_hash in FROZEN_ARTIFACTS.items():
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            gate.block(f"冻结制品不存在: {rel_path}")
            continue
        actual_hash = sha256_file(full_path)
        if actual_hash == expected_hash:
            gate.ok(f"{rel_path}")
        else:
            gate.block(
                f"{rel_path} hash 不匹配!\n"
                f"         期望: {expected_hash}\n"
                f"         实际: {actual_hash}"
            )


def check_forbidden_paths(gate: GateResult) -> None:
    print("\n[2/5] 禁止路径写入检查")
    staged = get_staged_files()
    if not staged:
        gate.ok("无 staged 文件（或不在 git 仓库中）")
        return

    violations = []
    for staged_file in staged:
        normalized = staged_file.replace("\\", "/")
        for forbidden in FORBIDDEN_STAGED_PATHS:
            if normalized.startswith(forbidden) or normalized == forbidden.rstrip("/"):
                violations.append((staged_file, forbidden))

    if violations:
        for staged_file, rule in violations:
            gate.block(f"禁止提交: {staged_file} (规则: {rule})")
    else:
        gate.ok(f"已检查 {len(staged)} 个 staged 文件，无禁止路径违规")


def check_ai_safety_contract(gate: GateResult) -> None:
    print("\n[3/5] AI 安全合同检查")
    ai_dir = PROJECT_ROOT / AI_MODULE_ROOT
    if not ai_dir.exists():
        gate.ok("ai_accel 目录不存在，跳过")
        return

    violations = []
    py_files = list(ai_dir.rglob("*.py"))
    for py_file in py_files:
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = py_file.relative_to(PROJECT_ROOT)
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for path_ref in AI_FORBIDDEN_PATH_REFS:
                if path_ref in line:
                    violations.append((str(rel), i, path_ref, stripped))

    if violations:
        for rel, lineno, pattern, line_text in violations:
            gate.block(f"AI 模块引用了禁止路径: {rel}:{lineno} 包含 '{pattern}'")
    else:
        gate.ok(f"已扫描 {len(py_files)} 个 AI 模块文件，无禁止引用")


def check_exact_exploratory_isolation(gate: GateResult) -> None:
    print("\n[4/5] 精确/探索边界隔离检查")
    staged = get_staged_files()
    if not staged:
        gate.ok("无 staged 文件")
        return

    exact_staged = [
        f for f in staged
        if f.replace("\\", "/") in EXACT_MODE_FILES
    ]

    if not exact_staged:
        gate.ok("本次提交未修改精确求解核心文件")
        return

    violations = []
    for rel in exact_staged:
        full_path = PROJECT_ROOT / rel
        if not full_path.exists():
            continue
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--cached", "--", rel],
                capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            )
            diff_text = diff_result.stdout
        except FileNotFoundError:
            continue

        added_lines = [
            line[1:] for line in diff_text.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]

        for pattern in EXPLORATORY_LEAK_PATTERNS:
            for line in added_lines:
                if pattern.lower() in line.lower():
                    violations.append((rel, pattern, line.strip()))

    if violations:
        for rel, pattern, line_text in violations:
            gate.block(
                f"探索性约束泄漏到精确模式: {rel}\n"
                f"         模式: '{pattern}'\n"
                f"         内容: {line_text}"
            )
    else:
        gate.ok(f"已检查 {len(exact_staged)} 个核心文件的 diff，无探索性泄漏")

    gate.warn(
        f"本次提交修改了精确求解核心文件: {', '.join(exact_staged)}\n"
        f"         建议做一次 AI 语义审查确认求解语义未变"
    )


CORE_TEST_FILES = [
    "src/tests/test_exact_contract.py",
    "src/tests/test_parallel_scheduler.py",
]


def check_tests(gate: GateResult, *, full: bool = False) -> None:
    label = "全量" if full else "核心门禁"
    print(f"\n[5/5] 测试门禁（{label}）")
    test_target = "src/tests/" if full else None
    test_files = None if full else CORE_TEST_FILES
    timeout = 600 if full else 120

    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short", "--no-header"]
    if test_files:
        existing = [f for f in test_files if (PROJECT_ROOT / f).exists()]
        if not existing:
            gate.warn("核心测试文件不存在，跳过")
            return
        cmd.extend(existing)
    else:
        cmd.append(test_target)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            timeout=timeout,
        )
        last_lines = [l for l in result.stdout.splitlines() if l.strip()][-3:]
        summary_line = last_lines[-1] if last_lines else ""

        if result.returncode == 0:
            gate.ok(f"pytest ({label}): {summary_line}")
        else:
            gate.block(f"pytest 失败 (exit={result.returncode}): {summary_line}")
            if result.stdout:
                for line in result.stdout.splitlines()[-10:]:
                    print(f"         {line}")
    except subprocess.TimeoutExpired:
        gate.block(f"pytest 超时 (>{timeout}s)")
    except FileNotFoundError:
        gate.warn("pytest 不可用，跳过测试")


def run_gate(*, full: bool = False, hook: bool = False) -> int:
    print("=" * 60)
    print("Preflight Gate — 提交前门禁检查")
    print("=" * 60)
    mode = "full" if full else ("hook" if hook else "staged")
    print(f"模式: {mode}")

    gate = GateResult()

    check_frozen_artifacts(gate)
    check_forbidden_paths(gate)
    check_ai_safety_contract(gate)
    check_exact_exploratory_isolation(gate)

    if full:
        check_tests(gate, full=True)
    elif hook:
        check_tests(gate, full=False)
    else:
        check_tests(gate, full=False)

    print("\n" + "=" * 60)
    verdict = "BLOCKED" if gate.blockers else ("PASSED (with warnings)" if gate.warnings else "PASSED")
    print(f"结果: {verdict}")
    print(f"统计: {gate.summary()}")
    if gate.blockers:
        print(f"\n有 {len(gate.blockers)} 个硬阻塞问题，提交被拒绝。")
    print("=" * 60)

    return gate.exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight gate — 提交前门禁检查")
    parser.add_argument("--full", action="store_true", help="全量检查（含 pytest）")
    parser.add_argument("--hook", action="store_true", help="作为 git pre-commit hook 运行（快速模式）")
    args = parser.parse_args()
    sys.exit(run_gate(full=args.full, hook=args.hook))


if __name__ == "__main__":
    main()
