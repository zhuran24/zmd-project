use topology::{load, validate, Status};
const INPUT: &str = include_str!("../../../数据/候选B/contract.json");
fn changed(f: impl FnOnce(&mut serde_json::Value)) -> topology::Contract {
    let mut v: serde_json::Value = serde_json::from_str(INPUT).unwrap();
    f(&mut v);
    load(&v.to_string()).unwrap()
}
fn rejects(c: &topology::Contract, prefix: &str) {
    let r = validate(c);
    assert!(
        r.checks
            .iter()
            .any(|x| x.status == Status::Fail && x.name.starts_with(prefix)),
        "没有拦截 {prefix}"
    );
}
#[test]
fn candidate_passes_static_only() {
    let c = load(INPUT).unwrap();
    let r = validate(&c);
    assert_eq!(
        r.failures(),
        0,
        "{:#?}",
        r.checks
            .iter()
            .filter(|c| c.status == Status::Fail)
            .collect::<Vec<_>>()
    );
    assert!(r
        .checks
        .iter()
        .any(|c| c.name == "正式条目/轮询均分" && c.status == Status::Unknown));
    assert!(c
        .logical_feeds
        .iter()
        .all(|e| e.proven_actual_rate.is_none()));
}
#[test]
fn changed_channel_breaks_local_balance() {
    rejects(
        &changed(|v| v["logical_feeds"][0]["planned_rate"]["value"] = "19/20".into()),
        "逐机配方守恒/",
    );
}
#[test]
fn wrong_target_recipe_is_rejected() {
    rejects(
        &changed(|v| v["logical_feeds"][0]["target_recipe"] = "粉碎-源矿".into()),
        "契约/送料引用/",
    );
}
#[test]
fn overload_is_exact_and_not_rounded() {
    rejects(
        &changed(|v| {
            v["logical_feeds"][0]["planned_rate"]["value"] =
                "100000000000000000000000000000000000001/100000000000000000000000000000000000000"
                    .into()
        }),
        "端口速率/",
    );
}
#[test]
fn shared_port_rates_are_summed() {
    rejects(
        &changed(|v| {
            let p = v["logical_feeds"][0]["source_port"].clone();
            let s = v["logical_feeds"][0]["source"].clone();
            v["logical_feeds"][1]["source"] = s;
            v["logical_feeds"][1]["source_port"] = p;
        }),
        "端口速率/取货/",
    );
}
#[test]
fn fabricated_capacity_cannot_relax_rule() {
    rejects(
        &changed(|v| v["machines"][0]["input_ports"]["value"] = "99".into()),
        "端口数/",
    );
}
#[test]
fn false_actual_rate_is_not_a_certificate() {
    rejects(
        &changed(|v| {
            v["logical_feeds"][0]["proven_actual_rate"] =
                serde_json::json!({"value":"1","category":"实测"})
        }),
        "契约/实际速率/",
    );
}
#[test]
fn duplicate_source_identity_is_rejected() {
    rejects(
        &changed(|v| {
            for i in [0, 1] {
                v["sources"][i]["identity"] = serde_json::json!({"status":"已指定","kind":"协议核心","side":null,"index":{"value":"1","category":"候选"}});
            }
        }),
        "来源端口身份/",
    );
}
#[test]
fn zero_denominator_and_missing_fields_fail_loading() {
    for mutation in ["zero", "missing", "float", "category"] {
        let mut v: serde_json::Value = serde_json::from_str(INPUT).unwrap();
        match mutation {
            "zero" => v["logical_feeds"][0]["planned_rate"]["value"] = "1/0".into(),
            "missing" => {
                v["logical_feeds"][0]
                    .as_object_mut()
                    .unwrap()
                    .remove("proven_actual_rate");
            }
            "float" => v["logical_feeds"][0]["planned_rate"]["value"] = 0.6.into(),
            _ => v["logical_feeds"][0]["planned_rate"]["category"] = "已认证".into(),
        };
        assert!(load(&v.to_string()).is_err(), "{mutation}");
    }
}
#[test]
fn false_fanout_certification_is_rejected() {
    rejects(
        &changed(|v| v["fanouts"][0]["certification"] = "已认证".into()),
        "扇出/计划分类/",
    );
}
#[test]
fn wrong_target_cannot_redefine_task() {
    rejects(
        &changed(|v| v["targets"]["精选荞愈胶囊"]["value"] = "3/5".into()),
        "目标/精选荞愈胶囊",
    );
}
#[test]
fn unsupported_routing_fails_closed() {
    rejects(
        &changed(|v| v["logical_feeds"][0]["via"]["merger"] = true.into()),
        "契约/运输占位/",
    );
}
#[test]
fn multi_material_obligations_cannot_disappear() {
    rejects(
        &changed(|v| v["machines"][120]["multi_material"] = serde_json::Value::Null),
        "契约/多料栏/",
    );
}
#[test]
fn zero_rate_does_not_count_as_live_channel() {
    rejects(
        &changed(|v| v["logical_feeds"][0]["planned_rate"]["value"] = "0".into()),
        "端口速率/记录/",
    );
}
#[test]
fn every_formal_constraint_has_coverage_row() {
    let r = validate(&load(INPUT).unwrap());
    let cat: serde_json::Value =
        serde_json::from_str(include_str!("../../../数据/正式静态目录.json")).unwrap();
    assert_eq!(cat["constraints"].as_array().unwrap().len(), 56);
    for rule in cat["constraints"].as_array().unwrap() {
        assert!(r
            .checks
            .iter()
            .any(|c| c.name == format!("正式条目/{}", rule["name"].as_str().unwrap())));
    }
}

#[test]
fn dedicated_ports_cannot_fork_without_transport_model() {
    rejects(
        &changed(|v| {
            let port = v["logical_feeds"][109]["source_port"].clone();
            v["logical_feeds"][111]["source_port"] = port;
        }),
        "契约/端口身份/",
    );
}

#[test]
fn legacy_channels_and_storage_shortcut_are_rejected() {
    let mut v: serde_json::Value = serde_json::from_str(INPUT).unwrap();
    v["channels"] = v.as_object_mut().unwrap().remove("logical_feeds").unwrap();
    assert!(load(&v.to_string()).is_err());
    for storage in [serde_json::Value::Null, true.into(), false.into()] {
        let mut v: serde_json::Value = serde_json::from_str(INPUT).unwrap();
        v["logical_feeds"][0]["via"]["storage"] = storage;
        assert!(load(&v.to_string()).is_err());
    }
}

#[test]
fn logical_feed_ids_cannot_be_physical_or_buffer_channels() {
    for prefix in ["C", "PC", "BC", "LF"] {
        rejects(
            &changed(|v| v["logical_feeds"][0]["id"] = prefix.into()),
            "契约/送料身份/",
        );
    }
}

#[test]
fn storage_split_counts_both_sides_and_deduplicates_item_rows() {
    // 合成结构：源→箱、箱→目标。仅测试计数投影，不声称箱体运行可行。
    let c = load(INPUT).unwrap();
    let mut first = c.logical_feeds[0].clone();
    let mut second = first.clone();
    first.target = "BOX".into();
    first.target_port = "BOX:in:1".into();
    second.source = "BOX".into();
    second.source_port = "BOX:out:1".into();
    assert_eq!(
        topology::feed_interface_counts(&[first.clone(), second.clone()]),
        (2, 2)
    );
    let mut other_item = first.clone();
    other_item.item = "另一物品".into();
    assert_eq!(
        topology::feed_interface_counts(&[first, second, other_item]),
        (2, 2)
    );
    assert_eq!(
        topology::feed_interface_counts(&c.logical_feeds),
        (315, 315)
    );
}

#[test]
fn catalog_unit_properties_match_formal_reference_values() {
    // 固定对照值只在回归测试保留；运行代码及转换脚本均从目录读取。
    let cat: serde_json::Value =
        serde_json::from_str(include_str!("../../../数据/正式静态目录.json")).unwrap();
    let expected = [
        (
            "粉碎机",
            3,
            3,
            3,
            3,
            true,
            vec![
                ("input", Some(1), Some(50)),
                ("output", Some(1), Some(50)),
                ("buffer", Some(1), None),
            ],
        ),
        (
            "精炼炉",
            3,
            3,
            3,
            3,
            true,
            vec![
                ("input", Some(1), Some(50)),
                ("output", Some(1), Some(50)),
                ("buffer", Some(1), None),
            ],
        ),
        (
            "配件机",
            3,
            3,
            3,
            3,
            true,
            vec![
                ("input", Some(1), Some(50)),
                ("output", Some(1), Some(50)),
                ("buffer", Some(1), None),
            ],
        ),
        (
            "塑形机",
            3,
            3,
            3,
            3,
            true,
            vec![
                ("input", Some(1), Some(50)),
                ("output", Some(1), Some(50)),
                ("buffer", Some(1), None),
            ],
        ),
        (
            "种植机",
            5,
            5,
            5,
            5,
            true,
            vec![
                ("input", Some(1), Some(50)),
                ("output", Some(1), Some(50)),
                ("buffer", Some(1), None),
            ],
        ),
        (
            "采种机",
            5,
            5,
            5,
            5,
            true,
            vec![
                ("input", Some(1), Some(50)),
                ("output", Some(1), Some(50)),
                ("buffer", Some(1), None),
            ],
        ),
        (
            "研磨机",
            6,
            4,
            6,
            6,
            true,
            vec![
                ("input", Some(2), Some(50)),
                ("output", Some(1), Some(50)),
                ("buffer", Some(1), None),
            ],
        ),
        (
            "封装机",
            6,
            4,
            6,
            6,
            true,
            vec![
                ("input", Some(2), Some(50)),
                ("output", Some(1), Some(50)),
                ("buffer", Some(1), None),
            ],
        ),
        (
            "灌装机",
            6,
            4,
            6,
            6,
            true,
            vec![
                ("input", Some(2), Some(50)),
                ("output", Some(1), Some(50)),
                ("buffer", Some(1), None),
            ],
        ),
        (
            "协议核心",
            9,
            9,
            14,
            6,
            false,
            vec![("warehouse", None, Some(80000))],
        ),
        (
            "传送带",
            1,
            1,
            1,
            1,
            false,
            vec![("transport", Some(1), Some(1))],
        ),
        (
            "桥接器",
            1,
            1,
            2,
            2,
            false,
            vec![("vertical", Some(1), None), ("horizontal", Some(1), None)],
        ),
        (
            "物品准入口",
            1,
            1,
            1,
            1,
            false,
            vec![("transport", Some(1), Some(1))],
        ),
        (
            "分流器",
            1,
            1,
            1,
            3,
            false,
            vec![("transport", Some(1), Some(1))],
        ),
        (
            "汇流器",
            1,
            1,
            3,
            1,
            false,
            vec![("transport", Some(1), Some(1))],
        ),
        (
            "协议储存箱",
            3,
            3,
            3,
            3,
            true,
            vec![("storage", Some(6), Some(50))],
        ),
        ("仓库取货口", 3, 1, 0, 1, false, vec![]),
        ("供电桩", 2, 2, 0, 0, false, vec![]),
    ];
    let units = cat["units"].as_array().unwrap();
    assert_eq!(units.len(), expected.len());
    for (id, w, h, ins, outs, power, slots) in expected {
        let found: Vec<_> = units.iter().filter(|u| u["id"] == id).collect();
        assert_eq!(found.len(), 1, "{id}");
        let u = found[0];
        for (v, n) in [
            (&u["dimensions"]["width"], w),
            (&u["dimensions"]["height"], h),
            (&u["area"], w * h),
            (&u["ports"]["input_count"], ins),
            (&u["ports"]["output_count"], outs),
        ] {
            assert_eq!(v["value"], n.to_string(), "{id}");
        }
        assert_eq!(u["power_required"], power);
        let actual = u["inventory"].as_array().unwrap();
        assert_eq!(actual.len(), slots.len(), "{id}");
        for (slot, (role, count, cap)) in actual.iter().zip(slots) {
            assert_eq!(slot["role"], role);
            for (key, n) in [("count", count), ("capacity", cap)] {
                if let Some(n) = n {
                    assert_eq!(slot[key]["value"], n.to_string(), "{id}/{role}");
                } else {
                    assert!(slot[key].is_null(), "{id}/{role}");
                }
            }
        }
        for layout in u["ports"]["layouts"].as_array().unwrap() {
            let mut seen = std::collections::BTreeSet::new();
            let mut counts = [0, 0];
            for edge in layout.as_array().unwrap() {
                let side = edge["side"].as_str().unwrap();
                assert!(["north", "south", "east", "west"].contains(&side));
                for pos in edge["positions"].as_array().unwrap() {
                    let p: i32 = pos["value"].as_str().unwrap().parse().unwrap();
                    assert!(
                        p >= 0
                            && p < if ["north", "south"].contains(&side) {
                                w
                            } else {
                                h
                            }
                    );
                    assert!(seen.insert((side, p)));
                    counts[if edge["role"] == "input" { 0 } else { 1 }] += 1;
                }
            }
            assert_eq!(counts, [ins, outs], "{id}");
        }
    }
    for recipe in cat["recipes"].as_array().unwrap() {
        assert!(units
            .iter()
            .any(|u| u["id"] == recipe["kind"] && u["family"] == "manufacturing"));
    }
}

#[test]
fn catalog_port_edges_match_formal_reference_layouts() {
    let cat: serde_json::Value =
        serde_json::from_str(include_str!("../../../数据/正式静态目录.json")).unwrap();
    type Edge = (String, String, Vec<i32>);
    fn edge(side: &str, role: &str, positions: Vec<i32>) -> Edge {
        (side.into(), role.into(), positions)
    }
    for u in cat["units"].as_array().unwrap() {
        let id = u["id"].as_str().unwrap();
        let expected: Vec<Vec<Edge>> = match id {
            "协议核心" => vec![vec![
                edge("south", "input", (1..8).collect()),
                edge("north", "input", (1..8).collect()),
                edge("west", "output", vec![1, 4, 7]),
                edge("east", "output", vec![1, 4, 7]),
            ]],
            "仓库取货口" => vec![vec![edge("north", "output", vec![1])]],
            "供电桩" => vec![vec![]],
            "传送带" => ["north", "east", "west"]
                .iter()
                .map(|s| vec![edge("south", "input", vec![0]), edge(s, "output", vec![0])])
                .collect(),
            "桥接器" => [("south", "north"), ("north", "south")]
                .iter()
                .flat_map(|(a, b)| {
                    [("west", "east"), ("east", "west")]
                        .iter()
                        .map(move |(c, d)| {
                            vec![
                                edge(a, "input", vec![0]),
                                edge(b, "output", vec![0]),
                                edge(c, "input", vec![0]),
                                edge(d, "output", vec![0]),
                            ]
                        })
                })
                .collect(),
            "分流器" => vec![vec![
                edge("south", "input", vec![0]),
                edge("north", "output", vec![0]),
                edge("east", "output", vec![0]),
                edge("west", "output", vec![0]),
            ]],
            "汇流器" => vec![vec![
                edge("south", "input", vec![0]),
                edge("east", "input", vec![0]),
                edge("west", "input", vec![0]),
                edge("north", "output", vec![0]),
            ]],
            _ => {
                let n = match id {
                    "物品准入口" => 1,
                    "种植机" | "采种机" => 5,
                    "研磨机" | "封装机" | "灌装机" => 6,
                    _ => 3,
                };
                vec![vec![
                    edge("south", "input", (0..n).collect()),
                    edge("north", "output", (0..n).collect()),
                ]]
            }
        };
        let actual: Vec<Vec<Edge>> = u["ports"]["layouts"]
            .as_array()
            .unwrap()
            .iter()
            .map(|l| {
                l.as_array()
                    .unwrap()
                    .iter()
                    .map(|e| {
                        edge(
                            e["side"].as_str().unwrap(),
                            e["role"].as_str().unwrap(),
                            e["positions"]
                                .as_array()
                                .unwrap()
                                .iter()
                                .map(|p| p["value"].as_str().unwrap().parse().unwrap())
                                .collect(),
                        )
                    })
                    .collect()
            })
            .collect();
        assert_eq!(actual, expected, "{id}");
    }
}

#[test]
fn numeric_categories_have_field_semantics() {
    for field in ["source_domain", "machine_ports", "rate", "target", "fanout"] {
        rejects(
            &changed(|v| match field {
                "source_domain" => v["source_domain"]["left"]["category"] = "算术推论".into(),
                "machine_ports" => v["machines"][0]["output_ports"]["category"] = "条文直引".into(),
                "rate" => v["logical_feeds"][0]["planned_rate"]["category"] = "实测".into(),
                "target" => v["targets"]["高容谷地电池"]["category"] = "候选".into(),
                _ => v["fanouts"][0]["batch_size"]["category"] = "候选".into(),
            }),
            "契约/数字类别",
        );
    }
}

#[test]
fn same_item_multiport_and_mixed_recipe_obligations_are_required() {
    let c = load(INPUT).unwrap();
    assert_eq!(
        c.machines
            .iter()
            .filter(|m| m.multi_material.is_some())
            .count(),
        43
    );
    for id in ["M152", "M153", "M154", "M155", "M156"] {
        rejects(
            &changed(|v| {
                let m = v["machines"]
                    .as_array_mut()
                    .unwrap()
                    .iter_mut()
                    .find(|m| m["id"] == id)
                    .unwrap();
                m["multi_material"] = serde_json::Value::Null;
            }),
            &format!("契约/多料栏/{id}"),
        );
    }
    rejects(
        &changed(|v| {
            let plan = serde_json::json!({"recipe":"粉碎-蓝铁块","planned_batch_rate":{"value":"1/2","category":"候选"},"planned_mean_batch_interval":{"value":"2","category":"候选"}});
            v["machines"][0]["recipes"]
                .as_array_mut()
                .unwrap()
                .push(plan);
        }),
        "契约/多料栏/M000",
    );
}

#[test]
fn full_speed_and_transport_projection_are_explicit_but_not_certified() {
    let c = load(INPUT).unwrap();
    assert_eq!(
        c.logical_feeds
            .iter()
            .filter(|e| e.planned_full_speed)
            .count(),
        300
    );
    let r = validate(&c);
    let bound = r
        .checks
        .iter()
        .find(|x| x.name == "运输端口收支/派生运输下限")
        .unwrap();
    assert_eq!(bound.status, Status::Unknown);
    assert!(bound.detail.contains("315+E≥315"));
    assert!(r
        .checks
        .iter()
        .find(|x| x.name == "满速独占/计划适用集合")
        .unwrap()
        .detail
        .contains("非矿石 248"));
    assert!(r
        .checks
        .iter()
        .find(|x| x.name == "契约/专用端口双射恒等式")
        .unwrap()
        .detail
        .contains("冗余自查"));
    for name in ["接通先后", "分叉分支", "传输相位", "判定先后"] {
        let row = r
            .checks
            .iter()
            .find(|x| x.name == format!("正式条目/{name}"))
            .unwrap();
        assert!(row.detail.contains("目标须对其每种取值都达成"));
        assert!(row.detail.contains("据："));
    }
    rejects(
        &changed(|v| v["logical_feeds"][0]["planned_full_speed"] = false.into()),
        "满速独占/计划标记/",
    );
}

#[test]
fn storage_relay_cannot_double_material_origin_flow() {
    let mut c = load(INPUT).unwrap();
    let first = c.logical_feeds[0].clone();
    let item = first.item.clone();
    let mut inbound = first.clone();
    inbound.planned_rate.value /= num_bigint::BigInt::from(2);
    inbound.target = "BOX".into();
    let mut outbound = inbound.clone();
    outbound.source = "BOX".into();
    outbound.target = first.target;
    c.logical_feeds = vec![inbound.clone(), outbound];
    assert_eq!(
        topology::material_origin_flow(&c)[&item],
        inbound.planned_rate.value
    );
    // 分段投影可算不代表带箱格式已支持。
    rejects(&c, "契约/送料引用/");
}

#[test]
fn invalid_ore_machine_is_not_counted_as_dedicated() {
    let c = changed(|v| {
        let target = v["logical_feeds"]
            .as_array()
            .unwrap()
            .iter()
            .find(|e| e["source"].as_str().unwrap().starts_with("ORE"))
            .unwrap()["target"]
            .clone();
        let m = v["machines"]
            .as_array_mut()
            .unwrap()
            .iter_mut()
            .find(|m| m["id"] == target)
            .unwrap();
        m["recipes"][0]["planned_batch_rate"]["value"] = "1/2".into();
    });
    rejects(&c, "矿石分流与专机/定义计数");
    rejects(&c, "箱体过站/已知流量投影");
}

#[test]
fn plant_storage_condition_uses_current_machine_count() {
    let c = changed(|v| {
        let mut m = v["machines"]
            .as_array()
            .unwrap()
            .iter()
            .find(|m| m["kind"] == "种植机")
            .unwrap()
            .clone();
        m["id"] = "EXTRA_GROWER".into();
        v["machines"].as_array_mut().unwrap().push(m);
        let e = v["logical_feeds"]
            .as_array_mut()
            .unwrap()
            .iter_mut()
            .find(|e| e["target"] == "CORE")
            .unwrap();
        e["item"] = "荞花".into();
    });
    let r = validate(&c);
    assert_eq!(
        r.checks
            .iter()
            .find(|x| x.name == "矿系不入库/计划")
            .unwrap()
            .status,
        Status::Pass
    );
    assert!(r.failures() > 0); // 只核条件守卫，变异不是达标候选。
}

#[test]
fn catalog_is_checked_against_live_formal_sources() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap();
    let result = std::process::Command::new("python")
        .env("PYTHONDONTWRITEBYTECODE", "1")
        .arg(root.join("数据/工具/formal_catalog.py"))
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
}
