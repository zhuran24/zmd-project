//! 独立 sim2 共同投影和 Python 逐步台账审计；所有子进程仅管道 I/O。
use kernel::{value::*, Config, Engine, Input};
use serde_json::Value;
use std::{
    path::{Path, PathBuf},
    process::Command,
};
fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap()
}
fn cfg() -> (Config, PathBuf) {
    let p = root().join("规格/内核配置-v2.json");
    (Config::parse(read_json(&p).unwrap()).unwrap(), p)
}
fn compare(path: &Path) {
    let (config, _) = cfg();
    let input = Input::load(path, &config).unwrap();
    let count = input.raw["scenario"]["differential"]["steps"]
        .as_u64()
        .unwrap() as usize;
    let process = Command::new("python3")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .arg("-B")
        .arg(root().join("数据/工具/sim2_adapter.py"))
        .arg(path)
        .arg("--steps")
        .arg(count.to_string())
        .output()
        .unwrap();
    assert!(
        process.status.success(),
        "{}: {}",
        path.display(),
        String::from_utf8_lossy(&process.stderr)
    );
    let reference: Vec<Value> = serde_json::from_slice(&process.stdout).unwrap();
    assert_eq!(reference.len(), count);
    let mut engine = Engine::new(input).unwrap();
    let mut moves = Vec::new();
    let mut starts = Vec::new();
    for expected in reference {
        let report = engine.step().unwrap();
        let actual = engine.observe(&report);
        for event in &report.events {
            for mv in &event.moves {
                moves.push((report.step, mv.channel.clone()));
            }
            if event.phase == "start" {
                starts.push((
                    report.step,
                    event.subject.clone(),
                    event.detail.as_ref().unwrap()["recipe"].clone(),
                ));
            }
        }
        for key in [
            "step",
            "moves",
            "transport",
            "stock",
            "machines",
            "boxes",
            "warehouse",
        ] {
            assert_eq!(
                actual[key],
                expected[key],
                "{} first difference: step {} field {key}",
                path.display(),
                report.step
            );
        }
    }
    let name = path.file_stem().unwrap().to_str().unwrap();
    let times = |prefix: &str| {
        moves
            .iter()
            .filter(|(_, c)| c.starts_with(prefix))
            .map(|(t, _)| *t)
            .collect::<Vec<_>>()
    };
    let gaps = |ts: Vec<i64>| ts.windows(2).map(|w| w[1] - w[0]).collect::<Vec<_>>();
    match name {
        "a-纯链" => {
            assert!(starts.len() > 40);
            assert!(starts.windows(2).all(|w| w[1].0 - w[0].0 == 8));
        }
        "b-迟滞" | "断尾" => {
            let n = if name == "b-迟滞" { 2 } else { 1 };
            let gs = gaps(
                times(&format!("PC|s{}:", n - 1))
                    .into_iter()
                    .filter(|t| *t >= 100)
                    .collect(),
            );
            assert!(gs.len() > 20);
            for chunk in gs[gs.len() - n * 10..].chunks(n) {
                assert_eq!(chunk.iter().sum::<i64>(), (8 * n + 1) as i64);
            }
        }
        "c-换主料" => {
            assert!(starts.len() >= 12);
            for w in starts.windows(3) {
                assert_eq!(w[2].0 - w[0].0, 18);
                assert_eq!(w[2].2, w[0].2);
                assert_ne!(w[1].2, w[0].2);
            }
        }
        "d-满箱串联" => assert_eq!(times("PC|b0:")[0], 3),
        "e-汇流" => {
            let gs = gaps(times("PC|m:").into_iter().filter(|t| *t >= 100).collect());
            assert!(gs.len() > 30);
            assert!(gs.iter().all(|g| *g == 8));
            assert!(times("PC|gate:").len() >= 8);
        }
        "分矿" => {
            for u in ["f1", "f2"] {
                let ts = starts
                    .iter()
                    .filter(|(t, id, _)| id == u && *t >= 100)
                    .map(|(t, _, _)| *t)
                    .collect::<Vec<_>>();
                assert!(ts.len() > 12, "{u}: {ts:?}");
                assert!(gaps(ts).iter().all(|g| *g == 16));
            }
            assert!(!times("PC|o1_3:").is_empty());
            assert!(!times("PC|o2_3:").is_empty());
        }
        "侧面优先" => {
            assert!(times("PC|side:").is_empty());
            assert_eq!(times("PC|b:").len(), 50);
        }
        "三上游" => {
            let arrivals = moves
                .iter()
                .filter(|(_, c)| c.split('|').nth(2).is_some_and(|p| p.starts_with("m:")))
                .collect::<Vec<_>>();
            assert_eq!(arrivals.len(), 50);
            assert_eq!(
                arrivals
                    .iter()
                    .map(|(_, c)| c.split('|').nth(1).unwrap())
                    .collect::<std::collections::BTreeSet<_>>()
                    .len(),
                1
            );
        }
        _ => unreachable!(),
    }
    println!("{name}: {count} steps equal; phenomenon assertions passed");
}
macro_rules! differential {
    ($test:ident,$name:literal) => {
        #[test]
        fn $test() {
            compare(&root().join(concat!("数据/样例/步进/差分/", $name, ".json")));
        }
    };
}
differential!(a_pure_chain, "a-纯链");
differential!(b_hysteresis, "b-迟滞");
differential!(c_material_switch, "c-换主料");
differential!(d_full_boxes, "d-满箱串联");
differential!(e_merger, "e-汇流");
differential!(dead_tail, "断尾");
differential!(mining, "分矿");
differential!(side_priority, "侧面优先");
differential!(three_upstreams, "三上游");
#[test]
fn migrated_fixtures_run_declared_steps() {
    let (c, _) = cfg();
    let mut count = 0;
    for entry in std::fs::read_dir(root().join("crates/kernel/tests/fixtures/step")).unwrap() {
        let p = entry.unwrap().path();
        if p.extension().is_some_and(|x| x == "json") {
            let i = Input::load(&p, &c).unwrap_or_else(|e| panic!("{}: {e}", p.display()));
            let steps = i.raw["scenario"]["steps"].as_u64().unwrap_or(64);
            let mut e = Engine::new(i).unwrap();
            for _ in 0..steps {
                e.step().unwrap_or_else(|e| panic!("{}: {e}", p.display()));
            }
            count += 1;
        }
    }
    assert_eq!(count, 5);
}
fn python_audit(payload: &Value) -> std::process::Output {
    use std::{io::Write, process::Stdio};
    let mut child = Command::new("python3")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .arg("-B")
        .arg(root().join("crates/kernel/tests/audit_step.py"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let mut stdin = child.stdin.take().unwrap();
    let bytes = serde_json::to_vec(payload).unwrap();
    let writer = std::thread::spawn(move || {
        stdin.write_all(&bytes).unwrap();
    });
    let output = child.wait_with_output().unwrap();
    writer.join().unwrap();
    output
}
#[test]
fn independent_python_audit_full_delta_and_tamper_rejection() {
    let (c, cp) = cfg();
    for name in [
        "无线空箱",
        "无线部分接收",
        "无线多格全收",
        "同刻双箱争余量",
        "装载与普通制造",
    ] {
        let p = root().join(format!("数据/样例/步进/机制/{name}.json"));
        let input = Input::load(&p, &c).unwrap();
        let record = kernel::output::run_record(
            Engine::new(input.clone()).unwrap(),
            &c,
            &cp,
            input.raw["scenario"]["steps"].as_u64().unwrap().min(48) as usize,
            "checkpoint_delta",
            5,
        )
        .unwrap();
        assert_eq!(record["status"], "completed");
        let payload =
            serde_json::json!({"input":input.raw,"input_base":p.parent().unwrap(),"record":record});
        let audited = python_audit(&payload);
        assert!(
            audited.status.success(),
            "{name}: {}",
            String::from_utf8_lossy(&audited.stderr)
        );
        if name == "无线空箱" {
            let mut bad = payload.clone();
            bad["record"]["trace"]["steps"][0]["events"][0]["detail"]["transfer"]["sent"] =
                serde_json::json!({"高容谷地电池":1});
            assert!(!python_audit(&bad).status.success());
        }
    }
    let p = root().join("数据/样例/步进/差分/a-纯链.json");
    let i = Input::load(&p, &c).unwrap();
    let record = kernel::output::run_record(
        Engine::new(i.clone()).unwrap(),
        &c,
        &cp,
        64,
        "full_state_each_step",
        1,
    )
    .unwrap();
    let a = python_audit(
        &serde_json::json!({"input":i.raw,"input_base":p.parent().unwrap(),"record":record}),
    );
    assert!(a.status.success(), "{}", String::from_utf8_lossy(&a.stderr));
}

#[test]
fn cycle_schema_and_production_representative_python_audit() {
    let (c, cp) = cfg();
    let path = root().join("数据/样例/步进/周期/生产环带.json");
    let i = Input::load(&path, &c).unwrap();
    let cycle = kernel::cycle::run_cycle(i.clone(), &c, &cp, 200).unwrap();
    let r = python_audit(&serde_json::json!({"schema_values":[cycle]}));
    assert!(r.status.success(), "{}", String::from_utf8_lossy(&r.stderr));
    let record = kernel::output::run_record(
        Engine::new_production(i.clone()).unwrap(),
        &c,
        &cp,
        48,
        "full_state_each_step",
        1,
    )
    .unwrap();
    let r = python_audit(
        &serde_json::json!({"input":i.raw,"input_base":path.parent().unwrap(),"record":record}),
    );
    assert!(r.status.success(), "{}", String::from_utf8_lossy(&r.stderr));
}

#[test]
fn generated_inputs_and_migration_boundary_contract() {
    let code = r#"
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'数据/工具'))
from step_samples import generate_all,ROOT
from migrate_input_v4 import migrate
from step_inputs import t
rows=generate_all()
assert len(rows)==29
for path,raw in rows.items():assert json.loads(path.read_text())==raw,str(path)
src=ROOT/'数据/样例/任务7内核/静止成熟与暂停键.json';raw=json.loads(src.read_text());dest=ROOT/'数据/样例/步进/机制'
a=migrate(raw,src.parent,dest)
assert a['initial_state']['nonwarehouse']['value']['environment']['time']==t(0)
raw['initial_state']['nonwarehouse']['value']['semantic_context']['judgment_context']['value']['phase']='after_closure'
b=migrate(raw,src.parent,dest)
assert b['initial_state']['nonwarehouse']['value']['environment']['time']==t(8)
assert b['initial_state']['nonwarehouse']['value']['progress'][1]['remaining']==t(8)
raw['initial_state']['nonwarehouse']['value']['progress'][1]['phase']='intake'
try:migrate(raw,src.parent,dest)
except ValueError as e:assert 'intake' in str(e)
else:raise AssertionError('intake accepted')
print('29 inputs deterministic; before/after boundary and intake rejection checked')
"#;
    let out = Command::new("python3")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .args(["-B", "-c", code])
        .arg(root())
        .output()
        .unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
}

#[test]
fn python_graph_rejects_impossible_ties_and_component_collisions() {
    let code = r#"
import copy,json,sys
from pathlib import Path
root=Path(sys.argv[1]);sys.path.insert(0,str(root/'数据/工具'))
from step_graph import build,axis
from step_inputs import generate,t
from step_samples import u
base=root/'数据/样例/步进/差分'
r=json.loads((base/'a-纯链.json').read_text())
events={e['id']:e for e in r['timeline']['events']}
connections=r['timeline']['connection_events']
times={c['channel']:int(events[c['event']]['time']['value']['value']) for c in connections}
channels=axis(r,'connection.tie')['channels']
channels.sort(key=times.get)
for e in events.values():
    if e['kind'] in ('build','connection_open'):e['time']=t(-1)
build(r,base)
channels.reverse()
try:build(r,base)
except ValueError as e:assert 'connection.tie' in str(e)
else:raise AssertionError('impossible tie accepted')
specs=[u('horizontal','传送带',10,10,180,2),u('z1','传送带',11,10,270,2),u('z2','传送带',11,11,0,2),u('z3','传送带',10,11,90,2),u('cross','桥接器',20,20)]
r=generate({'units':specs},base);build(r,base)
bad=json.loads(json.dumps(r).replace('cross','ring'))
try:build(bad,base)
except ValueError as e:assert '元件身份重复' in str(e)
else:raise AssertionError('duplicate component accepted by graph')
specs[-1]['id']='ring'
try:generate({'units':specs},base)
except ValueError as e:assert '元件身份重复' in str(e)
else:raise AssertionError('duplicate component accepted by generator')
print('Python graph and generator reject both malformed input classes')
"#;
    let out = Command::new("python3")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .args(["-B", "-c", code])
        .arg(root())
        .output()
        .unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
}
