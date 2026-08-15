# 06｜候选摆位枚举与几何降维引擎

## 目的与权威边界

本规范定义如何把二维网格中的平移、旋转与端口模式编译为有限候选集合。稳定语义由本规范、canonical rules 和实现共同约束；当前 artifact 的字节身份、生成收据和候选数量只从机器 manifest、生成器与 checker 查询，不在本文复制。

候选生成只允许应用不依赖实例绑定或端口身份的必要条件。master、binding、routing 与终验继续承担精确可行性判断。预处理成功不等于某个实例可被选择，也不等于 campaign 获得证明。

## 模板级候选池

设施实例按几何模板共享候选池。对模板集合 \(\mathcal T\)，生成器为每个模板 \(t\) 构造有限集合 \(\mathcal P_t\)。属于同一模板的实例引用同一几何池，实例标签、需求、端口绑定和对称性约束由下游模型处理。

不得为等价实例复制独立几何字典来制造虚假的身份差异。

## Placement 合同

每个候选至少包含：

- `pose_id`：在模板池内稳定且唯一的位姿标识；
- `anchor`：绝对锚点坐标；
- `pose_params`：旋转和端口模式；
- `occupied_cells`：设施本体占格；
- `input_port_cells`、`output_port_cells`：该模式下全部实体口的 stored access-cell 坐标与方向；
- 与模板有关的覆盖、边界或辅助几何字段。

stored port 坐标表示设施体外第一个 access cell。下游必须根据实际激活口复核越界、占用、方向和路由合法性；候选文件不能把“存在实体口”解释为“该口必被激活”。

## 遍历规则

### 一般设施

对每个合法旋转姿态和端口模式，锚点域由旋转后的本体包围盒与网格边界决定。本体必须完全位于图内。长方形与方形制造模板按 canonical 端口模式展开；物理投影完全相同的坐标别名应去重。

### 协议核心与协议箱

核心和箱的 generic 槽允许未使用。生成器只要求本体位于图内，不得因为某一侧实体口落在边界外就删除 pose。真正激活的端口仍由 binding、routing 和终验 fail closed。

### 供电设施

无方向差异的旋转别名只保留一个。覆盖域可以按 canonical 语义与地图做交集截断；本体越界仍非法。

### 边界存取口

边界设施只在 canonical 允许的基线上枚举，并保留 canonical 明确允许的角落姿态。端口 stored 坐标必须指向体外第一格，不能把第二格误当作 access cell。

## 健全域约简

生成期约简必须是对所有后续实例绑定都成立的必要条件。允许的典型约简包括：

- 本体越界删除；
- canonical 明确禁止的锚点或模式删除；
- 制造模板在所有 operation 都至少激活输入和输出时，对必需整侧完全不可用的 pose 做必要条件剪枝；
- 物理投影相同的旋转或模式别名去重。

以下信息通常不得在预处理层擅自使用：

- 实例标签或具体需求分配；
- 尚未确定的 generic 端口激活数；
- routing 成功与否；
- 某次 campaign 的经验性不可行结论；
- 只在特定 sample 中观察到的候选统计。

任何新增约简都要给出必要性证明、独立反例测试和与下游精确 twin 的一致性检查。

## 幽灵空地候选域

`generate_empty_rect_domain(w, h)` 为外层给定的矩形尺寸生成所有本体在图内的绝对禁区候选。每个候选只表达矩形占格；外层模型选择唯一位置并禁止其他设施占用该区域。尺寸合法性和最小边界由调用方与 canonical contract 共同验证。

## 输出 artifact

规范输出为：

```text
data/preprocessed/candidate_placements.json
```

结构示意：

```json
{
  "facility_pools": {
    "facility_template": [
      {
        "pose_id": "p_x10_y20_o0_m_TB",
        "anchor": {"x": 10, "y": 20},
        "pose_params": {"orientation": 0, "port_mode": "TB"},
        "occupied_cells": [[10, 20]],
        "input_port_cells": [{"x": 10, "y": 19, "dir": "S"}],
        "output_port_cells": [{"x": 10, "y": 21, "dir": "N"}]
      }
    ]
  }
}
```

实际 schema、排序、字段完整性和字节身份由实现、生成器与外部 artifact checker约束。生成后至少验证：

- 每个模板池和 `pose_id` 唯一；
- 本体占格与旋转包围盒一致；
- stored port 坐标、方向和 canonical 模式一致；
- 必需端口约简没有误删合法边界 pose；
- generic 未激活口不被错误当作必需口；
- 输出能够被下游 loader、binding 和 campaign identity closure 接受。

## 重生成与换代

改变 canonical 几何、端口语义、约简、排序或 schema 时，应在同一变更中更新实现、规范、测试、artifact manifest、受影响 claim 与 campaign reset / replay 说明。旧 artifact 的身份留在历史收据或 dossier 中，不在现行规范维护 superseded 哈希链。

当前 artifact 身份通过注册 checker 查询：

```bash
python scripts/check_external_artifacts.py
```

历史版本及其当时的候选计数和哈希链保存在 [`../docs/history/convergence/spec06_candidate_placement_pre_phase3_batch4_20260812.md`](../docs/history/convergence/spec06_candidate_placement_pre_phase3_batch4_20260812.md)。
