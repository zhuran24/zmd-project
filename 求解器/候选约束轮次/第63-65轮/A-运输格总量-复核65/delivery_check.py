#!/usr/bin/env python3
"""Check delivery evidence and current source identity without writing outside OUT."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
REPORT = OUT.with_suffix(".md")


def read(name):
    return json.loads((OUT/name).read_text())


def main():
    snapshot = read("inputs_snapshot.json")
    for name,entry in snapshot["materials"].items():
        assert hashlib.sha256(entry["text"].encode()).hexdigest()==entry["sha256"]
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==entry["sha256"], name
    geometry=read("geometry_all.json")
    expected={(a,b) for a in range(0,70,3) for b in range(0,70,3) if min(a,b)==0}
    assert len(geometry["cases"])==47
    assert {(c["gap_left"],c["gap_bottom"]) for c in geometry["cases"]}==expected
    assert all(c["budget"]==7 and c["status"]=="INFEASIBLE" for c in geometry["cases"])
    assert read("independent_witness.json")["witness"]["cost"]==8
    accounts=read("accounts.json")
    assert accounts["new_lower_bound"]["fraction"]=="6273/20"
    assert accounts["new_slots"]==314
    assert len(accounts["cases"])==24
    assert all(not c["excluded_by_this_account"] for c in accounts["cases"])
    for key in ("author_witness_check","independent_witness_check"):
        assert accounts[key]["cost"]==8 and len(accounts[key]["rectangle_checks"])==8
        assert all(c["body_overlap"]==0 for c in accounts[key]["rectangle_checks"])
    body=REPORT.read_text()
    assert "verdict：**未否证**" in body and "revised_text：`\"\"`" in body
    assert str(REPORT) in body
    links=[]
    for target in re.findall(r"\]\(([^)]+)\)",body):
        assert not target.startswith(("http:","https:")), target
        resolved=REPORT.parent/target
        assert resolved.exists(),target
        links.append(target)
    verdict={"report_path":str(REPORT),"verdicts":[{
        "name":"无协议储存箱的运输过站下限（修正箱体过站的无箱分支）",
        "verdict":"未否证",
        "reason":"现行规则支持分数流转整数匹配和运输容量换算；独立模型对全部47种边带排布证明额外费用不可能≤7，有理数复算得到V≥313.65、T+b≥314、2T≥314+D+M+L。费用8的放宽匹配经独立坐标检查覆盖八个指定空矩形，24个位置/P组合均未被本项容量账排除。",
        "revised_text":""}]}
    (OUT/"verdict.json").write_text(json.dumps(verdict,ensure_ascii=False,indent=2)+"\n")
    artifacts={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(OUT.iterdir()) if p.is_file() and p.name!="delivery_check.json"}
    artifacts[str(REPORT.relative_to(ROOT))]=hashlib.sha256(REPORT.read_bytes()).hexdigest()
    result={"checked_at":datetime.now(timezone.utc).isoformat(),"result":"PASS",
            "current_inputs_equal_snapshot":True,"geometry_cases":47,"branch_cases":24,
            "reference_targets":links,"artifact_sha256":artifacts}
    (OUT/"delivery_check.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k not in ("artifact_sha256","reference_targets")},ensure_ascii=False))


if __name__=="__main__":
    main()
