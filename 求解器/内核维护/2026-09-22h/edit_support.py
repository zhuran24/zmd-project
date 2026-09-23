from helpers import *
from guard import guard
guard('edit-support-before')
p=ROOT/'规格/内核配置-v1.json'; c=json.loads(p.read_text())
c['revision']='bridge-bidirectional-2026-09-22'
for name,value,meaning in [
    ('bridge.scheduling_scope','per_axis','每对平行边独立分存取两侧；存货分级、取货不分级；两轴各自轮询'),
    ('bridge.capacity',1,'运输单位的例外只涉及格数；桥两独立格各上限1'),
    ('connection.bridge_first_contact','not_applicable','四边固定双向，不存在先接定型；保留兼容轴名，值固定为不适用'),
    ('connection.bridge_tie','not_applicable','相邻桥按双向端口形成通道，无定向依赖或首次并列停止')]:
    c['axes'][name].update(value=value, meaning=meaning, disposition='已定',lifetime='F',
        coverage_loss='该已定范围无读法损失',extension_gate='输入不匹配即invalid',basis='规则L24、L59、L63；743f18b')
c['axes']['offline.direction_effect']['value']['trigger']='请求离线回放'
c['axes']['offline.direction_effect']['meaning']='桥四边始终双向，接通重排不改变端口角色；离线回放及一般指针接续仍未实现，返回unsupported'
write(p,dump(c))

p=ROOT/'数据/样例/check_examples.py';t=p.read_text();a=t.index('            fields(unit["bridge_axes"]');b=t.index('\n        else:',a)
edit('数据/样例/check_examples.py',[(t[a:b],'''            require(unit["bridge_axes"] is None, "桥四边固定双向，bridge_axes 必须为 null")
            edges = kind["ports"]["layouts"][0]'''),
    ('if port["role"] != "output":','if port["role"] not in {"output", "bidirectional"}:'),
    ('ports[other]["role"] == "input"','ports[other]["role"] in {"input", "bidirectional"}'),
    ("'bridge.scheduling_scope': 'unit'", "'bridge.scheduling_scope': 'per_axis', 'bridge.capacity': 1, 'connection.bridge_first_contact': 'not_applicable', 'connection.bridge_tie': 'not_applicable'")])
t=p.read_text();a=t.index('    bridge_evidence = []');b=t.index('    for field, derived',a)
edit('数据/样例/check_examples.py',[(t[a:b],'''    bridge_evidence = [{'unit': uid, 'status': 'permanent_bidirectional', 'axes': ['vertical', 'horizontal']}
                       for uid, unit in units.items() if unit['kind'] == '桥接器']
'''),
    ('reject("桥接器按轴调度", 0, lambda d: d["parameters"]["fixed"]["bridge.scheduling_scope"].update(value="per_axis")', 'reject("桥接器按整单位调度", 0, lambda d: d["parameters"]["fixed"]["bridge.scheduling_scope"].update(value="unit")')])
t=p.read_text();a=t.index('    reject("未知桥轴');b=t.index('    return tests',a)
edit('数据/样例/check_examples.py',[(t[a:b],'''    reject("旧桥方向声明不可继续生效", 0, lambda d: d["layout"]["units"][2].update(bridge_axes={"horizontal": {"status": "resolved", "input_side": "west"}}), "bridge_axes")
'''),
    ('    bridge["bridge_axes"]["horizontal"] = {"status": "pending", "input_side": None, "basis": ["该轴未有相邻端口"]}', '    bridge["bridge_axes"] = None')])

p=ROOT/'数据/样例/generate_examples.py';t=p.read_text();a=t.index("'bridge_axes': ");b=t.index(", 'occupied_cells'",a)
edit('数据/样例/generate_examples.py',[(t[a:b],"'bridge_axes': None")])
edit('数据/样例/runtime_example.py',[
    ("if 'status' in value and ('value' in value or 'basis' in value):", "if 'status' in value and ('value' in value or 'basis' in value) and '.bridge_axes.' not in name:"),
    ('''else f"{uid}:{'transport' if family=='transport' else 'output'}:0"''', '''else f"{uid}:{ports[source]['axis'] if kind=='桥接器' else 'transport' if family=='transport' else 'output'}:0"'''),
    ("            row=rows[0];item=row['item']", "            row=rows[0];item=row['item']\n            if row.get('last_unit') == ports[target]['unit']:return False"),
    ("if family=='transport':slots=[f'{uid}:transport:0'];capacity=1", '''if family=='transport':slots=[f"{uid}:{ports[target]['axis'] or 'transport'}:0"];capacity=1''')])

p=ROOT/'数据/样例/polling_reference.py';t=p.read_text();a=t.index('        for side,key,peer');b=t.index("    return {'schema'",a)
block=t[a:b]
block=block.replace('        for side,key,peer', '        for side,key,peer')
block='        for axis in (["vertical", "horizontal"] if unit["kind"]=="桥接器" else [None]):\n'+''.join('    '+line+'\n' for line in block.splitlines())
block=block.replace("if ports[c[key]]['unit']!=uid:continue", "if ports[c[key]]['unit']!=uid or ports[c[key]]['axis']!=axis:continue")
block=block.replace("'L|'+uid+'|'+side", "'L|'+uid+('|' + axis if axis else '')+'|'+side")
block=block.replace('old.get((uid,side)', 'old.get((uid,side,axis)')
block=block.replace("result.append({'unit':uid", "result.append({**({'axis':axis} if axis else {}),'unit':uid")
edit('数据/样例/polling_reference.py',[(t[a:b],block),
    ("(s['unit'],s['side']):s", "(s['unit'],s['side'],s.get('axis')):s"),
    ("ties.append(s['unit']+':'+s['side'])", "ties.append(s['unit']+':'+s['side']+(':'+s['axis'] if s.get('axis') else ''))")])
edit('crates/kernel/src/output.rs',[
    ('仅校验输入中已解桥方向及先接历史；运行段不执行建造/先接定向，后续搬运不构成定向事件。','校验四边固定双向及先接轴为不适用；运行移动不构成先接定向事件。')])
edit('crates/kernel/src/engine.rs',[
    ('                items.insert(c.item.as_str());', '''                if let Some(previous) = &c.last_unit {
                    let connected = self.input.geometry.channels.values().any(|channel| {
                        let from = &self.input.geometry.ports[&channel.source_port];
                        let to = &self.input.geometry.ports[&channel.target_port];
                        from.unit == *previous && to.unit == uid && to.axis.as_deref() == Some(role)
                    });
                    if unit.kind != "桥接器" || !connected {
                        return Err(Stop::invalid(&row.slot, "桥物品来路不是本轴相邻单位"));
                    }
                }
                items.insert(c.item.as_str());''')])
guard('edit-support-after')
