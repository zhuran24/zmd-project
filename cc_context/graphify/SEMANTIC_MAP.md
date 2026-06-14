# SEMANTIC_MAP — Endfield Exact Solver 语义架构地图

> **这是什么**：把 graphify 跑出的**确定性代码结构图**（src/ 814 文件 → 原始 12556 节点 / 34570 边 → **通用名降噪后 11684 节点 / 27377 边**、588 社区，纯 tree-sitter AST，零联网零 token；**边可信度 = 22775 EXTRACTED + 4593 VERIFIED + 仅 9 INFERRED**）当骨架，由 Claude 补上 graphify 纯离线时缺的**语义层**（588 个社区全部语义命名 + god-node 解读 + Benders 数据流串讲 + 新窗口入口）。
>
> **定位（重要）**：只读导航辅助，**不进 certified 证明路径**。社区划分是启发式；边绝大多数已坐实（EXTRACTED/VERIFIED），但**整图仍只是导航辅助、不是真相源**——真相源仍是 `rules/canonical_rules.json` / proof 工件 / 测试。看本图是为了"先知道去哪找"，不是"拿它当依据"。
>
> **绑定快照**：src/ 工作树 @ HEAD `26e4543`（2026-06-14 生成）。⚠️ 代码改动后本图会过时——graphify 自带的 `built_at_commit` 字段在镜像模式下**不准**（探测到的 `ad073d60` 是错的，镜像无 `.git`），**以本行 HEAD 为准**。刷新办法见文末。

---

## 30 秒上手（新窗口"query before grep"）

```powershell
$gfx = "C:\Users\22957\.local\bin\graphify.exe"
$g   = "C:\claude pj\zmd_pj\cc_context\graphify\out\graphify-out\graph.json"

# 某符号在哪、连到谁（边标三档：EXTRACTED=AST 铁定 / VERIFIED=import 坐实 / INFERRED=仍存疑）
& $gfx explain "MasterPlacementModel" --graph $g

# 两个符号之间怎么走到（调用链）
& $gfx path "run_outer_search" "MasterPlacementModel" --graph $g

# 谁会被 X 影响（反向依赖）—— 注意符号名要唯一，重名会报 ambiguous
& $gfx affected "BState" --graph $g
```

- 社区编号 ↔ 语义名映射在 `community_semantics.json`（`{id: {name, role, size, dominant_dir, top_symbols}}`）。
- explain/query/MCP 输出只显示社区**数字编号**（如 `community=18`），不显示语义名——拿编号回查 `community_semantics.json` 或本文件。

---

## 边的可信度（三档，越高越可信）

| 标签 | 数量 | 含义 |
|---|---|---|
| `EXTRACTED` | 22775 | graphify AST 铁定的结构边（文件包含符号、类的方法、定义）——100% 确定 |
| `VERIFIED` | 4593 | 原本"猜的"(INFERRED)，已用 Python `ast` 的 import 解析坐实（A 确实 import 了 B 且来源模块对得上，排除同名巧合） |
| `INFERRED` | 9 | 坐实不了的——全是 graphify 同名巧合误连（如测试里 `.validate()` 被连错），保留存疑 |

> **怎么把"猜"变"确认"**：graphify 缺 import 解析、只靠"名字相同就连"，所以不敢打包票。`verify_inferred.py` 补上这步逐条核实——**99.8% 坐实**（4593/4602），剩 9 条正是 graphify 连错的。
> **怎么在刷新中保持**：核实是**确定性**的（同代码必出同结果），已写进刷新流程每次自动重跑——确认结果自动重现，还跟着代码变化自动更新（代码删了某调用，下次自动降回存疑），比"存一份确认清单去套"更可靠（清单会过时）。

---

## God Nodes — 系统承重墙（连接度 Top 10，通用名降噪后）

改动这些会牵动全局，新窗口优先理解：

| 符号 | 边数 | 它是什么 |
|---|---|---|
| `now_iso()` | 172 | 时间戳工具，**渗透全项目**（介数中心性 0.39，最大跨社区桥）——遥测/台账无处不在 |
| `BState` | 171 | Benders 求解状态容器，cut/blocked-cells/ghost-rect 都挂它（c1） |
| `MasterPlacementModel` | 169 | CP-SAT 放置 master，整个 Benders 的核心建模对象（c7） |
| `Cut` | 155 | cut 基类，9 个 family 共同抽象（c1） |
| `CoordinateExactMasterDelegate` | 127 | ghost rectangle 坐标精确 master 委托（c5） |
| `OracleCert` | 116 | oracle 证书对象，cut 合法性凭据（c12） |
| `run_outer_search()` | 102 | 外层候选循环入口（c32） |
| `atomic_write_json()` | 83 | 原子落盘工具，所有持久化的公共底座 |
| `Cell` | 82 | 网格单元基本几何类型 |
| `CutScope` | 75 | cut 作用域，within-instance 提升边界 |

> `now_iso()` / `atomic_write_json()` 高连接 = **基础设施工具散布各处**（不是设计耦合）；其余 8 个才是真正的领域承重抽象。
>
> **已做通用名降噪**：graphify 纯 AST 靠"名字相同就连线"的启发式，会把 `raise ValueError` 误当成"调用 ValueError"——`ValueError` 一个就被瞎连 366 条。已用 Python 自己的 `builtins`+`typing` 名单当停用词，删掉 872 个通用名节点（`Path`×516 / `Any`×303 / `ValueError` 等）+ 7193 条噪声边（含 776 条假 INFERRED 调用），**领域符号之间的真实关系零误伤**。原始图备份在 `graph.json.raw`，可回滚。

---

## Benders 数据流主线（按真实求解顺序串）

```
main.py
  └─> run_outer_search()                    c32 outer search 候选循环与 frontier
        └─> 每个候选矩形跑 LBBD ──────────── c29 Benders 主循环 & ghost anchor 过滤
                                              c43 Campaign 持久化 & CutManager/Benders 主循环
              ① master  (放置 + ghost 几何)   c7  MasterPlacementModel CP-SAT 主模型
                                              c5  CoordinateExactMaster ghost rectangle 几何
                                              c9  master forced-label 冲突判定
                                              c10 PoseBoolExactMaster & separator 容量
              ② binding (端口绑定)            c18 binding 子问题端口绑定 · c210 pose 级端口绑定
              ③ routing (网格布线)            c31/c52 routing 子问题 CP-SAT 建模
                                              c115 PCR-CUT patch routing core · c195 局部 routing
              ④ flow    (多商品流诊断)        c40 D2 commodity flow 分离器 · c37 flow & wireless sink
              └─> 子问题不可行 → 生成 cut 收紧 master（LBBD 闭环）
```

**Cut families（F1–F9，作为 Benders cut 收紧 master）** — 核心生命周期 c1/c4/c12（Cut 生命周期 & 状态哈希 & Oracle 证书），各 family：

| 社区 | family |
|---|---|
| c26 | region_capacity（F1 区域容量） |
| c3 | density_envelope（密度包络） |
| c6 | power_grid_reach（F5 电网可达） |
| c13 | shape_packing_hall（形状装填 Hall） |
| c17 | power_hitting_set（电力命中集） |
| c20 | pattern_nogood（模式 nogood） |
| c22 | port_exposure（端口暴露） |
| c244 | component_reach（连通性可达） |
| c113 / c312 | cutset（割集 + oracle 证书） |

**终态/交付侧**：c19 campaign 持久化与终态验证 · c33 campaign UNKNOWN 候选分诊 · c68 **certified 交付 manifest 写入** · c55/c59/c87/c95/c125 单基地交付面渲染（frontdoor/对齐/落地页/入口/viewer）。

---

## 模块化社区索引（按 src/ 顶层，节点数排序）

**`models/` (839 节点, 15 社区) — CP-SAT 建模核心**
c7 MasterPlacementModel 主模型 · c5 CoordinateExactMaster ghost 几何 · c9 forced-label 冲突 · c10 PoseBoolExactMaster & separator · c18 binding 端口绑定 · c43 Campaign & CutManager · c46 HiGHS/SCIP master & power 分离器 · c52 routing CP-SAT · c65 ghost 锚点收紧 · c115 PCR-CUT patch routing · c201 CP-SAT worker 配置 & 内存 cap

**`cuts/` (538 节点, 18 社区) — cut 生命周期 + oracle**
c1 生命周期 & Benders 状态核 · c4 状态哈希指纹 · c12 Oracle 证书 · c77 Dinic 最小割 helper · c113 cutset family · c220 power_network 电网可达 · c244 component_reach 连通性 · c273 power grid reach oracle

**`search/` (5167 节点, 187 社区) — outer + campaign + Phase3B**
c32 outer search 候选循环 · c19 campaign 持久化 & 终态 · c29 Benders 主循环 & ghost anchor 过滤 · c33 UNKNOWN 分诊 · c0 **Phase3B 长跑 preflight 验收** · c2 **B5a certified anchor 晋升评审包** · c15/c16/c30/c35 anchor119 验收/row_domain/混合车道 · c21 anchor 电杆审计 · c24 forced_anchor 削减 · c25 pose-order 几何签名

**`tests/` (4637 节点, 311 社区) — 按被测子系统命名**
c8 exact 契约测试(certified 边界) · cut family 测试群 c3/c6/c13/c17/c20/c22/c26/c27 · c23 Cut store/replay · c31 routing CP-SAT 测试 · c37 flow & wireless sink · c14 power_protocol 诊断 · c38 master fixture 工厂

**`adapters/` (421 节点, 17 社区) — postprocess-only，不重定义 solve schema**
c28 endfield_calc TS 快照摄取 · c34 industrial_planner blueprint 校验 · c48 语义映射/商品解析 · c56 base_planner 外部部署 · c80 吞吐量审计 · c249 recipe matcher · c300 catalog diff

**其余**：`render/` 295 节点（单基地交付面渲染 c55/c59/c87/c95/c125/c140 + c356 LBBD 动画 + c354 ASCII）· `io/` 102 节点（c68 certified manifest · c154 蓝图序列化 · c333 strict_json）· `runtime/` 162 节点（c73 CPU 拓扑/进程优先级 · c101 checkpoint-free 评估器 · c316 pacman freeze 监控）· `interchange/`（c106 preprocess context · c138 export registry）· `preprocess/`（c109 需求精确求解器 · c225 instance builder）· `placement/`（c180 候选生成 · c258 对称破缺）· `ai_accel/`（c11 AI sidecar 离线 replay & 影子排序）· `rules/`（c242 pydantic 配置模型）

---

## 新窗口入口指引（先读这 6 个社区/文件）

1. **求解主线** → c32 `src/search/outer_search.py` → c29/c43 Benders 主循环
2. **master 建模** → c7 `src/models/master_model.py`、c5 `exact_coordinate_master.py`
3. **cut 机制** → c1 `src/cuts/lifecycle.py`（含 `step_8_apply_to_master` 那条"尚未集成"边界）
4. **cut families** → c26/c6/c20 等 `src/cuts/oracles/` + `src/tests/cuts/`
5. **当前范式 Phase3B** → c0 长跑 preflight、c2 B5a certified anchor 晋升、c15 anchor119
6. **certified 交付面** → c68 `src/io/delivery_manifest.py`、c55/c59 render 交付面

---

## 怎么刷新

完整刷新流程（robocopy 镜像 → extract → 通用名降噪 → 聚类 → import 坐实 VERIFIED → 社区命名 workflow → finalize → 更新成品快照）见同目录 **`README.md`**，全程离线零 token。

> 判断是否过时：看本文件头部绑定的 HEAD vs 当前 `git rev-parse HEAD`。代码大改后按 README 重跑刷新。
