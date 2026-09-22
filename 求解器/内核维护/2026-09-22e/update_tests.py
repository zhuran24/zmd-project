from pathlib import Path
R = Path(__file__).resolve().parents[2]
p = R/'crates/topology/tests/validation.rs'
s = p.read_text().replace('cat["constraints"].as_array().unwrap().len(), 71', 'cat["constraints"].as_array().unwrap().len(), 72')
a = s.index('#[test]\nfn plant_storage_condition_uses_current_machine_count()')
b = s.index('\nfn check_catalog_against_sources', a)
s = s[:a] + '''#[test]
fn core_storage_plan_accepts_only_products_at_any_grower_count() {
    let plants = ["荞花", "砂叶", "荞花种子", "砂叶种子", "荞花粉末", "砂叶粉末", "细磨荞花粉末"];
    let minerals = ["蓝铁矿", "源矿", "蓝铁块", "蓝铁粉末", "源石粉末", "致密蓝铁粉末", "致密源石粉末", "钢块", "钢制零件", "钢质瓶"];
    let products = ["高容谷地电池", "精选荞愈胶囊"];
    for growers in [32, 33] {
        for item in plants.iter().chain(minerals.iter()).chain(products.iter()) {
            let c = changed(|v| {
                if growers == 33 {
                    let mut m = v["machines"].as_array().unwrap().iter()
                        .find(|m| m["kind"] == "种植机").unwrap().clone();
                    m["id"] = "EXTRA_GROWER".into();
                    v["machines"].as_array_mut().unwrap().push(m);
                }
                let e = v["logical_feeds"].as_array_mut().unwrap().iter_mut()
                    .find(|e| e["target"] == "CORE").unwrap();
                e["item"] = (*item).into();
            });
            assert_eq!(c.machines.iter().filter(|m| m.kind == "种植机").count(), growers);
            let r = validate(&c);
            let check = r.checks.iter().find(|x| x.name == "矿系不入库/计划").unwrap();
            assert_eq!(check.status, if products.contains(item) { Status::Pass } else { Status::Fail },
                "growers={growers}, item={item}");
            // 核心计划结果不能替代实际循环的两途径与全参数证书。
            for name in ["矿系不入库", "非成品零入库", "传输按仓库余量判定"] {
                assert_eq!(r.checks.iter().find(|x| x.name == format!("正式条目/{name}")).unwrap().status,
                    Status::Unknown);
            }
        }
    }
}
''' + s[b:]
p.write_text(s)
