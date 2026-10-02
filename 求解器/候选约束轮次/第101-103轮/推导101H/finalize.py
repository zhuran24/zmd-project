"""Extract full candidates, create the short schema reply, verify delivery."""
from pathlib import Path
import ast
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent/"推导101H.md"
MARKER = "<!-- AUDIT_APPENDIX -->"

SHORT = [
    ("传输相位", "必要条件",
     "无离线段内40步一次；冷却清空后在下一次本箱判定重取相位。",
     "规则20、25—27、37；临时规则4。",
     "分别递推保留冷却与归零冷却，组合须共同可达。",
     "修订正式及第92轮A第2条、95T迁移说明，加入清空分支。"),
    ("判定先后", "必要条件",
     "实际送货触发元件联判；每个元件或非运输单位每步一次。",
     "规则25—33；临时规则1、2、4。",
     "从离线更新后的完整状态派生步序，桥两轴分计。",
     "修订正式及第92轮A第3条、95T§3.2，采用96T措辞。"),
    ("轮询均分", "必要条件",
     "原固定轮转限无离线段；非运输单位跨m次离线的件数差≤m+1。",
     "轮询、8步滞留及原组数前件。",
     "段内逐组归纳；跨段按实际成功历史重新计数。",
     "修订正式及第92轮A第12条，固定接通不再等于记录保留。"),
    ("混料轮询分料", "必要条件",
     "固定成功词时保留同余公式；跨离线按实际物品词和通道词计数。",
     "修订后的轮询均分及周期守恒。",
     "模L同余计数；离线尾段不得丢弃或重置。",
     "修订正式及第92轮A第13条，限制跨清空沿用单一公式。"),
    ("整批k件配k条取货通道的均分", "充分条件",
     "原前件下，段内差≤1；任意离线下差≤2，循环均分仍成立。",
     "整批k件、恰k路、独占首格恰8步腾空。",
     "连续有货的k件块各路一次，任意子段仅两端块不完整。",
     "修订正式、第92轮C第20条及95T§3.4，撤去跨清空固定轮转。"),
    ("采种单元的回路存量下界", "充分条件",
     "段内150/176按起点区分；跨清空给累计界，Φ(s)≥1保Φ≥1/2。",
     "正向单轴链、植物配方及物品来源保留。",
     "连续BB反压计数、逐段复合与独立不耗尽证明。",
     "合并正式、92C第22条、92D第25条及95T§6，修正起值支跨离线范围。"),
    ("采种单元不断料", "充分条件",
     "保留条件性活性与满库存强版；K首单位可为另一轴有通道的桥。",
     "正存量、满回路、单链补料、8步滞留。",
     "C两路请求错开；库存与n−1步服务无需成功记录保留。",
     "合并92C第23条与92D第26条、修订95T§7，按97T恢复桥轴范围。"),
    ("传输箱不满", "必要条件",
     "两读法均保留18件界与守恒；现行步进实际可证15件。",
     "持续传输、仓库全收、三口8步滞留。",
     "冷却清空只提前清箱；40步内每口至多5件。",
     "补证正式及第92轮A第11条，清空间隔改用至多40步。"),
]


def write_json(name, obj):
    (HERE/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n")


def main():
    text = REPORT.read_text()
    assert text.count(MARKER) == 1
    text = text.split(MARKER)[0]+MARKER+"\n\n## 附录：50条版本逐条审查表\n\n"+(HERE/"audit_table.md").read_text()
    REPORT.write_text(text)
    matches = list(re.finditer(r"(?m)^## (\d+)\. H(\d+)：([^\n]+)$", text))
    assert len(matches) == 8
    full = []
    for index, match in enumerate(matches):
        end = matches[index+1].start() if index+1 < len(matches) else text.index("\n## 11.")
        body = text[match.end():end]
        name = match[3]
        kind = re.search(r"类型：([^。]+)。", body)[1]
        clause = body.split(name+"：", 1)[1].split("\n\n据：", 1)[0]
        basis = body.split("\n\n据：", 1)[1].split("\n\n推导：", 1)[0]
        proof = body.split("\n\n推导：", 1)[1].split("\n\n状态：待审。", 1)[0]
        relation = body.split("\n\nrelation：", 1)[1].strip()
        assert clause.strip() and basis.strip() and len(proof) > 200 and relation
        assert body.count("状态：待审。") == 1
        full.append(dict(id="H"+match[2], name=name, kind=kind, text=clause.strip(),
                         basis=basis.strip(), derivation=proof.strip(), relation=relation, status="待审"))
    assert [(r["name"], r["kind"]) for r in full] == [(r[0], r[1]) for r in SHORT]
    write_json("candidates.json", full)
    short = [dict(zip(("name", "kind", "text", "basis", "derivation", "relation"), values)) for values in SHORT]
    reply = dict(report_path=str(REPORT), candidates=short,
                 summary="50条逐项核查，形成8条合并修订；完整证明、两读法逐步双编码及反例均已留档。",
                 status="待审")
    assert set(reply) == {"report_path", "candidates", "summary", "status"}
    for row in reply["candidates"]:
        assert set(row) == {"name", "kind", "text", "basis", "derivation", "relation"}
        assert row["kind"] in ("必要条件", "简化", "充分条件")
        assert all(isinstance(v, str) and v for v in row.values())
    write_json("reply.json", reply)
    audit = json.loads((HERE/"audit.json").read_text())
    assert len(audit["entries"]) == 50
    assert len({r["id"] for r in audit["entries"]}) == 50
    assert audit["counts"] == {"92": 35, "95M": 10, "95G": 2, "95T": 3}
    inputs = json.loads((HERE/"inputs.json").read_text())
    for row in inputs:
        data = Path(row["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row["sha256"], row["path"]
    rule = next(r for r in inputs if r["path"].endswith("《明日方舟：终末地》游戏规则.txt"))
    assert rule["lines"] == 115
    premise_counts = {}
    for name in ("求解约束.txt", "求解充分条件.txt"):
        source = next(r for r in inputs if r["path"].endswith("/"+name))
        lines = Path(source["path"]).read_text().splitlines()
        count = sum("：" in line and bool(line.split("：", 1)[1].strip())
                    and not line.lstrip().startswith("据：") for line in lines)
        premise_counts[name] = count
    assert premise_counts == {"求解约束.txt": 77, "求解充分条件.txt": 11}
    for p in HERE.glob("*.py"):
        ast.parse(p.read_text(), filename=str(p))
    values = {
        "polling": json.loads((HERE/"polling_results.json").read_text()),
        "plant": json.loads((HERE/"plant_results.json").read_text())["summary"],
        "bridge": json.loads((HERE/"bridge_results.json").read_text()),
        "cooldown": json.loads((HERE/"cooldown_results.json").read_text()),
        "combined": json.loads((HERE/"combined_results.json").read_text()),
        "arithmetic": json.loads((HERE/"arithmetic.json").read_text()),
    }
    assert values["polling"]["paired_step_states"] == 600*600+1200*220 == 624000
    assert values["plant"]["paired_step_states"] == 240*900+160*1200 == 408000
    assert values["bridge"]["paired_step_states"] == 2*sum(2**n for n in range(1, 9))*240 == 244800
    assert values["cooldown"]["paired_step_states"] == 8**3*2*160 == 163840
    assert values["combined"]["paired_step_states"] == 4*400 == 1600
    assert values["polling"]["largest_batch_all_interval_gap"] == 2
    assert values["cooldown"]["maximum_contents"] == values["cooldown"]["independent_40_step_count"] == 15
    assert values["plant"]["counterexample_min_phi2"]["geometric_clear"] == 171
    assert values["plant"]["counterexample_min_phi2"]["geometric_retain"] == 172
    assert values["arithmetic"]["constants"]["normal_start_offset"] == 176
    assert values["arithmetic"]["constants"]["arbitrary_start_offset"] == 150
    assert "在不含离线的连续段内" in full[0]["text"]
    for i in (2, 3, 4, 5):
        assert "在不含离线的连续段内" in full[i]["text"]
    assert "每个元件或非运输单位每步只判定一次" in full[1]["text"]
    assert "另一轴有无通道不限" in full[6]["text"]
    # The review text is an execution record, separate from the report's proof.
    review = """# 第101轮H组交付读者自审记录

日期：2026-10-02。状态：完成。

- 把报告作为独立文件复读：起点、步末、离线两种状态及全部8条前件在文内给出。
- 150与176按准备截面/正常完整步末区分，末次BB证明和跨段复合分别展开。
- 整批k件的跨离线2件界有独立分块证明，不借一般轮询公平；一件组反例与其前件区别明确。
- 活性支、满库存强支、额外满速支各自的前件均推到对应结论；没有由有限服务跳到满速。
- K首桥另一轴有通道已恢复；内部桥另一轴限制仍明示。来源记录不得妨碍前移，未默默清掉来源。
- 数值主批次与单列见证分开；接口放宽模型、局部几何轨迹和整厂证书没有混用。
- 35、10、2、3条逐条编号，旧35调试依赖由95M已有静态版本消除，未漏报。
- relation逐条指明正式、第92轮C/D、第95轮版本；8条状态均为待审。
- 复算脚本、相对链接、输入哈希、回复schema、文件大小和后缀由finalize.py检查。
"""
    (HERE/"reader_review.md").write_text(review)
    # Reserve final outputs before resolving report links.
    write_json("delivery_check.json", {})
    write_json("artifact_manifest.json", {})
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    for link in links:
        if "://" in link:
            continue
        target = REPORT.parent/link.split("#", 1)[0]
        assert target.exists(), (link, str(target))
    files = sorted(p for p in HERE.iterdir() if p.is_file())
    assert all(p.suffix in (".py", ".json", ".log", ".md", ".gz") for p in files)
    assert all(p.stat().st_size < 100_000_000 for p in files)
    assert not any(p.is_dir() for p in HERE.iterdir())
    check = dict(status="pass", report_path=str(REPORT), full_candidates=len(full),
                 audited_versions=50, premise_lines=115, premise_counts=premise_counts,
                 unchanged_input_hashes=len(inputs), report_links_checked=len(links),
                 scripts_syntax_checked=len(list(HERE.glob("*.py"))),
                 report_sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest(),
                 maximum_artifact_bytes=max(p.stat().st_size for p in files),
                 required_name_kind_and_status_consistent=True, reply_schema_valid=True,
                 main_paired_step_states={name: values[name]["paired_step_states"]
                                         for name in ("polling", "plant", "bridge", "cooldown", "combined")},
                 reader_review="reader_review.md")
    write_json("delivery_check.json", check)
    manifest = []
    for p in [REPORT]+sorted(p for p in HERE.iterdir() if p.is_file() and p.name != "artifact_manifest.json"):
        data = p.read_bytes()
        manifest.append(dict(path=str(p), bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    write_json("artifact_manifest.json", manifest)
    print(json.dumps(check, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
