# 02 — ①′ 第二段执行记录：结构加固 + env 分类提升批（2026-07-16）

> 依据 = 01 号文书 v2（11 席对抗验证后的 soundness 审查）§7 工程义务清单。
> 本批全部落地并过完整门禁 + 三席 codex 对抗复核 + 复核发现的修复回合。

## 改动清单

**结构加固（sealed 面）**
- `binding_subproblem.py`：cert 整证不发 fail-closed×2（归因不完备 / blocker literal
  解析失败）；`_strict_literal_pose_idx`（F-BL-R10 同款字面 int 口径，复核回合加，
  使实现精确等于 F-BL-R11-01 条款——int() 宽松转换会把 '1'/True/0.5 静默铸成
  literal 或抛异常）；filter commodity 严格取值镜像 model；`unattributed` 记名
  追踪面（内部 set + 可审计 stats 字段）；generic output/input disjoint fail-closed
  断言（消费者边界，codex hybrid 探针缺口）。
- `benders_loop.py`：`_rab_empty_domain_thin_fallback_forbidden` 结构守卫 +
  EMPTY_DOMAIN 循环接线（layout 依赖空域禁全局 thin fallback，全跳走既有
  cut_stall→UNKNOWN）；`EXACT_B1_ROUTING_AWARE_BINDING` 收编 certified
  operational allowlist（带完整依据注释，默认仍 OFF）；`:6887` 旧注释史料订正。
- `routing_binding_context.py`：ghost_pick 等非设施 marker 显式排除（升级
  空池巧合安全为结构保证）。

**条款/文档**：PROJECT_LOCK 新增 **F-BL-R11-01**；`18_workflow_env_config.md`
RAB 行更新。

**测试（两轮）**：`test_rab_sep_soundness_sentinels.py`（首轮 10 → 复核加固后
25 用例：front_blocked build 短路哨兵、relaxed_disconnected 正确语义三臂、
归因同源逐格断言、ghost 排除全格+正向对照、cert 逐 literal 精确断言、
混合归因臂、strict pose_idx 9 值参数化、单缺追踪面 4 型参数化、真·全出界
pose 内在臂、disjoint 拒绝+acceptance 对照、autouse solver env 钉扎）+
`test_exact_contract.py` 新增 env 收编测试与**控制器接线级三臂集成测试**
（真实 LBBD EMPTY_DOMAIN 循环 + RAB env 开启：两个 fail-closed 臂断 UNKNOWN
零 cut，pose_intrinsic 臂断 singleton cut + CERTIFIED——顺带钉死收编后
certified 会话真实可跑）。

## 对抗复核（3 席 codex）与处置

| 席位 | 判定 | 处置 |
|---|---|---|
| soundness 攻击 | **holds**（无现行可达洞） | medium「lock 条款比实现强：不可转换 pose_idx 会抛异常而非跳证」→ 本回合以 `_strict_literal_pose_idx` 修复+9 值参数化测试；两条 future-drift low（外部 context 的归属正确性校验、正向记账"全部拒因=OOB"）记档不阻断 |
| reseal/条款审计 | **holds** | 四文件 sha 逐字节核对一致、零 CRLF、条款/注释逐句对码；low 记录：ghost_pick 是隐含保留 ID（canonical 数据无冲突，非本批可达） |
| 测试充分性 | **refuted**（作为防护网） | **block**「接线点删除不被任何测试察觉」→ 控制器三臂集成测试修复，并做**变异验证**（临时掐死守卫 ⟹ 恰两个 fail-closed 臂红、pose_intrinsic 臂绿 ⟹ 字节级复原、pin 复核吻合）；两 high（cert 只断键集/计数、混合归因+单缺面未测）与两 medium（stats 正向断言、solver env 继承）全部修复 |

**遗留（记档、不阻断，均非现行洞）**：①深层 adherence 防线（伪造 feasible
analysis 强迫建模）无专门哨兵——该层已有 F-BL-R9-01 条款 + codex 探针证据，
挂后续；②cert-happy 路径的 master 侧 all-or-nothing 由既有 master 测试覆盖，
单实例 fixture 造不出 core≥2 可解析 cert；③外部 context 归属正确性校验
（仅当未来允许非 builder-produced context 时需要）。

## 门禁与 reseal（终态）

- preflight `--full`：19 gates PASSED，**4425 passed / 74 skipped**（快 lane 2:23）。
- `--slow-tests`：31 passed（首轮 4:09 绿；复核修复回合后重跑，见提交信息）。
- 双 checker：15 obligations / 67 sinks + 65 AST / 83 entries（计数不变=纯 reseal）。
- close-kernel reseal 两轮（首轮三文件；复核回合 binding 再改再 reseal），
  全部按 SOP：字节 sha、纯 LF、checker 自钉最后算。
- 变异验证的临时改动已字节级复原（sha 与 pin 逐字符核对一致）。

## 下一步

第三段 = prod 注入演习：单发 6×6 锚点 master solve（~500s/43G，owner 已预批
"单发不算长跑"），开 `EXACT_B1_ROUTING_AWARE_BINDING=1` 量 EMPTY_DOMAIN 触发率、
cert core 分布、master 吃细粒度 cut 的收敛行为（01 文书 §8 声明的唯一未验面）。
