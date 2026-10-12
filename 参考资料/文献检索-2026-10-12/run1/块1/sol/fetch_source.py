#!/usr/bin/env python3
"""Bounded primary-source acquisition; records URL and file sha256."""
from pathlib import Path
import hashlib, json, requests, subprocess, sys
out = Path(__file__).resolve().parent
name, url = sys.argv[1:3]
with requests.get(url, timeout=45, stream=True, headers={"User-Agent":"literature-research/1.0"}) as r:
    r.raise_for_status()
    if int(r.headers.get("content-length", 0)) > 100_000_000: raise SystemExit("over 100MB")
    data = bytearray()
    for part in r.iter_content(65536):
        data.extend(part)
        if len(data) > 100_000_000: raise SystemExit("over 100MB")
target = out / "sources"
target.mkdir(exist_ok=True)
pdf = data.startswith(b"%PDF")
path = target / (name + (".pdf" if pdf else ".html"))
path.write_bytes(data)
if pdf:
    subprocess.run(["pdftotext", "-layout", str(path), str(target / (name + ".txt"))],check=True)
with (out / "全文来源.jsonl").open("a") as f:
    f.write(json.dumps({"name":name,"url":url,"file":str(path.relative_to(out)),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()},ensure_ascii=False)+"\n")
print(path)
