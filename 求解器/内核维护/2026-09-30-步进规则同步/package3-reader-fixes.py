"""包三读者自审修正暂存稿；不执行测试。"""
from pathlib import Path
from guard import OUT
s=OUT/'package3-staging'
p=s/'规格/运行语义.md';t=p.read_text()
t=t.replace('布局工具按 样例工具的代表选支规则填选支','布局工具按显式代表规则填选支').replace('缓存格通往存货物品格的闸只在开工时打开','存货物品格通往缓存格的闸只在开工时打开')
t=t.replace('每个元件、每个非运输单位每步恰判定一次（L26）','每个元件、每个非运输单位每步只判定一次（L26）')
t=t.replace('一个成员的物品送走后，它在后面的收货方里就没有可送的了。','一个成员成功送出后本步不可再次送出；带链随后跟上的头件也受本步已判定限制。')
t=t.replace('传输按原实现「能送多少送多少」','传输按「能送多少送多少」').replace('按原有选格与容量守卫','按选格与容量守卫').replace('沿用现有实现：收货','收货').replace('，与现状同','').replace('，全部沿用。显式补矿事件的时刻改用步','均按当前状态核验。显式补矿事件时刻用步').replace('与现状一样在触及时','在触及时')
t=t.replace('按先后逐个判定（§3.4—§4.6）','按先后逐个判定（§3.4、§4.4—§4.6）')
t=t.replace('内核没有独立的每 tick 每端口次数守卫。它是求解约束「端口速率」，由滞留 8 步和运输格上限 1 推出，不是规则；运行中不另加。','内核没有独立的每 tick 每端口次数守卫。约束「端口速率」由滞留8步和运输格上限1推出，运行中不另加计数预算；以下假设H按每tick计，与现行每步至多外送一件不同。')
t=t.replace('配方（沿用 `manufacturing.recipe_match_scope/completeness/quantity_match/extra_items/recipe_selection/input_slot_selection` 各轴的现值）','配方（按 manufacturing 的 recipe_match_scope、recipe_completeness、recipe_quantity_match、recipe_extra_items、recipe_selection、input_slot_selection 各轴取值）')
t=t.replace('（与 sim2 的 eager 模式逐状态相同，核对-模拟2「即时前挪」一节）','；链式共同构型的差分范围见[差分记录](../内核维护/2026-09-30-步进规则同步/差分.md)')
p.write_text(t)
p=s/'规格/内核输入.md';t=p.read_text().replace('unknown/unresolved 不被悄悄填默认，not_applicable 须有可核的不适用范围。','status只接受specified、derived、unresolved、not_applicable；后两者value必须null，实际执行读取须已解，所有basis须非空。不适用只用于获准的字段与范围，不会被默填默认。')
p.write_text(t)
# 选择点编号不承担现行配方/阶段语义；修正缺失的链接及直接来源提示。
p=s/'规格/受限模型声明.md';t=p.read_text().replace('可重跑核验见第三轮任务验证的自查报告。','历史几何核验见第三轮任务验证的自查报告；该报告的旧版本状态不替代本轮验证。')
p.write_text(t)
print('reader corrections staged')
