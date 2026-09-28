# README-madSUN

> 原文：https://docs.qq.com/aio/DTmluZ1diWlpQZldw?p=cRL5oXezEI87KqsXuOEng7　上级：[完美的终末地工业模拟代码](完美的终末地工业模拟代码.md)

````mermaid
## 时序图

```mermaid
sequenceDiagram
    autonumber
    participant U as 上游
    participant C as 当前
    participant D as 下游

    rect rgb(255, 255, 255)
        note over U,D: 步骤 1: 向下传递请求
        U->>C: 请求 (当U试图输出时)
        activate C
        C->>C: 记录请求
        C->>D: 请求 (当C试图输出时)
        activate D
        D->>D: 记录请求
        deactivate D
        deactivate C
    end

    rect rgb(255, 255, 255)
        note over U,D: 步骤 2: 决定路径 (可选择)
        C->>C: 选择上游 (e.g. 轮询)
    end

    rect rgb(255, 255, 255)
        note over U,D: 步骤 3: 回答请求
        D->>D: 是否可接受
        D->>C: 接受 (如果可接受)
        C->>C: 是否可接受 (检查自己可接受或下游可接受)
        C->>U: 接受 (接受)
    end

    rect rgb(255, 255, 255)
        note over U,D: 步骤 4: 物品移动
        U->>C: 移动物品
        C->>D: 移动物品 (如果D接受)
    end

    rect rgb(255, 255, 255)
        note over U,D: 步骤 5: 提交 与 重置
        U->>U: 更新状态
        C->>C: 移动物品, 接受输入, 重置标签
        D->>D: 收集物品, 重置标签
    end
```

### 2026.03.16 更新

增加了“剪枝跳过”逻辑，如果前方空且当前想递送，则直接递送物品，跳过后续阶段. 遗憾的是，依然未能实现优先级. 

## 测试

```sh
uv run pytest
```

- 还未能实现分流器-汇流器直接相连时的优先级（测试失败）
- 还未测试“阻尼”现象，猜测多半无法实现（其应该和优先级有相同的诱发原因）

## Usage

```python
from simulation import *

# 建立组件列表
components = [
    ...
]

# 连接组件
# upstream.connect_to(downstream)
components[...].connect_to(...)
components[...].connect_to(...)
components[...].connect_to(...)
...

# 模拟 (方式 1)
controller = Controller(components)
for _ in range(total_ticks):
    controller.step()

# 模拟 (方式 2)
run_simulation(components, total_ticks)
```
````
