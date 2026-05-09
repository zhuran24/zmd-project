#!/usr/bin/env python
"""Phase 3C P2 #19 — production readiness gate (168h campaign 启动前)

启动 168h campaign 之前手动跑：

    python scripts/production_readiness_gate.py

通过 = exit 0；任何 BLOCK = exit 1。

检查项（按严重度）:
  [B] pacman freeze 已启用 (CachyOS 滚动稳定性)
  [B] venv 存在 + ortools 可导入
  [B] preflight_gate 86 守卫测试通过
  [W] kernel 是 cachyos-bore 变种 (BORE/EEVDF scheduler)
  [W] .artifacts/ 所在分区 ≥ 100 GB free
  [W] git working tree 干净

[B] = blocker（不通过则 BLOCK）；[W] = warning（提示但不阻塞）。

Cross-OS：在 non-Linux 上 pacman freeze 检查自动 skip + 标 N/A。
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACMAN_CONF = Path("/etc/pacman.conf")
FREEZE_MARKER = "# === Phase 3C campaign freeze BEGIN ==="
ARTIFACT_MIN_FREE_GIB = 100
DISK_PATH_TO_CHECK = PROJECT_ROOT / ".artifacts"


class Gate:
    def __init__(self) -> None:
        self.checks: list[Tuple[str, str, str]] = []  # (level, label, msg)
        self.has_block = False

    def ok(self, label: str, msg: str = "") -> None:
        self.checks.append(("OK", label, msg))

    def warn(self, label: str, msg: str) -> None:
        self.checks.append(("WARN", label, msg))

    def block(self, label: str, msg: str) -> None:
        self.checks.append(("BLOCK", label, msg))
        self.has_block = True

    def na(self, label: str, msg: str) -> None:
        self.checks.append(("N/A", label, msg))

    def render(self) -> str:
        lines = ["=" * 60, "Production Readiness Gate (168h campaign 启动前检查)", "=" * 60, ""]
        block_count = 0
        warn_count = 0
        ok_count = 0
        for level, label, msg in self.checks:
            tag = {"OK": "OK   ", "WARN": "WARN ", "BLOCK": "BLOCK", "N/A": "N/A  "}[level]
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
    if platform.system() != "Linux":
        gate.na("pacman freeze", f"non-Linux ({platform.system()}) — skip")
        return
    if not PACMAN_CONF.exists():
        gate.na("pacman freeze", "/etc/pacman.conf 不存在 — 非 Arch/CachyOS 系统")
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


def check_venv_and_ortools(gate: Gate) -> None:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python_win = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        if venv_python_win.exists():
            venv_python = venv_python_win
        else:
            gate.block("venv", f".venv/bin/python 或 .venv/Scripts/python.exe 不存在 — 跑 cachyos_setup.sh --apply")
            return
    try:
        result = subprocess.run(
            [str(venv_python), "-c", "from ortools.sat.python import cp_model; print(cp_model.CpSolver().parameters.num_search_workers)"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        gate.block("ortools import", f"venv python 调用失败: {exc}")
        return
    if result.returncode != 0:
        gate.block("ortools import", f"venv 里 import ortools 失败 (exit {result.returncode}): {result.stderr.strip()[:200]}")
        return
    gate.ok("ortools import", "venv ortools.sat.python 可导入")


def check_preflight_gate(gate: Gate) -> None:
    venv_python = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python_win = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        if venv_python_win.exists():
            venv_python = venv_python_win
        else:
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
    if platform.system() != "Linux":
        gate.na("kernel", f"non-Linux ({platform.system()})")
        return
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


def main() -> int:
    gate = Gate()
    check_pacman_freeze(gate)
    check_venv_and_ortools(gate)
    check_preflight_gate(gate)
    check_kernel(gate)
    check_disk_space(gate)
    check_git_clean(gate)
    print(gate.render())
    return 1 if gate.has_block else 0


if __name__ == "__main__":
    sys.exit(main())
