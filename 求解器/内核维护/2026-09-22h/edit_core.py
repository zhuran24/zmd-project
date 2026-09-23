from pathlib import Path
from guard import ROOT, OUT, guard

def edit(rel, pairs):
    path = ROOT / rel
    text = path.read_text()
    backup = OUT / 'before' / rel
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(path.read_bytes())
    for old, new in pairs:
        assert old in text, (rel, old[:100])
        text = text.replace(old, new)
    path.write_text(text)

guard('edit-core-before')
edit('数据/工具/formal_units.py', [
    ("'桥接器': [[edge(a, 'input', [0], 'vertical'), edge(b, 'output', [0], 'vertical'),\n                    edge(c, 'input', [0], 'horizontal'), edge(d, 'output', [0], 'horizontal')]\n                   for a, b in [('south', 'north'), ('north', 'south')]\n                   for c, d in [('west', 'east'), ('east', 'west')]],", "'桥接器': [[edge(side, 'bidirectional', [0], axis)\n                    for axis, sides in [('vertical', ['south', 'north']), ('horizontal', ['west', 'east'])]\n                    for side in sides]],"),
    ("('桥接器', (2, 2))", "('桥接器', (4, 4))"),
    ("slot(axis, 1, None, capacity_status='unresolved', item_policy='single_item')", "slot(axis, 1, capacity, capacity_status='known', item_policy='single_item')"),
    ("'port_assignment': 'first_connected_peer'", "'port_assignment': 'permanent_bidirectional'"),
    ("容量例外的辖域未定；端口类型由先接端决定；轮询及分级按单位。", "每对边上限1；四边一直双向；分级与轮询按每对边独立；物品不移回刚离开的单位。")])

p=ROOT/'crates/kernel/src/catalog.rs'
t=p.read_text(); start=t.index('                let mut e = BTreeMap::new();',t.index('let edges:')); end=t.index('\n            } else {',start)
edit('crates/kernel/src/catalog.rs',[(t[start:end],'''                if !row["bridge_axes"].is_null() {
                    return Err(Stop::invalid(&uid, "桥四边固定双向，bridge_axes 必须为 null"));
                }
                decode(k.layouts[0].clone(), &uid)?'''),
    ('if p.role != "output" {','if !["output", "bidirectional"].contains(&p.role.as_str()) {'),
    ('if q.role == "input"','if ["input", "bidirectional"].contains(&q.role.as_str())'),
    ('/// 内核输入§2.3：目录声明每个单位所有格，桥容量由显式轴补齐。','/// 内核输入§2.3：目录声明每个单位所有格；桥每轴上限 1。'),
    ('        let mut result = BTreeMap::new();\n        for (uid, u) in units {','        if bridge_capacity != 1 {\n            return Err(Stop::invalid("bridge.capacity", "正式规则规定每对边上限1"));\n        }\n        let mut result = BTreeMap::new();\n        for (uid, u) in units {')])
p=ROOT/'crates/kernel/src/input.rs';t=p.read_text();a=t.index('        // 内核输入§3.2：桥先接');b=t.index('        fields(\n            &raw["settings"]',a)
edit('crates/kernel/src/input.rs',[(t[a:b], '        // 桥端口恒为双向，接通史只决定通道时刻和轮询次序。\n'),
    ('&& (unit.kind != "桥接器" || source.axis == target.axis)', '&& (unit.kind != "桥接器"\n                                || (source.axis == target.axis && c.source_port != self.geometry.channels[&cid].target_port))')])
edit('crates/kernel/src/model.rs',[
    ('    pub entered_at: Option<Time>,','    pub entered_at: Option<Time>,\n    /// 桥格物品的直接来路；空值表示初态尚未移动。\n    #[serde(default, skip_serializing_if = "Option::is_none")]\n    pub last_unit: Option<String>,'),
    ('    pub side: String,','    pub side: String,\n    /// 桥按本地轴分开调度，其余单位为空。\n    #[serde(default, skip_serializing_if = "Option::is_none")]\n    pub axis: Option<String>,')])
edit('crates/kernel/src/catalog.rs',[
    ('impl Geometry {','''impl Geometry {
    pub(crate) fn scheduling_sides(&self, cat: &Catalog) -> BTreeSet<(String, String, Option<String>)> {
        self.units.iter()
            .filter(|(_, u)| cat.kinds[&u.kind].family != "power")
            .flat_map(|(uid, u)| {
                let axes = if u.kind == "桥接器" {
                    vec![Some("vertical".to_string()), Some("horizontal".to_string())]
                } else { vec![None] };
                axes.into_iter().flat_map(move |axis| {
                    ["input", "output"].map(|side| (uid.clone(), side.into(), axis.clone()))
                })
            }).collect()
    }
''')])
for rel in ['engine.rs','polling.rs']:
    edit('crates/kernel/src/'+rel,[
        ('((s.unit.clone(), s.side.clone()), i)', '((s.unit.clone(), s.side.clone(), s.axis.clone()), i)')])
edit('crates/kernel/src/engine.rs',[
    ('BTreeMap<(String, String), usize>', 'BTreeMap<(String, String, Option<String>), usize>'),
    ('                        entered_at: None,','                        entered_at: None,\n                        last_unit: None,'),
    ('                entered_at: Some(Time::at(self.t)),','                entered_at: Some(Time::at(self.t)),\n                last_unit: None,'),
    ('        if let Some(i) = self.gate_index.get(target_unit) {','        if content.last_unit.as_ref() == Some(target_unit) {\n            return Ok((None, "immediate_return"));\n        }\n        if let Some(i) = self.gate_index.get(target_unit) {')])
p=ROOT/'crates/kernel/src/engine.rs';t=p.read_text();a=t.index('        let expected_sides: BTreeSet<_> =');b=t.index('        if expected_sides',a)
edit('crates/kernel/src/engine.rs',[(t[a:b],'        let expected_sides = self.input.geometry.scheduling_sides(&self.input.catalog);\n')])
p=ROOT/'crates/kernel/src/seed.rs';t=p.read_text();a=t.index('        let expected: BTreeSet<_> =');b=t.index('        if self\n            .memory',a)
edit('crates/kernel/src/seed.rs',[(t[a:b],'        let expected = self.input.geometry.scheduling_sides(&self.input.catalog);\n'),
    ('(s.unit.clone(), s.side.clone())','(s.unit.clone(), s.side.clone(), s.axis.clone())'),
    ('.map(|(unit, side)| Side {\n                    unit,\n                    side,','.map(|(unit, side, axis)| Side {\n                    unit,\n                    side,\n                    axis,')])
edit('crates/kernel/src/polling.rs',[
    ('if self.input.geometry.ports[end].unit != *uid {','if self.input.geometry.ports[end].unit != *uid\n                    || self.input.geometry.ports[end].axis != prior.axis {'),
    ('.entry(format!("L|{uid}|{side}|{category}"))','.entry(if let Some(axis) = &prior.axis {\n                        format!("L|{uid}|{axis}|{side}|{category}")\n                    } else { format!("L|{uid}|{side}|{category}") })'),
    ('                side: side.clone(),','                side: side.clone(),\n                axis: prior.axis.clone(),'),
    ('p.unit == target.unit && (unit.kind != "桥接器" || p.axis == target.axis)', 'p.unit == target.unit && (unit.kind != "桥接器"\n                        || (p.axis == target.axis && self.input.geometry.channels[*id].source_port != c.target_port))'),
    ('"{}:{}",\n                        self.memory.sides[*i].unit, self.memory.sides[*i].side','"{}:{}:{:?}",\n                        self.memory.sides[*i].unit, self.memory.sides[*i].side, self.memory.sides[*i].axis'),
    ('format!("{}:{}", s.unit, s.side)', 'format!("{}:{}:{:?}", s.unit, s.side, s.axis)')])
edit('crates/kernel/src/cache.rs',[
    ('&(self.input.geometry.ports[port].unit.clone(), side.into())','&(self.input.geometry.ports[port].unit.clone(), side.into(), self.input.geometry.ports[port].axis.clone())')])
edit('crates/kernel/src/transition.rs',[
    ('&(source_unit, "output".into())','&(source_unit.clone(), "output".into(), self.input.geometry.ports[&c.source_port].axis.clone())'),
    ('&(target_unit.clone(), "input".into())','&(target_unit.clone(), "input".into(), self.input.geometry.ports[&c.target_port].axis.clone())'),
    ('                self.put(&route.target, &route.item, 1)?;','                self.put(&route.target, &route.item, 1)?;\n                if self.input.geometry.units[&target_unit].kind == "桥接器" {\n                    self.state.inventory[self.inv[&route.target]].contents[0].last_unit = Some(source_unit.clone());\n                }'),
    ('.get(&(uid.into(), "output".into()))','.get(&(uid.into(), "output".into(), None))')])
edit('crates/kernel/src/tests.rs',[
    ('&("splitter".into(), "output".into())','&("splitter".into(), "output".into(), None)'),
    ('&("source".into(), "output".into())','&("source".into(), "output".into(), None)'),
    ('assert_eq!(stops.len(), 18);','assert_eq!(stops.len(), 17);')])
guard('edit-core-after')
