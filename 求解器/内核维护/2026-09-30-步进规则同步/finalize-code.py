import sys, subprocess
from work import *
guard('format-before')
# 文本表述按步；Time 中 1/8 tick 是换算定义。
p=ROOT/'规格/内核配置-v2.json';s=p.read_text().replace('5 tick','40 步');write('规格/内核配置-v2.json',s)
# 配置字节已更新，fixture 重锁。
p=ROOT/'crates/kernel/tests/fixtures/step/base.json';v=json.loads(p.read_text());v['parameters']['axis_registry']['sha256']=digest(ROOT/'规格/内核配置-v2.json');write('crates/kernel/tests/fixtures/step/base.json',json_text(v))
# put 普通格同种唯一先于提交；内部缓存整批通道仍排除在该约束之外。
p=ROOT/'crates/kernel/src/engine.rs';s=p.read_text();anchor='        let total = contents\n'
insert='''        let uid = slot.split(':').next().unwrap();
        let kind = &self.input.catalog.kinds[&self.input.geometry.units[uid].kind];
        if !buffer && kind.same_item_unique && self.unit_inventory[uid].iter().any(|i| {
            let r = &self.state.inventory[*i];
            r.slot != slot && !r.slot.contains(":buffer:") && r.contents.iter().any(|c|c.item == item)
        }) { return Err(Stop::invalid(slot, "put违反同单位同种普通格唯一")); }
'''
assert anchor in s;s=s.replace(anchor,insert+anchor);write('crates/kernel/src/engine.rs',s)
# 方法说明去掉被删除的输入模式/模板术语。
p=ROOT/'crates/kernel/src/input.rs';s=p.read_text().replace('结构例只作静态检查，执行例还需完整参数和 StateSeed。','v4 输入严格装载，要求完整参数、状态与步进先后。').replace('接口对象形状及全序必须完整；新事件不改变模板全序。','接口对象形状与全序必须完整。');write('crates/kernel/src/input.rs',s)
excluded={'output.rs','cycle.rs','cycle_io.rs','event_identity.rs','seed.rs','digest.rs','ledger.rs'}
paths=[str(p) for p in sorted((ROOT/'crates/kernel/src').glob('*.rs')) if p.name not in excluded]+[str(ROOT/'crates/kernel/tests/reference.rs')]
argv=['rustfmt','--edition','2021','--config','skip_children=true',*paths]
with (OUT/'format.log').open('w') as log:r=subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT)
save('format-command.json',{'argv':argv,'exit_code':r.returncode});assert r.returncode==0
guard('format-after')
