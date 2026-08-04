> 【2026-08-03 追注】本文第 4 步「GPT 类划分与 repo 语义不符（按商品种类数）」的判断
> **已被更正**：repo demand SSOT 实为 slot 数（⌈rate/belt⌉），GPT 九类表与之逐行相同。
> 更正全文见同目录 `21_w0_port_semantics_correction_20260803.md`；本文其余结论
> （seed 死刑，两种语义下均成立）不受影响。正文按史料纪律保持原样。

# 19 号：W0 pinned seed「先天绑不上端口」死刑指控的独立复算（2026-08-03）

**性质**：research-only 复算记录。不产生任何 bound/witness/soundness claim；
`U=(1188,18)`、`L=absent` 不受影响。复算对象 = 17 号文书（GPT Pro 07-30 回复，
`zmd_lower_bound_unblock_20260730.7z`，SHA-256 `0c23cdde…48fd61`）的核心指控：
**W0 power-cycle domino 的 pinned geometry seed 先天不可完成——219 台制造机中
129 台无法承担任何真实 operation class**。

## 复算方法与结论

复算者：主会话（Claude），2026-08-03；全程无 solver，输入为
`w0-d6-6b-d9-6g-swap-v3-20260728T202427Z-db00416d3c68` 运行的 inputs
（strict_instance/framework/seed 三件，现存
`/mnt/wd_external/archives/zmd-codex-autonomy-20260801/zmd-pj-codex/.artifacts/research_runs/`）。

**判决：指控成立，且在仓库权威语义下更强。** 五步验：

1. **包完整性**：7z 内 `SHA256SUMS.txt` 逐文件校验全 OK。
2. **脚本复跑**：`seed_front_viability_audit.py` 在钉死解释器复跑，输出与包内
   记录 `results/seed_front_viability.json` **语义逐字段相等**（仅时间戳/路径
   元数据不同）。headline：219 台中 `dead_for_any_actual_class=129`（58.9%）、
   `dead_even_for_one_input_one_output=128`。
3. **前提审计——front 语义**：脚本 `_port_front` = port body cell 沿方向一步
   （体外第 1 格），与 owner 07-18 实测定谳口径一致，未踩 front-offset 事故坑。
4. **前提审计——输入对账仓库冻结权威**：
   - strict_instance 266 实例与 `data/preprocessed/mandatory_exact_instances.json`
     逐 operation 计数相等（唯一差异=命名：repo 的 boundary_io×46+protocol_core×1
     在 W0 表示中合并为 generic_io×47）；制造机 219=132(3x3)+49(5x5)+38(6x4) 自洽。
   - **发现前提偏差（不救指控、反而加重）**：framework 的类划分 need 向量
     （3I2[2,1]/3O3[1,3]/6G[3,1]/6F[4,1]/6B[5,1]…）与仓库冻结 `canonical_rules.json`
     recipes 的商品种类数**不符**——按 repo 语义全部 3x3 recipe 恰 1 进 1 出、
     全部 5x5 恰 1 进 1 出、全部 6x4 恰 2 进 1 出。GPT 的 need 向量疑似其自有
     吞吐模型产物（吞吐在 certified 范围外）。**但在最弱可能要求（每台 ≥1 自由
     输入 front + ≥1 自由输出 front）下，seed 仍然死**：3x3 可用 43/132（缺 89）、
     5x5 可用 33/49（缺 16）、6x4 可用 15/38（缺 23），合计仅 91/219 台身位可活。
     这是纯 body-front 几何计数，与 routing/class 分配方案无关。
5. **手工抽验**：死名单第 4 号（anchor (11,11) 3x3）局部占用图独立重建——三面
   被固定 body 围死仅南侧开放，而 3x3 模板每模式进出口在对侧 →
   mode0=3进0出、mode1=0进3出、mode2/3 全堵，任何模式拿不到 1进1出。判死正确。

## 含义与边界

- **W2b 六次 prod UNKNOWN 与 D6 反复碰壁得到解释**：都是在给一张先天绑不上
  端口的本体图接线。pinned seed 线续跑无意义。
- 17 号处方（front-aware pattern generator → exact-cover master → 孔洞全局
  变量 → SCC 收路由，G1/G2/G3 三道门）与 16 号 H20 沙漏梳（含廉价一维行排列
  +供电覆盖微型判定器）是两条候选新方向；**方向选择属 owner 拍板项**。
- 修复设计必须用 repo 端口语义（种类数），不得沿用 GPT 吞吐类划分——本复算
  第 4 步的偏差记录就是为此。
- 本文书不修改 W0 任何状态；`docs/research/` 下 W0/D6 工件与三个 research_runs
  归档保持原样。

复算工作目录（session scratchpad，会话结束即失效）：
`scratchpad/w0audit/`；关键数字均可由上述归档输入 + 包内脚本确定性重现。
