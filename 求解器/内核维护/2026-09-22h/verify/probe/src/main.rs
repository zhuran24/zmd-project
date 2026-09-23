use kernel::{catalog::{Catalog,Geometry},value::{read_json,q,tv}};
use serde_json::{Value,json};
use std::{collections::{BTreeMap,BTreeSet},path::Path};

fn axis(raw:&mut Value,key:&str,value:Value) {
    for group in ["fixed","offline_mutable","fixedness_unproven"] {
        if raw["parameters"][group].get(key).is_some() {
            raw["parameters"][group][key]["value"]=value.clone();
        }
    }
    for row in raw["initial_state"]["nonwarehouse"]["value"]["semantic_context"]["parameter_values"].as_array_mut().unwrap() {
        if row["axis"]==key {row["value"]["value"]=value.clone();}
    }
}
fn main() {
    let args:Vec<_>=std::env::args().collect();
    let solver=Path::new(&args[1]);let verify=Path::new(&args[2]);
    let fixture=read_json(&solver.join("crates/kernel/tests/fixtures/bridge.json")).unwrap();
    let catalog=Catalog::load(&solver.join("数据/正式静态目录.json")).unwrap();
    let cases=read_json(&verify.join("cases.json")).unwrap();
    for case in cases.as_array().unwrap() {
        let mut raw=fixture.clone();
        raw["catalog"]["path"]=json!(catalog.path);
        raw["parameters"]["axis_registry"]["path"]=json!(solver.join("规格/选择点参数轴.md"));
        let mut units=vec![fixture["layout"]["units"][0].clone()];
        for u in case["units"].as_array().unwrap() {
            units.push(json!({"id":u[0],"kind":u[1],"origin":[q(u[2].as_i64().unwrap()),q(u[3].as_i64().unwrap())],
                "rotation":u[4],"port_layout":if u[1]=="桥接器" {Value::Null} else {json!(0)},"bridge_axes":null,"occupied_cells":null}));
        }
        // Belts are constructed after their fixed-neighbour shapes are available.
        units.sort_by_key(|u| u["kind"]=="传送带");
        raw["layout"]["units"]=json!(units);
        raw["layout"]["physical_channels"]=Value::Null;
        raw["layout"]["buffer_channels"]=json!([]);
        raw["scenario"]=json!({"name":case["name"],"recipe_intents":[],"expected_paths":[],"assertions":[]});
        raw["settings"]["switches"]=json!([]);
        raw["initial_state"]["anchor"]["value"]=json!({"event":"built_0","side":"after"});
        raw["initial_state"]["anchor"]["basis"]=json!(["仓库初值锚在隔离核心建成后；有限轨迹从debug_end开始"]);
        axis(&mut raw,"initialization.warehouse_anchor",json!({"kind":"input_anchor","event":"built_0","side":"after"}));
        let geom=Geometry::build(&raw["layout"],&catalog).unwrap();
        raw["layout"]["physical_channels"]=json!(geom.channels.values().collect::<Vec<_>>());
        let rank:BTreeMap<String,usize>=units.iter().enumerate().map(|(i,u)|(u["id"].as_str().unwrap().into(),i)).collect();
        let n=units.len() as i64;
        let mut events=vec![];let mut relations=vec![];let mut moments=vec![];let mut connections=vec![];
        for (i,u) in units.iter().enumerate() {
            let event=format!("built_{i}");
            events.push(json!({"id":event,"kind":"build","time":tv(i as i64-n)}));
            moments.push(json!({"unit":u["id"],"event":event,"placement":{
                "kind":u["kind"],"origin":u["origin"],"rotation":u["rotation"],"port_layout":u["port_layout"],"occupied_cells":null}}));
            relations.push(json!({"before":event,"after":if i+1<units.len(){format!("built_{}",i+1)}else{"blueprint_complete".into()},"relation":"strict","basis":["独立小布局的显式顺序"]}));
        }
        for id in ["blueprint_complete","debug_end"] {events.push(json!({"id":id,"kind":id,"time":tv(0)}));}
        relations.push(json!({"before":"blueprint_complete","after":"debug_end","relation":"occurs_before","basis":["构建完成后开始有限轨迹"]}));
        for (i,c) in geom.channels.values().enumerate() {
            let a=rank[&geom.ports[&c.source_port].unit];let b=rank[&geom.ports[&c.target_port].unit];let later=a.max(b);
            let event=format!("opened_{i}");
            events.push(json!({"id":event,"kind":"connection_open","time":tv(later as i64-n)}));
            connections.push(json!({"event":event,"channel":c.id,"action":"open","cause":format!("built_{later}"),"geometry_snapshot":raw["layout"]["id"],
                "construction_basis":{"status":"specified","value":{"source_build":format!("built_{a}"),"target_build":format!("built_{b}"),"later_build":format!("built_{later}")},"basis":["相邻端口在较晚单位建成时接通"]}}));
        }
        raw["construction"]["moments"]=json!(moments);
        raw["construction"]["selected_order"]=json!(units.iter().map(|u|u["id"].clone()).collect::<Vec<_>>());
        raw["timeline"]=json!({"events":events,"relations":relations,"connection_events":connections});
        axis(&mut raw,"connection.belt_shape",json!({"kind":"layout_build_history","values":units.iter().filter(|u|u["kind"]=="传送带").map(|u|json!({"unit":u["id"],"build_event":format!("built_{}",rank[u["id"].as_str().unwrap()]),"shape":"straight"})).collect::<Vec<_>>()}));
        axis(&mut raw,"transfer.phase",json!({"kind":"explicit_residuals","values":[]}));
        axis(&mut raw,"connection.tie",json!({"kind":"explicit_order","channels":geom.channels.keys().collect::<Vec<_>>()}));
        axis(&mut raw,"judgment.order",json!({"schema":"event-order-v1","scope":"global","template_order":geom.channels.keys().map(|c|json!({"operation":"move","target":c})).collect::<Vec<_>>(),"repeat_embedding":"scan_round_then_template","instant_overrides":[]}));
        let mut levels=BTreeSet::new();
        for c in geom.channels.values() {
            for (local,peer,side) in [(&c.source_port,&c.target_port,"output"),(&c.target_port,&c.source_port,"input")] {
                let port=&geom.ports[local];let graded=side=="input" || catalog.kinds[&geom.units[&port.unit].kind].family!="transport";
                let direct=graded && geom.units[&geom.ports[peer].unit].kind==if side=="input"{"分流器"}else{"汇流器"};
                let suffix=if direct {format!("direct:{}",c.id)}else{if graded{"other"}else{"ungraded"}.into()};
                let ax=port.axis.as_ref().map(|x|format!("|{x}")).unwrap_or_default();
                levels.insert(format!("L|{}{ax}|{side}|{suffix}",port.unit));
            }
        }
        let state=&mut raw["initial_state"]["nonwarehouse"]["value"];
        state["inventory"]=json!(catalog.slots(&geom.units,1).unwrap().keys().map(|slot| {
            let contents=case["inventory"].as_array().unwrap().iter().filter(|r|r[0]==*slot).map(|r| {
                let mut c=json!({"item":r[1],"quantity":q(r[2].as_i64().unwrap()),"entered_at":tv(-1)});
                if !r[3].is_null() {c["last_unit"]=r[3].clone();} c
            }).collect::<Vec<_>>();json!({"slot":slot,"contents":contents})
        }).collect::<Vec<_>>());
        state["progress"]=json!([]);
        state["logistics"]["poll_memory"]["value"]["sides"]=json!([]);
        state["semantic_context"]["arbitration"]["level_order"]=json!(levels);
        let dir=verify.join("cases").join(case["name"].as_str().unwrap());std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("input.json"),serde_json::to_string_pretty(&raw).unwrap()+"\n").unwrap();
    }
}
