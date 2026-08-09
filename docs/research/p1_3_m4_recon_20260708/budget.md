# budget（专题⑦：cut 总量预算 + CutStore eviction）— recon-budget agent 两段合并

## 硬事实清单

| # | 事实 | 出处 |
|---|---|---|
| H1 | 生产 attach 路径完全不经过 CutStore——_maybe_attach_framework_cuts 直接 generate→validate→step_8 | benders_loop.py:7614-7665 |
| H2 | CutStore 没有 remove/eviction/容量上限；quarantine_cut 保留 cut 在 self.cuts（audit） | store.py:177-184；全类 114-331 |
| H3 | CutStore 磁盘持久化显式 defer 到 Phase 1.3 P1.21（当前纯内存） | store.py:27-30, 71-72 |
| H4 | master CP-SAT 约束 model.Add 后无法删除 | exact_coordinate_master.py:7200 |
| H5 | master 有累计计数器 coordinate_region_capacity_cut_count | exact_coordinate_master.py:7197-7201 |
| H6 | attach stat cut_framework_attach_last 只记最后一次（覆盖，非累计） | benders_loop.py:7657-7664 |
| H7 | attach 只在 binding_infeasible / routing_exhausted 两拒绝点触发 | benders_loop.py:6046-6048 / 7179-7181 |
| H8 | master applied=False → step_8 raise RuntimeError（fail-closed） | lifecycle.py:1180-1184 |
| H9 | PROJECT_LOCK 无 "V82" 字面；V82=README 记载+checker 结构性封堵，非锁条款 | grep 全仓 |
| H10 | 裸实现 50% 退化线 ~2.5-3K cut；literal 复用后外推 ~15-20K | verdict.md:85-90, 128-129 |

## CutStore 接口

- add_cut(cut, *, cell/group/pose/commodity/region_keys, initial_state="held")（:114-175）——默认 held，须显式 reactivate_cut 才 active（GPT pro v5 P0-2 防 silent-attach race）
- quarantine_cut(cut_id, reason)（:177-184）/ hold_cut（:186-193）/ reactivate_cut（:195-201）/ is_active（:203-208）
- watcher 查询 cuts_affected_by_{cell,group,pose,commodity,region,ghost}（:212-228）
- on_ghost_rect_changed（:232-296）——旧 ghost cut→hold；新 ghost cut→replay_cut 全 validator（:276-280）
- 无 remove/eviction/上限；持久化 replay：checker 12571-12581 强制 persisted exact_safe_cuts=telemetry 非 proof（"certified runs must regenerate cuts"）

## V82 边界

- README.md:526：候选 domain h<=w canonical 化 vs master 朝向敏感→半 domain 穷尽 + 伪造 checkpoint cut
- checker 结构封堵：oriented domain（:12394-12396）+ cut replay sealing（:12571-12581）
- 「跨 attempt 复用=fresh revalidated attach」出处 = m3 落地卡:75；含义：不得把落盘 cut 当证据 replay，必须当前进程重生成+全套重验。预算只能约束当前 attempt 内活跃规模。

## 计数现状

- attach 端：build_stats["cut_framework_attach_last"]={"trigger","iteration","generated","attached"} last-only
- master 端：coordinate_region_capacity_cut_count（累计，仅 F1）+ coordinate_region_capacity_last_cut 快照（:7202-7207）

## 预算数字（verdict.md）

- 裸 50% 线 ~2.5-3K；literal 复用后 ~15-20K（5K 挡劈叉 -88%）
- 建议：千级起步；eviction 最简版提前到 M4；配 F5 telemetry 10^5 撞墙/10^3 工作；放宽到 10K+ 须 before/after 复测（:133 "不取消预算"）
- whole 型每条 2-8s 但生产个位数条，非瓶颈

## 落点裁决

- **方案 A（推荐）**：_maybe_attach_framework_cuts 入口（:7623 后）count 检查，读 master 累计计数，>=预算 → return 0 + stat 记 budget_exhausted。单文件最小改动。
- 方案 B（CutStore cap）否决：生产不经 CutStore（H1）
- 方案 C（master add 端拒绝）否决：applied=False → RuntimeError 崩链（H8）
- **eviction 语义 =「预算满即停发」是唯一 sound 最简版**：①CP-SAT 约束删不掉（真 eviction 须 master rebuild 38.9s+27-54s，归 M5）②CutStore held/quarantine 对 master 活跃约束零作用③F1 类 valid inequality 停发只弱化剪枝永不损 soundness

## 风险

1. CutStore 不在生产路径（最大陷阱）——要让它成 SoT 需独立架构改动（attach 改经 store）
2. 计数器口径：M4 逐族接线前先立统一 active framework cut 总计数（现仅 F1）
3. 预算必须在 step_8 之前拦截，不得借 master False 实现（触发 fail-closed 崩溃）
4. 不得设计跨 attempt 持久缓存（撞 checker 12571-12581）
5. 千级起步安全锚点；放宽须复测背书
6. 方案 A 不碰 sealed 常量，风险最低
7. persisted_exact_safe_cut_replay_* 两字符串行号未定位（grep 被 hook 拦），存在性由 checker 强制坐实
