"""输出§2.0：两份独立有限参考的真实PC出库账；未支持无线不伪造通用验收。"""
from collections import defaultdict
PRODUCTS=('高容谷地电池','精选荞愈胶囊')
FLOWS=('core_inbound','wireless_inbound','port_outbound','external_supply','player_withdrawal','representative_adjustment')
def quantity(n):return dict(value=str(n),category='算术推论')
def warehouse_ledger(data,events,state):
    ledger={k:[] for k in FLOWS}
    channels={c['id']:c for c in data['layout']['physical_channels']}
    assignments={r['port']:r['slot'] for r in data['settings']['warehouse_assignments']}
    for movement in state['semantic_context']['tick_context']['value']['movements']:
        channel=channels[movement['channel']];port=channel['source_port']
        if port in assignments:
            ledger['port_outbound'].append(dict(event=movement['event'],channel=movement['channel'],port=port,slot=assignments[port],item=movement['item'],quantity=quantity(1)))
    totals=defaultdict(lambda:{k:0 for k in FLOWS})
    for p in PRODUCTS:totals[p]
    for field in FLOWS:
        for row in ledger[field]:totals[row['item']][field]+=int(row['quantity']['value'])
    ledger['totals']=[dict(item=item,**{k:quantity(v) for k,v in amounts.items()},actual_inbound=quantity(amounts['core_inbound']+amounts['wireless_inbound'])) for item,amounts in sorted(totals.items())]
    return ledger
