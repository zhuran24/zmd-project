# cut framework 通电前修复批规格书（I-2/I-3 必修 + I-1 深化 + 0004 卫生）

> 2026-07-10 主会话预写（1D 实现进行中）。**实施排期：批 1（1D/1E/1F）收口后、attach
> 通电线（M3 续/F 族接线）之前的独立批**——certified 下 `EXACT_CUT_FRAMEWORK_ATTACH`
> 禁用中，两个反例无现链风险，但 I-2 在通电后是 soundness 级（cut 错 ghost 生效可切可行解）。
> 上游：`00_TRIAGE.md`（反例当前 HEAD 复现实测）+ `REVIEW.md` I-1/I-2/I-3 + `patches/`。
> ⚠ 行号锚以「实施时 HEAD」为准重校（本稿写作时 1D 正在改 benders_loop.py，必漂）。

## §0 原则

1. **不直接 `git apply` 外来补丁**：5.6 Pro 的 patch 0001-0004 是快照上做的（上下文已漂），
   且外来代码必须过本项目审查链。按补丁思路自写，语义对齐、代码重写。
2. 流程走定型流水线：本规格书（实施前校准行号）→ codex 实现 → fable+codex 双审 →
   主会话终审 + reseal → preflight → 慢 lane。
3. reseal 面预告：`src/search/benders_loop.py`（pin 双处+自钉，1C 同型）+
   `src/cuts/lifecycle.py`（close-kernel 钉面，M2 批 B 确认 cert_schema/lifecycle/replay
   在钉面——实施时用 `grep -rn <旧sha>` 全仓定位 pin 位置）。

## §1 手术点

### F1（=I-2 必修）：BState ghost 轴反置修复
- 落点：benders_loop.py 的 BState builder（审查快照 :7581-7587/:7646-7652 两处；
  实施时按函数名定位——构造 `(anchor_x, anchor_y, ghost_h, ghost_w)` 的地方改为
  `(anchor_x, anchor_y, ghost_w, ghost_h)`，对齐 BState 契约 `(x, y, x_span, y_span)`
  与 master ghost_rect 契约 `(width, height)`）。
- 红测：**非方形 ghost**（如 (2,1)）的 state 装配断言 `state_ghost_rect == (x, y, 2, 1)`；
  加一个 cut scope 含非方形 ghost 的 HOLD/ATTACH 判定回归（square 掩盖正是病根）。
- 长期项（本批不做，通电线 RFC-001 评估）：`GhostRect(x,y,width,height)` 命名 dataclass。

### F2（=I-3 必修）：artifact scope 完整快照严格相等
- 落点：`src/cuts/lifecycle.py` 的 `step_6_attach_scope_check`（快照 :968-978 一带）——
  schema v1 下 cut 的 artifact map 必须与 state 的 artifact snapshot **全 map 严格相等**
  （不是「cut 有的 key 才比」），缺项/多项/值异全部拒绝。
- 回归：cut 自删依赖 → 拒绝；cut 多报不存在依赖 → 拒绝；完整一致 → 通过。
- 长期项（RFC-001 的 per-family dependency manifest）本批不做——先收紧到严格相等，
  「无关 artifact 变动导致不必要 quarantine」是可接受代价（fail-closed 方向）。

### F3（=I-1 深化，酌情）：Step 8 二次完整性检查 + 拒绝原因 telemetry
- 核心 bypass 已被 `c7cd6a0` 拦（接线层返回值 fail-closed，当前 HEAD 实测 attached:0）。
- 本批补 defense-in-depth：`step_8_apply_to_master` 入口重跑 `validate_cut_integrity`
  （防未来出现绕过接线层的新调用点）；attach 拒绝原因进 telemetry（当前只记
  generated/attached/family，加 rejection taxonomy——对照 REVIEW I-5 的批评面，
  但不做 I-5 的完整 gauntlet 收口，那属通电线 RFC-001）。
- 恶意 cert 回归：c7cd6a0 已有 wiring 侧回归（实施时核对 test_cut_framework_attach_wiring
  现有覆盖），本批补 lifecycle 侧（Step 8 直调路径）的恶意 cert 拒绝钉。

### F4（=patch 0004，卫生）：bare generic 注解补全
- mypy strict 卫生，照补丁范围自写，零语义变化。

## §2 显式不做（通电线再议）

- RFC-001 typed proof 单一真相（body/cert 双轨合一）、`validate_and_compile_cut()` 收口
- RFC-002 F5 独立 verifier（registry 共同失效解耦）——**F5 在此之前保持 shadow/不 mutate master**
- RFC-003 model epoch/ledger/semantic dedup
- I-6（Cut 内 status 与 store 双权威）、I-7（BState immutable 化）、I-8（语义去重与 selector）

这些与 5.6 复审给 attach 通电追加的三硬门一起，已在 `00_TRIAGE.md` 记为通电 checklist。

## §3 验收

```bash
.venv/bin/python -m pytest -p no:randomly --basetemp=.pytest_tmp/cutfix \
  src/tests/cuts/ src/tests/test_cut_framework_attach_wiring.py -q   # 全量 cut 面
# + 触碰文件 ruff/mypy + preflight（base 解释器）+ 慢 lane（动了 close-kernel 钉面）
```

三个 repro 脚本（`evidence/repro_scripts/`）修后必须翻绿：I-2 输出 `(x,y,2,1)`、
I-3 输出 `decision: 'REJECT/HOLD'`（按实现的拒绝形态）、I-1 保持 attached:0。
