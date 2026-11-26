export const meta = {
  name: 'phenomena-recheck-dry-run',
  description: '现象清单 29 条逐条只用规则文本（带上待改七行）去推，再换一席核对推导，找规则文本缺的和读得岔的地方',
  phases: [
    { title: '只用规则推', detail: '每条现象一席，只读规则文本和这一条现象' },
    { title: '核对推导', detail: '换一席核对引用、暗含的假设和结论' },
  ],
}
// __wf_selfheal_v1: agent() null 自动补发一次(hook 注入)
{ const __wf_orig_agent = agent; agent = async (p, o) => { let r = await __wf_orig_agent(p, o); if (r === null) { const __lb = ((o && o.label) || String(p).slice(0, 40)); try { log('[selfheal] null 补发: ' + __lb); } catch (_e) {} r = await __wf_orig_agent(String(p) + '\n\n[selfheal 补发注记:此前同任务席位已死亡;若其留有部分产物请先检查并接续,不重复已完成部分。]', Object.assign({}, o, { label: __lb + ':retry' })); if (r === null) { try { log('[selfheal] ' + __lb + ' 补发仍死,放弃该路'); } catch (_e) {} } } return r; }; }
// __wf_gptschema_v4: 带 schema 的 gpt/gemini 席位把 schema 写进任务开头的 schema: 行，gpt mod（codex-direct）、gemini mod（agy-direct）读这一行(hook 注入)
{ const __wf_gs_seats = ['gpt', 'gemini']; const __wf_gs_agent = agent; agent = (p, o) => (o && o.schema && __wf_gs_seats.includes(o.agentType)) ? __wf_gs_agent('schema: ' + JSON.stringify(o.schema) + '\n' + String(p), o) : __wf_gs_agent(p, o); }
// __wf_seatguard_v4: 每次 agent() 调用时核对席位：model 含 fable 一律拦；没写 agentType/model 一律拦；agentType 'fork' 算继承主会话，主会话不可派时拦；旧席位名、gpt/gemini 带 model 都拦(hook 注入；静态层在 check_seat_dispatch.py)
{ const __wf_sg_agent = agent; const __wf_sg_inherit_ok = false; const __wf_sg_legacy = {"sol": "sol 是旧席位名，新派请写 agentType:'gpt'，默认就是 sol，不用写参数行", "astra": "astra 是旧席位名，新派请写 agentType:'gpt'，任务开头写参数行 model: astra（一行一个，和正文之间空一行）", "pro": "pro 是旧席位名（现在写成 gpt 加参数行 model: pro），只能用 Agent 派；Workflow 里的 gpt 只能用 sol（默认）或 astra", "agy-carbon": "agy-carbon 是旧席位名，新派请写 agentType:'gemini'，默认就是 antigravity 平台的 carbon，不用写参数行", "agy-neon": "agy-neon 是旧席位名，新派请写 agentType:'gemini'，任务开头写参数行 model: neon（一行一个，和正文之间空一行）", "studio-carbon": "studio-carbon 是旧席位名（现在写成 gemini 加参数行 platform: aistudio），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon", "studio-argon": "studio-argon 是旧席位名（现在写成 gemini 加参数行 platform: aistudio、model: argon），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon", "studio-neon": "studio-neon 是旧席位名（现在写成 gemini 加参数行 platform: aistudio、model: neon），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon", "agy-flash": "agy-flash 是旧席位名，新派请写 agentType:'gemini'，默认就是 antigravity 平台的 carbon，不用写参数行", "agy-argon": "agy-argon 是旧席位名，新派请写 agentType:'gemini'，任务开头写参数行 model: neon（一行一个，和正文之间空一行）", "carbon": "carbon 是旧席位名（现在写成 gemini 加参数行 platform: aistudio），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon", "argon": "argon 是旧席位名（现在写成 gemini 加参数行 platform: aistudio、model: argon），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon", "argon-ultra": "argon-ultra 是旧席位名（现在写成 gemini 加参数行 platform: aistudio、model: argon），只能用 Agent 派；Workflow 里的 gemini 只能用 antigravity 平台的 carbon（默认）或 neon"}; const __wf_sg_has = (d, k) => Object.prototype.hasOwnProperty.call(d, k); agent = (p, o) => { const __m = (o && o.model != null) ? String(o.model) : ''; const __t = (o && o.agentType != null) ? String(o.agentType) : ''; let __why = ''; if (/fable/i.test(__m)) __why = 'model=' + __m + '：fable 不派席'; else if (__wf_sg_has(__wf_sg_legacy, __t)) __why = __wf_sg_legacy[__t]; else if ((__t === 'gpt' || __t === 'gemini') && __m) __why = __t + ' 席不要写 model 选项（这次是 ' + __m + '）：模型写在任务开头的参数行（如 model: ' + (__t === 'gpt' ? 'astra' : 'neon') + '，和正文之间空一行），外层 model 会让它绕过席位直接按那个模型跑；要 Claude 席就只写 model，不写 agentType'; else if (!__m && !__t) __why = '没写 agentType/model，不写席位一律拦'; else if (!__wf_sg_inherit_ok && __t === 'fork') __why = "agentType:'fork'，会继承主会话模型"; if (__why) { const __lb = (o && o.label) || String(p).slice(0, 40); const __msg = '[seatguard] agent() 席位不合规（' + __lb + '）：' + __why + '。每个 agent() 的选项都要带 agentType（gpt/gemini，模型写在任务开头的参数行）或 model（opus/sonnet）。'; try { log(__msg); } catch (_e) {} throw new Error(__msg); } return __wf_sg_agent(p, o); }; }


const RULE = args.rule
const ITEMS = args.items
if (!Array.isArray(ITEMS) || ITEMS.length !== 29) throw new Error('现象条数不对：' + (ITEMS && ITEMS.length))
const DIR = RULE.replace(/\/[^/]+$/, '')

const D_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', description: '推得出 / 对不上 / 定不下来' },
    rule_predicts: { type: 'string', description: '照规则文本推出的结果（和现象可比的那一层），几句话' },
    derivation: { type: 'string', description: '推导的要点：通道和接通先后、次序、组和级别、逐步怎么走，引规则行号' },
    assumptions: { type: 'array', items: { type: 'string' }, description: '用到的、规则文本里没有的假设' },
    gaps: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          line: { type: 'string', description: '规则第几行或哪个名词' },
          problem: { type: 'string', description: '缺什么、哪里有两种读法或矛盾' },
          readings: { type: 'string', description: '各种读法各推出什么、哪种和现象一致；不适用就留空' },
        },
        required: ['line', 'problem', 'readings'],
      },
    },
  },
  required: ['verdict', 'rule_predicts', 'derivation', 'assumptions', 'gaps'],
}

const V_SCHEMA = {
  type: 'object',
  properties: {
    final_verdict: { type: 'string', description: '推得出 / 对不上 / 定不下来' },
    agrees: { type: 'boolean', description: '和上一席的结论是否一致' },
    errors: { type: 'array', items: { type: 'string' }, description: '上一席推导里的错：引错行、漏读、照着现象凑的步骤' },
    text_gaps: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          line: { type: 'string' },
          problem: { type: 'string', description: '规则文本为了让这一条推得出，缺的或要改的地方' },
        },
        required: ['line', 'problem'],
      },
    },
    note: { type: 'string' },
  },
  required: ['final_verdict', 'agrees', 'errors', 'text_gaps', 'note'],
}

function dPrompt(it) {
  return [
    'model: astra',
    'cwd: ' + DIR,
    '',
    '任务：只用一份规则文本，推一条已经在游戏里观察到的现象。只读，不改任何文件。',
    '',
    '材料（只读这两个文件；不读别的任何文件，不搜索项目仓库，不上网，不用自己对这个游戏的了解补）：',
    '- 规则：' + RULE + '（全文 105 行，引用时写行号）',
    '- 现象：' + it.file + '。从开头到「要推的这一条」之前，是这份清单给读者的背景，和规则文本说的是同一个游戏；「要推的这一条」是观察到的规律，当作游戏里确实如此。',
    '',
    '要你做的：',
    '1. 把现象里的布局和建造先后摆出来，照规则文本逐项定出：有哪些通道、各自什么时候接通；哪些是元件、运输带、终点，终点的时刻；各元件的次序；取货通道怎么分组、组的时刻、级别；然后照「判定顺序」一步一步推物品怎么走，推到能和现象里写的结果比为止。现象里有数量关系（比例、周期、步数、几种先后各自的结果）的，要推到数；有多种建造先后的，至少把结果不同的各类各推一种，推得动就全推。',
    '2. 给结论 verdict，三选一：',
    '   - 推得出：规则文本推出的结果和现象一致。',
    '   - 对不上：规则文本推出的结果和现象不同。写出规则推出什么、现象是什么、分歧出在规则哪一行。',
    '   - 定不下来：规则文本缺东西，或某一行有两种读法，结果因此定不下来。写出缺什么、每种读法各推出什么、哪种读法和现象一致。',
    '3. 推的过程中凡是用了规则文本没写的假设（包括从背景那一段借来、规则里没有的话），逐条列进 assumptions。',
    '4. 规则文本里读着有两种读法的句子、互相矛盾的句子，即使不影响这一条的结论，也列进 gaps。',
    '把握不到几乎确定的判断也请写出来，注明是推测。',
  ].join('\n')
}

function vPrompt(it, d) {
  return [
    '请帮忙核对一份推导，只读，不改任何文件。只看下面两个文件和这份推导，不读别的文件，不搜索仓库。',
    '',
    '- 规则：' + RULE + '（全文 105 行）',
    '- 现象：' + it.file + '（开头是背景，「要推的这一条」是在游戏里观察到的规律，当作确实如此）',
    '',
    '另一席只用规则文本去推「要推的这一条」，下面是它交回的结论（JSON）：',
    JSON.stringify(d),
    '',
    '请核对：',
    '1. 它引用的规则行号和原话对不对。',
    '2. 它的每一步有没有用到规则文本里没有的东西，却没列进 assumptions。',
    '3. 它的结论站不站得住。它说「推得出」的，找一找有没有哪一步其实推不出、只是照着现象凑的；它说「对不上」「定不下来」的，看是不是漏读了规则里哪一行。',
    '4. 给你自己的结论（推得出 / 对不上 / 定不下来），并列出规则文本为了让这一条推得出，缺的或要改的地方。',
    '只写结论和依据。',
  ].join('\n')
}

function cut(s, n) { s = String(s || ''); return s.length <= n ? s : s.slice(0, n) + '…' }

const results = await pipeline(
  ITEMS,
  (it) => agent(dPrompt(it), { label: 'derive:' + it.n, phase: '只用规则推', schema: D_SCHEMA, agentType: 'gpt' }),
  (d, it) => {
    if (!d) return { n: it.n, title: it.title, derive: null, verify: null }
    return agent(vPrompt(it, d), { label: 'verify:' + it.n, phase: '核对推导', schema: V_SCHEMA, model: 'opus' })
      .then(v => ({ n: it.n, title: it.title, derive: d, verify: v }))
  },
)

const brief = results.map((r, i) => {
  if (!r) return { n: ITEMS[i].n, failed: true }
  const d = r.derive, v = r.verify
  return {
    n: r.n,
    v1: d ? d.verdict : null,
    v2: v ? v.final_verdict : null,
    agrees: v ? v.agrees : null,
    assumptions: d ? d.assumptions.length : 0,
    gaps: (d ? d.gaps : []).map(g => cut(g.line, 30) + '｜' + cut(g.problem, 160)),
    text_gaps: (v ? v.text_gaps : []).map(g => cut(g.line, 30) + '｜' + cut(g.problem, 160)),
    errors: v ? v.errors.length : 0,
  }
})
return { brief }
