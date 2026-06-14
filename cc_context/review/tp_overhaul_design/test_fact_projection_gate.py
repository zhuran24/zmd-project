#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回归 fixture for fact↔projection forcing function (设计草稿伴随测试).

落地时随 check_fact_projection_layer 一起搬进 src/tests/ (或保留在 cc_context 下,
但要让 CI 的 pytest 收集到), 给 forcing function 自身做回归 —— 这正是它要治的病的
解药: 「又出现新马甲就加一个不能回归的 fixture, 而不是又记一条更强的规则」。

可直接 `python` 跑 (无 pytest 也能自检), 也可 `pytest` 收集。
"""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("fpg", _HERE / "fact_projection_gate_design.py")
_FPG = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FPG)


def _node(name: str, fm_extra: str = "", body: str = "") -> str:
    return f"---\nname: {name}\n{fm_extra}---\n{body}\n"


# _HERE 已是 tp_overhaul_design 目录 (上面 _HERE = ...parent), 故 repo root = parents[2]
# (review→cc_context→repo)。注意: gate_design.py 的 main() 用 Path(__file__).parents[3]
# 是因为那里基准是文件本身(未先取 .parent), 多一层 —— 两处基准不同, 别照抄层数。
_REPO_ROOT = _HERE.resolve().parents[2]


def _run(files: dict[str, str], repo_root=None):
    d = Path(tempfile.mkdtemp())
    for fn, txt in files.items():
        (d / fn).write_text(txt, encoding="utf-8")
    return _FPG.check_fact_projection_layer(d, repo_root=repo_root)


def test_empty_layer_is_noop():
    """fact 层未落地 → 零 error 零 warning (对现状零影响, 铁律 C)。"""
    errs, warns = _run({"plain.md": _node("plain", "type: feedback\n", "普通节点。")})
    assert errs == [] and warns == []


def test_reference_integrity_warns_on_missing_path():
    """检查 3 (引用完整性, warn 级): fact/投影正文引用不存在的仓库路径 → warn;
    存在的路径、URL、单层带点词都不报 (误报边界)。真值源=文件系统。"""
    errs, warns = _run({
        "feedback_fact_x.md": _node(
            "fact-x", "metadata:\n  node_role: fact\n",
            "见 `scripts/check_memory_tree.py` (真存在) 和 `scripts/ghost_deleted.py` (不存在)。"
            "URL https://example.com/a/b.py 不该当路径; 单层 version.json 不算路径。"),
        "feedback_rule_a.md": _node("rule-a", "metadata:\n  derives_from: fact-x\n", "[[fact-x]]"),
    }, repo_root=_REPO_ROOT)
    assert errs == []                                      # 引用完整性是 warn 不 block
    assert any("ghost_deleted.py" in w for w in warns)     # 不存在的报
    assert not any("check_memory_tree.py" in w for w in warns)  # 存在的不报
    assert not any("example.com" in w for w in warns)      # URL 不误报
    assert not any("version.json" in w for w in warns)     # 单层带点词不误报


def test_reference_integrity_off_without_repo_root():
    """不传 repo_root → 检查 3 不跑 (引用路径不存在也不报), 只跑检查 1/2。"""
    _, warns = _run({
        "feedback_fact_y.md": _node("fact-y", "metadata:\n  node_role: fact\n", "见 `a/b/ghost.py`。"),
        "feedback_rule_b.md": _node("rule-b", "metadata:\n  derives_from: fact-y\n", "[[fact-y]]"),
    })  # 不传 repo_root
    assert not any("引用完整性" in w for w in warns)


def test_healthy_relation_single_source():
    """fact 不列 projections; 关系只在投影的 derives_from。两投影认领 → 0 err。
    多个投影认同一 fact 也不用在 fact 侧维护任何清单 (机器反向派生)。"""
    errs, _ = _run({
        "fact-x.md": _node("fact-x", "metadata:\n  node_role: fact\n", "抽象事实 X。"),
        "rule-a.md": _node("rule-a", "metadata:\n  derives_from: fact-x\n", "规则A 派生自 [[fact-x]]。"),
        "rule-b.md": _node("rule-b", "metadata:\n  derives_from: [fact-x]\n", "规则B 见 [[fact-x]]。"),
    })
    assert errs == []


def test_dead_fact_blocks():
    """fact 没有任何投影 derives_from 它 → 死事实 (真值源=反向索引, 不看正文 link)。"""
    errs, _ = _run({
        "fact-dead.md": _node("fact-dead", "metadata:\n  node_role: fact\n", "没人派生我。"),
        "rule-c.md": _node("rule-c", "type: feedback\n", "普通节点不挂事实。"),
    })
    assert any("死事实" in e for e in errs)


def test_fact_with_only_prose_link_still_dead():
    """关键: fact 即使正文被随便一条散文 [[link]] 提到, 只要没投影 derives_from 它,
    仍是死事实 —— 死事实判据用 derives_from 反向索引(硬关系), 不用正文 link 计数
    (会被任意散文撑起来=噪声)。这道题 v1 的 indeg 版会漏判(误判活), v2 抓得到。"""
    errs, _ = _run({
        "fact-q.md": _node("fact-q", "metadata:\n  node_role: fact\n", "抽象事实 Q。"),
        "mentions.md": _node("mentions", "type: feedback\n", "随口提一下 [[fact-q]], 但我不派生自它。"),
    })
    assert any("死事实" in e for e in errs)


def test_orphan_projection_declares_but_no_wikilink():
    errs, _ = _run({
        "fact-y.md": _node("fact-y", "metadata:\n  node_role: fact\n", "事实Y。"),
        "rule-d.md": _node("rule-d", "metadata:\n  derives_from: fact-y\n", "声明派生自 fact-y 但正文没链。"),
    })
    assert any("孤立投影" in e for e in errs)


def test_bad_derives_from_targets():
    errs, _ = _run({
        "fact-w.md": _node("fact-w", "metadata:\n  node_role: fact\n", "事实W 被 [[rule-f2]] 认领。"),
        "rule-f.md": _node("rule-f", "metadata:\n  derives_from: ghost-fact\n", "[[ghost-fact]] 不存在。"),
        "rule-g.md": _node("rule-g", "metadata:\n  derives_from: rule-f\n", "[[rule-f]] 不是 fact。"),
        "rule-f2.md": _node("rule-f2", "metadata:\n  derives_from: fact-w\n", "[[fact-w]] 让 W 不死。"),
    })
    assert any("不存在的节点" in e for e in errs)
    assert any("不是 fact" in e for e in errs)


def test_no_second_list_to_drift():
    """回应 km-skeptic 反讽门槛: 不存在 fact 侧的 projections 清单, 所以没有「改一边
    没改另一边」的双向漂移可能。即便 fact frontmatter 残留旧 projections 字段, gate
    也完全无视它 (不读), 关系只认 derives_from 一处。"""
    errs, _ = _run({
        "fact-r.md": _node("fact-r", "metadata:\n  node_role: fact\n  projections: [ghost1, ghost2]\n",
                           "事实R 残留了过时 projections 字段, gate 应无视。"),
        "rule-j.md": _node("rule-j", "metadata:\n  derives_from: fact-r\n", "真正认领 R 的是我 [[fact-r]]。"),
    })
    # 残留的 ghost1/ghost2 不该引发任何 error (字段被无视); 关系靠 rule-j 闭合
    assert errs == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    raise SystemExit(0 if passed == len(fns) else 1)
