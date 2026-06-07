"""
Preflight gate — 提交前自动门禁检查。

用法：
    python scripts/preflight_gate.py              # 检查 staged changes
    python scripts/preflight_gate.py --full       # 全量检查（含 pytest）
    python scripts/preflight_gate.py --hook       # 作为 git pre-commit hook 运行
    python scripts/preflight_gate.py --ci --base-ref origin/main

检查项：
    1. 冻结/外部制品 hash 校验（checked-in JSON + lightweight external artifacts）
    2. 外部大制品 contract 检查
    3. 禁止路径写入检查（checkpoint, proof, blueprint）
    4. AI 安全合同检查（ai_accel 不碰 proof 路径）
    5. 精确/探索边界隔离检查
    6. 调研产物 audit 覆盖检查
    7. 文档/记忆主体投影同步检查
    8. 文档树完整收尾检查
    9. 行尾策略检查
    10. 发布安全 secret scan
    11. 记忆树结构/currentness 检查
    12. 历史证据/生成制品边界检查
    13. mypy 严格类型 (cut lifecycle 核心两文件)
    14. ruff 全仓静态检查 (分层 ignore 在 ruff.toml)
    15. pytest 测试（核心门禁 / 全量取决于模式）

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
    "data/preprocessed/mandatory_exact_instances.json": "545B98C2B4F96643F1346B423EDF2DC8E300A0C815B6CF821776CEED03CD4CD6",
    "data/preprocessed/generic_io_requirements.json": "AD5125B50E607A7F3F3BF0B54FEA64F93EDF87CEDB62E8D24F5590E1C895C44E",
}

EXTERNAL_FROZEN_ARTIFACTS = {
    # The lightweight GitHub checkout intentionally omits this 53 MiB payload.
    # If the file is restored into the working tree, preflight verifies its bytes;
    # if it is absent, preflight records the external-artifact contract as OK and
    # certified exact runs remain responsible for restoring it before solve time.
    "data/preprocessed/candidate_placements.json": {
        "sha256": "D5E3911FC1BC7C0AB48D67B981D28E8090741B04884C475E78DC0E128CA4683F",
        "size_bytes": 53_594_995,
        "policy_doc": "START_HERE.md",
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
    return [
        line[1:] for line in diff_text.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def _warn_or_block_tool_timeout(gate: GateResult, msg: str) -> None:
    if STRICT_TOOL_TIMEOUTS:
        gate.block(msg)
    else:
        gate.warn(msg)


def _load_changed_files_file(path: Path) -> list[str]:
    return [line.strip().replace("\\", "/") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def configure_change_scope(*, ci: bool = False, base_ref: str | None = None, changed_files_from: Path | None = None) -> None:
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
    print("\n[1/15] 冻结/外部制品 hash 校验")
    for rel_path, expected_hash in FROZEN_ARTIFACTS.items():
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            gate.block(f"checked-in 冻结制品不存在: {rel_path}")
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

    for rel_path, info in EXTERNAL_FROZEN_ARTIFACTS.items():
        full_path = PROJECT_ROOT / rel_path
        expected_hash = str(info["sha256"])
        expected_size = int(info["size_bytes"])
        if not full_path.exists():
            gate.ok(
                f"{rel_path} 外部大制品未入轻量 checkout "
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
    print("\n[3/15] 禁止路径写入检查")
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
    print("\n[4/15] AI 安全合同检查")
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
    print("\n[5/15] 精确/探索边界隔离检查")
    staged = get_staged_files()
    if not staged:
        gate.ok(f"无 {CHANGE_SCOPE_LABEL} 文件")
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
    """[6/15] 调研产物 audit 覆盖检查 (memory feedback_research_roi_metric v2)。

    R13 教训: 调研 agent 报告即使引用 URL 也常出错 (5/5 历史 audit 翻盘)。
    路线图 / INDEX 改动如新增 R-N 调研引用，必须配套有 audit (agent ID) 引用。
    [W] warning 不阻塞 — audit 可能在另一 commit, 但提醒一下避免漏审。
    """
    print("\n[6/15] 调研产物 audit 覆盖检查")
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


def check_doc_subject_projections(gate: GateResult) -> None:
    """[7/15] 文档/记忆主体投影同步检查.

    项目知识树采用 subject/projection 架构: docs/subjects/*.md 是抽象主体,
    cc_context/knowledge/PROJECT_SUBJECT_PROJECTIONS.json 登记 docs + memory projection slots.
    这个 gate 只检查同步状态, 不自动写文件; 主体改动后运行
    `python scripts/sync_doc_subjects.py --sync`, 投影改动后运行 `--absorb`.
    """
    print("\n[7/15] 文档/记忆主体投影同步检查")
    script = PROJECT_ROOT / "scripts" / "sync_doc_subjects.py"
    registry = PROJECT_ROOT / "cc_context" / "knowledge" / "PROJECT_SUBJECT_PROJECTIONS.json"
    if not script.exists() or not registry.exists():
        gate.warn("文档主体/投影同步脚本或 registry 不存在 — 跳过")
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script), "--check"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        gate.block("doc subject projection check 超时 (>30s)")
        return
    except FileNotFoundError:
        gate.warn("python 不可用 — 跳过 doc subject projection check")
        return

    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode == 0:
        gate.ok(out.splitlines()[-1] if out else "doc subject projection check passed")
        return
    summary = out.splitlines()[0] if out else (err.splitlines()[0] if err else "non-zero exit")
    gate.block(f"doc subject projection check: {summary}")
    for line in (out.splitlines() + err.splitlines())[:12]:
        print(f"         {line}")


def _run_script_check(gate: GateResult, *, title: str, script_name: str, ok_prefix: str, timeout: int = 30, args: list[str] | None = None) -> None:
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
    print("\n[2/15] 外部大制品 contract 检查")
    _run_script_check(gate, title="external artifacts", script_name="check_external_artifacts.py", ok_prefix="external artifact check")


def check_line_ending_policy(gate: GateResult) -> None:
    print("\n[9/15] 行尾策略检查")
    _run_script_check(gate, title="line endings", script_name="check_line_endings.py", ok_prefix="line-ending policy check")


def check_artifact_boundaries(gate: GateResult) -> None:
    print("\n[12/15] 历史证据/生成制品边界检查")
    _run_script_check(gate, title="artifact boundaries", script_name="check_artifact_boundaries.py", ok_prefix="artifact boundary check")


def check_publish_secret_scan(gate: GateResult) -> None:
    """[10/15] 发布安全 secret scan.

    这层扫描当前 tracked/untracked 工作区文本, 防止 API key / token / private key
    重新进入当前树。它不宣称清理 Git 历史; 已暴露 credential 仍需 owner 侧轮换。
    """
    print("\n[10/15] 发布安全 secret scan")
    script = PROJECT_ROOT / "scripts" / "check_repo_secrets.py"
    if not script.exists():
        gate.block("secret scan 脚本不存在: scripts/check_repo_secrets.py")
        return
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        gate.block("secret scan 超时 (>30s)")
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


def check_memory_tree_health(gate: GateResult) -> None:
    """[11/15] 记忆树结构/currentness 检查."""
    print("\n[11/15] 记忆树结构/currentness 检查")
    script = PROJECT_ROOT / "scripts" / "check_memory_tree.py"
    if not script.exists():
        gate.block("memory tree check 脚本不存在: scripts/check_memory_tree.py")
        return
    try:
        args = []
        if (PROJECT_ROOT / "_cc_live_memory").exists() or (PROJECT_ROOT.parent / "_cc_live_memory").exists():
            args.append("--require-live-mirror")
        result = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        gate.block("memory tree check 超时 (>30s)")
        return
    except FileNotFoundError:
        gate.warn("python 不可用 — 跳过 memory tree check")
        return

    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode == 0:
        gate.ok(out.splitlines()[-1] if out else "memory tree check passed")
        return
    summary = out.splitlines()[0] if out else (err.splitlines()[0] if err else "non-zero exit")
    gate.block(f"memory tree check: {summary}")
    for line in (out.splitlines() + err.splitlines())[:16]:
        print(f"         {line}")


MYPY_STRICT_TARGETS = [
    # GPT v4 follow-up G2/G3/G4: cut lifecycle + 求解核心两个大文件都进 strict gate.
    # 历史类型错全清 (master_model 69 错, benders_loop 8 错), 由 _Any annotation
    # 一招扫掉 ortools .pyi 不全的 attr-defined + 真 type bug 单点修.
    "src/models/cut_manager.py",
    "src/models/power_placement_subproblem.py",
    "src/models/master_model.py",
    "src/search/benders_loop.py",
]


def check_doc_tree_completeness(gate: GateResult) -> None:
    """[8/15] 文档树完整收尾检查.

    这层不是语义 NLP 审查, 而是 structural closeout gate: docs surface
    manifest、subject/projection registry、无未登记 projection block、所有 subject
    field 至少有一个 concrete projection。
    """
    print("\n[8/15] 文档树完整收尾检查")
    script = PROJECT_ROOT / "scripts" / "check_doc_tree_completeness.py"
    manifest = PROJECT_ROOT / "docs" / "DOC_TREE_COMPLETENESS.json"
    if not script.exists() or not manifest.exists():
        gate.warn("文档树完整收尾脚本或 manifest 不存在 — 跳过")
        return
    try:
        args = []
        if (PROJECT_ROOT / "_cc_live_memory").exists() or (PROJECT_ROOT.parent / "_cc_live_memory").exists():
            args.append("--require-live-mirror")
        result = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=30,
        )
    except subprocess.TimeoutExpired:
        gate.block("doc tree completeness check 超时 (>30s)")
        return
    except FileNotFoundError:
        gate.warn("python 不可用 — 跳过 doc tree completeness check")
        return

    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode == 0:
        gate.ok(out.splitlines()[-1] if out else "doc tree completeness check passed")
        return
    summary = out.splitlines()[0] if out else (err.splitlines()[0] if err else "non-zero exit")
    gate.block(f"doc tree completeness check: {summary}")
    for line in (out.splitlines() + err.splitlines())[:12]:
        print(f"         {line}")


def check_mypy(gate: GateResult) -> None:
    """GPT v4 follow-up G2: mypy 严格 gate cut lifecycle 核心.

    锁 BendersCut + CutManager + PowerPlacementSubproblem 不让类型生命周期破洞
    再次发生 (lifecycle bug 根因是 schema 字段落了但 runtime resolver 没跟上).
    """
    print("\n[13/15] mypy 静态类型 (core lifecycle)")
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
    print("\n[14/15] ruff 静态检查")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "."],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT), timeout=30,
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


def check_tests(gate: GateResult, *, full: bool = False) -> None:
    label = "全量" if full else "核心门禁"
    print(f"\n[15/15] 测试门禁（{label}）")
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


def run_gate(*, full: bool = False, hook: bool = False, ci: bool = False, base_ref: str | None = None, changed_files_from: Path | None = None) -> int:
    print("=" * 60)
    print("Preflight Gate — 提交前门禁检查")
    print("=" * 60)
    global STRICT_TOOL_TIMEOUTS
    STRICT_TOOL_TIMEOUTS = ci
    configure_change_scope(ci=ci, base_ref=base_ref, changed_files_from=changed_files_from)
    mode = "full" if full else ("ci" if ci else ("hook" if hook else "staged"))
    print(f"模式: {mode}")
    print(f"变更范围: {CHANGE_SCOPE_LABEL}")

    gate = GateResult()

    check_frozen_artifacts(gate)
    check_external_artifact_manifest(gate)
    check_forbidden_paths(gate)
    check_ai_safety_contract(gate)
    check_exact_exploratory_isolation(gate)
    check_research_audit_coverage(gate)
    check_doc_subject_projections(gate)
    check_doc_tree_completeness(gate)
    check_line_ending_policy(gate)
    check_publish_secret_scan(gate)
    check_memory_tree_health(gate)
    check_artifact_boundaries(gate)
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
    parser.add_argument("--ci", action="store_true", help="按 base...HEAD diff 运行 PR/CI 变更范围检查")
    parser.add_argument("--base-ref", default=None, help="CI diff base ref/SHA，默认 origin/main")
    parser.add_argument("--changed-files-from", type=Path, default=None, help="从文件读取变更路径列表，每行一个 repo-relative path")
    args = parser.parse_args()
    sys.exit(run_gate(full=args.full, hook=args.hook, ci=args.ci, base_ref=args.base_ref, changed_files_from=args.changed_files_from))


if __name__ == "__main__":
    main()
