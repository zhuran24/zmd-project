"""Validate 95T artifacts without touching any input or Git state."""
from pathlib import Path
from collections import Counter
from urllib.parse import unquote
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPORT = ROOT / "推导95T.md"


def main():
    text = REPORT.read_text()
    raw = json.loads((ROOT/"第92轮候选清单.json").read_text())
    audit = json.loads((HERE/"audit.json").read_text())
    cs = json.loads((HERE/"candidates.json").read_text())
    reply = json.loads((HERE/"reply.json").read_text())
    checks = json.loads((HERE/"checks.json").read_text())
    plant = json.loads((HERE/"plant_results.json").read_text())
    assert len(raw) == len(audit["items"]) == 35
    assert len(cs) == 3
    for i,(original,entry) in enumerate(zip(raw,audit["items"]),1):
        assert entry["id"] == i
        for field in ["group","name","kind","derive_report"]:
            assert original[field] == entry[field],(i,field)
        needle = f'| {i:02d} | {entry["group"]}／{entry["name"]} | {entry["classification"]} |'
        assert text.count(needle) == 1,(i,needle)
    counts = Counter(x["classification"] for x in audit["items"])
    assert counts == {"不受影响":25,"结论不变但证明要补":7,"结论变化":3}
    assert dict(counts) == audit["counts"]
    for c in cs:
        assert set(c) == {"name","kind","text","basis","derivation","relation"}
        assert all(isinstance(v,str) and v for v in c.values())
        assert c["kind"] in {"必要条件","简化","充分条件"}
        assert c["name"]+"："+c["text"] in text
        for field,label in [("basis","据："),("derivation","推导："),("relation","relation：")]:
            assert label+c[field] in text
    assert text.count("状态：待审。") == 3
    assert reply["report_path"] == str(REPORT)
    assert reply["candidates"] == cs
    assert isinstance(reply["summary"],str)
    assert set(reply) <= {"report_path","candidates","summary","error","status"}
    assert "{{" not in text
    headings = set(re.findall(r"^#{2,4}\s+(\d+(?:\.\d+)?)\b",text,re.M))
    references = set(re.findall(r"§(\d+(?:\.\d+)?)",text))
    # References to the old reports' sections are textual; all numeric section
    # references used here are also present as current headings.
    missing_sections = sorted(references-headings)
    assert not missing_sections, missing_sections
    links = []
    for target in re.findall(r"\]\(([^)]+)\)",text):
        if "://" in target or target.startswith("#"):
            continue
        dest = (REPORT.parent / unquote(target.split("#",1)[0])).resolve()
        exists = dest.exists() or dest == HERE/"delivery_check.json"
        assert exists,str(dest)
        links.append(str(dest))
    drift = []
    for item in checks["inputs"]:
        p = Path(item["path"])
        now=hashlib.sha256(p.read_bytes()).hexdigest()
        if now != item["sha256"]:
            drift.append({"path":str(p),"old":item["sha256"],"now":now})
    assert not drift,drift
    assert checks["arithmetic_encodings_equal"]
    assert [r["rates"] for r in checks["density"]] == [["0","1/5","1/5"],["1/10","1/10","1/5"]]
    assert plant["gate_diagnostic"]["full_states_compared"] == 9000
    assert plant["pure_belt_checks"]["full_states_compared"] == 76800
    assert all("poll_order" in x["state"] for x in plant["gate_diagnostic"]["snapshots"])
    artifacts=[]
    for p in sorted(HERE.iterdir()):
        assert p.is_file(),str(p)
        assert p.suffix in {".py",".json",".md",".log",".gz"},str(p)
        assert p.stat().st_size < 100*1024*1024,str(p)
        if p.name in {"delivery_check.json", "validate_delivery.log"}:
            continue
        artifacts.append({"name":p.name,"bytes":p.stat().st_size,
                          "sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    result={"status":"PASS","report":str(REPORT),"candidate_count":3,"audit_count":35,
            "counts":dict(counts),"report_sha256":hashlib.sha256(REPORT.read_bytes()).hexdigest(),
            "report_lines":len(text.splitlines()),"local_link_count":len(links),
            "section_references_valid":True,"input_drift":drift,
            "independent_numeric_checks_passed":True,
            "review_scope":"Migration classification preserves pending M/G/S corrections; gate diagnostic is not labeled a rule-certified counterexample.",
            "additional_materials_read":[{"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
                                         for p in [ROOT.parent/"第92-94轮"/"复核94F.md"]],
            "artifacts":artifacts}
    (HERE/"delivery_check.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ["status","audit_count","candidate_count","counts","report_lines","local_link_count","input_drift"]},ensure_ascii=False))


if __name__=="__main__":main()
