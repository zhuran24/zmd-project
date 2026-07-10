# M5 A/B 首战:产品默认 solve 参数病态的单变量归因(2026-07-11 凌晨)

## 背景与问题

M5 归因判决(`m5_c1_memory_attribution_20260710.md`)与 attach spike E1 系列(`../p1_3a_attach_power_on_spike_20260710/01_spike_spec.md`)两次把「产品默认 solve 参数(FIXED_SEARCH+probing3+symmetry3)在 C1 上持续吃内存不出解」列为待归因病态(smoke#4 撞帽死 vs 第四刀原型参数绿)。本实验做单变量二分。

## 实验形态

复用 `e2_harness.py --cuts 0`(certified 直建 C1 master,266 mandatory,6×6 ghost,参数经 env 注入),42G 帽+20G swap+w6+软 cap 28000,全核,单发串行。基线=spike E1'(automatic+probing1+symmetry1,OPTIMAL@513.5s)。

## 结果:三刀单变量全绿——无单一害群之马

| 刀 | 参数(翻转项加粗) | 结果 | wall vs 基线 | branches | conflicts | scope 峰值 |
|---|---|---|---|---|---|---|
| 基线 E1' | automatic+p1+s1 | OPTIMAL | 513.5s | 4,879,651 | 486 | 40.4G+19.6G swap |
| 刀1 | **fixed**+p1+s1 | OPTIMAL | 532.0s(+3.6%) | 4,990,408 | 1,076 | ~40.5G+18.9G |
| 刀2 | automatic+**p3**+s1 | OPTIMAL | 656.5s(+27.8%) | 4,878,851 | 531 | ~41G+19.2G |
| 刀3 | automatic+p1+**s3** | OPTIMAL | 586.3s(+14.2%) | 4,960,588 | 1,076 | ~40.9G+19.1G |

副发现:①probing3 是最贵的单变量(+27.8%)但远非病态;②**所有绿刀的内存峰值都贴 60G 域**(RSS ~41G+swap ~19G)——出解尖峰是参数无关常量,再次支持统一尖峰理论;③conflicts 在 fixed/s3 下同为 1076,与 branching 形态相关。

## 刀4(决胜,跑中):完整默认组合 fixed+p3+s3 全核

- 死(撞帽不出解)= 三参数组合交互病态实锤;
- 绿 = **「默认参数病态」结论被证伪**——smoke#4 的死因重新归因到其执行形态(taskset -c 4,5 两核,M5 codex 侦察当时已标 HIGH 混杂),M5 归因文档与 PIC-7 表述需修订。

## 刀4 结果与终判(2026-07-11 00:52)

**刀4 绿:fixed+p3+s3(完整产品默认)全核+42G/20G swap → OPTIMAL@649.1s(+26.4%),branches 4,899,973**。

### 终判:「产品默认 solve 参数病态」结论证伪——统一尖峰理论覆盖全部死亡案例

回溯 smoke#4(当时读成「默认参数病态」的唯一直接证据):其条款是 **42G 帽+MemorySwapMax=0**(1F B 段,swap 条款修订前)——42G 预算 < ~60G 出解尖峰,按 M5 统一尖峰理论**本来就必死,与参数无关**。当时第四刀(绿)同时翻转了参数与条款(无帽),双变量混杂导致误读。今日四刀在修订条款(62G 预算)下全绿终结此案:

| 死亡案例 | 真实死因(全部归一) |
|---|---|
| smoke#2/#3/#4(9-10min 死) | 42G+禁 swap 预算 < 60G 尖峰(条款,非参数) |
| E1/E1b/E1c/E1d(24-26min 死) | exploratory port clearance build 爆炸(py-spy 实锤,独立事实) |
| 今日 A/B 四刀+基线(全绿) | 62G 预算 ≥ 尖峰需求;参数只影响 wall(fixed +3.6%/p3 +27.8%/s3 +14.2%/组合 +26.4%) |

### 派生修订(本批全落)

1. **PIC-7 改判**:「默认参数病态归因」→已归因关闭;生产默认参数在修订条款下可用(wall 代价 +26%),通电对照可直接用生产默认形态,不再依赖原型参数 env 续命。
2. spike GO 效度注脚 #4 减负:默认参数可用性不再是独立前置,仅剩 wall +26% 的性能注记(优化机会,非阻塞)。
3. memory 卡 c1-solve-peak-memory-truth 同步(参数无病态)。
4. M5 线下一步:参数病态线关闭;M5 回到性能收敛主线(probing3 的 +27.8% 是最大单变量代价,默认组合 +26.4%——参数调优的收益面已量化,是否追优先级归 roadmap 排期)。

## 附:大 anchor(70×19)修订条款重测(2026-07-11 01:10)

harness 直建 `--ghost 70 19` @62G 预算+原型参数:**INFEASIBLE@557.5s**(build 25.4s,branches 4,731,094,尖峰 39.9G RSS+17.1G swap=57G 域,swap 正常吸收)。三个推论:

1. **70×19 的正确求解结果就是 INFEASIBLE**(266 mandatory 下该矩形放不下)——不存在「解不动」问题。
2. **smoke#1 死亡真相补全**:当年 9min47s 撞死于禁 swap 旧条款,离 INFEASIBLE 判决(9.3min)只差 ~30s——campaign 本会正常排除该候选推进。`07_batch1f_evidence.md` 的「本机大 anchor campaign 现阶段不可行」结论作废。
3. **本机真 campaign(不限 anchor)在修订条款下预期全程可行**:frontier 大候选逐个 INFEASIBLE 排除(~9min/57G 每个)→ 小候选出解(~9min/60G)。下一步=修订条款下 campaign 端到端冒烟。
