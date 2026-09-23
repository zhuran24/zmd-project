"""Bind external runtime dependencies and validate successful file accesses."""
import codecs,json,re,shutil,subprocess,sysconfig
from pathlib import Path
from continuation_guard import RUN,REPO,sha,write,check

def prepare():
    paths=set();packages={}
    for name in ['python','node','sha256sum','strace']:
        p=Path(shutil.which(name)).resolve();paths.add(p)
        text=subprocess.check_output(['ldd',str(p)],text=True)
        for s in re.findall(r'(/[^\s()]+)',text):
            p=Path(s).resolve()
            if p.is_file():paths.add(p)
    # Kernel's native dependencies are also included in the production probe.
    for name in ['libgcc_s.so.1','libc.so.6','libm.so.6']:
        paths.add((Path('/usr/lib')/name).resolve())
    for name in ['/etc/ld.so.cache','/etc/localtime','/etc/locale.alias','/etc/nsswitch.conf','/etc/passwd','/etc/group']:
        p=Path(name)
        if p.is_file():paths.add(p.resolve())
    stdlib=Path(sysconfig.get_path('stdlib'))
    for p in stdlib.rglob('*'):
        if 'site-packages' not in p.parts and p.is_file():paths.add(p.resolve())
    locale=Path('/usr/lib/locale')
    for p in locale.rglob('*'):
        if p.is_file():paths.add(p.resolve())
    modules=Path('/home/zhuran24/.local/lib/devspace/node_modules')
    def package(root):
        root=root.resolve()
        if str(root) in packages:return
        data=json.loads((root/'package.json').read_text());packages[str(root)]=dict(name=data['name'],version=data['version'],dependencies=data.get('dependencies',{}))
        for p in root.rglob('*'):
            if p.is_file():paths.add(p.resolve())
        for dep in data.get('dependencies',{}):
            choices=[root/'node_modules'/dep,*[p/'node_modules'/dep for p in root.parents]]
            resolved=next((p for p in choices if (p/'package.json').is_file()),None);assert resolved,dep;package(resolved)
    package(modules/'ajv')
    manifest=dict(files={str(p):dict(sha256=sha(p),size=p.stat().st_size) for p in sorted(paths)},packages=packages,method='complete Python standard-library files excluding third-party site-packages; recursively resolved AJV declared dependencies; native executable ldd closure and locale/config files')
    write(RUN/'continuation-runtime-dependencies.json',manifest);return manifest

def verify():
    manifest=json.loads((RUN/'continuation-runtime-dependencies.json').read_text())
    for p,row in manifest['files'].items():assert sha(p)==row['sha256'],('runtime dependency changed',p)
    return manifest

def audit_trace(path,source,outputs,executables=()):
    manifest=verify();external=set(manifest['files']);source=Path(source).resolve()
    roots=[Path(p).resolve() for p in outputs];executables={str(Path(p).resolve()) for p in executables}
    rows=[];seen=set()
    for line in Path(path).read_text().splitlines():
        match=re.search(r'= [0-9]+<([^>]+)>$',line)
        if not match:continue
        raw=match.group(1)
        decoded=codecs.escape_decode(raw.encode())[0].decode('utf-8',errors='strict')
        if decoded.startswith(('/proc/','/sys/','/dev/')):continue
        p=Path(decoded).resolve()
        if not p.is_file():continue
        key=str(p)
        if key in seen:continue
        seen.add(key)
        category='source' if p.is_relative_to(source) else 'output' if any(p.is_relative_to(q) for q in roots) else 'executable' if key in executables else 'external' if key in external else None
        assert category,('unregistered runtime read',key)
        rows.append(dict(path=key,sha256=sha(p),category=category))
    return rows

if __name__=='__main__':
    check('runtime-bind-before');m=prepare();verify();write(RUN/'continuation-runtime-summary.json',dict(files=len(m['files']),packages=m['packages']));check('runtime-bind-after');print('runtime files',len(m['files']))
