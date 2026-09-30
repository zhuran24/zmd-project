"""现行规格、配置及样例重锁；历史原字节保持。"""
import json,re,sys
from guard import ROOT,OUT,guard,digest,save

guard('revision-docs-before')
p=ROOT/'规格/内核配置-v2.json';c=json.loads(p.read_text());a=c['axes']
a['warehouse.acceptance']['extension_gate']='核协议核心入库候选、协议储存箱无线传输候选及实际接收的完整区间，见受限转移定义§6.1'
a['power.cell_rule']['basis']='游戏规则L19—L21、L76—L77'
a['initialization.other_inventory']['coverage_loss']='exact_reachable_set_enumerated=false；关闭时不进缓存，任务5准备程序须按现行开工与整批入格条件核后态，串行释放后保留全部相对进度'
a['warehouse.external_supply']['coverage_loss']='sufficient是循环环境选值；逐物种出矿守卫及D.2成品候选在容量读取前按受限转移定义§6.1检查；显式补矿历史仅覆盖声明区间'
a['warehouse.periodic_lift']['extension_gate']='按受限转移定义§6.5核正式循环投影与反向完整周期复原义务'
a['connection.tie']['meaning']='输入通道严格全序；同一步内不同建成引起的通道须按selected_order排序，仅同一次建成引起的通道可任意并列排序'
p.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n')
def edit(rel,fn):
 p=ROOT/rel;p.write_text(fn(p.read_text()))
def cell(v):return str(v).replace('|','&#124;').replace('\n',' ')
for rel in ['规格/受限模型声明.md','规格/选择点参数轴.md']:
 def project(s):
  for k,v in a.items():
   val=json.dumps(v['value'],ensure_ascii=False,separators=(',',':'))
   cols=([f'`{k}`',v['disposition'],f'`{val}`：{v["meaning"]}',f'据：{v["basis"]}；{v["choice"]}；{v["lifetime"]}',v['coverage_loss'],v['extension_gate']] if '受限模型' in rel else [f'`{k}`',v['choice'],v['lifetime'],v['disposition'],f'`{val}`：{v["meaning"]}',f'据：{v["basis"]}'])
   row='| '+' | '.join(map(cell,cols))+' |'
   s,n=re.subn(r'^\| `'+re.escape(k)+r'` \|.*$',lambda _:row,s,flags=re.M);assert n==1,k
  s=re.sub(r'^注册表遗留说明的读法：.*$', '表内未写书名的§6.5指受限转移定义。当前配置元数据与本表逐字段一致；任务编号仅用于定位历史证明材料，其结论仍须核现行前件。',s,flags=re.M)
  s=re.sub(r'^表内meaning及据为配置原文；.*$', '表内meaning及据为配置原文；旧任务编号只定位历史证据，未写书名的§6.5指[受限转移定义](受限转移定义.md)的对应接口。',s,flags=re.M)
  return s
 edit(rel,project)
rule='同一步内不同建成引起的通道必须与 construction.selected_order 的建成次序一致，违反则 invalid_input(connection.tie)；只有同一次建成引起的通道可由 connection.tie 自由排序'
edit('规格/内核输入.md',lambda s:s.replace('相同时刻的通道序用 connection.tie。',rule+'。').replace('装载按（建成接通步、tie序位）求唯一序位。','装载先核同一步内 tie 与逐个建成的先后一致，再按（建成接通步、tie序位）求唯一序位。'))
edit('规格/运行语义.md',lambda s:s.replace('同时刻用 connection.tie 的通道全序。','同时刻用 connection.tie 的通道全序；'+rule+'。'))
edit('规格/选择点参数轴.md',lambda s:s.replace('接通次序由实际建造时刻与 connection.tie 派生','接通次序由实际建造时刻、逐个建成的先后与 connection.tie 派生'))
coverage='''66轴逐项记录disposition、coverage_status、evidence、损失及其他值。exercised 只由下表的逐轴判据产生，证据为对应事件身份；不按族前缀扩散。没有专用判据或未触发的固定/选值轴为 not_exercised；已装载的输入轴及 initialization/connection 轴为 input_checked；停止轴为 stop_not_triggered；warehouse.periodic_lift 为 proof_pending。一次 exercised 不代表该轴全部值或全称覆盖。

| 轴 | 本次执行的取证条件 |
|---|---|
| time.domain、step.order | 判定事件有实际通道移动 |
| component.belt_segment | 实际移动经过至少两格带链的外部入口或出口 |
| polling.initial_cursor | 非运输送货侧以外的普通多通道循环侧，在 last_success 为空时成功；从种子逐移动更新游标 |
| polling.split_merge_start | 分流器送货侧或汇流器收货侧有多条通道，在 last_success 为空时成功 |
| polling.split_merge_singleton | 分流器送货侧或汇流器收货侧仅一条通道且实际移动 |
| manufacturing.recipe_completeness | 记录一次实际开工 |
| transfer.judgment | 记录一次原子传输尝试 |
| transfer.failure_cooldown | 传输事件明确记录 cooldown_restarted=true |
| transfer.partial_acceptance | 同次传输 sent 与 retained 均非空；空箱、全收、全拒均不触发 |
| warehouse.external_supply | 记录实际补给台账行 |
| warehouse.delivery_count | 记录核心或无线实际入库台账行 |

其余轴当前不提交 exercised。特别是 output_blocked、input_mixing、empty_slot_identity、transfer.pause、bridge 与 gate 各轴，不能仅凭普通制造、桥/门通行或传输尝试推得已触发；其运行实现与专用测试仍可独立核验。'''
edit('规格/内核输出.md',lambda s:re.sub(r'^66轴逐项记录.*$',coverage,s,flags=re.M))
edit('内核维护/2026-09-30-步进规则同步/设计.md',lambda s:s.replace('日期 2026-09-30。设计席交给实现席照做的文件。','日期 2026-09-30。状态：步进内核已实现，包含异源审查修订；实施包与验收流程留作设计依据。').replace('缓存格通往存货物品格的闸','存货物品格通往缓存格的闸').replace('同时刻按 `connection.tie` 给的通道全序；','同时刻按 `connection.tie` 给的通道全序（'+rule+'）；').replace('`connection.tie` 不变（通道严格全序，用于同时刻接通）。','`connection.tie` 为通道严格全序；'+rule+'。').replace('单位 id 只含字母数字下划线（`Geometry::build` 已核），不会与 `|` 冲突。','单位 id 只含字母数字下划线（`Geometry::build` 已核）。装载须断言全部元件身份唯一；环与桥轴格式碰撞时返回 invalid_input，要求使用不冲突的单位 id。').replace(next(x for x in s.splitlines() if x.startswith('`uncovered_axes` 按新 66 轴')), '`uncovered_axes` 逐轴按[内核输出](../../规格/内核输出.md)§2的取证表判定，不使用族前缀。有事件但不能区分该轴的，不宣称 exercised；输入、停止及完整周期提升的状态分别为 input_checked、stop_not_triggered、proof_pending。'))
# 输出规格 §2 是否正是覆盖章节，在自审中核对。
edit('数据/样例/历史说明.md',lambda s:s.replace('## 历史清单','旧回归入口 [kernel_regression.py](../工具/kernel_regression.py) 绑定已删除的 --no-cache 参数，停用并保留原字节；当前验证入口见步进样例与 kernel README。\n\n## 历史清单\n\n- [kernel_regression.py](../工具/kernel_regression.py)'))
# 同一身份守卫也用于新输入生成器。
edit('数据/工具/step_inputs.py',lambda s:s.replace("cid=f'C|{u}'+(f'|{a}' if a else '');owner[(u,a)]=cid;comps[cid]=", "cid=f'C|{u}'+(f'|{a}' if a else '')\n                if cid in comps:raise ValueError('元件身份重复: '+cid)\n                owner[(u,a)]=cid;comps[cid]="))
# sent/retained 是物种到件数对象。
edit('crates/kernel/src/output.rs',lambda s:s.replace('transfer["sent"].as_array()', 'transfer["sent"].as_object()').replace('transfer["retained"].as_array()', 'transfer["retained"].as_object()'))
sys.path.insert(0,str(ROOT/'数据/工具'))
from step_inputs import generate
from step_samples import generate_all
outputs=generate_all();base=ROOT/'crates/kernel/tests/fixtures/step/base.json';outputs[base]=generate(base=base.parent)
assert len(outputs)==30
for p,raw in outputs.items():
 assert p.exists(),p
 p.write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n')
save('revision-samples.json',{'config_sha256':digest(ROOT/'规格/内核配置-v2.json'),'catalog_sha256':digest(ROOT/'数据/正式静态目录.json'),'files':{str(p.relative_to(ROOT)):digest(p) for p in outputs}})
guard('revision-docs-after')
print('regenerated',len(outputs),'inputs; config',digest(ROOT/'规格/内核配置-v2.json'))
