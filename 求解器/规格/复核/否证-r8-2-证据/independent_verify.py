"""规格线第八轮第二否证席：独立核验停止谓词和输出字段名。"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import subprocess


output_dir = Path(__file__).resolve().parent
spec_dir = output_dir.parent.parent
root = spec_dir.parent.parent


def save(name, value):
    (output_dir / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )


def source_line(name, line_number):
    return (spec_dir / name).read_text().splitlines()[line_number - 1]


# 先核原文仍是本席推演的两个谓词，避免无来源的手填断言。
answer = source_line("参数轴-对内核输入请求的答复.md", 24)
transfer = source_line("受限转移定义.md", 90)
assert "至少两种无非空/历史目标物种且有无身份空格时" in answer
assert "len(U)>=2 and any(w in assigned_slots for w in E)" in transfer
products = ["高容谷地电池", "精选荞愈胶囊"]
cases = [
    ("两新种一未指派空格", products, ["E0"], ["W_ore_a", "W_ore_b"]),
    ("两新种一被指派空格", products, ["E0"], ["W_ore_a", "E0"]),
    ("两新种无空格", products, [], ["W_ore_a", "W_ore_b"]),
    ("单新种一被指派空格", products[:1], ["E0"], ["E0"]),
]
rows = []
for name, unknown, empty, assigned in cases:
    answer_stop = len(unknown) >= 2 and bool(empty)
    transition_stop = len(unknown) >= 2 and bool(set(empty) & set(assigned))
    plan = None
    if not transition_stop:
        plan = []
        for index, item in enumerate(sorted(unknown, key=lambda value: value.encode("utf-8"))):
            slot = empty[index] if index < len(empty) else "W_new_" + item.encode("utf-8").hex()
            plan.append({"item": item, "slot": slot, "quantity": 1})
        assert len({entry["slot"] for entry in plan}) == len(plan)
        assert all(entry["quantity"] <= 80000 for entry in plan)
    rows.append({"case": name, "U": unknown, "E": empty, "O": empty,
                 "assigned_slots": assigned, "answer_stop": answer_stop,
                 "transition_stop": transition_stop, "plan": plan})
assert rows[0]["answer_stop"] and not rows[0]["transition_stop"]
assert all(row["answer_stop"] == row["transition_stop"] for row in rows[1:])
save("停止条件独立复算.json", {
    "scope": "普通有限执行的局部仓库事务；不是完整布局、可达性或生产周期D域证书",
    "preconditions": ["箱体有电、传输开关开、冷却为0", "每个新物种各1件，分别占箱体一格",
                      "两成品均无现存或历史目标", "空格身份已解null、空格序完整",
                      "规范新标签无冲突", "区间无改指派、拿取或离线，保留历史身份"],
    "answer_source": answer, "transition_source": transfer, "cases": rows,
    "result": "PASS：复现了未指派空格时两条件不同"})

# 从当前封闭schema构造最小停止记录；它只用来检验字段契约。
schema_path = spec_dir / "内核输出.schema.json"
schema = json.loads(schema_path.read_text())
run_def = schema["$defs"]["RunRecord"]
assert "validation_scope" in run_def["required"]
assert "validation_scope" in run_def["properties"]
assert "verification_scope" not in run_def["properties"]
assert run_def["additionalProperties"] is False
assert "输出verification_scope" in source_line("参数轴-对内核输入请求的答复.md", 22)
record = {
    "schema": "kernel-output-v3", "run_id": "r8-seat2-schema-fixture",
    "profile_id": "kernel_profile_v1", "execution_mode": "finite_concrete",
    "port_meeting": "shared_edge_opposite",
    "producer": {"kind": "manual_expected", "path": str(Path(__file__).resolve()),
                 "claim": "仅字段形状试样，不是游戏执行记录"},
    "status": "invalid_input", "fingerprints": [], "parameter_assignment": None,
    "input_history": None, "uncovered_axes": [], "trace": None,
    "validation_scope": None, "open_items": ["手工字段试样：没有装载输入或执行游戏转移"]
}
renamed = deepcopy(record)
renamed["verification_scope"] = renamed.pop("validation_scope")
both = deepcopy(record)
both["verification_scope"] = None
save("字段名最小试样.json", {"original": record, "renamed": renamed, "both": both})

node_source = """
const fs = require('fs');
const Ajv = require(process.argv[1]);
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const branch = {$schema:payload.schema.$schema, $defs:payload.schema.$defs, $ref:'#/$defs/RunRecord'};
const root = new Ajv({strict:false, allErrors:true}).compile(payload.schema);
const run = new Ajv({strict:false, allErrors:true}).compile(branch);
const results = payload.values.map(value => {
  const rootValid = root(value);
  const runValid = run(value);
  return {root_valid:rootValid, run_record_valid:runValid, run_record_errors:run.errors};
});
process.stdout.write(JSON.stringify(results));
"""
ajv_path = "/home/zhuran24/.local/lib/devspace/node_modules/ajv/dist/2020.js"
payload = {"schema": schema, "values": [record, renamed, both]}
process = subprocess.run(["node", "-e", node_source, ajv_path],
                         input=json.dumps(payload), capture_output=True, text=True, check=True)
results = json.loads(process.stdout)
assert [entry["root_valid"] for entry in results] == [True, False, False]
assert [entry["run_record_valid"] for entry in results] == [True, False, False]
errors = results[1]["run_record_errors"]
assert any(error["keyword"] == "required" and error["params"].get("missingProperty") == "validation_scope" for error in errors)
assert any(error["keyword"] == "additionalProperties" and error["params"].get("additionalProperty") == "verification_scope" for error in errors)
save("字段名独立校验.json", {
    "scope": "仅验证当前schema的结构；不表示轨迹合法、来源核验或目标认证",
    "schema_path": str(schema_path), "schema_sha256": hashlib.sha256(schema_path.read_bytes()).hexdigest(),
    "validator": ajv_path, "validator_stderr": process.stderr,
    "original": results[0], "renamed": results[1], "both": results[2],
    "result": "PASS：正确字段通过，改名同时触发缺字段和未知字段，保留两名也失败"})
print(json.dumps({"stop_predicates": "PASS", "schema_field_mutation": "PASS"}, ensure_ascii=False))
