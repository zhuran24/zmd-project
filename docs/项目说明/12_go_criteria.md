# 12：GO、close 与证据词的稳定判读契约

> 本页定义状态词和判读边界，不陈述某个阶段当前是否已经关闭。当前 gate、义务与 owner decision 只看 [CURRENT](../CURRENT.md) 及其机器源。

## 1. 状态词不能互换

- **IMPLEMENTED**：代码路径已存在。
- **TESTED / VERIFIED IN THIS WORKTREE**：给定命令在给定 bytes 上运行并有退出码、日志和工作树身份。
- **MACHINE-CHECKED**：登记的 schema、guard、allowlist 或 obligation 与当前输入一致。
- **REVIEWED**：某个明确范围被 reviewer 阅读或复核。
- **OWNER-CLOSED**：owner authority 显式记录关闭。
- **CERTIFIED**：满足 `PROJECT_LOCK.md` 定义的完整终端铸造与发布链。

前四种证据都不能自动推出后两种。反过来，owner close 也不能抹掉仍存在的 soundness finding。

## 2. GO / close 的最小构成

一次阶段 GO 或 close 至少需要同时回答：

1. 被关闭的命题与 scope 是什么；
2. 哪些技术义务是必要条件；
3. 哪些验证在同一工作树实际运行；
4. 哪些 finding 仍开放，是否被明确排除在 scope 外；
5. 哪个 owner 或机器 authority 有权作出最终决定；
6. 后继阶段能做什么，不能把什么解释成已获授权。

具体清单属于相应 proof obligations、phase gate、spec 或 owner decision。本页不复制它们的当前值。

## 3. 常见 PASS 的正确含义

- obligation checker PASS：只证明登记义务与当前输入相符，不是全程序 theorem prover。
- allowlist checker PASS：只证明扫描到的点均有登记解释，不证明扫描范围外绝无路径。
- phase-gate checker PASS：可能只证明 fail-closed 状态自洽；是否允许进入下一阶段仍由 gate 字段与 owner decision 决定。
- pytest 或定点回归 PASS：证明相应测试在声明环境通过，不自动授予 release、数学结论或 production authority。
- review receipt / package seal：证明材料身份或审阅过程，不自动修改 owner gate。

## 4. 报告纪律

任何测试数、耗时、hash、gate 值、上下界或开关都必须引用机器源或 [CURRENT](../CURRENT.md)，不能作为本页的手写“当前值”。一次结果报告至少附：

- 命令；
- 工作树或输入身份；
- 退出码；
- 日志或收据路径；
- 未运行、超时和被排除的范围；
- 它明确不推出什么。

## 5. 权威坐标

- certified 与 release 边界：[`PROJECT_LOCK.md`](../../PROJECT_LOCK.md)
- 当前 gate 与 proof obligations：[CURRENT](../CURRENT.md)
- 稳定 claim / decision： [CATALOG](../CATALOG.md)
- 阶段未来工作与退出证据：[ROADMAP](ROADMAP.md)

迁移前包含旧阶段现态和历史测试数的正文已冻结为 [12_go_criteria_pre_phase3_20260812.md](../history/status/12_go_criteria_pre_phase3_20260812.md)。旧行号引用只解释为该快照；字节校验坐标见 [HISTORY](HISTORY.md)。
