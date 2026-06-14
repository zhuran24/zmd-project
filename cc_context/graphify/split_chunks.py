import json
import os
base = r"C:\claude pj\zmd_pj\cc_context\graphify\out"
out = json.load(open(base + r"\graphify-out\community_naming_input.json", encoding="utf-8"))
N = 8
os.makedirs(base + r"\chunks", exist_ok=True)
chunks = [[] for _ in range(N)]
# round-robin so big communities spread evenly across chunks
for i, c in enumerate(out):
    chunks[i % N].append(c)
for i, ch in enumerate(chunks):
    json.dump(ch, open(base + rf"\chunks\chunk_{i}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    chars = len(json.dumps(ch, ensure_ascii=False))
    print(f"chunk_{i}: {len(ch)} communities, ~{chars//4} tokens")
