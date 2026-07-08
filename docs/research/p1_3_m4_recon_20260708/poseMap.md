# poseMap

## FINDINGS

# 专题⑥侦察报告：literal 族（F3/F5/F7）的 pose_id → pose_idx 映射层

## 1. Cut 侧：F3/F5/F7 literal 里 pose_id 的形态

**类型**：`PoseId = str`（`src/cuts/lifecycle.py:50`）。注释 :46-49 明确：Gap 10（Gemini round 30）把 PoseId 从 PoC 的 int 改成 str，来源是 candidate_placements 的 `pose_id` 字段；**匿名化只在 slot 级**（`AnonymousSlotRef.slot_index` 是 int 且组内可置换，lifecycle.py:156-160），pose 级是几何身份、不匿名。

**Literal 结构**（lifecycle.py:163-166）：
```python
@dataclass(frozen=True)
class CutLiteral:
    slot_ref: AnonymousSlotRef   # (group_id: str, slot_index: int)
    pose_id: PoseId              # str
```

**pose_id 字符串的生成源**：`src/placement/placement_generator.py:111-123` `build_placement_obj`：
```python
"pose_id": f"p_x{x:02d}_y{y:02d}_o{o}_m_{mode}",
"pose_params": {"orientation": o, "port_mode": mode},
```
另有 :455 的 `f"rect_w{w}_h{h}_x{x:02d}_y{y:02d}"` 变体。**实测冻结工件**（`data/preprocessed/candidate_placements.json`，45,774,305 字节版）7 个 pool 全部是 `p_x##_y##_o#_m_<mode>` 格式（如 `p_x00_y02_o0_m_TB`、`p_x02_y02_o0_m_core_LR_out`）。⚠ lifecycle.py:47 与 `src/cuts/helpers/candidate_placements.py:13` docstring 里的示例 `"viewer::boundary_required_output_blue_iron_ore_019"` **与冻结工件不符**——`viewer::` 前缀只出现在 viewer 合成路径（`src/render/industrial_planner_single_base_delivery_viewer.py:377`），是 stale 示例，不是生产 pose_id 形态。

**三族 oracle 的 literal 构造**（pose_id 均为直接携带 BState 里的 pose_id 字符串）：
- F3 `src/cuts/oracles/port_exposure_oracle.py:312-321`：两个 literal（facility slot_index=0 + blocking (group, slot)）。
- F5 `src/cuts/oracles/pattern_nogood_oracle.py:251-256`：从 deduped_core 三元组 `(g, s, p)` 逐个建。
- F7 `src/cuts/oracles/power_cover_oracle.py:286-291`：单 literal，slot_index=0；`generate_power_hitting_set_cuts`（:165-233）要求 pose_id ∈ `state.groups[gid].pose_domain`（:205），且 `target_poses` 为 None 时全跳（:193-194，Phase 1.5+ 才从 master_solution 派生）+ env 门 `_env_enabled()`（:189）。

**验证器对 pose_id 的核对**（都是字符串域校验，无任何 pose_idx 概念）：
- F3 `src/cuts/families/port_exposure.py:161-195`：cert `facility_pose_id`/`blocking_facility[2]` ↔ literal 多重集绑定（:115-136 用 `Counter[(group_id, pose_id)]`）；blocking pose 走 `find_pose` + occupied_cells 复核（:106-111）。
- F5 `src/cuts/families/pattern_nogood.py:183-288`：`forbidden_pose_pattern` 每项 `[group_id, slot_index, pose_id]`，pose_id ∈ pose_domain（:277-285）；literal ↔ cert 按 frozenset 三元组比对（:291-323）。
- F7 `src/cuts/families/power_hitting_set.py:242-247`（pose_id ∈ pose_domain）+ :317-334 pose registry 扫描：**pose_id 在 pool 里不唯一 → unsound "registry binding ambiguous"**（这是 cut 侧唯一的 pose_id 唯一性显式检查）。

## 2. Master 侧：presence literal 缓存 key 的确切构成

类：`CoordinateExactMasterDelegate`（`src/models/exact_coordinate_master.py:756`）。类型别名 :44-45：`ModeToken = Tuple[str, str, str]`、`PoseTuple = Tuple[int, int, int]`。

**三层缓存**（声明 :784-790，M3-2 content-addressed 注释 :773-783，生命周期绑 model、永不失效因为都是 state-independent 定义）：
| 缓存 | key | 定义处 |
|---|---|---|
| `_eq_literal_cache: Dict[Tuple[int,int], IntVar]` | `(var.Index(), int(value))` | `_eq_literal` :6921-6935 |
| `_slot_pose_match_cache: Dict[Tuple[str, Tuple[int,int,int]], Optional[IntVar]]` | `(str(slot.key), normalized)` | `_slot_pose_match_literal` :6937-6981 |
| `_pose_present_cache: Dict[Tuple[Tuple[str,...], Tuple[int,int,int]], Optional[IntVar]]` | `(tuple(sorted(str(slot.key) for slot in slots)), normalized)` | `_pose_present_literal` :6983-7015 |

其中 `normalized = (int(pose_tuple[0]), int(pose_tuple[1]), int(pose_tuple[2]))`（:6948-6950 / :6990-6992）= **(anchor_x, anchor_y, mode_id)**。None 结果同样缓存（:6956, :6959, :7004）。

**PoseTuple 的构成与 pose_idx 的定义**（`_prepare_template_domains` :1691-1722）：
- 对每个 template：`pool = list(self.owner.facility_pools[tpl])`，**pose_idx = enumerate 序号**（:1700）。
- `pose_tuple = (int(anchor["x"]), int(anchor["y"]), mode_id_by_token[_pose_mode_token(pose)])`（:1702-1706）。
- mode token = `(str(pose_params["orientation"]), str(pose_params["port_mode"]), _pose_footprint_key(pose))`（`_pose_mode_token` :1021-1027）；footprint_key 由相对 occupied_cells + bounds 序列化（`_pose_footprint_key` :1012-1019）。mode_id = 该 token 在 `sorted(全 pool tokens)` 中的序号（:1694-1697）——**master 私有推导，池内容变则重排**。
- 重复 pose_tuple → build 时 `raise ValueError("Duplicate coordinate pose key…")`（:1707-1708），保证 pose_idx ↔ pose_tuple 双射：`_template_pose_idx_by_tuple` / `_template_pose_tuple_by_idx`（声明 :766-767，填充 :1713-1714）。

**facility_pools 里 pose_id 与 pose 对象的对应**：每个 pose dict 自带 `pose_id` 字段；master 侧**全文件零 pose_id 使用**（实测 grep：exact_coordinate_master.py 只出现 pose_idx / PoseTuple，无一处读 `pose["pose_id"]`）——即 master 现在完全靠 pool list 序号识别 pose，**pose_id→pose_idx 映射目前在 master 侧不存在，是真正的新表面**。

配套：`_slot_can_take_pose` :6915-6919（allowed_tuples 优先、否则 tuple_to_pose_idx 成员测试）；`CoordinateSlotSpec` :724-753（key: str, tuple_to_pose_idx, x/y/mode/active IntVar）；`mandatory_slots: Dict[str, List[CoordinateSlotSpec]]` :946。

**F1 参照实现** `add_region_capacity_cut`（delegate :7137-7213；`master_model.py:12095-12116` façade 只在 `exact_mode and _coordinate_delegate is not None` 转发、否则 False）：group_id → tpl（线性扫 `owner._mandatory_groups` :7169-7176）→ `mandatory_slots[gid]`（:7179）→ `_template_pose_tuple_by_idx[tpl]`（:7182）→ 对 `sorted(pose_tuples)` 每个 pose_idx 取 `_pose_present_literal(slots, pose_tuples[pose_idx])`（:7186-7190）。单 pose literal 为 None 跳过（恒零项 lossless，:7153-7158 注释），group 全 None → False；all-or-nothing；成功后 witness 失效 :7210-7212。**注意 F1 完全不经 pose_id——它对整个 pose 域求和，绕开了映射问题；F3/F5/F7 是点名单个 pose，绕不开。**

## 3. 映射数据源

- **权威结构**：`{"facility_pools": {facility_type: [pose, ...]}}`，pose = pose_id / anchor{x,y} / pose_params{orientation, port_mode} / occupied_cells / input_port_cells / output_port_cells / power_coverage_cells（`src/cuts/helpers/candidate_placements.py` docstring :7-27 + 冻结工件实测一致）。
- **`find_pose(state, gid, pose_id)`**（candidate_placements.py:133-176，注意实际 def 在 :133 不是任务提示的 :149）：gid→facility_type 走 `facility_type_for_group`（`src/cuts/helpers/canonical_rules.py:25-33`，= `state.instance_to_facility_type.get(gid)`，None fail-closed）→ 进程级 cache `_POSE_CACHE_BY_POOLS_DIGEST`，外层 key 是 facility_pools 的 canonical-JSON sha256（:102-112, :163-172，内容寻址防 object-id 复活）、内层 key `(ft, pose_id)`（:129），命中返回 deepcopy（:176）。**find_pose 不返回 pose_idx**——`_build_pose_cache`（:115-130）enumerate 序号被丢弃。
- **`_build_cut_framework_state` 重包的 dict 信息够不够**：够（几何上）。`facility_pools = getattr(master, "facility_pools")`（benders_loop.py:7543）**直接引用 master 同一 dict** 塞进 `candidate_placements={"facility_pools": facility_pools}`（:7611）；`pose_domain` = pool 内 pose_id 字符串 frozenset（:7585-7589）。master.facility_pools 在 `MasterPlacementModel.__init__`（master_model.py:2170）`{tpl: list(pool)}` 浅拷贝 list、共享 pose dict、保持 JSON 数组顺序——**因此 BState 侧 pool 顺序 == `_prepare_template_domains` enumerate 的顺序 == pose_idx 定义域，同一对象天然一致**。但 mode_id 分配（sorted token 序号，含 footprint_key）是 master 私有；BState 侧虽有 pose_params + occupied_cells 理论可复算，复算即复制 `_pose_mode_token`/`_pose_footprint_key` 逻辑 = 漂移风险。

## 4. 落点建议

- **(A) master API 入参收 (group_id, pose_id)，映射层放 delegate 内部 —— 推荐**：与 F1 同构（master 内部解析 group→tpl→slots，all-or-nothing），pose_idx/mode_id/PoseTuple 这些私有概念不外泄；维持 `src/cuts` 对 `src/models` 的 import 隔离（lifecycle.py:1115-1122 `MasterModelLike` Protocol 注释明说 duck-typed 传入就是为了隔离）；delegate 一次 enumerate `self.owner.facility_pools[tpl]` 建 `{pose_id: pose_idx}`（与 `_prepare_template_domains` 完全同源同序），当场对重复 pose_id fail-closed。代价：master 首次引入 pose_id 字符串概念。
- **(B) lifecycle step_8 内部 —— 不可行**：step_8 只有 `Cut + MasterModelLike`，没有 facility_pools 顺序权威；把映射塞进 Protocol 等于把 master 内部表升格为公共契约，还破坏 import 隔离。
- **(C) benders_loop state builder 建表传参 —— 可行但次优**：builder 手里同时有 master 和 BState，可建 `{(tpl, pose_id): pose_idx}`；但映射权威与 master enumerate 分离成两处隐式耦合，step_8 签名要加参数，且未来 CutStore 回放/其他 attach 入口都得重复带表。

## 5. 陷阱：alias 风险与 `_conflict_pose_entries` 纪律

**master 现行纪律**（`_conflict_pose_entries` :7017-7082，注释 :7020-7028）：certified replay 必须 all-or-nothing——静默丢弃一个 malformed 成员会把 {A,B} nogood 稀释成 {A} 的**更强** nogood → over-prune 合法布局；**两个 distinct conflict 成员 alias 到同一抽象 presence literal（例：同 group 两个对称 mandatory instance 撞同 pose_idx，key=`("mandatory::"+group_id, pose_idx)`）时整条 cut 拒绝表示，`return []`**（:7053-7055；malformed pose_idx :7032-7035、查不到 tpl/pose_tuple :7048-7052 同样整条拒）。scope 前缀 `mandatory::{group_id}` vs `optional::{tpl}`（:7053, :7074）防跨域串 key。对照：docs/research/paradigm_search_review_v12.../exact_coordinate_master.py:6500-6552 的旧版对同 key 是 `continue` 跳过（dedup 放行）——正是 M1 撞坑的前身形态，src 版已改为 fail-closed。

**映射层要避开的同类 alias（按危险度排）**：
1. **同 (group_id, pose_id) 多重度 ≥2（F5 特有）**：F5 validator 允许 `(g,0,pA),(g,1,pA)`——dedup 只按三元组、slot 唯一性不禁"异 slot 同 pose"（pattern_nogood.py:222-265）；`evaluate_literal_multiset` 按 Counter 计数（lifecycle.py:1047-1070，`state_counts[k] < demand_count`）。而 `_pose_present_literal` 是布尔 OR（任一 slot 实现该 pose），**表达不了"至少 2 个 slot 同 pose"**。映射层遇多重度 ≥2 必须要么建计数形式（`sum(slot match lits) >= k` 的 reified），要么整条 fail-closed——绝不能 dedup 成布尔（就是 `_conflict_pose_entries` 注释警告的稀释→over-prune）。
2. **pose_id 池内重复**：`_build_pose_cache` 是 last-wins 覆盖（candidate_placements.py:127-129 无重复检测）；只有 F7 validator 自查唯一性。映射层建 `{pose_id: pose_idx}` 必须显式查重 fail-closed，不能靠 dict last-wins。冻结工件当前无重复（`_prepare_template_domains` 的 pose_tuple 唯一 raise 给了间接保证，因 pose_id 恰编码 x/y/o/mode），但那是巧合性保证，程序里要自己查。
3. **同 facility_type 多 group 共享同一 pose pool**：pose_domain 按 group 整池复制（benders_loop.py:7584-7589），pose_id 字符串不含 group 信息——映射 key 必须永远是 `(group_id, pose_id)`，presence 用该 group 自己的 `mandatory_slots[gid]` slot 集（`_pose_present_cache` 的 sorted-slot-keys key 天然区分组，误用 tpl 级 slot 并集就串组）。
4. **mode_id 不可在 master 外复算**：mode_id 是 sorted(全 pool ModeToken) 序号且 token 含 footprint 序列化——在 benders_loop/cuts 侧重算 PoseTuple 有静默漂移风险；映射必须走 pose_idx →`_template_pose_tuple_by_idx` 路径。
5. **optional 域现不在 BState**：`_build_cut_framework_state` 只装 `_mandatory_groups`；F3 的 blocking_group 也要求 ∈ state.groups → 生产态只可能 mandatory。将来扩 optional 时沿用 `mandatory::`/`optional::` 前缀纪律。

**「实质停用」同类条款检查（F9 类比）**：F3/F5/F7 没有 F9 那种"validator 把非平凡 cut 全拒"的数学停用，但有三道现状闸：① 生产 `_maybe_attach_framework_cuts` 只 generate F1（benders_loop.py:7631-7641），且 `available_oracle_versions=frozenset({"region_capacity_v1"})`（:7607）——F3/F5/F7 的 oracle 版本不在白名单，step_6 scope check 必挡，**接线时必须同步扩这个集合**；② 整条 attach 链被 `EXACT_CUT_FRAMEWORK_ATTACH_ENV` 门控且该 env 注册在 `_CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES`（:7517-7525 注释）——certified/生产开它直接 fail-closed，现在只有直调/单测可达；③ F7 generator 自带 env 门 + `target_poses=None` 全跳（power_cover_oracle.py:189-194），families/power_hitting_set.py:28-29 明写 "F7 remains a non-certified master input until the P1.3 step_8 wiring batch lands its helper-vs-master equivalence regressions"。另 PROJECT_LOCK 锁面：F5 slot 完整性锁（:422-428）、F7 footprint/radius SoT 锁（:433-436，走 canonical_sot）、F1 `cells_per_pose` 刻意信任 cert 勿 consolidate（:450-452）。

## KEY_FACTS

- PoseId = str（src/cuts/lifecycle.py:50）；CutLiteral = {slot_ref: AnonymousSlotRef(group_id: str, slot_index: int), pose_id: PoseId}（lifecycle.py:156-166）；literal 族 = F3 port_exposure / F5 pattern_nogood / F7 power_hitting_set（_FAMILY_MODE_MAP lifecycle.py:81-90）
- 生产 pose_id 生成格式：f"p_x{x:02d}_y{y:02d}_o{o}_m_{mode}"（src/placement/placement_generator.py:116, build_placement_obj :111-123，同时写 pose_params={orientation, port_mode}）；冻结 candidate_placements.json（45,774,305B）7 个 pool 实测全为此格式；lifecycle.py:47 与 candidate_placements.py:13 的 "viewer::..." 示例是 stale（只在 src/render/industrial_planner_single_base_delivery_viewer.py:377 的 viewer 合成路径出现）
- master 缓存类 = CoordinateExactMasterDelegate（src/models/exact_coordinate_master.py:756）；_eq_literal_cache key=(var.Index(), int(value))（:784, :6921-6935）；_slot_pose_match_cache key=(str(slot.key), (x,y,mode_id))（:785-787, :6937-6981）；_pose_present_cache key=(tuple(sorted(slot keys)), (x,y,mode_id))（:788-790, :6983-7015）；None 结果也缓存
- PoseTuple = Tuple[int,int,int] = (anchor_x, anchor_y, mode_id)（exact_coordinate_master.py:45）；mode_id = sorted(池内 ModeToken) 序号，ModeToken = (orientation, port_mode, footprint_key)（_pose_mode_token :1021-1027, _pose_footprint_key :1012-1019）；pose_idx = facility_pools[tpl] list 的 enumerate 序号（_prepare_template_domains :1691-1722）；重复 pose_tuple → build raise ValueError（:1707-1708）；双向表 _template_pose_idx_by_tuple/_template_pose_tuple_by_idx（:766-767）
- master 侧现无任何 pose_id 字符串使用（exact_coordinate_master.py 实测 grep 全是 pose_idx/PoseTuple）——pose_id→pose_idx 映射层是全新表面
- F1 参照 add_region_capacity_cut：delegate 实现 :7137-7213（group→tpl 扫 _mandatory_groups :7169-7176 → mandatory_slots[gid] :7179 → _template_pose_tuple_by_idx[tpl] :7182 → _pose_present_literal 每 pose_idx :7186-7190；all-or-nothing，成功后 witness 失效 :7210-7212）；master_model.py:12095-12116 façade 非 exact/无 delegate → False；F1 对全 pose 域求和、不经 pose_id
- find_pose（src/cuts/helpers/candidate_placements.py:133-176，实际 def 在 :133 非提示的 :149）：gid→ft 走 facility_type_for_group（canonical_rules.py:25-33 = state.instance_to_facility_type.get）；cache 外层 key = facility_pools 内容 sha256（:102-112,:163-172）、内层 (ft, pose_id)（:129）、返回 deepcopy（:176）；不返回 pose_idx，_build_pose_cache :115-130 丢弃序号且重复 pose_id last-wins 无检测（:127-129）
- _build_cut_framework_state（src/search/benders_loop.py:7527-7612）：facility_pools 直接引用 master.facility_pools（:7543→:7611），pose_domain = pool 内 pose_id frozenset（:7585-7589）；master.facility_pools = {tpl: list(pool)}（master_model.py:2170，保 JSON 顺序）→ BState pool 顺序 == master pose_idx 定义域，同一对象
- available_oracle_versions=frozenset({"region_capacity_v1"})（benders_loop.py:7607）——F3/F5/F7 oracle 版本不在生产 BState 白名单，step_6 必挡；_maybe_attach_framework_cuts :7614-7656 只 generate F1；EXACT_CUT_FRAMEWORK_ATTACH_ENV 注册在 _CERTIFIED_MASTER_DOMAIN_UNSAFE_ENV_OVERRIDES（:7517-7525 注释），certified/生产开启即 fail-closed
- _conflict_pose_entries（exact_coordinate_master.py:7017-7082）：dedup key=("mandatory::"+group_id | "optional::"+tpl, pose_idx)；同 key 二次出现 → return []（:7053-7055 fail-closed 整条拒），注释 :7020-7028 写明丢成员会把 {A,B} nogood 稀释成更强 {A} → over-prune；docs/research 旧副本（:6500-6552）同处是 continue 跳过 = M1 坑的前身形态
- F5 允许同 (group, pose) 异 slot 多重度 ≥2（pattern_nogood.py:222-265 只禁重复三元组与 slot 重用）；evaluate_literal_multiset 按 Counter 多重度评估（lifecycle.py:1015-1071，state_counts[k] < demand_count）；_pose_present_literal 是布尔 OR，表达不了多重度 ≥2 —— 映射层必须计数化或整条 fail-closed，禁止 dedup 成布尔
- F7 validator 是唯一显式查 pose_id 池内唯一性的地方（families/power_hitting_set.py:317-334，len(matches)!=1 → unsound "registry binding ambiguous"）；F7 generator 有 env 门 + target_poses=None 全跳（power_cover_oracle.py:189-194），文件头 :28-29 自declare "non-certified master input until P1.3 step_8 wiring batch"
- step_8_apply_to_master（lifecycle.py:1133-1189）只接 F1，其余族 raise NotImplementedError（:1186-1189）；MasterModelLike Protocol（:1115-1130）只有 add_region_capacity_cut，注释明说 src/cuts 与 src/models import 隔离、master duck-typed 传入
- cert 字段：F3 facility_pose_id + blocking_facility=[group, slot, pose_id]（cert_schema.py:48-57）；F5 forbidden_pose_pattern=[[group_id, slot_index, pose_id],...]（:68-74）；F7 facility_pose_id（:91-100）；F8 已整族删除（lifecycle.py:75-77，2026-07-08）
- PROJECT_LOCK 相关锁：F5 slot 完整性（:422-428）；F7/F8 footprint SoT 走 canonical_sot（:433-436）；F1 cells_per_pose 刻意信任 cert 勿 consolidate（:450-452）；F9 tight-K 实质停用（:453-465）——F3/F5/F7 无同类数学停用条款，但有上述三道现状闸

## RISKS

- 多重度陷阱（最易写错）：F5 合法 core 可含同 (group_id, pose_id) 两个不同 slot 的 literal，多重集语义要求'至少 2 个 slot 取该 pose'；用布尔 _pose_present_literal 直接翻译会静默弱化成'至少 1 个'——比 oracle 证明的更强的 nogood → over-prune 合法布局（假阴性最优解）。必须 sum(per-slot match lits) >= k 计数化，或检测到多重度 ≥2 整条 return False
- dedup 方向性陷阱：照抄 _conflict_pose_entries 早期 'continue 跳过重复' 写法（docs/research 旧副本还留着这形态）而不是 src 版 'return [] 整条拒'——silent drop 一个成员 = 稀释 nogood = unsound；all-or-nothing 是纪律不是优化
- pose_id→pose_idx 建表用 dict last-wins：_build_pose_cache 就是这么写的（无重复检测）；映射层若同样写法，池内万一出现重复 pose_id 会静默绑错 pose_idx。建表时必须显式查重 raise/False（当前冻结工件无重复，但那是数据巧合不是代码保证）
- 在 master 外复算 PoseTuple：mode_id 依赖 sorted(全池 ModeToken) 序号且 token 含 footprint 序列化——任何在 benders_loop/src/cuts 侧重算 (x,y,mode_id) 的方案都可能与 master 静默漂移；正确路径是 pose_id→pose_idx（enumerate 同一 pool list）→ _template_pose_tuple_by_idx
- 跨 group 串池：同 facility_type 的多个 mandatory group 共享同一 pose pool 与 pose_id 命名空间，pose_id 单独不定位 group；presence 必须用该 group 自己的 mandatory_slots[gid]，key 永远 (group_id, pose_id)
- 接线时漏改 available_oracle_versions（benders_loop.py:7607 硬编码 {"region_capacity_v1"}）：F3/F5/F7 cut 会在 step_6 scope check 被挡，表现为'生成了但一条都没 attach'的假通电
- src/cuts 不得 import src/models（lifecycle.py:1115-1122 Protocol 隔离是刻意架构）——把映射放 step_8 内部或把 master 内表塞进 Protocol 都违反该隔离；推荐 F1 同构：master API 收 (group_id, pose_id)，解析全在 delegate 内部
- 文档信号误导：pose_id 示例 'viewer::...'（lifecycle.py:47、candidate_placements.py docstring:13）与冻结工件真实格式 p_x##_y##_o#_m_<mode> 不符，写测试 fixture 或解析假设时别按 viewer:: 前缀设计
- find_pose 返回 deepcopy 且无 pose_idx——不要试图用它做 pose_id→pose_idx（拿不到序号还多付 deepcopy 成本）；正确做法是直接 enumerate master.facility_pools[tpl]
- 行号锚点校正：find_pose 实际 def 在 candidate_placements.py:133（任务提示写 :149）；step_8 NotImplementedError 在 lifecycle.py:1186-1189；_maybe_attach_framework_cuts 实际 :7614 起（提示 :7631 是其中 import 行）——实施 PR 引用行号以本报告实测为准
- certified 铁律：整个 cut framework attach 链在 certified/生产因 EXACT_CUT_FRAMEWORK_ATTACH_ENV 属 unsafe override 而 fail-closed——映射层实施与测试只在非 certified 直调路径可验，别把'单测绿'当'生产已通电'
