import zipfile, os, hashlib, sys

zp = r"D:/追光/zmd/cc_context/review/phase1_2_spike_review_v28.zip"
pkg = os.path.join(os.environ["TEMP"], "v28_review_r7b", "_phase1_2_pkg_v28")

PFX = "_phase1_2_pkg_v28/"
z = zipfile.ZipFile(zp)
zip_names_raw = [n for n in z.namelist() if not n.endswith("/")]
zip_names = set(n[len(PFX):] if n.startswith(PFX) else n for n in zip_names_raw)
raw_of = {(n[len(PFX):] if n.startswith(PFX) else n): n for n in zip_names_raw}

disk_names = set()
for root, _, files in os.walk(pkg):
    for f in files:
        rel = os.path.relpath(os.path.join(root, f), pkg).replace("\\", "/")
        disk_names.add(rel)

zo = zip_names - disk_names
do = disk_names - zip_names
print("zip members:", len(zip_names), "disk files:", len(disk_names))
print("in zip not on disk:", len(zo))
for x in sorted(zo)[:30]:
    print("  ZIP-ONLY:", x)
print("on disk not in zip:", len(do))
for x in sorted(do)[:30]:
    print("  DISK-ONLY:", x)

# Spot-hash a few key files to confirm extraction == zip bytes
def h(b):
    return hashlib.sha256(b).hexdigest()[:16]

common = sorted(zip_names & disk_names)
mism = 0
for name in common:
    zb = z.read(raw_of[name])
    with open(os.path.join(pkg, name.replace("/", os.sep)), "rb") as fh:
        db = fh.read()
    if h(zb) != h(db):
        mism += 1
        if mism <= 10:
            print("  MISMATCH:", name)
print("byte mismatches among", len(common), "common files:", mism)
