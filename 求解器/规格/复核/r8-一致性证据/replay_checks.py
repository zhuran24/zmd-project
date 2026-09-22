"""只读重跑被审脚本；仅把生成位置改到本席证据目录，不更改任何断言。"""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import sys

output_dir = Path(__file__).resolve().parent
spec_dir = output_dir.parent.parent
revision_dir = spec_dir / '第五轮规格修订'
sys.path.insert(0, str(revision_dir))
source = (revision_dir / 'check_round5.py').read_text()
old = 'def dump(name,value): (here/name).write_text'
new = 'def dump(name,value): (review_output/name).write_text'
assert source.count(old) == 1
namespace = {'__file__': str(revision_dir / 'check_round5.py'), '__name__': '__main__', 'review_output': output_dir}
with (output_dir / '第五轮自查重跑.log').open('w') as log, contextlib.redirect_stdout(log):
    exec(compile(source.replace(old, new), str(revision_dir / 'check_round5.py'), 'exec'), namespace)

# 在内存捕获生成串，与交付schema逐字节比较；不运行被审脚本的写回语句。
source = (revision_dir / 'build_schema.py').read_text()
old = "(spec/'内核输出.schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\\n')"
new = "generated_text=json.dumps(schema,ensure_ascii=False,indent=2)+'\\n'"
assert source.count(old) == 1
builder = {'__file__': str(revision_dir / 'build_schema.py'), '__name__': '__main__'}
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(source.replace(old, new), str(revision_dir / 'build_schema.py'), 'exec'), builder)
actual = (spec_dir / '内核输出.schema.json').read_bytes()
assert builder['generated_text'].encode() == actual
facts = {'check_count': namespace['report']['check_count'], 'schema_rebuild_byte_equal': True, 'schema_sha256': hashlib.sha256(actual).hexdigest(), '断言改动': False, '输出目录': str(output_dir)}
(output_dir / '重跑摘要.json').write_text(json.dumps(facts, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(facts, ensure_ascii=False))
