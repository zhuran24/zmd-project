# 批C 执行计划(草稿 v0,2026-07-12 深夜)

> **地位**:批C = PIC-4 + PIC-5 生产 campaign 层 + RFC-003 门6 prod A/B(批E 规格 08 §4 门6「归批C prod 层」)。
> 本稿为执行计划草稿,第一验结果与窗口需求供 owner 排期拍板;非规格修订,不碰 sealed 面。
> 权威边界:PROJECT_LOCK:492(promotion 前置全集)、`03_production_integration_checklist.md` §1 PIC-4/PIC-5、批E 规格 08 §0 三卡点。

## §0 输入状态(开工时点)

- 工程前置全清:Stage B B0-B5b、批D verifier、α/α2/β、B6 前置工程批、批E RFC-003 均已落地(lock:492 Status snapshot 2026-07-12)。
- 宿主:`attach_host_runner.py`(本目录,批E 单元3 交付)——m5_cell_runner 基座+ledger 接线+GENESIS 血缘+enabled-families 旋钮+dedup/epoch telemetry;可解配方默认 fixed+p3+s3(m5_ab_param_bisect_20260711)。
- 内存条款:每 solve 尖峰 ~60G(RSS>42G+swap),**一次只跑一个**(铁律);本机 47.7G RAM+zram swap 46G 实测可承(M5 第五刀/E1' 先例)。
- 单 solve 时长基准:OPTIMAL@513-649s(E1' 基线 513.5s/产品默认 649.1s/批0 541s),attach 开销 +4.1%~+6.9%(E2' GO 判决)。

## §1 第一验:组织性触发(卡点①,阻塞后续全部)

**问题**:当前 C1 表示+可解配方下,binding-INFEASIBLE 是否自然发生→框架 cut 是否组织性触发?历史 cuts_6x6.json 证明旧表示下发生过 5 次;C1 表示下从未复现。

**命令**(2026-07-12 已启动,run-tag `batch_c_probe_1`):
```
.venv/bin/python docs/research/batch_ce_attach_host_20260712/attach_host_runner.py \
  --ghost-w 6 --ghost-h 6 --attach on --master-seconds 900 \
  --run-tag batch_c_probe_1 --out <scratch>/cell.json
```

**判定**:
- `coordinate_framework_cut_count > 0` → 组织性触发成立,§2 A/B 矩阵有意义,照跑。
- `== 0` 且 master OPTIMAL → 可解配方下无自然触发。**不是失败**,但 A/B 双臂会双零空过(门6 rev3 校准明令防的场景)。转 §1b 备选路径。
- master 非 OPTIMAL/超时/异常 → 先按 M5 纪律归因(单变量、完整条款上下文),不得混杂解读。

**§1b 无自然触发时的备选**(按序试,均不碰 sealed):
1. 换 ghost 尺寸(6×7/7×6/更大)扫描——更紧的 ghost 更易逼出 binding-INFEASIBLE;
2. 用 `--enabled-families` 与配方组合矩阵找触发窗;
3. 仍无 → 批C 判定口径改写为「PIC-5 编排/telemetry/成本验证 + 门6 改注入式对照」,组织性触发义务上报 owner 改判(这属于规格判据变更,owner-only)。

**结果**:⬜ 待填(probe_1 运行中)。

## §2 门6 prod A/B 矩阵(卡点②:窗口需求)

前提=§1 触发成立。判据(批E 规格 08 §4 门6 行):
- **on 臂**:`generated>0 && applied>0`(防双零空过);
- **off 臂**:`applied==0`;
- **等价性**:两臂目标值一致 + 独立复验等价(unforced 六项复验先例照搬批0);
- 附带测量:attach wall 开销、dedup 命中率(semantic_duplicate 桶)、epoch telemetry、ledger 三态读回=complete。

**最小矩阵**(CP-SAT w1 下 M5 四刀已证 branches/conflicts 逐位确定性,单跑即可判等价;重复第 2 次仅作稳定性佐证):

| 臂 | 配置 | solve 数 | 预计 wall |
|---|---|---|---|
| A/B 核心 | 6×6,fixed+p3+s3,on/off 各一 | 2 | ~25 min |
| 稳定性复跑 | 同上重复一轮 | 2 | ~25 min |
| 门7 rollback 演练(prod 侧) | on,`--enabled-families` 关一族(D-13) | 1-2 | ~15-25 min |
| PIC-4 多迭代观察 | 见 §3,可与 on 臂同 run 采集 | 0(共用) | — |
| PIC-5 多 rect 序列 | 见 §4,harness 自建外循环,2-3 rect | 2-3 | ~30-45 min |
| D-1 waiver 附带:oracle 重生成开销 | restart 链(GENESIS 血缘 flags),前后段各一 | 2 | ~25 min |

**窗口需求合计:约 9-11 个 prod-scale solve,串行 ~2.5-3.5 小时;含归因重试余量建议按半天(4-6h)申请。**
机器约束:窗口内整机独占(单跑铁律),期间不跑慢 lane/preflight(树冻结纪律)。

## §3 PIC-4:anchor 切换退役(单 controller 多迭代)

批E 侦察已重解释(规格 08 §0):框架 cut ghost-bound/per-master,**不跨 solve 迁移**;退役发生在单 controller 多迭代之间——anchor 切换后旧 ghost-bound cut 经 `OnlyEnforceIf(u_var)` 恒假物理失活(lifecycle.py:1657/1686/1797-1806)。

**实测形态**:on 臂 run 内采集——若 §1 触发且出现多迭代(cut 落地→master 重解),核对:①切换后旧 cut 的 u_var 恒假(telemetry/receipt);②新迭代无旧 cut 语义重执行;③dedup pool per-master-build 语义(generation 绑定)与 epoch 记账一致。若单 rect run 天然只有 1-2 迭代,则并入 §4 多 rect 序列观察。

## §4 PIC-5 生产 campaign 层(卡点③:守卫层边界)

- **flip 前可做**(本批):harness 自建外循环复刻多 rect 序列——同进程串行多个 ghost rect(6×6→6×7→7×6 之类),每 rect 完整 step5→6→7→8 编排+预算+rejection taxonomy+ledger 连续段(predecessor 血缘),采集真实 telemetry 与成本。**诚实边界:这是复刻,不是真生产编排**(真编排入口在 sealed 守卫层,certified 下 attach fail-closed)。
- **flip 后必做**(promotion 包⑤):真 production campaign 烧机验证,纳入 B6 promotion 包。本批文档必须把这条边界写死,防「harness 绿=生产层已验」(PIC-5 同款纪律)。

## §5 产出物(批C 收口=promotion 包素材)

1. 第一验判定+A/B 全矩阵证据(cell.json 全集+ledger segments+等价性核对表);
2. oracle 重生成开销测量(D-1 waiver 保留义务,批E 规格 §1);
3. PIC-4/PIC-5(harness 层)结论成文;
4. **promotion 包前口径确认点**(owner 拍板项,先行登记):
   - `07_batch_b6_prep_spec.md` 「B6 转硬门仍需完整多跳 alias-dataflow」字面 vs 06/roadmap/lock「α2 两项已闭(F-05 一跳已落+sink 注册 won't-do)」——二选一:补多跳,或 owner 明示接受一跳为非-soundness tripwire 边界并同步权威文档;
   - RFC-003 门6 状态 OPEN→本批结果改写;
   - F5 转正批排期(与 B6 合批或紧随)。

## §6 明确不做

- 不碰 sealed 文件、不 reseal、不动 unsafe map(B6 owner-only);
- 不做 F5 转正面任何工程(独立批);
- 不把 harness/fixture 绿写成生产层已验;
- 不在窗口外跑第二个 prod-scale solve。

---

## §7 实测修订(2026-07-13 凌晨追加;probe 1-2 + PTM 合体轮 1-2 的数据)

### 执行史
| run | 配置 | 结果 |
|---|---|---|
| batch_c_probe_1 | w1(runner 默认,配置失误),独占 | **SIGSEGV@24min**(官方构建,`Py_INCREF/_PyDict_FromItems`,SEGV_MAPERR,core 1.2G 在 systemd coredump,pid 541076) |
| batch_c_probe_2 | w1,独占,+faulthandler | 穿过 probe_1 死亡时点未复现崩溃(→间歇性);binding 段 67+min 未出结论,换硅脂关机中断 |
| ptm_cycle_1 | w6+全核 stress **无隔离**,master 900s | master UNKNOWN=**无效臂**(伴跑污染);87°C 全链 14min 零崩 |
| ptm_cycle_2 | w6+taskset 隔离(solve@0-6/stress@7-23),master 1800s | **master 出解**;binding 枚举 52min 未出结论被 3600s 兜底掐;peak 94°C 零崩;VmHWM 42.6G+swap 6.3G |
| batch_c_probe_3 | **独占**,w6+`EXACT_BINDING_CP_SAT_WORKERS=6`,master 1800s | master ~14min 完成(HWM 44.7G);binding 枚举 ~105min 无结论,**TIMEOUT@7200s**;零崩。与 probe_2(w1)行为一致=F-5 生产层坐实(env 对 binding 无效) |
| batch_c_probe_6 | 独占,w6+`EXACT_SUBPROBLEM_PARAMS="search_branching=0"`(F-5 修复验证臂,cf76bed 后) | 【跑中,09:43 起】判定点:binding 段 CPU 是否 ~600%+出结论时长 |

### 工程发现(F-1~F-4)
- **F-1 binding 段无段级帽**:单次 solve 的 600s 帽接线完好(`benders_loop:6803→binding_subproblem` `max_time_in_seconds`),但编排层有枚举/重试多次 solve(5 个调用点+retry),**段级总时长无上限**(probe_2/cycle_2 双复现)。宿主必须自带段级 wall 兜底(合体脚本用外层 3600s kill 实现)。提速选项:`EXACT_BINDING_CP_SAT_WORKERS`(实测 binding 单线程 99.8% 满转,默认 w1;binding 稳态内存 18.5G,有余量开 4-6 worker,留独占重跑实验)。
- **F-2 w1/w6 不可比**:runner 默认 `--workers 1`,而 OPTIMAL@541-649s 先例全是 w6 口径。**第一验标准命令必须显式 `--workers 6`**。
- **F-3 伴跑必须核隔离**:全核 stress 无隔离→master 900s UNKNOWN;taskset 隔离→master 出解。热/压力实验与求解共存的唯一有效形态=物理核隔离。
- **F-4 w6 内存实测**:峰值足迹 ≈49G(VmHWM 42.6G+VmSwap 6.3G,出解时刻),稳态 15-20G,与 M5 ~60G 口径同量级。1s 粒度采样器产出 `mem.csv`(PTM 轮次曲线)。

### 组织性触发:仍未验
cycle_2 是首次推进到 binding 的 attach-on 运行,但 binding 未在预算内给出 FEASIBLE/INFEASIBLE 结论。当前诚实状态:**C1 表示+可解配方下,binding 从未在时限内出过结论**——触发判定的前置=binding 提速(F-1 worker 选项)或更大预算,独占窗口重跑。

### 窗口需求修订(推翻 §2 原估)
§2 的「9-11 solve×10min≈2.5-3.5h」只覆盖 master 段,作废。完整链单点(含 binding 枚举)实测 >1h 未完成,按 1.5-2h/点计:**A/B 矩阵 14-22h,建议按 24h 窗口申请;或先做 binding 多 worker 提速实验,把单点压到 <1h 再跑矩阵(推荐后者)**。

### 平行的硬件归因线
详见 auto-memory 卡 `uv-python-interpreter-intermittent-segfault`(07-13 回填):13900KS Vmin shift 机制嫌疑、microcode 0x133、满载 VID 1.33-1.39V、换 PTM7950 后 87-94°C 两轮零崩。判据树:PTM 5 轮全过→热嫌疑主导;再崩→memtest86+ → BIOS P 核 +50mV 复测。

### F-5(07-13 晨,probe_3 实测):binding 并行被 FIXED_SEARCH 锁死
`EXACT_BINDING_CP_SAT_WORKERS=6` 注入成功(进程 environ 确认)且参数链完好(`resolve_cp_sat_worker_count` 正常,binding 默认即 4 worker),但 probe_3 实测 binding 段瞬时 CPU=1.0 核——`binding_subproblem.py` 的 solve 硬编码 `search_branching=FIXED_SEARCH`,**CP-SAT 在 FIXED 搜索下 num_workers 无效、退化单 worker**(此前所有轮的 binding 单线程同因;F-1 的「开 worker 提速」选项就此证伪)。真正的提速路=改 FIXED_SEARCH(sealed 文件,reseal 批+双审,须论证 search 策略不碰 soundness——solver 参数不改验证语义,预期可行但走完整流程)或接受段级时长。`EXACT_SUBPROBLEM_PARAMS` 注入 search_branching 无效(注入点在硬编码行之前,被覆盖)。窗口估算相应固定为 1.5-2h/点,矩阵拆多窗口执行。

### F-5 修复批(07-13 上午,`cf76bed`):env 注入通道打通,certified 默认零变化
probe_3 TIMEOUT@7200s 坐实「不提速矩阵不可行」后,按本节「先做 binding 提速」推荐执行。根因实为**两层**:
1. **顺序**:`apply_subproblem_memory_cap`(`EXACT_SUBPROBLEM_PARAMS` 通用注入)在 `binding_subproblem.solve` 里调用于 FIXED_SEARCH 硬编码**之前**,注入值被覆盖;
2. **类型**:ortools 9.15 原生绑定(`cp_model_helper.SatParameters`)的枚举字段 setter 只收枚举类型,`search_branching=0` 解析成裸 int 后 `setattr` 抛 TypeError,被注入函数的 garbage-no-op 契约静默吞掉——即使顺序对了 int 注入也永远失效。

修复:①注入调用挪到内置 profile(FIXED/symmetry/probing 硬编码)之后=「显式 env 覆盖内置默认」既有优先级哲学;②注入函数对 int 值加枚举类型重试(`type(current)(parsed)`)。**无 env 时行为零变化**(FIXED_SEARCH 原样),`EXACT_SUBPROBLEM_PARAMS` 本在 certified 操作性 allowlist、无新 env 面;solve 后 telemetry `search_branching` 字段本就如实记录最终值。新增测试 `test_binding_subproblem_params_env_overrides_search_branching`;close-kernel reseal 3 pin(V99 dict binding+worker_config、JSON binding entry、checker 自钉),双 checker 计数不变(15/67/65/83),`--full` 19 绿+慢 lane 绿。
**注意**:同款顺序 bug 存在于 routing/patch_routing/d2/power/master 各 `apply_subproblem_memory_cap` 调用点(master 有专属 `EXACT_MASTER_SEARCH_BRANCHING` 不受影响)——本批只修 binding(单变量纪律),其余留待需要时逐个处理。
验证臂=probe_6(`search_branching=0`+w6):若 binding 提速显著(CPU ~600%、时长大降),§2 矩阵估算按新单点时长重估;若 AUTOMATIC 下 binding 仍无结论,说明瓶颈在枚举结构本身(F-1 的多次 solve 循环)而非单 solve 并行度,提速路线转向编排层。
