r"""从 CC session transcript 抽取「对话全文」(用户 + 助手 的自然语言消息, 跳过工具噪声),
作为「本 session 内容是否全落盘 memory」覆盖检查的客观基准。
主体必须是整段对话 (user + assistant), 不能只抽 user —— 值得记的事 (finding / 踩坑修法 /
决策 / 结论) 助手侧也大量产生; 只抽 user 会漏掉它们 (本项目 2026-06-01 两次踩到: 先用
proxy=记忆树, 再只抽 user)。详见 memory verification-independent-backstop。
用法: <venv-py> extract_session_turns.py [transcript.jsonl]  (默认抽到 %TEMP%\_session_turns.txt)"""
import json
import os
import sys

src = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\Lenovo\.claude\projects\D-----zmd\ca5783d1-e3be-4591-8cfd-4ede5ed83635.jsonl'
dst = os.path.join(os.environ['TEMP'], '_session_turns.txt')

NOISE_PREFIX = ('<system-reminder', '<task-notification', '[SYSTEM', 'Caveat:',
                '<local-command', '<command-')
CAP = {'user': 4000, 'assistant': 3000}  # 助手消息可能很长, head 截断 (结论通常在开头)
out, nu, na = [], 0, 0
for line in open(src, encoding='utf-8'):
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
    except Exception:
        continue
    msg = obj.get('message') or {}
    role = msg.get('role')
    if role not in ('user', 'assistant'):
        continue
    content = msg.get('content')
    texts = []
    if isinstance(content, str):
        texts = [content]
    elif isinstance(content, list):
        for c in content:
            if isinstance(c, dict) and c.get('type') == 'text':
                texts.append(c.get('text', ''))
    for t in texts:
        t = (t or '').strip()
        if not t or t.startswith(NOISE_PREFIX) or 'tool_use_error' in t[:60]:
            continue
        if role == 'user':
            nu += 1
            tag = 'U%d' % nu
        else:
            na += 1
            tag = 'A%d' % na
        out.append('[%s] %s' % (tag, t[:CAP[role]]))

open(dst, 'w', encoding='utf-8').write('\n\n'.join(out))
print('user msgs:', nu, ' assistant msgs:', na)
print('written:', dst, ' bytes:', os.path.getsize(dst))
