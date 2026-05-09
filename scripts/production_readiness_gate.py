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

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime.campaign_freeze_monitor import (  # noqa: E402
    FREEZE_MARKER,
    PACMAN_CONF,
    is_pacman_freeze_enabled,
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
    if pending:
        gate.warn(
            "git status",
            f"working tree 有 {len(pending)} 个 modified/untracked 文件 — 启动 campaign 前确认是否需要 commit",
        )
    else:
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
    check_kernel(gate)
    check_disk_space(gate)
    check_git_clean(gate)
    check_thp(gate)
    check_jemalloc(gate)
    check_pcore_pinning(gate)
    return gate


def main() -> int:
    gate = gate_check()
    print(gate.render())
    return 1 if gate.has_block else 0


if __name__ == "__main__":
    sys.exit(main())
