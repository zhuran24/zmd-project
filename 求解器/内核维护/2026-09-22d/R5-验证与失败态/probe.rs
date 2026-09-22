use kernel::{Config, Engine, Input, value::{read_json, Time}, model::{Progress, Cooldown}, output, cycle};
use serde_json::{json, Value};
use std::path::Path;

fn field_types(p: &Progress) {
    let _: &String = &p.unit;
    let _: &String = &p.phase;
    let _: &Option<String> = &p.recipe;
    let _: &Vec<String> = &p.candidate_recipes;
    let _: &Option<String> = &p.locked_recipe;
    let _: &Option<Time> = &p.remaining;
    let _: &Vec<Cooldown> = &p.cooldowns;
}
fn public_state(e: &Engine) -> Value {
    json!({"state":e.state,"memory":e.memory,"ledger":e.ledger,
        "completed_batches":e.completed_batches,"delivery":e.delivery,"supplied":e.supplied})
}
fn call(e: &mut Engine, mode: &str) -> kernel::Result<()> {
    match mode {"compact"=>e.step_compact(),"no_output"=>e.step(false).map(|_|()),_=>e.step(true).map(|_|())}
}
fn main() {
    let args:Vec<_>=std::env::args().collect();
    let root=Path::new(&args[1]); let out=Path::new(&args[2]);
    let config_path=root.join("规格/内核配置-v1.json");
    let config=Config::parse(read_json(&config_path).unwrap()).unwrap();
    let crusher=Input::load(&root.join("数据/样例/混做粉碎机两下游.json"),&config,false).unwrap();
    let ring=Input::load(&root.join("数据/样例/生产循环环带.json"),&config,false).unwrap();
    let mut result=json!({});

    let mut bad=crusher.clone();
    let row=&mut bad.raw["initial_state"]["nonwarehouse"]["value"]["progress"][0];
    row["remaining"]=json!(Time::at(1));
    let p:Progress=serde_json::from_value(row.clone()).unwrap(); field_types(&p);
    let stop=Engine::new(bad).unwrap_err();
    assert!(["invalid_input","unsupported"].contains(&stop.status.as_str()));
    result["progress"]=json!({"compile_time_field_types_checked":true,"idle_with_remaining_deserializes":true,"engine_rejects":stop});

    let mut failures=vec![];
    for (mode,warmup) in [("snapshot",false),("no_output",false),("compact",false),("snapshot",true)] {
        let mut e=Engine::new_production(ring.clone()).unwrap();
        if warmup { e.step(true).unwrap(); }
        let before=public_state(&e);
        e.max_sweeps=1;
        let stop=call(&mut e,mode).unwrap_err();
        let failed=public_state(&e);
        assert_eq!(stop.status,"inconclusive"); assert_eq!(stop.axis,"resource.sweeps");
        assert_ne!(before["state"],failed["state"]);
        e.max_sweeps=1000;
        let frozen_debug=format!("{:?}",e);
        let retry=call(&mut e,mode).unwrap_err();
        assert_eq!(json!(retry),json!(stop));
        assert_eq!(frozen_debug,format!("{:?}",e));
        let restored=Engine::new_production(cycle::checkpoint_input(&ring,failed["state"].clone(),&config).unwrap());
        failures.push(json!({"mode":mode,"warmup_one_complete_tick":warmup,"stop":stop,
            "state_changed_before_error":before["state"]!=failed["state"],
            "inventory_changed_before_error":before["state"]["inventory"]!=failed["state"]["inventory"],
            "repeat_stop_identical":true,"repeat_entire_engine_debug_unchanged":true,
            "before_time":before["state"]["environment"]["time"],"failed_time":failed["state"]["environment"]["time"],
            "failed_judgment_context":failed["state"]["semantic_context"]["judgment_context"],
            "resume_failed_state":match restored {Ok(_)=>json!({"accepted":true}),Err(s)=>json!({"accepted":false,"stop":s})},
            "before":before,"after_error":failed}));
    }
    result["failure_probes"]=json!(failures);

    let mut guard=Engine::new_production(ring.clone()).unwrap();
    let guard_error=guard.step_tick(true).unwrap_err();
    assert!(guard.step(true).unwrap().is_some());
    result["precondition_guard"]=json!({"step_tick_error":guard_error,"subsequent_step_succeeds":true});

    let mut original=Engine::new_production(ring.clone()).unwrap(); original.step(true).unwrap();
    let checkpoint=original.state.clone();
    let mut resumed=Engine::new_production(cycle::checkpoint_input(&ring,json!(checkpoint),&config).unwrap()).unwrap();
    let a=original.step_tick(true).unwrap().unwrap(); let b=resumed.step_tick(true).unwrap().unwrap();
    for field in ["time","events","state","warehouse_ledger","closure"] {assert_eq!(a[field],b[field]);}
    result["last_complete_boundary"]=json!({"resume_and_next_tick_match":true,"fields":["time","events","state","warehouse_ledger","closure"]});

    let record=output::run_record(Engine::new(crusher.clone()).unwrap(),&config,&config_path,4,"full_state_each_instant",1).unwrap();
    output::verify_record_at(&record,crusher.clone(),&config,&config_path,root).unwrap();
    let mut tampered=record.clone(); tampered["trace"]["ticks"][0]["summary"]["r5_tamper"]=json!(true);
    let stop=output::verify_record_at(&tampered,crusher,&config,&config_path,root).unwrap_err();
    assert_eq!(stop.location,"record");
    result["record_verification"]=json!({"completed_ticks":record["trace"]["ticks"].as_array().unwrap().len(),"valid_record_passes":true,"summary_tamper_rejected":stop});

    let certificate=cycle::run_cycle(ring.clone(),&config,&config_path,64,1000).unwrap();
    assert!(!certificate["cycle"].is_null());
    let verified=cycle::verify_cycle_at(&certificate,&config,&config_path,root).unwrap();
    assert_eq!(verified["cycle_replayed"],true);
    let stopped=cycle::run_cycle(ring,&config,&config_path,2,1).unwrap();
    let verified_stop=cycle::verify_cycle_at(&stopped,&config,&config_path,root).unwrap();
    result["cycle_verification"]=json!({"generated_status":certificate["status"],"verification":verified,
        "stopped_status":stopped["status"],"stopped_completed_ticks":stopped["budget"]["completed_ticks"],
        "stopped_partial_events":stopped["stop"]["partial_events"].as_array().unwrap().len(),"stopped_verification":verified_stop});
    std::fs::write(out.join("probe-results.json"),serde_json::to_vec_pretty(&result).unwrap()).unwrap();
    for row in result["failure_probes"].as_array_mut().unwrap() { row.as_object_mut().unwrap().remove("before");row.as_object_mut().unwrap().remove("after_error"); }
    println!("{}",serde_json::to_string_pretty(&result).unwrap());
}
