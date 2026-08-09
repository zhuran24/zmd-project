import os, collections
pkg = os.path.join(os.environ["TEMP"], "v28_review_r7b", "_phase1_2_pkg_v28")
c = collections.Counter()
for root, _, files in os.walk(pkg):
    rel = os.path.relpath(root, pkg).replace("\\", "/")
    parts = rel.split("/")
    if rel == ".":
        top = "<pkg-root>"
    elif parts[0] == "project":
        top = "project/" + (parts[1] if len(parts) > 1 else "<root>")
    else:
        top = parts[0]
    c[top] += len(files)
for k in sorted(c):
    print(f"  {c[k]:5d}  {k}")
print("  TOTAL:", sum(c.values()))
