---
name: workload-latency-bound-not-bandwidth
index_summary: "BCP 指针追逐 + 280K pose L3 spill. **别再提带宽/多通道**."
description: "项目 CP-SAT workload 绝对是 latency-bound 不是 bandwidth-bound. Claude 之前判断带宽错了, GPT/Gemini 两轮独立 verdict 都推 latency. 未来 hardware 调优 prioritize DDR5 timings / Single Rank / Ring Bus, 不是 channel 数 / bandwidth"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

2026-05-21 用户提及历史: GPT 早期说项目需要内存延迟, Claude 当时说带宽, 系统优化按带宽假设做了一堆 host-level 调优. Gemini round 10 独立 verdict (fat-context, 不知道 GPT/Claude prior judgment) confirm GPT 对 Claude 错 — **绝对 latency-bound**.

## Workload 特征 (为啥 latency-bound)

CP-SAT 是 SAT-heavy 引擎:
- **BCP (Boolean Constraint Propagation)**: two-watched literal 机制做**随机指针追逐**, CPU 预取器死穴, IPC 0.5-0.8, 大部分时间 stall 等内存
- **Pricing CP-SAT 60-70% CPU time** + **Master CP-SAT** + **B&B tree search 5%** 都受 BCP 主导
- 280K pose registry (dict hash lookup) 是 working set >100 MB, **必然 L3 cache spill** (i9-13900KS L3 仅 36 MB)
- 每 L3 miss → 70-90 ns DDR5 access, 千万次随机 hash 累计延迟惊人

RMP LP relaxation (GLOP simplex) 是 bandwidth-bound matrix-vector ops, **但只占 1-5% CPU time**, 不是瓶颈, 优化没意义.

## "美丽的误会" — 现有 OS 调优 happens to be latency-friendly

Claude 按 bandwidth 假设做的调优实际全是 latency 优化:

| 调优 | Claude 当初理由 | 实际效果 |
|---|---|---|
| THP=always | 大块连续内存吞吐 | **减 TLB miss + Page Walk 延迟** |
| mitigations=off | 减少系统调用开销 | **减分支预测失败 / Pipeline Flush 惩罚** |
| jemalloc + PYTHONMALLOC=malloc | 高效分配 | **减内存碎片 → 提空间局部性 → 减 L3 miss** |
| isolcpus=0-7 + nohz_full=0-7 | P-core 独占 + 减 timer tick | **防 cache trashing (L1/L2 不被其他进程污染)** |
| rcu_nocbs=0-7 | RCU callback 移 E-core | latency 友好副作用 |

也就是说**当前调优没浪费**, 但是 **lucky alignment**, Claude 没 understand. 实际损失在哪? **未来调优方向** Claude 会推错: 比如推"多通道服务器内存"(Xeon Mesh 高延迟灾难) / 不 prioritize DDR5 timings / 选 dual rank (interleaving 提带宽但电气压力大时序压不下去).

## 真正 latency 调优方向 (按 ROI 排)

1. **DDR5 timings 压到极致** (比频率重要)
   - 目标: DDR5-7200~7600 MT/s + CL34/32 (vs 当前 default CL40+)
   - **tREFI 拉高** (刷新间隔) — 长尾延迟改善显著
   - tRFC 压低
   
2. **Single Rank 内存** (2×16GB 或 2×24GB Hynix A-die)
   - 双 Rank interleaving 提带宽但电气压力大, 时序压不下去
   - 项目要单次低延迟不要并发吞吐

3. **Ring Bus 频率超频** (i9-13900KS 单片 Ring Bus)
   - 当前 default ~4.5 GHz, 超到 5.0-5.2 GHz
   - 缩短 L3 cache + 内存控制器搬运延迟
   - 280K pose 频繁穿透 L3, Ring 频率收益立竿见影

4. **不需要 SNC** (Sub-NUMA Clustering)
   - SNC 是 Xeon Mesh 架构特性 (Sapphire Rapids 等)
   - i9-13900KS 单片 Ring Bus 不需要也不存在

## 我以后写啥要避免

❌ "项目需要更高带宽 / 多通道内存 / 高 throughput memory"
❌ "买 EPYC / Xeon 服务器内存系统"
❌ "选 dual rank 内存 interleaving"

✅ "项目是 latency-bound CDCL workload"
✅ "DDR5 timing tuning > frequency tuning"
✅ "Single Rank Hynix A-die 优先"
✅ "Ring Bus 超频 + tREFI 拉高"

## 实证 reference (Gemini 给的)

- Armin Biere (CaDiCaL/Kissat 作者) SAT solver memory performance paper
- Knuth TAOCP Vol 4 Fascicle 6 SAT analysis
- Intel VTune profiling reports CDCL 80%+ CPU time in BCP
- 待查证: Gemini 给的 specific paper 引用没 ID, 标记 "需查证"

## 跨域 implication for design B

B feature-level engine 也用 CP-SAT 作 placement / binding / routing oracle. Bitset kernel 选 Rust/C++/numpy 也要按 latency-bound 思路:
- Rust pyo3 / C++ pybind11 — native code 直接 access bitset, latency 最低
- numpy — Python list/array 带 overhead, latency 显著高 (但 bandwidth OK)

如果 design B 跑 latency-sensitive bitset ops, Rust/C++ 优先 numpy.

[[gemini-better-at-natural-tone]] 同 round Gemini 给的 verdict 也确认我之前对 register 的判断也 systemic 偏差. 两件事 cross-domain: Claude 系统性偏 structured/正式 + bandwidth-thinking — 都是 RLHF bias.
