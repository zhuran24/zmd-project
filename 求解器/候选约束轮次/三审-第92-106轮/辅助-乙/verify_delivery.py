#!/usr/bin/env python3
"""核验乙席报告、复算回执和短JSON，不执行其他席位程序。"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent / "辅助-乙.md"
ROOT = HERE.parent.parent
text = REPORT.read_text()
data = json.loads((HERE / "results.json").read_text())
assert data["all_checks_passed"]
assert data["script_sha256"] == hashlib.sha256((HERE / "independent_check.py").read_bytes()).hexdigest()

items = [
    {"name": "9 混做清空", "final_version": "第92-94轮/推导92A.md，第491—494行；95T、101H迁移保留", "assessment": "可直接通过", "note": "清空截止和整批出缓存条件成立，通道下界3、2、2、2独立复算一致。"},
    {"name": "10 回路存量", "final_version": "第92-94轮/推导92A.md，第501—504行；95T、101H迁移保留", "assessment": "可直接通过", "note": "16步最短存续时间与周期守恒支持64、22、42，半开窗边界已核。"},
    {"name": "14 满速箱头限存", "final_version": "并行：第92-94轮/推导92A.md第541—544行；推导92B.md §N56第636—646行，两版等强", "assessment": "可直接通过", "note": "满速迫使每路每8步成功一次；超过c_x的箱头库存必阻断拒收路，两个观察时点表述等价。"},
    {"name": "15 传输与送货先后", "final_version": "第92-94轮/推导92A.md，第551—554行；95T、101H迁移保留", "assessment": "可直接通过", "note": "规则37明确保留两种动作先后，临时规则没有消除此项。"},
    {"name": "11 传输箱不满", "final_version": "第101-103轮/推导101H.md §10 H08，第315—327行；承接92A、95T", "assessment": "有疑点", "note": "18件原结论可保留；15件加强依赖第40步判定时到期已可见，94A提出的晚一拍读法尚需裁定。"},
    {"name": "12 轮询均分", "final_version": "第101-103轮/推导101H.md §5 H03，第83—99行；替代92A跨离线解释", "assessment": "可直接通过", "note": "段内固定轮转及跨m次离线差至多m+1的证明成立，清空记录分支已吸收。"},
    {"name": "13 混料轮询分料", "final_version": "第101-103轮/推导101H.md §6 H04，第109—121行；替代92A跨离线解释", "assessment": "可直接通过", "note": "最大公约数公式复算一致；跨离线保留实际通道、物品清单及未完尾段计数。"},
    {"name": "16 核心邻格", "final_version": "第92-94轮/推导92B.md §N61，第712—723行；95T、101H迁移保留", "assessment": "可直接通过", "note": "邻格数、端头接触、角位和宽度排除均成立，未把不排除误写成可实现。"},
]
assert len(items) == 8 and len({i["name"] for i in items}) == 8
for i in items:
    assert i["assessment"] in {"可直接通过", "有疑点", "未做完"}
    assert all(isinstance(v, str) and v for v in i.values())
    assert i["name"] in text
assert text.count("**建议：可直接通过。**") == 7
assert text.count("**建议：有疑点") == 1
assert "92A版，候选条文" in text and "92B版，§N56" in text

unchanged, changed = [], []
for rel, info in data["inputs"].items():
    current = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    (unchanged if current == info["sha256"] else changed).append(rel)
assert not changed, changed

links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
missing = []
for link in links:
    path = REPORT.parent / link.split("#", 1)[0]
    if path == HERE / "delivery_check.json":
        continue
    if not path.exists():
        missing.append(link)
assert not missing, missing

expected = {
    "925,504": data["polling_groups"]["four_group_exhaustive_cases"],
    "6,629,312": data["polling_groups"]["success_events"],
    "30,272": data["saturated_box_head"]["phase_acceptance_observation_cases"],
    "6,144": data["box_cooling"]["cases"],
    "45,000": data["polling_resets"]["time_interval_checks"],
    "38,430": data["mixed_formula"]["indicator_equalities"],
    "3,306": data["core_geometry"]["legal_interval_core_touch_cases"],
}
for written, value in expected.items():
    assert int(written.replace(",", "")) == value
    assert written in text

response = {"report_path": str(REPORT), "items": items}
(HERE / "return.json").write_text(json.dumps(response, ensure_ascii=False, indent=2)+"\n")
receipt = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "status": "PASS",
    "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
    "report_lines": len(text.splitlines()),
    "items": len(items), "can_pass": 7, "questions": 1, "unfinished": 0,
    "links_checked": len(links), "missing_links": missing,
    "input_files_unchanged": unchanged, "input_files_changed": changed,
    "math_result_all_passed": True, "number_alignment_checks": expected,
    "reader_review": [
        "八条完整条文均可从本报告单独读取，内部H03编号换正式名称",
        "A/B并行箱头版本分别列出并比较等强关系",
        "40/41步敏感性不是规则反例或全厂反例",
        "程序实例与全称证明范围已分开",
        "已复读状态、版本链、数字与交叉引用，无超时未完成条目"
    ]
}
(HERE / "delivery_check.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
print(json.dumps({k: receipt[k] for k in ["status", "items", "can_pass", "questions", "unfinished", "links_checked"]}, ensure_ascii=False))
