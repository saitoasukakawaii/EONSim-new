# FSI-PC-05：场感知 AMG、压力 Schur 与混合精度界面校正证据

交付 [PR #59](https://github.com/saitoasukakawaii/EONSim-new/pull/59)，基线为已合并 #58 的
`af4a7fb3f4371fe1e518376bdd1c148b170f683e`。完整实现、公式和选项见
[使用说明](../../../development/FSI_ADVANCED_PRECONDITIONERS.md)，技术文章留在
[未发布草稿](../../../../website/drafts/fsi-field-amg-pressure-interface.md)。

## 源码、同步与执行顺序

所有生产、测试和驱动修改均先同步到远端，核对完整 Git tree 后才构建或执行。
本地 Git 没有 HTTPS 凭据，使用已连接的 GitHub API 创建同一 tree 的提交；没有更改权限。

| 阶段 | 已同步源码 / tree | 随后实际执行 |
|---|---|---|
| 首版实现 | `c5af27de8fdc7a42df855543ad6366ce7db70571` / `d959212602fc0e4149e8bbee55d2aedba31ff048` | Release 增量构建；三组 1/2/4-rank 代数；6 项集成；20 次真实 FSI |
| 空分区及更新契约修复 | `e565c9872551dad9dc7a01d4d7b613e8a96d3545` / `425cc9ddd9f235afa3d6255d56201504202dc9c2` | 压力和界面各 1/2/4 rank 通过；关闭对流 oracle 与 PCD 回调契约；两次单例诊断 |
| 独立消融研究驱动 | `9dfd8ac4435b484ab7eecb5e8fc4423c407ff235` / `00d589b0da6a96e9653027ea31b5d6ee98dfb6a6` | 使用 e565 二进制完成 60 次网格/密度/时间步对照 |
| PCD 边界尺度修复 | `19cd26f2af9b02859fac28ca8f662c29c20d47f1` / `4a5584bca52b05de1594ef38758987df84e66686` | 仅重建 eonsim/物理压力 oracle；2 项 CTest；旧库负控；38 次受影响 PCD 回放 |

最后一行是最终生产与测试源码。其后的文档/证据提交不算新的数值执行。
[来源记录](provenance.json)保存精确命令、构建配置、源码、文件及 ELF SHA256。
最终本地 PCD 回放所用 eonsim SHA256 为 `45ce710b6f7d1358c4b0524c9dc41d8cd2218beee2e416295d4c311d57132d77`。
初始 c5af 二进制没有另存不可变副本；其身份来自当时收据，不能从已覆盖的构建路径再次核验。

## 实现范围与未达目标

- `field_amg` 在联合流固速度块上递归保留 13 个候选槽位，包括两场平移/旋转及标量刚体速度，局部去秩后逐层传播，形成完整 Galerkin 粗算子；与语义压力/ALE 分裂组合。
- `lsc/bfbt` 是明确给出缩放规则、保留完整稳定化 D 的交换子变体；不是把 PETSc 忽略 A11 的原生 LSC 直接用于稳定化系统。
- 物理 PCD 装配当前 ALE 的质量、Laplace、有效时间/对流算子；最终保留质量及黏性尺度，完整 D 进入辅助求解。当前只支持统一正黏度及已有压力牵引辅助边界。
- 真实界面混合 patch 包含速度、压力、结构和 ALE 行，支持跨 owner 行、全局覆盖重数加权和刷新；它是 bulk 后校正，尚不是每个 AMG 层上的界面 smoother。
- FP32 仅用于局部 patch 的稠密 LU 因子及三角求解工作空间；全局矩阵、场向量、残量和改进更新保持 FP64，并支持显式 FP64 回退。

默认 `split/diagonal/none/double` 未改。当前结果没有完成一般网格无关收敛、全局内存/带宽或普遍加速目标；PCD 入口 Robin、速度质量 PCDR 增强、区域变黏度与每层界面 patch 未实现。不得将本 PR 写成这些目标已全部实现。

## 本地验证和原始失败

环境为锁定 PETSc 3.23.7、real double、Release，OMP/BLAS/MKL 各一线程，单节点共享容器。
`/proc/cpuinfo` 为 AMD EPYC 9V74；不能推断独占核心。实际 affinity、编译配置与文件摘要见 provenance。
最多 4 rank；没有本地全量、Debug、旧 PETSc、多节点或百万自由度验证。

| 当前有效覆盖 | 源码及结果 |
|---|---|
| `verify_field_amg` MPI 1/2/4 | c5af 三项通过；制造问题 385/1297 DoF、3/4 层，独立检查候选再现、Galerkin 数值更新、缺失分量/空 owner/恒等退化。1-rank 两档迭代 6→8；不能据此证明真实 FSI 网格无关 |
| `verify_pressure_schur` MPI 1/2/4 | e565 三项通过；独立稠密逆、完整/零 D、非转置 B/C、共享状态、失效/恢复、RCR compact 辅助传播、缺失/移除 PCD 回调及零 Newton 拒绝 |
| `verify_interface_patch` MPI 1/2/4 | e565 三项通过；独立加权作用、跨 owner、真实 patch 数 2/1/0/0、FP32/回退、奇异刷新及恢复 |
| `fsi_pressure_operators`、`fsi_pressure_operators_mpi2` | 19cd 两项通过；6 个独立 Stokes 作用 oracle、4 组 ALE/时间/对流积分 oracle、真实 WORLD 空流体 owner 与跨 rank 黏度拒绝 |
| 既有 `pc_plan_mpi1/2/4`、`pc_rcr_port_mpi2`、`adaptive_pc_mpi2` | c5af 五项通过；后续修改不影响这些默认路径，复用该证据，没有重复计为最终源码新通过 |

首版 `interface_patch_mpi4` 失败并达到 120 秒上限。PETSc v3.23.7 的 `MatIncreaseOverlap`
对局部 n=0 提前返回，而其它 rank 仍在 overlap 集体通信中，最终在 `VecScatterCreate`
暴露 `MPI_ERR_BUFFER`；诊断还复现 `MPI_ERR_TRUNCATE`。环境没有可用 GDB/LLDB，记录了
源码及错误轨迹诊断，未声称运行 debugger。e565 只在 overlap setup 临时补齐空 IS，使用共同
正 n，返回后立即销毁补位；patch 数值定义和门槛不变。原错误与修复后成功分别保留。

PCD 第二个问题来自物理研究：同时把 Mp、Kp、Fp 的辅助边界改成单位行列，破坏 Stokes
质量极限。最终用 `Kbc=QK+E`、`Ftilde=mu*Kbc+Q*N`，Mp 保持物理集中质量。
精确辅助逆时，N=0 应给 `(Mp/mu+D)^-1`。独立 oracle 只用解析体积/黏度及非对角 D
构造这个简单矩阵，再用长双精度消元，完全不读取实现的 K/F/T 来生成期望。
19cd 最大 Stokes 相对误差 `2.06789e-15`，四代积分最大误差 `3.97763e-16`。

将**同一新测试**链接冻结的 e565 静态库，编译/链接均成功，单 rank 运行明确 exit 1，
首个错误为 `PCD failed independent Stokes mass-limit action oracle`。这是真实旧实现负控；
正式新二进制未被替换。旧库、源码、编译器、对象及负控二进制摘要见归档 negative-control 收据。

e565 时以 MPI 2/4 启动的旧物理单元 oracle 只是在每个进程重复 `PETSC_COMM_SELF`，不能算分布式装配覆盖。真正的 WORLD fixture 是 19cd 新增的两项测试所覆盖。

## 真实 FSI 与独立原件审计

所有物理解、全步输出和历史对照 MUMPS 直接参考。严格门槛为场/历史绝对差 `2e-9`，
显式原 Jacobian 线性残量 `1e-12 + 1e-10*rhs_norm`；没有放松物理、Newton 或线性接受标准。

| 阶段 | 真实求解 / 接受步 / 已记录线性修正 | 最大场差 | 最大历史差 | 最坏残量/门槛 |
|---|---|---|---|---|
| 初始 c5af | 20 / 54 / 117 | 1.257624560047077e-11 | 8.104628079763643e-15 | 0.009257947264879914 |
| 三网格及强耦合研究，e565 binary + 9df driver | 60 / 180 / 360 | 9.641748510702541e-11 | 5.717648576819556e-14 | 0.009313561967114794 |
| 最终 PCD，19cd | 38 / 108 / 225 | 3.1915137199689525e-11 | 5.684341886080802e-14 | 0.009273085855602773 |

每阶段都通过独立标准库解析器重读 log/CSV/VTU、owner/ghost、单元拓扑与全部接受步；
原收据 pinned artifact 摘要全部匹配，owner/ghost 最大差为 0。最终 38 次是 34 个完整轨迹、
2 次 checkpoint 首段和 2 次 restart 尾段；另有 15 次 prepare，不算成求解。初始类似有
16 完整+2 首段+2 尾段；60 次研究均为完整三步轨迹。[汇总](summary.json)区分各来源。

审计没有保存原 J/b/dx，故只从实际程序日志的原 J 残量 norm/rhs 标量重新计算门槛比，
不是离线重新做一次矩阵乘法。部分 checkpoint/resume 文件的哈希首次在审计时记录，
不伪称这些文件已经被原驱动 pin。具体证据限制写在三份独立审计 JSON 中。

## 收敛与成本结论

以下为每例三步、六次 Newton 线性修正的**累计外层迭代数**。网格为 703/2299/5367 DoF，
密度比 1，dt=.02，generalized-alpha rho_infinity=.5，原门槛相同。

| 2-rank 方案 | 703 DoF | 2299 DoF | 5367 DoF |
|---|---:|---:|---:|
| 旧 aggregate + nodal | 83 | 100 | 131 |
| field AMG + nodal | 82 | 99 | 131 |
| field AMG + LSC + FP32 patch | 110 | 123 | 155 |
| field AMG + BFBt + FP32 patch | 94 | 109 | 140 |
| 历史错误边界 PCD + FP32 patch | 825 | 1199 | 1731 |
| 最终 PCD + FP32 patch | 144 | 166 | 225 |

最终 PCD 相对首版有明显改进，但仍比 nodal/BFBt 多迭代。其细/粗网格迭代比 1.5625，
field+nodal 为 1.59756；这些结果只支持所测窗口内的增长记录，不能宣布网格无关。
1-rank 的 field+nodal 为 77/91/108，最终 PCD 为 142/160/225。field 与 aggregate 的
同压力对照没有显示普遍迭代优势，递归物理模态保留本身不等于完整 FSI 的收敛定理。

| 2-rank 密度比 rho_s/rho_f | dt | BFBt 无 patch | BFBt + FP32 patch | 最终 PCD + FP32 patch |
|---|---:|---:|---:|---:|
| 1 | .02 | 103 | 94 | 144 |
| 1 | .005 | 82 | 80 | 215 |
| .1 | .02 | 107 | 95 | 146 |
| .1 | .005 | 89 | 81 | 216 |
| .01 | .02 | 107 | 95 | 146 |
| .01 | .005 | 92 | 81 | 217 |

BFBt 加 patch 在这六组条件下降低 2.44%–11.96% 外层迭代，但小算例的 patch 额外工作
仍使已记录线性时间增加。密度比扫描不等于已量化附加质量数或一般鲁棒性证明。
小网格默认例的新 PCD 无 patch 为 150 次，加 patch 为 161 次，不能宣称 patch 单调改善。

相同 307-DoF 例的 FP64/FP32 因子值数组为 216272/108136 字节，局部数值存储减半；
最终 double/single 的外迭代均为 161（2 rank）、164（1 rank）。该指标不含稀疏 patch、
全局矩阵、基础 PC、索引与工作向量，不代表总内存或带宽减半。未做独占资源上的重复计时，
单次 wall/linear_seconds 只归档，不作普遍加速结论。

两个诊断没有修改默认：旧 PCD 的 64 行辅助块改精确 LU/MUMPS，外迭代仅 442→412，
帮助排除辅助 AMG 精度是主因；旧 FP32 局部门槛 1e-10→1e-6，外迭代仍 400，改进次数
6406→5001，未消除细化成本。两次各一条三步轨迹，独立输出/残量检查通过，单独归档，
不计入上表 20/60/38 三批验收数量。

## 重现与归档

最终受影响检查命令：

```bash
bash build/locked.sh cmake --build build/cloud-3.23.7-release \
  --target eonsim verify_fsi_pressure_operators --parallel 3
bash build/locked.sh ctest --test-dir build/cloud-3.23.7-release \
  -R '^fsi_pressure_operators(_mpi2)?$' --output-on-failure -j1
bash build/locked.sh python tests/verify_fsi_advanced_pc.py \
  --executable build/cloud-3.23.7-release/eonsim \
  --mpiexec .cloud/petsc-3.23.7/bin/mpiexec \
  --work build/fsi-advanced/pcd-fix-19cd26f/physical \
  --build-source 19cd26f2af9b02859fac28ca8f662c29c20d47f1 \
  --study --modes pcd_field pcd_vanka_double pcd_vanka_single
```

`--sections scaling coupling` 是前一轮 60 次研究入口；不指定选项仍执行默认+RCR 组合。
`--modes` 仅过滤候选，所有选择的 section 必须至少保留一个候选，直接参考始终强制保留。
完整逐条命令、源/驱动/二进制/输入/分区摘要与失败都保留于 [evidence.tar.xz](evidence.tar.xz)；归档内部
相对路径从仓库根开始，可解压恢复到 `build/fsi-advanced/`。ELF、静态库及负控对象未放入
公开 raw 包，其摘要和构建/链接命令已保留。[archive-manifest.json](archive-manifest.json) 与 [archive-integrity.json](archive-integrity.json)
记录全部成员与重读校验；独立解析器的初始版和最终版随本目录保存。

跨源码 PCD 对照保留 HDF5 容器原始 SHA 差异，并另做完整数据/类型/属性语义比较；
不能因容器字节不同就说分区改变，也不能抹去该差异。对照收据为 `pcd-comparison.json`。

## 远端检查

最终生产源码 [run 45787454655](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45787454655)
实际完成 **85/85 Release 选测、54/54 Python unittest**。85 个测试无失败/错误/跳过/禁用，
receipt 的 executed=covered=85、reused=0；inventory 中另外30项未选，不是运行时skip。
Python五组为26+6+6+3+13，均OK；选择器测试故意输出的失败XML和run10复用是负例，不是
本次CI的失败或复用。Debug与旧PETSc两个手动job按策略未执行，不混入85项计数。

CI使用合并预览 `121e54bb77f05ea4f9c7c72bae5459a0451f74a6`，其 tree
`4a5584bca52b05de1594ef38758987df84e66686` 与19cd源码完全相同。源码选择、Release、
Record incremental evidence和网站Build VitePress均通过。三个官方artifact ZIP摘要均核实，
日志/plan/receipt及独立审核分别保存在 [source-ci.json](source-ci.json)、
[source-ci.receipt.json](source-ci.receipt.json)、[source-ci.audit.json](source-ci.audit.json) 和 [source-ci.tar.xz](source-ci.tar.xz)。
CI advanced_fsi_pc是85项CTest中的一项，内部执行20次求解、3次prepare，确认54个接受步、117条原Jacobian真实残量。CI只上传log/results，不把未上传的VTU/CSV/HDF5说成已离线重读。
本地完整原件审计提供前述独立字段验证。

前三个被新head取消的运行分别为45783981224、45785208181、45785692936，权威状态记录在
[source-ci.superseded.json](source-ci.superseded.json)，不计为通过。最终文档head四项必需
检查与锁定head的squash合并状态以GitHub权威记录为准；文档证据复用不算重新执行数值测试。
没有降低分支保护、跳过CI或绕过审批。
