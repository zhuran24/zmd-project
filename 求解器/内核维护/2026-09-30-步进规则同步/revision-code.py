"""本轮定向源码修订；开工原字节见 revision-before，不可重复执行。"""
from guard import ROOT, guard

guard('revision-code-before')
p=ROOT/'crates/kernel/src/output.rs'
s=p.read_text();a=s.index('/// 66 轴的本次证据');b=s.index('\npub fn step_row',a)
s=s[:a]+'''/// 每条轴单独取证；缺少可区分该轴的运行证据时不声称 exercised。
pub fn coverage(config: &Config, steps: &[Value], input: &Input) -> Vec<Value> {
    use crate::graph::{ComponentKind, Subject};
    let graph = &input.graph;
    let mut evidence = BTreeMap::<String, BTreeSet<String>>::new();
    // 从真实种子开始，逐移动更新，不能用步末游标反推首次成功。
    let mut cursors: BTreeMap<String, Option<String>> = input.raw["initial_state"]
        ["nonwarehouse"]["value"]["logistics"]["poll_state"]["cursors"]
        .as_array().into_iter().flatten()
        .map(|r| (r["side"].as_str().unwrap().into(),
                  r["last_success"].as_str().map(str::to_string)))
        .collect();
    for step in steps {
        for event in step["events"].as_array().into_iter().flatten() {
            let id = event["event"].as_str().unwrap_or("").to_string();
            let mut add = |axis: &str| {
                evidence.entry(axis.into()).or_default().insert(id.clone());
            };
            if event["phase"] == "start" {
                add("manufacturing.recipe_completeness");
            }
            if let Some(transfer) = event["detail"].get("transfer") {
                add("transfer.judgment");
                if transfer["cooldown_restarted"] == true {
                    add("transfer.failure_cooldown");
                }
                if transfer["sent"].as_array().is_some_and(|a| !a.is_empty())
                    && transfer["retained"].as_array().is_some_and(|a| !a.is_empty())
                {
                    add("transfer.partial_acceptance");
                }
            }
            for mv in event["moves"].as_array().into_iter().flatten() {
                if event["phase"] == "judge" {
                    add("time.domain");
                    add("step.order");
                }
                if let Some(ch) = input.geometry.channels.get(mv["channel"].as_str().unwrap_or("")) {
                    for (subject, side) in [(&graph.sender[&ch.id], "output"),
                                            (&graph.receiver[&ch.id], "input")] {
                        if matches!(subject, Subject::Component(i) if
                            graph.components[*i].kind == ComponentKind::BeltChain
                            && graph.components[*i].cells.len() > 1)
                        {
                            add("component.belt_segment");
                        }
                        // 非运输送货侧使用成功时间序，不使用循环初始游标。
                        if side == "output" && matches!(subject, Subject::Unit(_)) {
                            continue;
                        }
                        let channels = if side == "input" {graph.inputs(subject)} else {graph.outputs(subject)};
                        let special = matches!(subject, Subject::Component(i) if
                            (graph.components[*i].kind == ComponentKind::Splitter && side == "output")
                            || (graph.components[*i].kind == ComponentKind::Merger && side == "input"));
                        if special && channels.len() == 1 {
                            add("polling.split_merge_singleton");
                        }
                        if channels.len() > 1 {
                            let key = format!("{}:{side}", graph.label(subject));
                            if let Some(last) = cursors.get_mut(&key) {
                                if last.is_none() {
                                    add(if special {"polling.split_merge_start"} else {"polling.initial_cursor"});
                                }
                                *last = Some(ch.id.clone());
                            }
                        }
                    }
                }
            }
        }
        for flow in ["external_supply", "core_inbound", "wireless_inbound"] {
            for row in step["warehouse_ledger"][flow].as_array().into_iter().flatten() {
                let id = row["event"].as_str().map(str::to_string)
                    .unwrap_or_else(|| format!("step:{}:{flow}", step["step"]));
                let axis = if flow == "external_supply" {"warehouse.external_supply"}
                    else {"warehouse.delivery_count"};
                evidence.entry(axis.into()).or_default().insert(id);
            }
        }
    }
    config.axes.iter().map(|(axis,row)| {
        let name=axis.name();
        let ids=evidence.get(name).cloned().unwrap_or_default();
        let (status,ev)=if name=="warehouse.periodic_lift" {("proof_pending",vec!["完整循环复原及全称覆盖待证".to_string()])}
            else if row.disposition==Disposition::Stop {("stop_not_triggered",vec!["有限前缀未触及停止域".into()])}
            else if !ids.is_empty() {("exercised",ids.into_iter().collect())}
            else if row.disposition==Disposition::Input || name.starts_with("initialization.") || name.starts_with("connection.") {("input_checked",vec!["已核当前输入；不证明全称覆盖".into()])}
            else {("not_exercised",vec!["本次无可区分该轴的独立取证判据或触发证据".into()])};
        json!({"axis":name,"reason":row.coverage_loss,"disposition":row.disposition,"coverage_status":status,"evidence":ev,
            "other_values":if row.disposition==Disposition::Fixed{"已定域无其它值"}else{"其它值及其联合组合未覆盖"}})
    }).collect()
}
'''+s[b:];p.write_text(s)
# 独立 Python 图同样拒绝非法并列史与身份冲突，避免静默覆盖。
p=ROOT/'数据/工具/step_graph.py';s=p.read_text()
a="    rank={c:i for i,c in enumerate(sorted(channels,key=lambda c:(times[c],tie[c])))}"
b='''    selected={u:i for i,u in enumerate(raw['construction']['selected_order'])}
    build_rank={m['event']:selected[m['unit']] for m in raw['construction']['moments']}
    cause_rank={c['channel']:build_rank[c['cause']] for c in raw['timeline']['connection_events']}
    previous={}
    for c in sorted(channels,key=tie.get):
        if times[c] in previous and previous[times[c]] > cause_rank[c]:
            raise ValueError('connection.tie 与同一步内的建成次序相反')
        previous[times[c]]=cause_rank[c]
'''+a
assert a in s;s=s.replace(a,b)
a="                nodes[name]={'kind':u['kind']"
b="                if name in nodes:raise ValueError('元件身份重复: '+name)\n"+a
assert a in s;s=s.replace(a,b);p.write_text(s)
# 归因重跑必须保留先前 witness，使用本次标签命名。
p=ROOT/'内核维护/2026-09-30-步进规则同步/差分/diagnose.py';s=p.read_text()
s=s.replace("path=run.HERE/filename", "path=run.HERE/(args.label+'-'+filename)\n            assert not path.exists(),path")
s=s.replace("safe_reference_log=str(run.MAINT/'differential-reference.log')", "safe_reference_log=str(args.reference_log) if args.reference_log else None")
s=s.replace("p.add_argument('--label',required=True)","p.add_argument('--label',required=True)\n    p.add_argument('--reference-log',type=Path)")
p.write_text(s)
guard('revision-code-after')
