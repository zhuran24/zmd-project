#!/usr/bin/env python3
"""生成本席状态契约与直接算术；只写本席路径，不运行来源脚本。"""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import json

E = Path(__file__).resolve().parent
O = E.parent.parent
ROOT = O.parents[2]

def write(path, value):
    assert path.resolve() == (O/'调试后状态.json').resolve() or E.resolve() in path.resolve().parents
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def recipe(ins, item, quantity, ticks, lines):
    return {'inputs':ins, 'output':{item:quantity}, 'ticks':ticks, 'rule_lines':lines}

RECIPES = {
 '粉碎-源矿':recipe({'源矿':1},'源石粉末',1,1,[81]),
 '粉碎-蓝铁块':recipe({'蓝铁块':1},'蓝铁粉末',1,1,[82]),
 '粉碎-荞花':recipe({'荞花':1},'荞花粉末',2,1,[83]),
 '粉碎-砂叶':recipe({'砂叶':1},'砂叶粉末',3,1,[84]),
 '精炼-蓝铁矿':recipe({'蓝铁矿':1},'蓝铁块',1,1,[87]),
 '精炼-致密蓝铁':recipe({'致密蓝铁粉末':1},'钢块',1,1,[88]),
 '研磨-致密蓝铁':recipe({'蓝铁粉末':2,'砂叶粉末':1},'致密蓝铁粉末',1,1,[92]),
 '研磨-致密源石':recipe({'源石粉末':2,'砂叶粉末':1},'致密源石粉末',1,1,[93]),
 '研磨-细磨荞花':recipe({'荞花粉末':2,'砂叶粉末':1},'细磨荞花粉末',1,1,[94]),
 '塑形-钢质瓶':recipe({'钢块':2},'钢质瓶',1,1,[97]),
 '配件-钢制零件':recipe({'钢块':1},'钢制零件',1,1,[100]),
 '种植-荞花':recipe({'荞花种子':1},'荞花',1,1,[103]),
 '种植-砂叶':recipe({'砂叶种子':1},'砂叶',1,1,[104]),
 '采种-荞花':recipe({'荞花':1},'荞花种子',2,1,[107]),
 '采种-砂叶':recipe({'砂叶':1},'砂叶种子',2,1,[108]),
 '封装-电池':recipe({'钢制零件':10,'致密源石粉末':15},'高容谷地电池',1,5,[111]),
 '灌装-胶囊':recipe({'钢质瓶':10,'细磨荞花粉末':10},'精选荞愈胶囊',1,5,[114]),
}
WEIGHTS = {'源矿':1,'蓝铁矿':1,'源石粉末':2,'蓝铁块':2,'蓝铁粉末':3,
 '荞花种子':2,'砂叶种子':2,'荞花':3,'砂叶':3,'荞花粉末':2,'砂叶粉末':2,
 '致密蓝铁粉末':9,'致密源石粉末':7,'细磨荞花粉末':7,'钢块':10,
 '钢制零件':11,'钢质瓶':21,'高容谷地电池':216,'精选荞愈胶囊':281}

def main():
    interface=json.loads((O/'送料与接口.json').read_text())
    weights=[]
    for name,r in RECIPES.items():
        wi=sum(WEIGHTS[i]*q for i,q in r['inputs'].items())
        wo=sum(WEIGHTS[i]*q for i,q in r['output'].items())
        weights.append({'recipe':name,'input_weight':wi,'output_weight':wo,'increase':wo-wi})
    candidate_results=[]
    for candidate in interface['candidates']:
        ordinary=cache=0
        terminal=[]
        for m in candidate['machines']:
            assert len(m['recipes'])==1
            r=RECIPES[m['recipes'][0]['name']]
            ordinary+=50*sum(WEIGHTS[i] for i in list(r['inputs'])+list(r['output']))
            cache+=max(sum(WEIGHTS[i]*q for i,q in r[mode].items()) for mode in ['inputs','output'])
            if r['ticks']==5: terminal.append(m['id'])
        candidate_results.append({'id':candidate['id'],'machines':len(candidate['machines']),
            'feeds':len(candidate['feeds']),'terminal_machines':terminal,
            'ordinary_potential_capacity':ordinary,'normal_cache_potential_capacity':cache,
            'potential_capacity_excluding_transport':ordinary+cache,
            'transport_potential':'sum(l_e * item_weight[e])',
            'transport_lengths_provided':False,
            'preparation_proof_realized_in_physical_layout':False})
    data={
      'type':'StructuredOutput','schema':'debug-release-state-v1','date':'2026-09-21',
      'status':'partial','error':None,'L':0,'U':1113,
      'sources':'证据/调试释放/输入指纹.json',
      'rule_sha256':interface['current_rule_sha256'],
      'task4_interface_version':interface['schema'],
      'evidence_layers':{'preparation_termination':'conditional_direct_proof',
          'local_49_output_witness':'reachable_local_material_trace',
          'loss_identities':'exact_event_accounting',
          'numeric_loss_examples':'conditional_upper_bounds',
          'safe_margins':'task4_sufficient_sets_only',
          'full_factory':'unproved','independent_review':'pending'},
      'default_program':{
          'terminal_definition':'M213-M215封装和M216-M218灌装，A候选加A_前缀',
          'steps':['预生产正确中间品','全关并显式清旧缓存/错种',
              '输入各50、非末级输出各50、非成品专线填满；成品线允许自然排空',
              '恢复最终矿口/设定并显式清理在途旧种',
              '任意顺序开全部非末级并充分等待库存制造静止',
              '任意顺序逐台开六末级，第一次开末级起计释放，最后一步后零干预'],
          'input_preparation':'T12允许预生产、手工放料；不从关闭的机器获得新中间品',
          'normal_cache_only':True,'exact_tick_control_required':False,
          'manual_actions_after_zero_intervention':False,
          'physical_preconditions':['合法实际几何','私有有限路径且无纯运输环',
            '始终供电','单种计划配方，无R89回转','非成品无其他外流',
            '填料恢复已完成，末级此前关闭','仓库收得下成品'],
          'candidates':candidate_results},
      'main_inference':{
          'every_machine_has_completed_batch':False,
          'specific_exception':'六末级从空缓存保持关闭，所以缓存为空',
          'every_transport_slot_full':False,
          'specific_transport_exception':'关闭末级且仓库可收，六条成品输出路径有限排空',
          'every_input_slot_50':'六末级在准备静止时保持50；非末级全部50尚未证明',
          'no_work_in_progress_before_first_terminal_open':{
              'proved':True,'conditional_on':'default_program.physical_preconditions及充分等待',
              'reason':'正势函数、有限库存与有限成功物料动作'},
          'manufacturing_phase_eliminated_after_last_terminal_open':False,
          'remaining_states':['空/完成缓存身份','逐机输入输出数量','物品与混线字序',
            '轮询/接通序','箱相位','准入口计数及窗口','逐台开机后的相对制造进度']},
      'post_state_set':{
          'representation':'sound_envelope_with_exact_program_reachability_predicate',
          'exact_reachable_set_enumerated':False,
          'all_cartesian_combinations_claimed_reachable':False,
          'preparation_quiescence_meaning':'库存、占用、制造稳定；不声称失败指针停止',
          'preparation':{
              'terminal':{'input_each':50,'output':0,'cache':'empty','switch':'off','product_paths':'empty'},
              'other_machines':{'switch':'on','input_range':[0,50],'output_range':[0,50],
                  'cache_states':['empty','completed_one_batch'],
                  'empty_cache_condition':'至少一项计划配方原料不足',
                  'completed_cache_same_kind_output':'51-b <= q_out <= 50',
                  'no_successful_material_move':True},
              'transport':'每实际格为空或一件正确物品；非空已成熟；桥轴独立'},
          'serial_release':{
              'orders':'all permutations of six terminals',
              'delays':'all finite nonnegative d1..d5',
              'parameter_constraint':'固定判定序；合法离线接通重排保留',
              'relation':'On_pi6 E_theta(d5) On_pi5 ... E_theta(d1) On_pi1(S_pre)',
              'cache_states':['empty','one_batch_processing','one_batch_completed_waiting'],
              'remaining_time_domains':{'normal':'(0,1]','terminal':'(0,5]'},
              'transport_age':'未成熟或成熟',
              'gate_state':['item_identity','accepted_total','window_accepted','window_remaining'],
              'box_state':['stock_by_numbered_slot','cooldown_remaining'],
              'constructive_closure_and_certification':'pending'}},
      'potential':{'weights':WEIGHTS,'recipe_increases':weights,
          'proof':'每次计划制造完成至少增1；原矿补入增正值；库存有限；纯运输路径无环',
          'completion_bound':'V_cap - V_start + V_out',
          'conservative_wait_bound':{'K':'2*V_cap','M':'(V_cap+4*K)*(l_max+4)+4*K',
              'wait_ticks_strictly_more_than':'M+2',
              'coarse_l_max_bound':9800,'coarse_transport_potential_bound':2753800,
              'purpose':'有限且不需要命中精确tick；不是实际调试耗时推荐'},
          'excluded_recipe':{'rule_line':89,'input_weight':3,'output_weight':2},
          'scheduler_microstep_termination_proved':False},
      'species_accounts':{
          x:{'seed_identity':'S(t)=S0+2H-P-I_seed',
             'plant_identity':'V(t)=V0+P-H-G-I_plant',
             'net_loss':'D=G+I_seed+I_plant-H',
             'max_loss_definition':'sup over all event prefixes including t=0',
             'candidate_actual_N0':None,'candidate_actual_Dmax':None,
             'candidate_actual_safety_margin':None,
             'unconditional_bound':'0 <= Dmax <= N0',
             'completed_full_slots_example_N0':n,
             'completed_full_slots_example_N0_add':'actual seed/plant transport slots',
             'conditional_E1_zero_leak_Dmax_bound':d,
             'conditional_E1_zero_leak_Dmax_add':'actual P-to-G plant transport slots',
             'conditional_first_clear_all_harvesters_full_same_kind':clear}
          for x,n,d,clear in [('荞花',2023,307,12),('砂叶',3793,562,22)]},
      'loss_bound':{
          'conditions':['single final-use boundary per plant','correctly include initial assigned stock',
                        'A_G-A_H <= E throughout','weighted leakage W <= Wmax'],
          'identity':'D=(A_G-A_H)+W+(B_H-B_H0)-(B_G-B_G0)',
          'W':'I+I_H-I_G',
          'bound':'min(N0, E+Wmax+B_Hmax-B_H0+B_G0)',
          'actual_candidate_E':None,'actual_candidate_path_lengths':None,
          'per_rejection_loss_constant_used':False},
      'release_mechanisms':{
          'first_clear':{'same_kind':'max(0,q+b-50)','different_kind':'q',
                         'harvester_full':'2*h+48*m','meaning':'首次清出需求'},
          'double_belt_planter':{'identity':'Q(n)=50+J(n)-D1(n)-D2(n)',
              'conditional_bound':'D1=D2=n and J<=n+1 imply Q<=51-n',
              'continuous_double_service_epochs_max':51,
              'loss_bound':False},
          'mixed_old_inventory':{'formula':'q+b*(u+c+a)',
              'conditions':'后续无未计旧种到货；缓存c为旧种0/1批；旧种服务兑现',
              'harvester_or_buck_powder':152,'sand_powder':203,
              'in_transit_old_plants_coefficient':[2,3]},
          'leakage':{'zero_leak':'requires structural separation',
              'seed_bound':'I_seed <= initial warehouse seed vacancies',
              'plant_bound':'I_plant <= initial warehouse plant vacancies',
              'bound_condition':'最终只取矿、玩家只拿成品、物品不在仓库内转换',
              'position_check_required':True}},
      'sufficient_margins':{
          'SAFE-FULL-TREE':{'input_after_start':'a in [0,49]',
              'supply_margin':'a','capacity_margin':'49-a',
              'default_reaches_set':None},
          'SAFE-HALF-LOOP':{'threshold':'l_H+l_S+3','local_threshold':23,
              'q_range':[23,50],'q50_seed_margin':27,'q50_capacity_margin':0,
              'species':['荞花','砂叶'],'scope':'空线辅助程序',
              'arbitrary_loss_allowance':False,'default_reaches_set':None},
          'MIXED-Z':{'Z0':-50,'safe_integer_D':[-48,99],
              'AAB_all_rotations_D':[-2,2],'Z_range':[-52,-48],
              'distance_to_bad_boundaries':[47,98],
              'scope':'单保序混线永久输入互等排除；不单独给目标率'}},
      'warehouse_recovery':{
          'same_state_types':True,'same_exact_default_start_subset_proved':False,
          'short_blockage':'在制批次及全部进度保留',
          'both_products_fully_blocked_long_enough':'专线无其他外流且正势函数时有限物料静止，无在制批次',
          'box_cooldown':'零传输也5tick；恢复保留既有剩余冷却',
          'environment':'仓库收得下成品',
          'reentry_to_sufficient_sets':'unproved'},
      'old_injection':{'n_survives_threshold_change':True,
          'resume_conditions':['identity_matches','n<C<=5000','five_tick_allowance_available','physical_slot_service'],
          'received_is_delivered':False,'one_shot_before_cycle_allowed':True,
          'default_program_uses_old_injection':False},
      'open_items':[{'id':f'DR-{i:02}','category':cat,'description':desc,'handoff':hand}
          for i,cat,desc,hand in [
            (1,'缺构造与推导','实际路径及默认后置集合关联不变量','任务5/7; PR-01/05; U3'),
            (2,'缺推导','实际E、反复拒收服务、逐根收支和Dmax','任务4/5/6; PR-02/03; U4'),
            (3,'缺推导','默认释放进入或扩大安全集合、共同下游服务','任务4—7; PR-04/06; U5'),
            (4,'缺构造与推导','217换种、A两路、B三路、220输入3:2:1','任务4/6/7; PR-06'),
            (5,'缺推导','接收恢复状态的安全集合包含及循环对应','任务2/5/6'),
            (6,'缺推导','全起法覆盖或无损变换','任务5/汇总'),
            (7,'缺复核','本席新增条件证明和接口的独立复核','独立复核席')]],
      'for_owner':[],'for_owner_reason':'现行规则与owner裁定给出动作事实；剩余为构造、推导和复核。',
      'default_start_certified':False,'full_layout_certified':False,
      'full_start_search_lossless':False,'search_losslessness_status':'unproved',
    }
    write(O/'调试后状态.json',data)
    write(E/'势函数与条件算术.json',{'recipes':RECIPES,'weights':WEIGHTS,
      'recipe_increases':weights,'candidates':candidate_results,
      'scope':'有限停止势函数与条件数字，不是内核或整厂运行证书'})
    print('GENERATED: 调试后状态.json; 势函数与条件算术.json')

if __name__=='__main__':
    main()
