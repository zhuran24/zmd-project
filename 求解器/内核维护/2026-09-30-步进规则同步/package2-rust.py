from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
ST=OUT/'package2-stage'
def put(name,text):
 p=ST/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
def source(name):return (ROOT/name).read_text()
# Keep canonical delta/path/reference helpers; replace all old temporal and evidence semantics.
p='crates/kernel/src/output.rs';s=source(p)
head=s[:s.index('/// 内核输出§1：参数投影')].replace('full_state_each_instant','full_state_each_step').replace('"ticks"','"steps"').replace('trace.ticks','trace.steps').replace('ticks[{i}]','steps[{i}]')
finger=s[s.index('pub fn fingerprints('):s.index('/// 输出§5.1：单个输入')]
finger=finger.replace('        "event_identity.rs",\n','').replace('        "transition.rs",','        "step.rs",\n        "graph.rs",').replace('        "cache.rs",\n','')
tail=s[s.index('/// 内核输出§1：只规范属于记录'):] .replace('"ticks"','"steps"').replace('trace.ticks','trace.steps').replace('    engine.set_cache_enabled(true);\n','').replace('let mut engine = if','let engine = if')
put(p,head+finger+r'''
/// 单一输入和固定参数的有限执行，不提交全称或完整循环证明。
pub(crate) fn evidence_scope(kind: &str, direction: &str, sources: &[Value]) -> Value {
    json!({"kind":kind,"support_domain":["固定布局、设定、step-order-v1 与整数步的有限执行"],
        "fixed_parameter_lifecycle":"本段无离线或玩家动作，先后与参数固定",
        "context_bindings":sources.iter().map(|r|json!({"path":r["path"],"sha256":r["sha256"]})).collect::<Vec<_>>(),
        "initial_state_coverage":{"description":"一个显式条件种子及已重放前缀","exact_reachable_set_enumerated":false},
        "direction":direction,"review_status":"author_checked","proof_sources":[]})
}
/// 66 轴的本次证据；只以实际事件和流量宣称 exercised。
pub fn coverage(config: &Config, steps: &[Value], input: &Input) -> Vec<Value> {
    let mut evidence = BTreeMap::<String, BTreeSet<String>>::new();
    for step in steps {
        for event in step["events"].as_array().into_iter().flatten() {
            let id = event["event"].as_str().unwrap_or("").to_string();
            let mut add = |family: &str| { evidence.entry(family.into()).or_default().insert(id.clone()); };
            if ["start","complete","flush"].iter().any(|p|event["phase"]==*p) { add("manufacturing."); }
            if event["detail"].get("transfer").is_some() { add("transfer."); }
            for mv in event["moves"].as_array().into_iter().flatten() {
                if event["phase"]=="judge" {
                    for name in ["time.domain","component.belt_segment","step.order"] { add(name); }
                }
                if let Some(ch) = input.geometry.channels.get(mv["channel"].as_str().unwrap_or("")) {
                    for port in [&ch.source_port,&ch.target_port] {
                        let u=&input.geometry.ports[port].unit;
                        match input.geometry.units[u].kind.as_str() {
                            "桥接器"=>add("bridge."),
                            "物品准入口" if port==&ch.target_port =>add("gate."),
                            _=>()
                        }
                    }
                    let graph=&input.graph;
                    for (subject, side) in [(&graph.sender[&ch.id],"output"),(&graph.receiver[&ch.id],"input")] {
                        let channels=if side=="input"{graph.inputs(subject)}else{graph.outputs(subject)};
                        if channels.len()>1 {
                            add("polling.");
                            if matches!(subject,crate::graph::Subject::Component(i) if
                                (graph.components[*i].kind==crate::graph::ComponentKind::Splitter && side=="output") ||
                                (graph.components[*i].kind==crate::graph::ComponentKind::Merger && side=="input")) { add("polling.split_merge"); }
                        }
                    }
                }
            }
        }
        for flow in crate::ledger::FLOWS {
            if !step["warehouse_ledger"][flow].as_array().is_none_or(Vec::is_empty) {
                for row in step["warehouse_ledger"][flow].as_array().unwrap() {
                    let id=row["event"].as_str().map(str::to_string).unwrap_or_else(||format!("step:{}:{flow}",step["step"]));
                    evidence.entry("warehouse.".into()).or_default().insert(id.clone());
                    evidence.entry(format!("warehouse.flow.{flow}")).or_default().insert(id);
                }
            }
        }
    }
    config.axes.iter().map(|(axis,row)| {
        let name=axis.name();
        let key=if name.starts_with("polling.split_merge") {"polling.split_merge"}
            else if name=="warehouse.external_supply" {"warehouse.flow.external_supply"}
            else { ["polling.","transfer.","manufacturing.","bridge.","gate.","warehouse."].into_iter().find(|s|name.starts_with(s)).unwrap_or(name) };
        let ids=evidence.get(key).cloned().unwrap_or_default();
        let (status,ev)=if name=="warehouse.periodic_lift" {("proof_pending",vec!["完整循环复原及全称覆盖待证".to_string()])}
            else if row.disposition==Disposition::Stop {("stop_not_triggered",vec!["有限前缀未触及停止域".into()])}
            else if !ids.is_empty() {("exercised",ids.into_iter().collect())}
            else if row.disposition==Disposition::Input || name.starts_with("initialization.") || name.starts_with("connection.") {("input_checked",vec!["已核当前输入；不证明全称覆盖".into()])}
            else {("not_exercised",vec!["本次未记录该机制实际后效".into()])};
        json!({"axis":name,"reason":row.coverage_loss,"disposition":row.disposition,"coverage_status":status,"evidence":ev,
            "other_values":if row.disposition==Disposition::Fixed{"已定域无其它值"}else{"其它值及其联合组合未覆盖"}})
    }).collect()
}
pub fn step_row(engine: &Engine, report: &crate::model::StepReport) -> Value {
    json!({"step":report.step,"events":report.events,"state":engine.state,"warehouse_ledger":report.ledger})
}
/// 每一行对应一步；停止时只保留成功完成的边界状态。
pub fn run_record(mut engine: Engine, config: &Config, config_path: &Path,
    steps: usize, format: &str, interval: usize) -> Result<Value> {
    if !["full_state_each_step","checkpoint_delta"].contains(&format) || interval==0 {
        return Err(Stop::invalid("trace.format","未知格式或检查点间隔为零"));
    }
    let start=json!(engine.state); let from=engine.time();
    let mut rows=Vec::new(); let mut stop=None;
    for _ in 0..steps {
        match engine.step() {
            Ok(report)=>rows.push(step_row(&engine,&report)),
            Err(e)=>{stop=Some(e);break;}
        }
    }
    let uncovered=coverage(config,&rows,&engine.input);
    let completed=rows.iter().flat_map(|r|r["events"].as_array().unwrap()).filter(|e|e["phase"]=="complete").count();
    let end=from.checked_add(rows.len() as i64).ok_or_else(||Stop::invalid("end_step","整数越界"))?;
    let mut previous=start.clone();
    if format=="checkpoint_delta" {
        for (i,row) in rows.iter_mut().enumerate() {
            let current=row["state"].clone();
            if i%interval!=0 {row.as_object_mut().unwrap().remove("state");row["delta"]=json!(delta(&previous,&current)?);}
            previous=current;
        }
    }
    let mut trace=json!({"start_state":start,"steps":rows,"end_step":end,"format":format});
    if format=="checkpoint_delta" {trace["checkpoint_interval"]=json!(interval);trace["delta_encoding"]=json!("object_replace_v1");}
    let sources=fingerprints(&engine.input,config_path,&[])?;
    let status=stop.as_ref().map(|s|s.status.as_str()).unwrap_or("completed");
    let open=stop.iter().map(ToString::to_string).collect::<Vec<_>>();
    Ok(json!({"schema":"kernel-output-v5","evidence_scope":evidence_scope("finite_trace","diagnostic",&sources),
        "execution_mode":if engine.production_abstraction{"production_abstraction"}else{"finite_concrete"},
        "port_meeting":engine.input.parameters.value(Axis::ConnectionPortMeeting)?,
        "run_id":format!("kernel:{}:{from}:{steps}",engine.input.path.file_stem().and_then(|s|s.to_str()).unwrap_or("input")),
        "profile_id":config.profile_id,"producer":{"kind":"kernel","path":concat!(env!("CARGO_MANIFEST_DIR"),"/src/lib.rs"),"claim":"整数步有限条件轨迹；不作全称或完整目标认证"},
        "status":status,"fingerprints":sources,"parameter_assignment":engine.input.raw["parameters"],
        "input_history":{"timeline":engine.input.raw["timeline"],"construction":engine.input.raw["construction"],"debug_operations":engine.input.raw["debug_operations"],"environment":engine.input.raw["environment"],"reachability":engine.input.raw["initial_state"]["reachability"]},
        "uncovered_axes":uncovered,"trace":trace,
        "validation_scope":{"kind":"finite_trace","from":tv(from),"through":tv(end),"initial_history":"conditional_witness","universal_parameters":false,"all_reachable_cycles":false,"target_certified":false,"manufacturing_cycles_completed":q(completed as i64)},"open_items":open}))
}
pub fn stopped_record(stop: &Stop) -> Value {
    json!({"schema":"kernel-output-v5","evidence_scope":evidence_scope("diagnostic","diagnostic",&[]),"execution_mode":"finite_concrete","port_meeting":"shared_edge_opposite","run_id":"kernel:load-stop","profile_id":"kernel_profile_v2","producer":{"kind":"kernel","path":concat!(env!("CARGO_MANIFEST_DIR"),"/src/lib.rs"),"claim":"装载停止，未形成后继"},"status":stop.status,"fingerprints":[],"parameter_assignment":null,"input_history":null,"uncovered_axes":[],"trace":null,"validation_scope":null,"open_items":[stop.to_string()]})
}
/// 连续步、事件身份及台账引用，与重放比较独立。
pub(crate) fn verify_step_events(previous: &Value, row: &Value) -> Result<()> {
    let step=row["step"].as_i64().ok_or_else(||Stop::invalid("step","须为整数"))?;
    if step!=instant(&previous["environment"]["time"],"step")? || instant(&row["state"]["environment"]["time"],"state.time")?!=add(step,1,"step")? {
        return Err(Stop::invalid("step","步与前后边界不连续"));
    }
    let events:Vec<crate::model::Event>=decode(row["events"].clone(),"events")?;
    let mut ids=BTreeSet::new();
    for (i,e) in events.iter().enumerate() {
        if e.event!=format!("E|{step}|{i}") || !["supply","complete","flush","judge","start"].contains(&e.phase.as_str()) {
            return Err(Stop::invalid("events","身份不连续或阶段未知"));
        }
        ids.insert(e.event.as_str());
    }
    for flow in crate::ledger::FLOWS {
        for entry in row["warehouse_ledger"][flow].as_array().ok_or_else(||Stop::invalid(flow,"缺台账数组"))? {
            if let Some(id)=entry.get("event") {
                if !id.as_str().is_some_and(|id|ids.contains(id)) {return Err(Stop::invalid(flow,"台账引用未知事件"));}
            } else if flow!="representative_adjustment" {return Err(Stop::invalid(flow,"台账缺事件引用"));}
        }
    }
    crate::ledger::verify_tick(previous,row)
}
pub(crate) fn verify_record_events(record: &Value, _input: &Input) -> Result<()> {
    if record["schema"]!="kernel-output-v5" {return Err(Stop::invalid("schema","仅接受 v5 记录"));}
    let trace=decode_trace(&record["trace"])?;
    let mut previous=trace["start_state"].clone();
    for row in trace["steps"].as_array().ok_or_else(||Stop::invalid("trace.steps","须为数组"))? {
        verify_step_events(&previous,row)?; previous=row["state"].clone();
    }
    if trace["end_step"]!=instant(&previous["environment"]["time"],"end_step")? {return Err(Stop::invalid("trace.end_step","末边界不符"));}
    Ok(())
}
'''+tail)
# seed normalization has no invented polling history.
put('crates/kernel/src/seed.rs',r'''//! 步边界种子规范化；不继承或推测旧语义轮询。
use crate::{model::*, value::*, Config, Engine, Input};
use serde_json::{json, Value};
use std::path::Path;
impl Input {
    pub fn canonicalize_seed(raw: Value, base: &Path, config: &Config) -> Result<Value> {
        let mut input=Self::parse_with_base(raw,base,config)?;
        let mut state:State=decode(input.raw["initial_state"]["nonwarehouse"]["value"].clone(),"StateSeed")?;
        let time=state.environment.time.integer("time")?;
        let sides=input.graph.cursor_sides();
        for side in sides.keys() {
            if !state.logistics.poll_state.cursors.iter().any(|r| &r.side==side) {
                state.logistics.poll_state.cursors.push(Cursor{side:side.clone(),last_success:None});
            }
        }
        for (unit,channels) in &input.graph.outputs_nt {
            if channels.len()>1 && !state.logistics.poll_state.recency.iter().any(|r| &r.unit==unit) {
                state.logistics.poll_state.recency.push(Recency{unit:unit.clone(),order:vec![]});
            }
        }
        state.logistics.poll_state.cursors.sort_by(|a,b|a.side.cmp(&b.side));
        state.logistics.poll_state.recency.sort_by(|a,b|a.unit.cmp(&b.unit));
        for gate in &mut state.logistics.gate_counters {
            if let Some(w)=&gate.window_started_at {
                if add(w.integer(&gate.unit)?,input.catalog.kinds["物品准入口"].window,&gate.unit)?<=time {
                    gate.window_started_at=None;gate.window_received=Quantity::calc(0);
                }
            }
        }
        for row in &mut state.inventory {row.contents.sort_by(|a,b|a.item.cmp(&b.item));}
        input.raw["initial_state"]["nonwarehouse"]["value"]=json!(state);
        let engine=Engine::new(input)?;
        let mut raw=engine.input.raw.clone();
        raw["initial_state"]["nonwarehouse"]["value"]=json!(engine.state);
        raw["catalog"]["path"]=json!(engine.input.catalog.path);
        let registry=engine.input.source_paths.iter().find(|(r,_)|r=="axis_registry").ok_or_else(||Stop::invalid("axis_registry","缺来源"))?;
        raw["parameters"]["axis_registry"]["path"]=json!(registry.1);
        if let Some(doc)=raw["initial_state"]["reachability"]["value"]["document"].as_str() {
            if let Ok(p)=base.join(doc).canonicalize(){raw["initial_state"]["reachability"]["value"]["document"]=json!(p);}
        }
        Ok(raw)
    }
}
''')
lib=source('crates/kernel/src/lib.rs')
lib+='\npub mod output;\npub mod cycle;\nmod cycle_io;\nmod digest;\nmod seed;\n'
put('crates/kernel/src/lib.rs',lib)
