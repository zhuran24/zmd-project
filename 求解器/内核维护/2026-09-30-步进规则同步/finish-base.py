import sys
from work import *
guard('base-before')
s=(ROOT/'crates/kernel/src/input.rs').read_text().replace('        result.graph = crate::graph::StepGraph::build(&result)?;','''        result.transfer_timing = result.parameters.value(Axis::TransferTiming)?["values"].as_array().unwrap().iter().map(|r|(r["unit"].as_str().unwrap().to_string(),r["timing"].as_str().unwrap().to_string())).collect();
        result.graph = crate::graph::StepGraph::build(&result)?;''')
write('crates/kernel/src/input.rs',s)
for f in ['transition.rs','cache.rs','tests.rs','tests_revision.rs','tests_revision_r2.rs','tests_revision_r3.rs','tests_revision_r4.rs','tests_revision_r5.rs','tests_round5.rs','tests_round6.rs','tests_bridge.rs']:
    remove('crates/kernel/src/'+f)
sys.path.insert(0,str(ROOT/'数据/工具'))
from step_inputs import generate
base=ROOT/'crates/kernel/tests/fixtures/step'
d={'units':[{'id':'source','kind':'仓库取货口','x':10,'y':0},{'id':'b0','kind':'传送带','x':11,'y':1},{'id':'b1','kind':'传送带','x':11,'y':2},{'id':'crusher','kind':'粉碎机','x':10,'y':3},{'id':'power','kind':'供电桩','x':14,'y':3},{'id':'out','kind':'传送带','x':11,'y':6}]}
write('crates/kernel/tests/fixtures/step/base.json',json_text(generate(d,base)))
write('crates/kernel/tests/reference.rs','''//! 包一：新格式 fixtures 完整装载与 64 步执行；差分留包二。
use kernel::{value::*,Config,Engine,Input};
#[test]
fn step_fixtures_run_64_steps(){
    let root=std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let config=Config::parse(read_json(&root.join("../../规格/内核配置-v2.json")).unwrap()).unwrap();
    let mut count=0;
    for entry in std::fs::read_dir(root.join("tests/fixtures/step")).unwrap(){let path=entry.unwrap().path();if path.extension().is_some_and(|e|e=="json"){let mut engine=Engine::new(Input::load(&path,&config).unwrap()).unwrap();let start=engine.time();for _ in 0..64{engine.step().unwrap();}assert_eq!(engine.time(),start+64);count+=1;}}
    assert!(count>0);
}
''')
guard('base-after')
