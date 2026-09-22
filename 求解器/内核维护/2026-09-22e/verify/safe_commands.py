from run_guarded import run
import sys

commands = [
    ('build-debug', ['cargo', 'build', '--workspace', '-j', '4']),
    ('build-release', ['cargo', 'build', '--workspace', '--release', '-j', '4']),
    ('cargo-check', ['cargo', 'check', '--workspace', '--all-targets', '-j', '4']),
    ('cargo-clippy', ['cargo', 'clippy', '--workspace', '--all-targets', '-j', '4']),
]
for name, package, kind in [('kernel-lib', 'kernel', ['--lib']), ('topology-lib', 'topology', ['--lib']),
                             ('kernel-reference', 'kernel', ['--test', 'reference']),
                             ('topology-validation', 'topology', ['--test', 'validation']),
                             ('kernel-doc', 'kernel', ['--doc']), ('topology-doc', 'topology', ['--doc'])]:
    commands.append((name, ['cargo', 'test', '-p', package, *kind, '-j', '4', '--', '--test-threads=1']))
for name, args in commands:
    result = run(name, args)
    if result:
        sys.exit(result)
