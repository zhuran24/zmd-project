#!/usr/bin/env python
"""Phase 3C P2 #19 — production readiness gate (168h campaign 启动前)

启动 168h campaign 之前手动跑：

    python scripts/production_readiness_gate.py

通过 = exit 0；任何 BLOCK = exit 1。

也可以从 main.py 直接调用 `gate_check()` 拿 Gate 对象做内置检查。

检查项（按严重度）:
  [B] pacman freeze 已启用 (CachyOS 滚动稳定性)
  [B] venv 存在 + ortools 可导入
  [B] preflight_gate 86 守卫测试通过
  [B] EXACT_POWER_PLACEMENT_SUBPROBLEM 未启用 (exploratory only, cut scope 未补齐)
  [B] OOM headroom: parallel × peak_worker_RSS + host < MemAvailable
  [W] kernel 是 cachyos-bore 变种 (BORE/EEVDF scheduler)
  [W] .artifacts/ 所在分区 ≥ 100 GB free
  [W] git working tree 干净
  [W] THP enabled (always|madvise) — P1 #24
  [W] jemalloc 可用于 LD_PRELOAD — P1 #24
  [W] 进程 cpu_affinity 限定 P-core (cpu0-7) — P1 #24

[B] = blocker（不通过则 BLOCK）；[W] = warning（提示但不阻塞）。

项目 Linux only — 不做 cross-OS skip，非 Linux 上 pacman check 会直接报错。
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.cp_sat_worker_config import (  # noqa: E402
    DEFAULT_MASTER_CP_SAT_WORKERS,
    resolve_exact_cp_sat_worker_profile_details,
)
from src.runtime.campaign_freeze_monitor import (  # noqa: E402
    FREEZE_MARKER,
    PACMAN_CONF,
)

ARTIFACT_MIN_FREE_GIB = 100
DISK_PATH_TO_CHECK = PROJECT_ROOT / ".artifacts"


class Gate:
    def __init__(self) -> None:
        self.checks: List[Tuple[str, str, str]] = []  # (level, label, msg)
        self.has_block = False

    def ok(self, label: str, msg: str = "") -> None:
        self.checks.append(("OK", label, msg))

    def warn(self, label: str, msg: str) -> None:
        self.checks.append(("WARN", label, msg))

    def block(self, label: str, msg: str) -> None:
        self.checks.append(("BLOCK", label, msg))
        self.has_block = True

    def render(self) -> str:
        lines = ["=" * 60, "Production Readiness Gate (168h campaign 启动前检查)", "=" * 60, ""]
        block_count = 0
        warn_count = 0
        ok_count = 0
        for level, label, msg in self.checks:
            tag = {"OK": "OK   ", "WARN": "WARN ", "BLOCK": "BLOCK"}[level]
            line = f"  [{tag}] {label}"
            if msg:
                line += f": {msg}"
            lines.append(line)
            if level == "BLOCK":
                block_count += 1
            elif level == "WARN":
                warn_count += 1
            elif level == "OK":
                ok_count += 1
        lines.append("")
        lines.append("=" * 60)
        if self.has_block:
            lines.append(f"结果: BLOCKED ({block_count} 阻塞 / {warn_count} 警告 / {ok_count} 通过)")
            lines.append("有硬阻塞项，168h campaign 不应启动。修完后重跑此脚本。")
        else:
            lines.append(f"结果: READY ({warn_count} 警告 / {ok_count} 通过)")
            if warn_count:
                lines.append("有警告项 — 不阻塞 campaign 启动，但建议先看一下。")
        lines.append("=" * 60)
        return "\n".join(lines)


def check_pacman_freeze(gate: Gate) -> None:
    if not PACMAN_CONF.exists():
        gate.block("pacman freeze", "/etc/pacman.conf 不存在 — 当前不是 Arch/CachyOS 系统？")
        return
    try:
        content = PACMAN_CONF.read_text(encoding="utf-8")
    except PermissionError:
        gate.warn("pacman freeze", "/etc/pacman.conf 不可读 — 权限问题")
        return
    if FREEZE_MARKER in content:
        gate.ok("pacman freeze", "campaign-freeze block 已加入 /etc/pacman.conf")
    else:
        gate.block(
            "pacman freeze",
            "未启用！跑 `bash scripts/pacman_campaign_freeze.sh --enable` 锁定关键包",
        )


def _venv_python() -> Path:
    return PROJECT_ROOT / ".venv" / "bin" / "python"


def check_venv_and_ortools(gate: Gate) -> None:
    venv_python = _venv_python()
    if not venv_python.exists():
        gate.block("venv", f"{venv_python} 不存在 — 跑 cachyos_setup.sh --apply")
        return
    try:
        result = subprocess.run(
            [
                str(venv_python),
                "-c",
                "from ortools.sat.python import cp_model; print(cp_model.CpSolver().parameters.num_search_workers)",
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        gate.block("ortools import", f"venv python 调用失败: {exc}")
        return
    if result.returncode != 0:
        gate.block(
            "ortools import",
            f"venv 里 import ortools 失败 (exit {result.returncode}): {result.stderr.strip()[:200]}",
        )
        return
    gate.ok("ortools import", "venv ortools.sat.python 可导入")


def check_preflight_gate(gate: Gate) -> None:
    venv_python = _venv_python()
    if not venv_python.exists():
        gate.warn("preflight gate", "venv 缺失 — preflight gate 已被前面 venv check 阻塞")
        return
    preflight_path = PROJECT_ROOT / "scripts" / "preflight_gate.py"
    try:
        result = subprocess.run(
            [str(venv_python), str(preflight_path)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        gate.block("preflight gate", "core 86 守卫测试超时 (>120s)")
        return
    except Exception as exc:
        gate.block("preflight gate", f"调用失败: {exc}")
        return
    if result.returncode != 0:
        gate.block("preflight gate", f"86 守卫测试失败 (exit {result.returncode})")
        return
    gate.ok("preflight gate", "86 核心守卫测试通过")


def check_kernel(gate: Gate) -> None:
    try:
        kernel = subprocess.check_output(["uname", "-r"], text=True).strip()
    except Exception as exc:
        gate.warn("kernel", f"uname 调用失败: {exc}")
        return
    if "cachyos" in kernel.lower() or "bore" in kernel.lower():
        gate.ok("kernel", f"BORE 内核 ({kernel})")
    else:
        gate.warn(
            "kernel",
            f"当前 {kernel} 不含 cachyos/bore 标识 — 可能没用 BORE/EEVDF scheduler，损失 +5-10% 性能",
        )


def check_disk_space(gate: Gate) -> None:
    DISK_PATH_TO_CHECK.mkdir(parents=True, exist_ok=True)
    try:
        usage = shutil.disk_usage(DISK_PATH_TO_CHECK)
    except Exception as exc:
        gate.warn("disk space", f"无法读取 {DISK_PATH_TO_CHECK} 磁盘信息: {exc}")
        return
    free_gib = usage.free / (1024 ** 3)
    if free_gib < ARTIFACT_MIN_FREE_GIB:
        gate.warn(
            "disk space",
            f"{DISK_PATH_TO_CHECK} 所在分区 free={free_gib:.1f} GiB < {ARTIFACT_MIN_FREE_GIB} GiB 阈值",
        )
    else:
        gate.ok("disk space", f"{DISK_PATH_TO_CHECK} free={free_gib:.1f} GiB")


def check_git_clean(gate: Gate) -> None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        gate.warn("git status", f"git 调用失败: {exc}")
        return
    if result.returncode != 0:
        gate.warn("git status", f"git status exit {result.returncode}")
        return
    pending = [line for line in result.stdout.splitlines() if line.strip()]
    if not pending:
        gate.ok("git status", "working tree clean")
        return
    # GPT v4 Finding 5 fix: untracked files 在 code 区 (src/ scripts/ main.py) 必须
    # BLOCK. v3 → v4 之间发生过 5 个 scripts/*.py 被打进 release tar 但 git 没跟踪,
    # preflight 无法看见. 区分 code 区 vs data 区 (data/ .artifacts/ .pytest_tmp/
    # 等大文件/临时输出 区按 WARN 处理).
    code_zones = (
        "src/", "scripts/", "rules/", "docs/", "specs/",
        "main.py", "PROJECT_LOCK.md", "CLAUDE.md", "FILE_STATUS.md",
        "BORROWED_COMPONENTS.md", "requirements.txt", "requirements.lock.txt",
        "pytest.ini",
    )
    untracked_code: list[str] = []
    modified_or_other: list[str] = []
    for line in pending:
        # porcelain v1: "XY path". untracked = "?? path"
        status = line[:2]
        path = line[3:] if len(line) > 3 else line
        is_untracked = status.strip() == "??"
        if is_untracked and any(path.startswith(z) for z in code_zones):
            untracked_code.append(path)
        else:
            modified_or_other.append(line)
    if untracked_code:
        gate.block(
            "git status",
            f"code 区有 {len(untracked_code)} 个 untracked 文件 (会被打进 release 但 git 看不见): "
            f"{', '.join(untracked_code[:5])}{'...' if len(untracked_code) > 5 else ''}. "
            "commit / .gitignore / 删除, 三选一.",
        )
    if modified_or_other:
        gate.warn(
            "git status",
            f"working tree 有 {len(modified_or_other)} 个 modified/untracked 非 code 区文件 — 启动 campaign 前确认是否需要 commit",
        )
    elif not untracked_code:
        gate.ok("git status", "working tree clean")


THP_ENABLED_PATH = Path("/sys/kernel/mm/transparent_hugepage/enabled")
JEMALLOC_PATH = Path("/usr/lib/libjemalloc.so.2")


def check_thp(gate: Gate) -> None:
    """P1 #24: THP madvise/always reduces TLB miss on large-heap workloads."""
    if not THP_ENABLED_PATH.exists():
        gate.warn("THP", "/sys/kernel/mm/transparent_hugepage/enabled 不存在 — 非 Linux？")
        return
    try:
        content = THP_ENABLED_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        gate.warn("THP", f"读取失败: {exc}")
        return
    # Format: "[always] madvise never" — bracketed item is current.
    if "[always]" in content or "[madvise]" in content:
        gate.ok("THP", f"enabled = {content}")
    else:
        gate.warn(
            "THP",
            f"current = {content} — long-run workload 损失 TLB 红利，"
            f"建议 `echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled`",
        )


def check_jemalloc(gate: Gate) -> None:
    """P1 #24: jemalloc LD_PRELOAD reduces ptmalloc multi-thread contention."""
    if not JEMALLOC_PATH.exists():
        gate.warn(
            "jemalloc",
            f"{JEMALLOC_PATH} 不存在 — 跑 `sudo pacman -S jemalloc` 安装",
        )
        return
    ld_preload = os.environ.get("LD_PRELOAD", "")
    if "jemalloc" in ld_preload or "tcmalloc" in ld_preload:
        gate.ok("jemalloc", f"LD_PRELOAD 已含 allocator: {ld_preload}")
    else:
        gate.warn(
            "jemalloc",
            f"{JEMALLOC_PATH} 已装但 LD_PRELOAD 未设 — "
            f"用 `bash scripts/run_campaign_linux.sh ...` 启动以自动 preload",
        )


def check_power_subproblem_disabled(gate: Gate) -> None:
    # EXACT_POWER_PLACEMENT_SUBPROBLEM=1 当前是 exploratory: ghost-conditioned
    # cut 缺 condition_lits + pole alternatives 未穷尽, 进 certified path 会
    # 误切合法布局. 修完 cut scope 之前不能进 production.
    val = os.environ.get("EXACT_POWER_PLACEMENT_SUBPROBLEM", "").strip()
    if val in {"", "0", "false", "False"}:
        gate.ok("power subproblem", "EXACT_POWER_PLACEMENT_SUBPROBLEM 未启用")
    else:
        gate.block(
            "power subproblem",
            f"EXACT_POWER_PLACEMENT_SUBPROBLEM={val} — 当前 exploratory only, "
            f"cut scope 未补齐 (ghost-conditioned + pole alternatives), 不可进 certified path",
        )


def check_oom_headroom(gate: Gate) -> None:
    """Estimate whether parallel workers fit in RAM with safety buffer.

    Batch0 C1 evidence shows a mild w6 run, two w12 deaths, and a w24
    hard-cap breach. Peak RSS is therefore tiered by the resolved master
    CP-SAT worker count. Host overhead remains 8 GiB.

    Formula:
        needed   = parallel × WORKER_PEAK_RSS_GIB + HOST_OVERHEAD_GIB
        available= MemAvailable (excludes page cache 因 reclaimable)

    BLOCK if needed > available  → 168h 撞 global OOM
    WARN  if needed > available × 0.9  → tight margin
    OK    otherwise.

    parallel 从 EXACT_PARALLEL_PROCESSES env (跟 main.py / wrapper 一致),
    缺省 4 且下限为 1。Master worker 解析复用运行时的
    stage-specific → global → default 优先级。
    """
    # M5 attribution verdict (2026-07-10, m5_c1_memory_attribution_20260710.md):
    # the C1 master has an inherent ~60G-class allocation spike at solution
    # time (steady state 11-17G; spike RSS >42G plus ~18G swap overflow). The
    # spike is handled by the wrapper's cgroup terms (MemoryMax=42G +
    # MemorySwapMax=20G, zram absorbs the overflow — measured OPTIMAL@512.9s
    # with no wall regression), NOT by this gate. The w6 tier therefore models
    # the STEADY-STATE RSS (17G + margin = 20G): the gate guards "steady state
    # × parallel + host fits in physical RAM"; spike survival is the cgroup's
    # job. The interim 44G value (42G-cap kill evidence, batch 1F) was replaced
    # after the verdict showed it conflated the capped death value with steady
    # demand. Large anchors (70x19+) exceed even the spike terms on this host.
    WORKER_PEAK_RSS_GIB_W6 = 20.0
    WORKER_PEAK_RSS_GIB_W12 = 47.0
    WORKER_PEAK_RSS_GIB_GT12 = 47.0
    HOST_OVERHEAD_GIB = 8.0

    try:
        master_details = resolve_exact_cp_sat_worker_profile_details()["master"]
    except ValueError:
        master_workers = DEFAULT_MASTER_CP_SAT_WORKERS
        worker_peak_default = WORKER_PEAK_RSS_GIB_W12
        worker_tier_note = (
            "CP-SAT worker env invalid; "
            f"current default workers={master_workers}; conservative 47GB tier"
        )
    else:
        master_workers = int(master_details["workers"])
        master_worker_source = str(master_details["source"])
        if master_worker_source == "default":
            worker_peak_default = WORKER_PEAK_RSS_GIB_W12
            worker_tier_note = (
                "EXACT_MASTER_CP_SAT_WORKERS and EXACT_CP_SAT_WORKERS unset; "
                f"current default workers={master_workers}; conservative 47GB tier"
            )
        elif master_workers <= 6:
            worker_peak_default = WORKER_PEAK_RSS_GIB_W6
            worker_tier_note = (
                f"master_workers={master_workers} (w<=6 tier; source={master_worker_source})"
            )
        elif master_workers <= 12:
            worker_peak_default = WORKER_PEAK_RSS_GIB_W12
            worker_tier_note = (
                f"master_workers={master_workers} (6<w<=12 tier; source={master_worker_source})"
            )
        else:
            worker_peak_default = WORKER_PEAK_RSS_GIB_GT12
            worker_tier_note = (
                f"master_workers={master_workers} (w>12 tier; source={master_worker_source})"
            )

    # Gate-only estimate override, not a solver/cgroup limit: use a one-command
    # standalone gate prefix or unset it before launching a campaign so
    # calibration state cannot leak into the campaign environment.
    peak_override = os.environ.get("EXACT_GATE_WORKER_PEAK_RSS_GIB", "").strip()
    try:
        WORKER_PEAK_RSS_GIB = float(peak_override) if peak_override else worker_peak_default
        if not math.isfinite(WORKER_PEAK_RSS_GIB) or WORKER_PEAK_RSS_GIB <= 0:
            WORKER_PEAK_RSS_GIB = worker_peak_default
    except ValueError:
        WORKER_PEAK_RSS_GIB = worker_peak_default
    parallel_str = os.environ.get("EXACT_PARALLEL_PROCESSES", "4")
    try:
        parallel = int(parallel_str)
    except ValueError:
        parallel = 4
    parallel = max(1, parallel)

    try:
        meminfo_text = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError as exc:
        gate.warn("OOM headroom", f"/proc/meminfo 不可读 ({exc}) — 跳过 OOM 估算")
        return

    available_kib = 0
    for line in meminfo_text.splitlines():
        if line.startswith("MemAvailable:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    available_kib = int(parts[1])
                except ValueError:
                    pass
            break
    if available_kib == 0:
        gate.warn("OOM headroom", "MemAvailable 解析失败 — 跳过")
        return

    available_gib = available_kib / 1024.0 / 1024.0
    needed_gib = parallel * WORKER_PEAK_RSS_GIB + HOST_OVERHEAD_GIB
    msg_base = (
        f"parallel={parallel} × {WORKER_PEAK_RSS_GIB:.0f}GB/worker + "
        f"{HOST_OVERHEAD_GIB:.0f}GB host = 需 {needed_gib:.1f}GB; "
        f"available={available_gib:.1f}GB; {worker_tier_note}"
    )
    if needed_gib > available_gib:
        gate.block(
            "OOM headroom",
            f"{msg_base} — global OOM 风险：C1 batch0 已见 w12 两连死、w24 硬帽击穿。"
            f"降 parallel/master workers 或释 host RAM",
        )
    elif needed_gib > available_gib * 0.9:
        gate.warn(
            "OOM headroom",
            f"{msg_base} — tight margin (>90%), RSS spike 可能 OOM",
        )
    else:
        gate.ok("OOM headroom", f"{msg_base}")


def check_pcore_pinning(gate: Gate) -> None:
    """P1 #24: pinning to high-freq P-cores avoids E-core preemption.

    On i9-13900KS HT-off, P-cores are cpu0-7 (5600 MHz) and E-cores are
    cpu8-23 (4500 MHz). We detect P-cores by max cpufreq matching and
    check that the current process affinity is a subset.
    """
    try:
        affinity = os.sched_getaffinity(0)
    except (AttributeError, OSError):
        gate.warn("P-core pinning", "os.sched_getaffinity 不可用 — 跳过")
        return
    p_cores = set()
    cpu_root = Path("/sys/devices/system/cpu")
    if not cpu_root.exists():
        gate.warn("P-core pinning", "/sys/devices/system/cpu 不存在 — 跳过")
        return
    cpu_freq: dict[int, int] = {}
    for cpu_dir in cpu_root.glob("cpu[0-9]*"):
        try:
            cpu_id = int(cpu_dir.name[3:])
        except ValueError:
            continue
        freq_file = cpu_dir / "cpufreq" / "cpuinfo_max_freq"
        if freq_file.is_file():
            try:
                cpu_freq[cpu_id] = int(freq_file.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
    if not cpu_freq:
        gate.warn("P-core pinning", "cpufreq 信息读不到 — 跳过")
        return
    max_freq = max(cpu_freq.values())
    p_cores = {cpu for cpu, freq in cpu_freq.items() if freq == max_freq}
    if affinity == set(cpu_freq.keys()):
        gate.warn(
            "P-core pinning",
            f"affinity = 全部 {len(affinity)} cores — 用 "
            f"`bash scripts/run_campaign_linux.sh ...` 启动以 taskset 钉到 P-core ({sorted(p_cores)})",
        )
    elif affinity.issubset(p_cores):
        gate.ok(
            "P-core pinning",
            f"affinity = {sorted(affinity)} ⊆ P-cores {sorted(p_cores)} ({max_freq} kHz)",
        )
    else:
        non_p = sorted(affinity - p_cores)
        gate.warn(
            "P-core pinning",
            f"affinity 含 non-P-core: {non_p} — 损失 +2-5% from 5.6→4.5 GHz 抢占",
        )


def gate_check() -> Gate:
    """Run all readiness checks and return the populated Gate.

    Importable from main.py for in-process startup gating without
    spawning a subprocess.
    """
    gate = Gate()
    check_pacman_freeze(gate)
    check_venv_and_ortools(gate)
    check_preflight_gate(gate)
    check_power_subproblem_disabled(gate)
    check_kernel(gate)
    check_disk_space(gate)
    check_git_clean(gate)
    check_thp(gate)
    check_jemalloc(gate)
    check_oom_headroom(gate)
    check_pcore_pinning(gate)
    return gate


def main() -> int:
    gate = gate_check()
    print(gate.render())
    return 1 if gate.has_block else 0


if __name__ == "__main__":
    sys.exit(main())
