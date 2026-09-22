"""只读：比较 f8f6129 中若干入库历史记录所记来源哈希与 f8f6129 同路径 blob 的哈希。
用于判断 13 个未跟踪文件能否用 f8f6129 源码在原路径下重算。"""
import hashlib, json, subprocess, sys
root = '/home/zhuran24/zmd-research-fresh'
pref = '/home/zhuran24/zmd-research-fresh/'
def blob(rev, p):
    try:
        return subprocess.check_output(['git', '-C', root, 'show', f'{rev}:{p}'], stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None
out = {}
for rec in sys.argv[1:]:
    d = json.loads(blob('f8f6129', rec))
    fps = d.get('fingerprints') or []
    same = diff = absent = 0; diffs = []
    for f in fps:
        p = f['path']
        if not p.startswith(pref):
            absent += 1; continue
        b = blob('f8f6129', p[len(pref):])
        if b is None:
            absent += 1; diffs.append(('not-in-git', f['role'], p[len(pref):])); continue
        if hashlib.sha256(b).hexdigest() == f['sha256']:
            same += 1
        else:
            diff += 1; diffs.append(('differs', f['role'], p[len(pref):]))
    out[rec] = {'fingerprints': len(fps), 'same_as_f8': same, 'differs': diff, 'absent': absent, 'detail': diffs[:40]}
print(json.dumps(out, ensure_ascii=False, indent=1))
