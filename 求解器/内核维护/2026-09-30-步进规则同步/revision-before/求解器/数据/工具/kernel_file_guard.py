#!/usr/bin/env python3
"""Content guard: files, modes, directories and symlinks; no symlink traversal."""
import argparse, hashlib, json, os, stat
from pathlib import Path

def digest(path):
    with open(path, "rb") as f: return hashlib.file_digest(f, "sha256").hexdigest()

def scan(root, excludes=()):
    root=Path(root).absolute(); rows={}
    def visit(p):
        rel=str(p.relative_to(root))
        if any(rel==e or rel.startswith(e+"/") for e in excludes): return
        s=p.lstat(); row={"mode":stat.S_IMODE(s.st_mode)}
        if stat.S_ISLNK(s.st_mode): row.update(kind="symlink",target=os.readlink(p),size=s.st_size)
        elif stat.S_ISDIR(s.st_mode):
            row.update(kind="directory")
            for c in sorted(p.iterdir()): visit(c)
        elif stat.S_ISREG(s.st_mode): row.update(kind="file",size=s.st_size,sha256=digest(p))
        else: raise ValueError("unsupported file: "+str(p))
        rows[rel]=row
    visit(root)
    return {"root":str(root),"excludes":list(excludes),"entries":rows}

def changes(before, after):
    a,b=before["entries"],after["entries"]
    return [{"path":p,"before":a.get(p),"after":b.get(p)} for p in sorted(a.keys()|b.keys()) if a.get(p)!=b.get(p)]

def write(path, data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="action",required=True)
    s=sub.add_parser("snapshot");s.add_argument("--root",required=True);s.add_argument("--out",required=True);s.add_argument("--exclude",action="append",default=[])
    v=sub.add_parser("verify");v.add_argument("--before",required=True);v.add_argument("--out",required=True)
    a=p.parse_args()
    if a.action=="snapshot": write(a.out,scan(a.root,a.exclude))
    else:
        before=json.loads(Path(a.before).read_text()); diff=changes(before,scan(before["root"],before["excludes"]));write(a.out,{"passed":not diff,"changes":diff});return bool(diff)
if __name__=="__main__": raise SystemExit(main())
