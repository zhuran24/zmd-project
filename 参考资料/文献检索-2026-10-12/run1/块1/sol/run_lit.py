#!/usr/bin/env python3
"""Use the supplied lit.py with all cache/fulltext writes confined to this seat."""
from pathlib import Path
import sys

out = Path(__file__).resolve().parent
source = out.parents[2] / "lit.py"
code = source.read_text().replace('CACHE = os.path.join(ROOT, "cache")', 'CACHE = ' + repr(str(out / "lit-cache")))
ns = {"__name__": "lit_redirect", "__file__": str(source)}
exec(compile(code, str(source), "exec"), ns)

def safe_full(key):
    import hashlib, subprocess, requests
    w = None if key.lower().startswith("arxiv:") else ns["resolve"](key)
    urls = ["https://arxiv.org/pdf/" + key.split(":", 1)[1]] if w is None else []
    if w is not None:
        r = ns["_norm_oa"](w)
        if r["arxiv"]: urls.append("https://arxiv.org/pdf/" + r["arxiv"])
        if r["oa_url"]: urls.append(r["oa_url"])
    for url in urls:
        target = out / "lit-cache" / ("full_" + hashlib.sha1(url.encode()).hexdigest()[:16])
        if target.with_suffix(".txt").exists(): return str(target.with_suffix(".txt"))
        try:
            with requests.get(url, headers=ns["UA"], timeout=45, stream=True) as response:
                if response.status_code != 200: continue
                if int(response.headers.get("content-length", 0)) > 100_000_000: continue
                data = bytearray()
                for chunk in response.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > 100_000_000: raise ValueError("over 100 MB")
                if not data.startswith(b"%PDF"): continue
                target.with_suffix(".pdf").write_bytes(data)
            subprocess.run(["pdftotext", "-layout", str(target.with_suffix(".pdf")), str(target.with_suffix(".txt"))], check=True)
            return str(target.with_suffix(".txt"))
        except Exception as exc:
            print(str(exc), file=sys.stderr)
    raise SystemExit("没有拿到开放获取 PDF：" + " ".join(urls))

ns["full"] = safe_full
ns["main"]()
