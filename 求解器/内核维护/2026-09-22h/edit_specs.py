from helpers import *
from guard import REPO, SOURCES, digest, guard
guard('edit-specs-before')
config=json.loads((ROOT/'规格/内核配置-v1.json').read_text())
changed_axes=['bridge.capacity','bridge.scheduling_scope','connection.bridge_first_contact','connection.bridge_tie','offline.direction_effect']
for filename in ['选择点参数轴.md','内核输入.md','受限模型声明.md']:
    p=ROOT/'规格'/filename
    lines=p.read_text().splitlines()
    for i,line in enumerate(lines):
        for name in changed_axes:
            if not line.startswith('| `'+name+'` |'):continue
            r=config['axes'][name]; value=json.dumps(r['value'],ensure_ascii=False)
            if filename=='选择点参数轴.md':
                lines[i]=f"| `{name}` | {r['choice']} | {r['lifetime']} | {'known' if r['disposition']=='已定' else '输入/工程接口'}：{value}；{r['meaning']}。据：{r['basis']} |"
            elif filename=='内核输入.md':
                group='fixed' if r['lifetime']=='F' else 'fixedness_unproven'
                lines[i]=f"| `{name}` | `{group}`；{r['lifetime']} | {r['choice']}；{value}；{r['meaning']}。据：{r['basis']} |"
            else:
                lines[i]=f"| `{name}` | {r['disposition']} | `{value}`：{r['meaning']} | 据：{r['basis']} | {r['coverage_loss']} | {r['extension_gate']} |"
    write(p,'\n'.join(lines)+'\n')

def lines_replace(file,mapping):
    p=ROOT/file; lines=p.read_text().splitlines()
    for prefix,new in mapping.items():
        indices=[i for i,l in enumerate(lines) if l.startswith(prefix)]
        assert len(indices)==1,(file,prefix,indices)
        lines[indices[0]]=new
    write(p,'\n'.join(lines)+'\n')

lines_replace('规格/运行语义.md',{
    '| `layout` |':'| `layout` | 单位身份、机型、占格、朝向、端口；建成状态与建造次序；桥接器四边固定双向及本地轴身份 | 结构及建造历史；调试形状变更用重建表示；据：基地、蓝图、旋转、端口、桥接器 |',
    '| `logistics` |':'| `logistics` | 当前通道、准入口阻断、接通时刻与次序；各调度辖域的级和轮询记忆；桥按每对平行边各分存取侧；运输物品入格时刻及桥格物品来路 | 桥两轴独立分级、轮询，各格上限1；来路进入完整状态以禁止移回刚离开的单位。据：规则L24、L29—32、L59、L63 |',
    '外部通道按已定':'外部通道按已定 `connection.port_meeting=shared_edge_opposite` 形成：相邻格共边全长重合、法向相反、源可取且目标可存，至少一端为运输单位。桥四边一直双向，接通史不改变其角色；相邻两桥即使没有其它邻居也形成双向连接，在内核中表示为两个相反方向的 PC。每个 PC 仍由两端较晚建成时刻登记接通；同一物品不能移回刚离开的单位，故沿相邻桥前进后不能立即退回。内部缓存路径另按规则L18表示。（据：规则L12、L16、L18、L24、L28、L63）',
    '| 桥接器 |':'| 桥接器 | 两对平行边各一独立格，各上限1；分别记录滞留和直接来路 | 1×1，四边固定存货兼取货；不先接定型，不换轴；同种可同时占两轴；存货分级和存取轮询按每对边独立，取货侧不分级 | 规则L13、L24、L29—32、L59、L63 |',
    '| 桥接器方向 |':'| 桥接器端口角色 | 四边永久双向，不存在方向定型；按所在格同轴穿过 | 接通重排不改变角色；物品来路随成功移动更新，不随轮询或时间推进清空 | 桥接器、移动、离线 |',
})
edit('规格/运行语义.md',[
    ('桥接器 `ports.layouts` 只是编码，不可绕过接通史任选方向。','桥接器 `ports.layouts` 只有四边固定双向的一种端口型，旋转只改变本地轴到世界坐标的映射。'),
    ('桥接器亦按单位的存取两侧','桥接器按每对边各分存取两侧'),
    ('桥接器两轴共同分级','桥接器每对边独立分级'),
    ('及桥接器定向依赖','及桥接器两轴的调度状态'),
    ('同刻多边和平局、桥接器互依赖仍待审','同刻多边的接通平局仍须显式排序'),
    ('桥接器两轴共同参与该单位的存货侧/取货侧，物品格独立不产生调度例外（T14）','桥接器每对平行边各有存货侧/取货侧，分级和轮询均独立（T14）'),
    ('运输目标记录新入格时间','运输目标记录新入格时间，桥目标同时记录刚离开的单位，后续尝试不得返回该单位'),
    ('但不能由此推出轮询与分级独立（T14）','轮询与分级独立另由规则L63给出（T14）'),
    ('轴身份、容量、滞留和按单位调度分别保留。','轴身份、容量与滞留保留；调度按每对边独立。')])

p=ROOT/'规格/选择点清单.md';t=p.read_text();a=t.index('## T5.');b=t.index('## T6.',a)
write(p,t[:a]+'''## T5. 蓝图接通先后、平局及桥接器双向端口

蓝图逐个建成，传送带最后；通道初次接通取两端较晚建造时刻。同刻接通边的排序仍由显式接通平局轴表达；建造期时间及判定交织见 T11。

桥接器四边始终为存货兼取货端口，接通不会使端口定型。相邻桥自动形成双向连接；没有先接依赖、递归定向或定向平局。兼容字段 `connection.bridge_first_contact` 和 `connection.bridge_tie` 均已定为 `not_applicable`。运行方向由物品来路及可接收的另一端决定，物品不移回刚离开的单位。（据：规则L24、L63）

相遇谓词为 `shared_edge_opposite`：相邻格共边全长重合、法向相反，源可取且目标可存，至少一端运输；仅共角点不成通道。桥两边同时接向内送料带时两边均接通，进入的物品没有合法出口。（据：规则L12、L16、L24、L63）

'''+t[b:])
t=p.read_text();a=t.index('## T14.');b=t.index('## T15.',a)
write(p,t[:a]+'''## T14. 桥接器两对边独立及容量

两对平行边互不相干，各有一个物品格，上限1。同种物品可以同时占两轴，每格分别核滞留；物品不能换轴。每对边独立执行存货分级和存取轮询，取货侧作为运输单位不分级，另一轴直接连接分流器不会影响本轴的级成员、优先级或游标。（据：规则L13、L29—32、L59、L63）

`bridge.inventory_scope=two_independent_axis_slots`、`bridge.capacity=1`、`bridge.scheduling_scope=per_axis` 均为已定值。排除两轴共享库存、共享轮询或共享分级，以及先接定型。规则L59的括号只例外化格数，不例外化容量；容量1由正式条文给出。

每对边一进一出时同轴穿过；两端都向内送料时两端均可接入，但该格存入后不能出去。相邻桥的物品移动必须保存直接来路并阻止退回；该守卫不删除几何通道。T3 的一般双端协调和级内续接、T10 的离线后效仍按各自覆盖范围处理。

'''+t[b:])
edit('规格/选择点清单.md',[
    ('已建桥方向','桥四边双向角色'),('完整通道和桥定向','完整通道及桥轴身份'),
    ('桥接器按轴拆调度','桥接器跨轴共享调度'),
    ('轴身份、容量、滞留和按单位调度分别保留。','轴身份、容量与滞留保留；调度按每对边独立。')])

lines_replace('规格/内核输入.md',{
    '| `units[].port_layout`':'| `units[].port_layout` | 非桥接器为目录 ports.layouts 的零起点索引；桥接器必须 null，四边固定双向，不接受方向选择。据：规则L63 |',
    '| `units[].bridge_axes`':'| `units[].bridge_axes` | 所有单位均为 null；字段名保留用于拒绝旧先接方向声明。桥本地 vertical/horizontal 轴由目录固定，随实例旋转。据：规则L63 |',
    '桥方向的验证必须':'桥四边永久双向；装载时验证 `bridge_axes=null`，不推导先接方向。相邻桥形成两个相反方向的 PC，接通时刻均取两端较晚建成时刻。两个兼容轴 `connection.bridge_first_contact`、`connection.bridge_tie` 固定为 `not_applicable`，不再触发定向停止。据：规则L16、L24、L28、L63。',
    '| `inventory[]`':'| `inventory[]` | `{slot,contents}`，contents 为 `{item,quantity,entered_at,last_unit?}` 数组；运输逐件滞留必须可核。last_unit 为桥格内物品刚离开的单位 id，须经本轴真实入边可达；无先前移动的初态可省略或为 null。成功移入桥时覆盖此字段，离开或清空随物品移除，时间推进不清除；禁止向 last_unit 移动。该字段参与检查点、重放、闭包及生产循环键。据：规则L24、L59、L63 |',
    '| [桥接器双通路.json]':'| [桥接器双通路.json](../数据/样例/桥接器双通路.json) | 当前可执行输入；四边双向，两轴各自容量、滞留、分级和轮询。 |',
})
p=ROOT/'规格/内核输入.md';t=p.read_text()
a=t.index('物理面对面关系可用稳定无向');b=t.index('\n',a)
t=t[:a]+'桥与桥之间同一对物理端口形成两个相反方向 PC，共享各物理端口每 tick 的单件预算；没有外接邻居也不删除这两个方向。物品来路只影响可动守卫，不影响通道存在性。据：规则L16、L24、L63。'+t[b:]
t=t.replace('桥接器的四个物理端口位置从目录全部 layouts 的位置并集取得，未定方向不删除端口；pending/unresolved 端口角色为空。','桥接器四个物理端口取目录唯一型，角色均为 bidirectional。')
t=t.replace('两格独立不等于轮询按轴独立。','两轴的格、分级和轮询均独立。')
t=t.replace('先接方向由历史导出','端口始终双向').replace('结构变化与桥方向','结构变化与桥端口').replace('库存去向、桥定向、轮询','库存去向、桥轴身份、轮询').replace('已建桥定向','桥四边双向角色')
t=t.replace('每条为 `{unit,side,graded,current_level,levels}`','桥接器每轴各分 input/output 两侧，共四条；每条为 `{unit,side,axis?,graded,current_level,levels}`，桥必填 axis=vertical/horizontal，其余省略或 null')
t=t.replace('稳定成员类别编码，分级更新','稳定成员类别编码；桥在 unit 后增加 `|<axis>` 段，分级更新')
t=t.replace('桥接器按 unit 只有两条侧记录，禁止按轴重复四套。','桥接器按每对边各分存取两侧，共四条记录；不同轴的级成员、最高级和游标不得混用。')
write(p,t)
edit('规格/受限转移定义.md',[
    ('端口/桥方向已解','端口型已解，桥四边固定双向'),
    ('桥同轴；其余已定类型','桥同轴且目标不是物品刚离开的单位；其余已定类型'),
    ('按单位核轮询权限','按本轴核分级与轮询权限'),
    ('端口/桥方向','端口型/桥轴身份'),
    ('运输格按(item,规范剩余滞留)保留','运输格按(item,规范剩余滞留,last_unit)保留')])
p=ROOT/'规格/受限转移定义.md';t=p.read_text();t+='\n桥接器的成功入格事务记录 `last_unit=源单位`；离开清格时移除，时间推进保留。该来路与数量、物种、滞留一起保存和比较；禁止立即返回不删除 PC。分级、轮询和最高级均以 `(unit,axis,side)` 为桥调度辖域，两轴互不干扰。（据：规则L24、L63；内核输入§6.3）\n';write(p,t)
edit('规格/参数扫描约减.md',[
    ('桥方向','桥轴身份'),('及entered_at','及entered_at/last_unit'),
    ('另一轴仅在Peers及按单位调度依赖中读取','桥的 Peers 限于本轴；当前整单位缓存失效只作保守工程依赖'),
    ('桥跨轴因按单位调度保留，不能仅凭双格独立放行','桥跨轴调度独立；当前整单位分块仍保守保留冲突，未据此扩大约减域'),
    ('桥跨轴调度依赖','桥按轴调度及保守整单位分块')])
lines_replace('规格/选择点参数轴.md',{
    '| D1 |':'| D1 | T14 bridge.scheduling_scope | 每对边独立分级和轮询；据：规则L63 |',
    '| D2 |':'| D2 | T5 connection.bridge_first_contact/bridge_tie | 四边固定双向，兼容轴均不适用；据：规则L63 |',
    '| D3 |':'| D3 | T14 bridge.capacity | 每对边上限1由规则L59直接给出；据：运输单位、桥接器 |',
})
edit('规格/选择点参数轴.md', [('桥接器 `capacity_status=unresolved` 落 T14','桥接器 `capacity_status=known`、每轴容量1 落 T14')])
for file in ['规格/规则覆盖表.md','数据/规则覆盖表.md']:
    p=ROOT/file;ls=p.read_text().splitlines();source=(REPO/SOURCES[0]).read_text().splitlines()
    for i,l in enumerate(ls):
        for n in [24,59,63]:
            if l.startswith(f'| {n} |'):
                parts=l.split('|');parts[2]=' '+source[n-1].strip()+' ';ls[i]='|'.join(parts)
    t='\n'.join(ls)+'\n'
    t=t.replace('桥接器两轴共同分级','桥接器每对边独立分级').replace('独立库存与定向；按单位调度；容量例外及记账依据待审','双向端口；每对边独立库存、分级与轮询；每格上限1；保存来路禁止立即返回')
    t=t.replace('容量计数不裁定桥接器调度独立','桥调度独立由规则L63给出').replace('第2节逐轴 pending/resolved/unresolved；第3节先接读法和快照变化','第2节四边固定双向；第3节相邻桥双向PC和接通史').replace('未接一轴保留 pending；先接分歧报超出支持','空邻接桥也成通道；来路守卫禁止物品立即退回')
    write(p,t)
for filename in ['运行语义.md','受限模型声明.md']:
    p=ROOT/'规格'/filename;t=p.read_text()
    t=t.replace('52df4c12ce90975b861a6a663bd37873e03c9549658d200dc7e95fabc4bc29f3',digest(REPO/SOURCES[0])).replace('52df4c12ce90',digest(REPO/SOURCES[0])[:12]).replace('a67c18dec5f6',digest(REPO/SOURCES[2])[:12])
    write(p,t)
# Schema accepts persisted incoming-unit metadata; summaries remain their existing projection.
p=ROOT/'规格/内核输出.schema.json';s=json.loads(p.read_text())
def schema_walk(v):
    if isinstance(v,dict):
        props=v.get('properties',{})
        if {'item','quantity','entered_at'} <= props.keys() and props['entered_at'].get('$ref'):
            props['last_unit']={'type':['string','null'],'description':'桥物品刚离开的单位；初态尚未移动时可省略'}
        for x in list(v.values()):schema_walk(x)
    elif isinstance(v,list):
        for x in v:schema_walk(x)
schema_walk(s);write(p,dump(s))
guard('edit-specs-after')
