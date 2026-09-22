# 本轮完整文件清单

截止：2026-09-22；相对 HEAD 的已核对业务改动及接续生成物。未删除文件。

| 完整路径 | 变动及核对说明 |
|---|---|
| `/home/zhuran24/zmd-research-fresh/求解器/crates/kernel/tests/fixtures/benchmark_1000.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/crates/kernel/tests/fixtures/benchmark_brick.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/crates/kernel/tests/fixtures/benchmark_brick_60.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/crates/kernel/tests/fixtures/bridge.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/crates/kernel/tests/fixtures/core_inbound.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/crates/kernel/tests/fixtures/priority.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/crates/kernel/tests/fixtures/revision_r2_branch_cut.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/crates/kernel/tests/fixtures/revision_r2_phase_control.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/crates/topology/src/lib.rs` | 上一席改动已核对并保留（含并发期间的引用重锁）；核心入库计划只接受两成品；删除台数豁免，按非成品零入库解释；三条实际循环义务保持 Unknown |
| `/home/zhuran24/zmd-research-fresh/求解器/crates/topology/tests/validation.rs` | 上一席改动已核对并保留（含并发期间的引用重锁）；72条覆盖；32/33台×19物品共38组核心检查正负例及三条 Unknown 断言 |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/候选B/来源清单.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；重锁当前正式源、候选和目录；三项临时来源迁至等字节存档，16项均核哈希 |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/候选B/校验报告.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；与本次 release topology 输出逐字节相等：4924通过、0失败、75未知 |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/候选B/转换说明.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；当前72条、来源重定位及未获运行认证的范围 |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/候选B/验证记录.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；现行静态计数与2026-09-19历史验证分区，旧结果保留 |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/工具/check_revision.py` | 上一席改动已核对并保留（含并发期间的引用重锁）；计数72；允许本轮输出写入内核维护目录 |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/工具/convert_candidate_b.py` | 上一席改动已核对并保留（含并发期间的引用重锁）；失效临时任务来源改指 SHA 完全相同的仓库存档 |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/工具/formal_catalog.py` | 上一席改动已核对并保留（含并发期间的引用重锁）；约束计数72；删除 plant_trigger 提取 |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/工具/test_formal_catalog.py` | 上一席改动已核对并保留（含并发期间的引用重锁）；增加无 plant_trigger 投影成功和残留键拒收两项回归 |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/check_examples.py` | 上一席改动已核对并保留（含并发期间的引用重锁）；SOURCE_HASHES 重锁当前正式三源；未修改原样例结构检查逻辑 |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/kernel_profile_v1参数赋值.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/双门窗口恢复.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/同刻双箱争余量.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/成熟旧货重试.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/无线一满一可收.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/无线全拒收.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/无线多格全收.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/无线多格歧义.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/无线空箱.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/无线部分接收.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/生产环带.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/累计审计与窗口周期.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/累计调低保留.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/累计调高资格.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/装载与普通制造.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/身份实际切换.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/身份断边恢复.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/阻尼恢复.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/任务7内核/静止成熟与暂停键.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/传输拒收与暂停核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/分流器三路轮询-参数赋值.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/分流器三路轮询.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/双成品制造砖.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/双成品满仓起动试作.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/密集制造闭环基础.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/密集制造闭环序0核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/密集制造闭环序1核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/密集制造闭环序2核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/密集制造闭环序3核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/密集制造闭环序4核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/密集制造闭环序5核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/密集结点循环种子核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/密集结点核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/密集结点闭环核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/桥接器双通路.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/混做粉碎机两下游.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/生产循环环带.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/研磨混做核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/轮询均分序0核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/轮询均分序1核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/轮询均分序2核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/轮询均分序3核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/轮询均分序4核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/轮询均分序5核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/轮询均分核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/阻尼切支恢复核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/样例/阻尼连续带核验.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；仅重锁实际变动的目录/参数轴或配置来源 SHA；数据内容不变，已逐对象比对 HEAD |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/正式静态目录.json` | 上一席改动已核对并保留（含并发期间的引用重锁）；sources/constraints/static_checks 独立重建字节相等；r23、72条、32常量 |
| `/home/zhuran24/zmd-research-fresh/求解器/数据/规则覆盖表.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；规则114行、任务16行、约束72条及原据行映射 |
| `/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/检查器A/projections.py` | 接续补充；仅修改说明字符串：71条是固定旧版本，不是现行条数 |
| `/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/检查器A/说明.md` | 接续补充；补明实现/61项旧自测绑定71条版本；当前72条尚未支持，不伪装升级 |
| `/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/生成/代码/检查器乙.py` | 接续补充；输出说明删除写死71条，保留未实现及禁止全静态通过标记 |
| `/home/zhuran24/zmd-research-fresh/求解器/构造/第一张全厂候选/生成/代码/检查器甲.py` | 接续补充；输出说明删除写死71条，保留全部实现与未通过边界 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/check_revision.py` | 上一席改动已核对并保留（含并发期间的引用重锁）；任务16行、约束72条、本轮只读指纹；保留既有其余门禁及其失败 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/修订记录.md` | 接续补充；保留旧记录；登记r23目录、来源与本次接续安全验证结果和未通过项目 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/内核输入.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；更新现行正式源标签；原轴取值、接口和生命周期不变 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/内核输出.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；更新现行正式源标签；原轴取值、接口和生命周期不变 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/受限模型声明.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；更新现行正式源标签；原轴取值、接口和生命周期不变 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/受限转移定义.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；当前来源标签与原证明绑定版本分开；未修改转移算法 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/四件前置义务对照.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；更新现行正式源标签；原轴取值、接口和生命周期不变 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/推导/三种相位不改产量-v2.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；当前植物零入库引用改引非成品零入库；旧被审指纹/范围明确保留，不重新认证历史证明 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/推导/回路总数决定论-v2.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；当前植物零入库引用改引非成品零入库；旧被审指纹/范围明确保留，不重新认证历史证明 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/推导/总纲-流量存量相位.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；当前植物零入库引用改引非成品零入库；旧被审指纹/范围明确保留，不重新认证历史证明 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/规则覆盖表.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；规则114行、任务16行、约束72条及语义去向；旧轮自核单独标为史料 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/运行语义.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；三源指纹和条文依据同步；植物零入库不限台数，普通运行仍按实际余量接收 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/选择点参数轴.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；更新现行正式源标签；原轴取值、接口和生命周期不变 |
| `/home/zhuran24/zmd-research-fresh/求解器/规格/选择点清单.md` | 上一席改动已核对并保留（含并发期间的引用重锁）；更新现行正式源标签；原轴取值、接口和生命周期不变 |

接续生成物（逐文件）：

| 完整路径 | 说明 |
|---|---|
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/check_positive.py` | 本次接续复验/守卫/汇总脚本，不写历史目录 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/commands.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/final/commands.json` | 最终正向链或旧 SHA 拒收对照的输入/输出/命令证据 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/final/kernel-check.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/final/kernel-run.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/final/kernel-seed.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/final/kernel-verify-record.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/final/positive-input.json` | 最终正向链或旧 SHA 拒收对照的输入/输出/命令证据 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/final/positive-run.json` | 最终正向链或旧 SHA 拒收对照的输入/输出/命令证据 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/final/positive-validation.json` | 最终正向链或旧 SHA 拒收对照的输入/输出/命令证据 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/final/seed-output.json` | 最终正向链或旧 SHA 拒收对照的输入/输出/命令证据 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/final/stale-catalog-input.json` | 最终正向链或旧 SHA 拒收对照的输入/输出/命令证据 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/final/stale-catalog.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/kernel-check.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/kernel-run.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/kernel-seed.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/kernel-verify-record.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/positive-input.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/positive-run.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/positive-validation.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/seed-output.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/stale-catalog-input.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/positive/stale-catalog.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-complete-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-complete-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-complete-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-complete-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-complete-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-complete-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-complete.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync-final-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync-final-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync-final-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync-final-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync-final-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync-final-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync-final.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit-sync.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/audit_sync.py` | 本次接续复验/守卫/汇总脚本，不写历史目录 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/build-debug-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/build-debug-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/build-debug-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/build-debug-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/build-debug.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/build-release-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/build-release-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/build-release-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/build-release-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/build-release.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/candidate-b-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/candidate-b-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/candidate-b-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/candidate-b-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/candidate-b-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/candidate-b-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/candidate-b.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check-final-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check-final-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check-final-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check-final-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check-final-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check-final-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check-final.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-check.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy-final-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy-final-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy-final-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy-final-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy-final-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy-final-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy-final.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/cargo-clippy.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/catalog-regressions-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/catalog-regressions-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/catalog-regressions-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/catalog-regressions-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/catalog-regressions.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/catalog-verify-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/catalog-verify-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/catalog-verify-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/catalog-verify-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/catalog-verify.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/changed-files.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/changed-files.md` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/command-results.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/commands.jsonl` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/concurrent-writer.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/delivery-history-diff.json` | 历史快照差异：新增1、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/delivery-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/delivery-snapshot-stop.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/examples-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/examples-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/examples-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/examples-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/examples-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/examples-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/examples.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/final-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/final-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/finish_record.py` | 本次接续复验/守卫/汇总脚本，不写历史目录 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/grep-current-candidates.txt` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/grep-inventory.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/initial-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/initial-status.txt` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/initial-worktree.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/initial-worktree.patch` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc-final-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc-final-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc-final-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc-final-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc-final-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc-final-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc-final.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-doc.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib-final-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib-final-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib-final-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib-final-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib-final-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib-final-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib-final.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-lib.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference-final-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference-final-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference-final-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference-final-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference-final-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference-final-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference-final.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/kernel-reference.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive-final-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive-final-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive-final-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive-final-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive-final-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive-final-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive-final.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/positive.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/protected-sources.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/read-only-audit.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/reader-review.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/run_step.py` | 本次接续复验/守卫/汇总脚本，不写历史目录 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/safe_suite.py` | 本次接续复验/守卫/汇总脚本，不写历史目录 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-final-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-final-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-final-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-final-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-final-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-final-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-final.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-initial-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-initial-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-initial-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-initial-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/spec-check-initial.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/structured-summary.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-cargo-check-final-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-cargo-check-final-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-cargo-check-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-cargo-check-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-cargo-clippy-final-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-cargo-clippy-final-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-cargo-clippy-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-cargo-clippy-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-kernel-doc-final-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-kernel-doc-final-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-kernel-doc-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-kernel-doc-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-kernel-lib-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-kernel-lib-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-kernel-reference-final-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-kernel-reference-final-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-kernel-reference-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-kernel-reference-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-doc-final-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-doc-final-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-doc-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-doc-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-lib-final-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-lib-final-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-lib-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-lib-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-validation-final-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-validation-final-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-validation-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/suite-topology-validation-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/sync-audit.json` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc-final-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc-final-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc-final-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc-final-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc-final-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc-final-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc-final.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-doc.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib-final-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib-final-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib-final-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib-final-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib-final-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib-final-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib-final.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-lib.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation-final-active-after.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation-final-active-before.json` | 活动源码/文档/输入 SHA-256 快照，用于排除并发漂移 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation-final-after-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation-final-after-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation-final-before-history-diff.json` | 历史快照差异：新增0、删除0、修改0 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation-final-before-history.json` | 含忽略文件的三个历史目录 SHA-256 快照 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation-final.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/topology-validation.log` | 本次命令完整输出；返回码见接续 commands.jsonl |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/resume/上一席记录-并发任务结束.md` | 上一席最终记录的字节原样存档；其命令与本次接续命令分开 |
| `/home/zhuran24/zmd-research-fresh/求解器/内核维护/2026-09-22e/记录.md` | 接续核对、并发诊断、检索、指纹或完整交付清单 |
