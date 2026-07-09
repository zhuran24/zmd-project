# A 批 0：C6/C1 供电编码原型头对头（2026-07-09）

> 上游：M6 诊断（`../p1_3_m6_diagnosis_20260709/07_final_diagnosis.md`）+ A 设计定案（`00_design_decision.md`，主刀 C6/备刀 C1）。
> 原型 = 测量专用 monkeypatch（`c6_encoding_patch.py`/`c1_encoding_patch.py`），不碰 sealed，结果绝不回流 certified。
> C1 patch 经 codex 独立审查抓出 clone 路径致命 bug（`02_c1_patch_codex_review.md`），v1 修复后才产生有效数据。

## 结论：备刀 C1 破墙——项目史上第一个完整问题 master 解

**b0_4r（C1 v1 自由搜索 w6 1800s）：OPTIMAL @541.3s**（495 万分支 / 1077 冲突）。
266 mandatory + storage box + 26 杆 + 6×6 ghost（anchor (55,50)）完整布局，
独立覆盖复验（G0.4 门，照终端验证器语义、不 import 生产码）四项全过：
边界 / 两两不重叠 / ghost 全空 / 220 需电设施供电全覆盖；**unforced 记录=0
（每杆都是某设施唯一覆盖者，直接满足 exact_campaign.py:1243-1253 最严条件）**。
解在 `b0_4r_free_c1_w6.json.solution.json`，复验脚本 `03_b0_4r_independent_verify.py`。

三个直接推论：master 首解之墙破（原机 24h campaign 零候选 → 9 分钟 OPTIMAL）；
M6 头号悬案「供电可行布局存在性」关闭（存在，且可带 6×6 ghost）；M5 A/B 战场解锁。

## 完整结果表

| Cell | 编码 | 场景 | 结果 | 关键数 |
|---|---|---|---|---|
| （witness 基线） | witness | 钉死 anchor132 w12 | INFEASIBLE @94.5s | M6b-B |
| （witness 基线） | witness | 自由 w12 全阶梯 | 全 UNKNOWN | M5 14 cell |
| b0_1 | C6 v0 | 钉死 单核 300s | UNKNOWN | 冲突率 0.07%→10.9%（traction ~150×） |
| b0_1b | C6 v0 | 钉死 w12 600s | INFEASIBLE @238.6s | witness 的 2.5 倍慢（钉死场景 element 不弱，天然偏袒 witness） |
| b0_2 | C6 v0 | 自由 w12 1800s | UNKNOWN | 37,113 conflicts（~90×） |
| b0_2b | C6 v0 | 自由 w12 7200s | UNKNOWN | 6.66M br / 23,299 conflicts——学习率超线性赌注未中 |
| b0_3/b0_4 | C1 v1 | 钉死/自由 w12 | **OOM ×2（exit 137）** | solve 期传播态膨胀 >46GB（2min/12min 死） |
| b0_3r | C1 v1 | 钉死 anchor132 w6 600s | INFEASIBLE @37.8s | **branches=0 conflicts=0 纯传播判定**（witness 94.5s 的 2.5×，C6 的 6.3×，还让 6 个 worker） |
| **b0_4r** | **C1 v1** | **自由 w6 1800s** | **OPTIMAL @541.3s** | **破墙**；独立复验 PASS |

## 判读

1. **C1（杆侧 pose 布尔 + 全局 cov 通道）完胜**：钉死判定纯传播秒杀、自由搜索 9 分钟 OPTIMAL。
   B1 34× 历史证据的机制内核（静态覆盖系数 + 可学习布尔）在坐标表示下复现成立。
2. **C6（witness 原地 pairwise 重编码）判负但机制诊断兑现**：冲突率 90-150× 证明「element
   传播盲区」定性正确，但 per-pair 几何 enforcement 的节点代价吃掉收益，2h 不破墙。
3. **C1 的代价条款（批 1 必须带上）**：w12 下 solve 期内存 >46GB OOM 两连——与考古出土的
   witness「30GB 真凶=solve 期传播膨胀」（`01_cachy_archaeology_b1_evidence.md`）同类；
   w6 全程温和。生产化需 worker/内存条款或参数调优。
4. C6/C1 玩具等价各 PASS（C1 含 ghost clone 全链 4 场景，见 `batch0_toy_equivalence_c1.py`）。

## 批 1 建议（呈 owner）

胜者=C1。批 1 = C1 certified 化：杆侧 pose 布尔进 `exact_coordinate_master.py`（完整 reseal 连锁
+ benders_loop canonical env 面 + EXACT_* 三件套）+ 池完整性 fail-closed 断言 + 解级 dominance
剪杆步（对抗审查修订一；b0_4r 实测 unforced=0 说明 CP-SAT 自发给出极简杆集，剪杆步可能常为
no-op 但仍必须在链上）+ 内存条款（worker 上限或 RSS 监控）+ 新旧编码等价性单测。

## 附：b0_5 witness 交叉验证（2026-07-09 深夜补）

把 b0_4r 布局钉进无 patch 生产 witness 编码、放开杆让它自己找覆盖方案：**UNKNOWN @600s**
（7.26M branches / 7087 conflicts，`b0_5_witness_crosscheck.json`）。witness 连「验证已知可行解」
（钉布局搜杆）都溺死——M6 病灶的又一佐证；交叉验证通道因此不可用，首解的语义背书以独立
覆盖复验（`03_b0_4r_independent_verify.py`，终端验证器同语义）为准。复验脚本本身已列入
GPT Pro 外审对象。
