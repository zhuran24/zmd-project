---
name: d-step1-gpt-handoff
description: Linux wine 全 input-sim 路径被 Endfield SDL2 reject; Win 跑工具拼接 FINAL.jpg 成功; OCR 85% + visual 1-2 cell error 都 fail; 打包交 GPT-5.5 Pro
type: project
originSessionId: fc5cfd3e-9107-4e9c-810f-b6633140ce22
---
## 现状 2026-05-12 13:55

D 第 1 步(种子获取 placement_solution)经过一整夜尝试, 当前状态:

**已 done**:
- user 7 hr Win 上跑截图工具 + 手写 stitch 脚本 + manual_positions.json → 输出 `谷地-枢纽区_FINAL.jpg` 10854×10411 完整 valley4 基地俯瞰拼接图 (28 MB)
- Claude rapidocr OCR 跑 FINAL.jpg → 268 text region, 225 mandatory (85% 覆盖) → `ip_blueprint.json`
- Grid 校准: 1 cell ≈ 127.2 px, grid origin pixel ≈ (983, 732) (从 boundary port 排列推)
- Recipe-based typeId 映射(看 industrial_planner_v2/src/domain/registry.ts)
- 反编译截图工具 `auto_screenshot.pyc` 拿 REGION_CONFIG

**Fail**:
- ydotool / xdotool --window / nircmd / AutoHotkey (Linux wine 下) 全被 Endfield SDL2 RawInput grab 拒绝, 不可能在 Linux 模拟 input 进 Endfield
- Claude visual reading 1200×1200 block (100 px/cell) 精度不够, r0c0 块粉碎机数错 + 间距 3 vs 实际 4 → IP 内重叠
- 49 block visual batch 估 4-6 hr 但累计偏差大, user 改 IP UI 工时也大

**已交付给 GPT-5.5 Pro**:
- 包 `~/linwin_share/gpt_handoff.zip` 69 MB (含 README.md + content.tar.xz)
- 内容: FINAL.jpg + OCR result + ip_blueprint draft + project schema (canonical_rules / mandatory_exact_instances / CLAUDE.md / PROJECT_LOCK) + IndustrialPlanner v2 (registry.ts + 7 sample blueprints) + user stitch tooling (含 manual_positions.json + decompiled tool) + Claude 失败 attempts + 49 切块备用
- 期望 GPT 输出: placement_solution.json (project schema) 或 industrial_planner_blueprint.json (IP schema), 准确率 ≥98%

## 关键决定 (写进 memory 防下次走老路)

- **Linux wine 不能模拟 input 到 Endfield** — SDL2 raw input grab 排除任何 simulated event. Win 双系统是唯一 reliable input sim 路径.
- **OCR 文字识别只覆盖 85%** — label 被遮挡/切割/重叠/红色 ⊘ overlay
- **Claude visual block reading 精度限制** — 100 px/cell 看不准 ±1 cell, 累积偏差大
- **路径选择**: D 第 1 步任务级降到 ~98% 精确度需要外部工具 (GPT-5.5 Pro 多模态) 或者 user 在 IP UI 全手工

## D 第 2 步 (待 GPT 输出 placement_solution.json 后做)

- 项目 src/models/master_model.py + canonical_rules.json 知道 master 求解器
- 把 GPT 输出 placement_solution.json 转 master 求解器 hint API (model.AddHint 类似)
- 项目 master 求解器内存压力 18-40 GB / worker, 之前撞 OOM (commit 2915d6f 修 嵌套 CP-SAT)
- 长跑验证 binding_dumps.jsonl 真增长 (production data 收集解锁 P2 #14)

## 关键路径文件

- 包: `~/linwin_share/gpt_handoff.zip`
- FINAL: `~/linwin_share/endfield_d_step1/谷地-枢纽区_FINAL.jpg`
- OCR result: `~/linwin_share/endfield_d_step1/ocr_result.json`
- 失败的 ip blueprint draft: `~/linwin_share/endfield_d_step1/ip_blueprint.json`
- IP dev server (可能还在跑): http://localhost:5173 (vite dev)
