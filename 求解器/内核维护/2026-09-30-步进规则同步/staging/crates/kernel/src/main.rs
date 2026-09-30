use kernel::{value::*,Config,Engine,Input};
use serde_json::json;
use std::path::Path;
fn run()->Result<()> {
    let args:Vec<_>=std::env::args().skip(1).collect();
    if args.len()<2{return Err(Stop::invalid("cli","check INPUT | run INPUT --steps N --no-output"));}
    let config=Config::parse(serde_json::from_str(include_str!("../../../规格/内核配置-v2.json")).map_err(|e|Stop::invalid("config",e.to_string()))?)?;
    let mut engine=Engine::new(Input::load(Path::new(&args[1]),&config)?)?;
    match args[0].as_str(){
        "check" if args.len()==2=>{let mut layers=std::collections::BTreeMap::new();for n in &engine.graph().layers{*layers.entry(n).or_insert(0)+=1;}println!("{}",json!({"components":engine.graph().components.len(),"layers":layers,"order_length":engine.graph().order.len()}));}
        "run" if args.len()==5 && args[2]=="--steps" && args[4]=="--no-output"=>{let steps:usize=args[3].parse().map_err(|_|Stop::invalid("steps","须为非负整数"))?;for _ in 0..steps{engine.step()?;}println!("{}",json!({"completed_steps":steps,"next_step":engine.time(),"completed_batches":engine.completed_batches,"actual_inbound":engine.delivery}));}
        _=>return Err(Stop::invalid("cli","仅支持 check INPUT 或 run INPUT --steps N --no-output；记录与周期接口待包二"))
    }Ok(())
}
fn main(){if let Err(e)=run(){eprintln!("{}",serde_json::to_string(&e).unwrap());std::process::exit(1);}}
