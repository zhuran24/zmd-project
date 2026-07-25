# 分边 marked-membrane 模型与独立性合同

| 项目 | 当前值 |
|---|---|
| 文档性质 | 轻量实现合同 |
| 证据截止 | `2026-07-24` |
| 状态 | **SYNTHETIC_FIXTURES_READY / STRICT_RUN_PAUSED** |

## 当前可执行面

`sidewise_marked_membrane_v1.py` 实现闭合 fixture schema 与有限状态 DP。
一个 group 表示同类实体，`multiplicity` 展开为独立实体；每个实体最多选择
一个 face、一个 contact 和一条 rectangle side，也可以不接触矩形。

每个 contact 固定：

- 消耗的 side length；
- active incidence 数；
- marked incidence 数；
- `none/left/right` endpoint 类型。

状态同时记录四边已用长度和八个 directed endpoints。长度超限、同端点复用
或同实体选两个 face 均不可达。DP 设显式 state cap，超过即
`StateLimitExceeded`，不能把资源中止当成数学阴性。

`independent_sidewise_marked_membrane_v1.py` 不 import 主实现。它重新解析同一
闭合 schema，并对最多 12 个实体、最多 200,000 个搜索节点做递归穷举；
任一上限触发都 fail-closed。两份实现只在合成 fixture 上运行，用于锁定接口
与基本互斥语义。

## 当前 fixture

`fixtures/core_face_exclusivity.json` 把 protocol core 的两个 output faces
建成一个实体的两个备选。正确 optimum 为 6；把 multiplicity 错改为 2 会
变成 12，该 mutation 用于捕捉 core double-count。

`fixtures/endpoint_capacity.json` 同时覆盖 partial-contact endpoint 占用、
side capacity 与未接触备选。它不代表 strict instance。

## Strict 模型的待实现闭包

用户解除游戏暂停后，真实模型必须从 byte-locked strict instance 独立生成：

- 每个 operation group 的 instance multiplicity；
- mode 与 input/output face 备选；
- active port 数与实际 body-edge offsets；
- necessarily marked noncorner ports；
- 46 个 boundary raw providers 与 protocol core 的六个 raw-output slots；
- 两个 final-input terminals 的安全 provider 放松；
- 对 `22`、`54` 两种 side length 的所有 full/partial overlap profiles。

主复算计划使用分边 generating-function/DP。独立复算必须另写数据提取和递归
状态表达，不 import 主 extractor、optimizer、未来 encoder 或外部回复代码。
两者共享的只有 strict input bytes、公开模型语义和预注册阈值。

## Fail-closed 状态

- schema/type/重复 key/路径 symlink：`FAIL_CLOSED`；
- state 或资源上限：`INCOMPLETE`；
- 两实现结果不同：`GEOMETRY_INCOMPLETE`；
- treatment optimum `>=210`：`NO_LIFT`；
- treatment optimum `<=209` 但必要映射或对抗未过：
  `GEOMETRY_INCOMPLETE`；
- 三门全部通过：最多
  `ADMITTED_FOR_ENCODER_DESIGN`，此时仍不更新 `U`。

## 重负载边界

当前 strict CLI 固定返回 exit 3 与 `PAUSE_FOR_USER_GAME_END`，不会读取并求解
完整 strict contact model。PB、solver、systemd 与 full preflight 没有入口。
恢复后的新实现必须保留 no-overwrite run、单 worker、资源 telemetry 和
独立 translation gate，且不能覆盖本轮 pause 工件。
