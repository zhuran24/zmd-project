"""
Preflight gate — 提交前自动门禁检查。

用法：
    python scripts/preflight_gate.py              # 检查 staged changes
    python scripts/preflight_gate.py --full       # 全量检查（含 pytest）
    python scripts/preflight_gate.py --hook       # 作为 git pre-commit hook 运行
    python scripts/preflight_gate.py --ci --base-ref origin/main

当前检查面：
    冻结/外部制品、禁止路径、AI 与 exact/exploratory 隔离、调研覆盖、行尾、
    secret、artifact boundary、Phase review gate、P1.2 obligations、
    strong-status allowlist、mypy、ruff、pytest lanes 与记忆层测试 lane。

    旧的文档主体投影/文档树脚本已退役，本 gate 不运行
    scripts/sync_doc_subjects.py、scripts/check_doc_tree_completeness.py 或 cc_context workflow。

退出码：
    0 = 通过
    1 = 有硬阻塞问题（警告不会产生单独的 exit 2）
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_timeout_scale() -> float:
    """PREFLIGHT_TIMEOUT_SCALE: 慢执行环境(如 2 核 CI runner)对子检查超时的统一放大系数。

    默认 1.0(本机行为逐字节不变)。非法值 fail-closed 直接退出——门禁的超时参数
    被静默改坏比跑得慢更危险。2026-07-11 起因: 仓库长大后 checker(>30s)与快 lane
    pytest(>240s)在 GitHub 2 核 runner 上双超时, 而同批本机与 CI slow job 全绿。
    """
    raw = os.environ.get("PREFLIGHT_TIMEOUT_SCALE")
    if raw is None or raw.strip() == "":
        return 1.0
    try:
        scale = float(raw)
    except ValueError:
        print(f"FATAL: Unsupported PREFLIGHT_TIMEOUT_SCALE: {raw!r}; expected a positive number.")
        sys.exit(1)
    if not (scale > 0) or scale != scale or scale == float("inf"):
        print(f"FATAL: Unsupported PREFLIGHT_TIMEOUT_SCALE: {raw!r}; expected a positive finite number.")
        sys.exit(1)
    return scale


_TIMEOUT_SCALE = _resolve_timeout_scale()
BASELINE_PATH = PROJECT_ROOT / "scripts" / "preflight_baseline.json"

FROZEN_ARTIFACTS = {
    "rules/canonical_rules.json": "B675FB6A1CDAE7920F90ABF63E59AA76EA8DF37AE8A8C5D5D15B10B94218C4CA",
    # R6-F-01: the plan feeds runtime operation profiles / binding utility slots,
    # so it is hash-bound like the canonical rules (also in campaign hash closure).
    "rules/preprocess_plan.json": "5C669C4FA48D2ED77A3283F06C1D5F97F7542C92253C41BA31FBABA0B313C4EE",
    "data/preprocessed/mandatory_exact_instances.json": "545B98C2B4F96643F1346B423EDF2DC8E300A0C815B6CF821776CEED03CD4CD6",
    "data/preprocessed/generic_io_requirements.json": "AD5125B50E607A7F3F3BF0B54FEA64F93EDF87CEDB62E8D24F5590E1C895C44E",
}

EXTERNAL_FROZEN_ARTIFACTS = {
    # Distribution policy permits a lightweight checkout to omit this 51.9 MiB payload.
    # The current audited working tree includes it. Whenever present, preflight verifies
    # exact bytes; when absent, a certified run must restore/verify it before solve time.
    "data/preprocessed/candidate_placements.json": {
        "sha256": "F05B1291A51D64A1BC40507146E95F3257EFFAAF2B795A0FA83F85F5D8D280D3",
        "size_bytes": 54_467_709,
        "policy_doc": "PROJECT_LOCK.md",
    },
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


CHANGE_SCOPE_FILES: list[str] | None = None
CHANGE_SCOPE_LABEL = "staged"
CHANGE_SCOPE_BASE_REF: str | None = None
STRICT_TOOL_TIMEOUTS = False


def _git_run(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
    except FileNotFoundError:
        return None


def _git_lines(args: list[str]) -> list[str]:
    result = _git_run(args)
    if result is None or result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _git_diff_text_for_file(rel_path: str) -> tuple[str, str | None]:
    """Return the relevant diff text for one repo-relative file.

    Local hook/staged mode reads the index diff.  CI mode must inspect
    BASE...HEAD; otherwise a committed PR change leaves no cached diff and the
    exact/exploratory and research-audit gates silently become no-ops.
    """
    if CHANGE_SCOPE_BASE_REF:
        for range_expr in (f"{CHANGE_SCOPE_BASE_REF}...HEAD", f"{CHANGE_SCOPE_BASE_REF}..HEAD"):
            result = _git_run(["diff", "--unified=0", range_expr, "--", rel_path])
            if result is not None and result.returncode == 0:
                return result.stdout, None
        return "", f"cannot diff {CHANGE_SCOPE_BASE_REF} against HEAD for {rel_path}"

    result = _git_run(["diff", "--cached", "--unified=0", "--", rel_path])
    if result is None:
        return "", "git 不可用"
    if result.returncode != 0:
        return "", f"cannot read staged diff for {rel_path}"
    return result.stdout, None


def _added_lines_from_diff(diff_text: str) -> list[str]:
    return [line[1:] for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++")]


def _warn_or_block_tool_timeout(gate: GateResult, msg: str) -> None:
    if STRICT_TOOL_TIMEOUTS:
        gate.block(msg)
    else:
        gate.warn(msg)


def _load_changed_files_file(path: Path) -> list[str]:
    return [line.strip().replace("\\", "/") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def configure_change_scope(
    *, ci: bool = False, base_ref: str | None = None, changed_files_from: Path | None = None
) -> None:
    """Configure the file-diff scope used by staged-diff gates.

    Local pre-commit mode uses staged files. CI/PR mode must not rely on staged
    files, so it compares BASE...HEAD or reads an explicit changed-files list.
    """
    global CHANGE_SCOPE_FILES, CHANGE_SCOPE_LABEL, CHANGE_SCOPE_BASE_REF
    if changed_files_from is not None:
        CHANGE_SCOPE_FILES = _load_changed_files_file(changed_files_from)
        CHANGE_SCOPE_LABEL = f"changed-files:{changed_files_from}"
        CHANGE_SCOPE_BASE_REF = base_ref
        return
    if ci:
        if not base_ref:
            base_ref = "origin/main"
        diff = _git_lines(["diff", "--name-only", f"{base_ref}...HEAD"])
        if not diff:
            diff = _git_lines(["diff", "--name-only", f"{base_ref}..HEAD"])
        CHANGE_SCOPE_FILES = [line.replace("\\", "/") for line in diff]
        CHANGE_SCOPE_LABEL = f"ci:{base_ref}...HEAD"
        CHANGE_SCOPE_BASE_REF = base_ref
        return
    CHANGE_SCOPE_FILES = None
    CHANGE_SCOPE_LABEL = "staged"
    CHANGE_SCOPE_BASE_REF = None


def get_staged_files() -> list[str]:
    if CHANGE_SCOPE_FILES is not None:
        return CHANGE_SCOPE_FILES
    return [line.replace("\\", "/") for line in _git_lines(["diff", "--cached", "--name-only"])]


def check_frozen_artifacts(gate: GateResult) -> None:
    print("\n[1/18] 冻结/外部制品 hash 校验")
    for rel_path, expected_hash in FROZEN_ARTIFACTS.items():
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            gate.block(f"checked-in 冻结制品不存在: {rel_path}")
            continue
        actual_hash = sha256_file(full_path)
        if actual_hash == expected_hash:
            gate.ok(f"{rel_path}")
        else:
            gate.block(f"{rel_path} hash 不匹配!\n         期望: {expected_hash}\n         实际: {actual_hash}")

    for rel_path, info in EXTERNAL_FROZEN_ARTIFACTS.items():
        full_path = PROJECT_ROOT / rel_path
        expected_hash = str(info["sha256"])
        expected_size = int(info["size_bytes"])
        if not full_path.exists():
            gate.ok(
                f"{rel_path} 外部大制品在本 checkout 缺失（distribution policy permits omission） "
                f"(expected sha256={expected_hash.lower()}, size={expected_size}; see {info['policy_doc']})"
            )
            continue
        actual_size = full_path.stat().st_size
        actual_hash = sha256_file(full_path)
        if actual_hash == expected_hash and actual_size == expected_size:
            gate.ok(f"{rel_path} restored external artifact")
        else:
            gate.block(
                f"{rel_path} external artifact 不匹配!\n"
                f"         期望 hash: {expected_hash}\n"
                f"         实际 hash: {actual_hash}\n"
                f"         期望 size: {expected_size}\n"
                f"         实际 size: {actual_size}"
            )


def check_forbidden_paths(gate: GateResult) -> None:
    print("\n[3/18] 禁止路径写入检查")
    staged = get_staged_files()
    if not staged:
        gate.ok(f"无 {CHANGE_SCOPE_LABEL} 文件（或不在 git 仓库中）")
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
    print("\n[4/18] AI 安全合同检查")
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
    print("\n[5/18] 精确/探索边界隔离检查")
    staged = get_staged_files()
    if not staged:
        gate.ok(f"无 {CHANGE_SCOPE_LABEL} 文件")
        return

    exact_staged = [f for f in staged if f.replace("\\", "/") in EXACT_MODE_FILES]

    if not exact_staged:
        gate.ok("本次提交未修改精确求解核心文件")
        return

    violations = []
    for rel in exact_staged:
        full_path = PROJECT_ROOT / rel
        if not full_path.exists():
            continue
        diff_text, diff_error = _git_diff_text_for_file(rel)
        if diff_error:
            gate.block(f"无法读取 {CHANGE_SCOPE_LABEL} diff: {diff_error}")
            continue

        added_lines = _added_lines_from_diff(diff_text)

        for pattern in EXPLORATORY_LEAK_PATTERNS:
            for line in added_lines:
                if pattern.lower() in line.lower():
                    violations.append((rel, pattern, line.strip()))

    if violations:
        for rel, pattern, line_text in violations:
            gate.block(f"探索性约束泄漏到精确模式: {rel}\n         模式: '{pattern}'\n         内容: {line_text}")
    else:
        gate.ok(f"已检查 {len(exact_staged)} 个核心文件的 diff，无探索性泄漏")

    gate.warn(
        f"本次提交修改了精确求解核心文件: {', '.join(exact_staged)}\n         建议做一次 AI 语义审查确认求解语义未变"
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
    "src/tests/test_phase_review_gate.py",
    "src/tests/test_p1_2_proof_obligations.py",
    # Phase 1.2 close gate is a cut-soundness gate: F1-F9 validator/evaluator/
    # generator regressions must be caught by normal CI/preflight, not only by
    # ad-hoc manual sweeps.
    "src/tests/cuts",
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
    """[6/18] 调研产物 audit 覆盖检查 (memory feedback_research_roi_metric v2)。

    R13 教训: 调研 agent 报告即使引用 URL 也常出错 (5/5 历史 audit 翻盘)。
    路线图 / INDEX 改动如新增 R-N 调研引用，必须配套有 audit (agent ID) 引用。
    [W] warning 不阻塞 — audit 可能在另一 commit, 但提醒一下避免漏审。
    """
    print("\n[6/18] 调研产物 audit 覆盖检查")
    staged = get_staged_files()
    touched = [f for f in staged if f.replace("\\", "/") in RESEARCH_TRACKED_FILES]
    if not touched:
        gate.ok("本次提交未修改路线图 / INDEX")
        return

    research_refs: set[str] = set()
    audit_refs: set[str] = set()
    for rel in touched:
        diff_text, diff_error = _git_diff_text_for_file(rel)
        if diff_error:
            gate.block(f"无法读取 {CHANGE_SCOPE_LABEL} diff: {diff_error}")
            continue
        added = "\n".join(_added_lines_from_diff(diff_text))
        research_refs.update(_RESEARCH_REF_PATTERN.findall(added))
        audit_refs.update(_AUDIT_REF_PATTERN.findall(added))

    if not research_refs:
        gate.ok(f"路线图 / INDEX 改动 {len(touched)} 个文件，无新增 R-N 调研引用（可能是工时 / verdict 修订）")
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


def _run_script_check(
    gate: GateResult, *, title: str, script_name: str, ok_prefix: str, timeout: int = 30, args: list[str] | None = None
) -> None:
    timeout = max(1, int(timeout * _TIMEOUT_SCALE))
    script = PROJECT_ROOT / "scripts" / script_name
    if not script.exists():
        gate.block(f"{ok_prefix} 脚本不存在: scripts/{script_name}")
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script), *(args or [])],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        gate.block(f"{ok_prefix} 超时 (>{timeout}s)")
        return
    except FileNotFoundError:
        gate.warn(f"python 不可用 — 跳过 {ok_prefix}")
        return
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode == 0:
        gate.ok(out.splitlines()[-1] if out else f"{ok_prefix} passed")
        return
    summary = out.splitlines()[0] if out else (err.splitlines()[0] if err else "non-zero exit")
    gate.block(f"{ok_prefix}: {summary}")
    for line in (out.splitlines() + err.splitlines())[:12]:
        print(f"         {line}")


def check_external_artifact_manifest(gate: GateResult) -> None:
    print("\n[2/18] 外部大制品 contract 检查")
    _run_script_check(
        gate, title="external artifacts", script_name="check_external_artifacts.py", ok_prefix="external artifact check"
    )


def check_line_ending_policy(gate: GateResult) -> None:
    print("\n[9/18] 行尾策略检查")
    _run_script_check(
        gate, title="line endings", script_name="check_line_endings.py", ok_prefix="line-ending policy check"
    )


def check_artifact_boundaries(gate: GateResult) -> None:
    print("\n[12/18] 历史证据/生成制品边界检查")
    _run_script_check(
        gate,
        title="artifact boundaries",
        script_name="check_artifact_boundaries.py",
        ok_prefix="artifact boundary check",
    )


def check_phase_review_gate(gate: GateResult) -> None:
    print("\n[13/18] Phase review close-gate 状态一致性检查")
    _run_script_check(
        gate, title="phase review gate", script_name="check_phase_review_gate.py", ok_prefix="phase review gate check"
    )


def check_p1_2_proof_obligations(gate: GateResult) -> None:
    print("\n[14/18] P1.2 proof obligation consolidation 检查")
    _run_script_check(
        gate,
        title="P1.2 proof obligations",
        script_name="check_p1_2_proof_obligations.py",
        ok_prefix="P1.2 proof obligation check",
    )


def check_strong_status_write_allowlist(gate: GateResult) -> None:
    print("\n[15/18] P1.2 strong-status write allowlist 检查")
    _run_script_check(
        gate,
        title="P1.2 strong-status write allowlist",
        script_name="check_strong_status_write_allowlist.py",
        ok_prefix="P1.2 strong-status write allowlist check",
    )


def check_publish_secret_scan(gate: GateResult) -> None:
    """[10/18] 发布安全 secret scan.

    这层扫描当前 tracked/untracked 工作区文本, 防止 API key / token / private key
    重新进入当前树。它不宣称清理 Git 历史; 已暴露 credential 仍需 owner 侧轮换。
    """
    print("\n[10/18] 发布安全 secret scan")
    script = PROJECT_ROOT / "scripts" / "check_repo_secrets.py"
    if not script.exists():
        gate.block("secret scan 脚本不存在: scripts/check_repo_secrets.py")
        return
    timeout = max(1, int(30 * _TIMEOUT_SCALE))
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        gate.block(f"secret scan 超时 (>{timeout}s)")
        return
    except FileNotFoundError:
        gate.warn("python 不可用 — 跳过 secret scan")
        return

    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode == 0:
        gate.ok(out.splitlines()[-1] if out else "repo secret scan passed")
        return
    summary = out.splitlines()[0] if out else (err.splitlines()[0] if err else "non-zero exit")
    gate.block(f"repo secret scan: {summary}")
    for line in (out.splitlines() + err.splitlines())[:12]:
        print(f"         {line}")


MYPY_STRICT_TARGETS = [
    # GPT v4 follow-up G2/G3/G4: cut lifecycle + 求解核心两个大文件都进 strict gate.
    # 历史类型错全清 (master_model 69 错, benders_loop 8 错), 由 _Any annotation
    # 一招扫掉 ortools .pyi 不全的 attr-defined + 真 type bug 单点修.
    "src/models/cut_manager.py",
    "src/models/power_placement_subproblem.py",
    "src/models/master_model.py",
    "src/search/benders_loop.py",
    # 阶段 B typed TCB 新文件 (B1/B1.5/B2/B3/B5a): strict 全绿是双审验收项, 进 gate 防漂移.
    "src/cuts/frozen_artifacts.py",
    "src/cuts/state_snapshot.py",
    "src/cuts/typed_platform.py",
    "src/cuts/typed_apply.py",
    "src/cuts/families/region_capacity_typed.py",
    "src/cuts/families/power_hitting_set_typed.py",
    "src/cuts/families/shape_packing_hall_typed.py",
    # RFC-002 批 D: F5 独立 verifier (TCB) — strict 进 gate 同 B5a 先例.
    "src/cuts/verifiers/binding_empty_domain_verifier.py",
    # 批E: audit-channel cut ledger (close-kernel 外, spec 08 §5 — strict+测试钉).
    "src/cuts/ledger.py",
]


def check_mypy(gate: GateResult) -> None:
    """GPT v4 follow-up G2: mypy 严格 gate cut lifecycle 核心.

    锁 BendersCut + CutManager + PowerPlacementSubproblem 不让类型生命周期破洞
    再次发生 (lifecycle bug 根因是 schema 字段落了但 runtime resolver 没跟上).
    """
    print("\n[16/18] mypy 静态类型 (core lifecycle)")
    existing = [t for t in MYPY_STRICT_TARGETS if (PROJECT_ROOT / t).exists()]
    if not existing:
        gate.warn("mypy gate 目标文件不存在 — 跳过")
        return
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "mypy",
                "--explicit-package-bases",
                "--ignore-missing-imports",
                "--follow-imports=silent",
                *existing,
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=60,
            env={**os.environ, "MYPYPATH": str(PROJECT_ROOT)},
        )
    except subprocess.TimeoutExpired:
        _warn_or_block_tool_timeout(gate, "mypy 超时 (>60s) — 跳过")
        return
    except FileNotFoundError:
        _warn_or_block_tool_timeout(gate, "mypy 未安装 — 跳过")
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
    print("\n[17/18] ruff 静态检查")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "."],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        _warn_or_block_tool_timeout(gate, "ruff 超时 (>30s) — 跳过")
        return
    except FileNotFoundError:
        _warn_or_block_tool_timeout(gate, "ruff 未安装 — 跳过")
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


def _pytest_xdist_available() -> bool:
    return importlib.util.find_spec("xdist") is not None


def check_tests(gate: GateResult, *, full: bool = False) -> None:
    label = ("全量" if full else "核心门禁") + " · 跳过 @slow"
    print(f"\n[18/18] 测试门禁（{label}）")
    test_target = "src/tests/" if full else None
    test_files = None if full else CORE_TEST_FILES
    timeout = max(1, int((1200 if full else 240) * _TIMEOUT_SCALE))

    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short", "--no-header"]
    # 慢测试(@pytest.mark.slow)由专用慢 lane (preflight_gate.py --slow-tests) 用长超时真跑;
    # 快 gate 用 -m "not slow" 跳过它们, 否则慢集成测试会撑爆超时、把失败掩盖掉
    # —— 这正是让 ④b-stale 测试藏住的 C5 done-condition 盲区根因。
    # -n auto: 剔掉慢测试后快 lane 全是隔离单元测试, pytest-xdist 跨核并行, 用满硬件。
    # 慢 lane 刻意不并行(见 check_slow_tests)。
    # timeout 2026-07-08 从 120s 提到 240s: CORE_TEST_FILES 已随 close-gate 膨胀到
    # ~1035 条(src/tests/cuts 整目录进核心门禁后), -n auto 实测 118s, 120s 上限从
    # 「5 倍余量」退化成了「贴线必炸」;240s 恢复 ~2 倍余量。集合再膨胀先想拆分, 别只加时。
    # xdist 是提速, 不是语义前提: 插件不可用时退回串行, 避免 CI 因未知 -n 参数假失败。
    cmd += ["-m", "not slow"]
    if _pytest_xdist_available():
        cmd += ["-n", "auto"]
    else:
        print("  NOTE   pytest-xdist 不可用, 快 lane 退回串行 pytest")
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
            cmd,
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=timeout,
            env=pytest_env,
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


def check_slow_tests(gate: GateResult, *, require_collection: bool = False) -> None:
    # 专用慢 soundness lane: 跑 @pytest.mark.slow 的重型集成测试, 用长超时真跑到完成。
    # 堵住「快 gate 超时吞掉慢 soundness 测试失败」的 C5 盲区 —— CI / 阶段收口前必须跑、
    # 且必须看它的 pass/fail。刻意不并行(-n): 这些测试自身会 spawn 子进程(parallel
    # scheduler / ④b 隔离 `python -I` replay), xdist 叠加会过度订阅 CPU/内存、放大 ④b
    # replay 的偶发降级(harness flaky, 见 task #13)。提速到 xdist 需先根因那个 flaky。
    print("\n[slow] 慢 soundness 测试 lane（-m slow, 长超时, 串行)")
    timeout = 2400
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "--no-header",
        "-m",
        "slow",
        "src/tests",
    ]
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
            cmd,
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=timeout,
            env=pytest_env,
        )
        last_lines = [line for line in result.stdout.splitlines() if line.strip()][-3:]
        summary_line = last_lines[-1] if last_lines else ""
        if result.returncode == 0:
            gate.ok(f"pytest (slow): {summary_line}")
        elif result.returncode == 5:
            msg = "pytest (slow): 未收集到 @slow 测试 — 标记缺失? (慢 lane 形同虚设)"
            if require_collection:
                gate.block(msg)
            else:
                gate.warn(msg)
        else:
            gate.block(f"pytest (slow) 失败 (exit={result.returncode}): {summary_line}")
            if result.stdout:
                for line in result.stdout.splitlines()[-15:]:
                    print(f"         {line}")
    except subprocess.TimeoutExpired:
        gate.block(f"pytest (slow) 超时 (>{timeout}s)")
    except FileNotFoundError:
        msg = "pytest 不可用，跳过慢测试"
        if require_collection:
            gate.block(msg)
        else:
            gate.warn(msg)


MEMORY_TEST_DIRS = ("cc_memory/tests", "cc_memory_vnext/tests")
MEMORY_SCOPE_PREFIXES = ("cc_memory/", "cc_memory_vnext/")


def check_memory_tests(gate: GateResult, *, always: bool) -> None:
    """记忆层测试 lane：cc_memory + cc_memory_vnext 两个目录。

    这两个目录 2026-08-03 之前不被任何门收集（普查 §3.6）——200+ 条测试守着活
    hook（SessionStart 注入 / UserPromptSubmit / PreToolUse 高危闸），改坏了没有
    任何机械会说话。快 lane 只跑 `src/tests/`，所以它们必须有自己的一条。

    与既有 pytest lane 的三点差异，都是被这两个目录的性质逼出来的：
    - 不并行（-n）：这里大量用例真起子进程跑 hook，xdist 叠加只会互相挤。
    - 独立 basetemp：pytest.ini 的全局 `--basetemp=.pytest_tmp` 会被并发 pytest
      互删，而本 lane 常常跟主 lane 同时在跑。
    - 只在动到 cc_memory*/ 时进 staged 范围；--full / --ci 一律跑。

    两个目录任一不存在 = BLOCK，不是 warning（2026-08-03 对抗审查
    missing-memory-test-roots）。这条 lane 的全部意义是「这些测试真的被跑
    了」，而删掉一个目录、把它 rename 走、或者在 checkout 里根本没拉下来，
    都会让缺失的那半悄悄消失；旧写法只有两个目录**同时**消失才 warn 一句、
    退出码照样 0，少一个则连一句话都没有。缺目录只可能是两种情况——真删了
    （那要先改这里的登记），或者树不完整（那这次门禁本来就不该算数）——两
    种都该拦。
    """
    scope_note = "全量" if always else "staged 触及 cc_memory*/"
    print(f"\n[memory] 记忆层测试 lane（{scope_note}，串行，-p no:randomly）")

    missing = [target for target in MEMORY_TEST_DIRS if not (PROJECT_ROOT / target).is_dir()]
    if missing:
        gate.block(
            f"记忆层测试根缺失: {', '.join(missing)} — 这条 lane 守着活 hook，"
            "少一个根就等于那一半没人跑；真要下线先改 MEMORY_TEST_DIRS"
        )
        return

    if not always:
        touched = [
            path
            for path in get_staged_files()
            if any(path.startswith(prefix) for prefix in MEMORY_SCOPE_PREFIXES)
        ]
        if not touched:
            gate.ok("记忆层未改动，跳过记忆测试 lane")
            return

    existing = list(MEMORY_TEST_DIRS)

    # pytest 只建 basetemp 本身，父目录不存在就整批 setup error（144 条 ERROR、
    # 报告里看起来像测试真的坏了）——在干净 checkout / 新 worktree 上必然发生。
    #
    # 目录名带 pid + 时间戳：固定名字的 basetemp 会被并发的另一次 preflight
    # 当场删掉重建（pytest 启动时清理自己的 basetemp），先起的那个进程正在用
    # 的 tmp_path 就凭空消失、报出与被测代码无关的假红。同一台机器上并发跑
    # 门禁是常态（多窗口 / wf 并发），所以每次调用给自己一个唯一目录。
    basetemp = PROJECT_ROOT / ".pytest_tmp" / f"memory_gate_{os.getpid()}_{time.time_ns()}"
    basetemp.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "--no-header",
        "-p",
        "no:randomly",
        "--basetemp",
        str(basetemp),
        *existing,
    ]
    timeout = max(1, int(300 * _TIMEOUT_SCALE))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=timeout
        )
    except subprocess.TimeoutExpired:
        gate.block(f"pytest (memory) 超时 (>{timeout}s)")
        return
    except FileNotFoundError:
        gate.warn("pytest 不可用，跳过记忆层测试")
        return

    last_lines = [line for line in result.stdout.splitlines() if line.strip()][-3:]
    summary_line = last_lines[-1] if last_lines else ""
    if result.returncode == 0:
        gate.ok(f"pytest (memory): {summary_line}")
        return
    if result.returncode == 5:
        gate.block("pytest (memory): 未收集到测试 — 记忆 lane 形同虚设")
        return
    gate.block(f"pytest (memory) 失败 (exit={result.returncode}): {summary_line}")
    for line in result.stdout.splitlines()[-10:]:
        print(f"         {line}")


def run_gate(
    *,
    full: bool = False,
    hook: bool = False,
    ci: bool = False,
    slow_tests: bool = False,
    base_ref: str | None = None,
    changed_files_from: Path | None = None,
) -> int:
    print("=" * 60)
    print("Preflight Gate — 提交前门禁检查")
    print("=" * 60)
    global STRICT_TOOL_TIMEOUTS
    STRICT_TOOL_TIMEOUTS = ci
    configure_change_scope(ci=ci, base_ref=base_ref, changed_files_from=changed_files_from)
    mode = "slow-tests" if slow_tests else ("full" if full else ("ci" if ci else ("hook" if hook else "staged")))
    print(f"模式: {mode}")
    print(f"变更范围: {CHANGE_SCOPE_LABEL}")

    gate = GateResult()

    if slow_tests:
        # 专用慢 soundness lane (CI / 阶段收口前): 只跑 @slow 重型测试, 长超时真跑到完成。
        check_slow_tests(gate, require_collection=True)
    else:
        check_frozen_artifacts(gate)
        check_external_artifact_manifest(gate)
        check_forbidden_paths(gate)
        check_ai_safety_contract(gate)
        check_exact_exploratory_isolation(gate)
        check_research_audit_coverage(gate)
        check_line_ending_policy(gate)
        check_publish_secret_scan(gate)
        check_artifact_boundaries(gate)
        check_phase_review_gate(gate)
        check_p1_2_proof_obligations(gate)
        check_strong_status_write_allowlist(gate)
        check_mypy(gate)
        check_ruff(gate)

        if full:
            check_tests(gate, full=True)
        elif hook:
            check_tests(gate, full=False)
        else:
            check_tests(gate, full=False)

        # 记忆层 lane 挂在最后，既有 step 的顺序与语义一个没动。
        check_memory_tests(gate, always=full or ci)

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
    parser.add_argument("--full", action="store_true", help="全量检查（含 pytest, -m 'not slow'）")
    parser.add_argument("--hook", action="store_true", help="作为 git pre-commit hook 运行（快速模式）")
    parser.add_argument("--ci", action="store_true", help="按 base...HEAD diff 运行 PR/CI 变更范围检查")
    parser.add_argument(
        "--slow-tests",
        action="store_true",
        help="只跑专用慢 soundness 测试 lane（-m slow, 长超时, 串行；CI/阶段收口前必跑）",
    )
    parser.add_argument("--base-ref", default=None, help="CI diff base ref/SHA，默认 origin/main")
    parser.add_argument(
        "--changed-files-from", type=Path, default=None, help="从文件读取变更路径列表，每行一个 repo-relative path"
    )
    args = parser.parse_args()
    sys.exit(
        run_gate(
            full=args.full,
            hook=args.hook,
            ci=args.ci,
            slow_tests=args.slow_tests,
            base_ref=args.base_ref,
            changed_files_from=args.changed_files_from,
        )
    )


if __name__ == "__main__":
    main()
