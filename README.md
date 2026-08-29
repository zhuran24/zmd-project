# ZMD certified-exact 布局求解研究

[中文](README.md) | [English](README.en.md)

ZMD 在 `70×70` 网格上联合求解设施摆放、供电覆盖、端口绑定和双层路由，在满足全部硬约束时最大化合法连续空矩形，并建立可独立复验的精确证据链。研究路径先构造不预设目标空矩形的完整布局（“零条件完整布局”），再让完整合法见证与全局最优性证明在同一问题、规则、目标和前提下合拢；长期目标是形成能跨上下文重新推导结构和证据的通用体系。

## 方法与工具链

`规则与目标 → 统计资源收支、失败模式与被迫结构 → 构造必要条件、充分解法和有限表示 → 精确模型 → 独立复验 → 认证`

| 层面 | 工具与作用 |
|---|---|
| 规格 | Canonical rules、规格文件和冻结输入固定问题身份 |
| 精确计算 | Python、OR-Tools CP-SAT、LBBD/Benders 接口处理 placement、power、binding 与 routing |
| 推理外环 | 组合计数、有限枚举、取等结构、成功构造和失败证书改变下一轮问题 |
| 复验 | 独立 checker、负控和另一套实现或环境的重放检查输入、实现和作用域 |
| 工程 | CodeGraph、pytest、pytest-xdist、Ruff 支持代码理解与回归检查 |
| 过境 | Git 三树与 promotion packet 分离研究发现和认证审查 |

锁定依赖见 [`requirements.lock.txt`](requirements.lock.txt) 与 [`requirements-dev.lock.txt`](requirements-dev.lock.txt)。

## 三树工作流

| 分支 | 角色 |
|---|---|
| `main` | 历史材料树和公开仓库入口 |
| `research/main` | 猜想、实验、构造、反例与新表示 |
| `certification/main` | 从头独立审查和复验成熟候选（冷审） |

成熟研究通过紧凑的 promotion packet（精确命题、前提、选定改动、复现命令、对照和已知未知）送交认证，不整体合并研究分支。

## 项目历史

ZMD 是一个连续项目。两次备份并重建 Git 形成三个无父根时期，随后第三代正常分叉为三树；Git parent 的断开不代表项目重新开始。

`第一代 → 第一次 Git 重建 → 第二代 → 第二次 Git 重建 → 第三代 → main / research / certification`

完整时间线、备份点、公开脱敏和旧 GitHub 独有支线见 [`PROJECT_LINEAGE.md`](PROJECT_LINEAGE.md)；机器索引见 [`history/continuity.json`](history/continuity.json)。

## 项目入口

| 需要了解的内容 | 入口 |
|---|---|
| 当前状态与问题路由 | [CURRENT](docs/CURRENT.md) · [START_HERE](docs/START_HERE.md) |
| 代码、规格和规则 | [NAV_MAP](NAV_MAP.md) · [问题陈述](specs/01_problem_statement.md) · [rules](rules/) |
| 精确性与认证边界 | [PROJECT_LOCK](PROJECT_LOCK.md) · [CATALOG](docs/CATALOG.md) |
| 操作与文档结构 | [AGENT_OPERATIONS](docs/AGENT_OPERATIONS.md) · [GUIDANCE_INDEX](docs/GUIDANCE_INDEX.md) · [SECTION_INDEX](docs/SECTION_INDEX.md) |
| 其他稳定入口 | [docs/README](docs/README.md) · [HISTORY_START](HISTORY_START.md) · [BORROWED_COMPONENTS](BORROWED_COMPONENTS.md) |
