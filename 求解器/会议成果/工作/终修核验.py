"""核验终修的文件边界、文档结构与有限算术；不模拟或认证游戏。"""
from pathlib import Path
from fractions import Fraction as F
import hashlib
import json
import re

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
BASELINE = json.loads((WORK / "终修输入指纹.json").read_text())["inputs"]
OUTPUT = WORK / "终修核验.json"
EDITED = [
    ROOT / "求解器/会议成果/会议2成果修订-v46.md",
    ROOT / "求解器/会议成果/任务书7草案.md",
    ROOT / "求解器/规格/推导/回路总数决定论-v2.md",
    ROOT / "求解器/规格/推导/三种相位不改产量-v2.md",
]
RECORD = WORK / "终修记录.md"
checks = []


def check(name, ok, detail=None):
    checks.append({"name": name, "pass": bool(ok), "detail": detail})


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


readonly = {}
for name, before in BASELINE.items():
    p = Path(name)
    if p in EDITED:
        continue
    after = fingerprint(p)
    readonly[name] = {"before": before["sha256"], "after": after}
    check("只读输入保持原字节", before["sha256"] == after, name)

outputs = {}
for p in EDITED:
    outputs[str(p)] = {"sha256": fingerprint(p), "lines": len(p.read_text().splitlines())}
    check("指定正文确有改动", fingerprint(p) != BASELINE[str(p)]["sha256"], str(p))

v, task, loop, phase = [p.read_text() for p in EDITED]
old_h = v.split("**v45 H逐项核销。**")[1].split("### 新增")[0]
counts = {
    "replaced": len(re.findall(r"^#### S-", v, re.M)),
    "added": len(re.findall(r"^#### N-F", v, re.M)),
    "old_h_rows": len(re.findall(r"^\| \d", old_h, re.M)),
    "old_h_open": old_h.count("**仍未决**"),
    "main_open": len(re.findall(r"^#### N-F.*（仍未决）", v, re.M)),
    "mapping": len(re.findall(r"^\| F-\d+ \|", v, re.M)),
    "tasks": len(re.findall(r"^### 1\.\d 任务", task, re.M)),
    "task_open_mapping": len(re.findall(r"^\| F-\d+ / N-F\d+ \|", task, re.M)),
    "cost_rows": len(re.findall(r"^\| [1-8] \S+ \|", task, re.M)),
    "roles": len(re.findall(r"^\| (?:codex|opus)", task, re.M)),
}
check("登记计数", counts == dict(replaced=14, added=55, old_h_rows=23,
      old_h_open=12, main_open=26, mapping=69, tasks=8,
      task_open_mapping=26, cost_rows=8, roles=13), counts)
check("F1至F69映射完整", sorted(map(int, re.findall(r"^\| F-(\d+) \|", v, re.M))) == list(range(1, 70)))
ids = re.findall(r"^### ((?:漏|错|头|据|他)-\d+)：", RECORD.read_text(), re.M)
expected = [f"{kind}-{i}" for kind, n in [("漏", 5), ("错", 4), ("头", 4), ("据", 2), ("他", 4)] for i in range(1, n + 1)]
check("19条处理记录完整且无重复", ids == expected, ids)
check("回路指纹同步", outputs[str(EDITED[2])]["sha256"] in v and
      outputs[str(EDITED[2])]["sha256"][:12] in task)
check("两份第二版均有终修记录", "## §6 终修记录" in loop and "## §6 终修记录" in phase)
check("没有虚构回路独立复核文件", not (ROOT / "求解器/规格/推导/复核/否证-v2-loop.md").exists())
review_inputs = json.loads((ROOT / "求解器/规格/推导/证据-v2-phase-否证/input_hashes.json").read_text())
check("相位已有复核绑定本次修订前版本", review_inputs[str(EDITED[3])] == BASELINE[str(EDITED[3])]["sha256"])
check("相位旧缺件状态已更新", "第二版尚未经过新的独立复核" not in phase and
      "缺的是新的独立复核" not in phase and "第二版已有一次独立复核" in phase)
check("范围外旧任务书引用已删除", "2a1af1b1" not in task and "| 格式参考 |" not in task)
check("对用户回退原因的无据解释已删除", "owner最新一句" not in task and "所指是上一次工作流" not in task)
check("旧owner问题引用已同步", "§3第3、4项" not in task and "§3第4项" not in task)
check("成品通路有任务与产物承接", task.count("成品输出通路") >= 4 and "任务书7§1.7" in v)
check("回路公式排版已修正", "N_x$b$" not in loop and "N_x(b)-N_x(a)" in loop)

# 数值复算只核已列算术，不给完整布局存在性或全相位证明。
arithmetic = {
    "crush_base_batches": F(18) + 34 + F(11, 2) + F(21, 2),
    "refine_base_batches": F(34) + 17,
    "mineral_target": 50 * F(3, 5) + 40 * F(11, 20),
    "product_rate": F(3, 5) + F(11, 20),
    "bottling_three_input_bound": F(3, 20) + F(1, 5) + F(1, 5),
    "ordinary_plant_slots": F(48 * 100),
    "normal_plant_cache": F(32 + 2 * 16),
}
check("加工与目标算术", list(arithmetic.values()) == [F(68), F(51), F(52), F(23, 20), F(11, 20), F(4800), F(64)],
      {k: str(x) for k, x in arithmetic.items()})
clearance = [2 * 16 + 48 * m for m in [0, 1, 16]]
check("首次清出需求", clearance == [32, 80, 800], clearance)
check("清出量与必要数的算术差", [4800-x-128 for x in clearance] == [4640, 4592, 3872])
fixed = [3559, 3575, 3584, 3584, 3632, 3632]
transport = [208, 208, 208, 306, 198, 306]
bounds = [4900-a-b for a, b in zip(fixed, transport)]
check("D2直接界", bounds == [1133, 1117, 1108, 1010, 1070, 962], bounds)
check("D2无桥217与D1预算", 4900-3550-306 == 1044 and 1390-4*12-1113 == 229)
# 用独立系数消去完成批次H、G：ΔK=ΔN+ΔB_H−ΔB_G。
delta_n = dict(H=1, G=-1, I=-1)
delta_bh = dict(AH=1, H=-1, IH=-1)
delta_bg = dict(AG=1, G=-1, IG=-1)
coeff = {}
for sign, terms in [(1, delta_n), (1, delta_bh), (-1, delta_bg)]:
    for k, value in terms.items():
        coeff[k] = coeff.get(k, 0) + sign * value
coeff = {k: value for k, value in coeff.items() if value}
check("修正计数消项", coeff == dict(AH=1, AG=-1, I=-1, IH=-1, IG=1), coeff)
arrivals = [0, 4, 5, 6]
check("非滑动窗口例", [sum(a <= t < b for t in arrivals) for a, b in [(0, 5), (5, 10), (4, 9)]] == [2, 2, 3])
check("四通结点整理", 619-93+3*46 == 664)

# 链接仅核本次四稿与记录中的Markdown目标是否存在，不打开历史转录。
links = []
for p in EDITED + [RECORD]:
    for target in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", p.read_text()):
        if target.startswith(("https://", "http://", "#")):
            continue
        raw = target.strip("<>").split("#", 1)[0]
        q = Path(raw) if raw.startswith("/") else p.parent / raw
        exists = q.exists() or q.resolve() == OUTPUT
        links.append({"source": str(p), "target": raw, "exists": exists})
check("Markdown文件链接存在", all(x["exists"] for x in links), [x for x in links if not x["exists"]])

result = {
    "date": "2026-09-20",
    "scope": "文档结构、输入保护、版本对应和所列局部算术；不是内核或整厂认证",
    "pass": all(x["pass"] for x in checks),
    "readonly_inputs": readonly,
    "modified_outputs": outputs,
    "record_sha256": fingerprint(RECORD),
    "checks": checks,
    "link_count": len(links),
    "cargo_entry_check": {
        "cwd": str(ROOT / "求解器"),
        "command": "cargo locate-project --workspace --message-format plain",
        "exit_status": 0,
        "stdout": str(ROOT / "求解器/Cargo.toml"),
        "build_executed": False,
    },
    "simulator_accessed": False,
    "game_runtime_verification": "not run",
    "independent_loop_review": "not delivered",
    "reader_self_review": "完成；不冒称独立读者复核",
}
OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"pass": result["pass"], "checks": len(checks),
                  "failed": [c for c in checks if not c["pass"]],
                  "link_count": len(links)}, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["pass"] else 1)
