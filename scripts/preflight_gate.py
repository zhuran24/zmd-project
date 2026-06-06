"""Preflight gate — repo-native project guardrails.

Usage:
    python scripts/preflight_gate.py
    python scripts/preflight_gate.py --hook
    python scripts/preflight_gate.py --full
    python scripts/preflight_gate.py --ci --base-ref origin/main

The default mode checks staged changes for diff-scoped rules. CI mode checks the
merge/base diff, so GitHub Actions and PR reviews do not depend on local staged
state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_ARTIFACTS_MANIFEST = PROJECT_ROOT / "data" / "external_artifacts.json"

FROZEN_ARTIFACTS = {
    "rules/canonical_rules.json": "8AC667A1BCE67FF9084701D18892F370E19D68CC9B5ACE44BD63C68B20D3D6EA",
    "data/preprocessed/mandatory_exact_instances.json": "545B98C2B4F96643F1346B423EDF2DC8E300A0C815B6CF821776CEED03CD4CD6",
    "data/preprocessed/generic_io_requirements.json": "AD5125B50E607A7F3F3BF0B54FEA64F93EDF87CEDB62E8D24F5590E1C895C44E",
}

FALLBACK_EXTERNAL_ARTIFACTS = {
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
AI_FORBIDDEN_PATH_REFS = ["data/checkpoints", "data/solutions", "data/blueprints"]

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

CORE_TEST_FILES = [
    "src/tests/test_exact_contract.py",
    "src/tests/test_parallel_scheduler.py",
    "src/tests/test_power_placement_subproblem.py",
    "src/tests/test_coordinate_benders_cut_presence_nogood.py",
    "src/tests/test_benders_cut_condition_lits.py",
    "src/tests/test_benders_cut_replay_condition_lifecycle.py",
    "src/tests/test_power_witness_cut_dilution.py",
]

RESEARCH_TRACKED_FILES = {
    "docs/phase3c_optimization_roadmap_v1.md",
    "docs/research/INDEX.md",
}
RESEARCH_REF_PATTERN = re.compile(r"\bR\d+\s+`([0-9a-f]{16,})`")
AUDIT_REF_PATTERN = re.compile(r"\baudit\b[^`\n]{0,15}`([0-9a-f]{16,})`", re.IGNORECASE)

MYPY_STRICT_TARGETS = [
    "src/models/cut_manager.py",
    "src/models/power_placement_subproblem.py",
    "src/models/master_model.py",
    "src/search/benders_loop.py",
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
        return 1 if self.blockers else 0

    def summary(self) -> str:
        parts = [f"{len(self.passed)} passed"]
        if self.warnings:
            parts.append(f"{len(self.warnings)} warnings")
        if self.blockers:
            parts.append(f"{len(self.blockers)} BLOCKED")
        return ", ".join(parts)


class ChangeScope:
    def __init__(self) -> None:
        self.mode = "staged"
        self.base_ref: str | None = None
        self.files: list[str] | None = None
        self.setup_warning: str | None = None


CHANGE_SCOPE = ChangeScope()


def git_output(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=PROJECT_ROOT, capture_output=True, text=True)


def clean_file_list(stdout: str) -> list[str]:
    return [line.strip().replace("\\", "/") for line in stdout.splitlines() if line.strip()]


def git_ref_exists(ref: str) -> bool:
    return git_output(["git", "rev-parse", "--verify", "--quiet", ref]).returncode == 0


def resolve_base_ref(base_ref: str | None) -> str | None:
    if not base_ref:
        return None
    if git_ref_exists(base_ref):
        return base_ref
    if base_ref.startswith("origin/"):
        local_branch = base_ref.split("/", 1)[1]
        if git_ref_exists(local_branch):
            return local_branch
    return None


def configure_change_scope(*, ci: bool, base_ref: str | None, changed_files_from: str | None) -> None:
    CHANGE_SCOPE.mode = "ci" if ci else "staged"
    CHANGE_SCOPE.base_ref = None
    CHANGE_SCOPE.files = None
    CHANGE_SCOPE.setup_warning = None

    if changed_files_from:
        path = Path(changed_files_from)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        CHANGE_SCOPE.mode = "changed-files"
        if not path.exists():
            CHANGE_SCOPE.files = []
            CHANGE_SCOPE.setup_warning = f"changed-files file 不存在: {path}"
            return
        CHANGE_SCOPE.files = clean_file_list(path.read_text(encoding="utf-8"))
        CHANGE_SCOPE.base_ref = resolve_base_ref(base_ref)
        return

    if not ci:
        return

    resolved = resolve_base_ref(base_ref) or resolve_base_ref("origin/main") or resolve_base_ref("main")
    if not resolved:
        CHANGE_SCOPE.files = []
        CHANGE_SCOPE.setup_warning = (
            "CI diff base 不存在; changed-file scoped checks will see no changed files. "
            "Use --base-ref or --changed-files-from in CI."
        )
        return
    CHANGE_SCOPE.base_ref = resolved
    result = git_output(["git", "diff", "--name-only", f"{resolved}...HEAD"])
    if result.returncode != 0:
        result = git_output(["git", "diff", "--name-only", resolved, "HEAD"])
    if result.returncode != 0:
        CHANGE_SCOPE.files = []
        CHANGE_SCOPE.setup_warning = f"无法计算 CI diff against {resolved}: {(result.stderr or result.stdout).strip()}"
    else:
        CHANGE_SCOPE.files = clean_file_list(result.stdout)


def changed_files() -> list[str]:
    if CHANGE_SCOPE.files is not None:
        return list(CHANGE_SCOPE.files)
    result = git_output(["git", "diff", "--cached", "--name-only"])
    if result.returncode != 0:
        return []
    return clean_file_list(result.stdout)


def changed_diff(path: str) -> str:
    if CHANGE_SCOPE.base_ref:
        result = git_output(["git", "diff", f"{CHANGE_SCOPE.base_ref}...HEAD", "--", path])
        if result.returncode != 0:
            result = git_output(["git", "diff", CHANGE_SCOPE.base_ref, "HEAD", "--", path])
    elif CHANGE_SCOPE.mode == "staged":
        result = git_output(["git", "diff", "--cached", "--", path])
    else:
        result = git_output(["git", "diff", "HEAD", "--", path])
    return result.stdout if result.returncode == 0 else ""


def change_scope_label() -> str:
    if CHANGE_SCOPE.mode == "ci" and CHANGE_SCOPE.base_ref:
        return f"CI diff against {CHANGE_SCOPE.base_ref}"
    if CHANGE_SCOPE.mode == "changed-files":
        return "provided changed-files list"
    return "staged files"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_external_frozen_artifacts() -> dict[str, dict[str, object]]:
    if not EXTERNAL_ARTIFACTS_MANIFEST.exists():
        return FALLBACK_EXTERNAL_ARTIFACTS
    payload = json.loads(EXTERNAL_ARTIFACTS_MANIFEST.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("data/external_artifacts.json schema_version must be 1")
    raw = payload.get("artifacts", {})
    if not isinstance(raw, dict):
        raise ValueError("data/external_artifacts.json artifacts must be an object")
    artifacts: dict[str, dict[str, object]] = {}
    for name, info in sorted(raw.items()):
        if not isinstance(info, dict):
            raise ValueError(f"external artifact {name!r} must be an object")
        artifacts[str(info["path"])] = {
            "sha256": str(info["sha256"]).upper(),
            "size_bytes": int(info["size_bytes"]),
            "policy_doc": str(info.get("policy_doc", "START_HERE.md")),
        }
    return artifacts


def check_frozen_artifacts(gate: GateResult) -> None:
    print("\n[1/12] 冻结/外部制品 hash 校验")
    for rel_path, expected_hash in FROZEN_ARTIFACTS.items():
        full_path = PROJECT_ROOT / rel_path
        if not full_path.exists():
            gate.block(f"checked-in 冻结制品不存在: {rel_path}")
            continue
        actual_hash = sha256_file(full_path)
        if actual_hash == expected_hash:
            gate.ok(rel_path)
        else:
            gate.block(f"{rel_path} hash 不匹配!\n         期望: {expected_hash}\n         实际: {actual_hash}")

    try:
        external_artifacts = load_external_frozen_artifacts()
    except (ValueError, json.JSONDecodeError) as exc:
        gate.block(f"external artifact manifest 无效: {exc}")
        external_artifacts = {}
    for rel_path, info in external_artifacts.items():
        full_path = PROJECT_ROOT / rel_path
        expected_hash = str(info["sha256"]).upper()
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
                f"         期望 hash: {expected_hash}\n         实际 hash: {actual_hash}\n"
                f"         期望 size: {expected_size}\n         实际 size: {actual_size}"
            )


def check_forbidden_paths(gate: GateResult) -> None:
    print("\n[2/12] 禁止路径写入检查")
    files = changed_files()
    if not files:
        gate.ok(f"{change_scope_label()} 无文件（或不在 git 仓库中）")
        return
    violations = []
    for path in files:
        for forbidden in FORBIDDEN_STAGED_PATHS:
            if path.startswith(forbidden) or path == forbidden.rstrip("/"):
                violations.append((path, forbidden))
    if violations:
        for path, rule in violations:
            gate.block(f"禁止提交: {path} (规则: {rule})")
    else:
        gate.ok(f"已检查 {len(files)} 个 {change_scope_label()}，无禁止路径违规")


def check_ai_safety_contract(gate: GateResult) -> None:
    print("\n[3/12] AI 安全合同检查")
    ai_dir = PROJECT_ROOT / AI_MODULE_ROOT
    if not ai_dir.exists():
        gate.ok("ai_accel 目录不存在，跳过")
        return
    violations = []
    py_files = list(ai_dir.rglob("*.py"))
    for py_file in py_files:
        rel = py_file.relative_to(PROJECT_ROOT).as_posix()
        try:
            content = py_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for pattern in AI_FORBIDDEN_PATH_REFS:
                if pattern in line:
                    violations.append((rel, lineno, pattern))
    if violations:
        for rel, lineno, pattern in violations:
            gate.block(f"AI 模块引用了禁止路径: {rel}:{lineno} 包含 '{pattern}'")
    else:
        gate.ok(f"已扫描 {len(py_files)} 个 AI 模块文件，无禁止引用")


def check_exact_exploratory_isolation(gate: GateResult) -> None:
    print("\n[4/12] 精确/探索边界隔离检查")
    files = changed_files()
    if not files:
        gate.ok(f"{change_scope_label()} 无文件")
        return
    exact_files = [path for path in files if path in EXACT_MODE_FILES]
    if not exact_files:
        gate.ok(f"{change_scope_label()} 未修改精确求解核心文件")
        return
    violations = []
    for path in exact_files:
        for line in changed_diff(path).splitlines():
            if not line.startswith("+") or line.startswith("+++"):
                continue
            added = line[1:]
            for pattern in EXPLORATORY_LEAK_PATTERNS:
                if pattern.lower() in added.lower():
                    violations.append((path, pattern, added.strip()))
    if violations:
        for path, pattern, added in violations:
            gate.block(f"探索性约束泄漏到精确模式: {path}\n         模式: '{pattern}'\n         内容: {added}")
    else:
        gate.ok(f"已检查 {len(exact_files)} 个核心文件的 diff，无探索性泄漏")
    gate.warn(f"本次提交修改了精确求解核心文件: {', '.join(exact_files)}\n         建议做一次 AI 语义审查确认求解语义未变")


def check_research_audit_coverage(gate: GateResult) -> None:
    print("\n[5/12] 调研产物 audit 覆盖检查")
    touched = [path for path in changed_files() if path in RESEARCH_TRACKED_FILES]
    if not touched:
        gate.ok("本次提交未修改路线图 / INDEX")
        return
    research_refs: set[str] = set()
    audit_refs: set[str] = set()
    for path in touched:
        added = "\n".join(
            line[1:] for line in changed_diff(path).splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        research_refs.update(RESEARCH_REF_PATTERN.findall(added))
        audit_refs.update(AUDIT_REF_PATTERN.findall(added))
    if not research_refs:
        gate.ok(f"路线图 / INDEX 改动 {len(touched)} 个文件，无新增 R-N 调研引用")
        return
    missing = research_refs - audit_refs
    if missing:
        gate.warn(
            f"路线图 / INDEX 新增 {len(research_refs)} 个 R-N 调研引用，"
            f"{len(missing)} 个未看到配套 audit (agent IDs: {', '.join(sorted(missing)[:3])})。"
        )
    else:
        gate.ok(f"路线图 / INDEX 新增 {len(research_refs)} 个 R-N 调研引用，全部配套 audit")


def run_script_gate(gate: GateResult, *, index: str, label: str, script: str, args: list[str] | None = None, timeout: int = 30, missing_block: bool = False) -> None:
    print(f"\n[{index}] {label}")
    path = PROJECT_ROOT / script
    if not path.exists():
        msg = f"脚本不存在: {script}"
        gate.block(msg) if missing_block else gate.warn(msg)
        return
    cmd = [sys.executable, str(path), *(args or [])]
    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        gate.block(f"{label} 超时 (>{timeout}s)")
        return
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode == 0:
        gate.ok(out.splitlines()[-1] if out else f"{label} passed")
        return
    summary = out.splitlines()[0] if out else (err.splitlines()[0] if err else "non-zero exit")
    gate.block(f"{label}: {summary}")
    for line in (out.splitlines() + err.splitlines())[:16]:
        print(f"         {line}")


def check_doc_subject_projections(gate: GateResult) -> None:
    run_script_gate(gate, index="6/12", label="项目知识主体/投影同步检查", script="scripts/sync_doc_subjects.py", args=["--check"])


def check_doc_tree_completeness(gate: GateResult) -> None:
    run_script_gate(gate, index="7/12", label="文档树完整收尾检查", script="scripts/check_doc_tree_completeness.py")


def check_publish_secret_scan(gate: GateResult) -> None:
    run_script_gate(gate, index="8/12", label="发布安全 secret scan", script="scripts/check_repo_secrets.py", missing_block=True)


def check_memory_tree_health(gate: GateResult) -> None:
    args = ["--require-live-mirror"] if (PROJECT_ROOT / "_cc_live_memory").exists() else []
    run_script_gate(gate, index="9/12", label="记忆树结构/currentness 检查", script="scripts/check_memory_tree.py", args=args, missing_block=True)


def check_mypy(gate: GateResult) -> None:
    print("\n[10/12] mypy 静态类型 (core lifecycle)")
    existing = [target for target in MYPY_STRICT_TARGETS if (PROJECT_ROOT / target).exists()]
    if not existing:
        gate.warn("mypy gate 目标文件不存在 — 跳过")
        return
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--explicit-package-bases", "--ignore-missing-imports", "--follow-imports=silent", *existing],
        cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60,
        env={**os.environ, "MYPYPATH": str(PROJECT_ROOT)},
    )
    out = (result.stdout or "").strip()
    if result.returncode == 0:
        gate.ok(f"mypy: {out.splitlines()[-1] if out else 'no issues found'}")
        return
    summary = next((line.strip() for line in reversed(out.splitlines()) if line.startswith("Found ")), "non-zero exit")
    gate.block(f"mypy core lifecycle: {summary}")
    for line in out.splitlines()[:12]:
        print(f"         {line}")


def check_ruff(gate: GateResult) -> None:
    print("\n[11/12] ruff 静态检查")
    result = subprocess.run([sys.executable, "-m", "ruff", "check", "."], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30)
    if result.returncode == 0:
        gate.ok(f"ruff: {(result.stdout or 'All checks passed!').splitlines()[-1].strip()}")
        return
    out = result.stdout or result.stderr or ""
    summary = next((line.strip() for line in reversed(out.splitlines()) if line.startswith("Found ")), "ruff 报告非 0 退出")
    gate.block(f"ruff: {summary}")
    for line in out.splitlines()[:8]:
        print(f"         {line}")


def check_tests(gate: GateResult, *, full: bool = False) -> None:
    label = "全量" if full else "核心门禁"
    print(f"\n[12/12] 测试门禁（{label}）")
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short", "--no-header"]
    if full:
        cmd.append("src/tests/")
        timeout = 600
    else:
        existing = [path for path in CORE_TEST_FILES if (PROJECT_ROOT / path).exists()]
        if not existing:
            gate.warn("核心测试文件不存在，跳过")
            return
        cmd.extend(existing)
        timeout = 120
    env = os.environ.copy()
    for key in ("EXACT_OUTER_SKIP_UNKNOWN", "EXACT_BINDING_DUMP_STATE", "EXACT_MASTER_HINT_PERSISTENCE", "EXACT_BINDING_USE_OVERLOAD_SEPARATION"):
        env.pop(key, None)
    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        gate.block(f"pytest 超时 (>{timeout}s)")
        return
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    summary = lines[-1] if lines else ""
    if result.returncode == 0:
        gate.ok(f"pytest ({label}): {summary}")
    else:
        gate.block(f"pytest 失败 (exit={result.returncode}): {summary}")
        for line in lines[-10:]:
            print(f"         {line}")


def run_gate(*, full: bool = False, hook: bool = False, ci: bool = False, base_ref: str | None = None, changed_files_from: str | None = None) -> int:
    print("=" * 60)
    print("Preflight Gate — 提交前门禁检查")
    print("=" * 60)
    configure_change_scope(ci=ci, base_ref=base_ref, changed_files_from=changed_files_from)
    mode = "full" if full else ("hook" if hook else ("ci" if ci else "staged"))
    print(f"模式: {mode}")
    print(f"变更范围: {change_scope_label()}")
    gate = GateResult()
    if CHANGE_SCOPE.setup_warning:
        gate.warn(CHANGE_SCOPE.setup_warning)

    check_frozen_artifacts(gate)
    check_forbidden_paths(gate)
    check_ai_safety_contract(gate)
    check_exact_exploratory_isolation(gate)
    check_research_audit_coverage(gate)
    check_doc_subject_projections(gate)
    check_doc_tree_completeness(gate)
    check_publish_secret_scan(gate)
    check_memory_tree_health(gate)
    check_mypy(gate)
    check_ruff(gate)
    check_tests(gate, full=full)

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
    parser.add_argument("--ci", action="store_true", help="CI / PR 模式：用 base-ref...HEAD 计算变更范围")
    parser.add_argument("--base-ref", default="origin/main", help="CI diff base ref，默认 origin/main")
    parser.add_argument("--changed-files-from", default=None, help="从文件读取变更路径列表（一行一个），可与 --base-ref 配合取 diff hunk")
    args = parser.parse_args()
    raise SystemExit(run_gate(full=args.full, hook=args.hook, ci=args.ci, base_ref=args.base_ref, changed_files_from=args.changed_files_from))


if __name__ == "__main__":
    main()
