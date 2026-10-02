"""Read-only validation of inputs/report; manifest writes stay in this directory."""
from pathlib import Path
import json,re,hashlib,ast,datetime

here=Path(__file__).resolve().parent;base=here.parent
report=base/"复核99S2.md"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
text=report.read_text();links=re.findall(r"\]\(([^)]+)\)",text)
missing=[x for x in links if not (report.parent/x).exists()]
assert not missing,missing
verdict=json.loads(here.joinpath("verdict.json").read_text())
assert verdict["report_path"]==str(report)
assert len(verdict["verdicts"])==1 and verdict["verdicts"][0]["verdict"]=="未否证"
assert not verdict["verdicts"][0]["revised_text"]
old=json.loads(here.joinpath("inputs.json").read_text())
changed=[p for p,v in old.items() if sha(base.parent/p)!=v]
assert not changed,changed
for p in here.glob("*.py"):ast.parse(p.read_text(),filename=str(p))
for p in here.glob("*.json"):json.loads(p.read_text())
assert json.loads(here.joinpath("validation.json").read_text())["status"]=="pass"
result={"status":"pass","checked_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "report_sha256":sha(report),"report_links_checked":len(links),
        "input_files_unchanged":len(old),"verdict_count":1,
        "report_reader_audit":"reader_audit.md","other_review_reports_read":False,
        "max_parallel_single_thread_processes":3,
        "write_scope":[str(report),str(here)]}
here.joinpath("delivery_check.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
files=[report]+sorted(p for p in here.iterdir() if p.is_file() and p.name!="artifact_manifest.json")
manifest={str(p.relative_to(base)):sha(p) for p in files}
here.joinpath("artifact_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(result,ensure_ascii=False))
