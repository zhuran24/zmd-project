"""摘要新鲜度 gate (memtree 重构 P3 方案A, 2026-06-15)。

方案A 下索引行来自节点 frontmatter 的 `index_summary` (单一来源), description 仍供通道②
召回。两者都可能 vs 节点正文漂移。本 gate (gpt-red/gpt-eng 同源 forcing function) 抓它:

  记录每个节点基线 (body_sha, desc_sha, idx_sha)。复查时——
  - body 没变                         → OK
  - body 变了 + index_summary 也变了   → 视为编辑时已同步, OK
  - body 变了 + index_summary 没变      → **报红** "index_summary 可能 stale"
  - (description 同理单独标)

首跑 --seed 建基线 (无法回溯判旧 stale, 从当前态起算); 之后正文改而摘要没改才报。
**只读节点、不写节点、不碰 harness。** store 落 cc_context/knowledge/。

用法:
    python cc_context/tools/check_description_freshness.py          # 复查, 有 stale exit 1
    python cc_context/tools/check_description_freshness.py --seed   # 建立/重置基线
    python cc_context/tools/check_description_freshness.py --accept <name>   # 接受单节点当前态
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEM_DIR = ROOT / "cc_context" / "memory"
STORE = ROOT / "cc_context" / "knowledge" / "description_review.json"

_NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)
_DESC_RE = re.compile(r"^description:\s*(.+?)\s*$", re.MULTILINE)
_IDXSUM_RE = re.compile(r'^index_summary:\s*"((?:[^"\\]|\\.)*)"\s*$', re.MULTILINE)
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _sha(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def scan(mem_dir: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for md in sorted(mem_dir.glob("*.md")):
        if md.name == "MEMORY.md":
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = _FM_RE.match(text)
        front = fm.group(1) if fm else text
        body = text[fm.end():] if fm else ""
        nm = _NAME_RE.search(front)
        if not nm:
            continue
        dm = _DESC_RE.search(front)
        desc = dm.group(1).strip().strip('"').strip() if dm else ""
        im = _IDXSUM_RE.search(front)
        idx = im.group(1).replace('\\"', '"').replace("\\\\", "\\") if im else ""
        out[nm.group(1).strip()] = {
            "body_sha": _sha(body), "desc_sha": _sha(desc), "idx_sha": _sha(idx),
        }
    return out


def load_store() -> dict[str, dict]:
    if STORE.exists():
        return json.loads(STORE.read_text(encoding="utf-8"))
    return {}


def save_store(data: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8", newline="\n",
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--mem-dir", type=Path, default=DEFAULT_MEM_DIR)
    ap.add_argument("--seed", action="store_true", help="建立/重置基线 (接受全部当前态)")
    ap.add_argument("--accept", metavar="NAME", help="接受单个节点当前态")
    args = ap.parse_args()

    current = scan(args.mem_dir)

    if args.seed:
        save_store(current)
        print(f"基线已建立: {len(current)} 个节点 -> {STORE}")
        return 0

    store = load_store()
    if args.accept:
        if args.accept not in current:
            print(f"节点不存在: {args.accept}")
            return 1
        store[args.accept] = current[args.accept]
        save_store(store)
        print(f"已接受 {args.accept} 当前态为基线")
        return 0

    if not store:
        print("无基线: 先跑 --seed 建立基线")
        return 1

    stale, new_nodes = [], []
    for name, cur in current.items():
        rec = store.get(name)
        if rec is None:
            new_nodes.append(name)
            continue
        if cur["body_sha"] == rec["body_sha"]:
            continue  # 正文没变
        which = []
        if cur["idx_sha"] == rec.get("idx_sha"):
            which.append("index_summary")
        if cur["desc_sha"] == rec.get("desc_sha"):
            which.append("description")
        if which:  # 正文变了, 但这些字段没跟上
            stale.append((name, which))

    print(f"摘要新鲜度: {len(current)} 节点, stale {len(stale)}, 新增未基线 {len(new_nodes)}")
    for name, which in stale:
        print(f"  STALE {name}  ({'/'.join(which)} 没跟上正文更新 — 复查后 --accept {name})")
    for n in new_nodes:
        print(f"  NEW   {n}  (新节点未入基线 — --seed 或 --accept 收基线)")

    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
