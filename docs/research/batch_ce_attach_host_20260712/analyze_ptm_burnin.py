#!/usr/bin/env python3
"""PTM7950 烧机×批C probe 合体轮(2026-07-13 凌晨)收尾分析。

用法(烧机 DONE 后,任何会话/模型接手跑):
    python docs/research/batch_ce_attach_host_20260712/analyze_ptm_burnin.py

做三件事:
1. 归档:把易失的 scratchpad ptm_burnin/ 拷进本目录 ptm_burnin_20260713/(/tmp 重启即清,先抢救数据);
2. 分析:温度曲线(逐轮 peak 趋势=PTM 铺展证据/冷段底部)、内存(mem.csv 1s 采样:各轮 RSS 峰/均/中位+HWM+swap)、
   solve 结果(各 cycle_N/cell.json:status/cut_count/wall)、崩溃(coredumpctl 当晚新 core);
3. 输出 markdown 摘要到 stdout(贴给 owner 用)。

判读口径(写死在此,防换会话后口径漂移):
- 逐轮 peak 温度下降→PTM 铺展生效;不降≠失败(94°C 峰值本身在预期内,循环幅度 ΔT≈50°C 才是主驱动)。
- solve 全部零崩→SIGSEGV 热嫌疑主导(见 auto-memory 卡 uv-python-interpreter-intermittent-segfault item 12 判据树);
  再崩→memtest86+ → BIOS P 核 +50mV 复测(13900KS Vmin shift 对症)。
- cell.json 的 cut_count 只有在 master OPTIMAL/FEASIBLE 且 binding 出过结论时才有判定力(批C 计划 §7 F-1~F-3)。
"""
from __future__ import annotations

import csv
import json
import shutil
import statistics
import subprocess
from pathlib import Path

SCRATCH = Path(
    "/tmp/claude-1000/-home-zhuran24-zmd-pj/3e9c4e4c-c0ae-4a71-98f5-05f8b3a5a644/scratchpad/ptm_burnin"
)
HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "ptm_burnin_20260713"


def archive() -> Path:
    if SCRATCH.is_dir():
        ARCHIVE.mkdir(exist_ok=True)
        for f in SCRATCH.iterdir():
            dst = ARCHIVE / f.name
            if f.is_dir():
                shutil.copytree(f, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(f, dst)
        print(f"<!-- archived {SCRATCH} -> {ARCHIVE} -->")
    src = ARCHIVE if ARCHIVE.is_dir() else SCRATCH
    if not src.is_dir():
        raise SystemExit("既无 scratchpad 数据也无归档——数据已丢,只剩 cycle.log 若曾贴进对话")
    return src


def main() -> None:
    src = archive()
    print("# PTM7950 烧机×批C probe 合体轮汇总(2026-07-13)\n")

    print("## 轮次事件(cycle.log)\n```")
    log = src / "cycle.log"
    if log.exists():
        print(log.read_text().strip())
    print("```\n")

    temps = src / "temps.csv"
    if temps.exists():
        by_cycle: dict[str, dict[str, list[int]]] = {}
        for row in csv.reader(temps.open()):
            if len(row) != 4:
                continue
            _, cyc, phase, t = row
            try:
                by_cycle.setdefault(cyc, {}).setdefault(phase, []).append(int(t))
            except ValueError:
                continue
        print("## 温度(30s 采样;逐轮 hot peak 下降=PTM 铺展证据)\n")
        print("| 轮 | hot peak | hot 均值 | cool 底部 |")
        print("|---|---|---|---|")
        for cyc in sorted(by_cycle, key=int):
            h = by_cycle[cyc].get("hot", [])
            c = by_cycle[cyc].get("cool", [])
            print(
                f"| {cyc} | {max(h) if h else '-'} | "
                f"{round(statistics.mean(h)) if h else '-'} | {min(c) if c else '-'} |"
            )
        print()

    mem = src / "mem.csv"
    if mem.exists():
        by_tag: dict[str, dict[str, list[int]]] = {}
        for row in csv.DictReader(mem.open()):
            try:
                d = by_tag.setdefault(row["tag"], {"rss": [], "hwm": [], "swap": []})
                d["rss"].append(int(row["rss_kb"]))
                d["hwm"].append(int(row["hwm_kb"]))
                d["swap"].append(int(row["swap_kb"]))
            except (KeyError, ValueError):
                continue
        print("## 内存(1s 采样,GiB;峰值口径=HWM 终值+同刻 swap)\n")
        print("| run | RSS 峰 | RSS 均值 | RSS 中位 | HWM 终值 | swap 峰 |")
        print("|---|---|---|---|---|---|")
        g = 1048576
        for tag in sorted(by_tag):
            d = by_tag[tag]
            print(
                f"| {tag} | {max(d['rss'])/g:.1f} | {statistics.mean(d['rss'])/g:.1f} | "
                f"{statistics.median(d['rss'])/g:.1f} | {max(d['hwm'])/g:.1f} | {max(d['swap'])/g:.1f} |"
            )
        print()

    print("## solve 结果(cell.json)\n")
    print("| 轮 | status | master | cut_count | lbbd wall(s) | ledger |")
    print("|---|---|---|---|---|---|")
    for cdir in sorted(src.glob("cycle_*")):
        cell = cdir / "cell.json"
        if not cell.exists():
            print(f"| {cdir.name} | 无 cell.json(TIMEOUT 被掐/崩溃,查 run.log) | | | | |")
            continue
        d = json.loads(cell.read_text())
        ps = d.get("proof_summary", {}) or {}
        lr = d.get("ledger_read", {}) or {}
        print(
            f"| {cdir.name} | {d.get('status')} | {ps.get('master_status')} | "
            f"{d.get('coordinate_framework_cut_count')} | {d.get('lbbd_wall_seconds')} | "
            f"{lr.get('status')}/{lr.get('events')}ev |"
        )
    print()

    print("## 当晚 coredump(22:00 起;空表=零崩溃→热嫌疑主导)\n```")
    try:
        out = subprocess.run(
            ["coredumpctl", "list", "--since", "2026-07-12 22:00", "--no-pager"],
            capture_output=True, text=True, timeout=15,
        )
        print(out.stdout.strip() or out.stderr.strip())
    except Exception as e:  # noqa: BLE001
        print(f"coredumpctl 不可用: {e}")
    print("```")


if __name__ == "__main__":
    main()
