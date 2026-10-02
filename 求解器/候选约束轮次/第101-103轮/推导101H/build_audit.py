"""Version-specific audit of all 35+10+2+3 requested entries."""
from pathlib import Path
import hashlib
import json
import re

OUT = Path(__file__).resolve().parent
OLD = OUT.parent.parent/"第95-97轮"

NOTES_92 = [
("沿用95M§1", "只展开合法建造与数层选择；不从旧轮询历史推流量。"),
("H01修订", "40步只在无冷却清空的连续段保持；离线清空使下一次判定重新传输。"),
("H02修订", "更新实际送货触发，并明确每个元件或非运输单位每步一次；离线后从更新状态派生步序。"),
("沿用95M§2", "级间排序先于轮询，同级成功记录清空不反转严格层数差。"),
("结论不变", "存在性例可选择不离线；对所有实际可达循环的量词已覆盖新分支。"),
("沿用95M§3", "不含缓存的实际件数守恒不使用记录或冷却周期固定性。"),
("结论不变", "不可逆误料与选定不再离线的后续仍在允许集合内；制造容量上界不变。"),
("结论不变", "逐次实际传输前检查余量，含清空冷却新增的传输；不能只按旧相位抽查。"),
("结论不变", "批次切换截止和实际通道容量，不依赖轮询起点。"),
("结论不变", "配方、运输滞留及存量积分；离线不删除物品或重启制造。"),
("H08补证", "原18上界仍真；证明改用相邻清空至多40步，而非跨离线恰40步。"),
("H03修订", "固定接通先后仍可能发生记录清空；加入无离线段及跨段界。"),
("H04修订", "同余公式依赖H03的固定成功词，不能跨清空沿用旧编号和清单相位。"),
("结论不变", "满速取等迫使8步一次，拒收箱头的物理障碍与轮询历史无关。"),
("结论不变", "每次箱判定仍需覆盖传输与送货两种先后，冷却只改变哪些判定会传输。"),
("结论不变", "核心端口与必需矿口的几何及容量上界，不以轮询公平作前提。"),
("本项依赖不变", "采用后续M/G几何版本；方向账不使用成功记录或固定冷却。这里不裁定M/G角格版本差异。"),
("本项依赖不变", "同上，按所采用的M/G版本配套X、Y；不以此次迁移消除原几何争议。"),
("结论不变", "对实际拼接料序的每个前缀及有限清出作前提，清空造成的新料序也必须检查。"),
("H05修订", "取消无条件跨离线固定轮转和差≤1；跨离线差≤2且循环均分仍成立。"),
("结论不变", "400步来自初始原料，服务界由最多3条出口与8步滞留推出，不需成功记录。"),
("并入H06", "176为正常完整步末的加强支；起值减半件改为段内，给跨离线累计界与正存量界。"),
("并入H07", "活性原结论保留，改用不依赖记录的正存量证明；与满库存强版分列。"),
("沿用95M§6及95T§5", "两者输入均纯带、来源单出口，不比较成功记录；原含准入口版已有其他修订。"),
("并入H06", "承接95T无准入口、单轴桥版；150与176按起点条件统一。"),
("并入H07", "满起态使C两路请求错开，不依赖历史；K首单位恢复桥接器的一轴。"),
("沿用95M§7", "完整元件的实际格步占用；清空只能改变实际先后，前件要重新核对。"),
("结论不变", "断支守恒与实际先判容量上界；无离线坏运行仍合法。"),
("结论不变", "每个实际循环满速即间隔全为8；没有承诺所有循环共用一个余数。"),
("结论不变", "单口8步、机器一步一件给最早同种段长度，无公平性假设。"),
("结论不变", "两实际口均满速且错相，成功交替来自容量取等，偶数同种段来自整批。"),
("沿用95M§8", "新主料首件和第二件的物理到达下界，不使用记录。"),
("结论不变", "H按实际成熟拒收且耗掉唯一判定计费，冷却清空会变H，不变占格式。"),
("沿用95M§9", "新版明确固定完整状态、保留不同轮询历史分支；每次离线更新后再用交换证明。旧全范围不在本轮恢复。"),
("旧证依赖已由95M§10消除", "92版借跨操作Φ−1/2；95M改为A/C关机准备、统一开启时直接计数，不再调用此界。"),
]

NOTES_M = [
"建造和数层全称量词，不使用成功历史。",
"级间严格层数差，与级内历史无关。",
"实际件数守恒，离线无库存跳变。",
"几何方向账与容量上界，未用轮询公平或冷却。",
"同上；保留其版本配套定义，本轮不合并M/G角格差异。",
"纯带、单出口源；证明已明确不借跨离线记忆。",
"完整元件格步计数，前件为实际判定先后。",
"开批到新主料两次到达的步数下界。",
"明确不同轮询历史仍须覆盖；清空后从完整新状态重新比较。",
"关机放料、开启终点静态Φ；已消除92版跨调试Φ−1/2依赖。",
]


def main():
    originals = json.loads((OLD/"第92轮候选清单.json").read_text())
    assert len(originals) == len(NOTES_92) == 35
    rows = []
    for i, (entry, (disposition, reason)) in enumerate(zip(originals, NOTES_92), 1):
        rows.append(dict(id=f"92-{i:02d}", source="第92轮候选清单.json",
                         group=entry["group"], name=entry["name"], kind=entry["kind"],
                         original_text=entry["text"], disposition=disposition, reason=reason))
    md = (OLD/"推导95M.md").read_text()
    sections = list(re.finditer(r"(?m)^## (\d+)\. ([^\n]+)$", md))
    for j, match in enumerate(sections):
        number = int(match[1])
        if not 1 <= number <= 10:
            continue
        section = md[match.end():sections[j+1].start()]
        name = match[2]
        text = section.split(name+"：", 1)[1].split("\n\n据：", 1)[0].strip()
        rows.append(dict(id=f"95M-{number:02d}", source="推导95M.md", group="M", name=name,
                         kind=re.search(r"种类：(.*?)。", section)[1], original_text=text,
                         disposition="无需因本次补充改文", reason=NOTES_M[number-1]))
    for group, count in (("G", 2), ("T", 3)):
        entries = json.loads((OLD/f"推导95{group}"/"candidates.json").read_text())
        assert len(entries) == count
        for i, entry in enumerate(entries, 1):
            disposition = "无需因本次补充改文"
            reason = "端口、配方和几何方向计数，不依赖成功记录或传输冷却。"
            if group == "T":
                disposition = ["无需因本次补充改文", "并入H06", "并入H07"][i-1]
                reason = ["纯带和单出口源，同95M§6；缓存与填路证明不需要历史。",
                          "150的起值支依赖跨离线成功先后；与92C的正常步末176支统一。",
                          "满库存证明不依赖轮询记录；按97T恢复K取货首单位桥的另一轴可有通道。"][i-1]
            rows.append(dict(id=f"95{group}-{i:02d}", source=f"推导95{group}.md",
                             group=group, name=entry["name"], kind=entry["kind"],
                             original_text=entry["text"], disposition=disposition, reason=reason))
    assert len(rows) == 50 and len({row["id"] for row in rows}) == 50
    result = dict(total=50, counts={"92": 35, "95M": 10, "95G": 2, "95T": 3}, entries=rows)
    (OUT/"audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    lines = ["| 编号 | 条目 | 处置 | 依赖检查 |", "|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['id']} | {row['group']}／{row['name']} | {row['disposition']} | {row['reason']} |")
    (OUT/"audit_table.md").write_text("\n".join(lines)+"\n")
    # Include the two data files used to obtain exact corresponding full texts.
    manifest = json.loads((OUT/"inputs.json").read_text())
    for group in ("G", "T"):
        p = OLD/f"推导95{group}"/"candidates.json"
        data = p.read_bytes()
        row = dict(path=str(p.resolve()), sha256=hashlib.sha256(data).hexdigest(),
                   bytes=len(data), lines=len(data.splitlines()))
        manifest = [r for r in manifest if r["path"] != row["path"]]+[row]
    (OUT/"inputs.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(dict(total=len(rows), counts=result["counts"]), ensure_ascii=False))


if __name__ == "__main__":
    main()
