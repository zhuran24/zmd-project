# Routing-aware witness 研究构造器

本目录只承载 70×70 小实例的研究构造、独立复验和运行证据。目标工件是一个具体布局：266 个 mandatory 实例全部放置，辅助设施与传送带一并给出，并由独立 checker 同时确认以下六项：

1. 实体 body 不重叠；
2. placement 合法；
3. 所有 active front 空置；
4. active/null 端口计数与绑定精确；
5. 每个 active sink 至少可由一个同商品 source 到达，且每个 active source 至少能到达一个同商品 sink；
6. 全部需电实体被供电覆盖。

布局通过后，`objective_audit.py` 以 body occupancy 为唯一占用口径穷举最大空矩形，得到该具体 witness 的 `(A*, s*)`。它只形成一个真实可行下界，不承载任何全局结论。本目录不是发布面，不向 sealed/frozen/reseal 面写入，也不产生项目的受控证据工件。

## 固定边界

- 基线 HEAD 固定为 `ea407fafaff56333bcf18066cecf890f0ef0c6da`；HEAD 或 pinned input hash 漂移即 fail closed。
- strict 包、canonical rules、generic I/O、mandatory 实例与 candidate poses 在加载时独立复算；不能依赖构造器自己的统计作为验收依据。
- R3 信息在本件中只采用 `P >= 9` 作为杆数 hard sentinel。若 set-cover 或最终布局报告少于 9 根杆，构造必须拒绝。
- 口前格属于受保护的 active front；电线杆占格会堵塞；弯带不能与 crossing 叠用，crossing 只允许两条直穿且 channel 相互隔离。
- box 尝试顺序固定为 `0 -> 1 -> 2`。0-box 一旦被独立 checker 接受就立即停止；当前 1-box/2-box adapter 为 `UNSUPPORTED_BOX_GEOMETRY`，这只是未运行状态，不对对应分支作结论。

## 唯一推荐的 witness CLI

面向操作员的构造与复验入口只有 `construct_witness`：

```bash
.venv-uvbolt-backup/bin/python3.13 -m \
  docs.research.witness_constructor_20260717.07_routing_aware.construct_witness \
  run --geometry-result /absolute/path/to/shelf_power_result.json
```

对已有严格布局复验仍使用同一入口：

```bash
.venv-uvbolt-backup/bin/python3.13 -m \
  docs.research.witness_constructor_20260717.07_routing_aware.construct_witness \
  verify /absolute/path/to/layout.<sha256>.json
```

`construct_witness` 不搜索“latest”结果，必须显式给出 geometry result 或 layout。它依次做输入协调、几何 replay、strict witness 组装、body-only 空矩形审计、pinned 独立 checker、审计结果交叉比对，最后才发布 content-addressed 工件。不得直接调用模块内部 builder 代替这条验收链。

`launch_shelf_power` 只是受控生成 explicit geometry result 的内部 launcher；`solve_shelf_power` worker 不可裸跑。需要新 geometry 时，由 launcher 持有全局锁并创建唯一 run，再把所得路径显式交给上述 CLI。

## 运行与资源合同

- 每次 run 与 attempt 使用 exclusive create；既有目录或终态记录绝不覆盖。
- layout、geometry snapshot、checker report、objective audit 和 manifest 按内容摘要命名。同名同字节可幂等复用，同名异字节立即拒绝。
- 所有 CLI 输出必须位于本目录的研究子树。
- prod-scale 同时只允许一个。launcher 从 busy preflight 起到终态证据落盘一直持有 `/run/user/$UID/zmd-pj-prod-scale-solve.lock`，并检查相关 user unit 与进程。
- worker 必须运行在 cgroup v2 合同 `MemoryHigh=34G`、`MemoryMax=38G`、`MemorySwapMax=16G`、`OOMPolicy=continue` 下。启动与结束时都从 cgroupfs 读取前三项的 leaf/ancestor 有效限制、`memory.events`、peak 与 swap；`OOMPolicy=continue` 则由记录的 exact systemd argv 与定向测试约束。合同或遥测缺失均拒绝。
- `OOMPolicy=continue` 用于保留分类证据，不把 OOM 美化为普通 timeout/unknown。`memory.events` 的 `oom`、`oom_kill`、`oom_group_kill` 与进程退出信息共同决定崩溃分类。
- `CLEAN_RESULT` 只表示进程、结果 schema/integrity 与 OOM 遥测均干净；它不等于 `geometry_ready`。只有结果实际携带可 replay 的完整几何，`geometry_ready` 才可为 true。

## 模块分工

- `strict_contract.py`：pinned 输入读取、hash 与独立数字账。
- `geometry.py` / `shelf_constructor.py`：47 边界模式、placement/front/power 几何以及 worker result replay。
- `network_router.py` / `route_adapter.py`：component-typed 网络与 strict 传送带适配。
- `witness_io.py`：端口精确绑定、canonical JSON、pinned 独立 checker 子进程。
- `objective_audit.py`：与 checker 实现独立的 body-only 最大空矩形审计。
- `run_supervisor.py` / `cgroup_telemetry.py`：no-overwrite、全局互斥、cgroup 合同与崩溃分类。
- `construct_witness.py`：唯一的 witness campaign/verify CLI。

当前求解进展与不变运行记录见 [`07_construction_log_20260720.md`](07_construction_log_20260720.md)。在出现独立 checker 全绿的 content-addressed layout 之前，本目录不报告 `(A*, s*)` 数值。

## 定向检查

```bash
.venv-uvbolt-backup/bin/python3.13 -m pytest -p no:randomly \
  --basetemp=.pytest_tmp/witness-routing-aware \
  src/tests/test_witness_*.py src/tests/test_construct_witness_cli.py -q

.venv-uvbolt-backup/bin/python3.13 -m ruff check \
  docs/research/witness_constructor_20260717/07_routing_aware \
  src/tests/test_witness_*.py src/tests/test_construct_witness_cli.py
```
