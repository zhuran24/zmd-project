import os, re, glob

pkg = os.path.join(os.environ["TEMP"], "v28_review_r7b", "_phase1_2_pkg_v28")
tdir = os.path.join(pkg, "project", "docs", "research", "agent_transcripts")

email_full = re.compile(r"RositaToddcpj@chef\.net")
email_domain = re.compile(r"chef\.net")
gkey = re.compile(r"AIzaSy[0-9A-Za-z_\-]{10,}")
home = re.compile(r"/home/zhuran24|Users[\\/]Lenovo|zhuran24|D:[\\/]?追光")
emailguard = re.compile(r"RositaTodd")

files = sorted(glob.glob(os.path.join(tdir, "*")))
print(f"transcript files: {len(files)}")
for fp in files:
    rel = os.path.basename(fp)
    try:
        with open(fp, encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
    except Exception as e:
        print(rel, "READERR", e); continue
    for label, pat in [("FULL_EMAIL", email_full), ("EMAIL_DOMAIN", email_domain),
                       ("GKEY", gkey), ("HOME_OR_USER", home), ("EMAIL_NAME", emailguard)]:
        ms = list(pat.finditer(txt))
        if ms:
            print(f"\n{rel}  [{label}] x{len(ms)}")
            for m in ms[:5]:
                s=max(0,m.start()-70); e=min(len(txt),m.end()+70)
                ctx = txt[s:e].replace("\n", " ")
                print("   ...", ctx, "...")
