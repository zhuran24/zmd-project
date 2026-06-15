---
name: precompact-and-self-inject-ui
description: precompact skill 最终设计 + selfguard 自注入新机制(即时模式绕 Stop hook / code-3 桌面弹窗 / 双ESC清打字草稿 / 等草稿轮询)。2026-06-14 与 owner 共建并实测。
metadata: 
  node_type: memory
  type: reference
  originSessionId: 20690dc4-0860-4f42-a5a5-e1cccbd7b8d7
---

2026-06-14 与 owner 一整轮共建 + 实测的 CC 自压缩/自注入机制。selfguard = `C:\Users\22957\cc_watchdog\cc_model_selfguard.ps1`(用户级, 不在 zmd 仓库)。skill = `~/.claude/skills/precompact/`。

## precompact skill 最终设计(简化版, owner 2026-06-14 裁决)

压缩前要做一次**专门**的记忆树更新, 但**必须由一条独立提示词驱动一个单独回合** —— 塞进 skill 让 CC 本回合顺手做 = **CC 会偷懒**(owner 实证判断)。所以 skill **只做一件事**:
- **即时注入一条**: `-SendNow "要压缩上下文了,更新记忆树,把该记得都记一下"`。这条作为新 user 回合到达, 驱动**专门的记忆更新回合**。
- **不排队第二条、不用 seq worker。** `/compact` 由那个记忆更新回合里 **CC 自己在更新做完后 `-SendNow "/compact"`**(CC 本就在那回合, 知道何时做完)。
- **不清 goal、不恢复 goal**: 即时模式 `-SendNow` 不挑窗口空闲, 有 standing-goal Stop hook 挂着也照样注入(注入文本作 queued 输入, 优先于 Stop hook 提交)。
- **历史弯路(别再绕回去)**: 曾设计 `-SendSeqWorker` 排 `[记忆, /compact]` 两条 + 清/恢复 goal —— owner 一句点破是过度设计(要顺序就得等空闲会被 Stop hook 挡; 即时模式又压根不用清 goal)。seq worker 代码留在 selfguard 但 precompact 不用。

## 关键机制真相(实测, 2026-06-14)

- **Stop hook 挡空闲注入**: standing-goal Stop hook 会在 CC 每次停下的 ~8s 内把它拉回, 窗口**永远 idle 不到 8s** → 任何**等空闲的注入**(`-Send` 排程 worker / seq worker)**永不注入、且不报错**(log 停在"已就位")。**即时 `-SendNow` 绕开它**(不等空闲)。**离线自主压缩恰恰有 goal 挂着**(CC 朝 goal 自跑), 所以必须即时模式 —— "离线=没 Stop hook" 是错的蠢话。
- **`-SendNow` 设/清 goal/发 /compact 都行**(都是注入 slash 命令; 必须 PowerShell 工具不走 Bash, 否则 `/` 被 MSYS 路径化)。
- **清空 owner 手打草稿要连按多次 ESC(实测 2~3 次)**, 单次 ESC 不清。记忆里旧说法"单 ESC 清"对**手打草稿不成立**(可能只对中断后还原回输入框的消息管用)。空输入框补 ESC 会开 rewind UI(铁律)。

## code-3 桌面弹窗功能(`-SendNow` 撞输入框被占时)

`-SendNow` 撞 code 3(输入框有 owner 草稿)→ 不再静默吃掉 → **派 detached WinForms 弹窗糊 owner 脸上**(`-InjectPopupWorker`): 置顶, [稍等]=消失不动草稿 / [立刻]=清草稿+注入。
- **launch 绝不用 `-WindowStyle Hidden`** —— 它会把 WinForms form 也隐掉/不显到交互桌面(form 建出来 ShowDialog 阻塞但看不见)。正解: **普通 launch + worker 内自隐控制台**(`GetConsoleWindow`+`ShowWindow SW_HIDE`)+ `SetForegroundWindow` 强拉前台 + `EnableVisualStyles`。(残: 黑窗一闪, 待用 CreateNoWindow 消掉。)
- **[立刻] 清草稿 = 自适应连发 ESC**: 发 ESC → 复查输入框 → 空了立即停(绝不对空框补 ESC), 最多 4 次。实测 3 次清掉。
- **`-WaitDraftThenSend` 轮询模式**: 测/演示弹窗路径时不靠定时猜时机 —— 轮询输入框, 连续 2 次检测到草稿才触发注入(→ code 3 → 弹窗)。定时延迟方案反复因 owner 没赶上打草稿失败(code=0 直接注入), 轮询彻底解决。

## 待办(owner "后面")
- 黑窗一闪 → CreateNoWindow / VBScript launcher 消掉。
- 这些机制的仓库侧投影(cc_context/memory 镜像)等并发会话结束后补(本轮仓库有并发会话, 只写了 harness 侧)。

关联 [[cc-api-watchdog]](自注入/-Send/-Context 主体) 与 [[verify-before-claiming]]。
