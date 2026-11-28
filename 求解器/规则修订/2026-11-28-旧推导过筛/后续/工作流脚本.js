export const meta = {
  name: 'core-nine-followup',
  description: '骨干九条回来以后的三件事：3 条再修正版从零复核；14 条改过的条文被别的正式条文引用处还成不成立；内带缺口修正版（常数从 921 提到 1002）的逐面计数独立检验和对面积上界的后果',
  phases: [
    { title: '再修正版复核', detail: '3 条各两席（GPT、Claude）' },
    { title: '引用处核对', detail: '改过的条文各一席，逐条看引用它的条文' },
    { title: '内带缺口', detail: '一席独立检验逐面计数，一席算对面积上界的后果' },
  ],
}
// __wf_selfheal_v1: agent() null 自动补发一次(hook 注入)
{ const __wf_orig_agent = agent; agent = async (p, o) => { let r = await __wf_orig_agent(p, o); if (r === null) { const __lb = ((o && o.label) || String(p).slice(0, 40)); try { log('[selfheal] null 补发: ' + __lb); } catch (_e) {} r = await __wf_orig_agent(String(p) + '\n\n[selfheal 补发注记:此前同任务席位已死亡;若其留有部分产物请先检查并接续,不重复已完成部分。]', Object.assign({}, o, { label: __lb + ':retry' })); if (r === null) { try { log('[selfheal] ' + __lb + ' 补发仍死,放弃该路'); } catch (_e) {} } } return r; }; }
// __wf_gptschema_v4: 带 schema 的 gpt/gemini 席位把 schema 写进任务开头的 schema: 行，gpt mod（codex-direct）、gemini mod（agy-direct）读这一行(hook 注入)
{ const __wf_gs_seats = ['gpt', 'gemini']; const __wf_gs_agent = agent; agent = (p, o) => (o && o.schema && __wf_gs_seats.includes(o.agentType)) ? __wf_gs_agent('schema: ' + JSON.stringify(o.schema) + '\n' + String(p), o) : __wf_gs_agent(p, o); }
// __wf_seatguard_v4: 每次 agent() 调用时核对席位：model 含 fable 一律拦；没写 agentType/model 一律拦；agentType 'fork' 算继承主会话，主会话不可派时拦；旧席位名、gpt/gemini 带 model 都拦(hook 注入；静态层在 check_seat_dispatch.py)
{ const __wf_sg_agent = agent; const __wf_sg_inherit_ok = false; const __wf_sg_legacy = {"sol": "sol 是旧席位名，新派请写 agentType:'gpt'，默认就是 sol，不用写参数行", "astra": "astra 是旧席位名，新派请写 agentType:'gpt'，任务开头写参数行 model: astra（一行一个，和正文之间空一行）", "pro": "pro 是旧席位名（现在写成 gpt 加参数行 model: pro），只能用 Agent 派；Workflow 里的 gpt 只能用 sol（默认）或 astra", "agy-carbon": "agy-carbon 是旧席位名，新派请写 agentType:'gemini'，默认就是 antigravity 平台的 carbon，不用写参数行", "agy-neon": "agy-neon 是旧席位名，新派请写 agentType:'gemini'，任务开头写参数行 model: neon（一行一个，和正文之间空一行）", "studio-carbon": "studio-carbon 是旧席位名（现在写成 gemini 加参数行 platform: aistudio），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon", "studio-argon": "studio-argon 是旧席位名（现在写成 gemini 加参数行 platform: aistudio、model: argon），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon", "studio-neon": "studio-neon 是旧席位名（现在写成 gemini 加参数行 platform: aistudio、model: neon），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon", "agy-flash": "agy-flash 是旧席位名，新派请写 agentType:'gemini'，默认就是 antigravity 平台的 carbon，不用写参数行", "agy-argon": "agy-argon 是旧席位名，新派请写 agentType:'gemini'，任务开头写参数行 model: neon（一行一个，和正文之间空一行）", "carbon": "carbon 是旧席位名（现在写成 gemini 加参数行 platform: aistudio），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon", "argon": "argon 是旧席位名（现在写成 gemini 加参数行 platform: aistudio、model: argon），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon", "argon-ultra": "argon-ultra 是旧席位名（现在写成 gemini 加参数行 platform: aistudio、model: argon），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon"}; const __wf_sg_has = (d, k) => Object.prototype.hasOwnProperty.call(d, k); agent = (p, o) => { const __m = (o && o.model != null) ? String(o.model) : ''; const __t = (o && o.agentType != null) ? String(o.agentType) : ''; let __why = ''; if (/fable/i.test(__m)) __why = 'model=' + __m + '：fable 不派席'; else if (__wf_sg_has(__wf_sg_legacy, __t)) __why = __wf_sg_legacy[__t]; else if ((__t === 'gpt' || __t === 'gemini') && __m) __why = __t + ' 席不要写 model 选项（这次是 ' + __m + '）：模型写在任务开头的参数行（如 model: ' + (__t === 'gpt' ? 'astra' : 'neon') + '，和正文之间空一行），外层 model 会让它绕过席位直接按那个模型跑；要 Claude 席就只写 model，不写 agentType'; else if (!__m && !__t) __why = '没写 agentType/model，不写席位一律拦'; else if (!__wf_sg_inherit_ok && __t === 'fork') __why = "agentType:'fork'，会继承主会话模型"; if (__why) { const __lb = (o && o.label) || String(p).slice(0, 40); const __msg = '[seatguard] agent() 席位不合规（' + __lb + '）：' + __why + '。每个 agent() 的选项都要带 agentType（gpt/gemini，模型写在任务开头的参数行）或 model（opus/sonnet）。'; try { log(__msg); } catch (_e) {} throw new Error(__msg); } return __wf_sg_agent(p, o); }; }


const ROOT = '（仓库根的绝对路径）'
const SCR = '（草稿目录）'
const GPT = (model, effort) => 'model: ' + model + '\neffort: ' + effort + '\ncwd: ' + ROOT + '\n\n'

const COMMON = [
  '背景：仓库根 ' + ROOT + ' 是一道游戏《明日方舟：终末地》集成工业的布局优化题（在 70×70 的基地里摆一座工厂，达到产量并让最大空矩形尽量大）。',
  '要用的文件：',
  '- 现行规则正文：仓库根下《明日方舟：终末地》游戏规则.txt；现行题面：求解任务.txt。',
  '- 9 月采纳这些条文时的规则和题面：求解器/规则修订/2026-11-28-旧推导过筛/旧规则-2026-09-26.txt、旧题面-2026-09-26.txt。',
  '- 正式条文：求解约束.txt、求解充分条件.txt（每条两行，首行「条名：正文」，次行缩进「据：所引条名」，所引的是规则里的名词、题面里的行名或别的正式条文）。当时的推导在 候选约束.txt、候选充分条件.txt 和 求解器/候选约束轮次/ 下（按条名找，以状态行写着已采纳或并入该正式条目的版本为准）。',
  '- 规矩：推导与采纳说明.md。必要条件是任何合格布局都必须满足的性质；充分条件是满足了就保证某个结论的条件。',
  '- 规则的可执行模型：规则模型/（Lean 4），规则没写清的地方模型怎样写、哪些在游戏里测过见 规则模型/边界清单.md。规则里各句限制的依据和项目主人确认过的事实：求解器/规则修订/2026-11-26-限制句核对/README.md 第三、四节；涉及规则依据或没测过的事先查它，已有记录的不要再列成疑问。',
  '- 这批条文正在照现行规则重核，材料在 求解器/规则修订/2026-11-28-旧推导过筛/：各条归类.md（88 条的归类：甲 前提都还在；乙 有前提变了但结论仍推得出；丙 结论要改；丁 作废；戊 定不下来）、各席全文.json（过筛两席）、第二轮复核-各条结论.md 和 第二轮复核-各席全文.json（乙类的第二轮复核）、骨干九条/（9 条丙、戊类条文的修正版文稿 条名.md、各条结论.md、各席全文.json、程序）、复算程序/、第二轮复核程序/。',
  '已经定下的处理：「分叉分支」「取货分级」「传输相位」三条作废，不要引用；「来源定序」「准入满额窗口」「封闭植物分区次数界」「轮询均分」「共用接货格余量」「混料轮询分料」和《求解充分条件》里的「单条混料进路逐件判据」「植物专机一一配对满库存不断料」「采种单元的回路存量下界」「采种单元不断料」「专用进路下缓存格不空的传递」「全厂专用进路接法达标」暂缓，也不要引用。',
  '9 月以后的主要变化：规则废除了「阻尼」「层数」；每一步的判定顺序改成 1 汇流器输入、2 元件移动、3 汇流器再输入、4 非运输单位移动、5 结束制造、6 开始制造；轮询、拓扑次序和组的级别、运输带和终点、物品准入口每 5 tick 的上限、无线传输的冷却、桥接器（四个物品格，各连一条边的存货端口和对边的取货端口）等照游戏实测重写。题面：建造方式改为全部单位由蓝图建成（可分多张，单张范围不超过 50×50 格）；调试期一行改写；删去了「操作精度」「判定次序」两行；离线一行写明保留哪些状态。',
  '规矩：只读，不改仓库里任何文件，不提交。自己写的小程序和文稿放在 ' + SCR + '/后续/ 下。只写核实过的；拿不准的单独写明。',
].join('\n')

const R_SCHEMA = {
  type: 'object',
  properties: {
    name: { type: 'string', description: '条名' },
    verdict: { type: 'string', enum: ['未否证', '否证', '修正'] },
    reason: { type: 'string', description: '理由，逐步引规则行或条名' },
    counterexample_or_gap: { type: 'string', description: '反例或推导里缺的一步；没有写无' },
    revised_text: { type: 'string', description: '结论是修正时写出再改过的正文和据行，否则留空' },
    recompute: { type: 'string', description: '数字怎样重算的、结果、程序路径；没有数字写无' },
    unsure: { type: 'string', description: '拿不准的' },
  },
  required: ['name', 'verdict', 'reason', 'counterexample_or_gap', 'revised_text', 'recompute', 'unsure'],
}

const C_SCHEMA = {
  type: 'object',
  properties: {
    条名: { type: 'string' },
    引用处: { type: 'array', items: { type: 'object', properties: {
      引用它的条文: { type: 'string' },
      用到它的哪一部分: { type: 'string' },
      新正文还提供这一部分吗: { type: 'string', enum: ['提供', '只在加了条件时提供', '不提供', '其实没用到'] },
      结论: { type: 'string', enum: ['不受影响', '推导要换依据但结论不变', '条文要改', '定不下来'] },
      说明: { type: 'string', description: '换成什么依据，或要怎样改，或卡在哪' },
    }, required: ['引用它的条文', '用到它的哪一部分', '新正文还提供这一部分吗', '结论', '说明'] } },
    没列在据行里但实际用到它的条文: { type: 'array', items: { type: 'string' } },
    拿不准的: { type: 'string' },
  },
  required: ['条名', '引用处', '没列在据行里但实际用到它的条文', '拿不准的'],
}

const F1_SCHEMA = {
  type: 'object',
  properties: {
    结论: { type: 'string', enum: ['计数成立', '找到反例', '有的步骤没法验'] },
    各类面的清点: { type: 'string', description: '47 种排布逐一生成各类被计的有向格边、两两是否不相交、合计是否等于 273+h；怎样验的' },
    分情形的局部穷举: { type: 'array', items: { type: 'object', properties: {
      情形: { type: 'string' }, 穷举了什么: { type: 'string' }, 结果: { type: 'string' } },
      required: ['情形', '穷举了什么', '结果'] } },
    用到的正式条文是否给出所用的事实: { type: 'string' },
    权重一百一十的复算: { type: 'string' },
    反例或没法验的步骤: { type: 'string', description: '具体坐标和摆法；没有写无' },
    程序路径: { type: 'string' },
    拿不准的: { type: 'string' },
  },
  required: ['结论', '各类面的清点', '分情形的局部穷举', '用到的正式条文是否给出所用的事实', '权重一百一十的复算', '反例或没法验的步骤', '程序路径', '拿不准的'],
}

const F2_SCHEMA = {
  type: 'object',
  properties: {
    占地恒等式照现行规则还成立吗: { type: 'string' },
    新的面积上界: { type: 'string', description: '修正版成立时，最大空矩形面积 A 的上界是多少、在哪种配置取到、每一步的式子' },
    面积预算各句怎样变: { type: 'string' },
    空矩形上界各句怎样变: { type: 'string' },
    增机面积界怎样变: { type: 'string' },
    依赖的别的条文和它们现在的状态: { type: 'string' },
    数字复算: { type: 'string', description: '程序路径和输出' },
    拿不准的: { type: 'string' },
  },
  required: ['占地恒等式照现行规则还成立吗', '新的面积上界', '面积预算各句怎样变', '空矩形上界各句怎样变', '增机面积界怎样变', '依赖的别的条文和它们现在的状态', '数字复算', '拿不准的'],
}

function reviewPrompt(it) {
  return COMMON + '\n\n' + [
    '你的任务：独立复核 ' + it.文件 + ' 的「' + it.条名 + '」的再修正版。',
    '来由：这条 9 月的条文前提变了，一席照现行规则写了修正版（文稿 ' + it.文稿 + '），两席复核里有一席认为还要改、写了下面的再修正版。再修正版照规矩从零起算，需要重新独立复核。',
    '请照现行规则和现行题面，自己从头核：再修正版正文是不是每个合格布局都成立（必要条件），或在它写明的前提下成立；相对第一版修正版改掉的地方改得对不对、有没有丢掉原来成立而且有用的内容、有没有把正文写得比证得出的更强；据行列得对不对；数字自己重算一遍。',
    '核的时候请大概想一下：按现行规则，条文说的这种运行情况大概是怎么来的；它会不会被别的现有约束明显否掉。只要想一想，不要求造出整厂布局。',
    '给出明确结论：未否证（再修正版正文成立）、否证（给出具体反例）、修正（写出再改过的正文和据行）。',
    '',
    '材料（JSON：原条文、再修正版、第一版修正版正文和据行、此前两席复核的全文）：',
    JSON.stringify(it, null, 1),
  ].join('\n')
}

const partA = () => parallel(args.A.map((it) => () =>
  Promise.all([
    agent(GPT('astra', 'high') + reviewPrompt(it), { label: '再修正版·甲：' + it.条名, phase: '再修正版复核', agentType: 'gpt', schema: R_SCHEMA }),
    agent(reviewPrompt(it), { label: '再修正版·乙：' + it.条名, phase: '再修正版复核', model: 'opus', effort: 'high', schema: R_SCHEMA }),
  ]).then(([a, b]) => ({ 条名: it.条名, 甲: a, 乙: b }))
))

const partC = () => parallel(args.C.map((it) => () =>
  agent(GPT('astra', 'high') + COMMON + '\n\n' + [
    '你的任务：' + it.文件 + ' 的「' + it.条名 + '」这次重核以后正文有改动（变弱、变窄、加了前提或换了说法）。下面列出了「据」行引用它的正式条文。请逐条判断这些引用处受不受影响。',
    '对每一条引用它的条文：找到那条条文的推导（候选文件里采纳的版本；归乙的另见过筛和第二轮复核里照现行规则重走的推导；骨干九条另见其文稿），看推导实际用到了「' + it.条名 + '」的哪一部分；新正文还提供不提供这一部分；不提供的话，那条条文的结论还能不能由现行规则、题面或别的可引用条文直接得出，还是条文本身要改。',
    '另外用 grep 查一下有没有条文据行没列、推导里却实际用到「' + it.条名 + '」的。',
    '',
    '材料（JSON：原条文、新正文、引用它的条文及其所在文件和行号）：',
    JSON.stringify(it, null, 1),
  ].join('\n'), { label: '引用处：' + it.条名, phase: '引用处核对', agentType: 'gpt', schema: C_SCHEMA })
    .then((r) => ({ 条名: it.条名, 结果: r }))
))

const F_BASE = [
  '对象：求解约束.txt 的「内带缺口」。9 月的正文是「研磨机 32、塑形机 6、灌装机 3、封装机 3 台、没有协议储存箱时 4(T+F)+2P ≥921」和带 X、Y 的一式。这次一席照现行规则重写了修正版，文稿在 求解器/规则修订/2026-11-28-旧推导过筛/骨干九条/内带缺口.md，程序 内带缺口_复算.py、内带缺口_独核.py、内带缺口_独立复核_格边.py 在同一目录，两席复核的全文在该目录 各席全文.json 的「内带缺口」一项。',
  '修正版正文：T、F、Ω、X₀、Y₀ 取「方向预算」的定义，X₀、Y₀ 对任一题定最大空矩形计算。以左下角为 (0,0)，K 为第 1 列或第 1 行中被供电桩占的格数，交格只数一次。左、下边界唯一未被仓库取货口占的格距 (0,0) 为 d 格，d 为 0 或 69 时 h=9，为 3 或 66 时 h=2，其余 h=0。在仓库同时可接收两种成品的每个可到达循环态中，4(T+F)+K ≥ S+R+273+h+⌈Ω⌉+X₀+Y₀，其中 S、R 见「运输端口收支」，S+R≥619+η（η 见「箱体接口」），K≤2J≤2P（J、P 见「供电下限」）。研磨机 32、塑形机 6、封装机 3、灌装机 3 台时，4(T+F)+K ≥1002+h+η+X₀+Y₀。此配置无协议储存箱时，记 Y=Y₀，X 在右上角格属于制造单位或协议核心时取 X₀+2，其余取 X₀，则 4(T+F)+2J ≥1000+h+X+Y，4(T+F)+2P ≥1002+h。',
  '这比 9 月的常数 921 大了约 80，而「面积预算」「空矩形上界」（最大空矩形面积至多 1110）是由 921 这一式推出的，所以它成立与否直接关系到面积上界，需要单独验。',
].join('\n')

const partF = () => Promise.all([
  agent(GPT('astra', 'xhigh') + COMMON + '\n\n' + F_BASE + '\n\n' + [
    '你的任务：独立检验修正版里这份「逐面计数」。验法要是可检验的：',
    '1. 清点。自己另写程序（不要改用文稿附带的程序，可以事后拿它们对照），照文稿各步的取面规则，对 47 种边带排布逐一生成每一类被计的有向格边（接口面除外的各类：核心 8 面、余格 q 的面、内带朝第 0 列或第 0 行的面、普通矿源各情形取的面、角区取的面等），检查各类两两不相交、每个面只算一次，合计是否等于 273+h。',
    '2. 分情形的局部穷举。文稿对「普通矿源东进运输格」「东进机身」「沿带进间隙格」、角区两种排布、余格 q 等情形各取了一些面，并论证这些面既不是活跃的非运输接口面、也不是被四机型（研磨机、塑形机、封装机、灌装机）存货边记权的面、也不是 X₀ 或 Y₀ 的面、也不和别的源取的面重合。请对每种情形，在足够大的局部窗口里穷举能占到相关格的各种单位（传送带、分流器、汇流器、桥接器、物品准入口、供电桩、九种制造单位的各种朝向、协议储存箱、协议核心、仓库取货口）的种类、位置和朝向，以及最大空矩形 Q 可能的贴靠方式，逐一检查文稿的断言。任何一种不违反现行规则和所引正式条文的摆法下断言不成立，就是反例，写出具体坐标。穷举时用到的「不可能出现」的排除条件要逐条写明出自哪条规则或正式条文。',
    '3. 文稿每一步引的正式条文（边带排布、取货口配置、核心离带、核心邻格、端口对接、矿系不入库、运输端口收支、箱体接口、供电下限、方向预算等）是不是确实给出了它用的那个事实；特别是这些条文自己现在的归类（甲或乙）和乙类在第二轮复核里的结论。',
    '4. 四机型权重合计 109.5、进位 110 自己重算。',
    '结论三选一：计数成立；找到反例；有的步骤没法验（写明哪一步、为什么）。',
  ].join('\n'), { label: '内带缺口：检验逐面计数', phase: '内带缺口', agentType: 'gpt', schema: F1_SCHEMA }),
  agent(GPT('astra', 'high') + COMMON + '\n\n' + F_BASE + '\n\n' + [
    '你的任务：算清楚「如果修正版成立」对面积上界的后果，供决定要花多大力气验它。',
    '1. 「方向预算」推导里的占地恒等式（T、F、A、P、E 之间的关系，9 月推导里是 T+F=1390−A−4P−E 这一类）照现行规则和现行条文是否仍成立，常数自己重算。',
    '2. 把修正版的不等式代进去，照「面积预算」「空矩形上界」「增机面积界」原推导的路子重推：最大空矩形面积 A 的上界变成多少（分九种制造单位恰为机型下限且无箱、有增机、有箱几种情形；P 的下界、J、X、Y、h、矩形尺寸的可行性都照现行条文取），写程序枚举，给出每一步的式子和取到上界的配置。原来「面积 1110 只能是 30×37」「不用桥接器时至多 1040」这些句子各自会怎样变。',
    '3. 列出这条推导链依赖的别的条文和它们现在的状态（甲、乙及第二轮结论、正在重核的）。',
    '这是条件结论：不要判断修正版本身对不对，那由另一席验。',
  ].join('\n'), { label: '内带缺口：对面积上界的后果', phase: '内带缺口', agentType: 'gpt', schema: F2_SCHEMA }),
]).then(([a, b]) => ({ 检验: a, 后果: b }))

const [A, C, Fr] = await Promise.all([partA(), partC(), partF()])
return { 再修正版: A, 引用处: C, 内带缺口: Fr }
