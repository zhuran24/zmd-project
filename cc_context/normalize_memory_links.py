# -*- coding: utf-8 -*-
"""
Fail-closed memory name/link normalizer.

Contract: canonical link slug for every *.md file =
  filename with {feedback_,project_,reference_,handoff_,index_} prefix stripped,
  drop .md, replace _ with -.

Steps:
  1. Build canonical slug per file.
  2. FAIL-CLOSED guard (a): abort if two files map to same canonical slug.
  3. Build resolver alias set per file: {canonical, with-each-prefix, current frontmatter name (if ascii slug)}.
  4. Count before: total [[links]], resolved, unresolved (strict by current frontmatter name).
  5. Rewrite: set each file frontmatter name: -> canonical slug; rewrite every [[link]] -> canonical slug it resolves to.
  6. Count after (resolved by canonical name set).
  7. FAIL-CLOSED guard (b): resolved must strictly increase AND unresolved strictly decrease, else abort (write nothing).

--apply to actually write; default is dry-run.
"""
import re, sys, os, io

MEM = r"C:\Users\Lenovo\.claude\projects\D-----zmd\memory"
PREFIXES = ("feedback_", "project_", "reference_", "handoff_", "index_")
APPLY = "--apply" in sys.argv

def canon_from_filename(fn):
    base = fn[:-3] if fn.endswith(".md") else fn
    for p in PREFIXES:
        if base.startswith(p):
            base = base[len(p):]
            break
    return base.replace("_", "-")

def read(fn):
    with io.open(os.path.join(MEM, fn), "r", encoding="utf-8") as f:
        return f.read()

def get_frontmatter_name(text):
    # name: appears in first frontmatter block
    m = re.search(r'(?m)^name:[ \t]*(.+?)[ \t]*$', text)
    return m.group(1) if m else None

def is_ascii_slug(s):
    return s is not None and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.\-]*', s) is not None

files = [f for f in os.listdir(MEM) if f.endswith(".md") and f != "MEMORY.md"]
files.sort()

# 1. canonical slug per file
canon = {f: canon_from_filename(f) for f in files}

# 2. guard (a): collision check
rev = {}
for f, c in canon.items():
    rev.setdefault(c, []).append(f)
collisions = {c: fs for c, fs in rev.items() if len(fs) > 1}
if collisions:
    print("ABORT (guard a): canonical slug collisions:")
    for c, fs in collisions.items():
        print("  ", c, "<-", fs)
    sys.exit(2)

# current frontmatter names (the strict-match key set BEFORE)
cur_name = {}
for f in files:
    n = get_frontmatter_name(read(f))
    cur_name[f] = n

# 3. resolver alias -> canonical (for rewriting links).
# Accept: canonical, each prefix+canonical, and current ascii frontmatter name.
alias_to_canon = {}
def add_alias(a, c):
    a = a.strip().lower()
    if a:
        alias_to_canon.setdefault(a, c)
for f in files:
    c = canon[f]
    add_alias(c, c)
    for p in PREFIXES:
        add_alias(p.rstrip("_") + "-" + c, c)
    n = cur_name[f]
    if is_ascii_slug(n):
        add_alias(n.lower(), c)
# MEMORY.md target slug fallback handled via canonical only

LINK_RE = re.compile(r'\[\[([^\]\|]+?)\]\]')

# BEFORE counts: strict match against current frontmatter name set (ascii lowered)
strict_names = set()
for f in files:
    n = cur_name[f]
    if n is not None:
        strict_names.add(n.strip().lower())

all_texts = {f: read(f) for f in files}
# include MEMORY.md links too for completeness of the link-graph metric
mem_md = None
mem_path = os.path.join(MEM, "MEMORY.md")
if os.path.exists(mem_path):
    with io.open(mem_path, "r", encoding="utf-8") as fp:
        mem_md = fp.read()

def count_links(texts_dict, name_set, extra_text=None):
    total = resolved = 0
    unresolved_samples = {}
    items = list(texts_dict.items())
    if extra_text is not None:
        items = items + [("MEMORY.md", extra_text)]
    for f, t in items:
        for m in LINK_RE.finditer(t):
            tok = m.group(1).strip().lower()
            total += 1
            if tok in name_set:
                resolved += 1
            else:
                unresolved_samples[tok] = unresolved_samples.get(tok, 0) + 1
    return total, resolved, total - resolved, unresolved_samples

b_total, b_res, b_unres, b_samples = count_links(all_texts, strict_names, mem_md)

# canonical name set AFTER
canon_names = set(canon.values())

# 5. rewrite link tokens -> canonical (only if alias resolves); also rewrite frontmatter name
def rewrite_text(t, is_mem=False):
    def repl(m):
        tok = m.group(1).strip()
        key = tok.lower()
        c = alias_to_canon.get(key)
        if c is not None:
            return "[[" + c + "]]"
        return m.group(0)  # leave unresolved untouched
    return LINK_RE.sub(repl, t)

new_texts = {}
for f in files:
    t = all_texts[f]
    # rewrite frontmatter name -> canonical (first occurrence in frontmatter only)
    c = canon[f]
    def name_repl(m, c=c):
        return "name: " + c
    t2 = re.sub(r'(?m)^name:[ \t]*.+?[ \t]*$', name_repl, t, count=1)
    t2 = rewrite_text(t2)
    new_texts[f] = t2
new_mem = rewrite_text(mem_md, is_mem=True) if mem_md is not None else None

# 6. AFTER counts (resolve against canonical name set)
a_total, a_res, a_unres, a_samples = count_links(new_texts, canon_names, new_mem)

print("=== BEFORE (strict current name match) ===")
print("total links:", b_total, "resolved:", b_res, "unresolved:", b_unres)
print("=== AFTER (canonical name match) ===")
print("total links:", a_total, "resolved:", a_res, "unresolved:", a_unres)
print("=== top remaining unresolved tokens (after) ===")
for tok, n in sorted(a_samples.items(), key=lambda x: -x[1])[:40]:
    print("   ", n, tok)

# 7. guard (b): resolved strictly increases, unresolved strictly decreases
if not (a_res > b_res and a_unres < b_unres):
    print("ABORT (guard b): no strict improvement (resolved %d->%d, unresolved %d->%d)" % (b_res, a_res, b_unres, a_unres))
    sys.exit(3)

if APPLY:
    for f in files:
        if new_texts[f] != all_texts[f]:
            with io.open(os.path.join(MEM, f), "w", encoding="utf-8", newline="\n") as fp:
                fp.write(new_texts[f])
    if new_mem is not None and new_mem != mem_md:
        with io.open(mem_path, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(new_mem)
    print("APPLIED.")
else:
    print("DRY-RUN (pass --apply to write). guard a/b PASSED.")
