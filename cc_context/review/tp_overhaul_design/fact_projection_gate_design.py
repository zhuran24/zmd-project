#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DESIGN DRAFT — fact↔projection forcing function (km-forcing / Q3).

这是**设计草稿**, 不是落地动作。落地 = team-lead 把这里的三个 `_check_fact_*`
函数合并进 `scripts/check_memory_tree.py`(它已挂 preflight_gate.py [11/17] +
CI + pre-push hook, 见 §"接入"), 不新建独立 test。本文件可独立 `python` 跑,
对当前 repo 树自检一遍, 证明它在 fact 层未落地时**零误报**(no-op until opt-in)。

------------------------------------------------------------------------------
治什么 (team-lead 三需求)
------------------------------------------------------------------------------
知识侧 normalize 出「抽象事实层 (fact 节点) + 投影回指」结构后, 这套治理本身
不能再变成靠人记得维护、会再漂的负担(否则同一个病换层)。需要一个 forcing
function 让下列三种情况**自动报红**, 类比 authoritative_numbers 的 pytest gate:

  (1) 新增投影/规则节点, 却没接到任何抽象事实(孤立于事实层);
  (2) 某 fact 节点没有被任何投影回指(死事实);
  (3) 投影声称依据的事实, 与事实节点实际内容漂移。

需求 (3) 字面是「语义内容漂移」, 无机器真值源 (见铁律 B); v2 把它收敛为唯一有真
值源且零额外维护的子集 = **引用关系完整性** (derives_from 指向的 fact 真存在、真是
fact、且在正文落地成 wikilink)。语义忠实度交人/审查。不为了凑满 (3) 去硬测语义而
引入会漂的新补丁 —— 那正是本治理要避免的「同一个病换层」。

------------------------------------------------------------------------------
设计三铁律 (全部从 authoritative_numbers 先例 + 本项目实测约束推出)
------------------------------------------------------------------------------
铁律 A — **opt-in, 不猜**: 一个节点只有在 frontmatter **显式**声明角色才进入
  检查范围。fact 节点声明 `node_role: fact`; 投影节点声明 `derives_from:
  <fact-slug>`。脚本**绝不**去猜「这条规则像不像某 fact 的投影」—— 猜必然误报,
  会淹没真信号(authoritative_numbers 拒绝扫散文同理)。这也直接满足 team-lead
  「别强制每个节点都必须挂事实(有些天然是纯事实/纯参考)」: 没声明角色的普通
  节点, 这个 gate **完全不管**。

铁律 B — **关系单一真值源, 其余机器派生 (km-skeptic 反讽门槛 v2 收敛)**: 需求
  (3)「投影与事实内容漂移」字面是语义漂移, 正则比不了、硬测必误报。但更深的陷阱是:
  若我让 fact 维护一份 `projections:` 清单、投影维护 `derives_from:` 清单、再查两者
  对称 —— 那两份就是**同一关系的冗余拷贝**, `projections:` 这张表本身会漂, 等于
  「拿一个会漂的检查守另一个会漂的东西」(违反 memory-currency-protocol「能指针就别
  copy 值、嵌值=drift 负债」)。正解: 关系**只存一处** = 投影节点的 `derives_from`
  (投影作者写投影时就知道的局部知识, 且本来就要和正文 [[fact]] wikilink 耦合)。
  fact 的「我有哪些投影」由全树 **derives_from 反向派生** (机器算, 零维护)。于是
  没有第二份清单可漂, 双向闭合检查随之消失 —— 这正是「不引入新补丁」的体现。语义
  忠实度 (投影正文是否还忠于 fact 陈述) 无机器真值源, 诚实交回人/审查, 不进 gate。

铁律 C — **fail-soft 分层, 跟现有 gate 一致**: 结构性硬不变量(死事实/孤立投影/
  derives_from 指向不存在或非-fact 的 slug)→ **block**(returncode 1, 同现有
  isolated/unresolved 检查); 而「fact 层整个还没落地」「harness 不在场」这类
  → 静默 no-op, 不报红。gate 在 fact 层为空时必须是纯加法、对现状零影响。

------------------------------------------------------------------------------
为什么不写死任何 slug (回应 km-arbiter Q1)
------------------------------------------------------------------------------
factmap 的「7 个 fact + 各自投影」还可能调整。所以脚本**不写死**任何具体 slug,
也不内嵌「应有几个 fact」。真值源 = 节点自己的 frontmatter:
  - fact 节点用 `node_role: fact` 自描述 (只声明「我是 fact」, 不列投影);
  - 投影节点用 `derives_from: <fact-slug>` 自描述 (唯一记录关系的地方)。
脚本只查 derives_from 是否落地为真 wikilink、目标是否真 fact, 并反向派生每个 fact
有没有人认领。fact↔投影清单怎么改, 改的是投影的 derives_from 一处, gate 自动跟着
走, 不用动脚本、也没有第二份表要同步维护。这正是 authoritative_numbers 把真值放进
core node、test 只查「core == live recompute」的同构搬运。

------------------------------------------------------------------------------
为什么 fact 的 repo 锚定必须靠真 repo 投影节点 (回应 km-arbiter Q2)
------------------------------------------------------------------------------
factmap index_size_note 建议把 fact 挂进 collaboration-rules-index /
gpt-delivery-acceptance-discipline / verification-hardening-ladder 等索引父节点。
**实测**: 这些索引父节点在 repo cc_context/memory 树里**不存在** —— 它们是
harness-only 合成节点(由 sync_memory_to_harness.py 动态生成, repo 侧无文件)。
而 check_memory_tree.py 只扫 repo 树。所以:
  - fact 节点的「被认领 / 不死」靠**真实存在的 repo 投影节点**
    (root-cause-over-symptom / lazy-mode / no-gpt-concurrency-field 等) 用
    `derives_from: <fact>` 认领它 + 正文 `[[fact]]` wikilink 落地;
    harness-only 节点的认领**不计入** repo gate (harness 不在扫描范围) —— 这是
    特性: 强制每个 fact 必须有 repo 锚, 否则 repo gate 永远抓不到它漂没漂;
  - fact 节点本身**不进 MEMORY.md 顶层**(factmap 设计, 省 24KB 预算), 故本 gate
    把 `node_role: fact` 节点**豁免**现有「每个节点必须进 MEMORY.md」coverage 检查
    (否则现有 coverage 检查会把 fact 节点当 missing 报红 —— 那是误报)。
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

# ------------------------------------------------------------------ frontmatter
# 复用 check_memory_tree.py 的宽松解析风格: 节点 frontmatter **不保证合法 YAML**
# (description 里有裸 `:` 和 Windows `\` 路径, 见 no-gpt-concurrency-field), 所以
# 不能用 yaml.safe_load。逐行扫, 支持两种现存写法: 顶层平铺 (feedback_lazy_mode:
# `type: feedback`) 和 `metadata:` 缩进块 (root-cause-over-symptom)。

_FM_RE = re.compile(r"^---\s*$")
_LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

# 引用完整性 (检查 3) 用: 只认「明确像仓库相对路径」的形态, 不猜裸词 (避免误报)。
# 形态 = 一段含至少一个 `/` 的路径, 以已知源码/配置扩展名结尾。前导可有反引号。
# 已知扩展名收窄到本仓真实出现的几类, 防止把 URL / 普通带点词误当路径。
_PATH_EXT = r"(?:py|json|md|yml|yaml|toml|sh|ps1|txt|cfg|ini)"
_REPO_PATH_RE = re.compile(
    r"(?<![\w./-])"                      # 左边界: 不接在别的路径/词中间
    r"((?:[\w.-]+/)+[\w.-]+\." + _PATH_EXT + r")"  # a/b/c.ext (至少一层目录)
    r"(?![\w/])"                          # 右边界
)
# 绝对/Windows 路径 (D:\... 或 /home/...) 是历史遗留示例语境, 不当仓库相对路径校验。


def _repo_path_refs(text: str) -> set[str]:
    """从节点正文抽出「明确像仓库相对路径」的引用 (去重)。只取相对路径形态,
    跳过 frontmatter 块 (那里是 description/derives_from, 不是正文引用)。"""
    body = text.split("---", 2)[2] if text.count("---") >= 2 else text
    refs: set[str] = set()
    for m in _REPO_PATH_RE.finditer(body):
        ref = m.group(1)
        # 排除明显是 URL 一部分的 (前面紧跟 http(s):// 的已被左边界挡掉大部分, 这里兜底)
        if "://" in ref:
            continue
        refs.add(ref)
    return refs


def _frontmatter_block(text: str) -> str | None:
    if not text.startswith("---"):
        return None
    try:
        return text.split("---", 2)[1]
    except IndexError:
        return None


def _scalar(block: str, field: str) -> str | None:
    """取 frontmatter 里某 scalar 字段 (顶层或 metadata 缩进块下均可)。"""
    pat = re.compile(rf"(?m)^\s*{re.escape(field)}\s*:\s*(.+?)\s*$")
    m = pat.search(block)
    if not m:
        return None
    return m.group(1).strip().strip('"').strip("'") or None


def _list_field(block: str, field: str) -> list[str]:
    """取 frontmatter 里某 list 字段, 容两种写法:
        derives_from: [a, b]           # flow list
        derives_from:                  # block list
          - a
          - b
    单值 `derives_from: a` 也当单元素 list。空 / 缺失 → []。
    """
    # flow list 或单值
    m = re.search(rf"(?m)^\s*{re.escape(field)}\s*:\s*(.+?)\s*$", block)
    inline = m.group(1).strip() if m else ""
    if inline:
        if inline.startswith("[") and inline.endswith("]"):
            inner = inline[1:-1]
            return [s.strip().strip('"').strip("'") for s in inner.split(",") if s.strip()]
        return [inline.strip('"').strip("'")]
    # block list: field: 之后是若干 `  - item`
    block_m = re.search(rf"(?m)^\s*{re.escape(field)}\s*:\s*$", block)
    if not block_m:
        return []
    out: list[str] = []
    for line in block[block_m.end():].splitlines():
        ls = line.strip()
        if ls.startswith("- "):
            out.append(ls[2:].strip().strip('"').strip("'"))
        elif ls and not ls.startswith("#"):
            break  # 下一个字段, list 结束
    return [s for s in out if s]


# ------------------------------------------------------------------ node model
class _Node:
    __slots__ = ("name", "path", "role", "type_", "derives_from", "body_links")

    def __init__(self, name: str, path: Path, block: str, text: str):
        self.name = name
        self.path = path
        # fact 标记两种口径都认 (对齐落地实际): GPT/km-arbiter retype 落地用 `type: fact`;
        # team-lead 原措辞 + 我早先草稿用 `node_role: fact`。落地走了 type:fact (实测 harness
        # fact-* 节点 frontmatter 全是 metadata.type: fact), 故 gate 必须认 type:fact 否则
        # 对落地的 fact 全空转。同时保留 node_role 兼容, 不破任何一边。
        self.role = (_scalar(block, "node_role") or "").lower()
        self.type_ = (_scalar(block, "type") or "").lower()
        # 关系的唯一真值源: 投影声明自己派生自哪个 fact。fact 侧**不**维护 projections
        # 清单 (v1 砍掉 — 冗余拷贝会漂)。fact 的被投影集由全树 derives_from 反向派生。
        self.derives_from = [s.lower() for s in _list_field(block, "derives_from")]
        # 正文里真实出现的 wikilink (用于「frontmatter 声明 vs 正文落地」一致性)
        body = text.split("---", 2)[2] if text.count("---") >= 2 else text
        self.body_links = {m.group(1).strip().lower() for m in _LINK_RE.finditer(body)}

    @property
    def is_fact(self) -> bool:
        return self.role == "fact" or self.type_ == "fact"

    @property
    def is_projection(self) -> bool:
        return bool(self.derives_from)


def _load_nodes(memory_dir: Path) -> dict[str, _Node]:
    nodes: dict[str, _Node] = {}
    for p in sorted(memory_dir.glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        text = p.read_text(encoding="utf-8")
        block = _frontmatter_block(text)
        if block is None:
            continue
        name = _scalar(block, "name")
        if not name:
            continue
        nodes[name.lower()] = _Node(name.lower(), p, block, text)
    return nodes


# ------------------------------------------------------------------ 两检查
# 返回 (errors, warnings)。errors → block(returncode 1); warnings → 非阻断打印。
#
# 单一真值源 (km-skeptic 反讽门槛收敛后, v2):
#   fact↔投影 这条关系**只存一处** = 投影节点的 `derives_from`。fact 的「被哪些
#   投影回指」**不**手维护第二份清单 (原 v1 的 `projections:` 字段已砍 —— 那是同一
#   关系的冗余拷贝, 违反 memory-currency-protocol「能指针就别 copy 值、嵌值=drift
#   负债」, 是「拿会漂的表守会漂的东西」)。fact 的被投影集 = **全树扫 derives_from
#   反向派生** (机器算, 零维护、零漂移)。于是没有第二套清单可漂, 双向闭合检查随之
#   消失。这跟 authoritative_numbers「真值进 core node、其余 recompute」同构。

def check_fact_projection_layer(
    memory_dir: Path, repo_root: Path | None = None
) -> tuple[list[str], list[str]]:
    """repo_root 给了 → 额外跑检查 3 (引用完整性, warn 级); 不给 → 只跑检查 1/2。
    合并进 check_memory_tree.py 时传 PROJECT_ROOT 即可启用引用完整性。"""
    nodes = _load_nodes(memory_dir)
    facts = {n.name: n for n in nodes.values() if n.is_fact}
    projections = {n.name: n for n in nodes.values() if n.is_projection}

    # fact 层整个未落地 → 纯 no-op, 对现状零影响 (铁律 C)
    if not facts and not projections:
        print("fact↔projection layer: 未启用 (无 node_role:fact / derives_from 节点), 跳过")
        return [], []

    errors: list[str] = []
    warnings: list[str] = []

    # 唯一真值源: 全树 derives_from 反向索引 fact -> {认它的投影}。机器派生, 不读任何
    # 手维护清单。这一份就是「fact 有哪些投影」的权威答案。
    claimed_by: dict[str, set[str]] = defaultdict(set)
    for pname, proj in projections.items():
        for fslug in proj.derives_from:
            claimed_by[fslug].add(pname)

    # --- 检查 1: 死事实 — fact 没有任何投影 derives_from 它 (真值源 = 反向索引) ---
    # 注意用 derives_from 反向索引, 不用「正文 [[link]] 计数」: 后者会被任意散文链
    # 撑起来 (噪声), 前者是「显式声明派生」的硬关系。要求 fact 必须被≥1 个**真投影
    # 认领**, 否则它就是没人派生的悬空抽象 = 死事实。
    for fname in sorted(facts):
        if not claimed_by.get(fname):
            errors.append(
                f"死事实: fact 节点 [[{fname}]] 没有任何投影 derives_from 它 — "
                f"抽象事实存在的意义就是被投影派生, 无投影认领 = 该删或该被某投影认领"
            )

    # --- 检查 2: 孤立投影 — derives_from 声明了, 但 (a) 目标不存在/不是 fact, 或
    #     (b) 正文没把这条派生落地成真 [[fact]] wikilink。真值源全在投影**自己这一个
    #     文件内** (frontmatter vs 正文), 无跨文件清单, 不会漂。 ---
    for pname, proj in sorted(projections.items()):
        for fslug in proj.derives_from:
            if fslug not in nodes:
                errors.append(
                    f"投影 {proj.path.name} 的 derives_from: {fslug} 指向不存在的节点"
                )
                continue
            if fslug not in facts:
                errors.append(
                    f"投影 {proj.path.name} 的 derives_from: {fslug} 指向的节点不是 fact "
                    f"(缺 node_role: fact) — derives_from 只能指向抽象事实层"
                )
                continue
            if fslug not in proj.body_links:
                errors.append(
                    f"孤立投影: {proj.path.name} frontmatter 声明 derives_from: {fslug}, "
                    f"但正文没有 [[{fslug}]] wikilink — 声明与正文不一致 (回指没落地)"
                )

    # --- 检查 3 (warn 级): 引用完整性 — fact/投影节点正文里引用的仓库文件路径是否真存在。
    #     真值源 = 文件系统 (km-skeptic 反讽门槛认可的那类: 路径/flag 在不在是机读硬事实,
    #     漂了确定性报红, 不碰任何语义/策略判断)。守的是「节点正文指向已删/改名的脚本就
    #     烂尾」(fact/投影节点高发: 它们正文常引 stamp_living_status.py / check_memory_tree.py
    #     这类来说明 forcing 机制)。 ---
    #     保守边界: ① 只扫 fact+投影节点 (opt-in, 不扫全树散文); ② 只认「明确像仓库路径」
    #     的形态 (反引号包裹 或 含 `/` + 已知扩展名), 不猜裸词; ③ warn 不 block (正文路径
    #     可能有历史/示意成分, 误报不该阻断 push, 但漂了要响亮提醒)。
    if repo_root is not None:
        for nname, node in sorted({**facts, **projections}.items()):
            for ref in _repo_path_refs(node.path.read_text(encoding="utf-8")):
                if not (repo_root / ref).exists():
                    warnings.append(
                        f"引用完整性: {node.path.name} 正文引用仓库路径 `{ref}` 不存在 "
                        f"(脚本被删/改名 → 节点烂尾; 真值源=文件系统)"
                    )

    print(
        f"fact↔projection layer: facts={len(facts)}, projections={len(projections)}, "
        f"errors={len(errors)}, warnings={len(warnings)} "
        f"(真值源=derives_from 单向 + 引用路径文件系统存在性)"
    )
    return errors, warnings


# ----------------- coverage 豁免 (供合并进 check_memory_tree._check_links 时用) ----
def fact_nodes_to_exempt_from_index(memory_dir: Path) -> set[str]:
    """node_role:fact 节点不进 MEMORY.md 顶层 (factmap 设计省 24KB 预算), 故现有
    coverage 检查 (known - covered) 计算时应把它们从 `known` 减掉, 否则误报 missing。
    合并落地点: check_memory_tree._check_links 里 `missing = sorted(known - covered)`
    改成 `missing = sorted(known - covered - fact_nodes_to_exempt_from_index(...))`。"""
    return {n.name for n in _load_nodes(memory_dir).values() if n.is_fact}


# ------------------------------------------------------------------ standalone
def main() -> int:
    root = Path(__file__).resolve().parents[3]  # repo root from .../tp_overhaul_design/
    memory_dir = root / "cc_context" / "memory"
    if not memory_dir.is_dir():
        print(f"memory dir not found: {memory_dir}", file=sys.stderr)
        return 2
    errors, warnings = check_fact_projection_layer(memory_dir, repo_root=root)
    for w in warnings:
        print(f"  WARN {w}")
    if errors:
        print("fact↔projection check FAILED:")
        for e in errors:
            print(f"  {e}")
        return 1
    print("fact↔projection check passed (or layer not yet enabled — no-op)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
