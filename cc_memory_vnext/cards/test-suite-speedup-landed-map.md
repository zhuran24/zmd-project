---
id: test-suite-speedup-landed-map
kind: decision
title: 2026-07-04 测试套件结构性提速已落地(快 lane 十几分钟→~5.5min,slow 登记 40→19)+ 剩余提速项收编进 PR2 深化主线四阶段的绑定排期
summary: 五维诊断+30 方案对抗审查后分两波落地(commits 53368b3/5151859/1202225/d4ca5be):golden 重生成测试改 size+SHA256 字节比对(69s→1.9s);test_run_supervisor_seal 改最小骨架+测试层 fake sealer(63.8s→3.1s,真 seal 哨兵在 test_p1_2_supervisor_pr1);B5A 新增 from_inspection 复用入口(4 项 fail-closed 来源校验,默认入口不变);新基建 artifact_pack_support.py(45MB 工件 session 缓存+测试侧轻 loader)/certified_surface_fixtures.py(golden surface 一次构建+clone)/select_tests_for_paths.py(codegraph affected 驱动的 advisory 选择器,锁面 fail-closed 回 FULL);IP e2e 拆 stage+纯 assembly(39.2s→7.9s);conftest slow 登记按无并发串行 --durations 全量对时 40→19 条(删 2 条 collect 不到的过期 nodeid)。剩余提速项已决定不再独立推进,全部绑进 PR2 深化主线:批 2a 带纯核心抽取(resume 清洗/frontier 投影+replay projection),批 2b 带 outer_search 非授权接缝(批后收 306s 巨无霸——已收,2026-07-07:实际改法=砍 max_attempts 64→8 而非用接缝,重放降级链是被测对象不能绕、能省的只有重复次数;306s→42s,commit 02f0f62,慢 lane ~20min→~16min),#5-F spike 带 fused child 固定税实验(判据:第二 child 固定税 <3s 提速价值不成立/≥10s 成立),#1 吞掉 l0-snapshot 拆分+lazy import。依据:60 sinks 名单确认 outer_search/exact_campaign/certified_frontier/benders_loop 全是 sealed 文件,独立小批=每批白付一次 reseal。
scope:
  domains:
    - test-infrastructure
    - conftest-slow-registry
    - pr2-deepening-mainline
  paths:
    - src/tests/conftest.py
    - src/tests/artifact_pack_support.py
    - src/tests/certified_surface_fixtures.py
    - src/tests/test_run_supervisor_seal.py
    - src/tests/test_preprocess_golden.py
    - scripts/select_tests_for_paths.py
    - scripts/run_industrial_planner_single_base_e2e.py
    - src/search/phase3b/b5a/b5_anchor_sprint.py
  symbols:
    - _SLOW_TEST_NODEIDS
    - build_phase3b_b5_anchor_sprint_summary_from_inspection
    - load_project_instances_and_rules
    - assemble_single_base_e2e_result
status: active
priority: P1
triggers:
  intents:
    - modify-tests
    - run-pytest
    - retune-slow-registry
    - plan-pr2-batch
    - investigate-slow-tests
  keywords:
    - pytest
    - slow
    - conftest
    - _SLOW_TEST_NODEIDS
    - preflight
    - 慢测试
    - 提速
    - fixture
    - supervisor_seal 测试
    - B5A
    - from_inspection
    - artifact_pack_support
    - certified_surface_fixtures
    - select_tests_for_paths
    - 批 2a
    - 批 2b
    - fused child
  negative_keywords: []
  paths:
    - src/tests/conftest.py
    - scripts/select_tests_for_paths.py
  symbols: []
  # 2026-08-03 终局:本卡退出 error_regex 定向召回,空表是刻意的、别再填。
  # 两轮收窄的账:裸 "deselected" 出现在【每一条】pytest 汇总行里、跑绿也弹
  # (普查 §3.5 第二噪声源,68 命中);收窄成"命令语境 + 汇总行真有 failed"后
  # 剩 8 条,复核发现里面含父/子转录镜像重复、且至少一条只是 grep 读旧红日志;
  # 再锚定调用形态后仍有绿跑误判(外层 `1 passed` 里嵌套一句 `2 failed`)与
  # 多类漏报(绝对路径 pytest 入口、带引号的环境变量前缀、`2 errors` 汇总)。
  # 历史真阳=0。普查 §3.5 的总账(39 次唯一注入里 30.8% 自触发、53.8% 良性输出、
  # 真阳 3 次、唯一一次被采纳的触发本身还是假阳性)说明这是个高假阳机制,
  # 正确处置是退出赛道、不是继续雕正则。
  # 本卡其余触发面(keywords / intents / paths / examples)全部保留:改测试、
  # 排 PR2 批次、retune slow 登记时照常靠意图/关键词召回。
  error_regex: []
  examples:
    - 为什么 slow 登记只剩 19 条了
    - 给新慢测试登记 slow
    - 排 PR2 批 2a/2b/#1 的批面
    - test_run_supervisor_seal 为什么不跑真 seal 了
activation:
  layer_hint: L1
  must_know: false
  reason: 其他线程改测试/排 PR2 批次时若按旧认知(46 条 slow/真 seal 在 run_supervisor_seal/提速线独立推进)会跑偏;三个实测坑(sealed 毒化/并发 pytest 假红/golden clone 绑定)不知道会白费排查。
provenance:
  op: record
  reason: 2026-07-04 测试提速线(5 诊断+30 对抗审查 workflow → 两波实施)完整落地后,与 owner 确认剩余项收编主线的绑定排期。
  evidence:
    - "commits: 53368b3(第一批 16 文件)/5151859(CLAUDE.md 对齐)/1202225(IP e2e)/d4ca5be(slow retune)。"
    - "preflight --full 最终态 19/19 PASSED,快 lane 3819 passed/338.97s。"
    - "slow lane 无并发串行扫描 41 条 859s;2 条失败(sink_replay_authority/parallel_scheduler)无并发重跑 2 passed 46.7s,系并发 pytest 挤压假红。"
    - "60 sinks 名单核实(data/proof_obligations/p1_2_proof_obligations.json close_kernel_contract.sink_files):outer_search/exact_campaign/certified_frontier/benders_loop/candidate_proof_replay/terminal_fixed_witness_*/pr2_l0_* 全在列;b5_anchor_sprint.py 不在(故 B5A 改动未触发 reseal)。"
    - "2026-08-03 普查 §3.5:triggers.error_regex 原为裸 [\"deselected\"],该词在每条 pytest 汇总行里都有(`44 passed, 3525 deselected`),跑绿也弹=第二大噪声源。收窄为 pytest 命令锚点 + 汇总行含 failed;跨 59 份转录 6260 条 Bash 结果复算 68 命中 -> 8 命中。"
    - "2026-08-03 审查复核:那 8 条里含父/子转录镜像重复,且至少一条只是 grep 读旧红日志的文本、不是真跑 pytest——所以「8 条全是真红 pytest 运行」不成立。二次收窄改成锚定调用形态(`-m pytest` 或命令头就是 pytest,且命令头不是 grep/rg/sed/cat/tail/head 这类读取工具),读旧日志整类不再命中。"
    - "2026-08-03 收尾(本卡 error_regex 归零):二次收窄后仍被实测打回——外层跑绿(`outer: 1 passed`)但输出里嵌了一句 `inner: 2 failed` 会误判成红测并消费 seen-once 账本,而绝对路径 pytest 入口、带引号的 PYTHONWARNINGS 前缀、`2 errors` 汇总又整类漏报。两轮收窄下来本卡历史真阳仍是 0,遂退出 error_regex 通道。"
  updated_at: "2026-08-03"
---
2026-07-04 测试提速线全部落地并收编。**其他线程必须更新的认知**:

== 已改动(行为影响事实) ==

1. **slow 登记 40→19 条**(conftest `_SLOW_TEST_NODEIDS`,commit d4ca5be):按无并发串行全量 --durations 对时,移出 21 条实测 <8s(inspector 11 条 4-7s、delivery_manifest 7 条 1.2-1.9s、b5a summary、v86/v89、v97),删 2 条 collect 不到的过期 nodeid(`test_campaign_resume_reconstructs_frontier_without_reinvoking_solver`、`test_parallel_and_serial_preserve_same_best_certified_result`——函数已不存在)。v98 保留(call 亚秒但 golden fixture setup 单独 ~23s)。快 lane 现 ~5.5min/3819 条;慢 lane 结构 = 19 条 10-67s(306s 巨无霸 test_aspect_ratio_sliced_search 已于 2026-07-07 收掉:max_attempts 64→8、306s→42s,commit 02f0f62,慢 lane 全程 ~20min→~16min)。
2. **test_run_supervisor_seal.py 不再跑真 seal**:现为最小 CANDIDATE_PROPOSED 骨架+测试层 monkeypatch fake sealer 的 CLI wiring 测试(63.8s→3.1s)。**真 seal E2E 哨兵在 test_p1_2_supervisor_pr1.py**(直接调 campaign.supervisor_seal() 的用例)。
3. **B5A 新入口** `build_phase3b_b5_anchor_sprint_summary_from_inspection`:4 项来源一致性校验(inspector source 常量/project_root/campaign_state display path/certified_surface source 常量),任一不匹配 fail-closed 回退自建 inspection;默认入口零改动。b5_anchor_sprint.py 不在 sealed 名单,改它不触发 reseal。
4. **新测试基建**:`src/tests/artifact_pack_support.py`(45MB candidate_placements 的 strict 缓存,deepcopy/readonly 两套 API+测试侧轻 loader `load_project_instances_and_rules`——**刻意不放 master_model.py,那是 sealed 文件**);`src/tests/certified_surface_fixtures.py`(golden publishable surface 一次构建+clone_surface_tree);`scripts/select_tests_for_paths.py`(advisory 选择器:codegraph affected 算闭包,碰锁面/checker/frozen 工件一律 exit 2 建议 FULL,不进 CI 硬门)。
5. golden 重生成测试(test_preprocess_golden)的 candidate_placements 比较改字节级 size+SHA256(69s→1.9s,比语义比较更严格);IP e2e 拆真实 stage+纯 assemble_single_base_e2e_result(39.2s→7.9s,drift/ceiling 为 synthetic_for_test 合成单测,唯一真 workflow 哨兵=writes_successful_active_contract_bundle)。

== 三个实测坑(不知道会白费排查) ==

- **sealed 文件改动毒化并行测试**:往 close-kernel sealed 文件加纯新增函数也会让 runtime `validate_locked_p1_2_close_kernel` fail-closed→同工作树所有走真实认证链的测试集体假红(实锤:master_model.py 加函数→supervisor_pr1 真 seal 哨兵 UNPROVEN,还原即绿)。看到认证链测试莫名红,先查 sealed 文件是否有未 reseal 改动。
- **并发 pytest 挤压假红**:与 slow lane 扫描/大套件并发跑 pytest 会挤 CP-SAT/L0 子进程超时 fail-closed(实锤:sink_replay_authority+parallel_scheduler 扫描中失败、无并发重跑即绿)。本机 hook 已拦,扫描类操作要独占跑。
- **golden surface clone 的绑定约束**:克隆 surface 树到新 project_root 后真实 verifier 在 terminal-evidence 层直接 fail-closed(证据与 project_root 绑定)——clone 模式只适用于"负例只 mutate 后仍走真实验证"的场景(v98 已用),不能给 inspector 正例省 publisher 构建;推广前要先解决绑定问题。

== 未改动:剩余提速项收编主线(绑定排期,不再独立推进) ==

依据:60 sinks 名单确认这些项动的全是 sealed 文件,独立小批=每批白付一次 reseal。绑定:**批 2a(#2+#3)** 带 resume 清洗/frontier 投影纯核心抽取+replay 纯 projection 核心(同文件面 exact_campaign/certified_frontier;顺序=先抽核心配测试再改 read-once 语义,给主线当安全网);**批 2b(B2 独立枚举)** 带 outer_search 三个非授权编排接缝(solve_candidate/run_parallel_wave/session_factory,不注入 sink/witness projector),批后收 306s 巨无霸测试改造(测试文件不触 reseal);**#5-F spike** 带 fused child 固定税实验(取证脚本量两个 child 的 spawn→验证起点固定税,判据 <3s 不成立/≥10s 成立;本机可测,CachyOS 就绪后校准);**#1** 吞掉 l0-snapshot 拆分(浅层版自动覆盖)+lazy import(import 拓扑重塑后大半消解)+若实验成立的 fused child。搁置:mini artifact pack/cache-reset-scope/sharded sidecar(收益小或未证实)。
