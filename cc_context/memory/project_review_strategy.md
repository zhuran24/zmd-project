---
name: review-strategy
description: 4层自动化审查体系：preflight gate → **L1.5 动态短跑 smoke** → 自主语义审查 → /ultrareview，用于判断每次改动需要什么级别的审查
type: project
originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---
## 4层审查体系

### 第1层：Preflight Gate（每次 commit 自动触发）
- 脚本：`scripts/preflight_gate.py`，通过 `.git/hooks/pre-commit` 挂载
- 6项检查：冻结hash、禁止路径、AI安全合同、精确/探索隔离、R-N audit 覆盖、86核心测试
- 耗时 ~2.5s，全自动，零人工

### 第1.5层：动态短跑 smoke（src/search 主路径或 env-gate 改动后）⚡ 新增
- 脚本：`scripts/dynamic_review_smoke.py`
- **跑 5 min 短 campaign + assert runtime 行为符合设计**
- 核心 assertion：
  - dumper 真在工作（binding_dumps.jsonl 增长）
  - **LBBD inner loop 实例真出现**（time_limit > 5s 或 instances > 2，区分 boundary precheck vs 真 LBBD）
  - candidate state 有变化迹象
- 为啥需要：2026-05-11 outer_search A+B 修订 4 agent L2 复审 + 全量 pytest + readiness gate 全过，但 168h 真跑发现 main 启动后没进 LBBD inner loop。**静态 review 抓不到 runtime path bug**。
- 触发：改 `src/search/outer_search.py` / `benders_loop.py` / `exact_campaign.py` 或 `src/models/{binding,routing,flow}_subproblem.py` 或 env-gate 影响 control flow
- 耗时 ~5-10 min wall-clock

### 第2层：自主语义审查（Claude 自行判断）
- 改动涉及求解核心时，自己做语义级检查
- 确认求解语义未变、目标函数 max_lex(area, min_side) 不受影响
- 不需要用户参与，但要在 commit message 里注明做了语义审查
- **限制**：静态 review。catches code-level invariant 违规，**不 catch runtime behavior gap**（这是 L1.5 补位）

### 第3层：/ultrareview（用户每天早上手动触发）
- 用于重大变更的全面外部审查
- 用户每天起床后跑一次，覆盖前一天的所有改动
- 前提：需要 main 分支存在 + GitHub repo（2026-05-10 已推到 https://github.com/zhuran24/zmd）

## 风险分级决策规则

- **低风险**（日志、遥测、诊断工具、测试补充、文档）：L1 够用
- **中风险**（AI sidecar、适配器、非核心搜索逻辑）：L1 + L2
- **高风险**（CP-SAT 参数、master model、Benders 分解核心、env-gate 控制流）：L1 + **L1.5** + L2 + 留给 L3 确认

**Why:** 项目有严格的精确性宪法（PROJECT_LOCK.md），机械性违规靠 gate 拦，**runtime path bug 靠 L1.5 短跑 smoke 抓**，语义性问题靠 Claude 自审 + 用户 ultrareview 兜底
**How to apply:** 每次改动前先判断风险等级，选对应的审查层级；任何 env-gate 加入或改 runtime control flow 必跑 L1.5

## 链 (补连 2026-06-01)
- [[index-packaging-cluster]] — 审查打包规范全套入口
- [[big-milestone-gpt-pro-review]] — 大节点外审
- [[gemini-review-algorithm-math]] — 算法层 cross-check
