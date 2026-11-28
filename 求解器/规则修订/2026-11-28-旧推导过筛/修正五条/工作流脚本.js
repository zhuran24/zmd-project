export const meta = {
  name: 'review-five-revised',
  description: '第二轮复核里判为修正的 5 条：改后的正文从零起算，每条由两席各自独立复核（一席 GPT、一席 Claude），给未否证、否证或再修正',
  phases: [
    { title: '复核', detail: '5 条各两席，只读不改' },
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
const GPT = 'model: astra\neffort: high\ncwd: ' + ROOT + '\n\n'

const COMMON = [
  '背景：仓库根 ' + ROOT + ' 是一道游戏《明日方舟：终末地》集成工业的布局优化题（在 70×70 的基地里摆一座工厂，达到产量并让最大空矩形尽量大）。',
  '要用的文件：',
  '- 现行规则正文：仓库根下《明日方舟：终末地》游戏规则.txt；现行题面：求解任务.txt。',
  '- 9 月采纳这些条文时的规则和题面：' + SCR + '/旧规则-2026-09-26.txt、' + SCR + '/旧题面-2026-09-26.txt。',
  '- 正式条文：求解约束.txt、求解充分条件.txt（每条两行，首行「条名：正文」，次行缩进「据：所引条名」，所引的是规则里的名词、题面里的行名或别的正式条文）。当时的推导在 候选约束.txt、候选充分条件.txt 和 求解器/候选约束轮次/ 下。',
  '- 规矩：推导与采纳说明.md。必要条件是任何合格布局都必须满足的性质；充分条件是满足了就保证某个结论的条件。',
  '- 规则的可执行模型：规则模型/（Lean 4），规则没写清的地方模型怎样写、哪些在游戏里测过见 规则模型/边界清单.md。规则里各句限制的依据和项目主人确认过的事实：求解器/规则修订/2026-11-26-限制句核对/README.md 第三、四节；涉及规则依据或没测过的事先查它，已有记录的不要再列成疑问。',
  '- 这批条文刚做过「过筛」和第二轮复核，结果在 求解器/规则修订/2026-11-28-旧推导过筛/（各条归类.md、各席全文.json、第二轮复核-各条结论.md、复算程序/、第二轮复核程序/）。',
  '已经定下的处理：「分叉分支」「取货分级」「传输相位」三条作废，不要引用；「来源定序」「准入满额窗口」「封闭植物分区次数界」「轮询均分」「共用接货格余量」「混料轮询分料」六条暂缓，也不要引用。',
  '9 月以后的主要变化：规则废除了「阻尼」「层数」；每一步的判定顺序改成 1 汇流器输入、2 元件移动、3 汇流器再输入、4 非运输单位移动、5 结束制造、6 开始制造；轮询、拓扑次序和组的级别、运输带和终点、物品准入口每 5 tick 的上限、无线传输的冷却、桥接器（四个物品格）等照游戏实测重写。题面：建造方式改为全部单位由蓝图建成（可分多张，单张范围不超过 50×50 格）；调试期一行改写；删去了「操作精度」一行；离线一行写明保留哪些状态。',
  '规矩：只读，不改仓库里任何文件，不提交。自己写的小程序放在 ' + SCR + '/修正五条/ 下。',
].join('\n')

const R_SCHEMA = {
  type: 'object',
  properties: {
    name: { type: 'string', description: '条名' },
    verdict: { type: 'string', enum: ['未否证', '否证', '修正'] },
    reason: { type: 'string', description: '理由，逐步引规则行或条名' },
    counterexample_or_gap: { type: 'string', description: '反例或推导里缺的一步；没有写无' },
    revised_text: { type: 'string', description: '结论是修正时写出再改过的正文，否则留空' },
    basis_line: { type: 'string', description: '「据：」后面该写什么；和给出的依据行一样就照抄' },
    recompute: { type: 'string', description: '数字怎样重算的、结果、程序路径；没有数字写无' },
    unsure: { type: 'string', description: '拿不准的' },
  },
  required: ['name', 'verdict', 'reason', 'counterexample_or_gap', 'revised_text', 'basis_line', 'recompute', 'unsure'],
}

function prompt(it) {
  return COMMON + '\n\n' + [
    '你的任务：独立复核 ' + it.文件 + ' 的「' + it.条名 + '」的修正版正文。',
    '来由：这条 9 月采纳的条文，推导用到的前提有的变了；过筛认为结论仍推得出，第二轮复核的一席认为字面或推导里有一步要改，写出了下面的修正版。修正版照规矩从零起算，需要重新独立复核。',
    '请照现行规则和现行题面，自己从头核：修正版正文是不是成立（必要条件要对每个合格布局成立；充分条件要在它写明的前提下保证结论）；它相对原条文改掉的地方改得对不对、有没有把原来成立的内容丢掉或把正文写得比证得出的更强；依据行列得对不对；数字自己重算一遍。',
    '核的时候请大概想一下：按现行规则，条文说的这种运行情况大概是怎么来的；它会不会被别的现有约束明显否掉。只要想一想，不要求造出整厂布局。',
    '给出明确结论：未否证（修正版正文成立）、否证（给出具体反例）、修正（写出再改过的正文）。只写核实过的，拿不准的单独写明。',
    '',
    '材料（JSON：原条文、修正版正文和依据行、提出修正的席位的理由和它指出的缺口、过筛两席的记录）：',
    JSON.stringify(it, null, 1),
  ].join('\n')
}

const items = args.items
phase('复核')
const out = await parallel(items.map((it) => () =>
  Promise.all([
    agent(GPT + prompt(it), { label: '复核甲：' + it.条名, phase: '复核', agentType: 'gpt', schema: R_SCHEMA }),
    agent(prompt(it), { label: '复核乙：' + it.条名, phase: '复核', model: 'opus', effort: 'high', schema: R_SCHEMA }),
  ]).then(([a, b]) => ({ 条名: it.条名, 文件: it.文件, 复核甲: a, 复核乙: b }))
))
log('完成 ' + out.filter(Boolean).length + ' / ' + items.length + ' 条')
return { 条目: out.filter(Boolean) }
