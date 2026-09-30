from pathlib import Path
O=Path(__file__).resolve().parent;R=O.parents[1];S=O/'package2-stage'
def put(p,t):(S/p).write_text(t)
s=(R/'crates/kernel/src/cycle.rs').read_text()
# Strictly remove scheduler/pending dependencies.
a=s.index('                for e in self.input.raw["timeline"]');b=s.index('\n            }\n            2 =>',a)
s=s[:a]+'''                for e in self.input.raw["timeline"]["events"].as_array().unwrap() {
                    let t=instant(&e["time"],"cycle.history")?;
                    if t>self.t || (t==self.t && ["offline","withdraw_product","debug_operation","unit_removed","unit_rebuilt"].contains(&e["kind"].as_str().unwrap_or(""))) {
                        return Err(fail(e["id"].as_str().unwrap_or(""),"生产域不接受未来历史或当前待执行玩家动作"));
                    }
                }'''+s[b:]
s=s.replace('.cooldowns\n                            .iter()\n                            .all(|c| c.remaining.integer(unit).is_ok_and(|n| n == 0))','.cooldown.as_ref().is_some_and(|c|c.integer(unit).is_ok_and(|n| n <= 1))')
s=s.replace('                    .arbitration\n','').replace('semantic_context.arbitration.warehouse_empty_slot_order','semantic_context.warehouse_empty_slot_order')
a=s.index('        // 固定几何预索引');b=s.index('\n        Ok(())',a)
s=s[:a]+'''        for (cid,c) in &self.input.geometry.channels {
            if self.input.geometry.units[&self.input.geometry.ports[&c.target_port].unit].kind!="协议核心" {continue;}
            if self.source(&c.source_port)?.is_some_and(|(_,c)| ORES.contains(&c.item.as_str())) {
                return Err(Stop::unsupported("cycle.domain.D2",cid,"现存回矿候选读取被抽象容量"));
            }
        }'''+s[b:]
a=s.index('    let jc = &state.semantic_context');b=s.index('    let mut s = json!(state);',a)
s=s[:a]+'''    if !state.semantic_context.warehouse_empty_slot_order.is_empty() {
        return Err(Stop::unsupported("cycle.domain.D3","cycle_key","仓库匿名空格序必须为空"));
    }
'''+s[b:]
s=s.replace('let residual = if age >= 1 { 0 } else { 1 };','let residual = difference(input.catalog.residence_steps, age.min(input.catalog.residence_steps), "cycle.residence")?;')
a=s.index('    for row in s["progress"].as_array_mut()');b=s.index('    for r in lg["gate_counters"]',a)
s=s[:a]+'''    sort_rows(&mut s["progress"], "unit");
    let lg=&mut s["logistics"];
'''+s[b:]
a=s.index('        r["blocked_reasons"]');b=s.index('        let uid =',a);s=s[:a]+s[b:]
a=s.index('    s["environment"]["time"] = tv(0);');b=s.index('    normalize(&mut s)?;',a)
s=s[:a]+'''    s["environment"].as_object_mut().unwrap().remove("time");
'''+s[b:]
s=s.replace('phase-cycle-key-v1','phase-cycle-key-v2').replace('phase_production_v1','phase_production_v2')
# Checkpoint input stays bound to fixed parameters. Validate immediately and retain absolute refs on export.
a=s.index('pub fn checkpoint_input(');b=s.index('\nfn stop_value',a)
s=s[:a]+'''pub fn checkpoint_input(input: &Input, state: Value, config: &Config) -> Result<Input> {
    let mut raw=input.raw.clone();
    raw["initial_state"]["nonwarehouse"]["value"]=state;
    let resumed=Input::parse(raw,&input.path,config)?;
    Engine::new(resumed.clone())?;
    Ok(resumed)
}
'''+s[b:]
s=s.replace('fn restore(input: &Input, state: &State, config: &Config, sweeps: usize)', 'fn restore(input: &Input, state: &State, config: &Config)')
s=s.replace('    let mut engine = Engine::new_production(checkpoint_input(input, json!(state), config)?)?;\n    engine.max_sweeps = sweeps;\n    engine.set_cache_enabled(true);\n    Ok(engine)','    Engine::new_production(checkpoint_input(input, json!(state), config)?)')
s=s.replace('    sweeps: usize,\n','').replace('restore(input, state, config, sweeps)?','restore(input, state, config)?')
s=s.replace('max_ticks','max_steps').replace('completed_ticks','completed_steps')
s=s.replace('    max_sweeps: usize,\n','').replace('        max_sweeps,\n','').replace(', max_sweeps, options',', options')
s=s.replace(' || max_sweeps == 0','').replace('    engine.max_sweeps = max_sweeps;\n','').replace('    engine.set_cache_enabled(true);\n','')
s=s.replace('if stop.is_none() && seed.semantic_context.judgment_context.value["phase"] == "after_closure"','if stop.is_none()')
s=s.replace('engine.step_compact()', 'engine.step()').replace('replay.step_compact()', 'replay.step()').replace('&engine.records','&engine.events')
s=s.replace('restore(&input, &start, config, max_sweeps)?','restore(&input, &start, config)?').replace('restore(&input, &seed, config, max_sweeps)?','restore(&input, &seed, config)?').replace('        replay.max_sweeps = max_sweeps;\n','')
s=s.replace('json!({"time":tv(replay.t),"warehouse_ledger":replay.ledger})','json!({"step":replay.t-1,"warehouse_ledger":replay.ledger})')
s=s.replace('(inbound as i128*d as i128)', '(inbound as i128*input.catalog.steps_per_tick as i128*d as i128)')
s=s.replace('rational(&format!("{inbound}/{period}"))?', 'rational(&format!("{}/{period}",inbound as i128*input.catalog.steps_per_tick as i128))?')
s=s.replace('cycle-normalization-v2','cycle-normalization-v3')
s=s.replace('cycle = json!({"period":q(period),','cycle = json!({"period":q(period),"period_ticks":{"value":rational(&format!("{period}/{}",input.catalog.steps_per_tick))?,"category":"算术推论"},')
s=s.replace('"resource.ticks"','"resource.steps"').replace('"damping."','"step.order"')
s=s.replace('full_state_each_instant','full_state_each_step').replace('kernel-output-v4','kernel-output-v5').replace('kernel-input-v3','kernel-input-v4').replace('kernel-cycle-v3','kernel-cycle-v4').replace('kernel_profile_v1','kernel_profile_v2')
s=s.replace('format!("cycle:{}:{max_steps}:{max_sweeps}",','format!("cycle:{}:{max_steps}",').replace('"max_sweeps":max_sweeps,','')
s=s.replace('let mut replay = restore(&input, &seed, config)?','let replay = restore(&input, &seed, config)?')
s=s.replace('global/v1','step-order-v1').replace('每刻','每步').replace('整刻','整步').replace('P刻','P步').replace('{period}刻','{period}步').replace('{completed}刻','{completed}步')
s=s.replace('一般真实事件推进到工程闭包的PC-06对应仍缺推导','整数步字段投影已实现；全域模拟关系仍需独立证明')
s=s.replace('PC-06：一般双端协调、失败环真实唤醒及关闭intake对应待证明','商状态各读取点的对应关系需独立审查；单一轨迹不替代全域证明')
s=s.replace('整数固定环境为本次支持域；实数时间有限化仍待证明','整数步固定环境为本次支持域')
s=s.replace('PC-06真实调度对应仍开放','全域模拟关系仍待独立审查').replace('同刻closure_key','记录编码').replace('after_closure','步边界')
s=s.replace('仓库容量/physical/权限前动态核验','仓库容量规划前动态核验').replace('容量/物理/授权','容量规划').replace('未来PC及有资格全箱','未来核心通道及有资格全箱')
s=s.replace('时刻预算耗尽','步数预算耗尽').replace('预算及检查点间隔须正','步数预算及检查点间隔须正').replace('公开预算仍恰为契约的ticks/sweeps','公开预算仍恰为步数')
s=s.replace('({a},{b}]，全部候选查询及实际提交','[{a},{b})，全部候选查询及实际提交')
put('crates/kernel/src/cycle.rs',s)
# Adapt independent verifier, preserving exact full-object comparison and fingerprint checks.
s=(R/'crates/kernel/src/cycle_io.rs').read_text().replace('    event_identity::EventValidator,\n','')
s=s.replace('kernel-cycle-v3','kernel-cycle-v4').replace('kernel-input-v3','kernel-input-v4').replace('kernel-output-v4','kernel-output-v5').replace('full_state_each_instant','full_state_each_step')
s=s.replace('max_ticks','max_steps').replace('completed_ticks','completed_steps').replace('ticks','steps')
s=s.replace('Input::load(&source, config, false)','Input::load(&source, config)').replace('Input::parse(raw, &source, config, false)','Input::parse(raw, &source, config)')
a=s.index('        let sweeps =');b=s.index('        let mut expected',a);s=s[:a]+s[b:]
s=s.replace('load_stopped_cycle(&stop, steps, sweeps, meeting)','load_stopped_cycle(&stop, steps, meeting)')
a=s.index('    let sweeps =');b=s.index('    let mut loaded_record',a);s=s[:a]+s[b:]
s=s.replace('cycle::search(input.clone(), config, config_path, steps, sweeps, &options)?','cycle::search(input.clone(), config, config_path, steps, &options)?')
s=s.replace('    prefix.max_sweeps = sweeps;\n','').replace('    prefix.set_cache_enabled(true);\n','').replace('    let mut registry = EventValidator::new(&input, &json!(prefix.state))?;\n','')
s=s.replace('        let row = prefix.step(true)?.unwrap();\n        registry.tick(&row)?;\n        crate::ledger::verify_tick(&previous, &row)?;', '        let report=prefix.step()?;\n        let row=output::step_row(&prefix,&report);\n        output::verify_step_events(&previous,&row)?;')
s=s.replace('    replay.max_sweeps = sweeps;\n','').replace('    replay.set_cache_enabled(true);\n','').replace('    let mut registry = EventValidator::new(&input, &c["start_state"])?;\n','')
s=s.replace('        let row = replay.step_tick(true)?.unwrap();\n        registry.tick(&row)?;\n        crate::ledger::verify_tick(&previous, &row)?;', '        let report=replay.step()?;\n        let row=output::step_row(&replay,&report);\n        output::verify_step_events(&previous,&row)?;')
s=s.replace('json!({"time":row["time"],"warehouse_ledger":row["warehouse_ledger"]})','json!({"step":row["step"],"warehouse_ledger":row["warehouse_ledger"]})').replace('t["time"] == row["time"]','t["step"] == row["step"]').replace('["time", "events", "state", "warehouse_ledger", "closure"]','["step", "events", "state", "warehouse_ledger"]')
s=s.replace('    max_sweeps: usize,\n','').replace('"max_sweeps":max_sweeps.max(1),','').replace('phase_production_v1','phase_production_v2')
s=s.replace('        "event_identity.rs",\n','').replace('        "transition.rs",','        "step.rs",\n        "graph.rs",').replace('        "cache.rs",\n','')
s=s.replace('P刻','P步').replace('周期刻','周期步').replace('跨刻','跨步').replace('step_tick','step').replace('完整v3前缀','完整v5前缀')
put('crates/kernel/src/cycle_io.rs',s)
# Restore full CLI, replacing removed modes and enforcing step flags.
s=(O/'before/crates/kernel/src/main.rs').read_text()
s=s.replace('--ticks','--steps').replace('--max-ticks','--max-steps').replace('ticks','steps').replace('full_state_each_instant','full_state_each_step').replace('kernel-cycle-v3','kernel-cycle-v4')
s=s.replace('    let mut cache = true;\n','').replace('    let mut max_sweeps = 100_000usize;\n','')
a=s.index('        if key == "--no-cache"');b=s.index('        if key == "--no-output"',a);s=s[:a]+s[b:]
a=s.index('            "--max-sweeps" =>');b=s.index('            "--format" =>',a);s=s[:a]+s[b:]
s=s.replace('let cfg = config_path.ok_or_else(|| Stop::invalid("cli", "缺 --config"))?;', 'let cfg = config_path.unwrap_or_else(|| PathBuf::from(concat!(env!("CARGO_MANIFEST_DIR"),"/../../规格/内核配置-v2.json")));')
s=s.replace('Input::load(&source, &config, false)','Input::load(&source, &config)').replace('Input::load(&path, &config, command == "check" && !cycle_domain)','Input::load(&path, &config)')
s=s.replace('Engine::check_cycle_domain(input)?','Engine::new_production(input)?.domain_report("static")')
s=s.replace('"schema":"kernel-input-v3"','"schema":"kernel-input-v4"')
s=s.replace('max_sweeps,\n','').replace('max_sweeps, ', '').replace('            engine.max_sweeps = max_sweeps;\n','').replace('        engine.max_sweeps = max_sweeps;\n','')
s=s.replace('            engine.set_cache_enabled(cache);\n','').replace('        engine.set_cache_enabled(cache);\n','')
s=s.replace('engine.run_without_output(steps)?', '(|| -> Result<_> {for _ in 0..steps {engine.step()?;} Ok(serde_json::json!({"completed_steps":steps,"next_step":engine.time(),"completed_batches":engine.completed_batches,"actual_inbound":engine.delivery}))})()?')
s=s.replace('"python"','"python3"')
put('crates/kernel/src/main.rs',s)
