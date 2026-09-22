# Rust 受限运行与生产周期内核

日期：2026-09-21。状态：任务书7工程同步已实现，定向验收见[内核验收](../../会议成果/任务书7执行/内核验收.md)。当前输出为有限运行记录或工程诊断周期；独立席复核、正式循环对应及全称达标认证分别按验收中的义务承接。

内核读取 `kernel-input-v3`、现行[配置](../../规格/内核配置-v1.json)和[正式目录](../../数据/正式静态目录.json)。目录、三份正式源、轴表、配置及实际读取的语义文件通过完整SHA-256绑定。运行输出 `kernel-output-v4`，周期结果输出 `kernel-cycle-v3`，生产键为 `phase-cycle-key-v1`。

## 运行与验证

下面命令在 `/home/zhuran24/zmd-research-fresh/求解器/` 执行，输出路径可换为使用者有写权的位置。

```bash
cargo build --release -p kernel --target-dir /home/zhuran24/zmd-research-fresh/求解器/target

target/release/kernel check 数据/样例/任务7内核/无线部分接收.json --config 规格/内核配置-v1.json

target/release/kernel run 数据/样例/任务7内核/无线部分接收.json --config 规格/内核配置-v1.json --ticks 6 --format checkpoint_delta --checkpoint-interval 16 --out 会议成果/任务书7执行/证据/内核/示例运行.json

target/release/kernel verify-record 会议成果/任务书7执行/证据/内核/示例运行.json --config 规格/内核配置-v1.json

target/release/kernel cycle 数据/样例/任务7内核/累计审计与窗口周期.json --config 规格/内核配置-v1.json --max-ticks 30 --no-record --out 会议成果/任务书7执行/证据/内核/示例周期.json

target/release/kernel verify-cycle 会议成果/任务书7执行/证据/内核/示例周期.json --config 规格/内核配置-v1.json
```

`seed`派生新调度起点的冗余上下文，`check`只校验装载。`check --cycle-domain`逐项报告D.1—D.5，`trajectory_executed=false`。这些命令不步进。原历史样例仍锁旧目录/轴表，当前可运行机制输入在[任务7内核样例](../../数据/样例/任务7内核/)。

`run`保持真实有限仓库；`cycle`在D域使用数学生产代表，分别保存实际入库、玩家拿取和代表调整。证书环境前提固定为“仓库收得下成品。”；代表化不是玩家动作。周期率始终由核心与无线实际入量除以真实正周期计算。

现有生成器对找到的周期给 `diagnostic_cycle`。正反向循环对应和全部可达循环三组检查单独列出：一般真实调度的前向对应为unresolved，具体完整基地复原及全称覆盖为not_claimed。整数工程率达标也保留这一诊断范围。

`cycle`默认把独立记录写在证书旁的`<证书名>.record.json`，`--no-record`仅保存可重放输入、端点及账。两种模式都核原种子前缀，另从周期起点重跑P刻并比完整终态。`--search-checkpoint-interval`改变搜索检查点间隔；摘要只找候选，完整键内容重放比较后才判相等。

`checkpoint`先验记录或证书，再导出完整末态；after_closure从下一刻继续，参数、游标、台账和待办身份保持。`run --no-output`保持同一转移，`--no-cache`用于直接计算对照。运行技术停止退出2；周期预算未决退出0并返回inconclusive，诊断周期退出0；退出码与认证范围分别读取。

## 当前行为与停止范围

- 无线传输逐物种按可收数量送出；空箱、全拒收、部分及全部接收均启动5 tick冷却。同种多编号格全部送出/全部拒收可执行；严格部分接收而残留位置有歧义时，在提交前返回unsupported。
- 准入口从原几何候选读取当前身份，重算三类原因，恢复后完整重建图、级、阻尼和指针。仅改累计阈值后的种子保留真实n，支持n>C的耗尽状态；运行中调试动作回放仍为unsupported。
- 判定排序固定放F组，当前镜像、恢复和输出逐值核验。已发生尝试后参与侧前移；单级非运输输出已短路阻尼；成功后反复扫描可唤醒成熟旧货。
- 新键截断成熟运输年龄、删除无读取非运输时标并合并同格同种审计组、删除无上限累计或饱和固定C、保留门窗及图维护；暂停制造按剩余工作量编码，完整原始截止及事件id留在StateSeed。[读取审计](周期键读取审计.md)给出条件及保留量。
- 玩家拿取、离线、调试/拆建、连续实数后态、一般失败环真实唤醒及完整证明求值器继续按具体未完成项停止或声明范围。关闭制造的intake工程后态与任务5默认程序尚待联合推导。

## 批量入口与历史

`kernel verify-batch <目录> --config 规格/内核配置-v1.json`只读验证当前v4记录和v3周期，使用AJV 2020结构检查、Rust完整重放和Python逐事件仓库/编号箱格/冷却重算。老v1—v3运行记录与v1—v2周期列为历史；未知版本和尚无语义验收的直接证明类型明确拒收。旧参考执行器尚未迁移v4，当前批量入口只接受kernel生产者。

任务7证据及实际命令见[证据目录](../../会议成果/任务书7执行/证据/内核/)。旧性能报告和141项测试数字留在各历史目录，本轮只运行实质改动所需检查。
