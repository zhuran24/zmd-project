# cc_context/graphify — 代码语义地图（跨窗口 handoff 导航）

把 **graphify**（代码→知识图谱工具）跑出的**确定性代码结构图**当骨架，由 Claude 补上它纯离线时缺的**语义层**，给新窗口/handoff 当"先看这个"的代码导航。

> **定位**：只读导航辅助，**不进 certified 证明路径**。社区划分是启发式；边绝大多数已坐实，但整图仍只是"帮你先知道去哪找"，不是真相源——真相源仍是 `rules/canonical_rules.json` + proof 工件 + 测试。
>
> graphify 本体装在本机 `C:\Users\22957\.local\bin\`（`uv tool install graphifyy`），**不在本仓库**。

## 先看什么

- **`SEMANTIC_MAP.md`** ← 新窗口先读这个。god-nodes（系统承重墙）+ Benders 数据流主线 + 按模块的社区地图 + "先读这 6 个"入口。
- **`community_semantics.json`** ← 588 个社区的语义名 + 职责（graphify 输出只显示社区**数字编号**，拿编号回查这里）。

## 怎么查（query before grep）

graph.json 在 `out/graphify-out/graph.json`（gitignore，本地产物；clone 后需跑一次刷新或让 owner 提供）。

```powershell
$gfx = "C:\Users\22957\.local\bin\graphify.exe"
$g   = "C:\claude pj\zmd_pj\cc_context\graphify\out\graphify-out\graph.json"
& $gfx explain "MasterPlacementModel" --graph $g          # 某符号在哪、连到谁
& $gfx path "run_outer_search" "MasterPlacementModel" --graph $g   # 调用链
```

边标三档可信度：`EXTRACTED`(AST 铁定) / `VERIFIED`(import 解析坐实) / `INFERRED`(仅剩 9 条、graphify 同名巧合存疑)。

**或用 MCP**：仓库根 `.mcp.json` 已注册 `graphify` server，新窗口可直接调 `query_graph` / `get_neighbors` / `shortest_path` / `get_node`。

## 目录结构

| 路径 | 进 git? | 说明 |
|---|---|---|
| `*.py` | ✅ | 刷新脚本（源码） |
| `SEMANTIC_MAP.md` | ✅ | 手写成品（新窗口先读） |
| `community_semantics.json` | ✅ | 588 社区语义档快照 |
| `out/` | ❌ gitignore | 工作产物：graph.json、src_mirror 镜像、chunks 命名中间件 |

## 怎么刷新（代码大改后，全程离线零 token）

```powershell
$P   = "C:\claude pj\zmd_pj\cc_context\graphify"
$gfx = "C:\Users\22957\.local\bin\graphify.exe"
# 1. 只含 .py 的镜像（排除 doc，否则 graphify 要 LLM key 报错）
robocopy "C:\claude pj\zmd_pj\src" "$P\out\src_mirror" *.py /S /MIR /NFL /NDL /NJH /NJS
# 2. 纯 AST 抽取（全离线）
& $gfx extract "$P\out\src_mirror" --out "$P\out"
# 3. 通用名降噪（删 ValueError/Any/Path 等"名字撞名字"噪声节点+边）
Remove-Item "$P\out\graphify-out\graph.json.raw" -ErrorAction SilentlyContinue
python "$P\clean_inferred_noise.py" --apply
# 4. 本地 Leiden 聚类 + 报告
& $gfx cluster-only "$P\out" --no-label --no-viz
# 5. 把"猜的"(INFERRED)边用 import 解析坐实成 VERIFIED（确定性，每次自动重算）
python "$P\verify_inferred.py" --apply
# 6. 社区语义命名（Claude 介入）：抽摘要 -> 分片 -> 命名 workflow -> 校验 -> 落地
python "$P\extract_naming_input.py"; python "$P\split_chunks.py"
#    >>> Claude 跑 community-semantic-naming workflow：8 个 agent 并行命名
#        out/chunks/chunk_*.json -> 写出 chunk_*_named.json
python "$P\verify_named.py"; python "$P\finalize_semantics.py"
# 7. 更新进 git 的成品快照
Copy-Item "$P\out\graphify-out\community_semantics.json" "$P\community_semantics.json" -Force
#    SEMANTIC_MAP.md 是手写成品，按新的 god-nodes / top 社区手动更新
```

## 各脚本职责

- `clean_inferred_noise.py` — 删 Python 内置/typing 通用名节点+边（graphify "名字撞名字"的噪声源，如 `raise ValueError` 被当成调用）。从 `graph.json.raw` 出发，幂等。
- `verify_inferred.py` — 用 `ast` import 解析把"猜的"(INFERRED)边坐实成 VERIFIED：A 文件确实 import 了 B 且来源模块对得上 → 确认。**确定性**，每次刷新自动重算、跟着代码变化自动更新。
- `extract_naming_input.py` / `split_chunks.py` — 给社区命名准备结构化输入 + 分 8 片。
- `verify_named.py` — 核对命名覆盖（agent 自报数量不可信，必须查落盘 id 集合）。
- `finalize_semantics.py` — 合并 LLM 命名 + 细碎社区目录兜底，写 `community_semantics.json` + 回填 graphify 标签。
- `group_for_map.py` — 按顶层模块聚合社区，给手写 `SEMANTIC_MAP.md` 当素材。

## 换机注意

脚本里工作区路径硬编码为 `C:\claude pj\zmd_pj\cc_context\graphify\out`，graphify.exe 路径为 `C:\Users\22957\.local\bin\`。换机时改这两处（脚本顶部 + 本 README + `.mcp.json`）。
