r"""从 CC session transcript 抽取全部用户真实消息 (跳过系统注入/工具噪声),
作为"本 session 内容是否全落盘 memory"覆盖检查的客观基准。
用法: <venv-py> extract_user_turns.py <transcript.jsonl>  (默认抽到 %TEMP%\_session_user_turns.txt)"""
import json, os, sys

src = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\Lenovo\.claude\projects\D-----zmd\ca5783d1-e3be-4591-8cfd-4ede5ed83635.jsonl'
dst = os.path.join(os.environ['TEMP'], '_session_user_turns.txt')

NOISE_PREFIX = ('<system-reminder', '<task-notification', '[SYSTEM', 'Caveat:',
                '<local-command', '<command-')
out, n = [], 0
for line in open(src, encoding='utf-8'):
    line = line.strip()
    if not line:
        continue
    try:
        obj = json.loads(line)
    except Exception:
        continue
    msg = obj.get('message') or {}
    if msg.get('role') != 'user':
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
        n += 1
        out.append('[U%d] %s' % (n, t[:2000]))

open(dst, 'w', encoding='utf-8').write('\n\n'.join(out))
print('user msgs:', n)
print('written:', dst)
