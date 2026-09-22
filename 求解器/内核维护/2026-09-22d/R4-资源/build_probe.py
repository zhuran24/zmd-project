#!/usr/bin/env python3
"""Compile an instrumentation entrypoint against unchanged source modules.

No production file is edited or copied. rustc outputs only to shared target.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

out = Path(__file__).resolve().parent
root = out.parents[2]
src = root / 'crates/kernel/src'
target = root / 'target'
modules = re.findall(r'^(?:pub )?mod (\w+);$', (src / 'lib.rs').read_text(), re.M)
lines = ['#![forbid(unsafe_code)]']
for module in modules:
    if module != 'tests':
        lines.append(f'#[path = {json.dumps(str(src / (module + ".rs")), ensure_ascii=False)}] pub mod {module};')
lines += ['pub use config::Config;', 'pub use engine::Engine;', 'pub use input::Input;',
          'pub use value::{Result, Stop};', 'include!("probe_body.rs");']
(out / 'probe_main.rs').write_text('\n'.join(lines) + '\n')
binary = target / 'release/r4-resource-probe'
argv = ['rustc', '--edition=2021', '--crate-name', 'r4_resource_probe', '-O',
        '-C', 'codegen-units=1', '-L', 'dependency=' + str(target / 'release/deps')]
for crate in ['serde', 'serde_json']:
    candidates = list((target / 'release/deps').glob('lib' + crate + '-*.rlib'))
    assert len(candidates) == 1, candidates
    argv += ['--extern', crate + '=' + str(candidates[0])]
argv += [str(out / 'probe_main.rs'), '-o', str(binary)]
env = {**os.environ, 'CARGO_MANIFEST_DIR': str(root / 'crates/kernel'),
       'CARGO_TARGET_DIR': str(target), 'RAYON_NUM_THREADS': '1', 'CARGO_BUILD_JOBS': '1'}
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:6])
(out / 'probe-build.command.log').write_text(shlex.join(argv) + '\n')
with (out / 'probe-build.stdout.log').open('w') as stdout, (out / 'probe-build.stderr.log').open('w') as stderr:
    result = subprocess.run(argv, cwd=root, env=env, stdout=stdout, stderr=stderr)
record = {'argv': argv, 'env_overrides': {k: env[k] for k in ['CARGO_MANIFEST_DIR','CARGO_TARGET_DIR','RAYON_NUM_THREADS','CARGO_BUILD_JOBS']},
          'returncode': result.returncode, 'production_modules': {str(src / (m+'.rs')): hashlib.sha256((src / (m+'.rs')).read_bytes()).hexdigest() for m in modules if m != 'tests'}}
if result.returncode == 0:
    record['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
(out / 'probe-build.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
raise SystemExit(result.returncode)
