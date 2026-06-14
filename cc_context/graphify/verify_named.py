import json
import os
base = r"C:\claude pj\zmd_pj\cc_context\graphify\out"
allnamed = {}
missing = {}
problems = []
total_in = 0
for i in range(8):
    src = json.load(open(rf"{base}\chunks\chunk_{i}.json", encoding="utf-8"))
    src_ids = {c["id"] for c in src}
    total_in += len(src_ids)
    nf = rf"{base}\chunks\chunk_{i}_named.json"
    if not os.path.exists(nf):
        problems.append(f"chunk_{i}: NAMED FILE MISSING")
        missing[i] = sorted(src_ids)
        continue
    try:
        named = json.load(open(nf, encoding="utf-8"))
    except Exception as e:
        problems.append(f"chunk_{i}: JSON parse error {e}")
        missing[i] = sorted(src_ids)
        continue
    named_ids = {c["id"] for c in named if "id" in c}
    miss = src_ids - named_ids
    extra = named_ids - src_ids
    if miss:
        problems.append(f"chunk_{i}: src={len(src_ids)} named={len(named_ids)} MISSING {len(miss)}: {sorted(miss)}")
    if extra:
        problems.append(f"chunk_{i}: EXTRA {len(extra)}: {sorted(extra)}")
    if not miss and not extra:
        problems.append(f"chunk_{i}: OK ({len(named_ids)})")
    for c in named:
        if all(k in c for k in ("id", "name", "role")):
            allnamed[c["id"]] = c
    if miss:
        missing[i] = sorted(miss)

print("total input ids (size>=10):", total_in)
print("total named (unique, valid):", len(allnamed))
for p in problems:
    print(" ", p)

if missing:
    need = []
    for i, ids in missing.items():
        src = json.load(open(rf"{base}\chunks\chunk_{i}.json", encoding="utf-8"))
        byid = {c["id"]: c for c in src}
        for cid in ids:
            need.append(byid[cid])
    json.dump(need, open(rf"{base}\chunks\missing_to_name.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("=> wrote missing_to_name.json with", len(need), "communities to re-name")
json.dump(allnamed, open(rf"{base}\chunks\named_merged_partial.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
