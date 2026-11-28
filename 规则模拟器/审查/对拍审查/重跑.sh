#!/usr/bin/env bash
# bash 重跑.sh   (临时目录保留源码副本、生成输入和计数器)
set -euo pipefail
audit=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$audit/../../.." && pwd)
run=$(mktemp -d)
echo "工作目录 $run"
sim="$run/规则模拟器"
model="$run/规则模型"
mkdir -p "$sim/审查/对拍审查" "$model" "$run/profiles"
cp -r "$repo/规则模型"/{Endfield,Endfield.lean,对拍,lakefile.toml,lake-manifest.json,lean-toolchain} "$model/"
cp -r "$repo/规则模拟器"/{Cargo.toml,Cargo.lock,src,tests,验收} "$sim/"
cp "$audit/独立对拍.py" "$sim/审查/对拍审查/"
(cd "$model" && lake build 对拍库 对拍)
cd "$sim"
export RUSTC_BOOTSTRAP=1 RUSTFLAGS="-C instrument-coverage -Zcoverage-options=branch"
export LLVM_PROFILE_FILE="$run/profiles/%m.profraw"
for gate in golden interfaces random_diff; do
    python3 -B "验收/$gate.py"
done
python3 -B 审查/对拍审查/独立对拍.py --inputs "$run/独立输入"
mkdir examples
cp "$audit"/复现/{正式入口.rs,指数库存.json} examples/
cargo build --locked --release --example 正式入口
# 格式外的指数和构造子对象由 Lean 接受，当前 Rust 入口按格式拒绝。
reject() {
    if "$@" > "$run/reject.out" 2> "$run/reject.err"; then
        echo "预期拒绝，实际成功：$*" >&2
        exit 1
    else
        test "$?" -eq 1
    fi
    test -s "$run/reject.err"
}
for sample in "$audit"/复现/*.json; do
    (cd "$model" && lake exe 对拍 "$sample") > "$run/lean.out"
    reject target/release/endfield-sim "$sample"
done
reject target/release/examples/正式入口
cargo test --locked --test replay_input
(cd "$model" && lake env lean "$audit/复现/分流器终点.lean")
testbin=$(find target/debug -type f -executable -name 'legal_base-*' -print -quit)
replaybin=$(find target/debug -type f -executable -name 'replay_input-*' -print -quit)
llvm-profdata merge -sparse "$run/profiles"/*.profraw -o "$run/coverage.profdata"
DEBUGINFOD_URLS='' llvm-cov export target/release/endfield-sim -object "$testbin" -object "$replaybin" -object target/release/examples/正式入口 -instr-profile="$run/coverage.profdata" src |
    python3 "$audit/汇总覆盖.py" | tee "$run/coverage.md"
DEBUGINFOD_URLS='' llvm-cov export target/release/endfield-sim -object "$testbin" -object "$replaybin" -object target/release/examples/正式入口 -instr-profile="$run/coverage.profdata" -format=lcov src > "$run/lines.lcov"
