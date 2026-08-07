# 侦察报告：认证路径约束族全量盘点（2026-08-07）

> 只读侦察转述，**非权威**——承重引用前回源核对 file:line。fp-derivation 席派出、主线程存档。
> 本清单是「正当表（justification table）」初始行集的原料（落地批第一步）。
> 路径修正：master/binding/routing 三文件实际都在 `src/models/`（非 src/master、src/subproblems）；
> 另两个承载约束语义的文件必须入盘点：`src/models/routing_binding_context.py`（front 可用性判据唯一实现）
> 与 `src/models/port_binding.py`（端口精确计数枚举器）。

## A. `src/placement/placement_generator.py` — 候选池枚举边界（「看不见的约束」，最强剪枝层）

| # | 族名 | file:line | 禁止什么 |
|---|---|---|---|
| P1 | 网格硬边界（本体全内） | :32-33, :287-288, :297-298, :324, :356-357, :403-404, :447-448 | 本体越出 70×70 |
| P2 | 占格=实心矩形 | :42-46 + :181-186（is_solid_z 必真否则 raise） | 非矩形/空心 footprint |
| P3 | 端口只在四边、体外第 1 格 | :49-76, :79-92 | 端口在体内/对角/体外第 2 格 |
| P4 | 边饿死剪枝（manufacturing 专属） | :95-108；调用 :292, :302, :335-337 | 必需侧全部 front 出界的 (x,y,mode)；箱豁免（allow_inactive_oog_port_sides=True, :498），核心与边界口豁免（:342-350） |
| P5 | 长方形机：口在两长边、整侧同向 | :275-305，契约 :188-199 | 短边开口/进出混侧；只 4 mode |
| P6 | 正方形机：对边平行四模式 | :308-339，契约 :201-212 | 相邻边组合 |
| P7 | 正方形旋转对等去重（o 固定 0） | :315, :338 | o=2/3 不入池——物理等价枚举期折叠 |
| P8 | 协议核心口拓扑硬编码 | :353-354（output_indices=[1,4,7]，input 1..7），契约 :214-231（9×9、6出/14进） | 核心任意开口；只 o=0/o=1 |
| P9 | 供电桩不可旋转+半径5模板 | :393-409（cov 用 x-5…x+7），契约 :235-248 | 桩带端口/旋转；覆盖=2×2 桩心 12×12 方形、边界截断 |
| P10 | 边界口只枚举左/下基线 | :412-438；契约 :250-263 | 右(x=69)/上(y=69)边界仓库口整族不存在 |
| P11 | 边界口朝向+端口锁中间格 | :429（左基线 (1,y+1,"E")）, :435（下基线 (x+1,1,"N")） | 向场外供料；端口在条两端 |
| P12 | 边界口全 output | :430, :436（in_ports=[]） | 成品送回边界仓库（边界口只能是 source） |
| P13 | 左下拐角不在枚举期互斥（反向注记） | :419-420（注释显式声明）；range(0,…) | ——(0,0) 两 pose 都保留，互斥归 master cell-exclusivity（故意没剪） |
| P14 | port_rule 白名单 fail-closed | :265-266, :505-508 | 未知 port_rule/未分派端口启用语义（omni_wireless 已从 schema 删，:233-234） |

## B. `src/models/exact_coordinate_master.py`（8604 行）— 坐标 master (CP-SAT)；build() 施加序 :4065-4136

| # | 族名 | file:line | 禁止什么 |
|---|---|---|---|
| M1 | 本体不重叠 NoOverlap2D（B∪F） | :4098-4101 | 任两设施 footprint 相交；(a) 类唯一主载体（无逐 cell ≤1 行） |
| M2 | 本体不重叠含 ghost（B∪G） | :4550-4552 | ghost 与本体互斥；dedup :4553-4578 |
| M3 | footprint interval 通道 | :2633-2756；表约束 :2689-2698；线性等式 :2720-2723 | (mode,dx,dy,w,h) 非法组合 |
| M4 | slot 位姿域表 | :2952-2969 | (x,y,mode) 出候选池 |
| M5 | mode/x/y 域界 | :2930-2938 | 坐标出 mode_rect_domains 并集 |
| M6 | 空域 fail-closed | :2928（Add(0==1)） | 无候选域 slot ⇒ 全模型 UNSAT |
| M7 | signature bucket 恰一/区域条件化 | :2971-2981, :3054-3059, :3040, :3048 | mandatory slot 不落恰一 bucket-region |
| M8 | optional inactive 坐标归零点 | :3087, :3300-3302, :3675-3676 | 未激活 slot 坐标游走 |
| M9 | 同组 order_key 单调（对称破缺） | :3174-3178, :3215-3219, :3315-3319；key :2945-2948 | 同组同模板置换重排 |
| M10 | optional 激活前缀单调 | :3316, :3749 | 空洞式激活 |
| M11 | signature 单调（可兼容时） | :2855-2889（:2887 施加），入口 :4374-4449 | 同组 signature 降序 |
| M12 | power_pole family 序+组内序 | :3748-3759 | pole family 乱序 |
| M13 | pole family 壳距查表通道 | :3668-3732；shell :619-678；距离 :3597-3646 | family 与 (d_lo,d_hi) 壳距不一致；inactive=sentinel（:3732） |
| M14 | front-clear 自由格证书通道 | :3790-3820 | free[c]=1 而 c 被占（1×1 optional interval 进 M1） |
| M15 | front-clear 每侧需求下界 | :4059（sum(b_vars)>=demand）；索引 :4044-4049；查表 :4054-4056；env 门 :726 | 进/出侧自由 front 少于 routing-visible 需求 |
| M16 | front-clear 4 几何前提 fail-closed | :3866-3871, :3887-3892, :3894-3899, :3905-3910；padding :4019-4030 | 前提破 ⇒ raise 不降级 |
| M17 | ghost 空矩形恰一锚点 | :4547（AddExactlyOne）；枚举 :4498-4527；越界 :4487-4488 | 不恰一放置 w×h 空矩形；anchor filter :4500 外部注入剪枝 |
| M18 | 供电覆盖 C1：受电 slot 需被覆盖 witness 格 | :6753-6787；:6745；witness 在 footprint 内 :6768-6772；target==1 :6785-6787 | 未被激活 pole 覆盖的受电设施（witness 只需一格非全 footprint） |
| M19 | 供电覆盖另两种 lowering（geometry/table） | :6808-6890；:6029-6080；矩形性判据 :5993-6027 | 同 M18；非矩形强制 table（:6011），C1 下 NotImplementedError（:6706） |
| M20 | 无 pole 时受电强制关/UNSAT | :6709-6713, :6827-6831, :6076-6079 | 没电开机 |
| M21 | 供电容量下界（family 系数聚合） | :7357（sum(coeff*count)>=demand）, :7359（无项 UNSAT） | pole 总容量低于需求；系数源 exact_compact_rect_cpsat_v14（:6946） |
| M22 | 协议箱数量下界 | :7211-7213；来源 master_model.py:5435-5436 | 箱数少于 generic slot 需求下界 |
| M23 | pole 支配上界（数量帽） | :7276-7281, :7287-7292 | pole 数超受电数和 |
| M24 | slot 池上界（枚举期数量帽） | :1871-1881；面积公式 master_model.py:5438-5455；family 计数 :1895-1915 | slot 数超 4900//面积；pole 的 certified optional 上界恒 0（master_model.py:5440-5441）改走 _power_pole_slot_upper_bound |
| M25 | bucket 计数上界 | :3188-3193, :3229-3234, :3269-3281 | bucket 内 slot 超预计算上界 |
| M26 | PROJECT_LOCK L4a fail-closed | :4072-4082 | certified 下 EXACT_POWER_PLACEMENT_SUBPROBLEM |

硬编码常量：grid 70×70 owner 注入；覆盖半径读模板 power_coverage_radius（:5987-5991，canonical=5）；C1 偏移 `+2+radius-1`/`radius+1` 写死 :6184-6191、:6224-6226；padding W+2/H+2 :3801。

## C. binding（`binding_subproblem.py` + `port_binding.py` + `routing_binding_context.py`）

| # | 族名 | file:line | 禁止什么 |
|---|---|---|---|
| B1 | 端口精确计数=速率整除 | port_binding.py:212-248；operation_profiles.py:65-73（ceil(rate/belt)） | 绑定数≠profile；total_slots>可用口 raise（port_binding.py:219-222） |
| B2 | 进/出独立枚举笛卡尔积 | port_binding.py:137 | （隐含）跨侧联合约束 |
| B3 | 每实例恰一 pattern | binding_subproblem.py:1108 | 一设施两套端口分配 |
| B4 | front-free 过滤（layout-local） | binding_subproblem.py:930-992；判据 routing_binding_context.py:110-154, :157-163 | active 口 front 出界/被本体占；belt 不算堵（:12-15） |
| B5 | front 无自我豁免 | routing_binding_context.py:122, :125 | 用自己体格当 front |
| B6 | 空 binding 域 ⇒ UNSAT | binding_subproblem.py:809-810 | —— |
| B7 | generic output 槽恰一商品（含 __unused__） | :1119, :1150-1154 | —— |
| B8 | generic input 槽恰一商品（含 __unused__） | :1178, :1221-1225 | —— |
| B9 | generic 槽也走 front 过滤 | :1134-1137, :1204-1207 | 堵口当候选槽 |
| B10 | generic 容量漂移 fail-closed | :1193-1200 | plan 槽数≠实体口数（虚拟槽） |
| B11 | generic 需求精确等式 | :1238（==required）, :1251；required==0 逐 var 置 0（:1236, :1249） | 超供/欠供 |
| B12 | 零 generic 槽才走 pose-level 精确绑定 | port_binding.py:31-33, :113-118；调用 binding_subproblem.py:1060-1061 | hub 类穷举绑定（raise） |
| B13 | 实例元数据一致性 fail-closed | :677-780, :782-786 | 与 placement solution 不符 |
| B14 | 位姿越界 fail-closed | :1045-1051 | pose_idx 出池 |
| B15 | 箱高低产商品同箱禁配（启发式硬 nogood） | :858-915（:913 施加）；env 门 :823-830（默认 OFF）；阈值 0.1（:854） | **可切可行解**——注释自认（:866-871）；只作用 box_sink 不作用 core（:891-894） |

## D. `src/models/routing_subproblem.py`（2044 行）；build() 序 :881-889

| # | 族名 | file:line | 禁止什么 |
|---|---|---|---|
| R1 | 障碍排除=变量不生成（隐式） | :1115-1117；域来源 :1013-1014 | 占格上任何 route 变量；ghost 格进 occupied（:39-50, GHOST_RESERVED_OWNER_ID） |
| R2 | 域裁剪：commodity-scoped 连通分量 | :529-602；分量 :244-275 | 不含该商品 source+sink front 的分量 |
| R3 | 域裁剪：terminal core peeling（度<2 剥皮） | :278-319；调用 :553-557, :580-586 | 死胡同格建变量 |
| R4 | 状态模式白名单 | :934-972 | 地面 belt 掉头（:946）；splitter 出度∉{2,3}；merger 进度∉{2,3}；高架只直行 bridge（:935-942） |
| R5 | 局部支持剪枝 | :992-1007；判据 :978-990 | 无活跃邻格/终端 front 支撑的模式 |
| R6 | use⟹phys + phys=max(use) | :1066, :1076 | 商品占未物化组件 |
| R7 | 每格每层至多一物理组件 | :1119-1122（AddAtMostOne） | 同格同层双组件 |
| R8 | 桥跨层互斥（除正交直行） | :1124-1143（:1141） | 地面非直行/非正交轴时同格 bridge |
| R9 | 后继支持（局部） | :1221-1257（:1257） | 有出向无兼容接收者；邻格不在域 ⇒ 强制 0（:1240, :1246, :1252） |
| R10 | 前驱支持（局部） | :1259-1295（:1295） | 有进向无兼容发送者 |
| R11 | 有向边流量守恒（等式） | :1169-1219（:1214 send==recv） | 幻影分流器（一发两层）；终端边跳过（:1193, :1201） |
| R12 | 端口贴合：每物理口恰一条线 | :1297-1336（:1329 sum==1）；front 不在域 ⇒ UNSAT（:1307, :1325） | 口接 0 或 ≥2 条带 |
| R13 | 重复终端 key fail-closed | :177-229；施加 :866-868（Add(0==1)） | 两口共享 (front,dir,commodity,type) |
| R14 | 域状态契约 fail-closed | :856-864, :873-879 | 未知状态/front_blocked/relaxed_disconnected（:32-36） |
| R15 | 间隙规则=空（反向注记） | :1338-1341 | ——1 格间隙无独立约束，靠 placement 隐含 |
| R16 | 桥数偏好 hint 非约束 | :1145-1158 | ——AddHint(var,0) 不改可行域 |

**连通性复验 `_validate_selected_route_connectivity`**（:1710-1819，调用 :1922，失败加 cut 重解 :1939-1974）＝五条量词合取：①∀source front 有选中起始态（:1744-1748）②∀sink front 有选中终止态（:1749-1753）③∀sink ∃source 可达（:1773-1777）④∀source ∃sink 从它可达（:1779-1784）⑤∀选中态落在 (source可达∩反向sink可达) 闭包内（:1769-1772，禁游离/环分量）。另 :1792-1793 两侧缺一即失败。有向图 :1430-1450，可达 :1451-1470。

## E. 预处理/实例构建（`src/preprocess/instance_builder.py` 入口 :175-203）

| # | 族名 | file:line | 禁止什么 |
|---|---|---|---|
| I1 | certified 只读 mandatory 工件 | :8-10；产物分离 :194-196 | provisional 实例入 certified |
| I2 | mandatory=制造机+唯一核心+边界口 | :186-190 | ——实例宇宙定义 |
| I3 | 协议核心恰 1（硬编码） | :75-86 | 0 或 ≥2 核心 |
| I4 | 边界口恰 46（硬编码常量，无出处注释） | :90, :189（写了两遍） | —— |
| I5 | 制造机数严格来自需求解 | :48-71, :129-148 | 手工调机器数 |
| I6 | operation→template 映射封闭 | :55-57 | 未登记 operation |
| I7 | exploratory 数量帽（pole 50/箱 10，provisional） | :32-45；solve_modes=["exploratory"]（:121） | ——certified 之外 |
| I8 | 端口 profile=速率整除派生 | operation_profiles.py:34-45, :65-73；belt 容量来自 canonical（rules/canonical_rules.json:16=1.0），preprocess_context.py:165-169 拒 ≤0 | 手改口数 |

## F. 「约束↔规则」映射注解覆盖率

**不存在系统映射**：全仓 grep `canonical_rules.semantics`/`rule_id`/`axiom` 在 src/models、src/placement、src/preprocess **零命中**（cuts 里的 rule_id 是割平面族注册表，无关）。实际是四套互不兼容散引用：规格书章节号（~6 族）、doc 04 v2 §x.y+Rnn（~4 族，几乎全在 front-clear 子系统）、PROJECT_LOCK Lxx（~2 族）、事故/审查批次 ID（~4 族）。**约 67 族中带任何引用的 ~14 族 ≈ 21%**。零引用重灾区：routing_subproblem 全文（R1-R16）、instance_builder 全文（I3 核心恰1/I4 边界口46/I7 帽）、供电覆盖几何常数（M18-M21 偏移量零注释）。正当表建设从 routing 与 instance_builder 起步。
