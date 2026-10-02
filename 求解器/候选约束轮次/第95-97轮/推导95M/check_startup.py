"""重跑分次放料反例；两份独立引擎均按临时规则1触发。

纯带的采种单元和缺砂叶粉末的研磨机是局部接法。
完整几何来源见复核93F/local_geometry.json；不声称是达标整厂。
"""
from pathlib import Path
import json
from plant_a import Plant
from plant_b import fresh,tick
from verify_plant import assert_equal
from repaired_startup import trial

OUT=Path(__file__).resolve().parent


def main():
    lengths=(7,13,31,5,5,5)
    # Build machines first; build road heads CA,CB,AC,BK,K0,K1 in that
    # order, then their interiors, then their tails in the same order.
    # All six lengths exceed one. This makes the ranks below realizable.
    a,b=Plant(lengths,order=('C','A','B','K')),fresh(lengths)
    assert a.add('A',50)
    b['machines'][0][0]=50
    first_nonempty=first_full=None
    for _ in range(6000):
        a.step();tick(b,machines=(2,0,1,3));assert_equal(a,b)
        if a.machines['C'].stock and first_nonempty is None:first_nonempty=a.t
        if a.machines['C'].stock==50 and first_full is None:first_full=a.t
    assert first_full is not None
    assert not a.add('C',50)
    frozen=a.state()
    keys=('phi2','stock','output','batch','route_counts','sink','sent','arrivals')
    for _ in range(80):
        a.step();tick(b,machines=(2,0,1,3));assert_equal(a,b)
        assert all(a.state()[k]==frozen[k] for k in keys)
    fixed=[]
    for seed in range(12):
        sizes=(7,13,31,5,5,5) if seed<4 else (48,7,49,5,3,3) if seed<8 else (51,7,49,5,3,3)
        fixed.append(trial(9500+seed,sizes))
    # Both storage assignments are held while A,C are off. A new rebuilding
    # permutation only changes channel ranks/history, never these items.
    result={'rule':'临时规则1实际可送者触发；路径均为纯带',
            'unrepaired':{'manufacturing_order':['C','A','B','K'],
                          'build_order_rule':'先制造单位，后按CA,CB,AC,BK,K0,K1建各路首格，再建中间格，最后同序建各路末格',
                          'first_C_nonempty_after_steps':first_nonempty,
                          'first_C_full_after_steps':first_full,'cannot_add_50':True,
                          'stationary_inventory':frozen,'state_checks':6080},
            'repaired':fixed,'all_checks_pass':True,
            'limit':'局部构型与关闭期间实施核对，不证明整厂速率'}
    (OUT/'startup_checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'first_C_full_after_steps':first_full,'repaired_cases':len(fixed),'all_checks_pass':True},ensure_ascii=False))


if __name__=='__main__':main()
