# 整数步运行内核

日期：2026-09-30。版本：r30；1步=1/8 tick。内核执行固定输入的有限轨迹、诊断生产周期和独立重放；不证明种子可达、全称达标或最优布局。

现行入口为[运行语义](../../规格/运行语义.md)、[受限转移定义](../../规格/受限转移定义.md)、[输入](../../规格/内核输入.md)与[输出](../../规格/内核输出.md)。输入kernel-input-v4、目录static-catalog-v3、配置kernel_profile_v2（66轴）、运行记录kernel-output-v5、周期证书kernel-cycle-v4、生产键phase-cycle-key-v2。

每步结束到时制造，按元件层数和接通序逐个判定，再开始制造。非分流器上游随收货组一起判定；带内成熟件即时前挪，轮询只在成功时更新。准入口拒收不改变通道。层数不确定选支/环上锚点及箱无线相对送货次序显式输入。

从求解器目录构建使用共享target、默认profile：

```bash
CARGO_TARGET_DIR="$PWD/target" cargo build --workspace -j 4
```

命令接口：check、run --steps N、cycle --max-steps N、request、seed、checkpoint、verify-record、verify-cycle、verify-batch。run可关闭记录，cycle可无引用记录但仍独立重放；完整开关见输出§6。旧输入不兼容，迁移另写新文件，见[步进样例](../../数据/样例/步进/README.md)与[历史清单](tests/历史说明.md)。

测试包括kernel库、reference的九例4000步sim2差分及Python独立账审；topology库/validation及两包doc测试另属安全集。2026-09-30维护只允许[任务书](../../内核维护/2026-09-30-步进规则同步/任务书.md)列出的安全命令，每条必须经过[run.sh](../../内核维护/2026-09-30-步进规则同步/run.sh)前后历史哈希守卫；不执行workspace测试或批量写记录入口。验证结果、限制和日志见[维护记录](../../内核维护/2026-09-30-步进规则同步/记录.md)。

周期边界与读取点见[周期键读取审计](周期键读取审计.md)。unsupported/unresolved/inconclusive均不表示游戏无解；diagnostic_cycle不等于完整基地周期或全称认证。
