"""记录前两包注册表说明的历史引用，保持配置原字节。"""
from guard import OUT
s=OUT/'package3-staging'
note='''\n注册表遗留说明的读法：本表逐字投影配置元数据，运行定义以现行正文为准。initialization.other_inventory 的 coverage_loss 所写“关闭时intake”属于已删除的历史阶段，当前关闭时不进缓存；warehouse.external_supply 的“physical/授权前”是旧实现读取点名称，当前 D.2 按受限转移§6.1在仓库容量读取前检查；warehouse.periodic_lift 的 extension_gate 所指旧§6.5.5现由受限转移§6.5承接。前两包配置保留原字节，这些证据文字不恢复旧语义。表内未写书名的§6.5也指受限转移定义。\n'''
p=s/'规格/受限模型声明.md';t=p.read_text();t=t.replace('\n## 3.',note+'\n## 3.',1);p.write_text(t)
p=s/'规格/选择点参数轴.md';t=p.read_text();t=t.replace('\n## 3. 输入接口', '\n表内meaning及据为配置原文；旧任务编号与未写书名的§6.5仅定位历史证据或[受限转移定义](受限转移定义.md)的对应接口。注册表遗留说明（已删除的intake阶段、旧读取点名称与旧小节号）的限定见[受限模型声明](受限模型声明.md)§2，不恢复旧运行语义。\n\n## 3. 输入接口');p.write_text(t)
p=s/'规格/运行语义.md';t=p.read_text();a=t.index('因此 **H 成立');b=t.index('\n\n独立的制造占地核验',a);t=t[:a]+'''因此 **H 成立则全题无达标解；在达标布局论域内 H 已排除**。这是按H对正式必要条件作出的条件论证，不使用“题目必有解”的公理。H不是现行参数轴，当前规则每步只判定一次不会推出每tick同侧至多一件；每tick有8步。不新增“所有执行必进入循环”的命题。（据：目标、循环态、约束·取货口配置；条件推论）'''+t[b:];p.write_text(t)
