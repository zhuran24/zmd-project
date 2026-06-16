import os, re

pkg = os.path.join(os.environ["TEMP"], "v28_review_r7b", "_phase1_2_pkg_v28")

# Residual dev-local path patterns
checks = {
    # disclosed-acceptable: forward-slash phase3b workspace, no identity
    "FWD_PHASE3B": re.compile(r"[A-Za-z]:/phase3b_workspaces"),
    # NOT acceptable: backslash drive abs path (Windows repo-style), real identity
    "BACKSLASH_DRIVE": re.compile(r"[A-Za-z]:\\[^\s\"']"),
    "ZHURAN": re.compile(r"zhuran"),
    "LENOVO": re.compile(r"Lenovo"),
    "ZHUIGUANG": re.compile(r"追光"),
    "HOME_ZHURAN": re.compile(r"/home/zhuran"),
    "REAL_USERNAME_WIN": re.compile(r"Users[\\/](?!devuser|<)[A-Za-z0-9]+"),
}
hits = {k: [] for k in checks}
for root, _, files in os.walk(pkg):
    for f in files:
        if f.lower().endswith((".png",".jpg",".jpeg",".gif",".pdf",".ico",".zip",".7z",".gz",".woff",".woff2",".ttf")):
            continue
        fp = os.path.join(root, f)
        rel = os.path.relpath(fp, pkg).replace("\\","/")
        try:
            with open(fp, encoding="utf-8", errors="strict") as fh:
                for i, line in enumerate(fh, 1):
                    for name, pat in checks.items():
                        if pat.search(line):
                            hits[name].append((rel, i, line.strip()[:160]))
        except (UnicodeDecodeError, PermissionError):
            continue

for name, lst in hits.items():
    print(f"\n### {name}: {len(lst)} hit(s)")
    # collapse by file for the noisy ones
    byfile = {}
    for rel,i,s in lst:
        byfile.setdefault(rel, []).append((i,s))
    for rel in sorted(byfile)[:25]:
        ex = byfile[rel][0]
        print(f"  {rel}  (x{len(byfile[rel])})  e.g. L{ex[0]}: {ex[1]}")
    if len(byfile) > 25:
        print(f"  ... +{len(byfile)-25} more files")
