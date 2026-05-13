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
    5. 调研产物 audit 覆盖检查
    6. mypy 严格类型 (cut lifecycle 核心两文件)
    7. ruff 全仓静态检查 (分层 ignore 在 ruff.toml)
    8. pytest 测试（核心门禁 / 全量取决于模式）

退出码：
    0 = 通过
    1 = 有硬阻塞问题
    2 = 通过但有警告
"""
from __future__ import annotations

import argparse
import hashlib
import re
import os
import subprocess
import sys
from pathlib import Path

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
    print("\n[1/8] 冻结制品 hash 校验")
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
    print("\n[2/8] 禁止路径写入检查")
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
    print("\n[3/8] AI 安全合同检查")
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
    print("\n[4/8] 精确/探索边界隔离检查")
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
    "src/tests/test_power_placement_subproblem.py",
    "src/tests/test_coordinate_benders_cut_presence_nogood.py",
    "src/tests/test_benders_cut_condition_lits.py",
    # GPT v4 follow-up: cut 生命周期 + power witness dilution 进核心门禁.
    "src/tests/test_benders_cut_replay_condition_lifecycle.py",
    "src/tests/test_power_witness_cut_dilution.py",
]


RESEARCH_TRACKED_FILES = {
    "docs/phase3c_optimization_roadmap_v1.md",
    "docs/research/INDEX.md",
}

# 匹配 R-N 调研引用 (e.g. "R13 `a8a448561dbacf07c`"). agent ID 是 16+ hex chars.
_RESEARCH_REF_PATTERN = re.compile(r"\bR\d+\s+`([0-9a-f]{16,})`")
# 匹配 audit 引用 (e.g. "audit `a062ff6396a691d74`" / "audit by `xxx`").
_AUDIT_REF_PATTERN = re.compile(r"\baudit\b[^`\n]{0,15}`([0-9a-f]{16,})`", re.IGNORECASE)


def check_research_audit_coverage(gate: GateResult) -> None:
    """[5/8] 调研产物 audit 覆盖检查 (memory feedback_research_roi_metric v2)。

    R13 教训: 调研 agent 报告即使引用 URL 也常出错 (5/5 历史 audit 翻盘)。
    路线图 / INDEX 改动如新增 R-N 调研引用，必须配套有 audit (agent ID) 引用。
    [W] warning 不阻塞 — audit 可能在另一 commit, 但提醒一下避免漏审。
    """
    print("\n[5/8] 调研产物 audit 覆盖检查")
    staged = get_staged_files()
    touched = [f for f in staged if f.replace("\\", "/") in RESEARCH_TRACKED_FILES]
    if not touched:
        gate.ok("本次提交未修改路线图 / INDEX")
        return

    research_refs: set[str] = set()
    audit_refs: set[str] = set()
    for rel in touched:
        try:
            diff_result = subprocess.run(
                ["git", "diff", "--cached", "--", rel],
                capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            )
        except FileNotFoundError:
            continue
        added = "\n".join(
            line[1:] for line in diff_result.stdout.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        research_refs.update(_RESEARCH_REF_PATTERN.findall(added))
        audit_refs.update(_AUDIT_REF_PATTERN.findall(added))

    if not research_refs:
        gate.ok(
            f"路线图 / INDEX 改动 {len(touched)} 个文件，无新增 R-N 调研引用"
            f"（可能是工时 / verdict 修订）"
        )
        return

    missing = research_refs - audit_refs
    if not missing:
        gate.ok(
            f"路线图 / INDEX 新增 {len(research_refs)} 个 R-N 调研引用，"
            f"全部配套 audit ({len(audit_refs)} 个 audit agent ID)"
        )
        return

    sample = ", ".join(sorted(missing)[:3])
    if len(missing) > 3:
        sample += "..."
    gate.warn(
        f"路线图 / INDEX 新增 {len(research_refs)} 个 R-N 调研引用，"
        f"{len(missing)} 个未看到配套 audit (agent IDs: {sample})。\n"
        f"         按 memory feedback_research_roi_metric.md v2: "
        f"调研产物进路线图前应做 zero-trust source-verify audit。"
        f"\n         如果 audit 在另一 commit / 已在过去 commit, 忽略本警告。"
    )


MYPY_STRICT_TARGETS = [
    # GPT v4 follow-up G2 scope: 只把 cut lifecycle 直接相关的两个 schema/runtime
    # 文件锁死 mypy 严格. benders_loop.py 太大, 历史类型错多, 单独修是大工程, 不
    # 进 gate; 但里面新加的 _resolve_condition_lits_from_condition_set helper 不报
    # 错 (mypy 整体跑过), 留 follow-up memory 记追加.
    "src/models/cut_manager.py",
    "src/models/power_placement_subproblem.py",
]


def check_mypy(gate: GateResult) -> None:
    """GPT v4 follow-up G2: mypy 严格 gate cut lifecycle 核心.

    锁 BendersCut + CutManager + PowerPlacementSubproblem 不让类型生命周期破洞
    再次发生 (lifecycle bug 根因是 schema 字段落了但 runtime resolver 没跟上).
    """
    print("\n[6/8] mypy 静态类型 (core lifecycle)")
    existing = [t for t in MYPY_STRICT_TARGETS if (PROJECT_ROOT / t).exists()]
    if not existing:
        gate.warn("mypy gate 目标文件不存在 — 跳过")
        return
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "mypy",
                "--explicit-package-bases",
                "--ignore-missing-imports",
                "--follow-imports=silent",
                *existing,
            ],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=60,
            env={**os.environ, "MYPYPATH": str(PROJECT_ROOT)},
        )
    except subprocess.TimeoutExpired:
        gate.warn("mypy 超时 (>60s) — 跳过")
        return
    except FileNotFoundError:
        gate.warn("mypy 未安装 — 跳过")
        return

    out = (result.stdout or "").strip()
    if result.returncode == 0:
        last = out.splitlines()[-1] if out else "no issues found"
        gate.ok(f"mypy: {last}")
        return
    summary = ""
    for line in out.splitlines()[::-1]:
        if line.startswith("Found "):
            summary = line.strip()
            break
    gate.block(f"mypy core lifecycle: {summary or 'non-zero exit'}")
    for line in out.splitlines()[:12]:
        print(f"         {line}")


def check_ruff(gate: GateResult) -> None:
    """GPT v4 follow-up G1: ruff 分层配置, core + scripts 全仓 0 警告.

    `ruff.toml` 已经把脚本入口的 sys.path-后-import 模式 (E402) 标 ignore,
    其他规则 (F4xx 系列 dead code / E7xx 命名 / W2xx 空白) 必须真过.
    跑全仓; 任何 warning 一律 BLOCK — 没有 "scripts 没事核心严格" 的二级容忍,
    因为 ruff.toml 已经把噪音吸收掉了.
    """
    print("\n[7/8] ruff 静态检查")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "."],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        gate.warn("ruff 超时 (>30s) — 跳过")
        return
    except FileNotFoundError:
        gate.warn("ruff 未安装 — 跳过")
        return

    if result.returncode == 0:
        last = (result.stdout or "All checks passed!").splitlines()[-1].strip()
        gate.ok(f"ruff: {last}")
        return

    # ruff exit !=0 → 有问题. count 简单 grep `Found N error`.
    out = result.stdout or ""
    summary = ""
    for line in out.splitlines()[::-1]:
        if line.startswith("Found "):
            summary = line.strip()
            break
    if not summary:
        summary = "ruff 报告非 0 退出 (见 stdout)"
    gate.block(f"ruff: {summary}")
    # 输出前几行细节方便定位
    for line in out.splitlines()[:8]:
        print(f"         {line}")


def check_tests(gate: GateResult, *, full: bool = False) -> None:
    label = "全量" if full else "核心门禁"
    print(f"\n[8/8] 测试门禁（{label}）")
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

    # 隔离 production runtime env vars 不污染 unit test: 部分 test 验证
    # default 行为 (e.g. UNKNOWN candidate 会被 retry), 而 EXACT_OUTER_SKIP_UNKNOWN
    # / EXACT_BINDING_DUMP_STATE 等 env 会改 default → 守卫 fail.
    pytest_env = os.environ.copy()
    for runtime_env in (
        "EXACT_OUTER_SKIP_UNKNOWN",
        "EXACT_BINDING_DUMP_STATE",
        "EXACT_MASTER_HINT_PERSISTENCE",
        "EXACT_BINDING_USE_OVERLOAD_SEPARATION",
    ):
        pytest_env.pop(runtime_env, None)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT),
            timeout=timeout, env=pytest_env,
        )
        last_lines = [line for line in result.stdout.splitlines() if line.strip()][-3:]
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
    check_research_audit_coverage(gate)
    check_mypy(gate)
    check_ruff(gate)

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
