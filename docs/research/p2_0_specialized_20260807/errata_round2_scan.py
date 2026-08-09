#!/usr/bin/env python3
"""勘误二轮（20260807，外审份4 + 核签）的验收扫描器 —— 一条命令产出全部机器收据。

背景：勘误**一轮**的完成度声明「本文已按该表就地订正」被外审份4 的 D-01 证伪（稿内仍有
6 处残留矛盾）。核签 `ADJUDICATION_fen4.md` §3.A 因此要求二轮改用**机器收据**关闭，而不是
自述。本脚本就是那份收据的生成器。

三段检查：

  [1] 旧误文扫描  逐条扫外审 + 核签点名的旧说法，命中分四类：
        BARE    裸命中——正文主叙述里仍在用旧说法。**必须为 0**，非 0 即不得标完成。
        TRACED  留痕命中——在引用块 / 带撤销标记的行 / 勘误一轮 errata 表的「现文」列里。
                这是家规「不静默覆盖」要求的痕迹，属正常，数目越多说明留痕越全。
        PROBE   探针冻结面——三个研究探针的 printed string / receipt 字段 / 内部注释。
                **刻意不改**：一改，归档的 *_stdout.log 与 *_receipt.json 就与脚本对不上，
                而它们是历史证据件。三个探针的 docstring 顶部已加勘误注，写明怎么读其输出。
        OTHER   本批施工范围外的文档（GAME_RULE_IMPACT_AUDIT.md 由 rule-impact-audit 席维护，
                本席不越界改；已在 CHECKLIST 的「新发现」栏登记）。
        另有两个文件整体不参与 [1]：本脚本自身（含全部短语字面量）与
        ERRATA_ROUND2_CHECKLIST.md（台账件，按设计逐字引用被撤旧说法）。
        两条排除都是显式声明的，见 LEDGER_FILES 与 CHECKLIST §4.3。

  [2] 新文断言  逐条断言订正后的新说法**确实写进去了**（防「删了旧的没写新的」）。

  [3] 外部件复跑  external_round2/ 的五个零依赖脚本复跑，与归档 stdout 逐字节比对。

用法：
    ./.venv/bin/python docs/research/p2_0_specialized_20260807/errata_round2_scan.py
    （或任何 python3——本脚本零依赖）
退出码 0 = 三段全过。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]  # <repo>/docs/research/<batch> -> <repo>

TARGETS = [HERE, ROOT / ".artifacts/gpt_pro_review_batch_20260807/DISPATCH_README.md"]
SKIP_SUFFIX = {".log", ".json"}                 # 归档机器输出，不是叙述文本
SKIP_DIRS = {"__pycache__", "external_round2"}  # external_round2 是外部原件，不得改

PROBE_FILES = {"split_free_probe.py", "maxmin_segment_probe.py", "split_free_probe_v2.py"}
OTHER_FILES = {"GAME_RULE_IMPACT_AUDIT.md"}
# 台账件：按设计就要逐字引用被撤的旧说法（「原文 X → 改为 Y」），
# 它们是收据本身、不是被订正的语料，故不参与 [1] 旧误文扫描。
# 这条排除是**显式声明**的，理由与逐条影响记在 ERRATA_ROUND2_CHECKLIST.md §4.3。
LEDGER_FILES = {"ERRATA_ROUND2_CHECKLIST.md"}

TRACE_MARKERS = [
    "已撤", "撤回", "原文", "原引", "原称", "原标题", "原话", "原稿", "原「", "原判",
    "勘误二轮", "应改为", "现文", "撤销依据", "已删", "取代", "已失效", "已闭合",
    "读作", "不是 616", "不可达", "证伪", "复算", "核签自产",
]


def is_errata_table_row(line: str) -> bool:
    """勘误一轮 §8 errata 表的行：| <位置> | <现文> | <应改为> |"""
    s = line.strip()
    if not (s.startswith("|") and s.count("|") >= 4):
        return False
    return s.startswith(("| §", "| 「", "| **Q", "| R2", "| 缺陷", "| 同段"))


# ---------------------------------------------------------------- [1] 旧误文
OLD_PHRASES = [
    ("已证为空", "D-01 / R2 风险行 + Q2"),
    ("常数（本稿 receipt", "D-01 / §9.1 工程量表"),
    ("6 种商品", "D-01 / 旧六例判决"),
    ("6 种货", "D-01 / OWNER 旧六例判决"),
    ("占 37%", "D-01 / 旧流量占比"),
    ("占总流量 37%", "D-01 / 旧流量占比"),
    ("未过独立 refute 席", "D-01 / README 欠账"),
    ("混流只可能发生在分流细流段", "D-01 / README 给 mixflow 的旧收窄"),
    ("网络级纯流恒不成立", "D-05 / 措辞越级"),
    ("没有第三条路", "D-05 / 措辞越级"),
    ("混流窗口", "D-05 / 措辞越级"),
    ("共道窗口", "D-05 / 措辞越级"),
    ("一格只准走一种中间货", "D-05 / OWNER"),
    ("shared-lane window always exists", "D-05 / canonical 替换文本"),
    ("NETWORK-LEVEL PURE FLOW IS UNCONDITIONALLY FALSE", "D-05 / canonical 替换文本"),
    ("无条件失效", "D-05 / 定理 2 旧标题"),
    ("616", "D-06 / 616 不可达（可达最小值是 622）"),
    ("前件与结论互斥", "D-06"),
    ("前件和结论互斥", "D-06 / OWNER"),
    ("理论下确界", "D-06"),
    ("理论下限", "D-06 / OWNER"),
    ("更满足前件 (ii)", "D-06 / 旧小节标题"),
    ("公分母 = **660**", "D-07"),
    ("公分母 660", "D-07 / 行数量级表"),
    ("乘 660 后全部系数为整数", "D-07"),
    ("整数（乘 660）", "D-07 / 行数量级表"),
    ("不需要新变量结构", "D-08"),
    ("不依赖任何前件", "D-09"),
    ("这个好处**不依赖", "D-09 / OWNER"),
    ("欠两条", "D-10"),
    ("欠**两条**", "D-10"),
    ("两条是甲案的未闭合项", "D-10"),
    ("从 1 条变成 2 条", "D-10"),
    ("上界 = 下界 ⇒ 全局 lex", "D-11"),
    ("零前件", "D-11 / D-08"),
    ("零有理变量", "R-06"),
    ("从 {1} 扩到 {1, 1/2}", "R-06"),
    ("全部段速率是单一常数", "R-06"),
    ("更容易而非更难", "R-08"),
    ("甲案族在速率算术层非空", "R-08"),
    ("rate_lemma_recompute.py:36", "A4b 行号订正 → :34/:37"),
    (":42-44", "A4b 行号订正 → :42-43"),
    ("为了让包自包含才放进来的", "C3 / DISPATCH_README"),
]

# ---------------------------------------------------------------- [2] 新文
NEW_ASSERTS = [
    # ---- A1 README ----
    ("README.md", "勘误二轮（20260807，外审份4 + 核签）", "A1 勘误标注"),
    ("README.md", "均摊硬编码制造出来的", "A1 :17 六例判决订正"),
    ("README.md", "10.5%", "A1 :17 真实流量占比"),
    ("README.md", "warehouse-bridge 排除", "A1 :17 前件（R-03）"),
    ("README.md", "master 显式固定了每商品的容量预留", "A1 :19 分解前件（D-09）"),
    ("README.md", "该报告本身的独立复审也已完成", "A1 :38 欠账订正"),
    ("README.md", "速率算术恒能找到一对不同中间品的段", "A1 :45 mixflow 收窄订正"),
    ("README.md", "`min_side` 上界从未立过", "A1 :21 D-11"),
    ("README.md", "external_round2", "A5/A6 索引"),
    # ---- A2 设计稿 ----
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "勘误二轮（20260807，外审份4 + 核签）", "A2 勘误标注"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "复合命题必须拆标签", "A2 §0 后新规则（D-13）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "命题 S2（聚合占空约束与算术自由域）", "A2 :45（D-04）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "U_rate", "A2 :45 单向包含（D-04）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "速率算术点", "A2 :45 uniform/staircase 改称"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "结论 A：无分支路由对两种作物不可能", "A2 §2.4（D-05）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "结论 B：速率分离不能无条件推出物理纯度", "A2 §2.4（D-05）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "速率兼容对", "A2 §2.4/§7.1 措辞（D-05）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "反稀释条款", "A2 §2.5（D-06 核签版）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "可达最小值是 **622**", "A2 §2.5（D-06 核签版）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "rate_lemma_recompute.py:34", "A4b 行号（§2.5）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "rate_lemma_recompute.py:42-43", "A4b 行号（§2.2）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "P7-S 的最小完整变量与行族", "A2 §3（D-08）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "exact LP / Fraction", "A2 §3 P2（D-07）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "甲-A0", "A2 §4（D-10）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "甲-A1", "A2 §4（D-10）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "甲-A2", "A2 §4（D-10）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "OB-P1（物理纯度支配，未证）", "A2 §4（D-10）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "阶段 A（面积）", "A2 §4 闭合判据（D-11）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "阶段 S（最短边）", "A2 §4 闭合判据（D-11）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "语义一致性", "A2 §4 闭合前提（核签补）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "Q1 实验规格", "A2 Q1 改造（D-08）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "model_proto_bytes", "A2 Q1 十四指标（D-08）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "**Q12**", "A2 新增开放问题（D-08）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "**Q13**", "A2 新增开放问题（D-11）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "**Q14**", "A2 新增开放问题（R-09）"),
    ("P2_0_SPECIALIZED_DESIGN_V1.md", "ERRATA_ROUND2_CHECKLIST.md", "A2 收据索引"),
    # ---- A3 OWNER 摘要 ----
    ("OWNER_DECISION_SUMMARY.md", "勘误二轮（20260807，外审份4 + 核签）", "A3 勘误标注"),
    ("OWNER_DECISION_SUMMARY.md", "再往下推就越界了", "A3 :21（D-05）"),
    ("OWNER_DECISION_SUMMARY.md", "防稀释", "A3 :23（D-06 核签版）"),
    ("OWNER_DECISION_SUMMARY.md", "真正够得到的最小值是 622", "A3 :23（D-06 核签版）"),
    ("OWNER_DECISION_SUMMARY.md", "最短边那一半的上界从来没有人立过", "A3 min_side（D-11）"),
    ("OWNER_DECISION_SUMMARY.md", "min_side 维度本文未触碰", "A3 我方文档自证（D-11）"),
    # ---- A4 重判报告 ----
    ("REJUDGE_REPORT.md", "勘误二轮（20260807，外审份4 + 核签）", "A4 勘误标注"),
    ("REJUDGE_REPORT.md", "本报告的证据等级规则", "A4 §0 后（R-10）"),
    ("REJUDGE_REPORT.md", "rate-balance-admissible", "A4 §0.1（R-10）"),
    ("REJUDGE_REPORT.md", "定理 1（作物回流必然分支", "A4 §3 标题（R-03）"),
    ("REJUDGE_REPORT.md", "warehouse-bridge routing 继续被当前模型排除", "A4 §3 前件（R-03）"),
    ("REJUDGE_REPORT.md", "净加强", "A4 §3 删多余前件（核签加强）"),
    ("REJUDGE_REPORT.md", "定理 2（速率分离不能推出物理纯度）", "A4 §3 标题（D-05）"),
    ("REJUDGE_REPORT.md", "完备二分", "A4 §4（D-06 核签版）"),
    ("REJUDGE_REPORT.md", "628 / 622 / **622**", "A4 §4 车道数订正（D-06）"),
    ("REJUDGE_REPORT.md", "max(n_op, ⌈c_p · x_op⌉)", "A4 §4 逐项下界（核签）"),
    ("REJUDGE_REPORT.md", "`:34` 的 `util = runs / machines`", "A4b 行号（§4 正文）"),
    ("REJUDGE_REPORT.md", "行号订正（勘误二轮，核签 §1.4）", "A4b 行号（§4 留痕）"),
    ("REJUDGE_REPORT.md", "rate_lemma_recompute.py:37", "A4b 行号（§4 分支二）"),
    ("REJUDGE_REPORT.md", "exact interval proof", "A4 §4 Part F（R-05）"),
    ("REJUDGE_REPORT.md", "A STATED PER-MACHINE DUTY VECTOR", "A4 方向 b 主修（D-06 核签）"),
    ("REJUDGE_REPORT.md", "LOCAL TO EACH ACTIVE MACHINE PORT", "A4 方向 b 附加澄清"),
    ("REJUDGE_REPORT.md", "固定 duty 后，端口速率固定，但内部段速率仍未固定", "A4 §5.2（R-06）"),
    ("REJUDGE_REPORT.md", "3/20, 1/5, 1/2, 11/20, 3/5, 1", "A4 §5.2 六元速率集（R-06）"),
    ("REJUDGE_REPORT.md", "Part D、Part F 以及 Part G", "A4 §9 欠账 2（R-05）"),
    ("REJUDGE_REPORT.md", "hardware_key = H(route_or_rate_state_key)", "A4 §9 欠账 4（R-09）"),
    ("REJUDGE_REPORT.md", "external_round2", "A5/A6 索引"),
    # ---- A4b 探针注释 ----
    ("split_free_probe_v2.py", "rate_lemma_recompute.py:34", "A4b :25 行号订正"),
    # ---- C3 ----
    ("DISPATCH_README.md", "发出去的 zip 一个都没装", "C3 如实口径"),
    ("DISPATCH_README.md", "必须随包", "C3 下批外发硬要求"),
]

# ---------------------------------------------------------------- [3] 外部件
EXTERNAL_SCRIPTS = [
    "independent_handcheck",
    "independent_staircase_check",
    "independent_part_f_continuous_proof",
    "aggregate_reading_check",
    "true_min_lanes",
]


def collect_files() -> list[Path]:
    out: list[Path] = []
    for t in TARGETS:
        if t.is_file():
            out.append(t)
            continue
        for p in sorted(t.rglob("*")):
            if p.resolve() == Path(__file__).resolve():
                continue  # 扫描器自身含全部短语字面量，不参与扫描
            if p.is_file() and p.suffix not in SKIP_SUFFIX and not any(
                d in p.parts for d in SKIP_DIRS
            ):
                out.append(p)
    return out


def scan_old(cache: dict[Path, list[str]]) -> int:
    totals = {"BARE": 0, "TRACED": 0, "PROBE": 0, "OTHER": 0}
    rows = []
    for phrase, tag in OLD_PHRASES:
        buckets: dict[str, list[tuple[str, int, str]]] = {
            "BARE": [], "TRACED": [], "PROBE": [], "OTHER": []
        }
        for p, lines in cache.items():
            if p.name in LEDGER_FILES:
                continue  # 台账件：见 LEDGER_FILES 注释
            for i, line in enumerate(lines, 1):
                if phrase not in line:
                    continue
                rel = str(p.relative_to(ROOT))
                if p.name in OTHER_FILES:
                    kind = "OTHER"
                elif (line.lstrip().startswith(">")
                      or any(m in line for m in TRACE_MARKERS)
                      or is_errata_table_row(line)):
                    kind = "TRACED"
                elif p.name in PROBE_FILES:
                    kind = "PROBE"
                else:
                    kind = "BARE"
                buckets[kind].append((rel, i, line.strip()[:120]))
        for k in totals:
            totals[k] += len(buckets[k])
        rows.append((phrase, tag, buckets))

    print("[1] 旧误文扫描")
    print(f"    短语 {len(OLD_PHRASES)} 条   "
          f"BARE={totals['BARE']}  TRACED={totals['TRACED']}  "
          f"PROBE={totals['PROBE']}  OTHER={totals['OTHER']}")
    for phrase, tag, b in rows:
        flag = "OK" if not b["BARE"] else "!! BARE"
        print(f"    [{flag:>7}] T={len(b['TRACED']):<2} P={len(b['PROBE']):<2} "
              f"O={len(b['OTHER']):<2} {phrase!r}  ({tag})")
        for kind in ("BARE", "PROBE", "OTHER"):
            for rel, i, txt in b[kind]:
                print(f"              [{kind}] {rel}:{i}  {txt}")
    return totals["BARE"]


def assert_new(cache: dict[Path, list[str]]) -> int:
    by_name: dict[str, str] = {}
    for p, lines in cache.items():
        by_name[p.name] = "\n".join(lines)
    missing = 0
    print("\n[2] 新文断言")
    for fname, phrase, tag in NEW_ASSERTS:
        text = by_name.get(fname)
        if text is None:
            print(f"    !! MISSING-FILE {fname}")
            missing += 1
            continue
        if phrase in text:
            print(f"    [ OK ] {fname}  {phrase!r}  ({tag})")
        else:
            print(f"    [!!MISS] {fname}  {phrase!r}  ({tag})")
            missing += 1
    print(f"    断言 {len(NEW_ASSERTS)} 条，缺失 {missing} 条")
    return missing


def rerun_external() -> int:
    d = HERE / "refute_round1" / "external_round2"
    print("\n[3] external_round2 复跑（与归档 stdout 逐字节比对）")
    bad = 0
    if not d.is_dir():
        print("    !! 目录不存在")
        return 1
    for s in EXTERNAL_SCRIPTS:
        py, log = d / f"{s}.py", d / f"{s}_stdout.log"
        if not py.is_file() or not log.is_file():
            print(f"    [!!MISS] {s}  脚本或日志缺失")
            bad += 1
            continue
        r = subprocess.run([sys.executable, str(py)], cwd=d,
                           capture_output=True, text=True)
        same = r.stdout == log.read_text(encoding="utf-8")
        print(f"    [{'  OK  ' if same and r.returncode == 0 else '!!DIFF'}] "
              f"{s}  exit={r.returncode}  "
              f"{'逐字节相同' if same else '与归档 stdout 不一致'}")
        if not same or r.returncode != 0:
            bad += 1
    return bad


def main() -> int:
    cache: dict[Path, list[str]] = {}
    for p in collect_files():
        try:
            cache[p] = p.read_text(encoding="utf-8").splitlines()
        except Exception:
            cache[p] = []

    print("勘误二轮验收扫描 —— 机器收据（20260807，外审份4 + 核签）")
    print(f"扫描文件 {len(cache)} 个\n" + "=" * 78)
    bare = scan_old(cache)
    miss = assert_new(cache)
    bad = rerun_external()

    print("\n" + "=" * 78)
    ok = (bare == 0 and miss == 0 and bad == 0)
    print(f"总判：裸命中={bare}  新文缺失={miss}  外部件复跑失败={bad}  "
          f"⇒ {'PASS（三段全过，可标完成）' if ok else 'FAIL（不得标完成）'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
