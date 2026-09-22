"""条文、存量恒等式和已给手推表的核对；不是内核或全基地模拟。"""
from fractions import Fraction
from hashlib import sha256
from itertools import product
from pathlib import Path
import json
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
DOC = OUT.parent / "回路总数决定论-v2.md"
checks = {}

manifest = json.loads((OUT / "输入核对.json").read_text())
for source in manifest["sources"]:
    path = Path(source["path"])
    assert sha256(path.read_bytes()).hexdigest() == source["sha256"], path
checks["all_16_recorded_inputs_unchanged"] = True
checks["protected_files"] = [
    entry for entry in manifest["sources"]
    if Path(entry["path"]).parent == ROOT
]
assert len(checks["protected_files"]) == 4

review = ROOT / "求解器/规格/推导/复核/否证-1-证据"
snapshot = json.loads((review / "正式文件与被审66行.json").read_text())
for source in snapshot["sources"]:
    current = Path(source["path"]).read_text()
    saved = source["text"]
    assert sha256(saved.encode()).hexdigest() == source["sha256"]
    if Path(source["path"]).name == "回路总数决定论.md":
        assert current.startswith(saved)
        assert len(saved.splitlines()) == 66
    else:
        assert current == saved
report = (review.parent / "否证-1.md").read_text()
fence = chr(96) * 3
embedded = json.loads(report.split(fence + "json\n", 1)[1].split("\n" + fence, 1)[0])
assert embedded == json.loads((review / "结构化结论.json").read_text())
assert (review / "被审66行.md").read_text() == "".join(
    (OUT.parent / "回路总数决定论.md").read_text().splitlines(keepends=True)[:66]
)
checks["review_snapshot_and_embedded_verdicts_match"] = True

# 原手推表：只重核计数与首次放出旧缓存的时刻，不声称重建全部事件。
trace = json.loads((review / "逐tick反例.json").read_text())
rows = trace["rows"]
assert [r["tick"] for r in rows if r["gate_seed_intake"]] == [0, 5]
for row in rows:
    assert row["delta_plant_plus_seed_count"] == (
        row["S_completed_since_start"] - row["C_completed_since_start"]
    )
    withdrawal = sum(
        r["gate_seed_intake"] for r in rows if r["tick"] <= row["tick"]
    )
    before = 50 - withdrawal
    assert before == row["S_output_before_cache_flush"]
    assert row["S_old_cache_flushed"] == (before <= 48)
    assert row["S_output_after_cache_flush"] == (
        before + 2 * row["S_old_cache_flushed"]
    )
assert rows[4]["delta_plant_plus_seed_count"] == -4
assert rows[5]["delta_plant_plus_seed_count"] == -5
assert rows[5]["S_completed_since_start"] == 0
checks["denial_1_manual_trace_counts"] = {
    "t4_net_change": -4,
    "t5_net_change": -5,
    "old_cache_release_is_not_new_completion": True,
}

# 否证 2 正文的前五个空位分配。
occupancies = [50] * 4
four_machine_rows = []
for tick, index in enumerate([0, 1, 2, 3, 0]):
    occupancies[index] -= 1
    release = occupancies[index] <= 48
    before = occupancies.copy()
    if release:
        occupancies[index] += 2
    four_machine_rows.append({
        "tick": tick, "source": index + 1, "before_cache_release": before,
        "release_old_cache": release, "new_harvest_completions": 0,
        "crush_completions": tick, "net_change": -tick,
    })
assert not any(r["release_old_cache"] for r in four_machine_rows[:4])
assert four_machine_rows[4]["release_old_cache"]
assert four_machine_rows[4]["net_change"] == -4
checks["denial_2_manual_trace_counts"] = four_machine_rows

# 有限取值检查防止公式转录错误，不代替一般代数证明。
identity_cases = 0
for ah, ag, h, g, ih, ig, other_loss in product(range(3), repeat=7):
    total_loss = ih + ig + other_loss
    dn = h - g - total_loss
    dbh = ah - h - ih
    dbg = ag - g - ig
    dk = dn + dbh - dbg
    assert dk == ah - ag - total_loss - ih + ig
    identity_cases += 1
checks["corrected_inventory_identity_cases"] = identity_cases
checks["identity_scope"] = (
    "代数恒等式；各整数取值不宣称是可到达的物理事件。"
    "无入库且无其他跨界交换时化为 delta K = delta A_H - delta A_G。"
)

for seeds, unassigned, bh, bg in product(range(4), repeat=4):
    total = seeds + unassigned + bh + bg
    corrected = total + bh - bg
    assert corrected == seeds + unassigned + 2 * bh
    assert corrected >= 0
checks["nonnegative_corrected_count_cases"] = 4 ** 4

n = 40
offset_trace = []
for tick, h, g in [(0, 0, 0), (1, 1, 0), (2, 0, 1)]:
    n += h - g
    offset_trace.append({"tick": tick, "N": n, "H": h, "G": g})
assert [r["N"] for r in offset_trace] == [40, 41, 40]
checks["completion_offset_trace"] = offset_trace

# 采种首次输出清出需求，不冒充释放过程全部净损失。
for q in range(51):
    same = max(0, q - 48)
    assert q - same + 2 <= 50
    if same:
        assert q - (same - 1) + 2 > 50
    different = q
    assert q - different == 0
    if different:
        assert q - (different - 1) > 0
clearance = {str(m): 2 * 16 + 48 * m for m in (0, 1, 16)}
assert clearance == {"0": 32, "1": 80, "16": 800}
checks["first_clearance_not_total_net_loss"] = clearance
checks["capacity_arithmetic_not_safety_margin"] = [
    {"assumed_loss": loss, "4800_minus_loss": 4800 - loss,
     "difference_from_necessary_128": 4800 - loss - 128}
    for loss in (32, 80, 800)
]

assert 50 * Fraction(3, 5) + 40 * Fraction(11, 20) == 52
checks["target_mineral_budget_exact"] = {
    "battery": "3/5", "capsule": "11/20", "mineral_rate": 52,
    "scope": "已达标循环的必要配平；不证明任意初态可达标。",
}

doc = DOC.read_text()
assert re.findall(r"^## §([0-5]) ", doc, re.M) == list("012345")
assert re.findall(r"^\d+\. \*\*(U\d+)", doc, re.M) == [
    f"U{i}" for i in range(1, 9)
]
assert "conclusion_stands = 否" in doc
assert doc.count(r"\[") == doc.count(r"\]")
for line in doc.splitlines():
    assert line.count("$") % 2 == 0, line
assert r"\(" not in doc and r"\)" not in doc
for target in re.findall(r"\]\(([^)]+)\)", doc):
    path = Path(target)
    if not path.is_absolute():
        path = DOC.parent / path
    assert path.exists(), path
formal = "\n".join(
    (ROOT / name).read_text()
    for name in ("《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt")
)
premises = doc.split("### 1.2", 1)[1].split("### 1.3", 1)[0]
quote_count = 0
for line in premises.splitlines():
    if not line.startswith("|"):
        continue
    for quote in re.findall("“([^”]+)”", line.split("|")[2]):
        assert quote in formal, quote
        quote_count += 1
checks["formal_premise_quotes_exact_substrings"] = quote_count
checks["document_structure_links_math_and_unproved_list"] = True
checks["document_sha256"] = sha256(DOC.read_bytes()).hexdigest()
checks["kernel_run"] = False
checks["limits"] = [
    "没有复演完整基地，也没有证明反馈收敛、全部相位或起法覆盖。",
    "32、80、800 是首次清出算术，不是已认证的全程净损失上界。",
    "脚本不验证全部自然语言推导；独立复核仍列为 U8。",
]
(OUT / "核对结果-本版.json").write_text(
    json.dumps(checks, ensure_ascii=False, indent=2) + "\n"
)
(OUT / "核对-本版.log").write_text(
    "PASS: 16 recorded inputs unchanged; review evidence matches; "
    "manual trace counts, corrected inventory algebra, first-clearance arithmetic, "
    "mineral budget, premise quotes, links and document structure checked.\n"
    "SCOPE: no kernel simulation; no complete-layout certificate; "
    "no proof of universal startup safety or phase independence.\n"
)
print((OUT / "核对-本版.log").read_text(), end="")
