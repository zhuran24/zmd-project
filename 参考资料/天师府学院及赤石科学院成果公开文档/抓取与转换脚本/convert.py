#!/usr/bin/env python3
"""把抓下来的腾讯文档（智能文档）块数据转成 Markdown。

用法：convert.py <输出目录> <配置.json>
配置里的 blocks 可以是抓取时的逐页转储目录，也可以是已合并的 原始数据/blocks.json；
assets 是「图片/附件原地址 → 输出目录下相对路径」的对照表（资源对照.json）。
输出：页面/*.md、目录.md、原始数据/blocks.json，以及 report

写法约定（为了在 GitHub 和常见 Markdown 阅读器里都不走样）：
- 正文里的 Markdown 特殊字符一律反斜杠转义（原文的 * 常是乘号）；
- 加粗、斜体、删除线、下划线、行内代码用 HTML 标签，不用 ** 之类的定界符；
- 文字颜色、背景色用 <span style=…>（GitHub 不显示颜色，但源文件里留着）；
- 块内换行用 <br>；子块缩进、分栏、画廊用 HTML 包起来，避免被当成代码块。
"""
import json, glob, re, os, sys, collections, html

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'out')
CFG = json.load(open(sys.argv[2], encoding='utf8')) if len(sys.argv) > 2 else {}
BLOCKS = CFG.get('blocks', os.path.join(HERE, 'blocks'))
TREE = CFG.get('tree', os.path.join(HERE, 'tree.json'))
KEY = CFG.get('key', 'DTmluZ1diWlpQZldw')
SPACE_URL = 'https://docs.qq.com/aio/' + KEY
SPACE_TITLE = CFG.get('title', '天师府学院及赤石科学院成果公开文档')
PAGEDIR = CFG.get('pagedir', '页面')      # 页面文件放在 OUT/PAGEDIR
REL = CFG.get('rel', '../')               # 从页面文件回到 OUT 的相对路径
EXTMAP = CFG.get('extmap', {})           # 外链 URL 关键字 -> 相对 OUT 的本地路径
WRITE_TOC = CFG.get('toc', True)
RAW = CFG.get('raw', '原始数据/blocks.json')
LINK_RE = re.compile(re.escape(KEY) + r'\?p=([A-Za-z0-9]{22})[^#"\s]*(?:#([^"\s)]+))?')

# ---------- 读数据 ----------
B = {}      # id -> block
COLL = {}   # collection id -> collection
VIEW = {}   # view id -> view


def _dumps():
    if BLOCKS.endswith('.json'):   # 已合并的原始数据（原始数据/blocks.json）
        R = json.load(open(BLOCKS, encoding='utf8'))
        yield {f'{ns}:{i}': v for ns in ('block', 'collection', 'collectionview') for i, v in R.get(ns, {}).items()}
        return
    for f in sorted(glob.glob(os.path.join(BLOCKS, '*.json'))):
        yield json.load(open(f, encoding='utf8'))


for dump in _dumps():
    for k, v in dump.items():
        if not isinstance(v, dict):
            continue
        pre, _, i = k.partition(':')
        tgt = {'block': B, 'collection': COLL, 'collectionview': VIEW}.get(pre)
        if tgt is None:
            continue
        old = tgt.get(i)
        if old is None or (v.get('version') or 0) >= (old.get('version') or 0):
            tgt[i] = v
if os.path.exists(TREE):
    tree = json.load(open(TREE, encoding='utf8'))
elif BLOCKS.endswith('.json'):
    tree = json.load(open(BLOCKS, encoding='utf8')).get('tree') or []
else:
    tree = []
assets = {}
ap = CFG.get('assets', os.path.join(HERE, 'assets.json'))
if os.path.exists(ap):
    assets = json.load(open(ap, encoding='utf8'))

report = collections.defaultdict(list)
ANCHORS = set()       # 被链接指向的块：输出时在它前面放 <a id>
CUR = {'page': None}  # 正在输出的页面
RENDERED = set()      # 第一遍里实际输出过的块（页面里已删掉、只剩缓存的旧块不在其中）
LIVE = {'ready': False}

# 腾讯文档的颜色名 → CSS 颜色
COLOR = {'red': '#e53935', 'green': '#2e7d32', 'purple': '#7b1fa2', 'blue': '#1e63d6', 'grey': '#8c8c8c',
         'gray': '#8c8c8c', 'orange': '#ef6c00', 'rose_red': '#d81b60', 'sky_blue': '#0288d1',
         'yellow': '#c9a000', 'default': None}
BG = {'default_background': None, 'light_grey_background': '#eeeeee', 'grey_background': '#dddddd',
      'orange_background': '#ffd8a8', 'light_orange_background': '#ffecd2', 'light_blue_background': '#dcebff',
      'blue_background': '#c5dcff', 'light_yellow_background': '#fff6c4', 'yellow_background': '#ffec8b',
      'red_background': '#ffc9c9', 'light_red_background': '#ffe3e3', 'light_sky_blue_background': '#d7f1ff',
      'sky_blue_background': '#b3e5fc', 'green_background': '#c8f0c8', 'light_green_background': '#e3f7e3',
      'purple_background': '#e6d5f5', 'light_purple_background': '#f1e8fa', 'rose_red_background': '#ffd1e3'}


def css_color(name, table):
    if not name:
        return None
    if isinstance(name, str) and name.startswith('#'):
        return name
    if name in table:
        return table[name]
    report['unknown_color'].append(name)
    return None


def plain(title):
    return ''.join(seg[0] for seg in (title or []) if seg).replace('\r', '')


# ---------- 转义 ----------
ESC = re.compile(r'([\\`*_\[\]<>$|~&])')


def esc(text):
    """正文转义：Markdown 与 HTML 特殊字符前加反斜杠。"""
    return ESC.sub(r'\\\1', text)


def esc_link_text(text):
    """链接文字：本身是网址时少转义（有的渲染器会把网址里的反斜杠原样显示）。"""
    if re.match(r'^\s*https?://\S+\s*$', text):
        return re.sub(r'([\\`*\[\]<>])', r'\\\1', text)
    return esc(text)


LINE_START = re.compile(r'^([#>+\-=]|\d+[.)]\s|\d+[.)]$)')


def esc_line_start(line):
    """行首会被当成标题、引用、列表、分隔线的，转义掉；行首空白换成不会触发代码块的空格。"""
    m = re.match(r'^([ \t]+)', line)
    if m:
        lead = m.group(1).replace('\t', '　　').replace(' ', ' ')
        line = lead + line[len(m.group(1)):]
    if re.match(r'^\d+[.)]', line):
        return re.sub(r'^(\d+)([.)])', r'\1\\\2', line)
    if LINE_START.match(line):
        return '\\' + line
    return line


def html_attr(s):
    return html.escape(s, quote=True)


# ---------- 页面与文件名 ----------
pages = {i: b for i, b in B.items() if b.get('type') == 'page'}


def title_text(title, depth=0):
    """标题的纯文字：页面引用占位符换成被引页面的标题。"""
    out = []
    for seg in title or []:
        if not seg:
            continue
        t = seg[0].replace('\r', '')
        for a in (seg[1] if len(seg) > 1 else []):
            if a[0] == 'bql' and depth < 3:
                t = page_title(a[1][0], depth + 1) or t
            elif a[0] == 'ql' and len(a[1]) > 1:
                t = a[1][1]
            elif a[0] == 'ei':
                t = f'${a[1][0].strip()}$'
        out.append(t)
    return ''.join(out)


def page_title(pid, depth=0):
    b = pages.get(pid)
    if not b:
        return None
    return title_text((b.get('props') or {}).get('title'), depth).strip()


def record_title(b):
    """集合里的记录页：标题在字段里。"""
    coll = COLL.get(b.get('parentId'))
    field = (b.get('props') or {}).get('field') or {}
    if coll:
        for fid, meta in (coll.get('meta') or {}).items():
            if meta.get('title') in ('标题', '名称', 'Title') and fid in field:
                return field_plain(field[fid], meta).strip()
    for fid, fv in field.items():
        t = field_plain(fv, {'type': 1}).strip()
        if t:
            return t
    return ''


def field_plain(fv, meta):
    v = fv.get('value') if isinstance(fv, dict) else fv
    if isinstance(v, list):
        return ''.join(seg.get('text', '') for seg in v if isinstance(seg, dict))
    return '' if v is None else str(v)


def field_md(fv, meta):
    v = fv.get('value') if isinstance(fv, dict) else fv
    ty = meta.get('type')
    if v is None:
        return ''
    if ty == 5:  # 图片
        return ' '.join(img_md(x.get('imageUrl', ''), x.get('title', '')) for x in v)
    if ty in (3, 17):  # 单选/多选
        opts = {o['id']: o['text'] for o in ((meta.get('property') or {}).get('options') or [])}
        vals = v if isinstance(v, list) else [v]
        return '、'.join(esc(opts.get(x, str(x))) for x in vals)
    if ty == 4:  # 日期
        import datetime
        try:
            ts = v if isinstance(v, (int, float)) else (v[0] if isinstance(v, list) else v)
            return datetime.datetime.fromtimestamp(int(ts) / 1000).strftime('%Y-%m-%d')
        except Exception:
            return esc(str(v))
    if isinstance(v, list):
        out = []
        for seg in v:
            if isinstance(seg, dict):
                t = esc(seg.get('text', ''))
                fm = seg.get('format') or {}
                if fm.get('bold'):
                    t = f'<b>{t}</b>'
                if fm.get('italic'):
                    t = f'<i>{t}</i>'
                if fm.get('strikeThrough'):
                    t = f'<s>{t}</s>'
                if fm.get('underline'):
                    t = f'<u>{t}</u>'
                if seg.get('link') or seg.get('url'):
                    t = f"[{t}]({url_href(seg.get('link') or seg.get('url'))})"
                out.append(t)
            else:
                out.append(esc(str(seg)))
        return ''.join(out).replace('\n', '<br>')
    return esc(str(v))


def parent_page(bid):
    """沿 parentId 往上找最近的页面。"""
    seen = set()
    b = B.get(bid)
    while b and b['id'] not in seen:
        seen.add(b['id'])
        pt, pid = b.get('parentTable'), b.get('parentId')
        if pt == 'collection':
            c = COLL.get(pid)
            if not c:
                return None
            pt, pid = c.get('parentTable'), c.get('parentId')
        if pid in pages:
            return pid
        b = B.get(pid)
    return None


SAFE = re.compile(r'[\\/:*?"<>|\r\n\t]')
fname = {}
used = set()
order = [t['id'] for t in tree] + sorted(set(pages) - {t['id'] for t in tree})
for pid in order:
    if pid not in pages:
        continue
    b = pages[pid]
    t = page_title(pid) or ''
    if not t and (b.get('props') or {}).get('field') is not None:
        t = record_title(b)
    t = t or f'无标题-{pid[:6]}'
    base = CFG.get('names', {}).get(pid) or SAFE.sub('_', t).strip(' .')[:80] or pid
    name = base
    k = 2
    while name.lower() in used:
        name = f'{base}-{k}'
        k += 1
    used.add(name.lower())
    fname[pid] = name + '.md'


def page_has_content(pid):
    return bool(pages[pid].get('children'))


def display_title(pid):
    return page_title(pid) or CFG.get('names', {}).get(pid) or fname[pid][:-3]


# ---------- 链接与资源 ----------
def md_href(name):
    for a, b in (('%', '%25'), (' ', '%20'), ('(', '%28'), (')', '%29'), ('#', '%23'), ('<', '%3C'), ('>', '%3E'), ('[', '%5B'), (']', '%5D')):
        name = name.replace(a, b)
    return name


def url_href(url):
    return url.replace(' ', '%20').replace('(', '%28').replace(')', '%29').replace('<', '%3C').replace('>', '%3E')


def asset_key(url):
    return re.sub(r'\?.*$', '', url or '')


def img_md(url, alt=''):
    if not url:
        return ''
    k = asset_key(url)
    local = assets.get(k)
    report['images'].append(k)
    alt = esc((alt or '').replace('\n', ' '))
    return f'![{alt}]({REL}{md_href(local)})' if local else f'![{alt}]({url_href(url)})'


def ext_local(url):
    for k, v in EXTMAP.items():
        if k in url:
            return REL + md_href(v)
    return None


def page_href(pid, anchor=None):
    """页面（和可选的块锚点）→ 本地链接；不是本地页面就返回 None。"""
    if pid not in fname:
        return None
    if anchor:
        if re.fullmatch(r'[A-Za-z0-9]{22}', anchor):
            if anchor in B and (not LIVE['ready'] or anchor in RENDERED):
                real = parent_page(anchor) or pid   # 块可能已被挪到别的页面
                if real in fname:
                    ANCHORS.add(anchor)
                    return f'{md_href(fname[real])}#{anchor}'
            return md_href(fname[pid])
        # 按标题文字的锚点：目标页真有这个标题才保留（放显式 <a id>），否则只链到页面
        from urllib.parse import unquote
        want = unquote(anchor).strip()
        for hb in B.values():
            if hb.get('type', '').startswith('header') and parent_page(hb['id']) == pid \
                    and plain((hb.get('props') or {}).get('title')).strip() == want \
                    and (not LIVE['ready'] or hb['id'] in RENDERED):
                ANCHORS.add(hb['id'])
                return f'{md_href(fname[pid])}#{hb["id"]}'
        return f'{md_href(fname[pid])}#{anchor}'   # 目标页里没有这个标题：照原链接保留片段
    return md_href(fname[pid])


def link_target(url):
    m = LINK_RE.search(url)
    if m:
        h = page_href(m.group(1), m.group(2))
        if h:
            return h
        report['dangling_page_links'].append(m.group(1))
        return url_href(url)
    if url.startswith('#'):
        return url
    return ext_local(url) or url_href(url)


# ---------- 行内 ----------
FMT_KEYS = ('b', 'i', 's', 'u', 'c')


def seg_info(seg):
    """一个富文本片段 → (文字, 格式集合, 颜色, 背景, 链接, 替换内容)。"""
    text = seg[0].replace('\r', '')
    anns = seg[1] if len(seg) > 1 else []
    fmt, color, bg, link, repl = set(), None, None, None, None
    for a in anns:
        kind = a[0]
        arg = a[1] if len(a) > 1 else None
        if kind in FMT_KEYS:
            fmt.add(kind)
        elif kind == 'h':
            color = css_color(arg, COLOR)
        elif kind == 'g':
            bg = css_color(arg, BG)
        elif kind == 't':
            link = arg[0] if isinstance(arg, list) else arg
        elif kind == 'ei':
            latex = arg[0].replace('\r', '').strip()
            # 结尾的「\ 」是控制空格：去掉空格后剩一个反斜杠会吃掉结束的 $，一并去掉
            while latex.endswith('\\') and not latex.endswith('\\\\'):
                latex = latex[:-1].rstrip()
            repl = ('math', latex)
        elif kind == 'ql':
            url, title = arg[0], (arg[1] if len(arg) > 1 else arg[0])
            m = LINK_RE.search(url)
            if m and m.group(2) and m.group(2) in B and text.strip() in ('△', ''):
                sub = title_text((B[m.group(2)].get('props') or {}).get('title')).strip()
                real = parent_page(m.group(2)) or m.group(1)
                if sub:
                    title = sub if real == CUR['page'] else f"{page_title(real) or title}-{sub}"
            repl = ('link', title, link_target(url))
        elif kind == 'bql':
            pid = arg[0]
            if pid in fname:
                repl = ('link', display_title(pid), page_href(pid))
            else:
                report['dangling_page_links'].append(pid)
                repl = ('link', page_title(pid) or text, f'{SPACE_URL}?p={pid}')
        elif kind == 'p':
            url, title = arg[0], (arg[1] if len(arg) > 1 else arg[0])
            repl = ('link', title, link_target(url))
        elif kind == 'r':
            repl = ('text', '@' + (arg[1] if isinstance(arg, list) and len(arg) > 1 else str(arg)))
        elif kind in ('m', 'bh'):
            pass  # 评论锚点
        else:
            report['unknown_inline'].append(kind)
    return text, frozenset(fmt), color, bg, link, repl


def wrap(content, fmt, color, bg):
    if 'c' in fmt:
        content = f'<code>{content}</code>'
    for k, tag in (('u', 'u'), ('s', 's'), ('i', 'i'), ('b', 'b')):
        if k in fmt:
            content = f'<{tag}>{content}</{tag}>'
    style = []
    if color:
        style.append(f'color:{color}')
    if bg:
        style.append(f'background-color:{bg}')
    if style:
        content = f'<span style="{";".join(style)}">{content}</span>'
    return content


def inline(title):
    """富文本 → Markdown 行内。返回的字符串可能含 \\n（原文块内换行），由块级负责断行。"""
    runs = []
    for seg in title or []:
        if not seg:
            continue
        text, fmt, color, bg, link, repl = seg_info(seg)
        key = (fmt, color, bg, link)
        if repl is None and runs and runs[-1][1] is None and runs[-1][0] == key:
            runs[-1][2] += text      # 相邻同格式片段合并（颜色不同时不合并）
        else:
            runs.append([key, repl, text])
    out = []
    for (fmt, color, bg, link), repl, text in runs:
        if repl is None:
            content = esc_link_text(text) if link else esc(text)
        elif repl[0] == 'math':
            content = f'${repl[1]}$' if repl[1] else ''
        elif repl[0] == 'link':
            content = f'[{esc_link_text(repl[1])}]({repl[2]})'
        else:
            content = esc(repl[1])
        if link and repl is None:
            content = f'[{content}]({link_target(link)})'
        if not content.strip():
            out.append(content)
            continue
        # 格式标签不跨行：每行各自包一次
        out.append('\n'.join(wrap(x, fmt, color, bg) if x.strip() else x for x in content.split('\n')))
    return ''.join(out)


def inline_html(title):
    """用在 HTML 块里（折叠块标题）：输出纯 HTML。"""
    out = []
    for seg in title or []:
        if not seg:
            continue
        text, fmt, color, bg, link, repl = seg_info(seg)
        if repl is None:
            c = html.escape(text)
        elif repl[0] == 'math':
            c = html.escape(f'${repl[1]}$')
        elif repl[0] == 'link':
            c = f'<a href="{html_attr(repl[2])}">{html.escape(repl[1])}</a>'
        else:
            c = html.escape(repl[1])
        if link and repl is None:
            c = f'<a href="{html_attr(link_target(link))}">{c}</a>'
        out.append(wrap(c, fmt, color, bg) if c.strip() else c)
    return ''.join(out).replace('\n', '<br>')


def lines_of(md):
    """行内结果按原文换行拆开：每行处理行首，行尾加 <br> 作硬换行。"""
    parts = md.split('\n')
    res = []
    for i, p in enumerate(parts):
        p = esc_line_start(p)
        if i < len(parts) - 1:
            p = p + '<br>'
        res.append(p)
    return res


# ---------- 块 ----------
def kids(b):
    return b.get('children') or []


def get(bid):
    b = B.get(bid)
    if b is None:
        report['missing_blocks'].append(bid)
    return b


LETTERS = 'abcdefghijklmnopqrstuvwxyz'


def render_children(b, ind, ctx, items=None):
    lines = []
    num = 0
    style = None
    prev_type = None
    for cid in (kids(b) if items is None else items):
        c = get(cid)
        if c is None:
            lines += [ind + f'〔缺失的块 {cid}〕', '']
            continue
        t = c.get('type')
        p = c.get('props') or {}
        if t == 'numbered_list':
            if prev_type == 'numbered_list' or (p.get('numberType') == 'continue' and num > 0):
                num += 1     # 接着编号：紧跟上一项，或者明确设了「继续编号」
            else:
                num = 1
                style = None
            if p.get('numberStyle'):
                style = p['numberStyle']
        prev_type = t
        lines += render(c, ind, ctx, num, style)
    return lines


def block_html(open_tag, inner, close_tag, ind):
    """把一段 Markdown 包进 HTML 容器：前后留空行，里面的 Markdown 照常解析。"""
    return [ind + open_tag, ''] + inner + ['', ind + close_tag, '']


def render(b, ind, ctx, num=1, style=None):
    RENDERED.add(b['id'])
    L0 = render_inner(b, ind, ctx, num, style)
    if b['id'] in ANCHOR_TARGETS:
        return [ind + f'<a id="{b["id"]}"></a>', ''] + L0
    return L0


def sub_blocks(b, ind, ctx):
    """普通段落下面挂的子块：原文里是缩进显示。用 div 包住，不用空格缩进（会变成代码块）。"""
    inner = render_children(b, ind, ctx)
    if not inner:
        return []
    return block_html('<div style="margin-left:2em">', inner, '</div>', ind)


def block_bg(p, lines, ind):
    bg = css_color(p.get('blockColor'), BG) if p.get('blockColor') else None
    if not bg or not lines:
        return lines
    return block_html(f'<div style="background-color:{bg}">', lines, '</div>', ind)


def render_inner(b, ind, ctx, num=1, style=None):
    t = b.get('type')
    p = b.get('props') or {}
    title = inline(p.get('title'))
    L = []
    if t == 'text':
        body = [ind + x for x in lines_of(title)] if title.strip() else []
        if body:
            L += block_bg(p, body + [''], ind) if p.get('blockColor') else body + ['']
        L += sub_blocks(b, ind, ctx)
        if not body and not kids(b):
            pass
    elif t in ('header1', 'header2', 'header3', 'header4'):
        lvl = int(t[-1]) + 1
        L += [ind + '#' * min(lvl, 6) + ' ' + title.replace('\n', ' '), '']
        L += render_children(b, ind, ctx)
    elif t in ('bulleted_list', 'numbered_list', 'to_do'):
        if t == 'bulleted_list':
            mark = '- '
        elif t == 'numbered_list':
            mark = f'{num}. ' if style != 'letter' else None
        else:
            mark = '- [x] ' if p.get('checked') else '- [ ] '
        parts = lines_of(title) if title else ['']
        if mark is None:   # 字母编号：Markdown 没有，写成「a. 」开头的段落
            letter = LETTERS[(num - 1) % 26]
            L.append(ind + f'{letter}\\. ' + parts[0])
            L += [ind + x for x in parts[1:]]
            L.append('')
            L += sub_blocks(b, ind, ctx)
            return L
        pad = ' ' * len(mark)
        L.append(ind + mark + parts[0])
        L += [ind + pad + x for x in parts[1:]]
        sub = render_children(b, ind + pad, ctx)
        if sub:
            L += [''] + sub
        L.append('')
    elif t == 'quote':
        inner = ([x for x in lines_of(title)] if title.strip() else []) + ([''] if title.strip() else []) + render_children(b, '', ctx)
        while inner and not inner[-1].strip():
            inner.pop()
        L += [ind + ('> ' + ln if ln.strip() else '>') for ln in inner]
        L.append('')
    elif t == 'callout':
        icon = p.get('pageIcon') or ''
        inner = (lines_of(title) + [''] if title.strip() else []) + render_children(b, '', ctx)
        while inner and not inner[-1].strip():
            inner.pop()
        if icon:
            if inner and inner[0].strip():
                inner[0] = f'{icon} ' + inner[0]
            else:
                inner.insert(0, icon)
        L += [ind + ('> ' + ln if ln.strip() else '>') for ln in inner]
        L.append('')
    elif t == 'toggle':
        L += [ind + '<details>', ind + f'<summary>{inline_html(p.get("title"))}</summary>', '']
        L += render_children(b, ind, ctx)
        L += [ind + '</details>', '']
    elif t == 'code':
        lang = p.get('codeLanguage') or ''
        code = plain(p.get('title'))
        runs = [len(x) for x in re.findall(r'`+', code)]
        fence = '`' * max(3, (max(runs) + 1) if runs else 3)
        L += [ind + fence + lang] + [ind + x for x in code.split('\n')] + [ind + fence, '']
        ctx['code_fences'] = ctx.get('code_fences', 0) + 1
    elif t == 'equation':
        latex = plain(p.get('title')).strip()
        L += [ind + '$$', *[ind + x for x in latex.split('\n')], ind + '$$', '']
    elif t == 'divider':
        L += [ind + '---', '']
    elif t == 'image':
        L += [ind + img_md(p.get('displaySource'), plain(p.get('title'))), '']
        cap = plain(p.get('caption')) if p.get('caption') else ''
        if cap:
            L += [ind + '<i>' + esc(cap) + '</i>', '']
    elif t == 'file':
        name = p.get('fileName') or 'file'
        size = p.get('fileSize')
        local = assets.get('file:' + (p.get('fileObjKey') or ''))
        report['files'].append({'name': name, 'key': p.get('fileObjKey'), 'size': size, 'page': ctx['page']})
        if local:
            L += [ind + f'📎 附件：[{esc(name)}]({REL}{md_href(local)})（{size} 字节）', '']
        else:
            L += [ind + f'📎 附件：{esc(name)}（{size} 字节，未能下载）', '']
    elif t == 'bookmark':
        url = p.get('linkUrl') or p.get('embedUrl') or ''
        name = p.get('linkName') or url
        desc = (p.get('linkDescription') or '').replace('\n', ' ')
        L += [ind + f'🔗 [{esc_link_text(name)}]({link_target(url)})' + (f' — {esc(desc)}' if desc else ''), '']
    elif t == 'page':
        if b['id'] in fname:
            L += [ind + f'📄 [{esc(display_title(b["id"]))}]({page_href(b["id"])})', '']
    elif t == 'column_list':
        L += render_columns([b], ind, ctx)
    elif t == 'column':
        L += render_children(b, ind, ctx)
    elif t == 'simple_table':
        L += render_table(b, ind, ctx)
    elif t == 'collectionview':
        L += render_collection(b, ind, ctx)
    elif t == 'hina_flow_chart':
        local = assets.get('hina:' + (p.get('hinaId') or ''))
        report['flowcharts'].append({'id': b['id'], 'page': ctx['page']})
        if local:
            L += [ind + f'![流程图（截图）]({REL}{md_href(local)})', '']
        else:
            L += [ind + '〔此处原文是一张流程图（腾讯文档插件），未能导出〕', '']
    else:
        report['unknown_block'].append(t)
        if title.strip():
            L += [ind + x for x in lines_of(title)] + ['']
        L += render_children(b, ind, ctx)
    return L


def render_columns(rows, ind, ctx):
    """分栏（column_list）→ HTML 表格：一个 column_list 一行，每栏一格；单栏直接展开。"""
    rows = [r for r in rows if r is not None]
    # 列数不同的行分开成几张表（混在一张表里列宽会互相挤）；单栏的行直接展开
    groups = []
    for r in rows:
        n = len(kids(r))
        if groups and groups[-1][0] == n:
            groups[-1][1].append(r)
        else:
            groups.append((n, [r]))
    if len(groups) > 1:
        out = []
        for n, g in groups:
            out += render_columns(g, ind, ctx)
        return out
    if all(len(kids(r)) <= 1 for r in rows):
        out = []
        for r in rows:
            RENDERED.add(r['id'])
            for cid in kids(r):
                c = get(cid)
                if c is not None:
                    RENDERED.add(c['id'])
                    out += render_children(c, ind, ctx)
        return out
    L = [ind + '<table>', '']
    for r in rows:
        RENDERED.add(r['id'])
        L += [ind + '<tr>', '']
        cols = [get(c) for c in kids(r)]
        for c in cols:
            if c is None:
                continue
            RENDERED.add(c['id'])
            ratio = (c.get('props') or {}).get('columnRatio')
            w = f' width="{round(ratio * 100)}%"' if isinstance(ratio, (int, float)) and 0 < ratio <= 1 else ''
            inner = render_children(c, ind, ctx) if c.get('type') == 'column' else render(c, ind, ctx)
            while inner and not inner[-1].strip():
                inner.pop()
            L += [ind + f'<td valign="top"{w}>', ''] + inner + ['', ind + '</td>', '']
        L += [ind + '</tr>', '']
    L += [ind + '</table>', '']
    return L


def cell_text(cell, ctx):
    lines = render_children(cell, '', ctx)
    txt = '<br>'.join(x.strip() for x in lines if x.strip())
    # 表格里公式、代码中的 | 也会断格，要转义；已转义的不动
    return re.sub(r'(?<!\\)\|', r'\\|', txt)


def render_table(b, ind, ctx):
    p = b.get('props') or {}
    cols = p.get('tableColumnOrder') or []
    rows = []
    for rid in kids(b):
        r = get(rid)
        if r is None or r.get('type') != 'simple_table_row':
            if r is not None:
                report['table_non_row'].append(rid)
            continue
        RENDERED.add(r['id'])
        byk = {}
        order_k = []
        for cid in kids(r):
            c = get(cid)
            if c is None:
                continue
            RENDERED.add(c['id'])
            k = (c.get('props') or {}).get('columnKey')
            order_k.append(k)
            byk[k] = cell_text(c, ctx)
        keys = cols or order_k
        rows.append([byk.get(k, '') for k in keys])
    if not rows:
        return []
    n = max(len(r) for r in rows)
    rows = [r + [''] * (n - len(r)) for r in rows]
    if p.get('tableRowHeader'):
        head, body = rows[0], rows[1:]
    else:
        head, body = [''] * n, rows   # 原表没有表头：用空表头，所有行都是数据行
    L = [ind + '| ' + ' | '.join(head) + ' |', ind + '|' + ' --- |' * n]
    L += [ind + '| ' + ' | '.join(r) + ' |' for r in body]
    return L + ['']


def render_collection(b, ind, ctx):
    p = b.get('props') or {}
    coll = COLL.get(p.get('collectionId'))
    if not coll:
        report['missing_collections'].append(p.get('collectionId'))
        return [ind + '〔缺失的数据表〕', '']
    meta = coll.get('meta') or {}
    L = []
    for vid in p.get('viewIds') or []:
        v = VIEW.get(vid)
        if not v:
            report['missing_views'].append(vid)
            continue
        vp = (v.get('props') or {})
        dt = vp.get('datatable') or {}
        prop = dt.get('property') or {}
        fids = [f for f in (prop.get('fieldIds') or list(meta)) if f in meta]
        rids = prop.get('recordIds') or kids(v)
        vtitle = dt.get('title') or v.get('type') or ''
        items = [get(r) for r in rids]
        if not fids or any(x is not None and x.get('type') != 'page' for x in items):
            # 画廊：条目是普通内容块（多为一排并列的图片），一个条目一行
            rows = [x for x in items if x is not None and x.get('type') == 'column_list']
            others = [x for x in items if x is not None and x.get('type') != 'column_list']
            if rows:
                L += render_columns(rows, ind, ctx)
            for x in others:
                L += render(x, ind, ctx)
            break
        L.append(ind + f'<b>数据表视图：{esc(vtitle)}</b>')
        L.append('')
        L.append(ind + '| ' + ' | '.join(esc(meta[f].get('title', f)) for f in fids) + ' |')
        L.append(ind + '|' + ' --- |' * len(fids))
        for rid in rids:
            r = get(rid)
            if r is None:
                continue
            RENDERED.add(r['id'])
            field = (r.get('props') or {}).get('field') or {}
            cells = []
            for j, f in enumerate(fids):
                txt = field_md(field.get(f, {}), meta[f]) if f in field else ''
                if j == 0 and rid in fname and page_has_content(rid):
                    txt = f'[{txt or esc(display_title(rid))}]({page_href(rid)})'
                cells.append(re.sub(r'(?<!\\)\|', r'\\|', txt.replace('\n', '<br>')))
            L.append(ind + '| ' + ' | '.join(cells) + ' |')
        L.append('')
        break  # 同一数据表的多个视图内容相同，只出第一个
    return L


def squeeze(lines):
    """合并多余空行，但不动代码块里面。"""
    out = []
    fence = None
    blank = 0
    for ln in lines:
        s = ln.strip()
        if fence:
            out.append(ln)
            if s.startswith(fence) and s.strip('`') == '':
                fence = None
            continue
        m = re.match(r'^(`{3,})', s)
        if m:
            fence = m.group(1)
            blank = 0
            out.append(ln)
            continue
        if not s:
            blank += 1
            if blank > 1:
                continue
            out.append('')
            continue
        blank = 0
        out.append(ln)
    while out and not out[-1].strip():
        out.pop()
    return '\n'.join(out) + '\n'


# ---------- 输出 ----------
ANCHOR_TARGETS = set()
for _pid in order:   # 先空跑一遍，收集被链接的块
    if _pid in pages:
        CUR['page'] = _pid
        render_children(pages[_pid], '', {'page': _pid})
ANCHOR_TARGETS = ANCHORS & RENDERED
LIVE['ready'] = True
report.clear()
os.makedirs(os.path.join(OUT, PAGEDIR), exist_ok=True)
written = []
for pid in order:
    if pid not in fname:
        continue
    b = pages[pid]
    if (b.get('props') or {}).get('field') is not None and not page_has_content(pid):
        continue  # 只有字段、没有正文的记录，已在数据表里展示
    ctx = {'page': pid}
    CUR['page'] = pid
    t_md = inline((b.get('props') or {}).get('title')).replace('\n', ' ').strip()
    head = [f'# {t_md or esc(display_title(pid))}', '']
    pp = parent_page(pid)
    src = f'{SPACE_URL}?p={pid}'
    head += [f'> 原文：{src}' + (f'　上级：[{esc(display_title(pp))}]({page_href(pp)})' if pp in fname else ''), '']
    field = (b.get('props') or {}).get('field')
    if field:
        coll = COLL.get(b.get('parentId')) or {}
        for fid, fv in field.items():
            m = (coll.get('meta') or {}).get(fid, {'type': 1, 'title': fid})
            head.append(f"- {esc(m.get('title', fid))}：{field_md(fv, m)}")
        head.append('')
    body = render_children(b, '', ctx)
    txt = squeeze(head + body)
    open(os.path.join(OUT, PAGEDIR, fname[pid]), 'w', encoding='utf8').write(txt)
    written.append(pid)

# 目录：按父子关系缩进；侧栏顺序优先
children_of = collections.defaultdict(list)
roots = []
for pid in order:
    if pid not in written:
        continue
    pp = parent_page(pid)
    while pp and pp not in written:
        pp = parent_page(pp)
    (children_of[pp].append(pid) if pp else roots.append(pid))

toc = [f'# {SPACE_TITLE}', '',
       f'> 原文：{SPACE_URL}（腾讯文档智能文档，公开只读）',
       f'> 抓取：2026-09-27，共 {len(written)} 页。每页文件开头有原文链接。',
       '> 图片在 `图片/`，附件在 `附件/`，编辑器原始块数据在 `原始数据/blocks.json`（转换漏掉什么可以从这里重新生成）。',
       '> 怎么抓的、怎么核的、以后怎么重抓，见 `抓取与转换脚本/抓取说明.txt`。', '']


def walk(pid, d):
    toc.append('  ' * d + f'- [{esc(display_title(pid))}]({PAGEDIR}/{md_href(fname[pid])})')
    for c in children_of.get(pid, []):
        walk(c, d + 1)


for r in roots:
    walk(r, 0)
if WRITE_TOC:
    toc += ['', '## 外链文档', '', '正文里链到的空间外文档，一并存在 `外链文档/`：', '']
    for k, v in EXTMAP.items():
        toc.append(f'- [{os.path.basename(v)[:-3]}]({md_href(v)})')
    open(os.path.join(OUT, '目录.md'), 'w', encoding='utf8').write('\n'.join(toc) + '\n')

os.makedirs(os.path.dirname(os.path.join(OUT, RAW)), exist_ok=True)
json.dump({'block': B, 'collection': COLL, 'collectionview': VIEW, 'tree': tree},
          open(os.path.join(OUT, RAW), 'w', encoding='utf8'), ensure_ascii=False)

rep = {k: (sorted(set(map(str, v))) if k not in ('files', 'flowcharts') else v) for k, v in report.items()}
rep['pages_written'] = len(written)
rep['pages_total'] = len(pages)
json.dump(rep, open(CFG.get('report', os.path.join(HERE, 'report.json')), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print({k: (len(v) if isinstance(v, list) else v) for k, v in rep.items()})
