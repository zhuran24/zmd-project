#!/usr/bin/env python3
"""Render a self-contained report from finished run records only."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import statistics
import argparse

ROOT=Path(__file__).resolve().parent


def main(final=False):
    results=[]
    for f in (ROOT/'results').glob('*.json'):
        d=json.loads(f.read_text())
        if {'tag','status','solve_seconds','load_samples'}<=d.keys():
            d['_file']=f
            check_file=f.with_name(f.stem+'.check.json')
            d['_checked_solution']=bool('solution' in d and check_file.exists() and json.loads(check_file.read_text()).get('ok'))
            results.append(d)
    results.sort(key=lambda d:d['started_utc'])
    summary=[]
    for y in (6,7,9,17):
        rows=[d for d in results if d['rect'][1]==y]
        infeas=[d for d in rows if d['status']=='INFEASIBLE']
        sols=[d for d in rows if d['_checked_solution']]
        status='INFEASIBLE' if infeas else ('找到可行骨架解' if sols else 'UNKNOWN')
        summary.append(dict(y=y,status=status,solve_seconds=sum(d['solve_seconds'] for d in rows),
                            total_seconds=sum(d['total_seconds'] for d in rows),runs=[d['tag'] for d in rows],
                            infeasible_runs=[d['tag'] for d in infeas],solution_runs=[d['tag'] for d in sols]))
    m=json.loads((ROOT/'manifest.json').read_text());repo=ROOT.parents[2]
    input_check={name:hashlib.sha256((repo/name).read_bytes()).hexdigest()==v['sha256']
                 for name,v in m['source_files'].items()}
    change_audit=json.loads((ROOT/'input_change_audit.json').read_text()) if (ROOT/'input_change_audit.json').exists() else None
    reviewed_current=(hashlib.sha256((repo/'求解约束.txt').read_bytes()).hexdigest()==change_audit['new_sha256']) if change_audit else input_check['求解约束.txt']
    now=datetime.now(timezone.utc).isoformat()
    started=m.get('first_recorded_task_clock_utc',m['start_utc'])
    elapsed=(datetime.fromisoformat(now)-datetime.fromisoformat(started)).total_seconds()
    out=dict(generated_utc=now,first_recorded_task_clock_utc=started,elapsed_wall_seconds=elapsed,
             experiment_complete=final,positions=summary,input_hashes_unchanged=input_check,
             all_inputs_unchanged=all(input_check.values()),input_change_audit=change_audit,
             current_constraints_match_reviewed_version=reviewed_current,runs=len(results))
    (ROOT/'summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    lines=['# 面积 1113：矿石与全体物品流量层实验报告','',
           f'日期：{now}。状态：{"本轮有限时实验已结束" if final else "实验进行中，仅汇总已完成运行"}。','',
           '检验对象是 21×53 空矩形左下角 `(49,6)`、`(49,7)`、`(49,9)`、`(49,17)`。模型对 x↔y 对称，转置位置不重复求解。所有坐标从 0 起算。','',
           f'首个记录时刻为 {started}；截至汇总经过 {elapsed/60:.2f} 分钟。已完成实例累计求解墙钟 {sum(d["solve_seconds"] for d in results)/60:.2f} 分钟，构建、核查、调度与报告时间不混入单次 solve 时间。','',
           '## 1. 位置结论','',
           '| 位置 | 最终状态 | 求解累计墙钟（秒） | 含构建/导出等累计（秒） |',
           '|---|---|---:|---:|']
    for d in summary:
        lines.append(f'| (49,{d["y"]}) | {d["status"]} | {d["solve_seconds"]:.3f} | {d["total_seconds"]:.3f} |')
    lines += ['', '**UNKNOWN 不算排除或存在性结论**：限时结束时既没有满足全部所编码必要条件的解，也没有完成不可行证明。模型可行也只给骨架，不给达标游戏布局。', '',
              '## 2. 每次求解、参数与负载','',
              '“矿石”层仅含两种原矿的合并流；“全体”层同时含独立矿石流与全体物品流。表中位置实例串行、每实例 8 个 CP-SAT worker；六个局部控制例各 1 worker，先于主测运行，没有并行 CP-SAT 实例。除首个矿石短测外，求解进程以 nice=10 运行。随机种子、探测和线性化配置见下表及结果 JSON；缺省对称等级 2。全体层不是联合分物品配方模型。', '',
              'OR-Tools 9.15.6755，Python 3.14.7，24 逻辑 CPU。整机 load average 包含其他工作，不能当作本进程 CPU 占用，也没有隔离测得争用的因果影响。每 15 秒采样，表中 load 为已采样 1 分钟负载的最小/平均/最大值，RSS 为进程已采样峰值。', '',
              '| 运行 | 层/编码 | 上限 s | 实测 s | 构建 s | 状态 | seed | probing/linearization | load 最小/均值/最大 | RSS GiB |',
              '|---|---|---:|---:|---:|---|---:|---|---|---:|']
    for d in results:
        ss=d['load_samples']; loads=[s['load'][0] for s in ss]; rss=max(s['rss_bytes'] for s in ss)/2**30;a=d['args']
        link=f'[{d["tag"]}](results/{d["_file"].name})'
        variant={'explicit_global_totals':'总量加强','compact_ore_with_recovered_labels':'标签消元','global_min_edges_first_solution':'总量+弧流目标/首解','global_min_edges_original_P_domain':'总量+原P域+目标/首解'}.get(d.get('variant'),'显式标签')
        lines.append(f'| {link} | {d["layer"]}/{variant}/{d["cut_mode"]} | {a["seconds"]:g} | {d["solve_seconds"]:.3f} | {d["build_seconds"]:.3f} | {d["status"]} | {a["seed"]} | {a["probing"]}/{a["linearization"]} | {min(loads):.2f}/{statistics.mean(loads):.2f}/{max(loads):.2f} | {rss:.2f} |')
    lines += ['', '每次求解的完整 CP-SAT 参数、环境、响应统计、模型统计、代码散列、开始/结束时间、负载样本均在对应 `results/*.json`。逐次搜索日志和 15 秒负载记录在 `logs/`；二进制模型快照及散列在 `models/` 和结果 JSON。实测包含求解器停止/回收开销，可能略超参数时限。所有时限重跑从头求解，不声称延续了上一轮学习状态。', '',
              '## 3. 模型全部约束、出处与覆盖证明','']
    spec=(ROOT/'模型说明.md').read_text().splitlines()
    # Include the full technical specification; preserve its internal numbering.
    for line in spec[4:]:
        line=re.sub(r'^## ([1-6])\. ',lambda m:'### 3.'+m[1]+'. ',line)
        line=re.sub(r'第 ([1-6]) 节',lambda m:'第 3.'+m[1]+' 节',line)
        line=line.replace('第 3、4 节','第 3.3、3.4 节')
        lines.append(line)
    lines += ['', '## 4. 不可行与可行见证复核','']
    if not any(d['status']=='INFEASIBLE' for d in results):
        lines += ['没有任何位置主测返回 INFEASIBLE，因此本轮没有位置排除结论，也没有可供执行“撤去可疑切割/换求解器”的位置不可行结果。`--cut-mode none` 已实现，但实现不等于完成了复核。局部负例测试的 INFEASIBLE 不计入位置结果。','']
    else:
        for d in results:
            if d['status']=='INFEASIBLE':
                lines.append(f'- `{d["tag"]}` 返回 INFEASIBLE；约束模式 `{d["cut_mode"]}`，用时 {d["solve_seconds"]:.3f} 秒。复核是否覆盖同一位置和全部 P/边带，应按上表的弱化运行状态单独判断。')
    sols=[d for d in results if 'solution' in d]
    if not sols:
        lines += ['没有找到满足完整几何和所选流量层的骨架，所以没有骨架解文件或可报告的瓶颈流。模型快照 `.pb`、UNKNOWN 统计、边界子模型的既有解均不冒充骨架。没有完整实例阳性样本，解导出及标签恢复的端到端路径尚未在这四个实例上实测通过；局部测试和坐标核对不能替代这一步。','']
    else:
        for d in sols:
            cf=d['_file'].with_name(d['_file'].stem+'.check.json')
            ck=json.loads(cf.read_text()) if cf.exists() else None
            label='骨架' if ck and ck['ok'] else '未认可的求解器候选'
            lines += [f'- {label}：[{d["tag"]}](results/{d["_file"].name})；直接检查状态：{ck["ok"] if ck else "尚无检查记录"}。']
            if ck:
                for layer,stats in ck['flow_statistics'].items():
                    lines += [f'  - {layer}：K={stats["K"]}，仓库/核心总源={stats["source_total"]}/{stats["K"]} 件/tick，运输格总通过量={stats["transport_throughput"]}/{stats["K"]}，饱和格 {stats["saturated_count"]}，整数替代流双轴正流桥 {stats["dual_active_bridges"]}。饱和格逐向流见检查 JSON。']
    audit=json.loads((ROOT/'encoding_audit.json').read_text())
    lines += [f'坐标/算术核查：[encoding_audit.json](encoding_audit.json)。47 种边带、{audit["port_cases"]} 个端口枚举案例、{audit["power_overlap_cases"]} 个供电相交案例全部一致；217 台、3291 格以及全体层总源量 6113/20 的算术核对通过。六个运输节点正反例见 [unit_checks.json](unit_checks.json)，复现脚本为 [test_flow_kernel.py](test_flow_kernel.py)。这些检查不替代完整实例判定。','',
              '检查器整段负例拒收通过：[checker_negative_control.json](checker_negative_control.json)。负例故意只有一台机器、无桩、零源流，不是候选布局。检查器的机身尺寸变量与仓库端口列表已分名；相关变量遮蔽回归的原始失败日志、修复后复跑和字节相同的旧源码见 [checker_regression.json](checker_regression.json)。该问题只涉及检查器，当时所有位置主测均为 UNKNOWN，求解模型和已完成求解结果不受影响。','',
              '## 5. 局限与后续复核边界','',
              '- 本轮的有限时 CP-SAT 状态不是一般复杂度结论。UNKNOWN 不能降低 1113 上界；亦不证明这些位置存在布局。',
              '- 流量整数替代证明针对这里逐层独立的网络。若后续加入联合容量、物品身份绑定、配方比例或最小正流量，需要重新证明整数化覆盖，或改用连续 LP。',
              '- 开工快照的 71 条正式约束没有全部机制进入本模型；已编码约束的完整清单在第 3 节。运行中 72 条版本的相关差异已单独核对。省略部分扩大可行域。',
              '- CP-SAT INFEASIBLE（若出现）是求解器结论；未生成 LRAT 等独立形式证明。弱化模型复跑、代码审查和直接解检查的证据层级分别记录。',
              '- 本轮检验只覆盖这 4 个代表位置，其余位置排除使用既有研究背景及正式72条版的“1113 位置”；本轮没有重做整个 1113 位置枚举。', '',
              '## 6. 输入保护与复现','',
              f'本次读取的正式文件、既有脚本/报告在汇总时的散列核对：**{"全部未变" if all(input_check.values()) else "发现变化，见 summary.json"}**。本轮产物只写入此目录，没有执行 git 操作、没有编译，没有改正式文件或候选约束。', '',
              f'开工快照与运行中版本的变化见 [输入变化.md](输入变化.md) 及 [input_change_audit.json](input_change_audit.json)。汇总时《求解约束.txt》与已审阅的 72 条版本散列一致：**{reviewed_current}**。其他输入是否变化逐文件列在 summary.json。', '',
              '单次重跑须使用新的 stage 名，已有结果拒绝覆盖。例如：','',
              '```bash',
              'python -B 求解器/几何/1113流量层/flow_model.py --y 6 --layer ore --stage replay_ore --seconds 600 --workers 8',
              'python -B 求解器/几何/1113流量层/flow_model_compact.py --y 6 --layer ore --stage replay_compact --seconds 300 --workers 8 --seed 20260923',
              'python -B 求解器/几何/1113流量层/flow_model_global.py --y 6 --layer all --stage replay_all --seconds 1800 --workers 8',
              'python -B 求解器/几何/1113流量层/flow_model_min_edges_domain.py --y 6 --layer all --stage replay_aux --seconds 300 --workers 8 --seed 20260923',
              'python -B 求解器/几何/1113流量层/flow_model.py --y 6 --layer all --stage replay_nocuts --seconds 900 --workers 8 --cut-mode none',
              '```','',
              '文件入口：[模型说明.md](模型说明.md)、[flow_model.py](flow_model.py)、[geometry.py](geometry.py)、[check_solution.py](check_solution.py)、[summary.json](summary.json)、[manifest.json](manifest.json)、[unit_checks.json](unit_checks.json)。','']
    (ROOT/'报告.md').write_text('\n'.join(lines))
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--final',action='store_true')
    main(ap.parse_args().final)
