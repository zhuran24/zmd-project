import os, re, sys

pkg = os.path.join(os.environ["TEMP"], "v28_review_r7b", "_phase1_2_pkg_v28")

# Secret / identity patterns
patterns = {
    "GEMINI_GOOGLE_KEY": re.compile(r"AIzaSy[0-9A-Za-z_\-]{20,}"),
    "OPENAI_KEY": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "OPENAI_PROJ_KEY": re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"),
    "ANTHROPIC_KEY": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "GH_TOKEN": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "AWS_KEY": re.compile(r"AKIA[0-9A-Z]{16}"),
    "PRIVATE_KEY": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    "GENERIC_BEARER": re.compile(r"[Bb]earer\s+[A-Za-z0-9_\-\.=]{20,}"),
    "SLACK": re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),
    # identity
    "ZHURAN24": re.compile(r"zhuran24"),
    "LENOVO_USER": re.compile(r"[Uu]sers[\\/]+Lenovo"),
    "EMAIL_REAL": re.compile(r"RositaTodd|chef\.net"),
    "WIN_REPO_ABS": re.compile(r"D:\\\\?追光|D:[\\/]追光"),
    "ZHURAN_HOME": re.compile(r"/home/zhuran24|\\Users\\zhuran"),
}

hits = {k: [] for k in patterns}
scanned = 0
skipped_bin = 0
for root, _, files in os.walk(pkg):
    for f in files:
        fp = os.path.join(root, f)
        rel = os.path.relpath(fp, pkg).replace("\\", "/")
        # skip obvious binary by extension
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".zip", ".7z", ".gz", ".woff", ".woff2", ".ttf")):
            skipped_bin += 1
            continue
        try:
            with open(fp, "r", encoding="utf-8", errors="strict") as fh:
                lines = fh.readlines()
        except (UnicodeDecodeError, PermissionError):
            skipped_bin += 1
            continue
        scanned += 1
        for i, line in enumerate(lines, 1):
            for name, pat in patterns.items():
                if pat.search(line):
                    snippet = line.strip()[:200]
                    hits[name].append((rel, i, snippet))

print(f"scanned text files: {scanned}, skipped binary/undecodable: {skipped_bin}")
for name, lst in hits.items():
    print(f"\n### {name}: {len(lst)} hit(s)")
    for rel, i, snip in lst[:40]:
        print(f"  {rel}:{i}: {snip}")
