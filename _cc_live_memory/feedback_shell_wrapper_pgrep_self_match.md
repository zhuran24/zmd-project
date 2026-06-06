---
name: shell-wrapper-pgrep-self-match
description: "shell wait wrapper 用 pgrep -f \"pattern\" 时, wrapper 自己的 cmdline 含 pattern 会永远匹配自己导致 until 死循环; 用 PID wait / 更精确 pattern / -v $$ 排除"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**写 wait wrapper (`until ! pgrep -f "X"; do sleep; done`) 时, 确保 wrapper 自己的 cmdline 不含 pattern X**.

**Why**: 2026-05-14 04:30 实际踩过. 想等 pytest 完成, 写
```
until ! pgrep -f "pytest src/tests" > /dev/null; do sleep 30; done
echo "pytest done"
```
传给 `Bash` 工具. 实际 wrapper bash 的整个 cmdline 是 `/usr/bin/zsh -c ... eval 'until ! pgrep -f "pytest src/tests" ...'` — **wrapper 自己的命令行字符串里就含 "pytest src/tests"** → `pgrep -f` 永远找到 wrapper 自己 → until 条件永远不满足 → 永远 sleep. Pytest 实际 4 min 就跑完了, 但 wrapper 仍在 sleep, 用户 13 min 后才发现"为啥没通知". 浪费两次 cycle.

**How to apply**:
- 避免 wrapper cmdline 含搜索 pattern. 改用:
  - `wait $PID` 如果直接 spawn 了 PID
  - 更精确 pattern (e.g. `pgrep -af "pytest" | grep -v "until" | grep -v $$`)
  - `pgrep -x` (exact match, 不撞 wrapper)
  - 直接 `pgrep -f "pattern" | grep -v $$` 排除自己 PID
- 通用规则: wait wrapper 用的 pgrep pattern **绝对不能跟自己的 cmdline 重叠**
- 调试卡死的 until loop, 先看 `ps -p <wrapper_pid> -o cmd` 是否 cmdline 撞自己
- **2026-05-15 recurrence**: spike chain script `while pgrep -f "main.py --campaign-hours 0.5 ..."` 写
  在 `.artifacts/spike_workers_4_chain.sh`, 但**前面 Bash tool 调用残留 zsh shells** (399893
  / 432958 / etc) 的 cmdline 含 eval string 中嵌入的 pattern → ghost zsh 永远 match,
  spike#6 真死 chain 不 detect, spike#7 不 fire. 修法: 手动 `kill <ghost_pid>` 让 pattern 真消失.
  防再犯: chain script 加 `pgrep -f "pattern" | grep -v zsh | grep -v bash | grep -v $$` 排除 shell
  process, OR 用 `pgrep -x python` exact match name not -f cmdline

## 链 (补连 2026-06-01)
- [[multiprocess-hang-inspect-all]] — 进程调试 lore
