# FEM G0B → G0 → G5 → G1：实施与验证记录

状态：G0B/G0/G5/G1完成并通过PR #23合入main。最早基线 main `72a335604a50c1ae27516b8bde15e05564b5748b`；
本次接续主线 `47b5bd46c992fcf64cf163361053ceb0091fa5a5`，G5检查点 `2fcd2fd834320883b3e148892fcc9ee3a431288c`。
下文按检查点保留历史；旧段落中的“尚未实施”不覆盖最新状态。
工程量估计与依赖在现有 [队列](CODEX_TASK_QUEUE.md) 维护；本文仅记录实现和验证事实。

## G5 独立场BDF2增量

实现与支持范围见[TIME_INTEGRATION](TIME_INTEGRATION.md)。主锁Debug新9项针对性检查全部通过，
42.23秒CTest墙钟；[逐项结果与源码清单](../research/data/fem-integration-2026-10-31/bdf-standalone.json)。
流体固定稳定化下BE速度阶约0.995–0.998、压力1.04–1.07；BDF2速度2.01–2.02、压力2.13–2.26。
线弹性卸载固体BDF2位移/速度约1.99–2.02、加速度1.95–2.00。
变步长、最多4rank、重启、真实拒绝及末步通过；事件测试仅验证控制器与历史，不是真实跳跃载荷。
独立审查指出并修正schedule签名缺失；稳定化限定已明示。G5整体仍未完成。

ALE/FSI BDF2增量：主锁Debug6项针对性CTest全部通过，138.35秒CTest墙钟，
[证据](../research/data/fem-integration-2026-10-31/bdf-coupled.json)。
弹性/刚体FSI速度、压力、网格位移时间阶趋近2；ALE解析网格速度阶趋近2，
均匀流保持及1/2/4rank完整历史恢复通过。整体J差分相对误差约1.4e-9。
新增全分量离散接口功率对照，不将其解释为总能量守恒。真实BDF2启动后拒绝恢复与同轨迹对照通过。

独立流体一阶/结构二阶generalized-alpha：主锁Debug7项针对性CTest全部通过，26.82秒CTest墙钟，
[证据](../research/data/fem-integration-2026-10-31/alpha-standalone.json)。rho=0/0.5/1的早期/终点压力、
速度与结构位移/物理加速度近二阶；算法历史与物理加速度区分，rho=1在线弹性BE启动后保持能量。
事件重置、真实拒绝恢复与最多4rank重启通过。该检查点尚未实施alpha ALE/FSI；后续增量如下。

## 47b5bd4 后的 G0 验收补强

接续源SHA：`47b5bd46c992fcf64cf163361053ceb0091fa5a5`，分支 `codex/fem-time-mesh`。
该主线SHA的 [云端CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41178465248)
主锁Debug/Release各43项、兼容锁Release 10项成功，无失败/跳过；本轮实际读取作业日志，
摘要见 [main-ci.json](../research/data/fem-integration-2026-10-31/main-ci.json)。
独立审查逐一核对原g0.json的100份源码哈希，与该主线完全一致。

本轮用户明确允许WSL2开发验证，并要求云端CI复验。两套锁定依赖恢复到仓库`.cloud/`；
默认PATH中的ParaView MPI不参与验证。首次沙箱MPI启动因PMIx socket被禁止（errno=1）失败，
获准在沙箱外重跑后2/4 rank预检成功。这是执行环境失败，不是数值失败。

新增显式 `-verify_operator_permutation` 仅用于具有可逆约束切线的小型诊断：
对真实初始装配的J/R作跨rank全局反序，通过分布式scatter验证矩阵作用和残量往返，
对J*v已知解求解，再以真实R为右端求解并逆映射检查原方程缺陷。
该诊断使用额外直接分解，关闭时不执行，不构成生产存储重排或不同布局重新装配。
不适用于初态收敛但Jacobian奇异的无需求解路径；诊断耗时不能纳入PC性能比较。
PETSc VecPermute不支持跨rank非本地置换，因此这里使用scatter；参见
[官方说明](https://petsc.org/release/manualpages/Vec/VecPermute/)。

三recipe测试新增逐步流体力、位置/速度、动量平衡和边界通量/压力对照，
增加同一仿射流的规范点定压及零均压；输出长度和有限值也明确检查。
新增性能脚本`benchmark_pc_recipes.py`固定两小算例、1/2/4rank，每模式预热一次、
三次重复轮换顺序，逐次保存直接解偏差、物理量对照及setup/solve/迭代/RSS。
总阶段时间包含嵌套，不能相加；不预设新recipe更快。

当前实际检查：主锁Debug/Release各43项通过；新增辅助求解奇异失败/恢复负例随后在主锁Debug及旧锁Release的10项故障选择中通过，旧锁三recipe补验3项通过。受控性能72个样本全部满足物理对照，最大场差3.307e-12；补强提交`e9e4d30`的[云端三环境CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41180022722)均成功。
[本轮证据](../research/data/fem-integration-2026-10-31/g0-supplement.json) 与 [性能原始报告](../research/data/fem-integration-2026-10-31/pc-recipes-benchmark.json)。
小型问题上直接解solve中位数均更低，不由此推断大规模结果。
G0补强验收通过，整体主线交付仍in_progress；G5独立场BDF2已实施，G1尚未实施。后文为前序检查点记录。

## 72a3356 历史基线

PETSc 3.23.7 real/double/int32 + OpenMPI 5.0.8 + GCC 15.3.0，Linux x86_64，cgroup 4 CPU/32 GiB，4编译任务、CTest串行、每rank BLAS/OpenMP单线程。
锁定恢复入口和来源继续使用 `environments/` 与 `scripts/cloud/`，没有增加安装框架。

```bash
bash scripts/cloud/restore.sh 3.23.7 /workspace/eonsim-cloud
bash scripts/cloud/run.sh 3.23.7 debug all /workspace/eonsim-cloud
bash scripts/cloud/run.sh 3.23.7 release all /workspace/eonsim-cloud
bash scripts/cloud/restore.sh 3.19.6 /workspace/eonsim-cloud
bash scripts/cloud/run.sh 3.19.6 debug mpi-failure /workspace/eonsim-cloud
```

以上为历史完整集成命令；PR #24 后 3.19.6 仅按需手动专项，不是日常矩阵。路径可替换为任意可写持久目录。快照旧构建缓存引用消失的 `/tmp/infra-pristine` Ninja；将旧目录移至证据目录后从空构建目录恢复成功。主环境初次依赖恢复使用新前缀及包缓存；再次恢复成功，不能将缓存命中代替运行验证。

| 代码 | 环境/模式 | 选择 | 实际结果 |
|---|---|---|---|
| 72a3356 | 3.23.7 Debug | 完整短套件 | 35/35，135.68秒CTest墙钟 |
| 72a3356 | 3.23.7 Release | 完整短套件 | 35/35，55.06秒CTest墙钟 |
| 72a3356 | 3.19.6 Debug | mpi-failure | 7/7 |

[机器可读清单](../research/data/fem-integration-2026-10-31/baseline.json) 保留实际dirty标记、依赖锁摘要、测试名/状态及日志摘要。原始日志位于 `/workspace/engineering-evidence/baseline-*-evidence/`。这些只是基线，不能用于声称新能力已验收。

## G0B 实现检查点

- `DofKey` 在一个layout的网格命名空间中使用网格实体ID、域、量、分量、空间/局部模式；不使用rank/代数编号作为身份。joined网格仍使用重编号后的实体ID，不承诺跨导入或跨分区重启身份。
- `AlgebraLayout::owned_semantics` 与 `fields` 分开；后者继续独立控制物理验收。保留原 owned/ghost 映射、编号、图、默认LU及原block/schur选项。
- `ReducedLayout::slot` 明确试探列、局部代表、仿射lifting及测试行。界面mesh列乘时间重建系数、测试行舍弃；结构kernel内部链式导数不重复相乘。
- `solver.pc_recipe` 或 `-pc_recipe` 选择 physics/quantity/hybrid；不能同时指定旧block/schur选项。当前只支持独立流体及现有FSI；没有增加生产存储重排。
- `PcBlock` 保存owned root provenance和直接父编号；每层用本地计数前缀生成子矩阵空间，不把根编号传给嵌套IS。空本地块参与collective，全局空块共同拒绝。
- 三树见G0A。独立流体退化为共同u/p Schur；FSI physics为fluid(u/p Schur)/solid/mesh，quantity为velocity(fluid_interior/structure)/pressure/mesh，hybrid为dynamics(velocity(fluid_interior/structure)/pressure Schur)/mesh。
- 叶子默认GAMG；唯一标量刚体使用Jacobi。quantity的原始压力块使用Jacobi：实际测试发现原始Jpp的AMG粗层可能奇异；完整系统仍可逆。不改变方程或容差，不宣称某种分组更快。
- options prefix按树命名。固定分裂类型不能被options改写；独立Schur inner/upper尚未接线，按真实第二孩子prefix的所有选项共同拒绝。`-pc_plan_report` 输出块大小、owned区间和实际prefix。
- 索引计划在每次solve的准备阶段生成；Newton内不重建。没有承诺跨时间步缓存或预条件因子复用。

## G0 首轮验收检查点与边界

已执行的首轮 targeted 检查：1/2/4 rank 子矩阵手写oracle和错误配置；三recipe独立流体、双域弹性、刚体、超弹性与直接解对照；初态收敛、callback分类/accepted不变/同对象恢复；fluid COO与FSI重启对照。后续slot映射改造后的完整回归正在执行，最终状态以后续实际结果为准。

独立审查发现并修正：rank局部布局错误的共同传播、子KSP数组异常释放、命名Schur inner/upper选项漏检、options改变固定分裂类型。上述审查不替代运行验证。

最终Debug/Release、兼容新路径和故障/缩步已在后文更新；尚未关闭整体CI/PR与主线交付。G5、G1尚未实施。没有大规模性能或新物理能力结论。

## G0 主环境最终数值验收

当前G0源码清单与实际结果见 [g0.json](../research/data/fem-integration-2026-10-31/g0.json)。测试执行时HEAD仍为72a3356、工作区dirty；逐文件SHA256用于区分新增代码，不把这些结果归给未修改基线。

- 主环境Debug `all`：43/43，无跳过，254.53秒CTest墙钟。
- 主环境Release `all`：43/43，无跳过，102.11秒CTest墙钟。
- 3.19.6 Debug `mpi-failure`：10/10；新三recipe/重启/子矩阵7项 targeted 均通过；最新所有权负例与真实缩步4项补验也全部通过。
- 独立审查的阻塞项均修复；另将负例的异常分类失败改成清理后共同报告，避免测试自身残留错误handler或单rank提前抛出。
- 实际覆盖：非对称WᵀJK与非零lifting手算oracle、PETSc置换矩阵值/残量/解、三层真实子矩阵、空owned rank、1/2/4rank、非法配置、回调/PC/线性失败区别和同对象恢复；四类流体/FSI算例对直接解；27组COO/重启；hybrid真实缩步对直接小步长。
- 默认旧路径、Poisson、固体、COO、checkpoint、局部/整体导数等现有短套件均保留。没有生产存储重排、跨rank数重启或大规模扩展性声明。

这些墙钟是CTest执行记录，不是工程实际耗时，也不是同配置性能比较。正式PR与主线交付仍等待G5/G1和整体CI/审查。

## G5 耦合generalized-alpha增量

主锁Debug10项针对性CTest全部通过，324.63秒墙钟；
[源码、命令、退出码和数值证据](../research/data/fem-integration-2026-10-31/alpha-coupled.json)。
弹性FSI末次加密速度阶2.04–2.12、压力1.97–2.10、网格位移1.95–2.02；
刚体FSI对应各字段约2.01–2.03。rho=0/0.5/1、完整历史及事件重启、真实Newton拒绝、
1/2/4rank与接口网格速度/结构速度一致性通过。ALE解析网格速度末次阶约2.00–2.01。
ALE stage有效但endpoint反转负例在4rank中坏单元数3/1/2/0，共同拒绝、缩步恢复；
补充脚本确认失败checkpoint哈希不变。FSI独立端点反转分支未直接触发，只作源码审查。
两轮独立只读审查无剩余源码阻塞项；不据此宣称任意非线性FSI稳定性或性能改善。
独立alpha提交25e0945已通过云端三环境CI（41194151488）；本增量提交2fcd2fd的云端三环境CI（41195474887）全部成功。


## G1 规范化网格与二维标量闭环

真实生产路径贯通 Gmsh2.2/4.1 ASCII、外部编号与 physical groups、Tri3/P1 与原生 Quad4/Q1、
相容混合网格、METIS 分区及 owned/ghost、AIJ 装配、Poisson/瞬态扩散、三类边界与输出。
[用户指南及输入限制](SCALAR_2D.md) 和 [DoF/PC 独立配置](DOF_AND_PC_GROUPING.md) 是当前接口入口。
二维分区元数据版本3；三维保持版本2及旧Tet4文件读取。高阶、参数化/周期/Gmsh自带分区、
曲面、非相容及三维混合体不在支持范围。多physical group在规范化层保留，求解适配器明确拒绝歧义。

- 独立解析矩阵 oracle 检查 Q1 质量/刚度、P1 映射及角点反转；4.1和2.2的Tet4结果作1/2/4rank对照。
- 三种二维拓扑的畸变仿射 patch、非零D/N/Robin、编号/方向变换、纯Neumann与双材料通过。
  二次制造解在4/8/16网格上的L2阶约1.99–2.01、H1阶趋近1；独立边界梯度通量缺陷随加密收敛。
- 瞬态仿射指数解控制空间误差，末次加密BE阶约0.97、BDF2约2.16、alpha约2.04；
  绝热均匀源的体积积分符合解析解。三格式1/2/4rank事件、完整历史重启和PVD时刻通过。
- 真实KSP失败保持accepted/checkpoint不变；缩步后与记录的实际步长重放一致。
  线性求解增加rank局部PC失败共同传播及同对象恢复，包含PETSc3.19.6旧PREONLY路径。
- 独立审查修复额外partition tags被忽略、合法高维名称拒绝、失败类型、断开域零空间范围、
  restart PVD及时间片文件覆盖；最终源码复核无确定阻塞项。源码审查不替代运行证据。
- 对称标量矩阵条目成对生成，避免极小重试步长下浮点乘法次序产生假非对称；未放宽检查容差。

这只交付G1所需的边界、稀疏图和输出子集，不关闭完整G2/G4。
未开展二维性能对比；G0性能结论仅对应其原检查点，不冒充最终代码的新测量。


## 最终本地集成回归（提交前源码清单）

[最终机器可读证据](../research/data/fem-integration-2026-10-31/fem-final.json) 保存109份生产/测试/构建源码SHA256、
实际inventory、JUnit/日志/二进制哈希、完整命令和退出码、依赖锁与数值结果。
运行时HEAD为2fcd2fd、工作区dirty；这些结果对应清单中的新源码，不能归给未修改HEAD。

| 环境 | 实际选择 | 结果 | CTest墙钟 |
|---|---|---|---|
| PETSc3.23.7 Debug | all | 60/60，无失败/跳过 | 574.87秒 |
| PETSc3.23.7 Release | all | 60/60，无失败/跳过 | 213.11秒 |
| PETSc3.19.6 Release | mpi-failure | 13/13，无失败/跳过 | 18.50秒 |

包含最后新增的layout_policy_verification；两种主构建完成2/4rank ABI/MPI预检，兼容锁完成2rank预检。
独立审查最终无确定源码阻塞。Python语法、Markdown本地链接及git diff空白检查通过；
本地node未安装，网站检查交由PR云端执行。该本地检查点尚待 CI 与主线合并；后续已完成，见下节。


## 主线交付

最终功能提交`9e5a1eddf06a02f5e64201d3eff2d55638ddbf13`经独立证据复核，109/109源码哈希匹配。
[PR #23](https://github.com/saitoasukakawaii/EONSim-new/pull/23)已合并为
`9cc2e102e8e32f929de1c9a790c1ae527b931fa2`，未强推、未绕过检查。
[云端PR数值检查](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41199182613)
主锁Debug/Release各60项、兼容13项均通过，无失败/跳过；4CPU、约16GiB云端资源与本地资源分开记录。
[push检查](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41199162462)及
[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41199182529)成功。
PR使用合并预览SHA `300a7544f181002063b954c014610ebc9a3c9fae`，其tree与功能提交均为
`ba8692ba4938995ad495aabd562380f43e590150`；[机器记录](../research/data/fem-integration-2026-10-31/delivery-ci.json)。
后续完成状态归档仅修改文档，生产源码及测试清单不变；最新main检查见仓库Actions。

G0B/G0/G5/G1及INFRA-01集成验收关闭。完整G2/G4和其它未授权阶段不关闭。
旧段落保留阶段历史，不能覆盖本节最终状态；源清单、数学适用性及未覆盖范围仍有效。
