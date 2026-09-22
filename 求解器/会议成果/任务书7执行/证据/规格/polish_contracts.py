from pathlib import Path
import json,hashlib,difflib,collections
R=Path('/home/zhuran24/zmd-research-fresh'); S=R/'求解器/规格'; E=R/'求解器/会议成果/任务书7执行/证据/规格'
changes=[]
def edit(name,pairs):
 p=S/name; old=p.read_text(); new=old
 for a,b in pairs:
  if a not in new:
   assert b in new,(name,a[:60]); continue
  new=new.replace(a,b)
 if new!=old:
  p.write_text(new); changes.append({'path':str(p),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest(),'diff':list(difflib.unified_diff(old.splitlines(),new.splitlines(),lineterm='',n=2))})
edit('运行语义.md',[
 ('逐行入口见[规则覆盖表](规则覆盖表.md)','旧逐行入口为史料[规则覆盖表](规则覆盖表.md)，当前行号以本节正式源和任务7回填为准'),
 ('本版扫描、重复归约和唯一后继由[受限转移定义](受限转移定义.md)§2–5给出','旧本版扫描与重复归约见[受限转移定义](受限转移定义.md)§5史料；条件恢复及部分传输后的完整推进由任务6复核'),
 ('### 4.4 第一版的确定转移接口','### 4.4 工程转移接口与迁移义务'),
 ('一般语义仍保留T1–T12、T14–T17；完整输入也可能','本次条件恢复与部分接收修改尚待任务6/8推导、实现和复核；旧唯一后继证明保留为史料。一般语义仍保留T1–T12、T14–T17；完整输入也可能'),
 ])
edit('选择点清单.md',[
 ('故本席不把它列为for_owner','因此该方案可绕开的自动去向不列为本次for_owner'),
 ('此项列入规格回填的for_owner，本席不向owner发问。','此项的原句和推导终点登记在[规格回填](../会议成果/任务书7执行/规格回填.md)的for_owner。'),
 ('也不授权玩家改写格内容。','零干预期玩家单位操作按任务L8限制；调试清理和放料按任务L12记录实际后效。'),
 ('- **待审方向**：“同时可以接受”的逐时刻条件/验收状态条件及环境量词；','- **待证接口**：接收环境写“仓库收得下成品”（任务L2、L9；主会话三审 §2.4、§6）；逐时刻读取与循环验收的对应由任务2推导；'),
 ('**真未定分轴**：`warehouse.acceptance`（路径可接/容量可接/两者）与 `warehouse.acceptance_quantifier`（逐时刻/验收状态条件）分别登记；','**工程接收字段**：`warehouse.acceptance`与`warehouse.acceptance_quantifier`保留实际接收谓词及观察范围的编码接口，任务2须证明其与既定接收环境的对应；'),
 ])
edit('受限转移定义.md',[
 ('其冷却后效见T6，；','其冷却后效见T6；')
 ] if '其冷却后效见T6，；' in (S/'受限转移定义.md').read_text() else [('其冷却后效见T6，','其冷却后效见T6；')])
# Formal source line renumbering inside explicitly historical proofs is accompanied by a mapping note.
edit('受限转移定义.md',[
 ('§6.1—6.4是2026-09-19旧工程模型的史料证明，','§6.1—6.4是2026-09-19旧工程模型的史料证明（其中任务旧L9=现L10、旧L12=现L13、旧L13=现L14、旧L14=现L15；史料的数值引用保留当时行号），'),
 ('反例见§6.5。','原回矿/标签局部例的史料见执行证据/旧条款摘录.md；现行义务见§6.5。'),
 ])
edit('内核输出.md',[
 ('## 1. 运行记录顶层契约（RunRecord）','当前schema仍为kernel-output-v3/kernel-cycle-v2，见[内核输出.schema.json](内核输出.schema.json)。角点枚举已移除；full_base仅保留待迁移的语法标签，语义验收待任务2、6、8。部分接收的逐物种账及门恢复的新增/恢复通道事件须由任务8实现后复核。\n\n## 1. 运行记录顶层契约（RunRecord）'),
 ('成功的生产部分仍只给该三元组的生产证书','成功的生产部分仍只给该三元组的生产证书') if '成功的生产部分仍只给该三元组的生产证书' in (S/'内核输出.md').read_text() else ('达到目标的生产部分仍只给该三元组的生产证书','达到目标的生产部分仍只给该三元组的生产证书'),
 ('身份维护事件`operation=gate_identity_maintenance`','史料接口：身份维护事件`operation=gate_identity_maintenance`'),
 ('若无新增原因或删边，不产生独立事件。','该旧接口只记录删边；当前条件恢复须另表示恢复通道及原因清除，事件身份和schema扩展交任务6/8，缺此扩展的记录仅作旧实现史料。'),
 ])
# Necessary schema synchronization: one enum removal at each occurrence; no structural redesign.
p=S/'内核输出.schema.json'; old=p.read_text(); obj=json.loads(old); spots=[]
def walk(v,path=''):
 if isinstance(v,dict):
  for k,x in v.items():
   if k=='enum' and isinstance(x,list) and 'closed_segment_touch' in x:
    x.remove('closed_segment_touch'); spots.append(path+'/enum')
   else: walk(x,path+'/'+k)
 elif isinstance(v,list):
  for i,x in enumerate(v): walk(x,path+'/'+str(i))
walk(obj); assert len(spots)==5,spots
p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
changes.append({'path':str(p),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'reason':'端口相遇已定；输出schema同时撤销角点枚举。未变schema版本和其它字段。','enum_paths':spots})
(E/'polish-changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
# Correct source-relock report to record original raw-byte digest rather than derived serialization.
p=E/'source-relock.json'; j=json.loads(p.read_text()); baseline=json.loads((E/'before.json').read_text()); j['catalog_before']=next(x['sha256'] for x in baseline['files'] if x['path'].endswith('/数据/正式静态目录.json')); j['note']='catalog_before is original raw-byte SHA-256; catalog_after is initial source relock, final catalog hash is recorded in manifest. task.goal/conditions refreshed from all current task lines.'; p.write_text(json.dumps(j,ensure_ascii=False,indent=2)+'\n')
print('reader review edits',len(changes),'schema enum removals',len(spots)); print('config dispositions',dict(collections.Counter(x['disposition'] for x in json.loads((S/'内核配置-v1.json').read_text())['axes'].values())))
