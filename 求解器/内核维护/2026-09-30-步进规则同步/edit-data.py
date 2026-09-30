import sys, re, json, copy
from work import *
guard('data-before')
s=(ROOT/'数据/工具/formal_units.py').read_text().replace(r'(\d+) tick 冷却',r'冷却 (\d+) tick').replace('身份不符或任一上限用尽，断开存货端口通道','身份不符或任一上限用尽时阻断，阻断时不收货').replace('阻断恢复、设定变更时计数重置等见规格 T8','设定变更时计数的后效见规格 T9')
s=re.sub(r"'basis': '游戏规则L25、L36；任务书7 §1.1；主会话三审 §6', 'note': '[^']*', 'note_before': '[^']*'", "'basis': '游戏规则L26、L37', 'note': '冷却结束后在它的判定里按仓库可收余量尽量传输，余货留箱；每次传输后箱级冷却 5 tick，有无物品都一样；与它的送货先后无法确定'",s)
write('数据/工具/formal_units.py',s)
s=(ROOT/'数据/工具/formal_catalog.py').read_text().replace("len(task['conditions']) == 11","len(task['conditions']) == 10").replace('static-catalog-v2','static-catalog-v3')
s=s.replace("    return {'constraints': rules,", "    rule_text = texts['《明日方舟：终末地》游戏规则.txt']\n    timing = {'steps_per_tick': quantity(re.search(r'每 1/(\\d+) tick 运算一步', rule_text).group(1), '算术推论'), 'residence_ticks': quantity(re.search(r'至少 (\\d+) tick', rule_text).group(1)), 'basis': ['游戏规则·步', '游戏规则·滞留']}\n    return {'timing': timing, 'constraints': rules,")
write('数据/工具/formal_catalog.py',s)
s=(ROOT/'数据/工具/test_formal_catalog.py').read_text().replace('    def test_live_catalog_passes(self):', '''    def test_timing_mutation_is_rejected(self):
        changed = copy.deepcopy(self.catalog)
        changed['timing']['steps_per_tick']['value'] = '7'
        with self.assertRaisesRegex(AssertionError, 'timing'):
            verify(changed)

    def test_live_catalog_passes(self):''')
write('数据/工具/test_formal_catalog.py',s)
sys.path.insert(0,str(ROOT/'数据/工具'))
import formal_catalog as fc
old=json.loads((ROOT/'数据/正式静态目录.json').read_text())
new=copy.deepcopy(old)
new.update(schema='static-catalog-v3',version='2026-09-30-r30-step',sources=fc.source_snapshot())
new.update(fc.formal_projection(new['sources']))
rules='\n'.join(new['sources'][0]['lines'])
new['units']=list(fc.unit_projection(rules,new['constraints'],fc.quantity).values())
new['recipes']=fc.recipe_projection(rules)
fc.verify(new)
# 逐对象核不属于本轮时间同步的投影。
for k in ['constraints','recipes','static_checks']:
    assert old[k] == new[k], k
ou={u['id']:u for u in old['units']}; nu={u['id']:u for u in new['units']}
for k in ou:
    for f in ou[k]:
        if (k,f) not in [('协议储存箱','transfer'),('物品准入口','settings')]:
            assert ou[k][f] == nu[k][f], (k,f)
write('数据/正式静态目录.json',json_text(new))
save('catalog-change.json',{'old_sha256':digest(OUT/'before/数据/正式静态目录.json'),'new_sha256':digest(ROOT/'数据/正式静态目录.json'),'unchanged':['77 constraints','18 recipes','32 constants','19 material flows','unit dimensions/ports/inventory'],'sources':[{k:r[k] for k in ['path','sha256']} for r in new['sources']]})
guard('data-after')
