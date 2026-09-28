#!/usr/bin/env python3
"""腾讯文档「经典文档」（docs.qq.com/doc/…）的 opendoc JSON → Markdown。

用法：ext_classic.py <opendoc.json> <原文URL> <输出.md> [REL] [资源对照.json]
- 正文取 mutations 里 ty=="is" 的字符串；ty=="mp" 是属性（区间 [bi, ei)）。
- 公式是 OMML 结构：\\x16 开始、\\x17 结束（argNum/argDen/argE/argSub/argSup 是参数结束），转成 LaTeX；
  整段只有公式的段落（isOMathPara）输出成 $$ 块。
- 表格：\\x1a 表开始、\\x1b 表结束、\\x07 单元格结束、\\x06 行结束。
- 段落编号按 numbering 定义输出；文字颜色、加粗、斜体、删除线、下划线用 HTML 标签。
- 正文里的 Markdown 特殊字符反斜杠转义，写法和 convert.py 一致。
"""
import json, re, sys, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))
src, url, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
REL = sys.argv[4] if len(sys.argv) > 4 else '../'
assets = json.load(open(sys.argv[5] if len(sys.argv) > 5 else os.path.join(HERE, 'assets.json'), encoding='utf8'))
d = json.load(open(src, encoding='utf8'))
title = d['bodyData'].get('description') or '无标题'
muts = [m for t in d['clientVars']['collab_client_vars']['initialAttributedText']['text']
        for c in t.get('commands', []) for m in c.get('mutations', [])]
s = ''.join(m.get('s', '') for m in muts if m.get('ty') == 'is')
N = len(s)

math, draw, para = {}, {}, {}
fmt = [None] * N          # 每个字符的 (加粗, 斜体, 删除线, 下划线, 颜色)
numbering = {}
styles = {}
for m in muts:
    if m.get('ty') == 'ms' and m.get('mt') == 'numbering':
        numbering = (m.get('pr') or {}).get('numbering') or {}
    if m.get('ty') == 'ms' and m.get('mt') == 'styles':
        styles = (((m.get('pr') or {}).get('styles') or {}).get('style')) or {}
    if m.get('ty') != 'mp':
        continue
    pr = m.get('pr') or {}
    bi, ei = m['bi'], m['ei']
    if 'math' in pr and ei - bi == 1:
        math[bi] = pr['math']
    if 'drawing' in pr:
        u = re.findall(r'https://docimg\d*\.docs\.qq\.com/image/[^"?]+', json.dumps(pr))
        if u:
            draw[bi] = u[0]
    if 'paragraph' in pr:
        para[ei - 1] = pr['paragraph']
    if 'run' in pr:
        r = pr['run']
        val = (lambda rr: (lambda k: (rr.get(k) or {}).get('val')))(r)
        color = val('color')
        color = None if (not color or str(color).lower() in ('000000', 'auto')) else '#' + str(color)
        u = val('u')
        f = (bool(val('b')), bool(val('i')), bool(val('strike')), bool(u and u != 'STUnderline_none'), color)
        for i in range(bi, min(ei, N)):
            fmt[i] = f

NEED = {'f': {'Num', 'Den'}, 'sSub': {'E', 'Sub'}, 'sSup': {'E', 'Sup'},
        'sSubSup': {'E', 'Sub', 'Sup'}, 'nary': {'Sub', 'Sup', 'E'}, 'd': {'E'},
        'rad': {'Deg', 'E'}, 'func': {'FName', 'E'}, 'acc': {'E'}, 'bar': {'E'}}
NARY = {'∑': r'\sum', '∏': r'\prod', '∫': r'\int', '∮': r'\oint', '⋃': r'\bigcup', '⋂': r'\bigcap'}
unknown = collections.Counter()


def render_math(fr):
    a, t, p = fr['args'], fr['type'], fr['pr']
    if t == 'f':
        return r'\frac{%s}{%s}' % (a.get('Num', ''), a.get('Den', ''))
    if t == 'sSub':
        return '{%s}_{%s}' % (a.get('E', ''), a.get('Sub', ''))
    if t == 'sSup':
        return '{%s}^{%s}' % (a.get('E', ''), a.get('Sup', ''))
    if t == 'sSubSup':
        return '{%s}_{%s}^{%s}' % (a.get('E', ''), a.get('Sub', ''), a.get('Sup', ''))
    if t == 'nary':
        np_ = p.get('naryPr') or {}
        ch = ((np_.get('chr') or {}).get('val')) or '∫'
        op = NARY.get(ch, ch)
        loc = ((np_.get('limLoc') or {}).get('val'))
        if loc == 'STLimLoc_undOvr':
            op += r'\limits'       # 上下限在运算符正上方、正下方
        elif loc == 'STLimLoc_subSup':
            op += r'\nolimits'     # 上下限在右侧（$$ 块里默认会放到正下方，要显式写）
        sub, sup = a.get('Sub', ''), a.get('Sup', '')
        return op + (f'_{{{sub}}}' if sub else '') + (f'^{{{sup}}}' if sup else '') + ' ' + a.get('E', '')
    if t == 'd':
        dp = p.get('dPr') or {}
        b = ((dp.get('begChr') or {}).get('val')) or '('
        e = ((dp.get('endChr') or {}).get('val')) or ')'
        escd = lambda c: {'{': r'\{', '}': r'\}', '': '.'}.get(c, c)
        return r'\left%s %s \right%s' % (escd(b), a.get('E', ''), escd(e))
    if t == 'rad':
        return r'\sqrt[%s]{%s}' % (a.get('Deg', ''), a.get('E', '')) if a.get('Deg') else r'\sqrt{%s}' % a.get('E', '')
    unknown[t] += 1
    return ' '.join(a.values())


ESC = re.compile(r'([\\`*_\[\]<>$|~&])')


def esc(text):
    return ESC.sub(r'\\\1', text)


def esc_line_start(line):
    m = re.match(r'^([ \t]+)', line)
    if m:
        line = m.group(1).replace('\t', '　　').replace(' ', ' ') + line[len(m.group(1)):]
    if re.match(r'^\d+[.)]', line):
        return re.sub(r'^(\d+)([.)])', r'\1\\\2', line)
    if re.match(r'^([#>+\-=])', line):
        return '\\' + line
    return line


def wrap(text, f):
    if not f or not text.strip():
        return text
    b, i, st, u, color = f
    if u:
        text = f'<u>{text}</u>'
    if st:
        text = f'<s>{text}</s>'
    if i:
        text = f'<i>{text}</i>'
    if b:
        text = f'<b>{text}</b>'
    if color:
        text = f'<span style="color:{color}">{text}</span>'
    return text


# 编号定义
nums = numbering.get('num') or {}
absn = numbering.get('abstractNum') or {}
counters = collections.Counter()


def number_prefix(numpr):
    nid = ((numpr.get('numId') or {}).get('val'))
    if not nid:
        return ''
    lv = ((numpr.get('ilvl') or {}).get('val')) or 0
    aid = (((nums.get(nid) or {}).get('abstractNumId') or {}).get('val'))
    lvl = (((absn.get(aid) or {}).get('lvl') or {}).get(str(lv))) or {}
    fmt_ = ((lvl.get('numFmt') or {}).get('val')) or 'STNumberFormat_decimal'
    start = ((lvl.get('start') or {}).get('val')) or 1
    counters[(nid, lv)] += 1
    n = start + counters[(nid, lv)] - 1
    if fmt_ == 'STNumberFormat_bullet':
        return '- '
    text = ((lvl.get('lvlText') or {}).get('val')) or '%1.'
    return re.sub(r'%\d', str(n), text) + ' '


state = {'cur': [], 'table': None, 'run_text': [], 'run_fmt': None}
out = []       # 已完成的 Markdown 段落
stack = []     # 公式结构栈


MATH_ESC = {'{': r'\{', '}': r'\}', '%': r'\%', '#': r'\#', '&': r'\&', '$': r'\$', '_': r'\_',
            '^': r'\^{}', '\\': r'\backslash '}


def emit(txt):
    # 两个行内公式紧挨着会拼出 $$，中间补一个空格
    if txt.startswith('$') and not stack:
        tgt = state['table']['cell'] if state['table'] is not None else state['cur']
        if tgt and tgt[-1].endswith('$'):
            txt = ' ' + txt
    if stack:
        stack[-1]['cur'].append(txt)
    elif state['table'] is not None:
        state['table']['cell'].append(txt)
    else:
        state['cur'].append(txt)


def flush_run():
    if state['run_text']:
        emit(wrap(esc(''.join(state['run_text'])), state['run_fmt']))
    state['run_text'], state['run_fmt'] = [], None


def end_paragraph(i):
    """在段落结束符（\\r，位置 i）处收尾当前段落。"""
    pp = para.get(i) or {}
    body = ''.join(state['cur'])
    state['cur'] = []
    if state['table'] is not None:
        state['table']['cell'].append('<br>')
        return
    if not body.strip():
        out.append('')
        return
    if pp.get('isOMathPara'):
        m = re.fullmatch(r'\s*\$(.*)\$\s*', body, flags=re.S)
        if m and '$' not in m.group(1):
            out.append('$$\n' + m.group(1).strip() + '\n$$')
            return
    sid = ((pp.get('pStyle') or {}).get('val'))
    lvl = ((((styles.get(sid) or {}).get('pPr') or {}).get('outlineLvl') or {}).get('val'))
    if isinstance(lvl, int) and 0 <= lvl <= 4 and '\n' not in body:
        plain_body = re.sub(r'</?b>', '', body).strip()   # 标题本身就是粗体，不再套 <b>
        out.append('#' * (lvl + 2) + ' ' + plain_body)
        return
    prefix = number_prefix(pp.get('numPr') or {})
    lines = body.split('\n')
    lines = [x if (k == 0 and prefix) else esc_line_start(x) for k, x in enumerate(lines)]
    out.append(prefix + '\n'.join(lines))


for i, ch in enumerate(s):
    mp = math.get(i)
    if mp is not None and ch in '\x16\x17':
        flush_run()
        t = mp.get('type', '').replace('STOMathType_', '')
        if ch == '\x16':
            stack.append({'type': t, 'args': {}, 'cur': [], 'pr': mp})
            continue
        if t == 'oMath':
            while stack and stack[-1]['type'] != 'oMath':
                fr = stack.pop()
                unknown['unclosed_' + fr['type']] += 1
                emit(''.join(fr['cur']))
            if stack:
                fr = stack.pop()
                emit(f"${''.join(fr['cur']).strip()}$")
                if state.get('math_break'):
                    emit('<br>\n')
                    state['math_break'] = False
            continue
        if t.startswith('arg') and stack:
            fr = stack[-1]
            fr['args'][t[3:]] = ''.join(fr['cur']).strip()
            fr['cur'] = []
            need = NEED.get(fr['type'])
            if need is None or need <= set(fr['args']):
                stack.pop()
                emit(render_math(fr))
            continue
        unknown['end_' + t] += 1
        continue
    if stack:                      # 公式里的字：OMML 里都是字面字符，LaTeX 特殊字符要转义
        if ch == '\x0b':
            state['math_break'] = True
        elif ord(ch) >= 32 or ch == '\t':
            stack[-1]['cur'].append(MATH_ESC.get(ch, ch))
        continue
    if ch == '\x08' and i in draw:
        flush_run()
        k = draw[i]
        local = assets.get(k)
        emit(f'![]({REL}{local})' if local else f'![]({k})')
        continue
    if ch == '\x1a':               # 表开始
        flush_run()
        body = ''.join(state['cur']).strip()
        if body:
            out.append(body)
        state['cur'] = []
        state['table'] = {'rows': [], 'row': [], 'cell': []}
        continue
    if ch in '\x07\x06\x1b' and state['table'] is not None:
        flush_run()
        tb = state['table']
        if ch == '\x07':
            cell = re.sub(r'^(<br>)+|(<br>)+$', '', ''.join(tb['cell']))
            tb['row'].append(re.sub(r'(?<!\\)\|', r'\\|', cell))
            tb['cell'] = []
        elif ch == '\x06':
            tb['rows'].append(tb['row'])
            tb['row'] = []
        else:
            rows = tb['rows'] + ([tb['row']] if tb['row'] else [])
            ncol = max((len(r) for r in rows), default=0)
            if ncol:
                rows = [r + [''] * (ncol - len(r)) for r in rows]
                md = ['| ' + ' | '.join([''] * ncol) + ' |', '|' + ' --- |' * ncol]
                md += ['| ' + ' | '.join(r) + ' |' for r in rows]
                out.append('\n'.join(md))
            state['table'] = None
        continue
    if ch == '\r':
        flush_run()
        end_paragraph(i)
        continue
    if ch == '\x0b':
        flush_run()
        emit('<br>\n')
        continue
    if ord(ch) < 32 and ch != '\t':
        continue
    f = fmt[i]
    if f != state['run_fmt'] and state['run_text']:
        flush_run()
    state['run_fmt'] = f
    state['run_text'].append(ch)
flush_run()
if state['cur']:
    end_paragraph(-1)

body = '\n\n'.join(p for p in out if p.strip()).strip()
head = f'# {esc(title)}\n\n> 原文：{url}（腾讯文档经典文档，公开只读；公式由文档内部结构转成 LaTeX，原始数据在 `原始数据/外链文档/`）\n\n'
open(out_path, 'w', encoding='utf8').write(head + body + '\n')
print(title, len(body), dict(unknown))
