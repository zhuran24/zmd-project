# 块六补充原文核查：机器人任务与运动规划

用途：核查任务与运动规划论文怎样以几何可行性检验约束离散候选，供静态工厂布局的构造与修复使用。这里只记录论文机制及适用边界，不把机器人规划成功当成工厂达标证据。

## 研究问题与检索记录

- 离散候选的低层检验失败后，返回的是可证明约束，还是基于有限搜索的暂时排除？检索词：incremental task and motion planning、motion feasibility constraints、failed motion plan、geometric feedback。
- 分层构造怎样减少同时求解的变量，又怎样回溯修复？检索词：logic-geometric programming、hierarchical task and motion planning、plan skeleton、optimistic adaptive planning。
- 连续采样器和符号求解器的接口能否改为端口、布线与逐步模拟器接口？检索词：PDDLStream、blackbox samplers、certified facts、factored task and motion planning。

网页搜索来源均为 web 搜索工具；未调用 OpenAlex search。实际提交的全部查询如下（按提交批次）：

1. `Dantam Kingston Chaudhuri Kavraki Incremental Task and Motion Planning 2018 constraints pdf`；`Toussaint Logic Geometric Programming 2015 pdf`；`Garrett Kaelbling Lozano Perez PDDLStream 2020 pdf`；`Garrett Chitnis Holladay Kim Silver Kaelbling Lozano Perez Integrated Task and Motion Planning 2021 survey pdf`。来源：web search，查找种子论文原文。
2. `"Logic-Geometric Programming" "2015" "ijcai" pdf`；`"PDDLStream" "2020" "doi" paper`；`"Incremental task and motion planning" "failed" constraints Dantam`；`"Hierarchical Task and Motion Planning in the Now" 2011 pdf`。来源：web search，查官方论文页与作者稿。
3. `Toussaint "Logic-Geometric" "arxiv"`；`"Logic-Geometric Programming" "10." DOI`；`"PDDLStream" arxiv 2020 Garrett`；`"Integrated Task and Motion Planning" Garrett "learning" "constraint" survey`。来源：web search，核标识与可下载版本。
4. `"Logic-Geometric Programming" "1930" "DOI"`；`"Logic-Geometric Programming" "2832415"`；`"Logic-Geometric Programming" Toussaint 2015 arxiv identifier`。来源：web search；未找到 LGP 2015 的 DOI/arXiv。改用精确 OpenAlex `W2403069916` 作品接口核题名和年份，接口仅给出 OpenAlex/MAG 标识，不把数字2832415声称为该论文 DOI。

下载直接来自 Kavraki Lab、IJCAI、arXiv、MIT 作者页面。精确标识元数据补核用 OpenAlex `/works/W2403069916` 和 Crossref `/works/{DOI}`，均非关键词搜索。ICAPS 官方 PDF 下载遇 SSL 错误，改读 arXiv v5；该替代版本的页码已单独标出。

## 游戏规则对应依据

规则文件：`/home/zhuran24/zmd-research-fresh/《明日方舟：终末地》游戏规则.txt`。

- 几何占用：原句「格：基地划分成的方格，每个单位都正好占满若干个格」「基地：所有单位都建在基地内，70×70 格」。
- 自动连接：原句「通道：物品在两个物品格之间移动的路径；不同单位的取货端口与存货端口相对紧贴、且至少一方是运输单位时，自动形成通道」。
- 状态运行：原句「判定顺序：每步开始时，所有单位同时进行结束制造判定；随后各汇流器进行输入判定，元件的各组按级别从高到低依次进行移动判定；随后非元件按建成的先后依次选取，每个非元件的各组按级别从高到低依次进行移动判定；所有移动判定结束后，所有单位同时进行开始制造判定，随后这一步结束」。
- 顺序不确定：原句「蓝图：一次建造一组单位，逐个建成；传送带均在非传送带单位之后建成，两类各自内部的建成先后无法确定」。
- 时间和缓存：原句「步：基地每 1/8 tick 为一步，玩家的操作只能在两步之间」「滞留：物品在运输单位的物品格中必须停留至少 1 tick」。

这几类 TAMP 论文主要是求一个可执行有限动作序列。块六最终必须额外以本题内核验证静态布局，并满足所有可到达循环态的长期吞吐，不能用一条机器人路径成功替代。

## 原文证据

- [DOI:10.1177/0278364918761570] Dantam、Kingston、Chaudhuri、Kavraki 2018，An Incremental Constraint-Based Framework for Task and Motion Planning（IJRR 37(10), 1134–1151）。解的问题：离散搬运、堆叠、推托盘动作序列必须能被碰撞自由运动具体化。方法：IDTMP 的离散层用增量 SMT；低层失败后加约束。最弱约束式(3)排除该整条任务序列；§7.3 式(5)把同一状态下失败的动作推广到所有步骤；§7.4 式(6)只保留碰撞检查发现的阻挡物所在位置，把失败推广到一组状态。增加任务步骤及运动采样时限时撤掉这些约束并重试，避免把运动超时误判成不可能；缓存和泛化的完备性还需要 §7.1 的后配置连通假设。规模：§8.2/Fig.7 的对象数实验到约30个对象，每个对象数做5次试验；作者称几十个对象的任务层约1秒，不能解读为完整运动计划用时。§8.2/Fig.8 到10个任务动作，任务层约10秒；§8.3/Fig.9 研究约8个阻挡物，碰撞泛化减少运动尝试。对应本题：把整厂离散拓扑或机器/端口/带子选择当任务候选，把窗口内几何布线与逐步模拟当具体化检查；碰撞或堵塞反例中的局部参与单元可用于确定修复窗口。游戏规则的自动形成通道意味着检查必须同时考虑相邻端口。不对应的：TAMP 求一条有限动作路径，本题求一张固定布局在所有可达循环态的长期吞吐；运动采样的连通假设未在本题证明。模拟得到一个失败历史不自动给出对任意上下文都成立的布线割。对本题有什么用：用于 L 的候选—检验—局部回传接口；分别存「内核反例」「限时未解」「已证明不可行」三类反馈，只对前两类暂时调整搜索，不能提升 U。依据：原文 PDF §5.2，PDF pp.9–10；§7.1–7.4，PDF pp.12–14；§8.1–8.3，PDF pp.14–16。原文：[Kavraki Lab PDF](https://www.kavrakilab.org/publications/dantam2018incremental-tmp.pdf)，本地 `dantam2018.pdf`/`dantam2018.txt`；DOI：[出版社记录](https://journals.sagepub.com/doi/abs/10.1177/0278364918761570)。这里页码是20页作者稿的 PDF 页码，不用期刊页码倒推。

- [W2403069916] Toussaint 2015，Logic-Geometric Programming: An Optimization-Based Approach to Combined Task and Motion Planning（IJCAI, 1930–1936）。解的问题：同时选择离散操作序列与连续几何，优化最后搭出的结构高度和稳定性。方法：把符号序列作为非线性程序约束的开关；三层检查依次为最终配置、操作关键帧、全轨迹。MCTS 展开符号序列，先用最终配置优化评价，再对最优候选做关键帧和全路径优化；前两层省去完整轨迹约束，只是更便宜的搜索指引。规模：§5/Fig.3(a) 最终配置优化试到100个物体，作者称一次优化小于1秒；这不是100物体完整计划的成功规模。§5/Fig.3(b) 完整轨迹举25个物体、50次操作、每次20个时间步，合计1000时间步、15维轨迹；作者的完整路径结论为最多50次操作的局部近似最优。对应本题：适合把「物料生产图/模块选择→机器与端口几何→带子详细连接→运行检验」做分级，先便宜筛候选再交完整内核；最终几何目标可类比最大空矩形目标。不对应的：本文变量连续，布局是整数格；本文控制代价和静态稳定性没有容量1运输格、轮询、反压或所有循环态吞吐。局部非线性优化失败不必然证明约束不可行；本文没有提供本题的局部反例割。对本题有什么用：用于 L 的多级构造管线，保留候选序列/拓扑但推迟昂贵布线与运行检查；100物体结果仅是便宜层规模提示，不可据此承诺217台机器整厂可解。依据：§3，pp.1932–1933；§4.1–4.3，pp.1933–1934；§5及 Fig.3，pp.1934–1935；§6，p.1936。原文：[IJCAI PDF](https://www.ijcai.org/Proceedings/15/Papers/274.pdf)，本地 `toussaint2015.pdf`/`toussaint2015.txt`。标识：[OpenAlex精确作品接口](https://api.openalex.org/works/W2403069916)，本地 `toussaint2015_openalex.json`；该记录没有 DOI 或 arXiv 字段，不补造标识。

- [DOI:10.1609/icaps.v30i1.6739；arXiv:1802.08705v5] Garrett、Lozano-Pérez、Kaelbling 2020，PDDLStream: Integrating Symbolic Planners and Blackbox Samplers via Optimistic Adaptive Planning（ICAPS 30, 440–448）。解的问题：符号动作计划含尚未确定的连续位姿、抓取、运动，怎样用领域专用黑箱产生参数，又保持通用规划接口。方法：§3.1 的 stream 是带输入条件与 certified predicates 的生成器，产出的每个参数都应保证相应事实；§7 用 optimistic objects 暂代未知输出，只评估候选真正需要的 stream；§8.1 在一条候选内传递绑定，stream 失败即停止无用后续评估；§8.3 维护可重复尝试的部分绑定队列，在找新计划和深挖旧计划之间平衡时间；§8.4 可把已产生对象重新当自由参数，连同依赖它们的 stream 重新绑定。规模：§9 在3个模拟领域各做100个随机问题、2分钟总超时；紧凑装块领域3–5块，双 rover 领域2–4拍摄目标，不能称为数百对象验证。§9.1 有4类真实 PR2 任务，9类动作。对应本题：可让「给定窗口边界与外部占用→窗口机器/端口/带子候选」成为生成器，让几何/端口合法性检查输出事实；复用已成功候选、反复替换未满足参数，接近小窗口重解。不对应的：本文任务是有限序列；stream-certified facts 的正确性由生成器契约保证，论文并未替本题证明所有可达循环态。自动通道可能使换一个窗口单元改变外部物流，边界参数不能只记录入口/出口坐标。附录A.2原算法要求每个输出对象只属于一个 stream instance；整数格候选易重复，若直接采用需处理重复输出或按附录修改。对本题有什么用：用于 L 的模块/窗口构造接口、已核实局部候选缓存和失败后局部重新绑定；把内核证书明确留作整厂验收条件。依据：arXiv v5 原文 §3.1，PDF pp.2–3；§7–8.4，pp.5–7；§9–9.1，pp.7–8；附录A.2和B，pp.11–12。原文：[arXiv](https://arxiv.org/abs/1802.08705)，本地 `pddlstream2020.pdf`/`pddlstream2020.txt`；DOI：[ICAPS官方论文页](https://ojs.aaai.org/index.php/ICAPS/article/view/6739)。这些页码是12页 arXiv v5 的 PDF 页码。

- [DOI:10.1146/annurev-control-091420-084139；arXiv:2010.01083v1] Garrett、Chitnis、Holladay、Kim、Silver、Kaelbling、Lozano-Pérez 2021，Integrated Task and Motion Planning（Annual Review of Control, Robotics, and Autonomous Systems 4, 265–293）。解的问题：整理任务与运动规划怎样搜索动作骨架、满足混合约束以及在子问题间分享信息。方法：§3.3 对比先定序后解约束、先采样解约束后定序、交错搜索；§3.4.1 共享成功约束赋值；§3.4.2 共享不可满足子问题，只要候选包含该子问题即可排除。反例越小，可排的骨架越多；讨论无连接的约束组件、SAT unsat core 及连续违约信息。对半判定求解器，失败暂当反例但必须持续分配搜索资源，找到解后撤回反例。规模：综述，无自己的实例规模；不能把表1的算法分类读成性能实测。对应本题：给生产图/模块/窗口/全厂四层设计「成功候选库」与「失败依赖集」两类反馈；小的合法反例可定位重解窗口。不对应的：通常的 TAMP目标是从初态到某个终态，不含本题全部可达循环态吞吐；违反约束的局部赋值不能随意变成排除所有上下文的全局割。对本题有什么用：用于 L 的生成—检验—反馈结构；要推广一个堵塞反例，先写出该反例依赖的边界与运行假设，再核实其它候选确实包含同一子问题。依据：2020 arXiv作者稿 §3.3，PDF pp.18–21；§3.4.1–3.4.2，pp.21–22；表1，p.23。原文：[arXiv](https://arxiv.org/abs/2010.01083)，本地 `garrett2021.pdf`/`garrett2021.txt`；正式刊载/DOI：[Annual Reviews官方页](https://doi.org/10.1146/annurev-control-091420-084139)。引用章节与页码按30页 arXiv v1，未把它们声称为正式排版页码。

- [DOI:10.1109/ICRA.2011.5980391] Kaelbling、Lozano-Pérez 2011，Hierarchical Task and Motion Planning in the Now（ICRA, 1470–1477）。解的问题：长时域机器人任务的完整底层计划太大，怎样分层规划，执行首个抽象步骤后再精化后续步骤。方法：按逐步补足前置条件构造层次；回归规划以弱前置条件产生下层子目标，几何 suggester 产生位姿/扫掠体积候选；抽象步骤尽量满足可串行化，即首步任意实现后仍存在后续实现。若串行化失败，提高涉及条件的抽象层次，最终允许联合解决。规模：§VII 给6房间家务领域；代表性 clean-and-tidy 解执行65步，生成169个子计划，最长子计划7步；仅代表性样本，无耗时基准或随机成功率。对应本题：先分别构造模块，但显式维护会被后续模块需要的边界空位、物流端口和覆盖条件；拼装失败时把有耦合的模块/窗口联合重解，避免把已冻结模块当不可回退选择。不对应的：本文边规划边执行，本题建好后不再改变；本文定理需要动作域静态连通性，即可达状态之间最终可逆，紧凑布局和运行缓存未满足该假设；当前连续 suggester 只试少量实例，作者明确不保证找到存在的解。模块单独达标也没有本文式串行化证明，更没有整厂循环态组合定理。对本题有什么用：用于 L 的模块后拼装以及自动扩大修复范围的策略；不适合直接作全厂可行性或吞吐证明。依据：§I，PDF p.1；§IV层次与 §V算法，pp.5–7；§VI正确性、§VII实证，pp.7–8。原文：[MIT作者PDF](https://people.csail.mit.edu/tlp/pdf/2011/hpnICRA11Final.pdf)，本地 `kaelbling2011.pdf`/`kaelbling2011.txt`。DOI元数据取自 Crossref 精确记录，本地 `kaelbling2011_crossref.json`。


## 可直接试的构造接口与尚未找到的保证

- 首选 Dantam 2018：把反馈分成单候选排除、依赖状态泛化、依赖局部参与物泛化，保留撤销和扩大搜索预算机制。本题的失败局部依赖可能涉及端口自动连接、轮询状态、外部缓存，必须把这些写进反馈条件。
- 次选 PDDLStream 2020：将窗口候选产生、几何合法性核查、局部运行核查做成带明确输入和已核实输出事实的接口；保留部分成功绑定，失败后只重新产生受影响参数，最后仍交整厂内核。
- 次选 LGP 2015：先便宜筛最终几何与模块候选，再做端口/布线，最后做完整运行，便宜层通过只表示值得精化。
- HPN 2011 提供模块拼装失败后联合重解的动机与边界条件，但其可逆性和可串行化条件没有在工厂布局证明。

本组检索未找到一种从机器人 TAMP 的静态几何/有限路径正确性，推出本题所有可达循环态吞吐保证的论文机制。查询中查到的反馈和分层构造可以帮助产生 L 候选；不能独立认证 L，也不能推出 U。没有找到217台级整数格工厂、轮询物流网络的 TAMP实例规模数据；已核实规模分别是小型装块、几十个机器人障碍物、或便宜层100物体，不跨层外推。
