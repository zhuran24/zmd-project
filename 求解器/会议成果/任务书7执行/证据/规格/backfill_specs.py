from pathlib import Path
import json,re,hashlib,difflib
ROOT=Path('/home/zhuran24/zmd-research-fresh'); SPEC=ROOT/'求解器/规格'; OUT=ROOT/'求解器/会议成果/任务书7执行/证据/规格'
NAMES=['运行语义.md','选择点清单.md','选择点参数轴.md','受限模型声明.md','受限转移定义.md','内核输入.md','内核输出.md','内核配置-v1.json','四件前置义务对照.md']
original={n:(SPEC/n).read_text() for n in NAMES}; docs=original.copy()
def sub(n,a,b,required=True):
 if required: assert a in docs[n],(n,a[:100])
 docs[n]=docs[n].replace(a,b)
def section(n,start,end,new):
 a=docs[n].index(start); b=docs[n].index(end,a); docs[n]=docs[n][:a]+new.rstrip()+'\n\n'+docs[n][b:]
def para(n,prefix,new):
 lines=docs[n].splitlines(); hits=[i for i,l in enumerate(lines) if l.startswith(prefix)]; assert len(hits)==1,(n,prefix,hits); lines[hits[0]]=new; docs[n]='\n'.join(lines)+'\n'
def row(n,axis,new): para(n,'| `'+axis+'` |',new)
C=json.loads(docs['内核配置-v1.json']); C['revision']='task7-rule-backfill-2026-09-21'
def cfg(a,**kw): C['axes'][a].update(kw)
def known(a,value,meaning,basis,loss='已定规则范围内无备选；实现及关联推导见受限转移定义',extension='任务8核对实现；规则回填不代表行为已验收'):
 cfg(a,disposition='已定',value=value,meaning=meaning,basis=basis,lifetime='F',coverage_loss=loss,extension_gate=extension)
known('connection.port_meeting','shared_edge_opposite','相邻格共边全长重合、法向相反、存取互补且至少一端运输；角点接触不成通道','规则L12、L16；约束L28、L94、L100、L123；主会话三审-0920.md §6 owner 09-21裁定')
known('polling.both_failure','advance_authorized','仅登记实际尝试后的后效：已取得并实际使用尝试权限的侧，无论成功失败都立即前移；尝试成立与授权侧识别由dual_permission等轴另行推导','规则L29原句“尝试后立刻传给下一条”、L30；v46 S-D05','双端怎样构成一次尝试、授权侧识别、失败空转和同刻推进仍缺任务6推导')
known('transfer.cooldown_scope','box','协议储存箱传输采用箱级5 tick冷却；初始相位单列','规则L25、L36；v46 S-D03；任务书7 §1.1')
known('transfer.partial_acceptance','max_receivable','一次单位判定按各物种现有余量尽量传输；可接部分立即送入，余货留箱','规则L36“能送多少送多少”、L13、L41；主会话三审-0920.md §6','当前Rust传输函数仍为旧实现，任务8须迁移部分接收、残留格与台账')
known('gate.identity_recovery','current_conditions','当前身份相符即解除身份阻断原因；全部原因消失恢复接收资格','规则L16、L22、L64；v46 N-F19','当前Rust身份锁存实现待任务8替换；恢复后的接通记账、轮询和同刻组织仍待任务6')
known('gate.total_recovery','current_conditions','同一门累计数n保持；当前阈值C>n解除累计阻断，C<=n继续阻断','规则L16、L22、L64；v46 N-F19')
known('gate.window_clock','wall_clock','首件开启5 tick窗口；走完清窗口计数并等待下一件重起；全时段累计数保留','规则L64“该5 tick从它收下的第一件物品起算、走完后由下一件物品重新起算”；v46 S-D04')
cfg('gate.identity_subject',meaning='检查当前几何对接的候选来件，阻断状态也须按现值复核恢复资格；具体观察事件待任务6',coverage_loss='当前条件恢复已定；观察、维护与判定的交织尚缺推导',basis='规则L16、L64；v46 N-F19')
cfg('transfer.phase',meaning='每箱输入整数剩余0…5及初态据；无箱且不增箱才可不适用',coverage_loss='非整数残余及未验证初态史；传输相位全取值义务保留',basis='规则L36；约束L3、L8—9')
cfg('transfer.failure_cooldown',disposition='超出覆盖即停',value={'policy':'stop','trigger':'需要确定空箱或零件入库尝试的冷却后效'},meaning='实际送出物品后的箱级5 tick冷却已定；空箱及全拒收零传输的起冷却条件现文未唯一给出，依赖该后效的执行停止',coverage_loss='缺游戏事实：零传输时是否启动冷却；当前Rust仍用every_attempt，任务8须落实停止边界',extension_gate='补足零传输冷却事实或证明具体接法对其全部后效无依赖',basis='规则L36现文、L20、L25；约束L8、L80；任务书7 §0.1')
cfg('gate.counter_edit',meaning='同一准入口只改阈值保持全时段累计数n；执行调试动作尚未实现，遇到动作按工程边界停止',coverage_loss='已定计数保留；改身份、拆建或另行处理历史状态的后效另核；缺任务5/6后置状态推导',extension_gate='任务8实现操作回放，并按任务5/6核全部后置状态',basis='规则L22、L64；任务L12—13；v46 N-F19')
cfg('gate.cancel_limit',meaning='调试期可取消限额或回到不设；操作回放尚未实现，停止属于工具支持范围',coverage_loss='取消许可已定；实际计数、窗口和送达后果须随操作记录核验',basis='任务L12—13；规则L22、L64；v46 N-F19')
cfg('initialization.debug_actions',meaning='任务L12已允许对基地任意操作，包括拆建、增建、清理、手工放料和改设定；工具尚不回放这些动作，按工程边界停止',coverage_loss='动作权限已定；非精确操作程序、实际物品收支和全部调试后置状态待任务5/6',extension_gate='按任务L13表示操作精度；任务8实现动作，依据具体程序核其后效',basis='任务L12“玩家可以做对整个基地做任意操作”、L13；规则L10、L22')
cfg('initialization.belt_shape_lifecycle',meaning='本实验区间保持建成时形状，调试可拆建改形；rotate本身保持相对转角',coverage_loss='其它调试改形动作属任务L12任意操作范围，具体前后几何与库存后效尚未实现',extension_gate='实现对应调试动作后检查完整快照及后置状态',basis='规则L10、L11、L60；任务L8、L12—13')
cfg('initialization.other_inventory',meaning='输入完整StateSeed及出处；任务候选默认关机、送料填满带子和存货格、上游逐批留缓存、末级最后开机，记录该程序的全部可能后态；合成试验单列',coverage_loss='默认程序的后置状态集合及释放过程缺任务5证明；合成种子不替代起法',basis='任务L6、L12—13；主会话三审-0920.md §6；任务书7 §0.1')
cfg('warehouse.periodic_lift',value={'policy':'stop','trigger':'请求生产部分周期与正式基地循环的对应认证'},meaning='生产部分周期须标明接收域；正式循环对应缺任务2替换稿与任务6认证，当前返回unresolved',coverage_loss='旧级二名目撤下；缺成品取空标签、接收边界、拿取收支及循环对应的完整证明',extension_gate='汇入任务2、6经复核的替换稿，再由任务8迁移和复核',basis='任务L2、L8—10、L13；规则L14、L36、L41、L73；主会话三审 §2.4、§6')
# All remaining numeric task references in config are current or changed explicitly above.
docs['内核配置-v1.json']=json.dumps(C,ensure_ascii=False,indent=2)+'\n'
# Axis table: preserve 99 field identities, separate rule facts from execution stops.
A={}
def ar(a,t,life,body):
 A[a]=(t,life,body); row('选择点参数轴.md',a,f'| `{a}` | {t} | {life} | {body} |')
ar('polling.both_failure','T3','F','known：advance_authorized仅登记实际尝试后立即前移，成功与失败相同；双端尝试成立、参与侧及完整推进仍由T3/T1推导。撤销实际尝试后保持原位的取值。据：规则L29—30；v46 S-D05')
ar('connection.port_meeting','T5','F','known：shared_edge_opposite；相邻格共边、相反法向、存取互补且至少一端运输。角点接触不成通道已定。据：规则L12、L16；约束L28；主会话三审 §6 owner 09-21裁定')
ar('transfer.cooldown_scope','T6','F','known：box；一次箱级传输之后5 tick冷却，初始相位另列。据：规则L25、L36；任务书7 §1.1')
ar('transfer.partial_acceptance','T6','F','known：max_receivable；每种物品按仓库可收余量尽量送入，余货保留，部分接收仍是一次单位判定。据：规则L36、L13、L41；主会话三审 §6')
ar('transfer.phase','T6','U','open：服从箱级5 tick冷却的到期时刻/残余量；相位全取值须覆盖，整数化需证明。据：规则L36；约束L3、L8—9')
ar('transfer.failure_cooldown','T6','U','缺游戏事实：空箱或全拒收而零件送入时是否重起冷却。现文L36仍给5 tick，但删除空格也尝试的专句，L20、L25及约束L80不能唯一补出零传输触发条件。依赖此后效时停止，任选分支不构成规则依据。详见T6。据：规则L20、L25、L36；约束L8、L80')
ar('gate.identity_subject','T8','U','open（事件表示）：读取当前几何对接候选来件；条件恢复已定，断边后的观察及同刻维护组织缺任务6推导。据：规则L16、L64；v46 N-F19')
for a in ['gate.identity_recovery','gate.total_recovery','gate.window_clock']:
 v=C['axes'][a]; ar(a,v['choice'],'F','known：'+str(v['value'])+'；'+v['meaning']+'。据：'+v['basis'])
ar('gate.counter_edit','T9','U','known（仅改阈值的规则）：同一准入口保留全时段累计n；改身份、拆建或另行处理历史状态的后效分别核，操作回放仍属工程停止域。据：规则L22、L64；任务L12—13；v46 N-F19')
ar('gate.cancel_limit','T9','U','known（动作许可）：调试期可取消限额/回到未设；具体动作后的计数、窗口及送达状态需表示，当前工具尚未实现。据：任务L12—13；规则L22、L64；v46 N-F19')
ar('initialization.debug_actions','T11','U','known（动作许可）：调试期对基地任意操作，含拆建、增建、清理、手工放料、改设定；具体后效、物品收支和非精确操作程序须表示，工具未实现时报告unsupported。据：任务L12—13；规则L10、L22')
ar('initialization.other_inventory','T11','U','默认起法已定：关机、送料填满带子和存货格、上游每台做一批留缓存、末级最后开；StateSeed承接程序的全部可能后置状态。状态集合与释放后果缺任务5推导；合成试验须单列。据：任务L12—13；主会话三审 §6；任务书7 §0.1')
ar('initialization.belt_shape_lifecycle','T11','U','工程区间选fixed_between_builds；调试期改形动作权限按任务L12，旋转自身保形、拆建可重选三形状。其它操作的库存、几何、接通后效待实现。据：规则L10—11、L60；任务L8、L12—13')
ar('warehouse.periodic_lift','T12','U','obligation：生产部分周期到正式循环的对应由任务2、6证明；接收环境前提为“仓库收得下成品”。旧级二名目撤下，保留成品格标签、接收边界及拿取收支义务。据：任务L2、L8—10、L13；规则L14、L36、L41、L73；主会话三审 §2.4、§6')
# Current text shared by the Input table, synchronized mechanically from axis registry.
for a,(t,l,b) in A.items():
 group='fixed' if l.startswith('F') else ('offline_mutable' if l=='O' else 'fixedness_unproven')
 row('内核输入.md',a,f'| `{a}` | `{group}`；{l} | {t}；{b} |')
for a,v in C['axes'].items():
 value=json.dumps(v['value'],ensure_ascii=False,separators=(',',':'))
 row('受限模型声明.md',a,f"| `{a}` | {v['disposition']} | `{value}`：{v['meaning']} | 据：{v['basis']} | {v['coverage_loss']} | {v['extension_gate']} |")
# Shared current status and explicit provenance boundary.
for n in NAMES:
 if not n.endswith('.md'): continue
 lines=docs[n].splitlines(); lines[2]='日期：2026-09-21。状态：任务书7任务1规则回填；已定规则与工程支持范围分开登记，完整语义与全称认证仍待后续推导、实现和复核。'
 docs[n]='\n'.join(lines)+'\n'
# Clear the superseded geometry alternatives entirely from current choices.
section('选择点清单.md','**相遇谓词轴**','## T6.', '''**相遇谓词已定**：`connection.port_meeting=shared_edge_opposite`。规则L12“每个端口占一格宽”、L16“相遇时将自动形成通道”，结合owner 09-21原话“在只在角上碰一点是不算通道的”（[主会话三审 §6](../会议成果/主会话三审-0920.md)），采用相邻格共边全长重合且法向相反的几何条件，再核存取互补、至少一端运输。只共角点的端口不形成通道，相关接法从输入允许值和覆盖损失中撤去。桥接器先接平局、互依赖及建造史仍按本节分别核验。

`damping.belt_adjacency`只描述“连续传送带”的成段关系，尚须回规则L26推导；它不允许两个只触角点的端口成通道。''')
section('选择点清单.md','## T6.','## T7.', '''## T6. 箱级传输、冷却与相位

**已定**：规则L25把传输判定归于“一个单位”，L36现文为“协议储存箱在供电状态时会一直尝试把自身物品格内的所有物品立刻无线传输到仓库中，能送多少送多少，5 tick 冷却”。因此每次是一箱的一次判定，箱级冷却为5 tick；按每种物品在仓库中的可收余量尽量送入，剩余物品留箱。该规则适用到同一格只送出部分件数；制造缓存的整批通过要求仍由L18独立规定。（据：规则L13、L18、L25、L36、L41、L72；主会话三审 §6；任务书7 §1.1）

**已定范围内的算术**：箱中物种i共B_i件，仓库该物种现有Q_i件且目标格身份已确定，一次可送量为min(B_i,80000−Q_i)；新物种可用新格。实际入库和箱内扣量相同；其它物种容量不足不阻止本物种可收部分。该式确定物种总量，箱内同种跨格的残留分配、仓库匿名格竞争与同刻观察由任务6补完整后态推导。（据：规则L13、L36、L41、L72）

**缺游戏事实：零传输冷却**。L36保留“5 tick 冷却”，现文删除了旧版关于空格也尝试的专句。合用L20“进行中的进度保留”、L25单位判定与约束L80箱界，可以确定已经发生的有货传输采用5 tick冷却；这些文字未说明空箱或全拒收、实际入库0件时是否启动下一段冷却。常态有货且仓库可全收时，两种零传输处理均可满足箱界，故该界不能选出唯一后效。依赖这个后效的轨迹先停止；相位仍按约束L3、L8—9全取值覆盖。此项列入规格回填的for_owner，本席不向owner发问。

**缺推导与复核**：L20停用保留进行中进度，须核冷却是否计入该进度及恢复事件怎样衔接；L36给时长而未给整数相位归约，任务6负责所需时间表示和覆盖证明。当前Rust传输仍为旧整箱接收代码，任务8负责实现部分接收、残留格、零传输停止边界及逐物种台账；装载检查覆盖指纹与输入自洽。

**约束的适用范围**：约束L80在有电、传输开、仓库能接全部物品的循环中给箱内至多18件。这个结论按其前件承接；新部分传输事实继续允许仓库只接一部分的普通过程，相关过程按实际收下量记账。''')
section('选择点清单.md','## T8.','## T10.', '''## T8. 准入口按当前条件阻断与恢复

规则L64“身份不符或任一上限用尽时阻断”对三项使用同一当前条件；L16要求相遇的互补端口自动成通道。几何对接保持时，当前来件身份符合、累计n<C（或累计未设）、当前窗口有余额（或窗口未设），原阻断条件解除，接收资格恢复。只要还有一项条件不满足就继续阻断。资格恢复之后，门格容量、源滞留、端口额度和移动权限共同决定实际收件。（据：规则L16、L22、L23、L29—30、L59、L64；约束L30；v46 N-F19）

正常5 tick窗口从首件开始，走完后由下一件重新起算；仅重置该窗口计数，全时段累计数保留。身份阻断也不改变已经起算的5 tick时长。`gate.window_clock=wall_clock`、`gate.window_recovery=on_expiry_if_other_guards`、身份和累计的`current_conditions`均为已定规则，旧锁存备选撤下。（据：规则L64；v46 S-D04、N-F19）

**缺推导**：断边恢复怎样读取当前候选物品、同刻先后怎样安排、恢复后的接通记录与两侧轮询/上游阻尼怎样更新，由任务6根据L16、L24—25、L28—32、L64补全。恢复资格已由上述合读推出，这些事件表示义务以该结论为前件。工程的快照批维护与逐边维护仍是待核组织方式；每次都须按完整前后图核成员、级排序和指针。当前Rust身份锁存实现待任务8替换。

## T9. 同一准入口改阈值与计数寿命

规则L64区分“全时段的累计收下上限”和“每5 tick”的窗口上限，只有后者写了重起；规则L22“设定”允许改的是阈值C。对同一个准入口只改阈值时，已经收下的历史件数n保持；C>n解除累计耗尽原因，C<=n保持耗尽。正常窗口重起也保留n。把n清零须另有实际动作及其后果，不能算作改阈值的自动副作用。（据：规则L22、L64；v46 N-F19）

任务L12允许调试期任意操作，所以取消限额、回到不设、清理和手工放料均有权限。设定为具体数值时仍取累计1…5000、窗口1…5，操作仍受L13精度限制。动作许可、历史计数和实际送达分别记账；工具未实现取消或改设回放时报告unsupported。

**剩余后效**：改身份、拆建换单位、另行处理历史状态、设限前已有收件怎样计入及当前窗口起点怎样承接，须由具体程序和L64继续核。N-F19已定结论的范围是同一单位仅改阈值；任务5、6负责程序的物品收支、在途残留、后置状态与释放后果。''')
section('选择点清单.md','**双端失败后效轴**','**内部通道与直接接**', '''**实际尝试后前移已定**：`polling.both_failure=advance_authorized`仅登记已经取得并实际使用尝试权限的侧在该次尝试后立刻前移，成功与失败同样处理（规则L29，v46 S-D05）。实际尝试失败还保持原位的备选已撤销。双端怎样组成一次尝试、哪些侧实际授权、对端不许可怎样协调，仍由`polling.dual_permission`与任务6给完整推导；当前both/授权集合A是工程实现。无可移动级时的筛选继续遵守L30，失败空转结束与同刻继续推进仍待T1。''')
section('选择点清单.md','## T11.','## T12.', '''## T11. 调试权限、默认起法及后置状态

任务L12原文：“布局的全部工作可以不用完全依赖蓝图，也可以由玩家可以做部分操作。玩家可以做对整个基地做任意操作”。因此调试期拆除、增建、重建、旋转、清理、手工放料、修改设定均已获准。任务L13“无法精确到某个tick，也无法精确计时”继续限制操作程序；L8规定调试结束后的玩家单位操作停止，成品拿取按L9保留。每项动作应记录条件、实际物品收支、几何/设定/进度后果及结束时的状态集合。工具缺动作编码或回放属于unsupported。（据：任务L8—9、L12—13；规则L10—11、L22）

**默认起法**：先关所有机器，从取货口送料，使带子和存货格填满，再开上游机器，每台做完一批停在缓存，末级最后开。owner 09-21已定采用此起法（主会话三审 §6；任务书7 §0.1）。任务5须推导该程序可能留下的库存分布、缓存与进度、开关、指针和时间状态，以及末级放开后的全过程；总数是否够填不再作为待定许可。合成全空种子仍可用于工程检查，须标明其用途。

**结构和历史**：规则L9蓝图逐个建成、传送带最后；L28初次接通为两端较晚建成时刻；L10重建使通道重新接通。调试动作形成的新布局须重新核占格、供电、完整通道和桥定向，并与建造事件及期间运行衔接。仅旋转自身保留传送带入出边的相对转角，三形状各四朝向；拆建可重选形状。其他改形动作权限归L12，具体事件表示与后果待实现。

**尚缺的后效**：仅“重建”一词没有给自动返仓、销毁或保留库存的规则；依赖这些自动结果的方案仍缺该事实。明确先手工清理再拆建的程序可以把去向写清，当前默认起法不依赖重建自动去向，故本席不把它列为for_owner。仓库初始锚点（任务L6）与默认调试后态分开，建造中取出的植物应记实际收支；默认填满也须由动作程序形成。任务5承接后置状态推导，任务8承接编码和回放。''')
# T12 replace only the superseded acceptance/lift assertions, not task2 proof.
sub('选择点清单.md','零干预例外允许玩家拿取成品','任务L9要求定期拿取一定数量成品，零干预例外允许该动作')
para('选择点清单.md','- **未决**：接收域与拿取环境','- **缺推导**：在“仓库收得下成品”的接收环境中，生产部分周期怎样对应任务L10的基地状态周期，交任务2、6；当前只保留证明义务。拿取量、间隔及与同刻判定的交织须反映真实环境，任务L9未给数值界。已定部分传输按规则L36处理。（据：任务L2、L8—10、L13；主会话三审 §2.4、§6）')
para('选择点清单.md','仓库属于字面完整状态；','仓库属于基地状态（规则L14、任务L10）。每种成品按入库I−厂内取出O−玩家拿取P记净变；最终端口只取原矿时O=0，只有仓库该物种状态复原的周期才令净变=0。生产部分周期、标签非干扰与正式循环对应分别证明。旧“级二提升”不再作为现行认证层级，任务2的有效替换稿尚待汇入；旧整箱容量论证保留于本次变更证据作史料。（据：任务L2、L8—10、L13；规则L14、L36、L41、L73；受限转移§6.5）')
sub('选择点清单.md','本版整箱落格须','一次传输的多物种落格须')
sub('选择点清单.md','级二所需拿取族可实现性、','正式循环所需环境族与',required=False)
# Axis historical independent checklist is explicitly historical; dispositions use current rules.
sub('选择点参数轴.md','素材为[第3轮独立清单]','史料素材为[第3轮独立清单]')
para('选择点参数轴.md','| D11 |','| D11 | T5 connection.port_meeting | 共边相遇已定，角点接触不成通道；据：主会话三审 §6 owner 09-21裁定；规则L12、L16 |')
para('选择点参数轴.md','| F2 |','| F2 | T6 transfer.judgment/cooldown_scope | 单位判定、箱级5 tick冷却已定；据：规则L25、L36；任务书7 §1.1 |')
para('选择点参数轴.md','| F3 |','| F3 | T12 warehouse.capacity；T6 partial_acceptance | 每种单格80000；无线传输按现有余量尽量送，余货留箱；据：规则L13、L36、L41 |')
para('选择点参数轴.md','| I2 |','| I2 | T11 initialization.debug_actions/debug_end | 任务L12任意调试操作已定，含手工放料；非精确操作族及后置状态仍须表示；据：任务L12—13 |')
para('选择点参数轴.md','| K1 |','| K1 | T11 debug_actions/rotation_stage；T7 recipe_selection | 调试任意操作权限已定；设定项、实际动作、状态后效与自动配方匹配分别记账；据：任务L12—13；规则L18、L22 |')
sub('选择点参数轴.md','不授权玩家改物种。','零干预运行中玩家单位操作受任务L8限制；调试动作按任务L12记录实际物品变化。')
sub('内核输入.md','不授权玩家改物种。','零干预运行中玩家单位操作受任务L8限制；调试动作按任务L12记录实际物品变化。')
sub('运行语义.md','abc7a5867f6477eedb619c63a21c4a77144c57ad4567fdcfb696b3049d66a670','31ced2a24fef738c72dfa406351b6bad5df3e353d6b1c2dfd06ab1febaf566ff')
sub('运行语义.md','| `求解任务.txt` | 15 | `10abf80fe6eefe647471eabe78da4053f77b489d3806722c501c6acb405a2864` |','| `求解任务.txt` | 16 | `1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac` |')
sub('运行语义.md','传输冷却状态（按箱一个或按格分别计时待 T6 审查）','箱级5 tick传输冷却状态；零传输触发条件见T6')
sub('运行语义.md','按箱或按格的冷却状态（粒度待 T6 审查）','箱级5 tick冷却状态（零传输触发条件见T6）')
para('运行语义.md','外部通道按所选相遇谓词','外部通道按已定`connection.port_meeting=shared_edge_opposite`形成：相邻格共边全长重合、法向相反、存取互补且至少一端为运输单位。owner 09-21裁定只共角点不成通道（主会话三审 §6），T5只保留桥定向、建造平局与历史核验等后效。制造内部缓存路径另按规则L18表示；计划送料边须经实际通道核验。桥方向须提交建造/接通历史，邻端已知且先接依赖无环时逐步传播，平局与互依赖仍待任务6推导。（据：规则L12、L16、L18、L28、L63；约束L28）')
para('运行语义.md','| 尝试无线传输 |','| 尝试无线传输 | 箱体有电、功能开、箱级冷却就绪；一次单位判定按各物种可收余量尽量送入仓库，余货留箱；有货传输后5 tick冷却 | 空箱及全拒收零传输是否启动冷却缺游戏事实；暂停归属、残留格和同刻事件组织待任务6，代码迁移待任务8。据：规则L20、L25、L36、L41、L72；T6 |')
para('运行语义.md','| 准入口收货 |','| 准入口收货 | 按当前身份、累计n与阈值C、窗口余额判断；所有阻断条件消失恢复接收资格；成功收件更新计数，首件开窗、满5 tick后下一件重起；仅改阈值保留n | 恢复事件、接通记账和同刻维护/轮询衔接待任务6。资格恢复后实际收件仍核容量、滞留和权限。据：规则L16、L22—25、L29—30、L59、L64；v46 N-F19 |')
para('运行语义.md','| 调试动作与结束调试','| 调试动作与结束调试（操作/阶段转移） | 调试期可任意操作，含增建、拆建、清理、手工放料和改设定；操作程序遵守非精确计时；零干预后按任务L8—9只保留成品拿取 | 每项记录实际物品收支、几何/设定/进度后果和全部调试后态；工具未实现时unsupported，任务5、6证明后效。据：任务L8—9、L12—13；规则L10、L22 |')
sub('运行语义.md','窗口边界判定交织、阻断恢复、改设定计数后效见 T8/T9','窗口边界事件及恢复后的轮询后效见T8/T9',required=False)
sub('运行语义.md','失败不免除前移。','成功与失败的实际尝试都立即前移，此项已定（规则L29，v46 S-D05）。')
sub('运行语义.md','调试旋转获准，本版形状变更经重建','调试任意操作获准，本实验形状变更用重建表示')
para('运行语义.md','调试办法产生一组可能后置状态','调试期任意操作已由任务L12授权，含拆建、清理、手工放料和改设定；L13继续要求非精确操作。默认起法为关机、从取货口送料填满带子和存货格、让上游各做一批停在缓存、末级最后开机（任务书7 §0.1、主会话三审 §6）。任务5证明该程序的全部可能后置状态与释放过程。仅改同一准入口阈值时保留全时段累计n，按当前条件恢复接收资格；实际送达及安全库存分布须结合路径证明。零干预后的正流量循环通道继续受约束L62限制。（据：规则L16、L22、L64；任务L12—13；v46 N-F19）')
para('运行语义.md','循环验收分级保存：','当前证书区分生产部分周期与正式基地循环对应义务。任务L2的接收环境前提为“仓库收得下成品”，任务L9给定期拿取，L10给基地状态按周期重复。每种成品按I−O−P记净变；实际交付按入库I计。受限转移§6.1—6.4保留为历史模型证明材料，须按本次传输与门恢复修改复核；§6.5列任务2待汇入的替换义务。旧级二名目撤下，装载通过仅证明对应输入通过校验，完整循环、参数/初态全称认证继续由任务2、6承担。（据：任务L2、L8—10、L13；规则L14、L36、L41、L73；主会话三审 §2.4、§6）')
sub('运行语义.md','原子判定串行，失败判定也须记录轮询后效','原子判定串行，失败判定也须记录轮询后效',required=False)
# Current model statement is a specification target, not evidence that binary implements it.
sub('受限模型声明.md','本版只回答给定完整状态、具体输入历史和逐轴解释下的轨迹。','本配置登记当前规则及受限工程接口。Rust实现尚待任务8同步部分接收和准入口条件恢复；配置被装载不构成这些行为已实现的证据。具体差异见[规格回填](../会议成果/任务书7执行/规格回填.md)。')
sub('受限模型声明.md','**已定**为规则单值','**已定**为所写范围的规则单值（同一行的后效义务仍可未完成）')
para('受限模型声明.md','本版both的合取只限定','本版`both`只限定成功所需的双端许可，是待任务6复核的工程协调。已经发生的尝试无论成败都立即前移属于规则L29已定事实；`polling.both_failure`现只登记这一后效。授权集合A、单侧许可是否构成一次通道尝试、失败空转的结束和同刻继续推进，仍由`dual_permission`、T1及受限转移§3的工程定义承接。最高可移动级筛选始终遵守规则L30。')
para('受限模型声明.md','[受限转移定义](受限转移定义.md)§2–5把','[受限转移定义](受限转移定义.md)§2—5列出工程事件组织与已定规则要求；部分接收、门条件恢复修改后的完整后继仍缺任务6推导与任务8实现。§5保留旧算法的条件证明作史料，当前只核所声明支持域和实际执行范围。')
para('受限模型声明.md','循环分两级：','当前报告生产部分周期及其适用域；生产投影到正式基地循环的对应是独立证明义务，任务2有效替换稿待汇入§6.5。旧级二名目撤下。')
# Transfer definition: do not retain an obsolete implementation as an allowed game choice.
sub('受限转移定义.md','显式选connection.port_meeting=shared_edge_opposite的布局（共边全长重合且法向相反；其它相遇谓词见T5，未选/不支持值返回unsupported）','采用已定connection.port_meeting=shared_edge_opposite的布局（共边全长重合且法向相反；仅角点接触不成通道，见T5）')
sub('受限转移定义.md','它是单段实验域，不能排除真实离线或拿取。','该单段实验域用于诊断；任务L9给定期拿取，完整任务认证须另覆相应环境。')
para('受限转移定义.md','每次访问前刷新本地计时阈值','每次访问前按当前几何对接候选物品、累计数和阈值及窗口余额复核三种阻断原因；当前条件消失即解除对应原因，全部原因解除恢复接收资格。条件事实据规则L16、L22、L64与v46 N-F19。候选物品的观察位置、恢复维护与判定的同刻交织、接通记录及指针映射仍缺任务6完整推导。旧实现只在现存PC读身份、断边后锁存的算法已撤出当前规则口径；任务8须据有效替换稿实现并验证该维护。')
sub('受限转移定义.md','这就是both＋advance_authorized的全部失败后效。','实际尝试后前移这一部分已定；本段用A定义参与侧及尝试成立，是任务6仍须复核的工程协调。')
sub('受限转移定义.md','一般both的其它失败后效仍见T3。','其它双端协调的完整定义继续由T3和任务6承接。')
para('受限转移定义.md','成功收件后同时记两计数','成功收件后同时更新两计数，未开窗时起点=t、window_received=1；累计/窗口用尽及身份不符按当前条件记原因。正常窗口满5 tick只清本窗口计数和该原因，下一件再开窗；同一门只改阈值保持total_received。三种当前原因全部消失时恢复接收资格，仍按源滞留、门格容量及权限决定收件。恢复后的接通记账、前后图映射和观察事件缺任务6推导，下段retain_survivors仅是待核工程组织。（据：规则L16、L22—25、L28—32、L64；v46 N-F19）')
sub('受限转移定义.md','传输的全箱扣减/冷却','传输的实际送出量扣减/箱级冷却')
sub('受限转移定义.md','容量拒收的整箱传输、空箱尝试均不改变仓库及O','实际入库0件的传输保持仓库及O；其冷却后效见T6，')
section('受限转移定义.md','### 4.3 传输模板','## 5.', '''### 4.3 箱体按可收部分传输

有电、传输开关开且箱级冷却就绪时，一次单位判定尽量把箱中物品送入仓库。规则L36现文“能送多少送多少”确定按件部分接收；缓存的整批通过仍只管制造内部路径（L18）。当前Rust仍实现旧整箱接收，以下是任务8须落实的规则要求。

1. 在判前快照按§4.1核仓库身份、空格序及每种物品的目标格。已有同种/历史格时按该格余量，新物种可用空格或新格；一物种在仓库仅一格、每格上限80000（规则L13、L41）。
2. 对箱中每种i统计B_i，目标格现有Q_i，实际送出a_i=min(B_i,80000−Q_i)。分别从箱中扣a_i、仓库加a_i，按a_i记录实际入库；未送部分留箱。某种收不下不阻止另一种的可收部分。
3. 多个新物种竞争被端口指派的无身份空格时，现有空格序只定格序、尚缺物种分配机制，继续报告unsupported(warehouse.empty_slot_identity)。箱内同种分占多个格时，a_i的物种总量已定，具体扣哪些格须补后态定义与复核；规则L72的编号顺序直接规定的是端口收发，任务6须核无线残留分配。已审替换稿到达前，依赖该分配的执行保持unsupported。
4. 实际送出后箱级冷却为5 tick。空箱或全拒收、a_i全0时的冷却触发未由现行文字唯一给出，报告unresolved(transfer.failure_cooldown)，或对具体接法证明所有此类后效均不影响所证结论。此停止是证据范围，不是一次游戏后继。

每次成功部分接收，库存、身份、实际入库账及幸存无身份空格序按§4.1同步提交。物理后态未确定时保留判前状态供诊断；一次单位判定内部不穿插另一箱/通道判定。（据：规则L13、L25、L36、L41、L72；主会话三审 §6）

未指派匿名格的标签对称性仍可作为待复核工具：在无改指派、无释放身份的运行段，没有端口读取这些格标签时，一致更名保持物种计数与容量。该观察须与部分传输后的残留格、身份维护和完整状态联合复核；它不直接提供新转移的唯一后继。''')
# Keep long established engineering derivations readable but explicitly bind them to the old model.
sub('受限转移定义.md','## 5. 同刻闭包、终止和唯一性','## 5. 旧工程闭包的条件证明（史料，2026-09-19）\n\n本节记录旧锁存与整箱接收实现的条件证明。当前规则采用§3.4条件恢复、§4.3部分接收，须重核事件组织、终止性及唯一后继后再用于新模型；本次只完成规则回填。')
sub('受限转移定义.md','## 6. 循环态判等','## 6. 生产周期接口与正式循环对应\n\n§6.1—6.4是2026-09-19旧工程模型的史料证明，依赖的旧传输、门恢复及支持域须按本次回填重核。状态字段表保留作迁移接口；旧证明的通过范围不随源指纹自动转移。§6.5给现行交接义务。')
section('受限转移定义.md','### 6.5 级二提升', '\n__END__' if False else '### 6.5 级二提升', '') if False else None
start=docs['受限转移定义.md'].index('### 6.5 级二提升')
old_lift=docs['受限转移定义.md'][start:]
docs['受限转移定义.md']=docs['受限转移定义.md'][:start]+'''### 6.5 正式循环对应：任务2替换稿接口

现行接收环境前提为：**仓库收得下成品。** 依据任务L2的目标范围、L9定期拿取，以及主会话三审 §2.4、§6。证书写明此环境前提，生产部分周期向任务L10“基地的状态以固定周期重复”的对应仍须证明；本节不把条件句改为数值拿取保证。

规则L36允许部分接收。箱内2件电池、仓库已有79999件时，有1件可送，余下1件留箱；旧“整箱全拒收”的后态已被现行规则取代。这个局部算术说明代码和旧证明要迁移，完整循环仍须逐类检查接收边界。

任务2的有效替换稿须核：最终取货端口只取原矿时，厂内读取成品数量的入口、成品取空后的格标签和空格次序、核心单件入库与箱体部分传输、拒收回堵及恢复状态、生产投影与正式基地周期的对应。每种成品分别记I−O−P=净变；最终口只取矿给O=0，玩家拿取P保留，只有该仓库状态确实复原的周期才令净变=0。（据：规则L13—14、L36、L41、L73；任务L2、L8—10；约束L34、L40）

当前任务2、6替换稿尚未交入本席，`warehouse.periodic_lift`保持unresolved证明义务；旧级二名目撤下。任务8须据复核后的替换稿更新循环键、证书schema/实现及停止项；单次seed装载不承担这些证明。
'''
# Input contract: active content refers to current task lines and permissions.
sub('内核输入.md','尝试传输是单位级判定，冷却粒度另外未定（规则 L25、L36）','尝试传输是单位级判定、箱级5 tick冷却、按可收部分传输（规则L25、L36）')
para('内核输入.md','本版按共享选择点 T5 的受限选值表示相遇：','按T5已定规则表示相遇：两端端口占用相邻格、法向相反并面对同一条格边，一端output、另一端input，且至少一端family为transport，导出PC。`connection.port_meeting=shared_edge_opposite`归fixed/F；仅角点接触不成通道（主会话三审 §6 owner 09-21裁定；规则L12、L16）。几何相遇给可能边，建成与准入口当前阻断状态决定实际可用边；其它端口相遇值按已定轴冲突拒收。')
sub('内核输入.md','无“改写格物种”动作。','调试清理和手工放料可改变格中实际内容，必须记录实际收支和容量检查。')
sub('内核输入.md','可表达不等于已证阶段授权和后效；rotation_stage/rebuild_inventory 等未解时不得执行。','调试阶段的任意操作权限已由任务L12给出；后效不完整或工具未实现时报告unsupported，零干预玩家动作按L8—9限制。')
sub('内核输入.md','action 包括 set_switch','当前已编码的action包括set_switch')
sub('内核输入.md','初始未设不授权调试取消限制。','任务L12允许调试取消限制，具体动作后的计数/窗口状态须保存；当前回放支持范围见§6.1。')
sub('内核输入.md','坐标变更不是任意搬运授权。','rotate自身的坐标变化由旋转定义核验；调试搬运或拆建另记相应动作及快照。')
sub('内核输入.md','任务 L11，零干预后禁止玩家改变据任务 L8','任务 L12，零干预后禁止玩家改变据任务 L8')
sub('内核输入.md','库存后效未定时不能执行重建。','缺库存后效时工具停止回放；明确清理后再拆建的程序仍在调试权限内。')
sub('内核输入.md','其未覆盖方向及新增轴请求见[修改请求](内核输入-对参数轴的修改请求.md)','其它调试操作的后效待实现；[旧修改请求](内核输入-对参数轴的修改请求.md)保留为史料')
sub('内核输入.md','两个每隔5 tick共同到期的空箱可取','史料示例（2026-09-19旧空箱冷却假设，现文缺口见T6）：两个每隔5 tick共同到期的空箱可取')
sub('内核输入.md','[二的幂次到期排序.json]','史料[二的幂次到期排序.json]')
sub('内核输入.md','其合法几何、每5 tick空箱判定历史、非周期证明及无穷时域论证见','该旧示例的几何、每5 tick空箱判定假设、非周期排序计算及无穷时域论证见')
sub('内核输入.md','`warehouse.periodic_lift` 的 stop 只阻断级二提升；级一按受限转移§6准入且用生产抽象执行','`warehouse.periodic_lift`的stop登记正式循环对应尚待证明；生产抽象的旧准入与键见受限转移§6.1—6.4史料，须按现行规则复核后执行')
sub('内核输入.md','有限轨迹与级一生产周期使用 §5.4 的 stop 处置，仍表示级二证明未完成。','有限轨迹与生产部分周期使用§5.4的stop处置，表示正式循环对应证明未完成。')
# Retain field identities and exact known codes without inventing an implemented action schema.
sub('内核输入.md','`fixed` 中的已定编码另包括','`fixed`中的已定编码现另含connection.port_meeting=`shared_edge_opposite`、polling.both_failure=`advance_authorized`（仅实际尝试后前移）、transfer.cooldown_scope=`box`、transfer.partial_acceptance=`max_receivable`、gate.identity_recovery/gate.total_recovery=`current_conditions`、gate.window_clock=`wall_clock`。其它已定编码包括')
para('内核输入.md','policy unresolved 和空 selected_events','policy unresolved和空selected_events表示未提供拿取方案；任务L9仍要求定期拿取。有限无拿取区间可作工程前缀，不能把无限不拿作为现行目标的反证。每种成品库存账为I−O−P，最终厂内口仅取原矿时O=0；只有仓庫状态复原的完整周期才把该净变置0。生产投影与任务L10基地状态周期的对应由任务2/6补证明，接口见受限转移§6.5。（据：任务L2、L8—10、L13；规则L14、L36、L41、L73；约束L34、L40）')
sub('内核输入.md','无动作策略允许 admissibility.specified.value={kind:no_actions}，仅表示本区间没有动作','无动作策略允许 admissibility.specified.value={kind:no_actions}，仅表示本有限区间没有动作')
# Add a concrete extension handoff without claiming engine supports unimplemented payloads.
pos=docs['内核输入.md'].index('### 6.2 零干预期成品拿取')
docs['内核输入.md']=docs['内核输入.md'][:pos]+'''调试的动作权限覆盖增建、拆除、清理、手工放料和改设定；当前v3动作枚举尚未包含每一种动作。此类程序先用带路径/指纹的Markdown或JSON机制证据表示操作对象、非精确触发条件、物品出入、前后快照和全部可能后置状态，经任务5/6推导后由任务8扩展编码。既有解析器遇未实现动作应报告unsupported；本次seed样例不执行调试动作。

默认起法为“关机、填满、开机、末级最后”（任务书7 §0.1、主会话三审 §6），填的是带子和存货格，上游每台完成一批停在缓存；调试后StateSeed须按实际程序生成，有限合成全空样例另标用途。任务5负责该程序留下的状态集合与放开后的过程。

'''+docs['内核输入.md'][pos:]
sub('内核输入.md','| [分流器三路轮询.json]','| 史料[分流器三路轮询.json]')
sub('内核输入.md','| [混做粉碎机两下游.json]','| 史料[混做粉碎机两下游.json]')
sub('内核输入.md','v3可跑：','v3历史工程输入（当前依赖须迁移）：')
sub('内核输入.md','运行例全部赋值，旧轴没有用新字段替代。','历史运行例按当时版本全部赋值；当前运行输入须按现行生命周期和配置迁移。')
sub('内核输入.md','执行入口：','史料执行入口（会写原数据，当前回填不运行；任务8先迁移其依赖）：')
# Outputs: reject obsolete corner choice and account for partial transfers.
sub('内核输出.md','shared_edge_opposite或closed_segment_touch的明确读法；须等于参数点。当前内核只实现前者，后者仅用于表达带该前提的停止/待实现记录。','已定shared_edge_opposite，须等于参数点；角点接触不成通道。旧角点输入只作为非法输入诊断或史料。')
sub('内核输出.md','相遇读法为shared_edge_opposite或closed_segment_touch且须等于参数点','相遇值为已定shared_edge_opposite且须等于参数点')
sub('内核输出.md','成功transfer按本次全箱各物种分别一条','有实际入库的transfer按本次送出各物种分别一条，包含部分接收量')
sub('内核输出.md','若储存箱全箱拒收，任何物种均无入库；不可只核第一个物种。','实际入库0件时无无线入库明细；部分接收时逐物种核实际送出、箱内残留、仓库增量，某种拒收仍允许其它可收物种入库。')
sub('内核输出.md','不把输出验收通过提升为两种相遇读法的共同轨迹。','该史料不参与现行角点规则判断；当前端口相遇按主会话三审 §6已定共边。')
sub('内核输出.md','配置中55本版选值、18停止轴、11已定保持不变；','各处置数量按当前内核配置统计，旧55本版选值、18停止轴、11已定属于2026-09-20史料；')
# Remove obsolete certification names from current contract; legacy JSON level remains a syntax tag.
for n in ['内核输入.md','内核输出.md','选择点参数轴.md','四件前置义务对照.md']:
 docs[n]=docs[n].replace('级二提升','正式循环对应证明').replace('级二','正式循环对应').replace('级一','生产部分')
# Line references: old task had 15 lines; map every explicitly current numeric citation.
# At this point new task references are already current; apply only known original-form fragments.
for a,b in {
 '任务 L15；约束出库上限':'任务 L16；约束出库上限',
 '依据：任务 L14；轴表 judgment.order_scope/order':'依据：任务 L15；轴表 judgment.order_scope/order',
 '任务 L14；约束不得依赖':'任务 L15；约束不得依赖',
 '任务 L8、L11–12；约束端口速率':'任务 L8、L12—13；约束端口速率',
 '任务L12；受限转移§1、§3.2–3.4':'任务L13；受限转移§1、§3.2–3.4',
}.items(): sub('内核输入.md',a,b,required=False)
# Obligations: full rewrite of affected paragraphs, retain unrelated proofs and limitations.
para('四件前置义务对照.md','**未结清**：允许域','**缺推导/复核**：共享端点的建造关系、离线接续、桥定向、级间记忆、双端协调、时间表示与调试后态须按所用认证路线补全。角点接触不成通道、箱级5 tick冷却、部分接收、正常窗口重起、仅改阈值保留累计数及按当前条件解除阻断均已回填；未完成项以这些规则为前件。分叉持续方式按约束L3—10全取值核，具体出口隔带设计是否使阻尼不参与比较由任务6证明。（据：规则L12、L16、L20—32、L36、L64；任务L12—15；主会话三审 §2.2、§6；v46 N-F19）')
para('四件前置义务对照.md','**未结清**：固定判定先后','**缺推导/复核**：规则L29“尝试后立刻传给下一条”已确定成败后都前移，L30确定最高可移动级；双端怎样构成尝试、失败空转何时结束、同刻怎样继续推进仍交任务6。准入口恢复资格已定，观察事件、接通记账、分级/阻尼及指针映射须补后效。传输按可收部分送出已定，箱内残留格、仓库空格竞争和冷却暂停须补完整后态；空箱/全拒收零传输的冷却触发单列为缺游戏事实（T6）。当前Rust与新规格的差异由任务8实现和复核。原受限转移§5、§6.1—6.4保留作旧工程模型史料，须核变更后才可沿用。')
sub('四件前置义务对照.md','初始缓存、调试能做什么、开闸是否提前','初始缓存、任意调试操作实际留下什么、开闸是否提前')
para('四件前置义务对照.md','生产部分生产部分周期','生产部分周期的旧D内字段映射、良定义及率保持见受限转移§6.1—6.4史料；部分接收和条件恢复之后的循环对应须由任务2、6复核。证书接收环境前提为“仓库收得下成品”，每种成品分别记入库、厂内取出和玩家拿取；操作精度仍按任务L13。（据：任务L2、L8—10、L13；规则L14、L36、L41；受限转移§6.5）')
sub('四件前置义务对照.md','按箱/按格相位及关联是否格点化/始终固定','箱级传输相位是否可有限化及其时间关联')
sub('四件前置义务对照.md','不能仅枚举五种整数相位或一个全空初态便宣称穷尽。','默认填满程序的全部可能后态与释放过程由任务5核；合成全空种子仅作工程检查。')
para('四件前置义务对照.md','[选择点参数轴](选择点参数轴.md)提供','[选择点参数轴](选择点参数轴.md)与[受限模型声明](受限模型声明.md)逐轴登记当前99字段的规则事实、输入接口与工程停止边界；规则回填完成后，任务2/5/6的推导、任务8实现及独立复核继续承担完整认证。对于直接证明已经覆盖的义务，可按其范围交付；采用轨迹或状态合并的路线才承担相应转移、时间、有限化及周期对应证明。（据：任务书7 §0.3；任务L2、L10、L12—15；约束L3—10）')
# Cross-file header for rule authority and implementation boundary.
for n in NAMES:
 if not n.endswith('.md'): continue
 marker='\n\n'
 p=docs[n].find(marker,docs[n].find('日期：'))
 note='\n\n本次现行依据为规则`31ced2a24fef`、任务`1630ca1febec`、约束`f6503e6c1568`，完整指纹见[运行语义§1](运行语义.md)。任务现行行号：拿取9、循环10、建造11、调试12、精度13、离线14、判定次序15、位置16。旧轮次报告、KQ编号及历史验证引用均作史料，效力按对应版本和覆盖范围读取。'
 if n=='运行语义.md': note=note.replace('[运行语义§1](运行语义.md)','本文§1')
 docs[n]=docs[n][:p]+note+docs[n][p:]
# Preserve old lifted theorem as a clearly dated small excerpt, not a repo snapshot.
historical='# 旧条款摘录（史料）\n\n截止版本：2026-09-19旧规格；2026-09-21回填时撤出有效正文。来源为受限转移定义.md原§6.5；完整原文件SHA-256见before.json。以下只用于定位旧论证，当前规则依据见规格回填.md。\n\n'+original['受限转移定义.md'][original['受限转移定义.md'].index('### 6.5 级二提升'):]
assert not (OUT/'spec-changes.json').exists(), 'do not overwrite original edit evidence'
changes=[]
for n,new in docs.items():
 p=SPEC/n
 assert p.read_text()==original[n],f'concurrent edit: {p}'
 if new!=original[n]:
  diff=list(difflib.unified_diff(original[n].splitlines(),new.splitlines(),fromfile=str(p)+' before',tofile=str(p)+' after',lineterm='',n=2))
  changes.append({'path':str(p),'before_sha256':hashlib.sha256(original[n].encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest(),'diff':diff})
# All in-memory assertions complete before writes.
for n,new in docs.items(): (SPEC/n).write_text(new)
(OUT/'旧条款摘录.md').write_text(historical)
(OUT/'spec-changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
cat=ROOT/'求解器/数据/正式静态目录.json'; d=json.loads(cat.read_text()); cat_before=cat.read_text()
for u in d['units']:
 if u['id']=='协议储存箱':
  u['transfer']['cooldown_scope']='box'
  u['transfer']['basis']='游戏规则L25、L36；任务书7 §1.1；主会话三审 §6'
  u['transfer']['note']='一次单位判定按仓库可收余量尽量传输，余货留箱；箱级5 tick冷却已定，零传输时的冷却触发见规格T6。'
cat.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
(OUT/'catalog-semantic-changes.json').write_text(json.dumps({'path':str(cat),'diff':list(difflib.unified_diff(cat_before.splitlines(),cat.read_text().splitlines(),lineterm='',n=2))},ensure_ascii=False,indent=2)+'\n')
print('updated',len(changes),'specifications; catalog transfer scope synchronized')
