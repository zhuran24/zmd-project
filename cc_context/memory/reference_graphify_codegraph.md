---
name: graphify-codegraph
index_summary: "src→确定性代码结构图 + Claude 补语义层, 新窗口先查图再 grep; .mcp.json 注册 mcp__graphify__*; graph.json gitignore 需刷新; 只读导航辅助不进 certified 证明路径."
description: "代码语义地图 / 跨窗口代码导航工具 graphify——把 src 跑成确定性代码结构图(知识图谱)+ Claude 补语义层,新窗口 'query before grep' 先查图再 grep。已注册 MCP server(mcp__graphify__*)。只读导航辅助,不进 certified 证明路径。"
metadata:
  node_type: memory
  type: reference
---

zmd 仓库有一套 **graphify 代码语义地图**子系统(2026-06-14 落地),给新窗口 / handoff 当"先看这个"的代码导航——**query before grep**:大改代码前先查图知道"去哪找",别一上来盲 grep。

## 位置 + 入口
- 全在 `cc_context/graphify/`(repo 内)。graphify 本体装在 `C:\Users\22957\.local\bin\`(`uv tool install graphifyy`)、**不在仓库**。
- **新窗口先读 `cc_context/graphify/SEMANTIC_MAP.md`**:god-nodes(系统承重墙)+ Benders 数据流主线 + 按模块社区地图 + "先读这 6 个"入口。
- 社区编号 ↔ 语义名映射在 `cc_context/graphify/community_semantics.json`(588 社区;graphify 输出只显示数字编号,拿编号回查这里)。

## 怎么用(两条路)
1. **MCP(最省事)**:仓库根 `.mcp.json` 已注册 `graphify` server → 直接调 `mcp__graphify__query_graph` / `get_neighbors` / `shortest_path` / `get_node` / `god_nodes`。
2. **CLI**:`graphify.exe explain <符号> --graph <graph.json>` / `path <A> <B>` / `affected <X>`。`graph.json` 在 `out/graphify-out/graph.json`(**gitignore 本地产物**,clone 后需先刷新或让 owner 提供)。
- 边三档可信度:`EXTRACTED`(AST 铁定) / `VERIFIED`(import 解析坐实) / `INFERRED`(仅 9 条、同名巧合存疑)。

## 刷新(代码大改后,全程离线零 token)
完整 runbook 在 `cc_context/graphify/README.md` 第 38-62 行(robocopy src→镜像 → AST extract → 通用名降噪 → Leiden 聚类 → verify_inferred 坐实边 → 社区命名 workflow → finalize)。当前图绑定 src @ HEAD `26e4543`(2026-06-14 生成);代码改了图会过时,按 runbook 重跑。

## 定位(重要)
**只读导航辅助,不进 certified 证明路径**。社区划分是启发式,整图只是"帮你先知道去哪找",**不是真相源**——真相源仍是 `rules/canonical_rules.json` + proof 工件 + 测试。别拿它当依据。项目架构 / 求解器全貌见身份根 [[endfield-solver]];记录工具入口的约定见 [[record-tool-entry-points]]。
