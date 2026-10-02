# 程序来源

engine_a.py复制自第92轮D组factory_check.py，engine_b.py摘录第95轮S组factory_probe.py的EngineB类。原文件只读，源哈希见inputs.json。甲按进入时刻，乙按货龄和到期时刻分别实现一步；不共享状态转移。

本轮副本增加两种成品分别停收；甲另记收货/拒收。debug_engine_a.py与debug_engine_b.py仅进一步加制造开关及暂停进度，供调试操作核对。缓存内容只在初始化空状态时设空，此后的调试操作不写缓存。

新接法、源端单位建造排序、固定偏移不变量、完整状态周期确认及数值账本在factory_check.py等本轮脚本中。辅助引擎文件不是独立入口，复现入口见报告第10节。
