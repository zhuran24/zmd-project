import re,json
from work import *
def original(relative):
    p=OUT/"before"/relative
    return (p if p.exists() else ROOT/relative).read_text()
guard('core-before')
removed='time.instant_order time.retry_schedule time.instant_end time.boundary time.manufacture_events judgment.order_scope judgment.buffer_event_class judgment.order polling.split_merge_scope polling.ungraded_blocked polling.dual_permission polling.both_failure polling.memory_scope polling.resume polling.eligibility_stage polling.membership_change polling.internal_scope polling.level_tie damping.belt_component_rule damping.belt_adjacency damping.branch damping.no_terminal connection.bridge_first_contact connection.bridge_tie transfer.resume_event manufacturing.recipe_lock_time manufacturing.input_collection manufacturing.buffer_power_gate gate.window_recovery gate.identity_subject gate.identity_recovery gate.total_recovery gate.reconnect_record gate.concurrent_expiry residence.nontransport cascade.buffer'.split()
c=json.loads(original('规格/内核配置-v1.json')); c.update(schema='kernel-profile-registry-v2',profile_id='kernel_profile_v2',revision='step-2026-09-30',axis_count=66)
for a in removed: del c['axes'][a]
updates={'time.domain':('integer_steps','已定','F','时间取整数步，1 步 = 1/8 tick'), 'polling.split_merge_start':('second_connected_first_time','已定','F','分流器送货侧、汇流器收货侧从未成功时从第二条接通的通道开始'), 'transfer.phase':({'interface':'progress.cooldown'},'由输入全称量化','U','每箱剩余冷却 0…40 步'), 'component.belt_segment':('channel_chain','已定','F','沿带间通道首尾相接的最长一串'), 'step.order':({'interface':'step-order-v1'},'由输入全称量化','O','层数选支、环上层数、非运输单位全序'), 'transfer.timing':({'interface':'transfer-timing-v1'},'由输入全称量化','U','每箱传输在送货前或后')}
for a,(v,d,l,m) in updates.items():
    c['axes'][a]={'value':v,'disposition':d,'lifetime':l,'meaning':m,'coverage_loss':'固定一种输入不代表全称成立' if d=='由输入全称量化' else '仅覆盖本条给出的语义','extension_gate':'超出当前接口须另行实现与审查','choice':'条文读法' if d=='已定' else '显式输入','basis':''}
bases={'polling':'游戏规则L30—L33','connection':'游戏规则L9—L12、L16、L30；求解任务L14','initialization':'游戏规则L9—L11、L18、L20、L22、L25；求解任务L7—L13','transfer':'游戏规则L20、L26、L37、L73','manufacturing':'游戏规则L13、L17—L18、L20、L25、L36、L78—L115','gate':'游戏规则L22、L65','warehouse':'游戏规则L13、L14、L37、L42、L74；求解任务L2、L7—L10','bridge':'游戏规则L24、L29、L60、L64','power':'游戏规则L19—L21、L75','time':'游戏规则L25','component':'游戏规则L29','step':'游戏规则L27—L31；求解任务L14','offline':'游戏规则L20、L23—L33、L36—L37、L64—L65；求解任务L14'}
for a,r in c['axes'].items():
    r['basis']=bases[a.split('.')[0]]
    if a=='polling.direct_peer': r['meaning']='取货优先级按物理直连的对端元件分类'
    if a=='gate.window_clock': r['meaning']='首件起 40 步，走完由下一件重新起算'
    if a=='polling.initial_cursor': r['meaning']='其余循环侧从未成功时从第一条接通的通道开始'
    if a=='bridge.scheduling_scope': r['meaning']='每对平行边一个元件、各自轮询、按轴分收货方'
assert len(c['axes'])==66
from collections import Counter
save('config-counts.json',dict(Counter(r['disposition'] for r in c['axes'].values())))
write('规格/内核配置-v2.json',json_text(c))
s=original('crates/kernel/src/config.rs')
variants=dict(re.findall(r'#\[serde\(rename = "([^"]+)"\)\]\n    (\w+),',s[:s.index('impl Axis')]))
variants.update({'component.belt_segment':'ComponentBeltSegment','step.order':'StepOrder','transfer.timing':'TransferTiming'})
head='//! 66 个步进参数轴；取值来自编译时锁定配置。\nuse crate::value::*;\nuse serde::{Deserialize, Serialize};\nuse serde_json::Value;\nuse std::collections::BTreeMap;\n#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]\npub enum Axis {\n'
head+=''.join(f'    #[serde(rename = "{a}")]\n    {variants[a]},\n' for a in c['axes'])+'}\nimpl Axis {\n    pub fn name(self) -> &\'static str { match self {\n'
head+=''.join(f'        Self::{variants[a]} => "{a}",\n' for a in c['axes'])+'    }}\n}\n'
tail=s[s.index('#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]\npub enum Disposition'):]
tail=tail.replace('内核配置-v1.json','内核配置-v2.json').replace('p: &Parameters, structural: bool','p: &Parameters').replace('if !structural &&','if').replace('                if structural && d.status == "unresolved" {\n                    continue;\n                }\n','')
# 当前参数副本已不属于状态。
tail=tail[:tail.index('    /// 内核输入§6：核对种子的当前参数值及生命周期。')]+'}\n'
write('crates/kernel/src/config.rs',head+tail)
s=original('crates/kernel/src/value.rs').replace('self.kind != "rational"','self.kind != "step"').replace('"时刻未解释"','"只接受整数步"').replace('kind: "rational".into()','kind: "step".into()')
write('crates/kernel/src/value.rs',s)
s=original('crates/kernel/src/catalog.rs').replace('static-catalog-v2','static-catalog-v3').replace('    pub port_rate: i64,','    pub port_rate: i64,\n    pub steps_per_tick: i64,\n    pub residence_steps: i64,')
s=s.replace('        let mut kinds = BTreeMap::new();','        let steps_per_tick = num(&raw["timing"]["steps_per_tick"], "timing.steps_per_tick")?;\n        let residence_steps = num(&raw["timing"]["residence_ticks"], "timing.residence_ticks")? * steps_per_tick;\n        let mut kinds = BTreeMap::new();')
s=s.replace('num(&row["settings"]["window_ticks"], &id)?','num(&row["settings"]["window_ticks"], &id)? * steps_per_tick').replace('num(&row["transfer"]["cooldown_ticks"], &id)?','num(&row["transfer"]["cooldown_ticks"], &id)? * steps_per_tick').replace('duration: num(&r["duration"], &id)?,','duration: num(&r["duration"], &id)? * steps_per_tick,').replace('            port_rate,','            port_rate,\n            steps_per_tick,\n            residence_steps,')
a=s.index('    pub(crate) fn scheduling_sides(');b=s.index('    /// 内核输入§2.1–§2.3',a);s=s[:a]+s[b:]
write('crates/kernel/src/catalog.rs',s)
s=original('crates/kernel/src/input.rs').replace('model::*, ','').replace('    pub templates: Vec<Template>,','    pub graph: crate::graph::StepGraph,\n    pub transfer_timing: BTreeMap<String, String>,').replace('    pub branches: BTreeMap<(String, Vec<String>), String>,\n','')
s=s.replace('fn timeline(data: &Value, structural: bool)','fn timeline(data: &Value)').replace('row["kind"] != "runtime" && ["I|", "J|", "C|", "W|"].iter().any(|p| id.starts_with(p))','id.starts_with("E|")').replace('if !structural && !row["time"].is_null()','if !row["time"].is_null()')
a=s.index('    if !structural {\n        // 转移§2.1');b=s.index('    for r in &relations',a)
s=s[:a]+s[b:]
s=s.replace('== "rational"','== "step"')
s=s.replace(', structural: bool','').replace(',\n        structural: bool','').replace(', structural)',')').replace('config.validate(&parameters, structural)?','config.validate(&parameters)?')
a=s.index('        if !["kernel-input-v2"');b=s.index('        validate_tree',a)
s=s[:a]+'''        if raw["schema"] != "kernel-input-v4" {
            return Err(Stop::invalid("schema", "历史输入版本，见 数据/样例/历史说明.md"));
        }
'''+s[b:]
s=s.replace('            if structural && anchor.is_null() {\n                continue;\n            }\n','').replace('        if !structural {\n            for pair','        {\n            for pair')
a=s.index('            let t = if structural {');b=s.index('            connection_times.insert',a)
s=s[:a]+'''            let t = instant(&e["time"], eid)?;
            if t != instant(&events[&builds[later]]["time"], later)? {
                return Err(Stop::invalid(cid, "接通时刻不等于较晚建成时刻"));
            }
'''+s[b:]
s=s.replace('("total_limit", 5000),','("total_limit", num(&catalog.raw["units"].as_array().unwrap().iter().find(|r| r["id"] == "物品准入口").unwrap()["settings"]["total_limit"]["max"], "total_limit.max")?),').replace('("window_limit", catalog.kinds["物品准入口"].window),','("window_limit", num(&catalog.raw["units"].as_array().unwrap().iter().find(|r| r["id"] == "物品准入口").unwrap()["settings"]["window_limit"]["max"], "window_limit.max")?),')
s=s.replace('            templates: vec![],','            graph: crate::graph::StepGraph::default(),\n            transfer_timing: BTreeMap::new(),').replace('            branches: BTreeMap::new(),\n','')
s=s.replace('        if !structural {\n            result.validate_runtime_interfaces()?;\n            result.check_input_axes()?;\n        }','        result.validate_runtime_interfaces()?;\n        result.check_input_axes()?;\n        result.graph = crate::graph::StepGraph::build(&result)?;')
a=s.index('        let order = self.parameters.value(Axis::JudgmentOrder)?;');b=s.index('        let read_order =',a);s=s[:a]+s[b:]
s=s.replace('        self.validate_branches()?;\n','')
a=s.index('    /// 转移§3.1、输入§5.3');s=s[:a]+'}\n'
s=s.replace('        source_paths.push(("axis_registry".into(), axispath));','''        if std::fs::read(&axispath).map_err(|e| Stop::invalid("axis_registry", e.to_string()))? != include_bytes!("../../../规格/内核配置-v2.json") {
            return Err(Stop::invalid("axis_registry", "配置字节不同于编译时配置"));
        }
        source_paths.push(("axis_registry".into(), axispath));''')
write('crates/kernel/src/input.rs',s)
s=original('crates/kernel/src/interfaces.rs')
a=s.index('            if pr["cooldowns"]');b=s.index('        }\n        if boxes',a)
s=s[:a]+'''            if r["remaining"] != pr["cooldown"] {
                return Err(Stop::invalid(uid, "相位与种子冷却不符"));
            }
'''+s[b:]
s=s.replace('                || (t < start\n                    && seed["semantic_context"]["judgment_context"]["value"]["phase"]\n                        != "after_closure")','                || t < start')
a=s.index('        let context = &self.raw["initial_state"]');b=s.index('        for event in self.raw["timeline"]["events"]',a);s=s[:a]+s[b:]
# Transfer shape is checked separately when constructing Input.
s=s.replace('        self.check_action_references()?;','        self.check_transfer_timing()?;\n        self.check_action_references()?;')
s=s.replace('    fn check_event_owners(&self)', '''    fn check_transfer_timing(&self) -> Result<()> {
        let v = self.parameters.value(Axis::TransferTiming)?;
        fields(v, "schema values", "transfer.timing")?;
        if v["schema"] != "transfer-timing-v1" { return Err(Stop::invalid("transfer.timing", "未知版本")); }
        let mut units = BTreeSet::new();
        for r in v["values"].as_array().ok_or_else(|| Stop::invalid("transfer.timing", "须为数组"))? {
            fields(r, "unit timing", "transfer.timing")?;
            let u = r["unit"].as_str().unwrap_or("");
            if !units.insert(u.to_string()) || !["before_send", "after_send"].contains(&r["timing"].as_str().unwrap_or("")) {
                return Err(Stop::new("invalid_input", "transfer.timing", u, "重复箱或非法先后"));
            }
        }
        if units != self.geometry.units.iter().filter(|(_,u)| u.kind == "协议储存箱").map(|(u,_)|u.clone()).collect() {
            return Err(Stop::new("invalid_input", "transfer.timing", "values", "须恰覆盖每箱"));
        }
        Ok(())
    }
    fn check_event_owners(&self)''')
write('crates/kernel/src/interfaces.rs',s)
guard('core-after')
