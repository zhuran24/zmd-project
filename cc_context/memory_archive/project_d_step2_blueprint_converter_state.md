---
name: d-step2-blueprint-converter-state
description: "2026-05-16 D step 2: 用户手调验证过的 blueprint 文件路径 + converter 还没写完时的 session state"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7db7f276-a2bf-4762-b9b8-bb35f8cf3fb9
---

**2026-05-16 D step 2 (task #40) 开始状态 (session 压缩前 snapshot)**:

## 用户手调最终版 blueprint

**文件**: `/home/zhuran24/下载/BP-2026-05-13 08_35_36.blueprint(1).json`

- mtime 5/16 05:56 (用户重下载导致, 实际 blueprint createdAt 是 5/13 08:35:36)
- 5/12 gpt_output/placement_solution*.json **不是** — 那是 GPT OCR 推算版, 38 records inferred + 非 boundary rotations 默认 0 (rich.json accuracy_note 自承)
- 用户在 IP v2 web app (localhost:5173 或 https://endfield.anonymous-test.top/) 里**手调验证过**, 5/13 export 出来
- **跟 [[ip-v2-blueprint-lp-modeling]] 已 LP 验证版同一个文件** (2 天前 LP 算出稳态 18 电池_3 + 12 胶囊_3/min, 100% production utilization, 收支守恒)
- device count 1175 vs memory 1156: 07:42→08:35 加了 19 个 belt (13 直 + 2 逆转 + 4 顺转), 都在 x=9-12 y=52-54 一小块. **0 设施改动 0 删除**, master hint converter 不 care belts → 用 08:35 版完全 OK
- 下载 里 5 个 BP variants: 5/12 11:21 (972, 早期) / 5/13 03:30 (1156) / 5/13 07:42 (1156, 同设施 belt 微调) / 5/13 08:35 (1175) / 5/13 08:35(1) (1175, md5 完全一致同内容)

## Blueprint schema = IP v2 (不是 项目 placement_solution 格式)

- top keys: schema/id/version/blueprintVersion/name/createdAt/baseId/**devices**/links
- 1175 devices (包含 belt/conveyor/splitter routing)
- baseId: valley4_protocol_core

### 关键 device typeId (取自实际 file)

| IP v2 typeId | 计数 | 项目 facility_type (推测) | 备注 |
|---|---|---|---|
| item_port_unloader_1 | 43 | boundary_storage_port (项目要 46) | 短 3, 待 verify mapping |
| item_port_sp_hub_1 | 1 | protocol_core | ✓ exact |
| item_port_grinder_1 | 59 | manufacturing_3x3? | 粉碎机 |
| item_port_furnance_1 | 42 | manufacturing_5x5? | 熔炉 |
| item_port_thickener_1 | 27 | manufacturing_? | 浓缩机 |
| item_port_planter_1 | 26 | manufacturing_? | 种植机 |
| item_port_seedcol_1 | 13 | manufacturing_? | 采种机 |
| item_port_shaper_1 | 4 | manufacturing_? | |
| item_port_filling_pd_mc_1 | 2 | manufacturing_? | |
| item_port_cmpt_mc_1 | 6 | manufacturing_? | |
| item_port_tools_asm_mc_1 | 3 | manufacturing_6x4 (项目要 38)? | 不太对 |
| item_port_storager_1 | 3 | protocol_storage_box | optional |
| item_port_power_diffuser_1 | 27 | power_pole? | |
| item_port_power_sta_1 | 5 | power_pole? | |
| belt_*, item_log_* | 900+ | 不是 facility, internal routing | 跳过 |

device sample: `{'blueprintInstanceId':'base_valley4_protocol_hub_1', 'typeId':'item_port_sp_hub_1', 'rotation':0, 'origin':{'x':41, 'y':61}, 'config':{...}, 'placementRecord':{'baseId':'valley4_protocol_core','baseOrigin':{'x':41,'y':61}}}`

## 项目侧 mandatory_exact_instances 数 (要对得上)

- boundary_storage_port: 46
- manufacturing_3x3: 132
- manufacturing_5x5: 49
- manufacturing_6x4: 38
- protocol_core: 1
- **总 266 mandatory**

Blueprint 1175 devices 里:
- Power-related (diffuser + sta): 32 → 项目 power_pole (residual optional)
- Storager: 3 → 项目 protocol_storage_box (residual optional)
- Boundary: 43 → 项目 boundary_storage_port (mandatory, 缺 3 个? 或 mapping 错)
- Hub: 1 → protocol_core ✓
- Manufacturing (各种 grinder/furnance/...): 59+42+27+26+13+4+2+6+3 = 182 → 项目 manufacturing_*** 219 mandatory (差 37 — 可能某些 IP v2 typeId 是 furnance 但项目分 manufacturing_5x5 vs 6x4 vs 3x3)
- Belts/conveyors: 873+ → 不属 facility, 项目内部 routing 算

## Converter 写法 (待写, ~80-150 LOC)

1. **Load blueprint** + filter devices (skip belt_*, item_log_*)
2. **typeId → project facility_type lookup** (用 IP v2 registry, `.upstream_clones/industrial_planner_v2/src/domain/registry.ts` 应该有 device dim/recipe map)
3. **origin/rotation → project pose_idx**:
   - origin (x, y) 等于 project pose anchor (x, y) [需 verify orientation 是否 same]
   - rotation (0/90/180/270) → project pose_params orientation (0/1/2/3 或 port_mode token)
   - 同 facility_type 内查 candidate_placements.json pose 列表, match anchor + orientation
4. **map 1 个 instance_id**: blueprint devices 列出 266 物理 placement, 对应项目 mandatory_exact_instances.json 的 266 instance_id (按 facility_type + 顺序 enumerate)
5. **output**: `Dict[instance_id, pose_idx]` 给 `master.solve(solution_hint=...)`

### 关键 verify 步骤 (实施前)

- 抽 1 个 device (e.g. base_valley4_protocol_hub_1 origin=(41,61) rot=0), 找 candidate_placements.json `protocol_core` pose anchor=(41,61) — 验证 coordinate convention 一致
- 抽 1 个 boundary_storage_port (例如 origin=(1,0) rot=180), 之前 verify 过 = pose[67] anchor=(1,0) orientation=1 port_mode=bottom_base. **rotation 180 → orientation 1**, **rotation 90 → orientation 0 left_base**

## Master API (已 ready, 不动)

- `master_model.py:11130` `solve(solution_hint: Dict[str, int])` 接 `{instance_id → pose_idx}`
- 内部 `apply_solution_hint` (exact_coordinate_master.py:6268) 调 `model.AddHint(slot.x/y/mode, ...)`
- benders_loop.py:3766 已经把 greedy hint 喂给 iteration=1; community hint 应**替换** `self._greedy_hint` 或 union

## 整 session 状态摘要 (压缩前)

- 11 commits land (heuristic finder, 5 env hooks, 3 production wrappers, gate worker-aware, findings doc, UNKNOWN-skip fix)
- 9 subagent findings + 5 spike + 完整 workers RAM curve (1=12.19/2=16.4/4=20.44/8=30 GiB)
- 24h trial dead (kill by 用户 5h+ sleep loop 之后, 51 candidates 全 UNKNOWN), trial verified RAM 够但 quality 不够
- 任务 #67 (RAM 减锁 -p 2) closed completed
- 任务 #40 (D step 2) **正要开始** (this state)

## 下一 session 该立刻做

1. Read `.upstream_clones/industrial_planner_v2/src/domain/registry.ts` 找 IP v2 typeId → 项目 facility_type 真实 mapping
2. 写 `scripts/blueprint_to_master_hint.py` converter (~80-150 LOC)
3. 跑短 trial: `bash scripts/run_campaign_p2_workers1.sh --campaign-hours 0.5 --resume-campaign` 加 hint env, 看 master 是否真返回 FEASIBLE
4. 若 FEASIBLE: land hint converter + restart 168h
5. 若 UNKNOWN: 进 deeper debug (hint 是否 partial inconsistent / repair_hint 是否 fire / 哪个 instance fail)

## 链

- [[d-step1-gpt-handoff]] D step 1 上下文 (5/12 GPT handoff)
- [[2026-05-15-ram-session-misdirected]] RAM session 跑偏 lesson
- [[30gb-real-culprit-power-coverage]] RAM 数据
- [[no-sleep-loop-for-goal-hook]] 不用 sleep loop
