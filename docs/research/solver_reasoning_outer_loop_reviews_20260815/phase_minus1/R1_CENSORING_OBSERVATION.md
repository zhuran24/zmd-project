# Phase -1 r1：终态收据删失观察

> **运行目录：** `.artifacts/solver_reasoning_outer_loop_phase_minus1_20260815/phase-minus1-r1-20260815/`
> **终态：** `.DONE`，`EXIT_CODE=0`；开始 `2026-08-15T14:55:38Z`，结束 `2026-08-15T15:22:42Z`。
> **协议根：** `2bd28a9848a1b247a96ca2c34b1f83782f2cda11`。
> **执行 harness：** `054216951c8375d1ac5ae7ec7a497c4e72de7ea9` 中的 `phase_minus1_harness.py`。

## 结果

- corpus admission：9/9 admitted；6 个预注册旧 arm-off 样本按 `AMBIGUOUS_OPTIONAL_STORAGE_BOX_MIGRATION` 排除；
- 9/9 fixed layouts 均在 180 秒 end-to-end watchdog 下记为 `WALL_TIMEOUT_END_TO_END`；
- uncensored terminal：`0/9`，未达到协议要求的 `6/9`；
- 所有删失均保持 `terminalStatus=UNKNOWN`，没有被写成 `INFEASIBLE` 或死因家族；
- D3 未触发，D4 未开；
- organic D2 receipt：0；
- injected D2 canary：成功走通 registry→resolver→consumer，selection nogood 含 285 个 literals，第一次和第二次 FEASIBLE selection digest 不同，故 `effect=true`；第二解仍 FEASIBLE，分类为 `EFFECT_NO_TERMINAL`。

## 这轮证明了什么

1. **删失纪律有效。** wall timeout 没有污染成无解结论。
2. **D2 consumer 基本链可达。** injected canary 证明研究侧 selection feedback 能被登记、解析并由 `PortBindingModel.add_nogood_cut` 消费，且确实改变下一 binding selection。
3. **r1 的终态-only receipt 形态不足。** 子进程在 180 秒内没有结束时，父进程只能保存空 counters/events；无法区分 binding build、binding selection 循环、routing precheck 或 routing solve 热点，也无法收割已经发生的 organic failure。

第 3 项是证据可观测性缺口，不是数学死因。r2 只增加每个昂贵阶段的原子 progress receipt，并在 watchdog 时保留已发生事件；它不改变 corpus、discovery/holdout、20/30/180 秒预算、worker、seed、无 ALT_CAP 口径、指标或阈值。

## 小型工件身份

| 文件 | SHA-256 |
|---|---|
| `CORPUS_ADMISSION.json` | `8ec8e7daf36d11265d4be629a0f8f5addc33ada53c757ac8b816132bee54ff1f` |
| `D1_DEATH_SPECTRUM.json` | `11aef8a522e30767ea4919e66611141e9cd6698a0028a1660226f26b2a4cc552` |
| `D2_INJECTED.json` | `ab11acdcf3915c3646ac0f9b595451180b58a6fb4a7736e9e98e932695829755` |
| `D2_REACHABILITY_MANIFEST.json` | `3b8643cba21a1e78019844f52925b8862eb7698db6398f36882bda831e3de041` |
| `BATCH_SUMMARY.md` | `60cea8fb22fc5d45230ec16304e1fdef9d6d8a582ee67747b37b8305e6051d26` |
| `full.log` | `8d5e571ce0ef323153c32f68a2dba190f69e6ed2691100d402f0e23b12bf72b5` |

## r1 判词

`INCONCLUSIVE / OBSERVABILITY_HARDENING_REQUIRED`。

这不是对接口可压缩性的 NO-GO，也不是 GO。r1 被 9/9 wall censor 截断，唯一可采纳的正向信号是 injected consumer effect；organic 触达与死因谱仍待 r2。
