from helpers import *
from guard import digest, REPO, SOURCES, guard
guard('tidy-before')
edit('规格/四件前置义务对照.md',[
    ('桥接器定向','桥物品来路'),('离线接续、桥定向、级间记忆','离线接续、级间记忆')])
edit('规格/内核输入.md', [('bridge.scheduling_scope=`unit`','bridge.scheduling_scope=`per_axis`；bridge.capacity=1；connection.bridge_first_contact/connection.bridge_tie=`not_applicable`')])

# Keep JSON object ordering and parameter-row ordering from the original input.
# Only migrated values, lifecycle groups, bridge sides and fingerprints change.
def order_like(new, old):
    if isinstance(new,dict) and isinstance(old,dict):
        return {k:order_like(new[k],old.get(k)) for k in [*[k for k in old if k in new],*[k for k in new if k not in old]]}
    if isinstance(new,list) and isinstance(old,list):
        if new and old and all(isinstance(r,dict) and 'axis' in r and 'lifetime' in r for r in new+old):
            lookup={r['axis']:r for r in new}
            new=[lookup[r['axis']] for r in old]
        return [order_like(v,old[i] if i<len(old) else None) for i,v in enumerate(new)]
    return new
sync=json.loads((OUT/'sync-summary.json').read_text())
for rel in sync['inputs']:
    p=ROOT/rel;old=json.loads((OUT/'before'/rel).read_text());new=json.loads(p.read_text())
    aligned=order_like(new,old)
    # Restore original per-axis-state order; a bridge side expands in place.
    state=aligned['initial_state']['nonwarehouse'].get('value')
    if isinstance(state,dict) and 'logistics' in state:
        old_sides=old['initial_state']['nonwarehouse']['value']['logistics']['poll_memory']['value']['sides']
        new_sides=state['logistics']['poll_memory']['value']['sides']
        state['logistics']['poll_memory']['value']['sides']=[s for o in old_sides for s in new_sides if s['unit']==o['unit'] and s['side']==o['side']]
    write(p,dump(aligned))
# Scalar replacement preserves the non-bridge expected parameter order above;
# projection files must keep the same order as their input.
import sys
sys.path.insert(0,str(ROOT/'数据/样例'))
from runtime_example import profile_projection
for name,source in [('kernel_profile_v1参数赋值.json','混做粉碎机两下游.json'),('分流器三路轮询-参数赋值.json','分流器三路轮询.json')]:
    write(ROOT/'数据/样例'/name,dump(profile_projection(json.loads((ROOT/'数据/样例'/source).read_text()))))
# Add the requested revision entry without rewriting any previous entry.
p=ROOT/'规格/修订记录.md'
text=p.read_text()
assert '## 2026-09-22 r25' not in text
text+='''\n## 2026-09-22 r25：双向桥接器、禁止立即返回及逐轴调度\n\n依据正式规则提交 `743f18b` 的 L24、L59、L63 和已确认游戏行为：桥四边永久双向，两对平行边独立存货分级及存取轮询，每对边上限1。相邻桥按双向端口生成两个方向PC；物品保存直接来路，禁止移回刚离开的单位，不删除反向几何通道。每个物理端口仍共享每tick单件预算。\n\n内核配置 revision=`bridge-bidirectional-2026-09-22`；`bridge.scheduling_scope=per_axis`、`bridge.capacity=1` 已定；先接及桥并列兼容轴均固定为 `not_applicable`，不再因相邻桥停止。StateSeed增加桥物品 `last_unit` 和桥轮询 `axis`；来路参与恢复与循环比较。运行语义、T5/T14、参数轴、输入规格、转移定义、覆盖表、正式投影及活动样例同步。`runtime_example.py` 的桥轴/Decision判别和逐轴参考接口一并迁移。\n\n'''
text+=f"目录版本 `{sync['catalog_version']}`，SHA-256 `{sync['catalog_sha256']}`；72条约束。54份内核输入（45样例、9fixture）及2份参数赋值的目录/轴表/配置/声明引用同步。\n\n"
text+='| 正式文件 | SHA-256 |\n|---|---|\n'+''.join(f'| {s} | `{digest(REPO/s)}` |\n' for s in SOURCES)
text+='\n本轮新增桥行为单测及指定安全集的实际结果、失败归因和旧指纹拒收对照见[2026-09-22h记录](../内核维护/2026-09-22h/记录.md)。历史证据不重锁；不登记为规格总自查或目标循环认证。T12旧断言和两处无关实现状态文字原样保留。\n'
write(p,text)
guard('tidy-after')
