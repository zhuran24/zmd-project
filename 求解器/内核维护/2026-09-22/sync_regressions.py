#!/usr/bin/env python3
"""同步旧回归的任务7契约；保留实际负例强度，不修改运行内核。"""
from pathlib import Path
import json,sys
R=Path.cwd();O=R/'内核维护/2026-09-22';sys.path.insert(0,str(R/'数据/样例'))
import runtime_example as r
for name in ['混做粉碎机两下游','分流器三路轮询']:
 d=json.loads((R/f'数据/样例/{name}.json').read_text());r.write_profile(d)
def edit(name,a,b):
 p=R/name;s=p.read_text();assert a in s,(name,a);p.write_text(s.replace(a,b))
edit('crates/kernel/src/tests.rs','''    assert_eq!(
        e.transfer("south_box", "unit-test-transfer").unwrap(),
        ("success".into(), "empty_box".into())
    );''','''    let (status, details) = e.transfer("south_box", "unit-test-transfer").unwrap();
    assert_eq!(status, "success");
    assert_eq!(serde_json::from_str::<Value>(&details).unwrap(),
        json!({"cooldown_restarted": true, "retained": {}, "sent": {}}));''')
edit('crates/kernel/src/tests.rs','身份不符批量删边，窗口到期不清身份锁存。','身份不符断边；当前身份条件满足且其它守卫解除后恢复。')
edit('crates/kernel/src/tests.rs','fn identity_latch_and_no_cross_disconnected_observation()', 'fn identity_current_condition_restores_disconnected_channel()')
edit('crates/kernel/src/tests.rs','''    e.maintain_identity().unwrap();
    assert!(!e.active.contains(incoming));''','''    e.maintain_identity().unwrap();
    assert!(e.active.contains(incoming));
    let g = &e.state.logistics.gate_counters[e.gate_index["probe_gate_a"]];
    assert!(!g.blocked_reasons.contains(&"identity_mismatch".into()));''')
edit('crates/kernel/src/tests_round5.rs','assert_eq!(result["status"], "counterexample");','assert_eq!(result["status"], "diagnostic_cycle");')
edit('crates/kernel/src/tests_round5.rs','''    let slot = e.inv["source:storage:0"];
    e.state.inventory[slot].contents[0].entered_at = Some(Time::at(i64::MIN));
    let stop = e.cycle_key().unwrap_err();''','''    // 非运输年龄已按当前精确键投影删除；溢出负例须放在实际读取年龄的运输格。
    let source = e.inv["source:storage:0"];
    e.state.inventory[source].contents[0].entered_at = Some(Time::at(i64::MIN));
    assert!(e.cycle_key().is_ok());
    let slot = e.inv["belt_1:transport:0"];
    e.state.inventory[slot].contents[0].entered_at = Some(Time::at(i64::MIN));
    let stop = e.cycle_key().unwrap_err();''')
print('projection and four stale regression contracts synced')
