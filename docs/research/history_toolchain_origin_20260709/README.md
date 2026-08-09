# 工具链起源考古：「自建 cut framework」决策的调研与最初设计（2026-07-09）

> owner 提问「当时是打算怎样新建工具链」后，三路 codex workflow（wf_c9a034ff）对 cachy 老仓
> （<repo-root>，2026-05 主战场）的定向考古。姊妹篇：批 0 目录的
> `01_cachy_archaeology_b1_evidence.md`（B1 证据链考古）。

- `01_literature.md` 调研层：32 paradigm 方向 + 24 死杠杆收敛史 + 四路文献调研（CG/LBBD cuts/CP-SAT internals/paradigm shift）——「现成工具全 KILL 或硬 gate」的排除法全程。
- `02_decision.md` 决策层：GPT v13「换 cut 语言不是换 solver」thesis（2026-05-21，直接提案源）+ 当时台面全部活候选与各自死因 + 决策时间线（05-17 B1 拍板 → 05-18 B1 上层死 → 05-20 复盘 → 05-21 thesis + 外审 GO → 05-22 Phase 0 close + src/cuts 落地）。
- `03_design.md` 设计雏形层：Cut 四元组/9 族/HOLD-QUARANTINE 状态机/6 步 scope verify/validator=唯一 trust point（oracle 按 Byzantine 对待）+ 最早 phase 路线图（Phase 1.0→1.4，即当前 P1.x 前身）+ 与当前实现的差异清单。

wf→codex 通道验证（本次顺带）：3/3 完成、0 错误 0 空转，channel_check 全 OK。
