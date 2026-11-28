export const meta = {
  name: 'phenomena-recheck-final-rules',
  description: '现象清单 29 条逐条拿定稿规则去推（一席只看规则正文和这一条，另一席核它的推导），并各派一席对规则模型里的回放',
  phases: [
    { title: '只用规则推', detail: '每条一席，只读规则正文和这一条现象' },
    { title: '核对推导', detail: '换一席核引用、暗含的假设和结论' },
    { title: '对回放', detail: '每条一席，查模型里对应的回放核的是不是这条现在写的内容' },
  ],
}
const RULE = args.rule
const ITEMS = args.items
if (!Array.isArray(ITEMS) || ITEMS.length !== 29) throw new Error('现象条数不对：' + (ITEMS && ITEMS.length))
const DIR = RULE.replace(/\/[^/]+$/, '')
const ROOT = '（仓库根的绝对路径）'

const D_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['推得出', '对不上', '定不下来'] },
    rule_predicts: { type: 'string', description: '照规则文本推出的结果（和现象可比的那一层），几句话' },
    derivation: { type: 'string', description: '推导的要点：通道和接通先后、次序、组和级别、逐步怎么走，引规则行号' },
    assumptions: { type: 'array', items: { type: 'string' }, description: '用到的、规则文本里没有的假设' },
    gaps: { type: 'array', items: { type: 'object', properties: {
      line: { type: 'string', description: '规则第几行或哪个名词' },
      problem: { type: 'string', description: '缺什么、哪里有两种读法或矛盾' },
      readings: { type: 'string', description: '各种读法各推出什么、哪种和现象一致；不适用就留空' } },
      required: ['line', 'problem', 'readings'] } },
  },
  required: ['verdict', 'rule_predicts', 'derivation', 'assumptions', 'gaps'],
}

const V_SCHEMA = {
  type: 'object',
  properties: {
    final_verdict: { type: 'string', enum: ['推得出', '对不上', '定不下来'] },
    agrees: { type: 'boolean', description: '和上一席的结论是否一致' },
    errors: { type: 'array', items: { type: 'string' }, description: '上一席推导里的错：引错行、漏读、照着现象凑的步骤' },
    text_gaps: { type: 'array', items: { type: 'object', properties: {
      side: { type: 'string', enum: ['规则', '现象'], description: '缺口在规则正文一侧，还是现象没把条件写全' },
      line: { type: 'string' },
      problem: { type: 'string' } },
      required: ['side', 'line', 'problem'] } },
    note: { type: 'string' },
  },
  required: ['final_verdict', 'agrees', 'errors', 'text_gaps', 'note'],
}

const M_SCHEMA = {
  type: 'object',
  properties: {
    有回放吗: { type: 'string', enum: ['有', '部分有', '没有'] },
    回放位置: { type: 'array', items: { type: 'string' } },
    条件一致吗: { type: 'string' },
    结果一致吗: { type: 'string' },
    现象里回放没核到的: { type: 'array', items: { type: 'string' } },
    回放比现象多设的条件: { type: 'array', items: { type: 'string' } },
  },
  required: ['有回放吗', '回放位置', '条件一致吗', '结果一致吗', '现象里回放没核到的', '回放比现象多设的条件'],
}

function dPrompt(it) {
  return [
    'model: astra',
    'effort: high',
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
    '3. 它的结论站不站得住。它说「推得出」的，看有没有哪一步其实推不出、只是照着现象凑的；它说「对不上」「定不下来」的，看是不是漏读了规则里哪一行。',
    '4. 给你自己的结论（推得出 / 对不上 / 定不下来），并列出为了让这一条推得出，缺的或要改的地方；每一处标明是规则正文一侧的，还是现象没把条件写全。',
    '只写结论和依据。',
  ].join('\n')
}

function mPrompt(it) {
  return [
    'model: sol',
    'effort: high',
    'cwd: ' + ROOT,
    '',
    '任务：查一条游戏现象在规则模型里有没有对应的回放，回放核的是不是这条现象现在写的内容。只读，不改仓库里任何文件，不提交。',
    '',
    '- 现象：' + it.file + '（开头是背景，「要推的这一条」是第 ' + it.n + ' 条：' + it.title + '）。这份清单 2026-11-28 改过几处字面（补条件、改错），以这个文件为准。',
    '- 规则模型：' + ROOT + '/规则模型/（Lean 4）。回放在 规则模型/Endfield/回放/ 下，每个文件头写着来源和它核的内容；规则模型/README.md 里有回放表；「现象.lean」集中放了现象清单的不少条，另有按题目单列的文件。整库刚刚编译过，全部回放的断言现在都是通过的，不用再跑。',
    '',
    '要做的：',
    '1. 找出对应这一条的回放（文件名、定义名或行号）。没有就写没有；只核到一部分的写部分有。',
    '2. 对照回放摆的布局、建造先后、工况和现象现在写的条件是否一致；回放断言的结果（数字、先后、周期）和现象写的行为是否一致。',
    '3. 列出：现象里写了、回放没核到的部分；回放为了能跑另外设定、现象里没写的条件。',
    '只写查到的事实，拿不准的写明拿不准在哪。',
  ].join('\n')
}

const results = await parallel(ITEMS.map(it => () => Promise.all([
  agent(dPrompt(it), { label: '推:' + it.n, phase: '只用规则推', schema: D_SCHEMA, agentType: 'gpt' })
    .then(d => {
      if (!d) return { derive: null, verify: null }
      return agent(vPrompt(it, d), { label: '核:' + it.n, phase: '核对推导', schema: V_SCHEMA, model: 'opus' })
        .then(v => ({ derive: d, verify: v }))
    }),
  agent(mPrompt(it), { label: '回放:' + it.n, phase: '对回放', schema: M_SCHEMA, agentType: 'gpt' }),
]).then(([dv, m]) => ({ n: it.n, title: it.title, derive: dv.derive, verify: dv.verify, replay: m }))))

const ok = results.filter(Boolean)
log('完成 ' + ok.length + ' / 29 条')
return { items: ok }
