"""description 新鲜度 gate (memtree 重构 P3 极简, 2026-06-15)。

极简设计下 MEMORY.md 索引摘要 = 节点 description 截断生成 (无独立 index_summary 字段),
所以唯一残留的漂移面 = description 本身 vs 节点正文。本 gate 就抓它 (gpt-red/gpt-eng 同源
的 forcing function):

  记录每个节点的基线 (body_sha, desc_sha)。复查时——
  - body 没变            → OK
  - body 变了 + desc 也变 → 视为编辑时已同步更新 desc, OK, 刷新基线
  - body 变了 + desc 没变 → **报红** "description may be stale (正文更新了摘要没跟上)"

首次跑 --seed 建立基线 (无法回溯判旧 stale, 从当前态起算); 之后正文改而摘要没改才报。
**只读节点、不写节点、不碰 harness。** store 落 cc_context/knowledge/ (control layer)。

用法:
    python cc_context/tools/check_description_freshness.py          # 复查, 有 stale exit 1
    python cc_context/tools/check_description_freshness.py --seed   # 建立/重置基线 (写 store)
    python cc_context/tools/check_description_freshness.py --accept <name>   # 接受单个节点当前态
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
        out[nm.group(1).strip()] = {"body_sha": _sha(body), "desc_sha": _sha(desc)}
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
        if cur["desc_sha"] != rec["desc_sha"]:
            continue  # 正文与摘要同变 = 编辑时已更新摘要
        stale.append(name)  # 正文变了, 摘要没动 = 疑似 stale

    print(f"description 新鲜度: {len(current)} 节点, stale {len(stale)}, 新增未基线 {len(new_nodes)}")
    for n in stale:
        print(f"  STALE {n}  (正文更新了, description 没跟上 — 复查后 --accept {n})")
    for n in new_nodes:
        print(f"  NEW   {n}  (新节点未入基线 — --seed 或 --accept 收基线)")

    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
