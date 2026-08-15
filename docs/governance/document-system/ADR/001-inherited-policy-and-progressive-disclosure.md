# DOC-ADR-001：目录继承 policy 与渐进式上下文

状态：Accepted
日期：2026-08-11

## 背景

项目已有数百份 tracked 文档和大量本地证据。把完整维护手册塞给每次操作，会消耗 agent 的工作上下文；只给裸命令，又无法让 agent 理解规则保护的概念，并在新情形下正确类推。

逐文件 front matter 会把相同规则复制数百次，重建另一种漂移。单一中央分类表离目标文件太远，目录移动和局部例外也难以理解。

## 决定

采用目录继承的 `DOC_POLICY.json`：

- 目录声明多数成员的默认契约；
- 少量 rule 声明局部例外；
- `docctl` 从根到目标路径合并有效规则；
- 只有 Git 可见的 policy 参与治理，被 ignore 的本地同名文件没有 authority；
- 操作卡同时给出动作、原则短因、写入源和检查；
- 完整解释通过 invariant、architecture 和 ADR 坐标按需读取；
- dossier lifecycle 和稳定知识 ID 提供动态语义，不复制完整报告。

局部策略默认只能提高 mutation 保护强度。降低保护必须在发生放松的同一 overlay 中显式引用当前 owner decision，而且该 decision 必须以 `scope_boundary` 为 authority effect，并在 scope 中包含 `document-system` 或 `document-policy`。祖先 decision 不会变成后代可继承的通行证。

selector 的优先级由类型和目标本身决定，不由声明顺序决定。`prefix` 必须以 `/` 结尾；`paths` 中无关成员的长度不能改变某个已匹配目标的优先级。

## 结果

优点：

- 普通文件不增加 front matter；
- 规则与目录共置；
- agent 每次只加载相关上下文；
- 新目录可以继承已有语义；
- 全仓 doctor 仍能计算完整覆盖。

代价：

- resolver 成为承重工具，必须有恢复路径和测试；
- policy 继承和 glob 语义必须保持明确；
- 跨目录移动需要同时比较旧、新路径契约。

## 未采用方案

- 每次注入完整维护指南：注意力成本过高。
- 只保留操作命令：无法安全类推，也无法维护框架。
- 每文件 YAML front matter：重复多、易漂移、正文噪声大。
- 只用中央巨型 JSON：局部可发现性差，目录结构不再携带维护知识。
