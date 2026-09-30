use crate::{tests_support::*,cycle::*,*};
use serde_json::json;
#[test]
fn production_samples_find_verify_and_reject_cycle_ledger_tampering() {
    let c=config();let cfg=root().join("规格/内核配置-v2.json");
    for name in ["生产环带","生产循环环带"] {
        let input=Input::load(&root().join(format!("数据/样例/步进/周期/{name}.json")),&c).unwrap();
        let result=run_cycle(input,&c,&cfg,1200).unwrap();
        assert_eq!(result["schema"],"kernel-cycle-v4");assert_eq!(result["status"],"diagnostic_cycle","{result}");assert_eq!(result["record_mode"],"none");
        assert_eq!(result["cycle"]["start_key"]["schema"],"phase-cycle-key-v2");
        assert_eq!(verify_cycle(&result,&c,&cfg).unwrap()["cycle_replayed"],true);
        let mut bad=result.clone();bad["cycle"]["ledger"][0]["warehouse_ledger"]["totals"][0]["actual_inbound"]=value::q(77);
        assert!(verify_cycle(&bad,&c,&cfg).is_err());
    }
}
#[test]
fn relative_transport_and_window_keys_preserve_remaining_work() {
    let c=config();let path=root().join("数据/样例/步进/机制/累计审计与窗口周期.json");let mut e=Engine::new_production(Input::load(&path,&c).unwrap()).unwrap();
    for _ in 0..9 {e.step().unwrap();}
    let key=e.cycle_key().unwrap();let mut input=e.input.clone();let mut st=json!(e.state);
    let n=e.time()+80;st["environment"]["time"]=value::tv(n);
    for row in st["inventory"].as_array_mut().unwrap() {for content in row["contents"].as_array_mut().unwrap(){if !content["entered_at"].is_null(){let t=value::instant(&content["entered_at"],"test").unwrap();content["entered_at"]=value::tv(t+80);}}}
    for g in st["logistics"]["gate_counters"].as_array_mut().unwrap(){if !g["window_started_at"].is_null(){let t=value::instant(&g["window_started_at"],"test").unwrap();g["window_started_at"]=value::tv(t+80);}}
    input.raw["initial_state"]["nonwarehouse"]["value"]=st.clone();let shifted=Engine::new_production(input.clone()).unwrap();assert_eq!(shifted.cycle_key().unwrap(),key);
    let mut changed=false;
    for row in st["inventory"].as_array_mut().unwrap() {for content in row["contents"].as_array_mut().unwrap(){if !content["entered_at"].is_null(){content["entered_at"]=value::tv(n);changed=true;break;}}if changed{break;}}
    assert!(changed);input.raw["initial_state"]["nonwarehouse"]["value"]=st;
    assert_ne!(Engine::new_production(input).unwrap().cycle_key().unwrap(),key);
}
#[test]
fn collision_buckets_compare_full_keys_and_replay_budget_never_claims_cycle() {
    let c=config();let cfg=root().join("规格/内核配置-v2.json");let i=Input::load(&root().join("数据/样例/步进/周期/生产环带.json"),&c).unwrap();
    let opts=SearchOptions{force_collision:true,..Default::default()};let a=run_cycle_with_options(i.clone(),&c,&cfg,256,&opts).unwrap();let b=run_cycle(i.clone(),&c,&cfg,256).unwrap();assert_eq!(a,b);
    let opts=SearchOptions{force_collision:true,replay_limit:0,..Default::default()};let a=run_cycle_with_options(i,&c,&cfg,256,&opts).unwrap();assert_eq!(a["status"],"inconclusive");assert!(a["cycle"].is_null());
}
