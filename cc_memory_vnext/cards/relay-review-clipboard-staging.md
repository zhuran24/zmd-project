---
id: relay-review-clipboard-staging
kind: decision
title: 每轮 GPT Pro 外审 relay staged 后,把审包路径 + 全部提示词逐条放进剪贴板历史(Win+V),不是拼成一坨
summary: owner 定的固定操作(2026-07-02 round-18 起):每次外审包 + 提示词备好后,**不等 owner 开口**,把【审包 .7z 完整路径】和【每份提示词全文】各作为**独立条目**写进 Windows 剪贴板历史(Win+V 挑着贴),**不是拼接成一份**。写入序 = 倒序:提示词 N→…→1,最后写包路径,这样 Win+V 顶→底 = 包路径, 提示词 1..N(使用顺序)。技术要点:①Set-Clipboard 在沙箱下会**静默假成功**,必须 dangerouslyDisableSandbox + 每条写后回读长度验证;②首条可能竞态失败(回读 0),带重试;③条间隔 ≥600ms 让历史服务捕获;④历史对相同文本去重置顶,重跑安全;⑤前提 EnableClipboardHistory=1(本机已开)。
scope:
  domains:
    - external-review
    - workflow
  paths:
    - scripts/package_review_snapshot.py
  symbols: []
status: active
priority: P1
triggers:
  intents:
    - external-review-relay
    - stage-review-package
  keywords:
    - 外审
    - relay
    - GPT Pro
    - 审包
    - 提示词
    - 剪贴板
    - clipboard
    - Win+V
    - Set-Clipboard
    - review entry
    - round
    - staged
    - 打包
    - 7z
    - pr2_pkg
  negative_keywords: []
  paths:
    - scripts/package_review_snapshot.py
  symbols: []
  error_regex: []
  examples:
    - round-19 外审包和提示词都备好了,staged 等 owner 跑
    - 把这几份外审提示词放到剪贴板
    - 准备下一轮 GPT Pro relay
activation:
  layer_hint: L1
  must_know: false
  reason: 准备/宣布外审 relay staged 的时刻该想起这条,否则会等 owner 手动要、或把提示词拼成一坨放(2026-07-02 实发:先拼一坨被纠正为逐条)。
provenance:
  op: record
  reason: owner 2026-07-02 round-18 第 12 轮外审 relay 时确立;先拼接单条被纠正为逐条,随后 owner 明示"每次外审都这么做"并要求记入记忆。
  evidence:
    - "2026-07-02 round-18:6 份 pr2_5_round18_review_entry_{1..6}_*.md 逐条入剪贴板历史;首次沙箱 Set-Clipboard 静默失败(回读仍是旧内容)、首条竞态回读 0,重试后 6/6 OK。"
updated_at: "2026-07-20"
---
每轮 GPT Pro 外审 relay 的剪贴板 staging 规程(owner 固定偏好,relay 备好即做、不等开口):

== Linux 侧(CachyOS,2026-07-20 owner 确认)==
- 工具 = `wl-copy`;剪贴板管理器**有历史**(同 Win+V),owner 从历史里挑着贴。
- 所以**逐条连发即可,条间隔 ~2s**;不需要"先放路径、90s 后换正文"的延迟两段式(07-19/20 曾用过,owner 已明示不必)。
- 顺序同 Windows 口径:倒序写入(提示词 N→…→1,最后写包路径),历史顶→底 = 使用顺序。附件包 = zip(非 .7z)。

== 放什么 ==
- 【审包 .7z 完整路径】(如 `C:\Users\22957\pr2_pkg\zmd_pr2_5_roundNN_<hash>.7z`)——owner 用它在 GPT Pro 上传附件。
- 【每份外审提示词的全文】(如 `C:\Users\22957\pr2_5_roundNN_review_entry_{1..N}_*.md`)——一份一条,**不拼接**。

== 顺序 ==
倒序写入:提示词 N→…→1,**最后**写包路径 → Win+V 列表顶→底 = 包路径, entry_1 … entry_N,正好是 owner 的使用顺序(先传包、再逐条贴提示词)。

== 技术坑(2026-07-02 实测)==
1. **沙箱下 Set-Clipboard 静默假成功**——命令 exit 0 但剪贴板没变。必须非沙箱(dangerouslyDisableSandbox)执行,且**每条写后 Get-Clipboard 回读长度核对**。
2. **首条写入竞态**——可能回读 0(剪贴板服务初始化),每条带 ≤3 次重试。
3. **条间隔 ≥600ms**——让剪贴板历史服务来得及捕获成独立条目。
4. **相同文本去重置顶**——历史不会因重跑产生重复条目,重跑 = 理顺顺序,安全。
5. 前提:`HKCU:\Software\Microsoft\Clipboard` 的 `EnableClipboardHistory=1`(本机已开;若关闭需先提示 owner 打开)。

== relay 准备各步时长基线(2026-07-03 round-19 实测,checker 变大后的新常态)==
round-19 给 checker +769 行/新语义门后,凡"跑完整 checker"的测试全部变慢一个量级,别再用 round-18 前的旧经验判断"卡死":
- 打包解包自测(package_review_snapshot 内嵌 pytest):**~30 分钟级**(旧经验"几分钟"已作废);
- close-kernel 定向回归(test_p1_2_proof_obligations 等):394 tests ≈ **16 分钟**;
- preflight --slow-tests(slow lane):44 tests ≈ **16 分钟**(旧 13 分钟基线偏短);
- preflight --full 的 fast pytest:3741 tests ≈ 5.5 分钟(变化不大)。
等这些步骤时把等待器/超时阈值按上述放宽;进程活着且 CPU 在持续消耗 = 在正常跑,别 kill。

背景:外审 relay 流程本身(codex 本地审修 → GPT Pro relay、owner 仓库外手动跑、回传 union+triage)见 README 第 4/6 章;原项目 AGENTS.md 的 relay UI 约束**未随交付副本迁入**,故这条操作规程记在本卡。
