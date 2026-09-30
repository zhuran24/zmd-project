//! 只在内存构造布局、完整输入和条件状态，不写样例或历史证据。
use crate::{*,catalog::*,config::*,graph::*,model::*,value::*};
use serde_json::{json,Value};
use std::{collections::BTreeMap,path::PathBuf};
pub type Spec<'a>=(&'a str,&'a str,i64,i64,i64,usize);
pub fn root()->PathBuf{PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..").canonicalize().unwrap()}
pub fn config()->Config{Config::parse(read_json(&root().join("规格/内核配置-v2.json")).unwrap()).unwrap()}
pub fn set_axis(raw:&mut Value,axis:&str,v:Value){for g in ["fixed","offline_mutable","fixedness_unproven"]{if raw["parameters"][g].get(axis).is_some(){raw["parameters"][g][axis]["value"]=v;return;}}panic!("missing {axis}");}
pub fn axis<'a>(raw:&'a Value,axis:&str)->&'a Value{for g in ["fixed","offline_mutable","fixedness_unproven"]{if let Some(v)=raw["parameters"][g].get(axis){return &v["value"];}}panic!("missing {axis}");}
pub fn d(v:Value)->Value{json!(Decision::specified(v,"步进机制测试的显式条件输入"))}
pub fn state(raw:&mut Value)->&mut Value{&mut raw["initial_state"]["nonwarehouse"]["value"]}
pub fn raw(specs:&[Spec])->Value{
    let path=root().join("crates/kernel/tests/fixtures/step/base.json");
    let mut raw=read_json(&path).unwrap();let catalog=Catalog::load(&root().join("数据/正式静态目录.json")).unwrap();
    raw["catalog"]["path"]=json!(catalog.path);raw["parameters"]["axis_registry"]["path"]=json!(root().join("规格/内核配置-v2.json"));
    let mut specs=specs.to_vec();if !specs.iter().any(|s|s.1=="协议核心"){specs.push(("core","协议核心",50,50,0,0));}
    let units:Vec<_>=specs.iter().map(|(id,kind,x,y,turn,layout)|json!({"id":id,"kind":kind,"origin":[q(*x),q(*y)],"rotation":format!("r{turn}"),"port_layout":if *kind=="桥接器"{Value::Null}else{json!(layout)},"bridge_axes":null,"occupied_cells":null})).collect();
    raw["layout"]["units"]=json!(units);raw["layout"]["physical_channels"]=Value::Null;raw["layout"]["buffer_channels"]=Value::Null;
    let geometry=Geometry::build(&raw["layout"],&catalog).unwrap();
    raw["layout"]["physical_channels"]=json!(geometry.channels.values().collect::<Vec<_>>());
    raw["layout"]["buffer_channels"]=json!(geometry.buffers.iter().map(|id|{let p:Vec<_>=id.split('|').collect();json!({"id":id,"source_slot":p[1],"target_slot":p[2]})}).collect::<Vec<_>>());
    let mut order:Vec<_>=units.iter().map(|u|u["id"].as_str().unwrap().to_string()).collect();order.sort_by_key(|u|geometry.units[u].kind=="传送带");
    let builds:BTreeMap<_,_>=order.iter().enumerate().map(|(i,u)|(u.clone(),format!("build_{i}"))).collect();let times:BTreeMap<_,_>=order.iter().enumerate().map(|(i,u)|(u.clone(),i as i64-order.len() as i64-1)).collect();
    let mut events:Vec<_>=order.iter().map(|u|json!({"id":builds[u],"kind":"build","time":tv(times[u])})).collect();events.extend([json!({"id":"complete","kind":"blueprint_complete","time":tv(0)}),json!({"id":"debug_end","kind":"debug_end","time":tv(0)})]);
    let moments:Vec<_>=order.iter().map(|u|{let mut placement=geometry.units[u].raw.clone();placement.as_object_mut().unwrap().remove("id");placement.as_object_mut().unwrap().remove("bridge_axes");json!({"event":builds[u],"unit":u,"placement":placement})}).collect();
    raw["construction"]["selected_order"]=json!(order);raw["construction"]["moments"]=json!(moments);
    let mut connections=Vec::new();let mut connection_times=BTreeMap::new();
    for (i,ch) in geometry.channels.values().enumerate(){let a=&geometry.ports[&ch.source_port].unit;let b=&geometry.ports[&ch.target_port].unit;let later=if times[a]>times[b]{a}else{b};let event=format!("conn_{i}");events.push(json!({"id":event,"kind":"connection_open","time":tv(times[later])}));connections.push(json!({"event":event,"channel":ch.id,"action":"open","cause":builds[later],"geometry_snapshot":"built_layout","construction_basis":d(json!({"source_build":builds[a],"target_build":builds[b],"later_build":builds[later]}))}));connection_times.insert(ch.id.clone(),times[later]);}
    raw["timeline"]=json!({"events":events,"relations":[],"connection_events":connections});
    let switches:Vec<_>=geometry.units.iter().flat_map(|(u,x)|catalog.kinds[&x.kind].functions.iter().map(move |f|json!({"unit":u,"function":f,"enabled":true}))).collect();raw["settings"]["switches"]=json!(switches);
    let gates:Vec<_>=geometry.units.iter().filter(|(_,u)|u.kind=="物品准入口").map(|(u,_)|json!({"unit":u,"item":null,"total_limit":null,"window_limit":null})).collect();raw["settings"]["gates"]=json!(gates);
    raw["settings"]["warehouse_assignments"]=json!(geometry.ports.iter().filter(|(_,p)|p.role=="output" && ["协议核心","仓库取货口"].contains(&geometry.units[&p.unit].kind.as_str())).map(|(id,_)|json!({"port":id,"slot":"warehouse_0"})).collect::<Vec<_>>());
    let slots=catalog.slots(&geometry.units,1).unwrap();let inventory:Vec<_>=slots.keys().map(|s|json!({"slot":s,"contents":[]})).collect();
    let progress:Vec<_>=geometry.units.iter().filter(|(_,u)|!catalog.kinds[&u.kind].functions.is_empty()).map(|(u,x)|json!({"unit":u,"phase":"idle","recipe":null,"remaining":null,"cooldown":if x.kind=="协议储存箱"{tv(0)}else{Value::Null}})).collect();
    set_axis(&mut raw,"transfer.phase",json!({"kind":"explicit_residuals","values":progress.iter().filter(|p|!p["cooldown"].is_null()).map(|p|json!({"unit":p["unit"],"slot":null,"remaining":p["cooldown"]})).collect::<Vec<_>>()}));
    set_axis(&mut raw,"transfer.timing",json!({"schema":"transfer-timing-v1","values":progress.iter().filter(|p|!p["cooldown"].is_null()).map(|p|json!({"unit":p["unit"],"timing":"before_send"})).collect::<Vec<_>>()}));
    let mut shapes=vec![];for (u,x) in &geometry.units{if x.kind!="传送带"{continue;}let sides=["south","east","north","west"];let edges=catalog.kinds[&x.kind].layouts[x.raw["port_layout"].as_u64().unwrap() as usize].as_array().unwrap();let a=edges.iter().find(|e|e["role"]=="input").unwrap();let b=edges.iter().find(|e|e["role"]=="output").unwrap();let a=sides.iter().position(|s|a["side"]==*s).unwrap();let b=sides.iter().position(|s|b["side"]==*s).unwrap();shapes.push(json!({"unit":u,"build_event":builds[u],"shape":match (b+4-a)%4{1=>"turn_left",2=>"straight",3=>"turn_right",_=>unreachable!()}}));}
    set_axis(&mut raw,"connection.belt_shape",json!({"kind":"layout_build_history","values":shapes}));
    let tie:Vec<_>=geometry.channels.keys().cloned().collect();set_axis(&mut raw,"connection.tie",json!({"kind":"explicit_order","channels":tie}));
    set_axis(&mut raw,"manufacturing.input_slot_selection",json!({"kind":"explicit_order","slots":slots.keys().filter(|s|s.contains(":input:")).collect::<Vec<_>>()}));
    let graph=StepGraph::structure(&geometry,&catalog,&connection_times,&tie).unwrap();set_axis(&mut raw,"step.order",graph.default_order());
    let cursors:Vec<_>=graph.cursor_sides().keys().map(|s|json!({"side":s,"last_success":null})).collect();let recency:Vec<_>=graph.outputs_nt.iter().filter(|(_,c)|c.len()>1).map(|(u,_)|json!({"unit":u,"order":[]})).collect();
    let wh=raw["initial_state"]["warehouse"].clone();let s=state(&mut raw);s["warehouse"]=wh;s["inventory"]=json!(inventory);s["progress"]=json!(progress);s["environment"]["time"]=tv(0);s["logistics"]=json!({"poll_state":{"schema":"poll-state-v1","cursors":cursors,"recency":recency},"gate_counters":gates.iter().map(|g|json!({"unit":g["unit"],"total_received":q(0),"window_received":q(0),"window_started_at":null})).collect::<Vec<_>>()});s["semantic_context"]=json!({"warehouse_empty_slot_order":[]});
    raw
}
pub fn parse(raw:Value)->Result<Input>{Input::parse_with_base(raw,&root(),&config())}
pub fn engine(raw:Value)->Engine{Engine::new(parse(raw).unwrap()).unwrap()}
pub fn put_seed(raw:&mut Value,slot:&str,item:&str,n:i64,entered:Option<i64>){let row=state(raw)["inventory"].as_array_mut().unwrap().iter_mut().find(|r|r["slot"]==slot).unwrap();row["contents"].as_array_mut().unwrap().push(json!({"item":item,"quantity":q(n),"entered_at":entered.map(tv)}));}
pub fn count(e:&Engine,slot:&str)->i64{e.state.inventory[e.inv[slot]].contents.iter().map(|c|c.quantity.integer(slot).unwrap()).sum()}
pub fn advance(e:&mut Engine,n:usize)->Vec<StepReport>{(0..n).map(|_|e.step().unwrap()).collect()}
pub fn moves(reports:&[StepReport])->Vec<(i64,String,String)>{reports.iter().flat_map(|r|r.events.iter().flat_map(move |e|e.moves.iter().map(move |m|(r.step,m.channel.clone(),m.item.clone())))).collect()}
pub fn switch(raw:&mut Value,u:&str,enabled:bool){for s in raw["settings"]["switches"].as_array_mut().unwrap(){if s["unit"]==u{s["enabled"]=json!(enabled);}}}
pub fn chain()->Value{raw(&[("source","仓库取货口",10,0,0,0),("b0","传送带",11,1,0,0),("b1","传送带",11,2,0,0),("m","粉碎机",10,3,0,0),("out","传送带",11,6,0,0),("power","供电桩",14,3,0,0)])}
pub fn progress<'a>(raw:&'a mut Value,u:&str)->&'a mut Value{state(raw)["progress"].as_array_mut().unwrap().iter_mut().find(|p|p["unit"]==u).unwrap()}
pub fn reload(e:&Engine)->Engine{let mut raw=e.input.raw.clone();*state(&mut raw)=json!(e.state);let phases:Vec<_>=e.state.progress.iter().filter_map(|p|p.cooldown.as_ref().map(|t|json!({"unit":p.unit,"slot":null,"remaining":t}))).collect();set_axis(&mut raw,"transfer.phase",json!({"kind":"explicit_residuals","values":phases}));engine(raw)}
