"""包二安装：只安装 package2-stage，保留包一脚本与历史基线。"""
import sys
from pathlib import Path
from guard import OUT, ROOT, guard, save, active_snapshot
from work import write, remove

def install(label):
    guard(label+'-before')
    try:
        for p in sorted((OUT/'package2-stage').rglob('*')):
            if p.is_file():
                relative=str(p.relative_to(OUT/'package2-stage'))
                if not (ROOT/relative).exists() or (ROOT/relative).read_bytes()!=p.read_bytes():
                    write(relative,p.read_bytes())
        for relative in ['crates/kernel/src/event_identity.rs', *['crates/kernel/tests/'+n+'.rs' for n in ['revision_cli','revision_r2_cli','revision_r3_cli','revision_r4_cli','revision_r5_cli','round5_cli','round6_cli']], 'crates/kernel/tests/support/mod.rs']:
            if (ROOT/relative).exists():remove(relative)
    finally:guard(label+'-after')
if __name__=='__main__':
    if sys.argv[1]=='baseline':
        guard('p2-start')
        save('package2-active-start.json',active_snapshot())
    else:install(sys.argv[1])
