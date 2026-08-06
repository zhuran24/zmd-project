# 第四轮包组装说明（给主线自己，非 reviewer 材料）

**发包前置（硬序）**：owner 完成公理审阅（`.artifacts/axiom_analysis_20260806/
AXIOM_REVIEW_FOR_OWNER.md` 五件把关项给出裁定）→ 按裁定改写任务书规则段
（占位段替换；若 owner 解锁输出口过境则硬约束 6 改写并把新自由度扩为双向）→
打包 → owner 传。

## 打包清单（沿用 band22 严格重设计包框架）

1. `00_TASK_BRIEF.md`（本目录草稿替换规则段后的终版）
2. 冻结输入：`rules/canonical_rules.json`（c3666d78…；若 canonical 修正批先落地
   则用新版+新 sha，任务书语义随之）、`rules/preprocess_plan.json`、
   `data/preprocessed/mandatory_exact_instances.json`、`generic_io_requirements.json`
3. 速率表：`rate_lemma_recompute.py` 的输出表（17 残道逐条+满率口径）
4. 见证 schema：沿用 `band22_strict_witness_v2.json` 结构说明（上轮包的 schema 章）
   +本轮新增字段无；坐标系注记（N=y+1）
5. 上轮死因分析：任务书内嵌（已写）；不附上轮见证本体（避免锚定）
6. 几何账本：候选池引用（f05b1291…）或按上轮包的几何摘要形态
7. MANIFEST.sha256
8. 独立成包，不与外审包混（受众不同：设计任务 vs 审计任务）

## 验收管线（收到回件后）

1. 独立重算（上轮 codex_reverify 同款：几何/端口/供电/孔严格性）
2. ④路 driver 全阶梯：intake → 固定 master → 官方 binding/routing 门
   （budgets 沿用；RAB 开关按需）——**本轮预期 rung3 可过**（死因已修）
3. 叙述层按交付合同验数字（脚本复算 vs 报告数字）

## 变更记录

- 2026-08-06 备料稿立（规则段占位）。触发：owner 拍板第四轮开工+「先确定再找」。

- 2026-08-06 午后：owner 公理审阅五件★全清（A9 认+三点精化/A2 实质裁毕/箱条款槽数口径/
  输出口过境安全+汇流速率注记/回退=留上游）。规则段终版替换、staging 组装、
  `band22_r4_design_20260806.7z`（sha 6b5ca808…）落 ~/下载/zmd-咨询包，解包抽验过。
  组包时发现上轮包 06 是严格空语义条款前旧快照（ERRATA E-05，实害零，本轮已换正版）。
  模型侧 source front 解锁 = 独立 freeze-ritual 批（sealed 面），不阻塞本轮。

- 2026-08-06 傍晚：**验收管线预检通过**——④路 driver 用上轮 strict42 见证走 intake 段
  smoke：INTAKE_ACCEPTED / exit 0（session build 30.5s、master build 9.7s、ghost
  identity+结构全过，收据 band22-registration-driver/2 正常）。driver 测试 42/42 绿。
  产物在 `.artifacts/band22_registration_20260805/r4_driver_precheck_20260806/`。
  r4 回件到达可直接跑全阶梯（rung3 预期可过）。注：driver 真身在
  `docs/research/band22_registration_20260805/`（.rgignore 投影区，fd 需 --no-ignore）。
