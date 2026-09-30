use crate::{tests_support::*,value::*};
use serde_json::json;
fn machine()->serde_json::Value{raw(&[("m","粉碎机",10,10,0,0),("out","传送带",11,13,0,0),("power","供电桩",14,10,0,0)])}
#[test] fn completes_at_start_plus_eight_d_and_flushes_immediately(){let mut r=machine();put_seed(&mut r,"m:input:0","源矿",2,None);let mut e=engine(r);let reports=advance(&mut e,9);assert!(reports[0].events.iter().any(|e|e.phase=="start"));assert!(reports[..8].iter().all(|r|r.events.iter().all(|e|e.phase!="complete")));assert!(reports[8].events.iter().any(|e|e.phase=="complete"));assert!(reports[8].events.iter().any(|e|e.phase=="flush"));assert!(reports[8].events.iter().any(|e|e.phase=="start"));assert_eq!(count(&e,"out:transport:0"),1);assert_eq!(e.state.progress[e.progress["m"]].remaining.as_ref().unwrap().integer("m").unwrap(),8);}
#[test] fn completed_batch_flushes_on_the_send_that_makes_room(){let mut r=machine();put_seed(&mut r,"m:output:0","源石粉末",50,None);put_seed(&mut r,"m:buffer:0","源石粉末",1,None);put_seed(&mut r,"m:input:0","源矿",1,None);progress(&mut r,"m")["phase"]=json!("completed");progress(&mut r,"m")["recipe"]=json!("粉碎-源矿");let mut e=engine(r);let report=e.step().unwrap();assert_eq!(count(&e,"m:output:0"),50);let phases:Vec<_>=report.events.iter().map(|e|e.phase.as_str()).collect();assert_eq!(phases,["judge","flush","start"]);}
#[test] fn disabled_machine_does_not_intake_and_work_freezes(){let mut r=machine();switch(&mut r,"m",false);put_seed(&mut r,"m:input:0","源矿",1,None);let mut e=engine(r);advance(&mut e,10);assert_eq!(count(&e,"m:input:0"),1);assert_eq!(count(&e,"m:buffer:0"),0);assert_eq!(e.state.progress[e.progress["m"]].phase,"idle");
    let mut r=machine();switch(&mut r,"m",false);put_seed(&mut r,"m:buffer:0","源矿",1,None);let p=progress(&mut r,"m");p["phase"]=json!("working");p["recipe"]=json!("粉碎-源矿");p["remaining"]=tv(5);let mut e=engine(r);advance(&mut e,10);assert_eq!(e.state.progress[e.progress["m"]].remaining,Some(Time::at(5)));}
#[test] fn output_unique_item_guard_keeps_completed_batch_in_buffer(){let mut r=machine();put_seed(&mut r,"m:input:0","源石粉末",1,None);put_seed(&mut r,"m:buffer:0","源石粉末",1,None);let p=progress(&mut r,"m");p["phase"]=json!("completed");p["recipe"]=json!("粉碎-源矿");let mut e=engine(r);advance(&mut e,9);assert_eq!(count(&e,"m:buffer:0"),1);assert_eq!(count(&e,"m:output:0"),0);}
#[test] fn step_boundary_reload_has_identical_successors(){let mut e=engine(chain());advance(&mut e,31);let mut resumed=reload(&e);for _ in 0..50{let a=e.step().unwrap();let b=resumed.step().unwrap();assert_eq!(e.observe(&a),resumed.observe(&b));assert_eq!(a.ledger,b.ledger);}}
#[test]
fn material_switch_cycles_are_16_16_and_18_steps_with_formal_recipes(){
    // sim2 c 的前两例为单料单格机，正式配方对应粉碎机；第三例才是研磨机。
    for case in 1..=3 {
        let (kind,output_y,power_x)=if case==3{("研磨机",34,16)}else{("粉碎机",33,14)};
        let mut specs=vec![("m",kind,10,30,0,0),("power","供电桩",power_x,30,0,0),("out","传送带",11,output_y,0,0),("sink","协议储存箱",10,output_y+1,0,0)];
        let names:Vec<_>=(0..16).flat_map(|i|if case==2{vec![(format!("a{i}"),10,i)]}else{vec![(format!("a{i}"),10,i),(format!("b{i}"),12,i)]}).collect();
        for (name,x,i) in &names{specs.push((name,"传送带",*x,14+i,0,0));}
        let mut r=raw(&specs);
        for (name,_,i) in &names{let a=if case==2{i%2==1}else{name.starts_with('a')};let item=if case==3{if a{"源石粉末"}else{"蓝铁粉末"}}else if a{"源矿"}else{"蓝铁块"};put_seed(&mut r,&format!("{name}:transport:0"),item,1,Some(-7));}
        if case==3{put_seed(&mut r,"m:input:1","砂叶粉末",50,None);}
        let mut e=engine(r);let reports=advance(&mut e,120);let starts:Vec<_>=reports.iter().flat_map(|r|r.events.iter().filter(|e|e.phase=="start").map(move |e|(r.step,e.detail.as_ref().unwrap()["recipe"].clone()))).collect();
        assert!(starts.len()>=10,"case {case}: {starts:?}");for pair in starts.windows(2){assert_ne!(pair[0].1,pair[1].1,"case {case}");}for window in starts.windows(3){assert_eq!(window[2].0-window[0].0,if case==3{18}else{16},"case {case}: {starts:?}");}
    }
}
