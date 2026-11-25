# EONSim Codex Session Log

## 2026-11-25–26 · FSI-PERF-02 — 适用优化、回退修复和证据交付

用户继续要求完成 EONSim-new 性能优化。核实 PR #51 已合入 main `4e25e2a7b1aa921dc473fe09cd5f9b3f09d4645f`，
从该点在 `codex/fsi-performance-completion` 开发并创建 [PR #52](https://github.com/saitoasukakawaii/EONSim-new/pull/52)。
7f3d12ed 与 2b0b30bc 两次实现均先推送后编译/验证；测量工作树与构建来源均 clean。
知识草稿仍留在 `website/drafts/`，没有晋升公开文章。本文不把 PR 提交写成已合并。

### 实现与独立审查

默认 AIJ/COO 共用精确物理图，保留移动 RCR 的速度行/压力行到面内几何列。
残量默认固定 COO，包括实际 SNES line-search Vec 的预分配；失败先同步，成功后才发布部分缓冲。
局部 COO K→U 保留 contribution→slot，主线程保持原贡献相加次序；OpenMP 仅执行纯单元核与私有暂存。
线性参考 mesh 和解析面积导数移出 AD，流体仍传播全部当前几何、metric 与跨场导数。
合资格 Newton 会话及 field/diagnostic 缓冲跨步复用，数值 Jacobian/PC 始终刷新。

审查在推送前发现 keep/release 判断是 rank-local，而 SNES 析构需要 collective 一致。
修为 MPI_MIN 共同决定，增加仅 rank 0 关闭复用的普通/双 COO 连续求解测试；未声称曾实测死锁。
另外审查 callback 借用范围、Workspace 析构顺序、实际 Vec ID、失败 stash 清理和 USER PC 数值刷新。
BAIJ 因异构有效编号不采用；真正 halo/内部单元计算重叠因历史细网格 ghost/solve 仅 0.015%–0.023% 不新增。

### 实测回退与修复

7f3 首轮 local Release **13/13** 通过，构建 43.153 s / CTest 73.414 s。
首批 default/COO/threads 共 80 次、1,600 步运行全部通过数值门槛，但 COO 细网格单 rank
一次性准备配对中位数 **+23.03%**：plan 29.445→207.212 ms，system 156.877→33.014 ms。
压缩仍带来 RSS −6.28%，因此保留 K→U，把 K 项全局间接排序改为 local-row bucket 和桶内列排序，
owned 算术索引、ghost 二分与重复行查找缓存；生成唯一坐标的全局顺序、value_slots 与数值 scatter 保持。
填好 permutation 后提前释放 K 项临时行数组。

修复 2b0 推送后，只运行受影响的 `fsi_coo_verification` **1/1**（31 commands，1 个预期失败），
构建 26.815 s / CTest 9.151 s；107 个共有数值摘要与 7f3 相同。
重跑最终 COO 的 32 次/640 步，初始化四组中位数下降 20.17%–47.72%，细网格单 rank **−39.90%**、双 rank **−47.72%**。
未重复不受影响的默认/线程性能，也未将其来源改写为 2b0。

### 最终证据及审计修正

最终三组共 **80 次运行、1,600 接受步、3,200 线性修正**，含 20 次预热；另外保留旧 COO 32 次/640 步。
默认 assembly 配对中位数 −9.47%～−20.34%；COO RSS −2.13%～−8.89%。
默认细网格单 rank RSS +4.01%；部分 wall 配对范围跨零，多线程和矩阵 COO 维持显式选择。
新版每次首步新建、后 19 步复用；全部每步 SNES/KSP=2/2，物理方程与接受门槛未改。

独立审计核验 13,787 份哈希、985,204,950 B，重读 1,680 个状态/5,040 体 VTU，
最大字段差 6.661338147750939e-16、历史差 2.609024107869118e-15、ghost 差 0，
最大真实线性残量/门槛 0.00019408852157546064。两次审计辅助程序修正均保留原尝试：
首步 RSS 六位有效数字产生 12 B 表面下降，改按原 token 的半末位区间核验，聚合仍严格取原打印值 max；
Python 3.12 的 sum 与逐项 += 相差 1 ULP，改按统计定义 sum(raw steps) 重算。均未更改物理或统计门槛、原始数据或重新求解。
GCC Tri3 sort 小数组警告经静态边界审查属不可达大范围分支，未关闭警告或增加无关 Debug。

源码 CI 7f3 在 merge `9393f27` 实际 **51/51 Release、65 Python**，
2b0 在 merge `a071ed2` 实际 **28/28 Release、6 Python**，另 23 项复用首轮证据。
四项必需检查的来源与状态均读取 GitHub；分支前进而 PR head 曾滞后，通过重新打开同一个 PR 刷新，
未将旧 head 的成功检查当作新源码已验证。

归档 21,848 份原始逻辑文件、4,421 个内容对象和三个实际二进制，压缩流 19,946,772 B，
分为五块并核验全部对象/清单/重组 SHA。后到的 2b0 CI 收据单独保存相邻 JSON，未冒充已在压缩包内。
[完整命令、逐组统计、限制与重放](../research/data/fsi-performance-2026-11-25/README.md) ·
[审计](../research/data/fsi-performance-2026-11-25/independent-audit.json) ·
[知识草稿](../../website/drafts/fsi-performance-completion.md)。
本地未运行全量、Debug 或 PETSc 3.19.6；本任务未证明多节点/GPU 或生产网格普遍加速。

## 2026-11-25 · FSI-ASSEMBLY-01 — 实现与验证完成，待用户 review/merge

基线为 GitHub 已核实的 main `f7acccb7a8239c60a2d2be193a158ac430851dcf`。
独立分支 `codex/fsi-assembly-performance`，交付 [Draft PR #51](https://github.com/saitoasukakawaii/EONSim-new/pull/51)。
生产实现 `df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e` 和计时驱动修复
`b2ccd96419091c669b8dceae4369c5b255f47f57` 均先推送再执行相应验证。
实现与本地验收完成，保留 Draft，合并留待用户审核。

### 实现和独立源码审查

消除 PREALLOCATOR→临时 AIJ→逐行容量→第二 AIJ 的重复准备，直接转移最终 AIJ 所有权；
physical-slot ghost 编号交换不再生成无用 nodal adjacency/field 元数据。
缓存单元测试行、试探列及 trace 掩码，融合 AD primal/Jacobian，可选压缩 COO 含全部刚体／RCR 项。
界面反力重放仅遍历两域实际接触界面的单元并复用缓冲，仍采用未投影的物理残量。

独立静态审查核对局部结构零、不同的 test/trial 映射、变步长链系数、出口几何导数和贡献顺序。
固定拓扑缓存不缓存 `mesh_dt` 对应的权重；每次尝试按当前时间参数刷新，保留 retry/restart 语义。
COO 重复 alias 由 PETSc 累加，残量单独求值不更新矩阵，失败同步后才发布数值矩阵；
材料、端口及时间历史仍只在完整接受步提交。方程、时间离散与数值接受门槛未改。
推送前静态审查修复了空 rank 隐患：COO 模式按 `coo && j` 判断，不能依赖可能为空的值缓冲指针。
该问题没有伪称发生过运行时失败。

### 推送后的本地 Release 验收

在 clean df6e9ac 源码与锁定 PETSc 3.23.7 / Open MPI 5.0.8 / GCC 15.3.0 环境执行：

```bash
OMPI_MCA_smsc=^cma bash scripts/cloud/run.sh 3.23.7 release explicit \
  /workspace/scratch/6d25aa929185/pr42/.cloud \
  /workspace/scratch/d56ec93a621c/assembly-tests.json
```

**8/8 通过，零失败、跳过或超时**；构建 41.015 s，CTest 35.443 s。
实际选测为 `nonlinear_acceptance`、`nonlinear_acceptance_mpi`、`fsi_element_jacobian`、
`fsi_coo_verification`、`fsi_metric_stabilization`、`time_retry_verification`、
`domains_verification`、`fluid_coo_verification`。
新矩阵所有权测试包含仅由远程 rank 产生的图、移出 owner 为空、Mat 对象身份不变与重复 solve。
融合单元在 24 组配置下对独立 double 残量作 48 个 fluid/ALE 方向比较，最大相对差 `2.23866e-10`。

新增 FSI COO 验证的 27 次 solve 覆盖刚体、共享网格弹性、独立双域 Neo-Hookean、固定/移动 RCR，
以及 1/2 rank、变步长、跨后端 restart、真实 nonlinear retry 和失败后 checkpoint 不污染。
最大 owned 字段差 `4.617972670928339e-13`、归一化历史差 `5.920530605376608e-14`；
移动 RCR 全局 Jacobian 相对 FD 差 `1.98755e-08`。真实 retry 缩步 3 次，接受 dt=0.0125。
metric 检查包含 BE/BDF2/generalized-alpha；既有 Neo-Hookean retry 恢复到 dt=0.00125，1/2 rank 均完成 32 步。
共享 NonlinearSystem 的既有独立流体 COO 检查覆盖 1/2/4 rank。

### 性能驱动缺陷、修复与固定来源

实际基线二进制来自 clean `c4fb266edec94afbf610cb1379dd1595ed96ae40`，
其 src/include/tests、CMake、依赖锁和 cloud 构建输入与 f7acccb 无差异；候选二进制来自 df6e9ac。
各 campaign 保存二进制 SHA-256、源码与驱动版本、环境、输入、命令、原日志、保存场和退出状态。
两组首轮 pilot 各 32 次运行的数值检查通过，但外部 wall 呈约 50 ms 台阶。
独立检查和源码审查定位到 POSIX `Popen.wait(timeout=...)` 的轮询等待。

b2ccd 改为阻塞 `wait()`，由独立 watchdog 负责超时及进程组清理，正常计时不再轮询；
失败和超时仍保存原始收据。修复先推送，再串行重做默认与 COO 两个正式 campaign。
`perf-default`、`perf-coo` 原始 pilot 完整保留，wall 数据不用于最终结论；
正式结果仅来自 `perf-default-final`、`perf-coo-final`。
生产 C++ 未改变，复用 df6e9ac 的 8 项本地收据，没有为驱动修复重复编译或重跑该选测。

### 最终成对基准与实际取舍

共享主机的 CPU 标识为 Intel Xeon Platinum 8573C，可见 CPU 0–8，未验证独占物理核绑定。
每 rank 一线程，两套网格共 771/6,147 单元、703/5,367 DoF，1/2 rank，每次五个 BE 步。
双方显式 PREONLY/LU/SuperLU_DIST，使用相同输入、solver/linear report；候选另有一次装配计划报告。
驱动参数为 `--subdivisions 4 8 --ranks 1 2 --steps 5 --repeats 3`，
第二个 campaign 最后追加 `--candidate-options -fsi_coo`；每组一对预热、三对交替测量，串行执行。

两次正式 campaign 合计 **64 次运行（48 次测量、16 次预热）、320 个接受步、640 次线性修正**。
每步 SNES/KSP 次数均为 2/2，逐步时刻、物理接受、全部保存场和 ghost、接口平衡与 CSV 历史一致。
默认最大场及历史差为零；COO 最大场差 `2.220446049250313e-16`，历史差 `1.8158547268845473e-15`。
真实线性残量保持 `norm <= 1e-12 + 1e-10*rhs_norm` 门槛，最大 residual/limit 为 `0.000160287150638544`。

默认 assembly 的四组配对中位数下降 **2.72%–11.81%**，COO 下降 **30.16%–43.37%**。
统计量是逐对 `candidate/baseline−1` 的中位数，不能用双方独立中位数之比替代。
所有 COO 整次 wall 变化范围均跨过零；细网格单 rank 峰值 RSS 配对中位数增加 **27.81%**，
2 rank 增加 **12.29%**。因此默认保留 MatSetValues，COO 继续显式开启，没有宣称普遍整次加速。

COO 唯一 nnz 从 36,643/364,635 降为 27,226/260,010，减少 25.70%/28.69%；
对应贡献值缓冲合计 1,271,880/12,765,704 B，不含映射及 PETSc 内部存储。
所有候选记录 `matrix_mallocs=0`、`nnz_unneeded=0`；唯一 nnz、贡献数与峰值 RSS 必须分开解释。
新 `fsi_assembly_plan` 给出候选初始化细分；旧通用 solver setup 不包含图和系统构造，
因此本轮没有测得可比较的旧/新图初始化百分比收益。各 rank 最大分项还可能重叠，不能相加当作整次 wall。

### 独立证据重放与源码 CI

独立重放读取最终两组证据，核对 3,328 份运行文件哈希、1,152 份 VTU、384 个保存状态、
3,118,848 个 owned 标量值、1,280 条字段接受记录及全部 640 次线性修正，并重算配对统计，未发现不一致。
归档初审发现已登记的保留二进制尚未对应最终内容对象，随后补齐两个实际可执行文件、审计和 CI 收据。
[最终归档校验](../research/data/fsi-assembly-2026-11-25/archive.json)的 `final_packaging_verification` 已通过，
核对所有内容对象哈希、大小及清单引用，缺失和孤立对象均为零，两个实际二进制字节流也已核对。
该最终校验关闭独立审计中保留的中间 `pending packaging` 状态，没有重新执行数值求解。

b2ccd 源码的 [Core numerical validation #104](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45632206852)
在 PR merge commit `ad0cbf5965c6d83e7d578d9ffe549f0e6c84e9b0` 上实际执行
**55/55 项 PETSc 3.23.7 Release 数值选测**，零失败、跳过，`executed=55`、`reused=[]`。
选择脚本的 **65 项 Python 检查（26+6+6+11+3+13）**通过；
[Website Build Check #124](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45632206859) 通过。
Debug 和 PETSc 3.19.6 手动 job 跳过；本地只运行上述 8 项定向检查，未运行全套、Debug 或 3.19.6。
55 项是 CI 的实际选测范围，不作全量推断，文档后续提交也不记为新数值执行。

[实际命令、完整性能范围和归档](../research/data/fsi-assembly-2026-11-25/README.md) ·
[独立审计](../research/data/fsi-assembly-2026-11-25/independent-audit.json) ·
[CI 来源](../research/data/fsi-assembly-2026-11-25/ci-source-b2.json) ·
[算法草稿](../../website/drafts/fsi-sparse-assembly-plan.md)。
单机小网格和五步成本不证明多节点扩展、GPU 收益或长时间生产算例加速；草稿未发布，PR 待用户 review/merge。

## 2026-11-25 · FSI-PC-03 — nodal 结构反馈与有界内层响应

从 PR #49 已合并的 `296246e53d895f29ea3d0f7e5c960dc26b1426dc` 开始，
分支 `codex/fsi-block-efficient-schur`，交付 [PR #50](https://github.com/saitoasukakawaii/EONSim-new/pull/50)。
本轮用户明确授权“代码先同步远端、再运行算例、最后合并”，取代上一轮人工合并限制。
每次源码及验证器修订均先推送后运行；四项必需检查与 head-locked squash 规则继续适用。

### 实现和独立审查

`664a6238ab08a42639a6c180addc99ddbf38886b` 实现可选的结构 USER 矩阵 `K−G H_F E`。
混合小块同时包含活动流体速度和压力，区分 mode、space、domain 及 boundary/vertex；
RCR tag 与数值相同的体节点 ID 不混组。行、列最大值平衡后选主元求逆并恢复原单位；
不因压力和动量数量级不同而直接误判奇异，也不加压力钉点、正则或隐式回退。
共享状态复用 IS、乘积图和 P handle；每个约束后成功 Jacobian 只刷新一次。
默认 nodal 结构应用一次 GAMG/Jacobi。压力 nodal 原算术与完整根 Jacobian 保持原路径。

独立代数 oracle 含非对称交叉块、4/3/1 维局部块、缺分量、不同 mode、约束行、
同 ID 的 RCR 实体、跨约 30 个数量级的混合尺度、数值刷新、奇异/非有限拒绝与恢复。
1/2/4 rank 三项通过；RCR、nodal retry 和初筛三个 CTest 也通过。
两名交叉审查者核对了缩放还原、所有权、矩阵生命周期和 collective 次序，没有发现阻断项。

### 性能筛选的负面结果与方向调整

初筛细网格原 a11/结构 FGMRES20 的线性时间 49.117077 s；结构 PREONLY 下 a11/nodal
分别为 68.456574/65.788333 s。节点矩阵正确不等于效率提高，故不提升为默认。
两项粗网格有界探测分别给出 nodal 加回结构 FGMRES 的 6.716347 s，
以及 a11 保留结构迭代、只把流体改成 PREONLY 的 0.907051 s；这些仅为单次四步探测。

随后固定同一 664a623 二进制，采用 `66b0a62af6575d8a98d85b7c90d88d6e22666439`
驱动显式比较旧/新 added_mass 和 twolevel 响应，另保留 direct、coupled_nodal。
72/72 次运行通过，含 12 条完整 32 步轨迹、预热和三次交替四步计时。
细网格线性中位数 added_mass `44.477524 → 6.506006 s`，twolevel `3.931200 → 0.609956 s`；
外层迭代从 354→661、563→682，说明只看外层次数会误判。
最大真实残量/目标比 0.5547250921，最大相对场峰值差 3.1382040814e-11；全部接受条件保持原值。
直接法在这两套小网格上仍最快；不作强扩展或一般问题加速结论。

### 验证器缺陷和修正

首轮纯 Python 正负对照 21/22 符合预期：早期错误的 KSP 类型会被后续正确的最后一次快照掩盖。
66b0a62 改为检查每个目标 prefix 的所有观测，并核对每 rank 的观测总数等于接受步数；
修复后扩展至 25/25，含缺失、重复和错 rank 的早期观测。原失败与其输入保留。
独立重放进一步按接受步区间核验每 rank 恰有一份目标观测。
独立重放的静态复核另发现只记录 KSP reason 而未限制的问题，在推送前补为
根正成功原因、目标正成功或有界迭代 ITS、PC_NOERROR 的检查；该项没有伪称发生过运行时失败。

### 最终源码的重新编译与验收

`c4fb266edec94afbf610cb1379dd1595ed96ae40` 仅把 added_mass 流体响应和 twolevel 速度响应
的默认 KSP 类型改为 PREONLY；保留显式 FGMRES 的 1e-4/20 预算，结构 a11 仍为 1e-2/20。
新的近似结构作用是 `K v−G B_F(E v)`，不能把完整 Schur 容器当作精确流体逆；
一次 PC 作用内仍可能有依赖右端的粗层迭代。外层完整 Jacobian 继续用 FGMRES。
`linear_report` 是诊断，严格真实线性残量门槛由验证器执行；生产物理接受条件未变。

推送并与远端树核对一致后，执行
`scripts/cloud/run.sh 3.23.7 release explicit /workspace/scratch/6d25aa929185/pr42/.cloud build/ci/fsi-efficient-defaults.json`。
clean Release **9/9 通过**：pc_plan_mpi1/2/4、fsi_tube_rcr、pc_added_mass_retry、
pc_added_mass_nodal_retry、pc_twolevel_retry、pc_recipe_restart、pc_recipe_hybrid。
新增物理变体涵盖 rigid、domains、hyperelastic 的结构 nodal 和 quantity-twolevel；
默认实际 KSP/PC 类型、非零 RHS 的一次 PCApply 等价、独立 main/inner/upper overrides 均通过。

同一推送中的独立标准库重放退出 0，核对 2,635 份文件、72 份日志、1,248 次修正、
2,028 个必要求解器观测、468 份体 VTU 和 156 个保存时刻的 780 项字段比较。
该比较数含 130 项直接参考自身对照；其余 650 项对应候选。重放仅重算记录时间的中位数，不重建实际墙钟。
初筛与历史失败仅核对哈希，未混入最终 72 次数值重放通过数。

[源码、环境、每条命令、CI 与原始归档](../research/data/fsi-block-efficiency-2026-11-25/README.md) ·
[配置指南](FSI_BLOCK_PRECONDITIONER.md) · [算法草稿](../../website/drafts/fsi-schur-response-cost.md)。
c4fb266 的数值 run `45622859538` 与网站 run `45622859337` 四项必需检查均通过。
CI 在 GitHub merge commit `aa248d65` 上新运行 15 项数值检查，全部通过，另复用 39 项兼容来源收据；
head/base 和逐项来源保存在 `ci-source-c4fb266.json`。最终文档 head 仍必须获得自己的四项检查。
历史证据复用按来源记录；文档后续提交不计为新的数值执行。
本地未运行全量、Debug 或 PETSc 3.19.6；知识文章未公开发布。

## 2026-11-25 · FSI-PC-02 — 本地及源码 CI 通过，待用户审阅

基线 `f50a4a4338689c9a065bee30ae4a7f3f52c5002e`，分支 `codex/fsi-block-completion`，PR #49。
本轮遵循用户要求：源码先推送远程，再运行相应数值验证；最终由用户审核并合并。
PR 保持 `manual-review`、`no-automerge` 标签，不执行自动合并。
**最终验证 head `b52281d7585ead08e545f29f8d83eca9177e7eac` 推送后，本地 clean Release 8/8 通过；该源码远端 53 项 Release、58 项 Python 及证据/网站检查通过，待用户审核。**
[实际命令、原始收据与复现](../research/data/fsi-block-2026-11-25/README.md)中的归档保留原 `build/...` 路径；下述工作路径可据此对应。

### 实现与审查范围

- `added_mass` 在 dynamics 内消去完整流体速度/压力块，构造结构 Schur 作用；结构 A11 用作预条件，外层继续保留完整 Jacobian 和 ALE 耦合。流体及结构内层采用有界迭代，外层要求 FGMRES。
- `twolevel` 在 hybrid/quantity 的联合流固速度块上建立稀疏分区常数插值和 Galerkin 粗校正；恒等约束行不进入粗空间，允许空本地块和全恒等退化。它不等同于完整多层 AMG 或网格无关迭代证明。
- 使用 PETSc 公共 API 分别配置 Schur main、interior、upper，按对象身份去重并保留各自 prefix；独立 upper 仅适用于 FULL。完整 fluid 的辅助子树也递归配置与验证。同一语义节点的 nodal USER 压力矩阵共享并按 Jacobian 装配刷新一次。
- interior postsolve 通过公开 `KSPCheckSolve` 传播真实 breakdown/PC failure，同时允许有界 ITS；失败报告保留原 field0/field1 路径并增加独立 inner/upper。最终源码只读审查未发现当前固定布局、共形 FSI 范围内新的 collective、对象寿命或算子替换阻塞问题。

### 首轮失败、根因与生产修复

统一采用锁定 PETSc 3.23.7 Release，经 `scripts/cloud/run.sh 3.23.7 release explicit <locked-prefix> <selection.json>` 运行增量选测，不执行全量或 PETSc 3.19.6。

| 源码提交 | 实际检查与结果 | 原始证据 |
|---|---|---|
| `d9f58572e67ffa3636460e21d6d864ea560c8329` | 编译成功；`pc_plan_mpi1/2/4` 全部失败，0/3 | `build/validation-history/algebra-d9f5857`；原收据记录 `dirty=true`，保留原值，不称 clean-head 验收 |
| `0f16d567fa908de9c374621fef2a8ebc48f24dfc` | 增加失败专用诊断后，仅复测 mpi1/2，仍 0/2；没有放宽原断言 | `build/validation-history/algebra-0f16d56` |
| `b8ac03ab162715fca24009f18903da8116ef4ecc` | 修复后 `pc_plan_mpi1/2/4` 3/3 通过，包含独立 Schur/粗空间 oracle、数值更新、空 rank、辅助 KSP、零残量拒绝及故意 PC 故障 | `build/validation-history/algebra-b8ac03a`，clean Release 收据 |

MPI 故障根因为 PETSc GAMG 创建时设置 `useAmat=true`，该状态在用户将 PC 改为 BJacobi 后仍保留。
MPI BJacobi 因而在隐式 Schur 算子上提取不支持的对角子块；串行路径避开该调用。
对已推送二进制加 `-fieldsplit_dynamics_fieldsplit_structure_pc_use_amat false` 后，原奇异局部 ILU 正确传播为
`FACTOR_NUMERIC_ZEROPIVOT` / `DIVERGED_PC_FAILED`。生产修复在语义及 legacy 默认创建后明确选用已装配 P，用户 options 仍最后生效。
串行 `twolevel_identity` 的失败实际发生在压力 GAMG；联合速度的全恒等退化本身正确。
对数值上严格对角且对角项有限、非零的叶子默认直接使用 Jacobi，保留原测试及精度标准。

### b8 物理批次与 retry 精度诊断

`build/ci/fsi-block-physical.json` 的 7 项选测结果为 **5 passed / 2 failed**。
通过：`fsi_tube_rcr`、`pc_twolevel_retry`、`pc_recipe_restart`、`pc_recipe_hybrid`、`schur_verification`。
失败：`fsi_tube` 的双 rank added_mass 32 步轨迹达到旧子进程 130 s 预算；`pc_added_mass_retry` 在串行 t=0.005 的后续重试耗尽。
原始收据和输入/输出保存在 `build/validation-history/physical-b8ac03a`，不能把整批记为通过。

retry 保持原 Neo-Hookean 物理、0.04 终止时间、字段接受条件和 `-snes_max_it 2`。
原外层默认 `rtol=1e-9, atol=1e-13` 接受 4 步后，在 `t=0.005` 的第二次 Newton 线性求解以 RTOL 结束，
真实线性残量为 `3.04444e-13`，mesh 无量纲 RMS 为 `1.45523e-12`，超过该字段约 `1.23e-12` 的接受限值；
缩步后的 mesh 线性 RMS 仍为 `1.47726e-12`。这些是独立线性残量，不冒充失败路径未打印的最终非线性 mesh 残量。
只追加 `-ksp_rtol 1e-11 -ksp_atol 1e-15`，原已推送二进制即完成 32 步至 0.04，`dt=0.00125`，仅有原先 5 次 t=0 缩步。
原失败位置的第 5 步 mesh 非线性 RMS 为 `2.47253e-14`，限值 `1.23476e-12`。
复用同网格既有直接解参考，最终流体/固体全部 Float64 VTK 最大差分别为 `6.04e-14` / `2.62e-15`。
确切 argv、源码/二进制/log SHA256、两次退出码及残量在 `build/diagnostics/retry-b8ac03a/summary.json`；原始日志分别为 `baseline.log`、`tighter.log`。
据此只收紧 retry verifier 各 recipe 变体的外层线性精度，不由这个刻意限制 Newton 次数的 fixture 改动全局默认值。

### 未采用的性能选项与保留的验收预算

在同一 b8 二进制、双 rank 细动脉管、固定外层真实残量目标下，尝试结构内层 max_it=4/2、
结构与流体速度 ASM/ILU(1)、三个 GAMG 粗层 MUMPS LU。
四次定向运行均在 80 s 诊断预算终止，退出码 124；请求 4 步时分别只接受 3、3、1、2 步。
这些组合没有提供可接受的性能改善证据，未进入默认或最终验收选项，也不计为通过。
详见 `build/diagnostics/arterial-budget-b8ac03a/results.json`、`arterial-asm-b8ac03a/results.json`、`arterial-coarse-lu-b8ac03a/results.json`。

保留新增完整 32 步与交替 timing 样本，将 added_mass 32 步子进程预算由 130 s 调至 600 s，
整个 `fsi_tube` CTest 由 600 s 调至 1200 s；其余子进程仍为 130 s。
物理参数、步数、每次修正的真实残量目标 `max(1e-23, 1e-10*rhs_norm)`、字段相对峰值门槛 `2e-6` 均未放宽。
运行更久不等于性能改善，本轮不提前宣称 added_mass 或 twolevel 比直接法更快。

### 最终复验完成与证据复用

`ff81e5bb1a8e02a3f484d855ea074461b716ff66` 加强 VTU 数组/长度/有限性和完整线性日志审计，
已用既有输出及篡改负例独立验证检查器，证据在 `build/diagnostics/validation-guards/summary.json`，没有新增求解器运行。
`b52281d7585ead08e545f29f8d83eca9177e7eac` 仅调整上述 retry 线性精度及实际工作预算；生产求解器自 b8 后未改变。
该 head 推送后执行 `scripts/cloud/run.sh 3.23.7 release explicit <locked-prefix> build/ci/fsi-block-final.json`。
clean Release 收据确认 `fsi_tube`、`fsi_tube_rcr`、`pc_added_mass_retry`、`pc_twolevel_retry`、
`pc_recipe_retry`、`time_retry_verification`、`pc_recipe_hybrid`、`schur_verification` **8/8 通过，零失败/跳过**。
原始收据冻结于 `build/validation-history/physical-b52281d`，持久化报告及归档见
[FSI-PC-02 验证记录](../research/data/fsi-block-2026-11-25/README.md)。

两套动脉网格的 60 次运行全部通过，其中 12 条完整 32 步轨迹共 768 次 Newton 修正。
全部样本最大真实残量/目标比 `0.5600385063731746`；最大相对场峰值差 `1.0712628632823266e-11`，
保留原真实残量和全场接受标准。
三次交替重复的 4 步墙钟中位数：粗网格 direct/twolevel/added_mass 为 `0.416/0.967/7.240 s`，
细网格为 `0.767/4.378/46.404 s`。这些测量未显示新路径普遍提速，不将外层迭代减少等同于端到端收益。

精确复用 b8 clean Release 的 `pc_plan_mpi1/2/4` **3/3** 和 `pc_recipe_restart` **1/1** 通过证据；
生产源码及相关输入未受后续检查器修改影响，这四项不记为 b522 本地新运行。

b522 源码 [数值 CI run 45606963270](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45606963270)
已完成：选测、PETSc 3.23.7 Release 和增量证据收据均为 success，**53 项数值选测、58 项 Python 检查通过**。
[网站 run 45606963330](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45606963330) 的
Build VitePress 与未发布内容隔离检查成功；Debug 和 PETSc 3.19.6 手动专项按策略 skipped。
[源码 CI 元数据](../research/data/fsi-block-2026-11-25/ci-source-b522.json)保留实际 job 状态，
这些是 b522 源码的运行结果，本次文档补记不计为额外数值执行。

最终归档为 7,180,452 bytes，SHA256 `03990426bfc193038353da504f38119cd006cf8ea7fd95743cb1ccb66f4bccdf`，
含 2,557 份数据文件及 3 份 manifest/generator 文件，保留原 build 路径。
全部 12 条完整轨迹与 60 份运行日志已核对文件哈希和输出新鲜性；归档和重放入口见上述持久化报告。
归档与独立复核脚本先推送为 `370358f3c9210eec8a1699dcd1db2c67f7702d74` 后执行复核，退出码 0。
2,557 份文件哈希通过，60 份日志的 1,152 次线性修正与 288 份完整轨迹体 VTU 的
96 个保存状态、480 项字段对照全部复现；回执为 `replay-result.json`，没有新增 MPI 求解。
本地实现、源码审查与目标验收已完成；本轮未执行全量或 PETSc 3.19.6，也不扩大为多节点可扩展性结论。
PR #49 保持人工审核和禁止自动合并；最终由用户审核并合并，知识文章保持草稿。

## 2026-11-24 · 弹性管与 RCR 连续开发记录

- 基线为 main 的 `6a5ac96`，工作分支为 `codex/fsi-smooth-load-six-hour`。沿用 PETSc 3.23.7 Release 和仓库编译脚本，外部 svFSI 固定为 `94a2ff5`。外部数值干预各有独立程序、输入和原始求解历史。[外部编译方法](../research/data/fsi-pressure-faces-2026-11-24/build-svfsi.sh)
- 先在两端同步升压的圆管中核对载荷时间层、镜像截面、角点空间加密、不同时间尺度和单元度量。随后加入固定几何的独立线性 DAE 与圆形子午面，分别检查离散方程和物理几何。[时间尺度控制](../research/data/fsi-linear-transient-2026-11-24/time-scale.md) · [空间和时间证据](../research/data/fsi-smooth-load-2026-11-24/README.md)
- 实施固定与面内移动的多 RCR、流量入口曲线、组织支撑、独立储液压力和压力采样曲线。每项检查涵盖实际接受步和端面场，关键路径包括同分区续算及缩步重试。[端口与流量符号](../research/data/fsi-rcr-2026-11-24/README.md) · [外壁边界功](../research/data/fsi-wall-support-2026-11-24/README.md)
- 以 20 mm 物性管分别复核双端增压、有反向流量的正弦灌流、全周期正向灌流。保持同网格同边界，只改外部程序 RCR 牵引的时间层，分离了端口阶段误差与轴向网格误差。[实测端口压力与流量](../research/data/fsi-linear-transient-2026-11-24/perfusion.md)
- 对 Tet4 精确矩、单体分块预条件和接受步质量历史作配对测量，保存两域场和每次求解状态。单机测量期间存在资源竞争，阶段时间与端到端时间分别报告。[阶段成本](../research/data/fsi-phase-costs-2026-11-24/README.md) · [质量守恒诊断](../research/data/fsi-phase-costs-2026-11-24/mass-history.md)
- 核对 20 mm 管真实的 $Ax-b$ 与四组物理行 RMS 的合成值，区分线性迭代用尽、非线性线搜索停滞、消减误差和进程信号。按相同输入检查修改正交化后的解与直接解；外部 BIPN 在同一上游提交上保留独立的观察、重算及 QR 版本。[可运行网格与 PETSc 参数](../research/data/fsi-linear-transient-2026-11-24/arterial-solvers.md) · [BIPN 各步证据](../research/data/fsi-linear-transient-2026-11-24/bipn-residual.md)
- 核对分叉两端的频率响应和容积谐波。曾有两个不同周期数的研究进程使用同一输出目录，原始摘要发现输入已改变。用单独目录重新运行 16 周期计算，增加输入与程序摘要、写入锁和完成结果校验。同输入复用、不同周期数拒绝均已实测。[刚性及弹性分叉](../research/data/fsi-rcr-2026-11-24/junction-harmonic.md)
- 单机四进程独立复算内径 20 mm 的压力管，逐秩退出码和启动器退出码均为零。32 个物理步内的 64 次线性修正全部满足真实残量界限，8 个输出时相的各场与直接解的最大差为对应场峰值的 1.99e−10。固定上游 svFSI 的粗、细两网格各做五种 BIPN 对照；收紧两个内层绝对容差后，粗网格 120/120、细网格 129/129 次修正达标。[四进程逐步记录](../research/data/fsi-linear-transient-2026-11-24/arterial-four-ranks.json) · [原始 BIPN 真实残量](../research/data/fsi-linear-transient-2026-11-24/bipn-residual.csv)
- 用原始 VTU 重新核对七个镜像截面并复测 #46 的四种负对照。单点应变加 0.001、缺失截面、移动截面和错时刻均在对应检查处失败；正例复现已归档的每项节点场指标。[镜像验证与失败原因](../research/data/fsi-smooth-load-2026-11-24/README.md#axial-reflection-control)
- 双进程周期回归曾在第 28 步后发出信号 11。用同一程序和分区三次跑完 80 步，三次均逐字节复现故障前的 224 份两域与边界 VTU。另在单进程小计算中由父进程和各秩分别记录退出码，区分求解器返回零与 MPI 启动器退出异常。[周期回放](../research/data/fsi-smooth-load-2026-11-24/mpi-periodic-replay.json)

单列圆管入口、组织支撑、RCR 耦合与 RCR 谐波/重试后，原 50 条断言的语法树与数量逐项一致。四项在记录子进程实时输出的版本上全部通过。同一单机采用不同的绑核及共享内存选项时，仍观察到测试超时。复用结果与新运行分别标出提交、目标与原日志摘要。[最终 Release 收据与历次失败](../research/data/fsi-smooth-load-2026-11-24/release-validation.md)

## 2026-11-24 · 压力端面历史、惯性缩步与独立管壁对照

基线为 `951064d`。受压面与装配共享标签和相邻流体单元，开关独立于 VTU 写出，缩步与续算均在接受步写记录。按倾斜面解析解检查面积、法向黏性项及流量，再从瞬态 VTU 的节点场独立重建 stage 和 endpoint。编译使用 `scripts/cloud/run.sh 3.23.7 release explicit`。[选测、版本和复现](../research/data/fsi-pressure-faces-2026-11-24/README.md)

首次四项选测中，原 `fsi_pressure_state` 在 generalized-α 第三步耗尽了 16 次重试。单独检出原主线，复现同一故障和一个速度增量为 1 ULP 的单元反例。分别插值两个大致相等的速度、随后相减，会让短步长放大舍入误差。改为先在节点作差，原求解容差、Newton 上限和重试预算下通过。数值提交 `ae6c8f6` 的 36 项增量选测通过，最终 `3697204` 的 4 项针对性检查通过。单独提取旧归档的部分文件时遇到跨目录硬链接，完整解包后按输入摘要验证。[原失败及通过收据](../research/data/fsi-pressure-faces-2026-11-24/validation.json)

固定上游 `94a2ff5` 后重新编译 svFSI，先复现 0.25 s 工况前四步的全部已保存场，再运行 0.125 s。12 组 EONSim 计算区分了阶跃、光滑升载和默认/固定稳定化。svFSI 场的时间层取其 VTU 输出时刻，EONSim 的阶段由相邻节点场按算法权重独立重建。首步 BE 求积处理解释了累计流入的一部分偏差，1 s 的跨程序截面差仍存在。[原始场、逐端面记录与判据](../research/data/fsi-pressure-faces-2026-11-24/README.md)

## 2026-11-24 · 知识网站选编、公式渲染与教程复核

原网站构建返回成功，但静态 HTML 中公式所在处只有空注释。将手动加载的 Markdown 数学插件改为 VitePress 1.6.4 的 `markdown.math`，以便 Vue 在服务端保留 MathJax 元素。四个新数值页面已生成 18、13、23、6 个公式，原单体 FSI 专题的公式也已恢复；生产内容检查新增对已渲染 SVG 公式的回归断言。

运行 `npm run docs:build`、`npm run docs:check`，核对 50 个上游条目、所有 34 份草稿的归类、波形图资源及新栏目链接。使用 `replay.py --verify` 复算 Womersley 归档，使用仓库 `scripts/cloud/run.sh 3.23.7 release explicit` 和既有 P2 教程清单编译，5/5 项通过。数值性能和网格加密表引用主线归档。

## 2026-11-24 · HPC 开源项目复查、仿射 Tet4 黏性积分

基线 main `89a1a3d823396df02fa9e8acb5ded36b70938e9c`，本地分支 `codex/hpc-survey-tet4-tangent`，数值提交 `4095e4bd4e18a350e62fd2e295d88de3a6d48640`。抽查上游实现/接口和公开说明，恢复锁定 PETSc 3.23.7。用 `scripts/cloud/run.sh 3.23.7 release explicit` 编译与选测，对照 4/4、候选 9/9；独立合成 #41 `10197d0` 与 #42 `0c8f6fb` 后应用数值改动，圆管选测 2/2。在畸变四面体上检查简单剪切和刚体转动的解析节点力，保留 FSI 几何种子求导。实际命令、选测文件和逐项结果见[复现记录](../research/data/tet4-viscosity-2026-11-24/README.md)。

首轮通过带超时的文件重定向子进程测量墙钟，发现短算例读数在轮询时间隔附近聚集。改用管道等待输出结束，将日志写盘置于计时区间外，重新执行全部 6 对和预热，报告仅用修正后的样本。最终逐对比较全部 owned 节点数据，流体、弹性 FSI 各 1/2 rank，各步迭代数一致。1 rank 固定流体单元核变化 −29.6%，弹性 FSI 的端到端配对范围跨零。后续先对齐 #42 的瞬态，再实测 FSI 各子阶段成本。[完整报告](../research/HPC_UPSTREAM_REVIEW_2026-11-24.md)

提交审阅前同步已合入 #41 的 `main@f7ec770`。以该主线为基准运行 `scripts/cloud/selection.py --offline` 得到 10 项增量选测，加入 `womersley_flow` 后用 `scripts/cloud/run.sh 3.23.7 release explicit` 编译并执行，11/11 项通过。公开数值提交 `7a0416d` 的源码树与配对测量使用的本地提交相同。

## 2026-11-20 / FSI-PROD-02B / 振荡刚性管

从 `89a1a3d` 建立独立分支，求解器实现为 `62c0b2f`，场审计与跨程序工具为 `bef75bd`。
执行锁定 PETSc 3.23.7 Release 相关小算例，核验三种格式的压力加载时刻、1/2 rank
重启、参数变化拒绝和旧 main 的真实检查点。同一旧检查点按原分区在新程序上续算，
1 和 2 rank 两组终点场的最大差均为零。归档了粗网格误差超过事前门槛的结果、
svFSI 输入和迭代失败，以及两处已修复的本地回归脚本故障。

独立从正负峰值与周期终点 VTU 积分速度、压力、散度、分截面通量。固定版本 svFSI 在相同
几何、负载、时间步和端面分量约束下跑完三个周期。细化后的 59,616 个四面体给出 0.7554% 幅值误差，压力迹的幅值偏差仍有 5.68%。该网格上 EONSim 与 svFSI 的复流量差为 1.3046%。20 组 EONSim 和 3 组外部运行共归档 200 个文件。默认稳定化的相邻步复流量变化为 0.3694%、0.3659%、0.6522%，固定 τ 的独立时间细化给出 1.960 和 1.991 阶。两、四进程均与串行端点吻合。源提交 `f802fa3` 的 Release 增量检查和证据收据已通过。[数值 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/44724492072)
[刚性管 PR #41](https://github.com/saitoasukakawaii/EONSim-new/pull/41) · [静压管壁 PR #42](https://github.com/saitoasukakawaii/EONSim-new/pull/42) ·
[数值、命令、失败记录与原始场](../research/data/womersley-2026-11-20/README.md)

## 2026-11-13 / CI-DEBUG-ON-DEMAND / 源码修改

基线 main `f34658082644eb5238ee4cc651d71823fe5d1587`。发现 core-numerics 双模式测试、receipt.py 强制双模式、selection.py 双模式历史来源、agent 自动合并五项必需检查彼此关联；不能简单删除 Debug job。同步修改 Release-only PR、手动 Debug、收据复用和自动合并检查。未执行 PETSc/MPI 求解，CI 结果须读取实际工作流，不能从文件存在推断通过。

## 2026-11-20 / FSI-PROD-02C / pressure–area study

Base `89a1a3d823396df02fa9e8acb5ded36b70938e9c`. Study source
`d08958e1e968640a35315b0571a849fc234ef36a`. The wall branch adds an optional
layer count to the existing tube generator, with byte-identical default
output. Thirteen isolated wall solves include single-direction refinements,
two pressures and 1/2/4 ranks. Coupled runs include two BE step sizes,
an MPI repeat and separate generalized-alpha pairs. Local locked Release
receipts cover `fsi_tube` and `lame_wall`. EONSim/svFSI cases use identical
volume cells and projected conforming interfaces. The archive preserves
failed numerical cases and the native predictor diagnosis. Five paired runs include
two common-pressure time steps with all saved wall states. The largest startup
difference is 9.947% at Δt=0.5 s and 8.444% at Δt=0.25 s. All 547 inputs and
fields are included in the expanded archive. [PR #42](https://github.com/saitoasukakawaii/EONSim-new/pull/42) · [Results](../research/data/lame-wall-2026-11-20/README.md)

The initial PR policy mapped 31 Release CTests. GitHub completed the
selection, locked Release job, evidence receipt and website checks for the
expanded data at `749739d`. A fresh extraction reproduced every recorded
field metric with the original external binary VTUs. The selection mapping
requires human review under the repository's merge rules.
[Initial numerical run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/44723204965)
· [Expanded data numerical run](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/44724685272)

## FSI-PROD-02 continuation / in_progress / 2026-11-07

Continued the same `codex/fsi-tube-qualification` branch from `92d63f1`, main
`dc37852`; PR #38 remains open. Source `4113ab8300410459dbfb057db5d4978e7d106aa7`.
Restored locked PETSc 3.23.7 in an 8 GiB Linux container. Added exact pressure/velocity
field and local divergence diagnostics, plus a seed-mesh runner. Five actual serial
solves: 96/12/24 sectors/radial/axial gives flow error 0.546409%, velocity L2 0.320760%,
pressure RMS/drop 0.489014%, end-pressure-drop error still 5.140012%. A 96/8/16
1/2/4-rank comparison has maximum field difference 5.31e-16. These isolated results
are not full PROD-02 acceptance; Womersley, elastic walls, default transient tau,
svFSI, error budgets and full review remain pending. No new PR or merge.
Release tube regression 1/1 and Python 6+3+26 checks passed; historical Debug
results reused, not rerun. Root MPI rejection and initial test-oracle arithmetic
mistake are recorded. [Evidence and replay](../research/data/rigid-tube-seeds-2026-11-07/README.md).


Execution notes: original EONSim workspace connector returned internal errors twice.
A fresh checkout of the existing branch was used; old uncommitted work could not be
inspected. Git HTTPS push dry-run lacked credentials; repository objects are uploaded
through the connected GitHub API, with tree equality checked. No auto-merge.
The new numerical solves use unchanged source at 92d63f1; postprocessing source is
4113ab8. Commands, initial failures and raw inputs/fields are in the evidence link.


## 2026-11-06 / FSI-PROD-02A 刚性管稳态流量基线

- 恢复：远端已合并PR #36/#37，基线dc378529538259567a78cea9820a202a6187809c。
  复用当前checkout，未修改旧WSL工作区。Windows Git报告295个M但diff空；逐文件确认原始blob
  与索引一致后刷新这些路径的索引，确认暂存diff为空，才建立独立分支；没有reset或丢弃用户修改。
- 实现：a0d228764850fa838229acb6a6e613933070490f。原接口每tag单一条件不能表达相容的
  Poiseuille端面：只允许按互斥笛卡尔分量组合流体条件，压力可选分量；规范检查移至实际法向
  trace，唯一标签诊断避免重复计数，签名涵盖全部条目。固体仍要求tag唯一。
- 验证设计：R=1/L=2/rho=mu=1/Delta p=.02，Re=.0025/alpha=0；充分发展稳态解，
  red细分保持多边形边界；几何变化单列。事前设定流量2%、末档变化1%、MPI2e-9、净通量1e-10。
- 首轮七个串行状态和MPI完成，但level-2场变化5.670926%/2.479559%失败；继续12边形到level4、
  48边形到level3、补24边形level3，不重复原状态。最终流量1.264676%、末档变化
  0.410813%/0.024769%、MPI2.78e-17、净通量4.12e-17通过；压力3.993089%仍未资格化。
- 实际构建与检查：仓库run.sh、PETSc3.23.7、WSL2、单线程/单MPI队列；首轮Release
  tagged_fluid/regions 2/2；扩充重启分量/规范检查后Release tagged_fluid/rigid_tube 2/2；
  Debug三项3/3。网格与重算3项、CI选择26项。此前CI选择在Windows遇到Git所有权保护，
  仅为当前进程设置该checkout safe.directory后通过；无全局配置修改。无数值求解失败。
- 证据：[原始数据、命令、校验和及迁移重算](../research/data/rigid-tube-2026-11-06/README.md)。
  构建原SHA/dirty字段保留，以实际数值源码哈希与二进制身份关联实现提交。未做性能测量。
- 自审：流量通过不能掩盖压强和局部散度误差；几何界适用于连续多边形解，不是FE约束。
  没有独立审查者。未重跑无关FSI/时间研究；PROD-02的Womersley、弹性管、瞬态tau、svFSI待后续。
- 知识沉淀：按eonsim-knowledge-capture生成[草稿](../../website/drafts/rigid-tube-geometry-and-mixed-boundaries.md)，
  区分理论、实现、实际验证和未测性能，保持draft；本地验收完成，已创建
  [PR #38](https://github.com/saitoasukakawaii/EONSim-new/pull/38)，未合并。
- 云端最终验收：[run 42236840428](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42236840428)
  PETSc3.23.7 Debug/Release各26/26，零失败/零跳过；Python26+6+3=35项与增量receipt通过。
  网站run42236840526通过。测试合并预览3f4625c394cb487a17b00a400ea98d2b9eb53375的tree
  2802d32421aa6c6c9ec49ac0146862b3de0d7853与已审查head d1c4be0完全一致。
  Debug运行较久，期间日志尚未发布，结束后读取实际成功计数；没有假定提前通过。
  最终补记仅文档/证据，后续CI应复用同PR成功收据。完整11状态研究仍是本地证据，CI只做小回归。

## 2026-11-06 / FSI-QA-01 质量预算有效性修复

- 基线：main `815755eb15ffb63299487e8f9163ddc9d242a2f2`，PR #35已合并。工作区连接两次内部错误，改从GitHub核对后克隆主线；未修改原连接工作区。
- 源码：`80571b102e31dd2e7664a64a39a92efc8402045c`，分支 `codex/fsi-mass-history-validation`。
- 复现：一条t=.1、dt=.1、进出流均0、体积1的历史，传入`initial_volume=NaN`，旧函数返回`final_defect=NaN`而`max_absolute_defect=0`。t=1e-12、accepted_dt=-1e-12也通过旧绝对容差检查。
- 根因：初始质量状态未验证；NaN在max归约中可被掩盖；时间一致性容差没有单独约束接受步长符号。有限输入也可在积分中溢出。
- 修复：验证初始三标量有限/体积正值，接受体积和步长正值、时间差有限；积分和缺陷在归约前验证有限性。梯形积分公式和既有时间一致性容差不变。
- 实际测试：`python tests/test_fsi_cycle_metrics.py` 10/10；`python tests/test_fsi_archive.py` 2/2；`python tests/test_fsi_field_cycles.py` 8/8；`python tests/test_fsi_space_metrics.py` 6/6。均为系统Python、无MPI/无PETSc依赖、无C++构建配置。`git diff --check`通过。
- 归档重算：以下命令实际执行，9组22400行、36个质量预算值精确一致；这是旧求解输出的新后处理验证，不是新的数值求解。C++/PETSc 3.23.7 Debug/Release、MPI以及3.19.6均未运行。
- 自审：volume_budget所有调用者共享修复；正常非零起始时间/非零初始通量续算通过；归档和原收据未改写。无独立审查，不推断既有数值证据曾含异常状态。
- 文档生成曾因嵌套here-document结束标记冲突失败，确认无文件变更后改用结构化补丁。代码修复没有失败尝试。
- 知识：补入既有周期FSI草稿，保持draft，无新架构决策。

```sh
python - <<'PY'
import csv,gzip,json,sys
from pathlib import Path
sys.path.insert(0,'scripts')
from fsi_cycle_metrics import volume_budget
root=Path('docs/research/data/fsi-next-03/time-accuracy-final')
count=0
for expected in json.loads((root/'mass-convergence.json').read_text()):
    name=f"{expected['scheme']}-{round(.1/expected['dt'])}"
    with gzip.open(root/name/'flow.csv.gz','rt') as stream:
        rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(stream)]
    result=volume_budget(rows)
    assert all(result[k]==expected[k] for k in result),(name,result,expected)
    count+=len(rows)
    print(name,len(rows),'rows: exact match')
print('PASS: 9 archived histories,',count,'accepted rows; all 36 budget values unchanged')
PY
```


## 2026-11-05 / FSI-NEXT-03 验收与PR #35交付

固定τ=.05的n=2/4/8、dt=.001/.0005六状态分别在77/88、39/49、31/31周期达到连续三周期判据。
全部完成三个十周期尾项区间和两周期真实100相位采样；时间/瞬态/采样预算的逐字段最大比分别为2.765560%、0.589428%、0.001042%，均严格小于10%。
空间五场差均递减，但观测阶不统一，不能宣称全场二阶或连续模型渐近误差已证明；默认随dt变化的τ候选仍未通过。
18个可恢复包迁移后核验49305文件，实际尾项与完整预算重算完全一致，原receipt未改写。
全部周期与追加研究审计77100行接受历史，质量/流量/正几何和100相位边界约束通过。
本机构建及fsi_periodic 1/1（含1/2/4 rank）、迁移修正e4bda86的6项检查通过；其余未受影响历史检查复用，本机未重跑。
本地验收与自审完成；[PR #35](https://github.com/saitoasukakawaii/EONSim-new/pull/35)已创建，[云端数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457299)主锁Debug/Release各29/29通过，零失败/零跳过；54项Python检查与[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/42049457283)通过。状态review，未合入main，不自动合并。[本轮证据](../research/data/fsi-next-03/local-recovery-2026-11-05/README.md)。

新执行命令及阶段退出码见证据matrix-status.json；归档重算见relocation-audit.json及relocated-budget.json。
原始失败未删除，冻结的生产输入74份逐字节匹配Git，二进制SHA保持不变。
n=8尾项交付包明确只保留每个区间末周期实际场；全部标量历史保留，迁移后从这些场重算验证。
本轮自审没有未解决阻塞项；不声称独立外部审查。按eonsim-knowledge-capture收敛既有草稿，未发布。

## 2026-11-05 / FSI-NEXT-03 本地接续与归档迁移修正

- 恢复最新分支`1b33db8`，核对main仍为`4f3a995`；保留已有Linux旧项目的未提交修改，复用其锁定PETSc依赖。
- 仓库完整下载无有效进度，按需取源码/相关归档；Windows换行导致首轮shell入口失败，恢复LF后用仓库run.sh成功编译。
  Release只执行`fsi_periodic`，1/1通过；构建dirty标志原样保留，74份生产输入逐字节匹配Git。
- 固定τ粗网格归档878文件、7700行接受历史和研究指纹核对通过；本地二进制完整周期重放最大场差2.21e-15。
  n=2半步长从初态计算88周期收敛；n=4两步长39/49周期收敛；n=8原步长31周期收敛；五状态尾项和100相位采样完成，n=8半步长继续。
- 发现原误差估计仅用绝对目录名和generation绑定，导致完整数据换机器后不能审计。
  `e4bda86`改为generation、完整检查点SHA、网格SHA和研究定义校验；`python tests/test_fsi_space_metrics.py`6/6通过。
  不改原receipt，不允许用路径迁移跳过不同构建的重放验收。
- 原固定n2续算包仅含30份索引/日志，没有实际场片段；本轮真实重算尾项/密集采样，并归档全部引用文件和SHA。
  归档辅助脚本最终打印的st_size调用错误已修正，重新生成并回读验证；未涉及求解。
- [本轮命令、日志及数据](../research/data/fsi-next-03/local-recovery-2026-11-05/README.md)。
  五状态15个归档迁移后45833文件SHA匹配，三个区间场差和尾项全部重算一致；10组续算的22400行接受历史质量/几何检查通过。
  n=8尾项包保存各区间最后周期的实际场及全部标量历史；大采样包4 MiB分片后重组SHA匹配。完整原件保留本机。
  无新Debug或全量检查；其余历史证据在未改数学/输入路径的前提下复用。整体尚未完成，无PR。
  使用eonsim-knowledge-capture更新既有误差分离草稿，未发布。

## 2026-11-04 恢复与串行补验

2026-11-04 已从远端 a67f329 恢复同一分支，核对 main 仍为 4f3a995。默认三网格归档逐文件校验通过（923/743/678 个文件），重新审计 8600/5000/3700 条接受步。使用仓库 restore.sh 和 run.sh 恢复 PETSc 3.23.7 Release，所得可执行文件 SHA-256 为 b4de28ffc6481701b533ec4772f4f0f604cfc18bc15bc63c858ebebae38352da。单一 MPI 队列的 fsi_periodic、fsi_flow、fsi_inlet、fsi_pressure_state 均通过。旧固定 τ 算例缺少原始场和 checkpoint，固定 τ=.05 的三网格与两步长研究从初态重算。完整误差预算、证据审查及 PR/CI 仍待完成。 原始日志、JUnit、构建摘要及归档复核见 docs/research/data/fsi-next-03/recovery-release/。

## FSI-NEXT-03 环境中断检查点 / 2026-11-03

执行环境被标记 unavailable，exec-server恢复超时；当前无法确认后台进程存活。不是预算耗尽，也不是整体完成。最后完整远端源码/证据检查点20ac3af；本提交通过GitHub API保存断开前已验证的两项Python修改和恢复记录。未创建PR。

默认稳定化n=2半步长dt=.0005在136周期达到周期判据，但20相位压强场差0.08908已超过末档100相位空间差0.03899的10%；候选拒绝，阈值不变。默认tau显式依赖integration_dt，时间加密同时改变稳定化；不能把全部差异解释为积分截断误差，也不据此宣称程序错误。固定tau=.05的三网格、半步长、尾项和100相位对照已排入单一MPI队列，尚未取得完整结果。n=4默认半步长最后确认在第28周期。

旧队列重复启动造成额外Release回归4项OpenMP启动断言失败、3项通过；失败日志在本地duplicate-worker-release，尚未确认推送。旧worker已退出，4项串行补验已排队。底层断言及旧描述符再次出现的精确原因未证实。n=4跨构建完整周期重放全部场差0；固定tau n=2旧状态7700行完整历史、压降/质量/几何/无滑移独立审计通过。断开前执行 `python tests/test_fsi_space_metrics.py`，5/5通过，包括新增固定tau一致性与不一致拒绝；不代表完整数值预算通过。

恢复顺序和未上传证据见 `docs/development/FSI_NEXT_03_RECOVERY.md`。恢复环境后继续同一分支，全部验收/证据/审查前不创建PR。

## FSI-NEXT-03 自审修正与实测尾项

阶段检查点已推送 `4119d8622a708997d25b66453957f33d178fdb6b`，与本地对应tree一致，无PR。随后自审修复连续但末尾截断历史可能被误复用的问题：原因是仅验证相邻时间连续性，没有验证达到声明终点；新增终点/步数/精确相位校验，并排入截断历史负例。时间矩阵原始数据在SHA和配置核对后显式迁移定义并重新分析，全部门槛仍通过，无重算/补造数据。

n=2在原86周期状态之后追加三个十周期块，完整场块间收缩率约0.54–0.57；得到经验尾项估计，非严格误差界。n=4追加周期与n=8周期检测继续。审查同时区分了波形重建与相位积分误差：正式空间/时间场差采用真实100相位，50/100统计差作为采样误差；20相位插值诊断另列。用户要求的时间/剩余瞬态10%阈值未改变。

## FSI-NEXT-03 时间精度与质量预算已验证，空间研究继续

本地基础提交 `96f232f`，后续改动尚在同一分支实施。三格式完整第二周期的时间精度矩阵已通过：BE 最小受检阶0.864，BDF2 1.882，generalized-alpha 1.981；参考加密差占最小候选误差3.17%–3.21%。累计质量预算的最大误差阶分别约1、2、2。它们是固定tau、n=2的瞬态验证，不替代稳态空间研究。原始配置、压缩CSV/日志和第二周期场已归档 `docs/research/data/fsi-next-03/time-accuracy-final/`。

新增可选 `fsi.checkpoint_interval`，默认仍每个接受步保存，指定停止点/最终接受步必保存；周期研究仅需每周期保存。仓库编译脚本完成 Debug 7/7 受影响回归，证据 `cadence-debug/`；后续纯Python相位采样/压降检查仍继续针对性验证。默认稳定化n=2已在第86周期通过，n=8仍在运行；从已收敛状态追加周期的瞬态估计和真实100相位输出复核正在实施。没有创建PR，也未声称48小时预算耗尽。


## FSI-NEXT-03 连续实施进展（未整体完成）

完成完整场参考体积加权周期比较、实际时间插值（禁止外推/大间隙）、周期checkpoint续算及定义/历史拒绝、独立Tet4移动体积与通量oracle、跨网格P1比较初版。Debug/Release新增fsi_periodic各1/1通过，涵盖1/2/4 rank、恢复、未收敛和修改定义拒绝；后续相位插值改动仍需针对性回归。固定tau n2第77周期、默认tau n4第50周期达到连续三周期1e-3判据，不能混合作为空间序列。

首次60周期上限正确拒绝；并行续算遇PMIx初始化及LLVM OpenMP启动断言，改用独立临时目录、串行MPI研究与PID隔离，保留失败日志。发现两段持久CSV尾部缺失：从相同初态/物理checkpoint真实重放，重放终点全部比较字段与原快照差为0，已有重叠行一致，保留原件后恢复完整历史；精确文件截断根因尚未确认，不归咎于求解器或平台。

时间粗矩阵及首轮加密仍有BE固体速度未进入渐近区，门槛未放宽；继续加密时间步和独立参考。完整网格序列、时间/瞬态10%污染、相位采样、最终复核和PR/CI未完成，无PR。可复用知识草稿：website/drafts/fsi-periodic-state-and-error-separation.md（未发布）。

## FSI-NEXT-03 启动检查点

已核对 PR #33 合入 main `4f3a995`；其下方未合并表述保留为历史。用户授权48小时计划实施，独立分支 `codex/fsi-next-03-periodic-convergence`，状态 in_progress。首先核查周期剩余瞬态和稳定化尺度；尚无新的数值通过或收敛结论。全部本地验收与审查完成前不创建PR。验收清单及剩余项见 CODEX_TASK_QUEUE.md。

本文件记录有实质代码、算法、验证或知识产出的开发会话。只记录事实，不写无法复现的“已优化”“性能显著提升”等结论。

### 首个实施检查点：尚未整体完成

新增 `scripts/fsi_cycle_metrics.py` 和四项合成历史验证（全部通过）；仅标量后处理，不能据此宣称完整场周期性。仓库编译脚本完成 Release 编译和 fsi_flow 1/1；首次 LLVM OpenMP 启动断言失败原样保留，使用上一轮PID隔离办法后通过，精确底层根因未证实。30周期2-rank/n=2/dt=.001固定tau与默认tau对照已完成，末周期位移归一化RMS差分别1.77e-4/1.55e-4（尺度1e-4），均值约4.489e-4/5.642e-4，差约26%。这不是空间收敛、完整场周期性或稳定化错误的证明。

证据 `docs/research/data/fsi-next-03/`。下一步：完整场多相位采样与停止/续算，再建立稳定化受控的时空误差矩阵；剩余验收仍见任务队列。没有创建PR。48小时预算未声称耗尽，当前也没有已确认不可解决的阻塞。

## 2026-11-03 / FSI-NEXT-02 — 周期流量、无滑移与移动域质量预算

- 用户授权20小时预算、同一独立分支持续实施、阶段检查点；全部本地验收/审查之前不创建PR，完成后唯一汇总PR且不自动合并。基线main `b2755b6`，分支 `codex/fsi-next-02-periodic-flow`，实现 `9bde79765ee57a2c42eb2964ac8297ec6246e3a7`。
- 首先读取 main/仓库契约；此前20小时计划原文未检索到，未以其它仓库历史计划替代。按本次明确目标在队列落实可执行验收。
- 现有仿射入口不能表达四边为零的非零截面形状；新增P1矩形形状的离散通量归一化与平滑周期波形，复用既有整体求解、端点/stage映射和签名机制。
- 新诊断独立积分当前表面通量与体散度，分开stage预算、secant体积变化及后处理累计预算。无滑移通道用真实弹性顶壁和夹持边界，非预设运动。
- 使用 `scripts/cloud/restore.sh` 和 `scripts/cloud/run.sh` 编译；Debug/Release 新增1项、旧入口/压力2项均通过；三格式/1和2rank/恢复/Jv/9次真实缩步重放。六周期研究完成三网格和三步长，原始数据与局限见[验收](../research/data/fsi-flow-2026-11-03/README.md)。没有全量和3.19.6编译，也没有性能研究。
- 重要失败：空环境恢复；MPI root拒绝；LLVM OpenMP启动断言在串行重试仍复现，保留失败且不冒充正确非法参数拒绝；避开残留注册PID名字后完整复验通过，底层断言精确原因仍未回溯确认。Git push无凭据，使用GitHub API保存相同tree后同步本地。详细命令、失败尝试、解决范围见验收，不将环境规避写成数值修复。
- 本 agent 完成源码diff自审、26项CI选择器测试；无外部独立审查。知识稿 `website/drafts/fsi-periodic-flow-mass-budget.md` 保持草稿；长期架构未变，不改架构契约。
- 本地验收/证据/自审后仅创建 [PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33)。[数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424335) Debug/Release各29/29通过，零失败/零跳过；[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424264)通过。 增量证据job也成功；不需要代码修复。合并预览tree与本地/PR head完全相同，精简证据见 `delivery-ci.json`。PR #33 随后于 2026-11-03 合入 main，合并提交 `4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e`；任务状态更新为 done。后续纯文档更新不重新运行未受影响的数值测试，保留并引用原 CI 来源。
- 同时核对前置 FSI-NEXT-01 已由 PR #32 合并为基线 `b2755b6`，纠正队列旧 in_progress，历史记录明确标注。

## 2026-10-31 / DOCS-01 — 全仓 Markdown 进度同步

- 用户要求审查全部 Markdown 并按当前进度更新；基线 `a508e3d`，在 `codex/markdown-progress-audit` 工作。本次只修改文档，未推送、合并或部署。
- 清点 88 份既有项目 Markdown，覆盖根入口、架构、研发/研究、Skill、环境、网站正式页面/草稿/模板；逐文件处理清单见 [审查记录](MARKDOWN_AUDIT_2026-10-31.md)。依赖包、构建产物与 Git 内部文件不属于项目文档。
- 根因：多个文档保留不同检查点的“当前”描述。同步 PR #24 已合并、G0/G5/G1 已交付、旧 PETSc 手动专项、Doxygen 实际输入和平台范围；明确 G2/G4 子集及历史 BE/测试计数。
- 按源码确认 checkpoint 容器仍 v3、二维分区 v3/三维 v2，并补充二维标量 LinearSolveFailure 的重试边界，未改数学模型。
- 用 eonsim-knowledge-capture 修订既有草稿和知识索引，补后续验收来源；没有新增数值/算法成果，不另造教学文章，不将草稿转为发布。
- 静态检查脚本首次把数据目录误判为网站页面、把首页 layout: home 判为缺标题；修正检查器的路径/页面分类后复查。旧研究中不可移植的 Windows 链接改为原工程相对路径与行号，保留来源提交。
- 实际执行 `python3 /tmp/eonsim_md_audit.py` 检查全文结构、本地链接/锚点和固定 Git 源码目标，`git diff --check` 检查空白；最终结果见审查记录。`command -v node` 未找到 Node，本次未执行网站构建或产物隔离检查。
- 未运行 CMake、编译、CTest、MPI、数值或性能实验；未访问外部文献链接或远程 PR Checks。PR #23 测试数字引用已归档证据，不是本次新结果。

## 2026-10-31 / G5 — generalized-alpha ALE与单体FSI

- 以25e0945为基线，独立alpha云端CI三环境成功。共同af、一阶流体/二阶运动学、各自算法历史接入单体残量和checkpoint；明确stage力/功率输出。
- 新增提交前端点几何检查，rank局部失效先allreduce再共同拒绝。
- 主锁Debug10项针对性CTest全部通过（324.63秒），rho=0/0.5/1的速度/压力/位移趋二阶，整体J差分约1.8e-9；1/2/4rank完整历史、事件重启、接口运动与功率通过。
- 首次极小步重试对照因时间戳相减及接口位移消减而算法网格加速度不一致；改为17位实际步长重放、接口直接共享stage速度，保持原容差后通过。
- ALE rho0.5粗步启动误差抵消，改用更细同问题网格时间步进入渐近区；未改阶数阈值。
- ALE补充实测stage有效/endpoint反转，坏单元rank分布3/1/2/0；缩步恢复与失败checkpoint哈希不变通过。FSI独立端点反转分支仅审查，未直接触发。
- 独立审查两轮无剩余源码阻塞项；更新知识草稿，未发布。证据alpha-coupled.json。继续G1，G5最终集成验收与整体主线交付仍待完成。

## 2026-10-31 / G5 — 独立场generalized-alpha

- BDF2耦合检查点`bab4fda`云端CI三环境成功（run41192856614）。
- 核对PETSc3.23.7 alpha1/alpha2版本源码、一阶原始预印本§3–4与压力评价论文。Chung1993出版社全文403，仅核实出版信息，不声称读过全文。
- 新时刻权重参数分别实现一阶流体与二阶结构；独立stage速度/压力、端点恢复、完整算法历史及rho checkpoint。接受一个BE启动步的策略明确不同于PETSc探测启动。
- 结构惯性q与位移beta*h/gamma分离；局部线弹性/Neo-Hookean方向导数通过。物理端点加速度由卸载模型一致质量方程恢复，算法加速度独立输出/保存。
- 独立审查发现stage残量与端点输出混用风险，已将流体字段命名stage_momentum_residual，结构保留stage字段但端点反力/残量使用质量恢复方程，日志标记evaluation_time。
- 主锁Debug7项针对性CTest全部通过，26.82秒CTest墙钟；包括rho=0/0.5/1的真实流体早期/终点速度与压力阶、结构位移/速度/物理加速度阶、rho=1启动后能量保持、阻尼、1/2/4rank、事件checkpoint、算法历史和真实拒绝。
- [alpha-standalone.json](../research/data/fem-integration-2026-10-31/alpha-standalone.json)保留实际源码/二进制、命令、退出码和结果。alpha ALE/FSI尚未接入并明确拒绝；G5不关闭，继续下一增量。

## 2026-10-31 / G5 — BDF2 ALE与单体FSI

- 独立场提交`c923387`的云端CI三环境成功（run41181938354）。
- FSI流体惯性、结构/刚体位置与加速度、ALE网格速度、reduced.slot位移试探列和lifting统一使用当前BDF2映射；各层历史只在共同接受后提交。
- ALE新增同分区checkpoint，保存当前与前一流体/网格状态及步长；重试重建trial几何不污染accepted。
- 独立审查指出测试遗漏压力MPI/重启与非均匀接口功率，已补齐。接口功率按全分量离散残量与共享速度内积计算，不声称总能量守恒。
- 主锁Debug6项针对性CTest全部通过，138.35秒CTest墙钟；包括3个新验收和旧motion/刚体FSI/弹性FSI回归。整体Jacobian差分相对误差约1.4e-9，MPI最多4rank。
- 弹性FSI压力阶1.86/1.97、刚体压力阶2.00/2.02，速度与网格位移趋近2；粗时间步压力未达门槛后保持物理问题和容差继续细化。ALE网格速度BE阶0.95/0.98、BDF2阶2.02/2.01，均匀/剪切流保持及重启通过。
- 高压超弹性真实拒绝压力测试：从两步accepted检查点限制Newton为2次，15次缩步后以原容差接受下一BDF2步，并与无拒绝相同轨迹一致。测试显式允许16次重试，只推进一个恢复步；不作为实用步长建议。原8次上限耗尽的结果不是生产回归；3次Newton上限没有触发拒绝，未拿它替代恢复证据。
- [bdf-coupled.json](../research/data/fem-integration-2026-10-31/bdf-coupled.json)保存实际源码/二进制/日志哈希、命令、退出码和数值结果。G5仍未关闭，继续generalized-alpha；G1未实施。

## 2026-10-31 / G5 — 独立流体和固体BDF2增量

- 从`e9e4d30`继续；该G0补强提交云端三环境CI成功（run41180022722）。
- 统一BE/BDF2导数映射、实际历史步长、比率上限2、事件后启动、两层accepted checkpoint；独立固体位移重建同步使用当前格式。
- 真实流体首次320步测试暴露累计舍入制造极短末步，时间控制器补偿求和修复，320/10000步oracle通过。
- 独立审查指出步长相关tau使时间加密同时改变空间离散；新增显式固定tau并保持旧BE默认。压力驱动实测速度/压力BDF2阶约2；不是Python参考替代生产验证。
- 固体粗步未进入渐近区，保持问题和门槛继续细化，位移/速度/加速度BDF2阶接近2。没有声称非线性材料阶数或BDF2逐步物理能量单调。
- 主锁Debug编译退出0；针对性CTest9项全部通过，42.23秒CTest墙钟。选择包含time_integration、fluid/solid_time_verification、fluid/solid_element_jacobian、time_retry_verification、restart_block_verification、fluid/solid_verification。
- 新测试覆盖变步长、1/2/4rank、事件处重启、最后短步、BDF2启动后的真实Newton拒绝与同轨迹对照；签名拒绝更换积分器/候选步计划。独立审查公式与状态无阻塞缺陷，建议的schedule签名已补齐。
- [证据清单](../research/data/fem-integration-2026-10-31/bdf-standalone.json)记录实际dirty源码哈希、基线SHA、二进制哈希、命令、退出码及结果；不是把新结果归给旧提交。新增知识草稿保持draft。
- G5未关闭，后续继续ALE/FSI及两类generalized-alpha，G1尚未实施；此处只记录可复现增量。

## 2026-10-31 / FEM-INTEGRATION — 从已合入的G0检查点接续

- fetch核实main为47b5bd46c992fcf64cf163361053ceb0091fa5a5，工作区起始干净，无开放PR；建立codex/fem-time-mesh。
- 读取主线CI作业日志，主锁Debug/Release各43项、旧锁Release 10项均成功；独立审查核对原g0.json的100份源码哈希全部匹配。
- 本轮明确追加授权WSL2开发验证、CI云端复验。两套仓库依赖锁成功恢复；主锁Debug编译与链接检查通过。首次MPI预检被沙箱socket策略拒绝，沙箱外同命令预检与完整43项通过。
- G0补强真实J/R跨rank置换、已知离散解与真实Newton右端检查，三recipe物理量及压力规范对照；独立审查发现辅助PREONLY失败分叉并修复为共同拒绝。
- 当前Release/兼容检查、受控性能、新提交CI尚待完成。整体任务继续，未将G5/G1标记完成。

## 2026-10-30 — ARCH-01 — 通用 FEM 架构与上游学习规划

- 用户要求审查 EONSim-new，并进一步规划多网格/空间、边界、非一致界面、DoF/预条件、时间格式与高性能执行；明确暂不开发、不编译。本轮遵守此范围。
- 独立本地 checkout 从旧审查基线同步 main 至 `38a5e516ffe129d1b70c7c1bd8365deb5ded101a`，确认 PR #21 已合并；建立 `docs/general-fem-architecture-plan`。未修改只读 sources/。
- 静态阅读当前拓扑、Gmsh、DoF、FSI、COO、VTU 及 L1/L2；确认 Tri3 只是 Tet4 边界、体域仅 Tet4，BE/共形接口仍为实现边界；现有独立流体 COO 与分片 VTU 不重复安排为全新功能。
- 新增 `docs/architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md`：明确拓扑/几何/空间分离、一般 BC、K/W 与非匹配传递、三类 DoF/PC 排列、约束后图、两类 generalized-α 与变步长 BDF2、输出和 native 批次执行；提供 G0–G8 依赖和验收候选。
- 新增 `docs/research/FEM_FRAMEWORK_LEARNING_2026-10-30.md`：访问官方文档和作者论文，覆盖用户列出的 20 组项目（Elmer 与 oomph-lib 分列）；给出具体迁移产物和不照搬部分，没有逐库源码全审或性能横评。
- 同步 L0/L1/L2、下一阶段设计、README、ROADMAP、进度与任务队列；纠正旧文档中持久 SNES/PC 的优先级，保留根据已有测量暂缓的决定。HPC-02 按 PR #21 标 done；所有新增实现任务 deferred，无新增 ready。
- 使用仓库 eonsim-knowledge-capture 技能，新增未发布草稿 `website/drafts/general-fem-dof-architecture.md` 与知识登记。证据为理论/设计和静态实现对应；lastVerifiedCommit 留空。非匹配稳定性、stage 相容性及 PC 语义为后续审阅重点。
- 文档检查：`git diff --check`；以 Python 标准库检查所有变更/新增文件仅为 Markdown、UTF-8、围栏闭合、相对文件/站点路径存在及新文件尾空白；通过。此为文档结构检查，未构建网站或声称渲染验证。
- 未运行 CMake、编译、CTest、MPI、求解器、性能实验、上游原型或网站发布。没有修改 src/include/tests/cases/scripts/CMake 等实现；历史数值与性能记录保持原有证据范围。
- 初次交付为本地文档草案，当时未创建 PR、未推送、未发布。下一步开发需用户另行启动；本轮不擅自领取候选。
- 用户后续明确要求将上述 16 份 Markdown 文档推送远程；交付目标为 origin 的 `docs/general-fem-architecture-plan` 分支，提交范围仍限这 16 份文档。保持不编译、不创建 PR、不合并 main、不发布网站；提交标识及交付结果以 Git 远程引用为准。

## 记录模板

~~~markdown
## YYYY-MM-DD — TASK-ID — 简短标题

- Branch / PR:
- Base commit:
- Objective:
- Changed files:
- Implementation:
- Commands executed:
- Tests and results:
- Performance evidence (if applicable):
- Knowledge draft:
- Limitations / unresolved issues:
- Next task:
~~~

## 2026-10-30 — HUB-01 — 持续研发与知识生产基础设施

- Branch / PR: feat/codex-continuous-development-workflow；[PR #3](https://github.com/saitoasukakawaii/EONSim-new/pull/3)。
- Objective: 为 EONSim 建立跨 Codex Task 的进度恢复、任务队列、会话记录和公开知识草稿模板。
- Changed files: CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md、CODEX_SESSION_LOG.md、website/templates/ 下的文章模板、知识采集 Skill，以及 AGENTS.md 入口。
- Implementation: 定义状态语义、任务领取规则、SOLVER-01 下一任务边界和知识文章证据分级。
- Commands executed: 通过 GitHub 仓库接口创建/更新文档；未在 Codex Cloud 本机执行命令。
- Tests and results: GitHub Actions Website Build Check 在 PR #3 分支上成功；执行了依赖安装和 VitePress 生产构建。未运行 EONSim C++/PETSc/MPI 测试（本次未修改求解器）。
- Performance evidence: 无，本次未进行性能实验。
- Knowledge draft: 本次新增的是模板和工作流，不将其伪装成已验证的数值研究文章。
- Limitations / unresolved issues: 尚未实现自动从测试日志提取数据或自动发布；Codex 需按 Skill 和 AGENTS 规则执行草稿生成。
- Next task: SOLVER-01 PETSc NonlinearSession 生命周期审计。

## 2026-10-30 / SOLVER-01

- 基线：0828f41（PR #3 已合并）；分支 docs/solver-baseline-audit。
- 变更：新增 docs/research/PETSC_LIFECYCLE_AUDIT_2026-10-30.md、website/drafts/petsc-object-lifetime.md；更新 CODEX_PROGRESS、CODEX_TASK_QUEUE、本日志和 KNOWLEDGE_LOG。
- 审计：读取 linear_system/nonlinear_system/schur_solver、PetscOwner 及 fluid/solid/fsi 调用链；主 Vec/Mat 跨步保留，SNES 每次 solve 创建；Context 为借用栈引用；计时不完整覆盖构造析构。结论为需要额外测量，SOLVER-02 保持阻塞。
- 实际验证：仓库根目录 `git diff --check` 通过；`git diff origin/main -- src include CMakeLists.txt CMakePresets.json` 为空；website 目录 `npm run docs:build` 成功；仓库根目录 `test ! -d website/.vitepress/dist/drafts` 成功。
- 数值测试/性能实验：未运行；本任务为静态审计，不能据此声明性能收益。
- 知识沉淀：有，已按 eonsim-knowledge-capture 形成草稿并登记；证据为源码分析，数值与性能仍待测量。
- 下一步：人工审核审计报告，再开展固定 transient case 的重复 profiling。

## 2026-10-30 / SOLVER-01B

- 基线 c1c7508，PR #4 已合并；分支 perf/nonlinear-setup-baseline。
- 新增 scripts/benchmark_nonlinear_setup.py、docs/research/NONLINEAR_SETUP_BASELINE_2026-10-30.md、data/nonlinear-setup-2026-10-30 的结果 JSON/原始日志及 website/drafts/nonlinear-setup-baseline.md；更新进度、队列与知识日志。
- 仓库根目录激活 /workspace/.eonsim-tools/activate.sh；`cmake --preset release -DBUILD_TESTING=ON -DCMAKE_PREFIX_PATH="$CONDA_PREFIX" -DMPIEXEC_EXECUTABLE="$CONDA_PREFIX/bin/mpiexec" -DEONSIM_BLAS_LAPACK_PROVIDER=OPENBLAS` 和 `cmake --build --preset release --parallel 4` 退出0。
- `python3 scripts/benchmark_nonlinear_setup.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-nonlinear-baseline` 退出0：12个样本、2个预热、2个预处理成功；同rank输出差0。raw日志已入Git，不依赖临时目录恢复。
- `ctest --preset release -R '^(solver_failures|solver_failures_mpi|nonlinear_acceptance|nonlinear_acceptance_mpi)$' --output-on-failure`：4/4通过，耗时4.57秒；未运行全套。
- website目录 `npm run docs:build` 成功；草稿目录未进入dist。求解器及CMake未改。
- 知识沉淀：已生成测量边界草稿并登记。构造析构独立计时仍未完成，无持久化优化收益结论；SOLVER-02保持blocked。
- PR：https://github.com/saitoasukakawaii/EONSim-new/pull/7，等待人工审核。文档末尾空行已修正。

## 2026-10-30 / SOLVER-02

- 同步基线8c8a4af，PR #7已合并；分支perf/multistep-setup-profile。按最新队列将旧SOLVER-02“设计原型”表格描述统一为正文规定的测量任务。
- 新增scripts/profile_multistep_setup.py、docs/research/MULTISTEP_SETUP_PROFILE_2026-10-30.md、data/multistep-setup-2026-10-30的JSON及16份原始日志、website/drafts/multistep-setup-profile.md；更新进度/队列/知识日志。
- 仓库根目录激活已有环境后 `cmake --build --preset release --parallel 4` 退出0（no work to do，求解器相对前一基线无变更）。
- `python3 scripts/profile_multistep_setup.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-solver02` 退出0：fluid与elastic、1/2rank、各3次，共120接受步，同rank重复输出差0。
- 对实际日志的解析检查：有效10步通过；删除一条报告、负SNES reason、NaN三个错误输入均被拒绝。website目录 `npm run docs:build` 通过；草稿未进入dist。未运行全套CTest，未改求解器/容差。
- 使用eonsim-knowledge-capture流程形成测量草稿；原始证据入Git。结论为暂缓持久化原型，首步成本不可外推后续；独立构造析构成本仍未知。
- 下一步：人工审核；未来只有业务需求或更大规模测量支持时重新打开优化任务。

## 2026-10-30 / SOLVER-05

- 同步 origin/main 至 a48de95，确认 PR #8 已合并；分支 fix/linear-solve-ksp-lifetime。SOLVER-02 标记 done。
- 修改 src/algebra/linear_system.cpp、include/eonsim/linear_system.hpp，将 KSP owner 从成员移到单次 solve 作用域；新增 tests/verify_linear_lifetime.cpp 和两项 CTest 注册。代码提交 c47f00d。
- 更新进度、队列、本日志、KNOWLEDGE_LOG；使用 eonsim-knowledge-capture 生成 website/drafts/linear-solve-ksp-lifetime.md，记录理论、实现、数值/生命周期验证及性能证据缺失。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target verify_linear_lifetime --parallel 4` 成功。旧实现 `ctest --preset release -R '^linear_lifetime$' --output-on-failure` 预期失败，提示 solve 返回后 PC 未释放。
- 修复后 `cmake --build --preset release --target eonsim verify_linear_lifetime --parallel 4` 成功；`ctest --preset release -R '^(linear_lifetime|linear_lifetime_mpi|poisson_verification|poisson_parallel)$' --output-on-failure` 4/4 通过（14.05 秒）。
- `cmake --build --preset debug --target verify_linear_lifetime --parallel 4` 成功；`ctest --preset debug -R '^linear_lifetime(_mpi)?$' --output-on-failure` 2/2 通过。每 rank 四次 PC 创建/销毁，覆盖成功、失败、恢复和 owned/ghost 解。
- 未运行全套 CTest；未测量内存字节数、耗时收益或大规模并行。下一步人工审核本修复；持久化优化保持延期。
- 文档验证：`git diff --check`、五份 Markdown 的解析/围栏配对检查通过；`npm run docs:build --prefix website` 成功；`test ! -d website/.vitepress/dist/drafts` 成功，草稿未进入生产构建。
- Markdown 检查最初直接导入 markdown-it 失败（非顶层依赖）；改用已安装 VitePress 的 createMarkdownRenderer 后五份文件解析及围栏检查通过，无新增依赖。

## 2026-10-30 / SOLVER-03

- `git fetch origin` 同步 main 至 717b25b；`gh pr view 9 --json state,mergedAt,url` 确认已合并；SOLVER-05 标记 done。新分支 docs/newton-scaling-spec。
- 领取原队列 SOLVER-03 的审查/规格任务；审查 FieldAcceptance、Context、convergence、NonlinearSystem::solve、Schur 配置和非线性验收测试。现有字段尺度仅用于验收，未实现完整 Newton 坐标变换。
- 新增 docs/research/NEWTON_SCALING_SPEC_2026-10-30.md、scripts/verify_newton_scaling.py、website/drafts/newton-scaling.md；更新 CODEX_PROGRESS、CODEX_TASK_QUEUE、本日志及 KNOWLEDGE_LOG。
- `python3 scripts/verify_newton_scaling.py` 通过：两组尺度，Newton/Jv、非零约束、试探点/加权 merit、逆预条件作用和 Schur 恒等式；两个错误公式负对照均被识别。规格/脚本提交 6dc2baf。
- 使用 eonsim-knowledge-capture 形成算法草稿，明确当前实现、候选理论、独立验证及性能证据缺失。未修改 C++、CMake、case 或容差；未运行 C++ 构建/CTest、MPI 或性能实验。
- SOLVER-03 标记 review，新增 deferred 的 SOLVER-03B 并列明实现验收条件与触发需求；不将候选规格描述为已实现能力。
- `python3 -O scripts/verify_newton_scaling.py` 同样通过；`git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功；草稿目录未进入 dist。核对 src/include/CMake/cases 相对 origin/main 无差异。
- 相对链接检查最初误将既有 `/learning/cfd` 网站路由视为本地文件；限定为相对文件链接后通过，未修改已有网站路由。

## 2026-10-30 / SOLVER-04

- `git fetch origin` 同步至 a4957e0；`gh pr view 10 --json state,mergedAt,url` 确认合并，SOLVER-03 标记 done。分支 perf/schur-mesh-profile。
- 新增 scripts/profile_schur_mesh.py（79eb826）、docs/research/SCHUR_MESH_PROFILE_2026-10-30.md、data/schur-mesh-2026-10-30 的 38 个证据文件、website/drafts/schur-mesh-profile.md；更新进度/队列/会话/知识日志。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target eonsim --parallel 4` 退出 0（no work to do）。
- `python3 scripts/profile_schur_mesh.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-schur-mesh` 退出 0：2/4/6 subdivisions、1/2 rank、6 个直接参考及 18 个 Schur 重复；最大字段差 4.0834e-12。
- 对实际日志解析的有效输入、缺报告/NaN/负 SNES reason 三种变异，以及节点集合/非有限值/超阈值差三个负对照检查均通过。
- 版本采集中的非提升权限 mpiexec --version 输出 pmix socket 警告但返回版本；实际 MPI 测量在允许本地通信的执行权限下全部成功。
- 使用 eonsim-knowledge-capture 形成 benchmark 草稿；完整计时范围与限制见报告。未修改求解器、CMake、既有案例或容差；未运行全套 CTest、FSI 或跨节点测试。下一步人工审核；大网格/粗层进一步测量需明确需求。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功，草稿未进入 dist；src/include/CMake/cases 相对 origin/main 无差异。

## 2026-10-30 / SOLVER-04B

- `git fetch origin` 同步至 f1e9594；`gh pr view 11 --json state,mergedAt,url` 确认已合并。SOLVER-04 标记 done，新分支 feat/solver-level-dimensions。
- 修改 src/algebra/nonlinear_system.cpp，使用 KSPGetOperatorsSet 后读取已有 A 的全局/本地行列；修改 tests/verify_schur.py 验证各层尺寸及顶层分布总行数；更新 L2 离散诊断契约。实现提交 124bed3。
- 更新 CODEX_PROGRESS、CODEX_TASK_QUEUE、本日志和 KNOWLEDGE_LOG；按 eonsim-knowledge-capture 生成 website/drafts/solver-level-dimensions.md，区分元数据理论、实现、数值验证与性能证据缺失。
- 激活 `/workspace/.eonsim-tools/activate.sh` 后，`cmake --build --preset release --target eonsim verify_solver_failures --parallel 4` 成功；`ctest --preset release -R '^(schur_verification|solver_failures|solver_failures_mpi)$' --output-on-failure` 3/3 通过（36.97 秒）。Schur 含四类问题的 1/2/4 rank 对照。
- `cmake --build --preset debug --target verify_solver_failures --parallel 4` 成功；`ctest --preset debug -R '^solver_failures(_mpi)?$' --output-on-failure` 2/2 通过（2.36 秒），包含初态收敛和故障路径。
- 未跑全套 CTest、性能基准；不宣称诊断零开销。尚无 P 尺寸/逐层非零元或累计成本；未设置 A 的哨兵分支未单独构造测试。下一步人工审核，本次不调参。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功；草稿未进入 dist。CMake 和 case 未更改。

## 2026-10-30 / HPC-01A

- 同步 origin/main 至 615af36，确认 PR #12 已合并，SOLVER-04B 标记 done；分支 feat/assembly-phase-timers。
- 修改 src/algebra/nonlinear_system.cpp：累计正常完成评价的 callback/failure_sync/assembly_finalize/constraint 时间；在 SNESSolve 后冻结，沿用原有报告规约。修改 tests/verify_schur.py 检查有限非负及外层时间界；更新 L2 计时契约。实现提交 fff4895。
- 更新进度/队列/本日志/知识登记；按 eonsim-knowledge-capture 生成 website/drafts/assembly-phase-timers.md。HPC-01A 是有界实现增量，HPC-01 的纯 kernel/插入分离与重复测量仍未完成。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target eonsim verify_solver_failures --parallel 4` 成功；`ctest --preset release -R '^(schur_verification|solver_failures|solver_failures_mpi)$' --output-on-failure` 3/3 通过（37.19 秒），含 Schur 四类问题的 1/2/4 rank 对照。
- `cmake --build --preset debug --target verify_solver_failures --parallel 4` 成功；`ctest --preset debug -R '^solver_failures(_mpi)?$' --output-on-failure` 2/2 通过（2.28 秒）。
- 未修改物理方程/容差/CMake/案例；未跑全套 CTest 或性能实验；新增时钟读取开销未知。失败评价的细分成本未纳入，详见契约。下一步人工审核，不能将计时接线报告为完整瓶颈结论。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功；草稿未进入 dist。

## 2026-10-30 / HPC-01B

- 同步 origin/main 至 7f2bc51，`gh pr view 13 --json state,mergedAt,url` 确认合并；HPC-01A 标记 done；分支 perf/assembly-phase-baseline。
- 修改 scripts/profile_schur_mesh.py，新增四阶段及 assembly/ghost 汇总、缺字段/阶段越界/拒绝计数检查；脚本提交 d1708e1。
- 新增 docs/research/ASSEMBLY_PHASE_BASELINE_2026-10-30.md、data/assembly-phase-2026-10-30 的 32 个日志/JSON 文件、website/drafts/assembly-phase-baseline.md；更新进度、队列、会话与知识日志。按 eonsim-knowledge-capture 整理证据边界。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target eonsim --parallel 4` 退出 0（no work to do）。
- `python3 scripts/profile_schur_mesh.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-assembly-baseline` 退出 0：6 个直接参考、18 个 Schur 样本，无拒绝评价；最大节点字段差 4.0834e-12。
- 有效日志解析及缺 callback/NaN/阶段越界/非零 domain_rejections 四个负对照均通过。本轮未修改 src/include/CMake/cases，未跑全套 CTest 或时钟开销 A/B。
- n=6 callback 中位数由单 rank 25.487 ms 降至双 rank 13.779 ms，最终装配由 0.138 ms 增至 9.609 ms；不把最终装配全解释为网络时间。完整设置与范围见报告。下一步人工审核，HPC-01 未完成的分离与规模测量仍延期。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功，草稿未进入 dist；已核对 src/include/CMake/cases 相对 origin/main 无差异。

## 2026-10-30 / HPC-01C

- 同步 main 至28c60da，PR #16已合并。用户在上一轮提出 transient fluid/FSI 1/2/4 rank 候选后要求继续，本轮执行该有界任务；分支perf/transient-assembly-profile。
- 修改scripts/profile_multistep_setup.py：新阶段校验/统计、1/2/4 rank参数、主输出按owner/原始节点ID跨rank对照、独立固体输出检查及逐步/逐次分布。新增研究报告、26份日志/JSON证据、知识草稿；更新进度/队列/本日志/知识登记。
- 激活/workspace/.eonsim-tools/activate.sh后 `cmake --build --preset release --target eonsim --parallel 4` 成功（no work to do）。
- `python3 scripts/profile_multistep_setup.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-transient-phases --ranks 1 2 4` 成功：18次运行、180接受步，主输出跨rank最大差6.6614e-16，同rank重复差5.5512e-16。
- 运行启动版本82081d5；确认FSI单独输出固体场后，用0f90585的verify_solid_outputs对全部已生成输出补验，最大跨rank差2.4287e-17。f92e57b的detailed_statistics补充18个逐次和60个逐步统计。无需重新运行物理求解；版本来源分别记录在JSON。
- 有效日志与缺phase/NaN/非零拒绝计数/超外层时间四个负对照通过。采用eonsim-knowledge-capture整理草稿，保留统计与计时边界。未修改C++/CMake/案例，未跑全套CTest；未测量时钟开销。
- 下一步人工审核，性能结论为暂缓重构，必要时按目标规模补更细事件；没有擅自激活其他deferred任务。
- `git diff --check`、六份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功，草稿未进入dist；src/include/CMake/cases相对origin/main无差异。

## 2026-10-30 / HPC-01D

- 同步origin/main至2e7e9a9，PR #17已合并，HPC-01C标记done。用户在上一轮提出独立流体kernel/插入分离建议后要求继续，本轮执行该有界任务，分支feat/fluid-element-timers。
- 修改src/physics/fluid.cpp，新增显式-fluid_element_report开关、单元kernel/Vec+Mat插入时间、逐rank/逐步单元计数；关闭时无单元时钟读取。新增tests/verify_fluid_element_report.py及CMake注册，更新README和L2契约。实现提交1722265。
- 新增website/drafts/fluid-element-timing.md；按eonsim-knowledge-capture区分理论/代码/验证与性能证据缺失；更新进度、队列、会话和知识登记。
- 激活/workspace/.eonsim-tools/activate.sh后，`cmake --build --preset release --target eonsim --parallel 4`及Debug同命令成功。
- `ctest --preset release -R '^fluid_element_report$' --output-on-failure` 1/1通过（21.34秒）；Debug同测试1/1通过（22.73秒）。每个构建覆盖三案例、1/2 rank、开关共12次求解；主物理字段/动量残量保持、计时有限非负、报告和单元计数有效。
- 本轮不跑全套CTest或性能基准；未修改方程、容差或PC策略。计时包含最终验收/原始反力回调，不可与callback_seconds直接相减；整个失败solve不输出，拒绝评价的专门计时路径未新增测试。FSI/ALE与owned/remote插入仍未分离。
- 下一步人工审核，无新增ready任务；如继续测量需明确目标规模并考虑计时扰动。
- `git diff --check`、六份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功，草稿未进入dist；README新增选项说明及契约链接已核对。

## 2026-10-30 / HPC-01E

- 同步main至f232b07，PR #18已合并；HPC-01D标记done。用户在上一轮提出计时开关扰动测量后要求继续，本轮执行该候选；分支perf/fluid-element-overhead。
- 新增scripts/benchmark_fluid_element_report.py（1423b99）：每配置预热两模式，5对交替顺序，固定solver_report，仅切换fluid_element_report；检查字段、逐步迭代轨迹、单元计数及报告完整性。
- 新增研究报告、data/fluid-element-overhead-2026-10-30的41份日志/JSON、website/drafts/fluid-element-overhead.md；更新进度/队列/会话/知识登记。使用eonsim-knowledge-capture标注证据及局限。
- 激活/workspace/.eonsim-tools/activate.sh后 `cmake --build --preset release --target eonsim --parallel 4` 成功（no work to do）。
- `python3 scripts/benchmark_fluid_element_report.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-element-overhead --repeats 5` 成功：1/2/4 rank，共30个计量样本/15对，另6次预热。最终字段同rank差3.3307e-16、跨rank差4.4409e-16，逐步迭代轨迹及计数一致。
- 有效报告及缺报告、重复报告、NaN、错误单元计数、关闭模式出现报告五个负对照通过。
- 单rank配对solve变化中位数+3.56%，范围-0.10%至+27.68%；2/4rank范围跨零。详细耗时/统计口径见报告；不将负值称为加速，不作纯时钟成本归因。
- 未修改C++/CMake/案例，未跑全套CTest；仅小规模独立流体，完整HPC-01未完成。下一步人工审核，无新增ready任务。
- `git diff --check`、六份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功，草稿未进入dist；src/include/CMake/cases相对origin/main无差异。


## 2026-10-30 / QA-01

- 同步origin/main至25e49af，PR #19已合并；HPC-01E标记done。用户继续上一轮日志校验候选，分支fix/profile-log-validation。
- 实现7b91030修改scripts/profile_multistep_setup.py、scripts/profile_schur_mesh.py，新增tests/test_profile_validation.py与CMake注册。原因/计数严格整数校验、计时和残量有限非负、报告/步顺序配对、稳态必需统计字段及逐rank根节点/重复层级校验。
- 修复前负对照发现NaN原因、非法迭代计数及缺失根节点等误接受；修复后 `python3 tests/test_profile_validation.py` 与 `python3 -O tests/test_profile_validation.py` 均11项通过。真实数据覆盖18份瞬态、18份稳态、36份开关测量/预热日志，共72份。
- 激活/workspace/.eonsim-tools/activate.sh后，`cmake --build --preset release --target eonsim --parallel 4` 与Debug同命令均成功；CMake重新生成，C++无需重编译。
- `ctest --preset release -R '^profile_log_validation$' --output-on-failure` 与Debug同命令均1/1通过（各0.09秒）。未执行全套CTest或新MPI/性能实验，测试读取已提交证据，不重新证明数值正确性。
- 更新进度/队列/本日志/知识登记；使用eonsim-knowledge-capture新增website/drafts/profile-log-validation.md，区分浮点语义、实际实现、解析器验证与性能未测量。
- 待人工审核；无新增ready任务。此解析协议限于现有固定十步、零拒绝评价的测量，不作为任意PETSc运行的通用成功判据。
- `git diff --check`、五份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功（3.37秒），dist未包含草稿或模板；未修改src/include/cases。

## 2026-10-30 / HPC-02

- 用户要求依据规划设计并完成预计 5 小时以上任务，然后创建 PR。核对指定 EONSim-new 与旧 EONSim 是不同仓库，在独立 checkout 从 `24eae62`（PR #20）建立 `codex/fluid-cached-coo`；旧工作区及未提交修改未改动。
- 任务队列登记 7–9 小时工程工作量估计及具体验收；实现 `ceea57d` 增加独立固定网格流体 `-fluid_coo`，一次准备图、复用数值缓冲，在错误同步后调用 collective COO 更新。默认装配、物理公式、停止条件、残量/反力与 FSI 路径保留。
- WSL Ubuntu24.04/GCC13.3/PETSc3.19.6/OpenMPI4.1.6 下 Release 和 Debug 完整构建成功。新增 COO 代数测试 1/2/4 rank 通过；真实流体每构建 87 个命令，最大字段差 5.190625707029994e-12。
- Debug 6/6 通过；Release 首轮 7/8 通过，`solver_failures_mpi` 60 秒超时在独立未修改基线构建中相同复现。共享求解器的 Schur/FSI、真实缩步、计时及日志回归额外 4/4 通过。不宣称整个 CTest 通过。
- `benchmark_fluid_coo.py` 完成两档网格、1/2/4 rank、36 次计量及12次预热；所有18对迭代轨迹一致，字段最大差 6.661338147750939e-16。装配中位变化约 -45% 至 -62%，solve 约 -8% 至 -44%，wall 约 -11% 至 0%；多组 wall 范围跨零，明确记录准备和内存成本。
- 原始测量使用 `ceea57d`；后续仅修正跨 Windows/WSL Git status 的 CRLF 元数据噪声。58 个编译源文件归一化哈希与提交相符，可执行哈希与测量一致；原始 JSON 未改写。
- 独立 deep review 对 `ceea57d` 为 PASS，无阻塞发现。报告、原始日志、字段证据、审查记录及 source provenance 已归档；按 eonsim-knowledge-capture 添加 website/drafts/fluid-coo-assembly.md 并登记知识日志，未发布网站。
- 代码、验证、性能测量和评审完成后创建 [PR #21](https://github.com/saitoasukakawaii/EONSim-new/pull/21)，人工决定是否合并；无新增 ready 任务。创建后的提交仅登记 PR 链接与 review 状态。此任务不提供 FSI/ALE/残量 COO、GPU、多节点或大规模扩展证明。
- 交付前代码/文档的 `git diff --check`（排除原样归档的日志）、8 份 Markdown 围栏/相对文件及站点路由链接检查、JSON 证据解析、测量脚本语法检查通过。两份构建日志保留 CMake 原始输出中 8 行尾空白，完整 diff 检查因此会报告这些空白；不改写原始证据。后续文档/元数据修改未改变已审查的 src/include/CMake/tests；未重复运行数值测试，未构建或发布网站。


## 2026-10-30 / INFRA-01

- 用户明确授权14–18小时估计工程量的云端基础设施任务；未将估计写实际耗时。仅远程Linux，main基线38a5e51，PR #21已核实合并，纠正HPC-02状态。独立分支codex/infra-reproducible-mpi-ci。
- 读取根AGENTS/L0、工程总纲/路线/构建/进度队列、并行/状态/求解契约及两份历史报告。用户指定architecture下L0路径不存在，实际入口在根目录。
- 新增environments两份SHA256显式锁及版本说明，scripts/cloud恢复/运行/证据入口、核心GitHub Actions、runtime探针；复用presets/provider和34项原测试（新增后35项），添加选择/rank标签。
- src/algebra/nonlinear_system.cpp修复旧PREONLY局部PC失败，在诊断前统一布尔失败标志，保留负枚举原因；本地失败树不额外collective。已共同传播的fatal callback早退后更换trial Vec，隔离PETSc残留读锁，COO图/矩阵保持。
- tests/verify_solver_failures.cpp覆盖三个诊断模式、fatal Jacobian、accepted不变及恢复；tests/verify_checkpoint.cpp补破坏指针前读者同步；tests/verify_runtime.cpp验证real/double/int32及实际MPI运行。
- 未改main隔离构建在PETSc3.19.6下原60秒超时（60.07秒），最小纯PETSc复现rank0 reason4、rank1 reason-11；上游3.20.0已加入归约。保留最小复现源码，详细归因见INFRA-01报告。
- 最终锁在/tmp/infra-pristine恢复；随后在/tmp/eonsim-cold-I3bOY2显式隔离所有包缓存、独立检出c07f94a，完成干净恢复/构建/7项故障回归，再重复restore与7项测试通过；云机4CPU/32GiB。旧hwloc CPUID启动问题及容器CMA限制分别适配，不混同应用死锁。
- 两套环境mpi-failure各7/7通过；主环境Debug全35/35通过474.17秒、Release全35/35通过409.08秒。d3f69d1分支CI三任务全部成功（41060786421），均上传诊断产物。最终入口/文档提交仍须head CI通过，尚无正式PR。
- 首轮主环境全套暴露COO Vec锁与checkpoint竞态并修复；CI四rank失败进一步定位OpenMPI5忽略旧映射变量，模拟两槽位前后验证后加入PRRTE设置及四rank预检。
- 独立审查指出负PC枚举、嵌套cgroup和超时残留，均修正并复核无源码阻塞；真实MPI超时清理与多层后代终止/reap通过。数值Python优化明确禁用。
- 使用eonsim-knowledge-capture新增未发布草稿，更新README/L2契约/BUILD_AND_VALIDATION/进度队列/知识登记。Markdown八文件解析及链接、网站构建3.94秒、草稿排除检查通过。精简机器证据见INFRA-01报告旁data目录；正式PR状态待验收后更新。


## 2026-10-30 / BRANCH-01 — 已合并分支清理与主线整合

- 用户明确授权删除已完全合并的 18 个远程分支，并审查剩余 6 个、优先架构与 CI、合入 main；明确禁止编译。以 38a5e51 为起点，在 integration/review-branches-2026-10-30 逐次整合。
- 18 个 tip 均为原 main 祖先，保存 SHA 后按精确旧值保护原子删除，复核只剩 main 与 6 个待整合分支；没有删除未审查引用或强制改写 main。
- 架构 16 份文档完整保留。CI 审查到 d3f69d1 后，推送前发现远程新增 c07f94a/5745fd3，继续审查并保留环境恢复与证据增量。其余旧分支按整合报告保留有效补充、维护主线状态，不复活过时任务。
- 新修正：锁定 ABI 的 runtime 探针改为云端显式启用；JUnit 解析按名称严格匹配并识别 error；文档检查支持 source-only 与 CRLF；网站 CI 增加模板哨兵；修正文档与真实 CMake target 的不一致。
- 工作目录为 EONSim-new checkout。执行 python -B tests/test_cloud_evidence.py（6 项通过）、node website/scripts/check-content.mjs --source-only（10 文件通过）、Python AST、bash -n、YAML/JSON/锁结构检查、Markdown 围栏和本地链接检查、git diff --check 及祖先关系核验。
- 本轮没有 CMake 配置/编译、CTest、MPI、数值/性能或网站构建；没有启动 GitHub 数值 CI。读取的历史成功状态只对应原分支 d3f69d1。最终推送含 [skip ci]，不把已有证据当作最终集成通过。
- 使用 eonsim-knowledge-capture 更新原 INFRA-01 草稿和知识登记，分开原分支执行记录与本次脚本验证；没有新性能证据，草稿未发布。
- 完整源提交、删除清单、冲突取舍和验证边界见 BRANCH_INTEGRATION_2026-10-30.md。INFRA-01 最终集成验收待执行，G0–G8 均 deferred；不自动开始新开发或构建。

- 推送前又检测到源 CI 分支新增 1497137/787372e：保留 PR #22 与 5745fd3 成功 CI 的证据、以及 ob1 单机传输适配。只读 GitHub 确认 CI 41063030121 三个 job 成功；核对 OpenMPI 官方 sm/vader 命名并检查脚本语法，未执行 MPI。最终整合范围以 branches.json 中的六个 tip 为准，INFRA-01 保留最终集成验收待完成。

- 第一次推送前置检查发现 main 已并发合入 PR #22（281699c2e86eb4eb0f9d0db7ca1bc891892c90dd），因此未执行推送；复核其唯一新增提交为已审查 CI tip 的 merge commit，纳入主线历史后树内容不变。继续采用正常快进推送与 [skip ci]，未覆盖并发提交。


## 2026-10-30 / FEM-G0A — DoF 与 FSI 分块详细设计（本地 review）

- 用户授权预计 10 小时工程量的有界设计/参考验证任务；预算不作实际耗时。开始 fetch origin/main 后 HEAD 与远程均为 `f44c3e0e81f090637f6f21a7b63a9d12d3e30424`，工作区干净；GitHub 开放 PR 查询为空。新建本地分支 `docs/fem-g0a-dof-design`，队列单独登记 in_progress。
- 阅读当前 AGENTS/L0、进度/队列/分支整合、通用 FEM 规划、L1/L2 离散/FSI/状态/并行、INFRA-01/HPC-02 证据边界；逐项审计 DoF/constraint/fields/嵌套 Schur、checkpoint/输出和既有测试源码，未执行既有数值检查。
- 新增 [专题设计](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md)，固定提交源码映射、六项契约、三种配置/14 行示例、父编号公式、PETSc 3.19.6/3.23.7 官方 tag 静态核对、容量复杂度与 C++ 切片。总纲只加链接和 G0A 范围说明。
- 新增 docs/research/fem_g0a/ 下参考模型、unittest 与只读文档/语法检查器。模型没有求解器/进程调用，全部标准库；Fraction 手算 oracle 含非对称矩阵、非零 lifting、K/W 不同、置换与 dt 更新，另覆盖三树/刚体/1/2/4 模拟分区/空 local block/错误编号。
- 实际执行 `python3 -B docs/research/fem_g0a/test_reference_model.py`：首轮 18/18；交叉审查新增真实语义 alias 键、三层子矩阵元素 oracle 和单孩子拒绝后，最终 20/20 通过。原始输出及源码哈希见 [证据目录](../research/data/fem-g0a-2026-10-30)。这是分区索引逻辑验证，不能称 MPI 测试。
- 同一作者交叉核对源码/契约/手算/反例，修正普通保留行 Dirichlet 与 FSI 消元的区别、结构内部 BE 系数避免双乘、joined ID 和含 rank 的 fingerprint、checkpoint 缺失 reduced 排列版本、旧 PETSc prefix 长度与 Schur 内部 KSP 的接线范围；不冒称独立多人审查。
- 官方源码直接临时下载超时，改用浏览工具读取版本 tag 源码；未安装依赖。`check_artifacts.py` 首次把既有站点路由误当文件路径，补上源码路由解析后通过；没有修改旧文章链接来规避检查。
- 实际执行 `python3 -B docs/research/fem_g0a/check_artifacts.py`（Python AST、7 份 Markdown 围栏/本地文件与站点路由、固定 EONSim SHA/路径/行号、14 份审计源码哈希）、`git diff --check`，并检查新文件空白和生产路径零差异。最终输出见 [checks.txt](../research/data/fem-g0a-2026-10-30/checks.txt)。检查不证明远程链接存活或网站渲染。
- 使用 eonsim-knowledge-capture 的 algorithm-note 模板新增 [未发布草稿](../../website/drafts/dof-semantics-and-nested-fsi-blocks.md)，登记 KNOWLEDGE_LOG；分开理论、基线实现、独立参考验证与性能未测量。值得沉淀的知识是 K/W 区别、共享代表唯一归属与父编号空间，待人工审查。
- 未执行配置/编译器/编译、CTest、MPI、EONSim、性能基准或网站构建；未修改生产 C++、CMake、既有数值测试/算例、CI 或 sources/；未 commit、push、创建 PR、合并或发布。FEM-G0A 转 review（本地交付），FEM-G0 整体和其它阶段仍 deferred，INFRA-01 review 与其真实数值验收状态不变。
- 未解决事项为人工审查、真实 PETSc/MPI 接入及物理验收；下一最小候选 G0-B1 仅将现有语义适配到 IS、保持 root 编号与默认行为，未启动。

## 2026-10-31 / FEM-G0A — 后续提交推送授权

- 用户明确要求将改动推送到远程；提交目标为 `docs/fem-g0a-dof-design`，保持 FEM-G0A review、FEM-G0 deferred 和 INFRA-01 原验收状态。
- 提交前 fetch 确认 origin/main 仍为 `f44c3e0e81f090637f6f21a7b63a9d12d3e30424`，远程目标分支尚不存在；工作区仅含此前 FEM-G0A 交付文件。
- 核对两个工作流：数值工作流 push 仅匹配 main/codex/**，网站工作流 push 仅匹配 main，均不匹配本设计分支；提交另加 `[skip ci]`。不创建 PR、不合并、不运行或重跑构建。
- 更新当前状态中的“本地未提交”说明，保留 2026-10-30 的基线、检查证据与会话历史；不改变参考模型、生产代码或知识草稿的未发布状态。


## 2026-10-31 / BRANCH-02 — 合并 G0A 与清理远程分支

- 用户明确授权合并远程分支并清理多余分支。基线 f44c3e0；6 个历史分支已完全合并，新增 docs/fem-g0a-dof-design 的 b674d5a 多 1 个提交；远程无开放 PR。
- 在 integration/merge-cleanup-2026-10-31 审查合入 G0A 设计、标准库参考模型与历史证据，重跑 20 项参考测试通过；源码、CMake、数值测试、算例和 CI 未变化。
- 检查工具首次执行因 GBK 解码 UTF-8 失败，启用 UTF-8 后发现 14 份源码仅因 CRLF 检出被误判修改。显式 UTF-8 读取并仅归一化 CRLF 后全部基线哈希匹配；代码及其他空白变化的负例仍被识别。没有改写审计源码或旧证据。
- 更新 G0A 的设计交付状态和本轮合并清理清单；G0 生产实现及 G0B/G5/G1 未执行，INFRA-01 最终集成验收仍 review。此次是维护已有知识成果，不新增重复知识文章，原草稿未发布。
- 实际检查：20 项参考测试、AST/Markdown/固定源码引用/14 份哈希、LF/CRLF 与修改负例、Git 差异和祖先关系；结果见 BRANCH_CLEANUP_2026-10-31.md 与对应 checks.txt。
- 远程更新采用原子正常快进 main 加 7 个精确 SHA 保护的分支删除；推送前再次核对各 tip，保留 main 与完整可追溯历史。提交使用 [skip ci]，本轮未配置或编译项目、未运行 CTest/MPI/性能/网站构建。

## 2026-10-31 / FEM-INTEGRATION — 基线恢复与G0检查点

- 用户已明确解除纯设计限制，授权G0B→G0→G5→G1整体实现/测试/推送及按规则主线交付。main复核为72a3356，无开放PR；分支codex/fem-g0-g5-g1。旧快照未提交G0A工作已stash与归档保护。
- 在4CPU/32GiB云环境复用锁恢复3.23.7与3.19.6；移走引用失效临时路径的旧构建目录，从空产物重建。基线主环境35/35各模式、兼容7/7通过。
- 实际修改：DoF语义头、field/reduced布局、显式slot K/W映射、PC树与SNES接入、配置/CMake；新增pc_plan及pc_restart测试，复用schur/time_retry脚本；文档/队列/知识草稿同步。没有G5/G1能力。
- 当前G0主环境 `scripts/cloud/run.sh 3.23.7 {debug,release} all /workspace/eonsim-cloud` 分别43/43通过；兼容mpi-failure 10/10及三recipe/重启7项通过。最后补验状态见实施记录。精简结果、来源清单和原始日志位置见FEM_INTEGRATION_VALIDATION.md。
- quantity首次失败定位为原始压力块AMG粗层问题，固定使用Jacobi后通过；没有改变物理方程、精度门槛或超时。独立审查指出并修正rank局部输入错误、子KSP数组生命周期、Schur命名options漏检、零初态配置绕过与PC负例假通过条件。
- 权限：仓库API报告push可用，main保护规则读取403（integration缺少该端点权限）；尚未尝试合并或绕过规则。正式PR等待全部阶段完成。
- 下一步：保存并推送经验证G0检查点，检查CI，随后统一时间映射/accepted历史，从BE迁移进入G5。预计工程量不是实际耗时。

- 接续验证：主锁Release完整43项通过；旧锁三recipe补验3项通过。主锁Debug及旧锁Release新增奇异诊断失败/恢复10项均通过。性能两算例/1、2、4rank/四模式/三重复共72样本，最大场差3.307e-12，直接解在此小问题中solve中位数较低。证据入g0-supplement.json及pc-recipes-benchmark.json。
- 使用知识采集Skill生成真实装配置换与PC验收草稿并登记；尚未发布。当前准备提交推送检查点并进行新提交云端CI，之后进入G5。

## 2026-10-31 / FEM-INTEGRATION — G5与G1最终集成

- 用户明确授权WSL2真实构建/MPI，并由云端CI复验；继续使用两套Linux显式依赖锁、原presets与恢复入口，没有另建构建系统。实际资源24逻辑CPU、约32GiB，编译并发4、每rank数学库单线程。
- G5依次推送c923387（独立BDF2）、bab4fda（ALE/FSI BDF2）、25e0945（独立一阶/二阶alpha）、2fcd2fd（共同stage ALE/FSI alpha）；四个检查点云端三环境CI均成功。局部/整体切线、速度/压力/结构与网格时间阶、能量/阻尼、接口运动与功、事件/拒绝/完整历史重启见阶段JSON，不能将BE启动或参考ODE单独当作FSI精度证据。
- G1增加独立规范化导入层、Gmsh4.1 ASCII子集、Tri3/P1与Quad4/Q1相容混合二维标量Poisson/扩散；贯通命名材料和D/N/Robin、纯Neumann、METIS/owned/ghost/AIJ、G5时间与checkpoint、VTU/PVTU/PVD。二维分区版本3，三维保留版本2及旧Tet4读取。
- 独立审查发现并修复导入partition tags静默丢弃、名称维数检查、线性PC局部失败集体传播、不连通域零空间和restart输出时间片覆盖。新布局配置独立声明固定语义/存储策略；不把PC树变化或诊断MatPermute称为生产排列。
- 数值检查包括独立解析Q1质量/刚度、角点反转、外部编号/方向、三拓扑patch/MMS/畸变/边界法向通量、双材料、纯Neumann、空间与时间加密、1/2/4rank重启和真实失败恢复。对称矩阵成对计算消除极小步长舍入导致的假非对称；未降低rank、放宽容差或延长失败超时。
- 配置补充前主锁Debug/Release各59项及兼容13项通过；这份中间证据保留于build/pre-layout-policy-evidence。配置补充后的最终清单为主锁各60项、兼容13项，运行结束结果与源码哈希归档fem-final.json；不将中间结果冒充最终通过。
- 使用eonsim-knowledge-capture生成二维规范化/双线性单元草稿并登记，所有文章仍在website/drafts。当前环境没有node，本地网站命令未运行成功；网站构建及草稿隔离交由PR云端检查。Markdown本地链接检查通过。
- 最终主线与PR状态以后续交付记录为准；G2/G4仅实施必要子集，其余阶段不关闭。未测二维性能，也未把G0原检查点72样本性能结果归到新源码。

- 最终配置补充后Debug60/60、Release60/60、兼容13/13全通过；CTest墙钟574.87/213.11/18.50秒。fem-final.json保存109份源码哈希和实际清单，独立审查无确定源码阻塞；准备最终G1提交、PR及云端验证。


## 2026-10-31 / FEM-INTEGRATION — 主线交付完成

- 最终提交9e5a1ed经独立复核：109/109源码哈希一致，实际inventory/JUnit为60/60/13，所有命令退出0，无超时/失败/跳过，日志及二进制哈希匹配。
- PR #23云端三环境同样60/60/13通过（41199182613），push CI成功（41199162462），网站及草稿隔离成功（41199182529）。云端4CPU约16GiB，未混同WSL2资源。PR合并预览300a7544与功能提交tree一致。
- GitHub按expected_head_sha=9e5a1ed正常merge成功，main为9cc2e102e8e32f929de1c9a790c1ae527b931fa2。未绕过检查、未强推、未覆盖他人修改。
- 完成状态、队列、用户指南和交付JSON归档；G0B/G0/G5/G1及INFRA-01关闭，G2/G4只含必要子集，其余阶段保持deferred。知识文章仍为草稿。
- 完成状态归档为文档变更；生产源码及测试保持已验收版本，最终远程同步与main CI由交付时再次核对。

## 2026-10-31 / CI-DEPENDENCY-POLICY — 主力 PETSc 与按需兼容验证

- 按用户要求，将 PETSc 3.23.7 确定为日常主力构建版本；PETSc 3.19.6 不再参与每次 Push/PR 的自动编译和链接检查。
- 更新 `AGENTS.md`：规定第三方差异优先通过能力检测、官方版本宏和集中兼容层处理；需要 Patch 时必须版本限定、可追溯、可重复应用；仅在相关兼容路径变化时做针对性验证。
- 更新 `.github/workflows/core-numerics.yml`：日常矩阵保留 PETSc 3.23.7 Debug/Release；3.19.6 仅在手动触发并勾选 `run_legacy_petsc` 时执行 Release `mpi-failure` 专项检查。
- 更新 `docs/development/BUILD_AND_VALIDATION.md`，使构建说明与工作流一致。保留 3.19.6 锁文件和运行脚本，未删除历史环境。
- 在工作流文件完成调整前，首个内容提交曾短暂触发旧矩阵的一次过渡 Push CI，其中 PETSc 3.19.6 Release 专项 job 已通过；随后最终工作流改为独立可选 job，当前 PR CI 中 3.19.6 job 明确 skipped，不执行编译/链接。最终 3.23.7 Debug/Release CI 正在验收；不将过渡运行解释为未来日常策略。

## 2026-10-31 / DEV-PROCESS-POLICY — 长期知识积累规则

- 用户明确提供“EONSim 持续知识积累要求”，将其固化为根目录 `AGENTS.md` 的项目级规则；Codex 新 Task 应读取该文件执行，不要求用户每次重复粘贴。
- 规则要求每项实质任务记录重要错误与根因、真实测试证据，更新 `CODEX_SESSION_LOG.md`、`CODEX_PROGRESS.md`、`CODEX_TASK_QUEUE.md` 和 `KNOWLEDGE_LOG.md`；有复用价值的技术成果使用 `eonsim-knowledge-capture` Skill 形成 `website/drafts/` 草稿。
- 明确边界：普通 typo/纯格式/机械小改动不强制生成文章；没有复用技术成果时不制造草稿；文章未经人工审核和 PR 合并不得发布。
- 同步更新进度和任务队列，将本项记为 review，并更新知识索引。相关文档提交：AGENTS `54cba2e`、进度 `04b334a`、队列 `389fc5b`；后续会话日志和知识索引提交由本条记录的 Git 历史追溯。
- 验证范围：通过 GitHub 仓库内容接口复读并检查目标文件，确认规则文本和链接路径存在；本任务没有修改 C++/CMake/数值测试，没有运行编译、CTest、MPI 或性能测试。PR #24 的 GitHub Actions 结果以实时 Checks 为准；未完成项目不标记为通过。
- 未生成技术文章草稿：本次交付是研发流程规范，不是新的算法、数值方法或可复用技术错误分析；该决定已登记在 `KNOWLEDGE_LOG.md`。


## 2026-10-31 / DOCS-01 远程交付授权

用户追加要求推送并合并到远程。再次 fetch 后 origin/main 仍为 a508e3d；89 份 Markdown 的静态检查与 git diff --check 通过。准备提交并通过 PR 合并；远程检查结果待实际完成后记录，草稿不转正式栏目。

## 2026-10-31 / DOCS-01 远程交付完成

- 功能提交 `40f87c0989cde56d085f3b05eea31b90116dc9e9` 已推送，并通过 [PR #25](https://github.com/saitoasukakawaii/EONSim-new/pull/25) 合并为 `be21882b589735ff449b472e8efc76555cffb9fb`；没有强推。合并 tree 与功能提交一致，已用 `git diff --exit-code 40f87c0 be21882` 核对。
- [PR 数值 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41207324586) 实际日志确认：PETSc 3.23.7 Debug/Release 各 60 passed、0 failed、0 skipped；测试对象为合并预览 `8e835ecb5b9475e2e70f802b9944554e13f4e2cb`。PETSc 3.19.6 手动兼容 job 本次 skipped，不计为通过。
- [网站 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41207324560) 的生产构建与草稿/模板隔离均成功。此为远程补验，前序本地缺少 Node 的记录仍成立。没有新增性能结论，也没有将草稿转为正式栏目。
- 本地 main 已快进至合并提交；仅补记任务完成状态和上述证据链接。本补记不改源码/网站，静态复核后使用 `[skip ci]` 提交，避免重复数值套件；不把前述结果标记为补记提交的新运行。


## 2026-10-31 / TEST-POLICY-01 — 增量验证与历史证据复用

- 用户明确要求仅改约束，不开发和编译项目，并停止每次开发结束后的全量测试及无关历史测试重跑。源码基线 `3df1c31f8f3b6c995e00368782a94971a92371c3`；本次变更仅为 Markdown；用户随后授权本地提交，分支 `codex/incremental-validation-policy`，未推送。
- 静态检查发现旧规则虽写“最小验证”，仍在基础设施交付、公共接口和最终集成处要求 `all`，且“代码继续变化”重跑条件未限定影响范围。已统一 AGENTS、L0、构建与验证、路线及 Goal 流程：只检查新增/受影响行为，复用未受影响的历史通过证据，全量仅在用户明确要求时运行。
- 历史证据保留原提交、命令/环境/结果或归档链接；本次未运行须明确标注，不计作当前提交新通过。受影响路径不能仅用改动前的通过记录代替必要检查。
- `.github/workflows/core-numerics.yml` 仍配置 Push/PR 的主锁 Debug/Release `selection: all`；本次按“仅改约束”限定未修改工作流、测试或脚本，没有实现 CI 自动选测，也没有触发远程验证。
- 验证仅限文档阅读、`git diff --check`、改动 Markdown 本地链接目标检查和差异范围核对；没有运行 CMake 配置、编译、CTest、MPI、性能实验或网站构建。无数值结果或性能结论，未生成知识文章。
- 进度、队列及知识索引同步；任务为 review（本地分支交付，未推送、未合入 main），不改写历史交付记录。


## 2026-10-31 / CI-INCREMENTAL-01 — PR 增量执行（进行中）

- 用户选择并批准：仅 PR 自动增量检查，分支 Push/main 不重复数值 CI；脚本验证加一次小型云端验收；不改生产求解器、不跑全量、不自动合并。基线 ef20e03，分支 codex/pr-incremental-ci。
- 原入口只有 core/all/mpi-failure，先编译所有目标且重复做 2/4 rank 预检。新增显式路径/测试/目标映射、精确 JSON 清单执行、同 PR 成功 receipt；保留原必需检查名称与手动全量/旧锁专项。
- 复用前检查 workflow 成功、repo/PR/base/规则及依赖指纹、head 祖先关系、完整双模式来源；找不到有效证据只重新计算 PR 相关项，不能落回 all。artifact 下载跨域时去除 Authorization；ZIP 只读取单个有界 receipt.json，不解压到工作区。
- 首轮选测脚本测试发现 include/eonsim/fsi_element.hpp 未映射；补齐后 24 项 Python 测试通过。共享 reader、流体边界对固体的使用者及 profile 日志输入也纳入显式规则。
- 已执行 python3 tests/test_ci_selection.py（24 项通过）、python3 tests/test_cloud_evidence.py（6 项通过）、bash -n scripts/cloud/run.sh、actionlint 1.7.7 的 core-numerics.yml 语法检查及 git diff --check；尚未运行本次生产构建/数值测试，云端 smoke 待 PR 验收。旧数值记录不计为本次通过。
- 使用 eonsim-knowledge-capture 记录 CI 选测/证据复用草稿，不发布；后续补充真实云端证据及文档提交的复用结果。

### CI-INCREMENTAL-01：首轮云端精确清单验收

- 实现提交 `8f695cc6ed17fcbbd2736cceba38e7984de2b67e` 已推送并创建 [PR #26](https://github.com/saitoasukakawaii/EONSim-new/pull/26)，未合并。主数值 [run 41214961025](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41214961025) 成功，实际测试 merge preview `9ce31f9f869770e5672b01a1dfa39b4788710c6f`，tree 与功能提交相同。
- PETSc 3.23.7、OpenMPI 5、GCC 15.3，云端 4 CPU/约 16 GiB；Debug/Release 仅运行 poisson_verification，各 1 passed、0 failed、0 skipped，rank=1。构建 targets 仅 eonsim、verify_runtime；锁定运行时探针 rank=1 另计，不冒充数值测试数。JUnit 与清单一致，receipt 已生成。
- 实际入口：`scripts/cloud/run.sh 3.23.7 <debug|release> explicit .cloud build/ci/plan.json`；CTest 使用 `-R '^(poisson_verification)$'`。完整命令、退出码及精简结果见 [initial.json](../research/data/ci-incremental-2026-10-31/initial.json)。本地未编译或运行求解器，主锁全量及旧锁未执行；旧锁 job 为 skipped。
- 网站 run 41214961032 成功，草稿隔离通过。GitHub runs 查询确认该提交只有两个 pull_request 事件，没有 Push run。
- 下一笔仅补记文档/证据，将用于实际验证同 PR receipt 复用；复用结果尚未计为完成。

### CI-INCREMENTAL-01：历史证据复用验收与交付

- 文档/证据提交 `00722958b64df7cb65821269a08e510c5214834b` 的 [run 41215264515](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41215264515) 全部成功；selection 明确 `tests=[]`、`python=[]`、`reused=[poisson_verification]`。Debug/Release 的依赖缓存、restore、checkout、build/test 和数值 artifact 上传步骤均 skipped，不是重新通过一次数值测试。
- 新 receipt 指向 previous_run_id=41214961025，每个模式的原始来源仍为首次 merge preview `9ce31f9f869770e5672b01a1dfa39b4788710c6f`。精简证据见 [reuse.json](../research/data/ci-incremental-2026-10-31/reuse.json)。网站 run 41215264596 也通过；旧锁专项未运行。
- 补充两个标准库测试验证手动 all/explicit 清单生成及 PR 禁止请求手动全量，执行 `python3 tests/test_ci_selection.py SelectionTests.test_manual_all_and_explicit_cli_only_plan_requested_names SelectionTests.test_pr_cannot_request_manual_full_suite`，2 项通过；没有执行任何全量数值测试。选测/receipt 测试文件现共 26 项。
- 本地直接查询 api.github.com 曾超时；改用已连接 GitHub 的只读 fetch/log/artifact 接口取得证据，没有修改网络策略或把查询失败计为测试失败。
- 交付为 PR #26 review，未自动合并。代码、规则、状态及知识索引同步，文章保持 draft。已验证范围为新 CI 路径；不扩大为现有 60 项套件的新通过记录。最后补记只涉及状态/证据及上述脚本测试，数值执行链与规则指纹保持不变。


## FEM-G2A — 局部 P2 检查点（未完成）

- 用户批准完整 P2 稳态 D/N、1/2 rank 闭环，本地开发及云端相关检查；10 小时为估计，闭环完成优先。
- 已将 main 快进至 PR #26 合并提交 `35bf1a1`，新分支 `codex/fem-g2a-p2`。
- 新增纯参考 P2 tabulation，节点顺序为顶点及 01/12/20 边中点；不修改网格几何、生产模型或依赖。
- 实际命令：`c++ -std=c++17 -Wall -Wextra -Wpedantic -Iinclude tests/verify_tri_p2.cpp -o build/p2-local/verify_tri_p2 && build/p2-local/verify_tri_p2`，退出 0；独立六个二次空间单项式的值/梯度重现、节点插值、反向边迹通过。无 MPI/PETSc；不是求解器验收。
- `python3 tests/test_ci_selection.py`：26 项通过；`git diff --check` 通过。新增 CMake 注册项尚未通过 CMake 构建执行，不将直接编译结果称为 CTest 通过。
- 未完成：实体边空间、分区存储、装配、D/N、输出、数值收敛和真实 1/2 rank、云端 CI、PR。任务继续 in_progress。源码检查点由本记录所在 Git 提交追溯。
- 暂不生成完整知识文章：只有局部基础函数证据，完成真实闭环后按知识采集 Skill 汇总，不能提前写成生产能力。


## 2026-11-01 / FEM-G2A — 分布式 P2 实现与本地验证

- 源码提交 edfc73c；基线 35bf1a1，分支 codex/fem-g2a-p2。新增独立 ScalarP2Space，以原始顶点 ID 对规范化边，在现有 METIS 单元分区之后建立 owned/ghost 和包含远程单元贡献的完整图。HDF5 可选组 version=1，原几何版本不变。
- P2 稳态统一系数 Poisson、非零 D/N、原生二次三角形 VTU/PVTU 已接入；geometry/space 分离。缺失空间、非法连接/owner、非有限坐标明确拒绝。未支持模型在配置/准备阶段报错。
- 本地命令 `scripts/cloud/run.sh 3.23.7 debug explicit .cloud build/p2-local/plan.json` 首次执行 p2_space_oracles、tri_p2_oracles，2/2 通过；随后 `scripts/cloud/run.sh 3.23.7 debug explicit .cloud build/p2-local/solve-plan.json` 只执行 scalar_p2_verification，1/1 通过。空间身份/读取校验修改后，仅重跑受影响的 P2 求解项，通过。
- 真实 1/2 rank 畸变 patch L2 约 3e-12、H1 约 5e-11；n=4/8/16 正弦最细 L2/H1 阶 2.9699/1.9711；双 rank 使用节点/单元反排输入，场按实体身份对照。配置拒绝和强制 KSP 失败均通过。
- 直接 C++17 编译执行 verify_tri_p2 补充解析刚度/载荷矩阵 oracle，及 verify_p2_space 的实体/远程邻接验证，均通过；26 项 CI 选择脚本测试通过。未执行全量、旧锁或本地 Release。
- `python3 build/p2-local/check_corruption.py` 使用 h5py 3.14 修改 rank_1.h5，分别删除 P2 组、篡改连接和 owner；真实双 rank 明确失败且未生成索引。该额外本地检查脚本与结果已归档。新补入自动脚本的旧 P1 分区拒绝场景尚待云端执行。
- 编译发现 signedness 和 misleading-indentation 警告，已修正并重新编译，无新增警告。未降低数值门槛或放宽测试超时来隐藏失败。
- 证据 docs/research/data/p2-2026-11-01；摘要记录实际执行时的 dirty 状态，不能把后来新增测试标为此前已执行。云端验收及 PR 仍待完成，任务 in_progress。


### FEM-G2A 云端验收完成

- PR #27：功能提交 6327c189b9cd936159fb11c5f472934047fa2f0e，生产实现 edfc73c。run 41283957039 的实际 merge preview 为 60ee8e26a0ccf8f1b11aad8fe1906c17f67cd87c。
- PETSc 3.23.7 Debug/Release 各 19 passed、0 failed、0 skipped；selected checks 包含 P2 三项及共享配置/分区/语义入口的代表回归，未运行全量。最终新增的 missing-space 自动负例与解析刚度/载荷 oracle 已随此次 CI 验收。旧锁 job skipped。
- 云端 4 CPU、约 16 GiB，网站 run 41283957245 通过；草稿保持未发布。来源摘要 docs/research/data/p2-2026-11-01/cloud.json。
- 状态 review，未自动合并。文档收尾只复用上述通过证据，不将其记作新提交重新运行。Markdown 本地链接与 git diff --check 通过。


## 2026-11-01 / FEM-G2A 合并状态接续

用户要求继续推进。通过 GitHub PR 信息及 git ls-remote 确认 PR #27 已于 2026-11-01 合并，main 为 c0745ea88c89ab08bb5babbcae530ee2008a49cf；本地 main 已快进。审核时间线没有待处理的代码审查意见。任务改为 done，数值证据复用既有 run 41283957039，不重新编译或运行测试。后续新增范围正在确认。


## 2026-11-01 / FEM-G2B — P2 Robin 与纯 Neumann

- 用户要求继续推进；上一任务 PR #27 已合并。提出后续范围选择，在等待期间完成主线同步；未收到其他选择后按已说明的推荐项推进边界扩展。未自动合并 PR。
- 实现 d6ec4244a73adbcbfd839b93cc595260a0138447。Robin 复用三节点边迹，增加正系数边界矩阵和相应制造解载荷；纯 Neumann 复用现有 LinearSystem 常数零空间及载荷相容性检查。无新配置键、依赖、分区格式或主求解器后端。
- 非直观数学细节：P2 顶点基函数的体积积分为零，节点均值不是物理体积均值；归一化使用积分后的全局均值，并同步规范制造解的误差参考。
- 执行 `scripts/cloud/run.sh 3.23.7 debug explicit .cloud build/p2-local/solve-plan.json`，清单仅 scalar_p2_verification：1/1 通过，真实 1/2 rank 全 Robin 与纯 Neumann patch、用户显式源项/Robin 数据、MPI 场值对照及不相容载荷拒绝均通过；相关已有 P2 路径随受影响测试复验。
- 双 rank 纯 Neumann L2=6.2481e-13、H1=9.2768e-12，物理积分=-9.9920e-16。没有放宽容差；编译无新增警告。没有执行全量、旧锁或本地 Release。精简数据与原摘要归档 docs/research/data/p2-boundaries-2026-11-01，原摘要保留实际 dirty 状态。
- 使用知识采集 Skill 更新现有 P2 草稿，不制造重复文章；云端相关验收待执行。


### FEM-G2B 云端交付

PR #28 的 run 41287626201 成功，实际 merge preview bbf494b84af62b904a7821355d75fab982831b16，功能提交 41547fa，生产源码 d6ec424。PETSc 3.23.7 Debug/Release 各 10 passed、0 failed、0 skipped；旧锁专项 skipped。网站 run 41287626208 成功。摘要 docs/research/data/p2-boundaries-2026-11-01/cloud.json；本次无全量测试。状态 review，未自动合并；收尾文档复用上述成功证据。


## 2026-11-02 / FEM-G2C — 启动检查点（未完成）

- 用户授权按约 10 小时规划实施，验收完成后才创建 PR。基线 `1bc87a7`，分支 `codex/p2-transient-diffusion`；当前改动未提交。
- 核对 P2 装配、P1/Q1 时间驱动及 checkpoint 接口。P2 空间身份尚未纳入 checkpoint，P2 输出局部 I/O 异常的集体传播需完善；这些是待实现事项。
- 增加独立解析 P2 一致质量矩阵 oracle（参考三角形面积 1/2，整数矩阵除以 360），同时保留刚度、载荷和二次重现检查。顶点行和为零，不采用行和集总质量。
- 实际执行 `c++ -std=c++17 -Wall -Wextra -Wpedantic -Iinclude tests/verify_tri_p2.cpp -o /tmp/eonsim-verify-tri-p2-g2c` 及 `/tmp/eonsim-verify-tri-p2-g2c`，均退出 0。独立 C++17 检查，无 PETSc/MPI，不计为 CTest 或瞬态生产验收。`git diff --check` 通过。
- 首次创建分支因沙箱中 .git 只读失败，按工具授权升级后创建成功；没有绕过文件系统权限。
- 尚未实现生产时间推进、恢复及时间序列，未构建求解器、未跑 Debug/Release 或 MPI 验收；未创建 PR。任务保持 in_progress。尚无完整可复用成果，不新增文章草稿。


## 2026-11-03 / FEM-G2C — P2 瞬态闭环本地验收

- 用户要求继续实施，完成后提交 PR；源码 `d19a03268577b33ddfb41177037d9bbc1f76d273`，基线 `1bc87a7`。上次只完成质量矩阵 oracle 后停止的检查点不代表完整交付；本轮继续实施，没有后台任务或绕过额度限制。
- 生产 P2 接入一致质量矩阵、BE/变步 BDF2/一阶 generalized-alpha、时变 D/N/Robin、事件、真实 KSP 失败后的有限缩步。历史只在求解成功后更新，瞬态 Neumann 保留均值。
- 复用 v3 checkpoint，附加 P2 实体整数身份、编号、owner、连接及边界标签签名；不能把大整数 ID 转 double 后散列。恢复时局部读取异常集体传播，校验跨 rank 时钟/历史元数据一致。P2 输出加入算法导数、接受步序列和 XML 转义，分片失败不发布全局索引。
- 初次沙箱 MPI 预检因 PMIx socket errno=1 失败，按工具授权在沙箱外重跑；不是数值失败。首次新增 time 测试误向 BE/BDF2 配置 rho_infinity，配置器正确拒绝；修正测试仅在 alpha 设置 rho，未改校验规则或放宽容差。其余 restart/failure/质量 oracle 已通过，未因该测试错误重复运行。
- 实际命令：`bash scripts/cloud/run.sh 3.23.7 debug explicit .cloud build/p2-local/solve-plan.json`，原 P2 steady 检查通过；`... debug explicit .cloud build/p2-local/transient-plan.json` 首轮 3 passed/1 failed；随后 `... debug explicit .cloud build/p2-local/time-only-plan.json` 仅时间项通过。补充变步时间阶和用户边界后重跑该时间项通过；签名加入语义身份与标签后仅 `... debug explicit .cloud build/p2-local/restart-only-plan.json` 重启项通过。
- `bash scripts/cloud/run.sh 3.23.7 release explicit .cloud build/p2-local/release-plan.json`：scalar_p2_verification/time/restart/failure、tri_p2_oracles 共 5 passed/0 failed/0 skipped；应用 Release，锁 PETSc 3.23.7/OpenMPI，单 rank 单线程，数值 MPI 为 1/2 rank。环境为本地 WSL2，不能称云端运行。各步命令、依赖和结果保留于证据 JSON。
- 独立质量矩阵逐项对照解析值；恒定与交替步长时间加密、rho=0/0.5/1、时变端点 D 与自然 N/Robin、绝热积分、乱序输入 1/2 rank 对照通过。重启覆盖事件处和有效多步历史，输出原时间片/序列保持；真实 KSP 限制触发缩步，重放到相同实际步长结果一致，重试耗尽不改 checkpoint。
- `python3 build/p2-local/check_history.py`（系统 h5py 3.14.0 + 锁定 MPI/求解器）：双 rank 缺失 previous/rate、非法 time_metadata、非有限 scalar、改变边实体语义身份均拒绝，8/8 通过；该脚本作为本地补验归档，不新增日常 Python 依赖。
- `python3 tests/test_ci_selection.py` 26 项通过；`python3 tests/test_cloud_evidence.py` 6 项通过；新增文件路径分类无未知项，PR 预计选取 15 个相关 CTest（最终以实际 PR 差异为准）；`git diff --check` 通过。没有全量、旧锁、性能或超过 2 rank 的本轮运行。
- 测试执行时 HEAD 为基线且源码 dirty，随后提交为上述实现 SHA；原始摘要保留真实状态。Debug 时间/失败结果早于仅签名补充，复用未受影响路径；最终 restart/Release/故障补验覆盖完整签名。不因为后续文档提交重跑。
- 使用 eonsim-knowledge-capture 整理 P2 瞬态历史草稿，保持未发布；已更新状态、队列及知识索引。PR 与云端检查尚待后续记录。


### FEM-G2C — PR #29 云端验收与交付

- 实现 d19a032，交付 head e5900a169d079c82b4af8509d1aa4af4fd199a88；[PR #29](https://github.com/saitoasukakawaii/EONSim-new/pull/29) 已创建，未合并。实际 merge preview b8c1642f08ef5333f55e874fa5c83157e7ba2a59 的 tree 284e3497681e54af1949869fee3c963e597deca3 与本地 head 一致。
- [数值 run 41582475827](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41582475827) 的 Debug/Release 日志及 receipt 均确认：PETSc 3.23.7，各 15 passed、0 failed、0 skipped。清单包含 P2 新增三组及配置/CMake 影响入口代表回归；不是全量。P2 新验收为 1/2 rank；共享旧检查 scalar2d_space 等保留自身最多 4 rank，不扩展 P2 验证结论。
- 云端 4 CPU、约 16 GiB；每模式构建、运行时链接和 CTest 命令退出 0；receipt 核对测试清单与双模式来源后成功。3.19.6 手动专项 job skipped。选测脚本的合成 failure/error/skipped XML 是负例输入，26/6 项脚本测试均通过，不将日志里的负例文本误认为数值失败。
- [网站 run 41582475766](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41582475766) 构建和草稿/模板隔离成功；文章仍是 draft。
- 精简机器证据、15 项清单与每项原始来源见 docs/research/data/p2-transient-2026-11-03/cloud.json。收尾仅补状态和证据，复用同 PR 上述通过记录，本次不重新编译或运行数值测试，不使用 skip ci 绕过检查。


### FEM-G2C 远端合并与补记竞态

最终状态查询发现 PR #29 已在 2026-11-03T05:16:50Z 合并，merge commit 为 dff911648e54507e9cca80ad1880c20b867a0c75，实际合并 head 为 e5900a1；本 agent 未调用合并工具。补记 87f6df0 在该时间之后推送到原分支，没有进入已关闭 PR，因此查不到它对应的新 PR CI，不属于检查失败或绕过。修正队列为 done；最终证据与合并状态单独提交纯文档补记 PR，不修改数值源码，不重跑历史已通过检查。


## 2026-11-03 / FSI-LOAD-01：时变压力与接受步历史

用户批准计划后执行；先 fetch origin，基线 `417e6f9`，独立分支 `codex/fsi-periodic-pressure`。
实现提交 `a6c6761084f2003c72593107c6aa5cbc351d75bb`。
新增 smoothstep 启动正弦压力、共同阶段评价、缩步重算和波形签名；
抽取既有场重建实现接受步 CSV/流固 PVD，集体传播写出失败，保留最终场路径。

实际验收命令、配置、rank、误差和失败尝试见 [本地验收](../research/data/fsi-pressure-2026-11-03/README.md)。
Debug state/convergence 直接脚本通过，局部切线/刚体 CTest 2/2；Release convergence 直接脚本通过，state/局部切线/刚体 CTest 3/3。
Python CI 选择器 26/26。Release 双 rank 示例 100 步完成，并实际生成检查响应图。
BE 粗步未达门槛后细化，保持原阶数标准；其他初期失败为测试配置/比较器/错误字符串问题，具体根因已归档。
未执行全量、旧 PETSc、新 4 rank 或性能基准；10 小时是计划估计，不宣称实际运行 10 小时。

使用 eonsim-knowledge-capture，形成 [阶段载荷与接受历史草稿](../../website/drafts/fsi-periodic-pressure-history.md)，未发布。
进度/队列/知识索引同步，任务 review；所有本地验收及记录完成后才创建 PR，未自动合并。

本地验收与记录提交 `38a83c9` 后创建 [PR #31](https://github.com/saitoasukakawaii/EONSim-new/pull/31)。自动增量 CI 数值 run `41589294783`，网站 run `41589294782`，开始时均 in_progress；最终结果另行记录。

云端数值 run `41589294783` 最终 success：PETSc 3.23.7 Debug/Release 各 24/24、零失败/跳过；3.19.6 按策略 skipped。网站 run `41589294782` success。数值检验提交为合并预览 `6bed816adfa8090d174c335da36b283b47d25f87`，PR head `38a83c9`，不是已合并 main。精简日志摘要见 [ci.json](../research/data/fsi-pressure-2026-11-03/ci.json)。仅补记录，不重跑本地检查。

## 2026-11-03 / FSI-NEXT-01：固定入口、可靠性与受控研究

- 用户要求实施下一步完整 FSI 任务，全部完成后才提交 PR；20 小时是工程量估计。fetch 确认 PR #31 已合并为 `06b05c4`，从该 main 创建 `codex/fsi-inlet-reliability`。未自动合并任何 PR。
- 生产实现 `0d93d41`，界面真实双域邻接补强 `69692ee`；最终性能脚本 `32783a5`。固定仿射三分量入口及 smoothstep 启动，BE/BDF2 终点规定值与 alpha 终点插值，冲突检查和 checkpoint 签名；新增共形弹性顶壁算例。
- 界面三角片按稳定节点 ID 分布式路由，只接受恰有一个流体与一个固体邻接单元的面。按参考面积积分位移/速度、另报当前面积；几何检查同时覆盖阶段和外推终点，失败必须早于历史提交。夹持反力不混入自由界面残量平衡。更新单体 FSI 长期契约。
- 实际本地 PETSc 3.23.7 Debug/Release 构建受影响目标，CTest 正则 `^(fsi_diagnostics|fsi_diagnostics_mpi|fsi_inlet|fsi_pressure_state)$` 各 4/4，零失败/跳过。含 1/2 rank、三时间格式终点、恢复、装配切线及真实拒绝重放；线性/Neo-Hookean Jacobian 最大差 1.54187e-8/1.54813e-8。
- 入口 Neo-Hookean 两格式各真实缩步 16 次；刚体 alpha 周期压力第四步阶段收敛而终点反转，失败 checkpoint SHA256 不变，失败步无历史发布。缩步 1 次后成功，与相同步长重放一致。
- `scripts/study_fsi_next.py --study inlet-time` Release 分场 RMS 比较：BE .905–1.056、BDF2 1.892–2.091、alpha 2.000–2.223。`--study accuracy` 最初时间污染为最后空间差 6.98 倍，统一细化后为 .09509；n=2/4/8 轨迹差减小，不宣称预定空间阶。旧进程超时不足，主动取消为退出 143；只复用已成功样本，以归档的 `finish_accuracy.py` 完成参考解，取消样本不计通过。
- `--study performance` 最终为 10 预热 + 30 正式样本，1/2/4 rank、n=4/8、625/5057 DoF。三次交替重复且同容差；最大场差 6.16e-11。直接法在小网格及 n=8 的 2/4 rank 更快，分块最大进程 RSS 更低；没有稳定加速证据，不改变默认求解器或引入推测性优化。
- 重要失败：BE/BDF2 误带 rho 参数；重复负例沿用输出前缀留下旧 PVD；粗 BE 固体位移阶 .844；仅按流体外表面计数缺少固体邻接。分别修正测试配置/前缀、细化时间、补强邻接及 oracle，未降低验收标准。性能首轮位移差 2.20e-14 经 dt^-2 放大为加速度差 1.027e-8；统一收紧非线性后旧 KSP atol 又导致 SNES -6，最终同时收紧所有 recipe 的线性容差，重新测量完整矩阵，失败数据单独保存。
- [验收 README](../research/data/fsi-next-2026-11-03/README.md) 记录完整命令、配置、依赖、rank、源码沿革、失败尝试及 JUnit/CSV/JSON/图。空间历史来自原方程提交，后续邻接修订不改变该平面共形算例，复用已有通过证据；没有全量或 PETSc 3.19.6 运行。
- Python 选测器 26/26；`git diff --check` 通过。使用 eonsim-knowledge-capture 形成 [知识草稿](../../website/drafts/fsi-inlet-endpoint-and-resolution.md)，未发布；更新进度、队列与知识索引。PR/云端结果另行记录。

FSI-NEXT-01 最终审查发现旧镜像弹性体使用单独参考几何分支，追加 Debug/Release `elastic_fsi_verification` 各 1/1（不重复前述已通过检查），并补 CI 映射；本地各累计 5 项。选测器 26/26、证据解析 6/6 通过，新文档链接检查通过。

## 2026-11-03 / WEBSITE-KNOWLEDGE-REFRESH — 网站与知识资产同步

- 基线 main `4f3a995de45dc1221a5303d7ed8a8a0104bd9f2e`；在独立分支 `codex/website-knowledge-refresh-2026-11-03` 更新网站首页、研发总览、知识索引、单体 FSI 专题及 FEM 学习页。
- 根据已合入 PR #31/#32/#33 更新 FSI 能力说明；根据 PR #27/#28/#29 更新 P2 标量有限元范围。相关测试数量只按已归档证据记录，不将选测描述为全量测试。
- 补记 FSI 与 P2 技术文章草稿的合并状态、CI 来源和限制；所有文章继续留在 `website/drafts/`，未自动发布。
- 同步 `KNOWLEDGE_LOG.md`、`CODEX_PROGRESS.md` 和 `CODEX_TASK_QUEUE.md`，修正 FSI-NEXT-02 已合并后的状态。
- 本任务只改文档，不运行 CMake、编译、CTest、MPI、数值或性能实验；网站构建/草稿隔离检查待本 PR 的 GitHub Actions 结果确认。

## 2026-11-06 — FSI-PROD-01 circular inlet / solid-wall tube

User asked to advance toward production FSI. Rechecked/fetched main `dd27eef`
(PR #36 merged), isolated branch `codex/fsi-production-tube`. Read architecture,
state, build and knowledge contracts. Implementation local `31a04e6`, remote
`718b7a6bb97fbb5eed09829a0bb7225d3963ee5f`, identical tree
`8b0adc8bd3b206576cefd9a0e90e5314397d24ec` verified before branch creation.
CLI push failed for missing HTTPS credentials; uploaded code via GitHub API.

Implemented circle profile with discrete MPI flux normalization and geometry
checkpoint signature, preserving rectangle default/signature; deterministic
independent disk/annulus Tet4 meshes with matching interface triangulations;
actual coupled tube acceptance and independent mesh oracles. Review performed
by the implementing agent, no independent external review claimed.

Important failure: an enlarged inlet radius violates zero velocity on clamped
interface rim nodes before restart compatibility is checked. Initial negative
test expected the wrong failure category. Split geometry-conflict and waveform
signature tests without changing solver tolerances. The test script was edited
while the first Python process retained its old code, so traceback source lines
can show a newer label; preserve the failed log and rerun the entire corrected
tube test. No production fix was needed for this failure.

Validation commands, source hashes, metrics, first failure and final logs:
[FSI-PROD-01 evidence](../research/data/fsi-tube-2026-11-06/README.md).
Restored pinned PETSc 3.23.7 with `scripts/cloud/restore.sh`; compiled using
`scripts/cloud/run.sh`, explicit affected tests only. Release tube and old
rectangle flow checks passed. Independent mesh tests 2/2 and CI-selection
checks 26/26 passed. Debug tube first failed at a negative-test process startup (LLVM OpenMP
assertion/PMIx error), while rectangle flow passed. Retained the failure,
reused the historical bounded PID-isolation workaround and reran the complete
tube check: 1/1 passed, zero skips. Thus Debug/Release each accumulated two
distinct affected checks passed. No tolerance or equation changes.

Additional signed radial-field inspection shows both local contraction and
expansion on this coarse transient mesh. Do not describe response as physically
qualified; PROD-02 must separate spatial/geometric/time effects and compare
against analytical limits and a pinned svFSI case. No default-tau, production
scale, patient accuracy, RCR, external Robin or multi-node claim.

Reusable derivation and failure lesson captured in unpublished draft
`website/drafts/fsi-circular-inlet-discrete-flux.md`; roadmap and task queue
advance toward quantitative tube qualification, vascular boundaries, real
geometry and multi-node scaling. Do not auto-merge main or publish the draft.

PR #37 acceptance: remote head `29d8082`, merge preview `92a28b5`, identical
accepted tree `8ef42cd7e716aa995b03030fa7ed0617e7e2c449`. Core run
42170183765 Debug/Release each 31 passed, zero failed/skipped; website run
42170183717 and incremental receipt passed. Final update only records evidence
and PROD-02 dimensionless-scale scoping (Re .006366, alpha 12.533 for current
coarse case); no numerical rerun or new physical accuracy claim. PR remains
unmerged and the knowledge article unpublished.
