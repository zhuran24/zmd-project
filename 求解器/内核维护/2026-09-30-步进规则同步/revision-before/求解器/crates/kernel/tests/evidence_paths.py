"""Allocate isolated test instances; importing this module never writes."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import uuid

SHARED_TARGET = Path("/home/zhuran24/zmd-research-fresh/求解器/target")

def real_directory(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("output root must be absolute without parent traversal")
    for ancestor in (*reversed(path.parents), path):
        if ancestor.is_symlink():
            raise ValueError("symlink in output path: " + str(ancestor))
    if path.exists() and not path.is_dir():
        raise ValueError("not a directory: " + str(path))
    return path

def output_root():
    explicit = os.environ.get("KERNEL_TEST_EVIDENCE_DIR")
    if explicit:
        root = real_directory(explicit)
        run = real_directory(os.environ["HEALTH_RUN"])
        registration = json.loads((run / "run-registration.json").read_text())
        if registration != dict(run=str(run), evidence=str(root), created_empty=True):
            raise ValueError("unregistered output root")
        if root != run / "cargo-test-evidence" or run.parent.name != "内核维护":
            raise ValueError("output root is outside this maintenance run")
        if not root.is_dir():
            raise ValueError("registered output root missing")
    else:
        base = real_directory(SHARED_TARGET / "health-tests")
        base.mkdir(exist_ok=True)
        root = base / ("run-" + uuid.uuid4().hex)
        root.mkdir()
    return root

def allocate(name):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
        raise ValueError("invalid test name")
    root = output_root()
    instance = root / (name + "-" + uuid.uuid4().hex)
    instance.mkdir(mode=0o700)
    (instance / ".instance.json").write_text(json.dumps(dict(test=name, instance=str(instance), root=str(root))))
    print("kernel test evidence retained: " + str(instance), file=sys.stderr)
    return instance

def instance_dir(name):
    supplied = os.environ.get("KERNEL_TEST_INSTANCE_DIR")
    if not supplied:
        return allocate(name)
    instance = real_directory(supplied)
    if os.environ.get("KERNEL_TEST_EVIDENCE_DIR"):
        parent = output_root()
    else:
        parent = real_directory(instance.parent)
        base = real_directory(SHARED_TARGET / "health-tests")
        if parent.parent != base or not re.fullmatch(r"run-[0-9a-f]{32}", parent.name):
            raise ValueError("unregistered default instance")
    if instance.parent != parent or not re.fullmatch(re.escape(name) + r"-[0-9a-f]{32}", instance.name):
        raise ValueError("instance outside registered root")
    manifest = json.loads((instance / ".instance.json").read_text())
    if manifest != dict(test=name, instance=str(instance), root=str(parent)):
        raise ValueError("instance identity mismatch")
    if sorted(p.name for p in instance.iterdir()) != [".instance.json"]:
        raise ValueError("instance is not new and empty")
    (instance / "python-source.json").write_text(json.dumps(dict(file=str(Path(sys.argv[0]).resolve()), root=str(Path(__file__).resolve().parents[3]))))
    return instance

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("name")
    print(allocate(parser.parse_args().name))
