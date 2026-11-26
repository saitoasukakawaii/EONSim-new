# RCR-PC-01：端口 Schur、低秩响应与基础 AMG 组合

交付 [PR #58](https://github.com/saitoasukakawaii/EONSim-new/pull/58)，基线
`b731d4713ab8428e02fb52af6547e1aa3097eca0`（#57）。生产与验证驱动分别在远端
核对完整 tree 后才构建、运行；后续文档和证据提交不算新的数值执行。

## 源码与执行顺序

| 阶段 | 远端 commit / tree | 随后的实际执行 |
| --- | --- | --- |
| 完成首版生产与测试 | `94046b1a1fc1182937dd170a5777f2a7e6c5ba88` / `a1eef79f61858bf74daf8ec2bf0eedf9dc648c0f` | Release 增量构建；32 项 Python；7 项定向 CTest，4 通过、3 失败 |
| 修复失效缓存的 PETSc failure 协议 | `28e6d54701abced040752aff70b69d29b35f1d01` / `abe936f13dc408c5c14fefbb5197498d655cc1d9` | 只重建 eonsim/verify_rcr_port；受影响的 3 项代数测试通过；首轮 FSI 在重启步数断言失败 |
| 对齐变步长计划与物理终点 | `ad08887f8b357ef16e6a6b49b89d968f531f8053` / `d537b74017181bdc279e97da96db6caabf271b73` | 仅改 Python 驱动，不重编译；只重跑 rcr_port_fsi，1/1 通过 |

最终生产源码为 `28e6d54`，最终 FSI 驱动为 `ad08887`。后者与前者的 `src/`、
`include/`、`CMakeLists.txt` 内容完全一致。[最终来源记录](provenance-final.json)
保存当前源码、依赖文件、二进制摘要及两次构建日志摘要；首版 provenance 保留在 raw
归档中。当前 eonsim ELF SHA256 为
`71d4c649fe60f834ba98782069bfaa9e26d9c7df651384170e0c67b589008b7b`。
来源记录是在验证后采集，明确记录当时文档工作区状态，不伪称全部工作区干净。

本地日志的 CTest 时间戳保留运行环境的 PST 标签；Git 和 provenance 使用 UTC。
这些操作均发生于 2026-11-26 UTC / Asia-Shanghai，原日志未改写。

## 实现范围

完整约束后 Jacobian 分块为 `J=[A,U;V,D]`。A 是去除端口压力后的所有 bulk 自由度，
不是仅速度块。保存实际 U/V，允许移动出口几何列及只替换约束行导致的非转置关系。
令 H 为原语义 bulk PC 的一次作用，缓存 `Y=HU`、`S=D-VY`，每次应用计算
`z=H r_bulk`、`q=S^-1(r_port-Vz)`、`x_bulk=z-Yq`。
单端口对应 Sherman–Morrison 的标量小系统，多端口对应 Woodbury 响应。
H=A⁻¹ 时才是原 J 的精确块逆；固定可逆线性 H 对应将 A 替换为 H⁻¹ 的块逆。
含残量相关内层求解时是响应近似，外层保留 FGMRES 和原 J 验收。

| 用户要求 | 本次实现 |
| --- | --- |
| P0 RCR-aware Port Schur | semantic boundary-pressure 识别，根 PCSHELL 包裹既有 bulk recipe，完整原 J 不变 |
| P0 单出口修正 | 一列缓存响应及 1×1 Schur，保留正确符号和量纲 |
| P0 多出口低秩修正 | k 列响应、k×k 行列均衡及带主元 LU，不假设 U/V 对偶 |
| P1 基础速度块组合 | 原 split/coupled/GAMG/twolevel/aggregate 保持可组合；新增实际 PCHYPRE/BoomerAMG 路径 |
| P1 MPI 合并归约 | 每次 apply 一次出口 Allreduce，刷新全部 k² 投影也合并为一次；错误标志同批归约 |
| P1 缓存与自适应 | 固定索引/图/缓冲复用；bulk、U/V/D、响应和小 Schur 随同一 PcSchurUpdates generation 发布 |

以上归约计数只覆盖新增端口层，不包含基础 AMG/KSP、矩阵操作或既有自适应监测内部通信。
每代构建 k 个响应列，每次 apply 仅调用一次 H；应用中不重新分配全局场或逐出口归约。
缓存数值不写入 checkpoint；恢复从物理状态重新构建。默认旧预条件器不变，新路径显式开启。

```text
-pc_recipe hybrid -pc_plan_rcr_ports true
-pc_plan_schur_approx nodal
-pc_plan_velocity_solver gamg
-ksp_type fgmres
```

将 `gamg` 改成 `boomeramg` 使用 hypre。bulk PETSc 前缀在根 KSP 原前缀后追加 `rcr_bulk_`，再接原子树前缀。
自适应开关和例子见[完整使用与数学说明](../../../development/RCR_PORT_PRECONDITIONER.md)。

## 本地构建与测试

PETSc 3.23.7（real double、hypre 2.32.0）、Release，复用锁定环境和构建目录。
依赖 OMP/BLAS/MKL 各一线程，MPI 测试串行调度，使用 1/2/4 rank；单节点共享容器。
/proc 报告 AMD EPYC 9V74，实际 affinity 与内存记录在 provenance；不推断独占硬件。
没有本地全量、Debug、旧 PETSc、多节点或百万自由度执行。

执行命令的要点如下，完整路径和输出保留在 CTest LastTest 日志：

```bash
export PATH="$PWD/.cloud/petsc-3.23.7/bin:$PATH"
export LD_LIBRARY_PATH="$PWD/.cloud/petsc-3.23.7/lib:${LD_LIBRARY_PATH:-}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1
export OMPI_MCA_rmaps_base_oversubscribe=1
export PRTE_MCA_rmaps_default_mapping_policy=:oversubscribe
cmake --build build/cloud-3.23.7-release \
  --target eonsim verify_rcr_port verify_pc_plan verify_adaptive_pc --parallel 3
python3 -m unittest tests.test_ci_selection tests.test_cloud_evidence
ctest --test-dir build/cloud-3.23.7-release \
  -R '^(pc_rcr_port_mpi[124]|pc_plan_mpi[124]|adaptive_pc_mpi2)$' \
  --output-on-failure -j1
# 28e6d54 同步后只重建受影响目标，并重跑首次失败的三项：
cmake --build build/cloud-3.23.7-release --target eonsim verify_rcr_port --parallel 3
ctest --test-dir build/cloud-3.23.7-release -R '^pc_rcr_port_mpi[124]$' \
  --output-on-failure -j1
# ad08887 同步后仅执行受影响的 FSI 驱动：
ctest --test-dir build/cloud-3.23.7-release -R '^rcr_port_fsi$' \
  --output-on-failure --output-junit "$PWD/build/rcr-port/fsi-ad08887.xml" -j1
```

32/32 Python 在首版通过。原 `pc_plan_mpi1/2/4` 和 `adaptive_pc_mpi2` 四项在
`94046b1` 通过，后续不受影响而复用，未重复运行。新 `pc_rcr_port_mpi1/2/4`
在修复源 `28e6d54` 实际 3/3 通过。最终 FSI 在 `ad08887` 实际 1/1 通过。
这给出八项相关 CTest 的有效本地覆盖，但不是八项都在最终提交重新执行。

代数测试独立以 long double 全矩阵消元对照实际 PCApply，覆盖 1/2/3 端口、非对称
U/V、类似网格的耦合列、交错编号、只有端口的 rank、完全空 rank、后续阶段 LU 换行、
20 个数量级的单位尺度差，以及非零→零→非零数值刷新。原作用门槛为
`2e-12*(1+|expected|)`，原矩阵残差门槛为 `3e-12*(1+||rhs||)`。
日志只打印通过而不打印这些误差的实测最大值，因此不推定更小数值。
奇异/NaN、失败后恢复、缓存次数/归约次数及实际 NonlinearSystem 自适应路径同样覆盖。

### 两次失败及闭环

1. 首版三项新代数测试在故障负控后失败：not-ready 的 PCApply 用 PetscCheck 提前返回，
   PETSc 没有机会释放 RHS 的 read lock，后续 NaN 注入 VecSet 被拒绝。修复通过
   `PC_SUBPC_ERROR` 和 `PETSC_INFINITY` 哨兵输出报告失败，并正常返回 PETSc 控制流；外层 KSP 仍按失败
   处理。锁定 PETSc 中此宏是有限哨兵，失败由 PC failure 状态表达。完整数值刷新成功
   才清除 failure/publish ready，代数三项复验通过。
2. 首轮 FSI 的四个计划步长度和为 .056，但名义 `dt*steps=.06`，TimeStepper 正确追加
   .004 步，重启后有三步而驱动期望两步。测试将名义 dt 设为计划步长均值，明确终点
   .056/.047，并新增时间和 accepted_dt 对齐断言；没有改生产时间推进或误差门槛。
   失败原始运行和最终通过运行分别归档。

## 真实移动出口结果及独立复核

13 次求解均成功，共 43 个接受时间步。单出口为 generalized-alpha 四个变步长，包含
直接参考、未包装 GAMG、split/GAMG/BoomerAMG、adaptive、两步 checkpoint 和跨基础
预条件器续算；多出口为 BE 三个变步长、两个相反法向和不同阻抗的移动出口，包含直接
参考、未包装 GAMG 与三种包装基础块。单出口 350 DoF，双出口 1020 DoF。

| 指标 | 最终本地实测 |
| --- | ---: |
| 最大最终场绝对差（对直接参考或连续续算参考） | 7.57779949900339e-11 |
| 最大 RCR 历史绝对差 | 2.1582735598713043e-12 |
| 最大离散电路缺陷（含未包装参考） | 1.6954840309502117e-13 |
| 实际记录的真实线性残差样本 | 96 |
| 最大 `||J dx-b|| / max(1e-12,1e-9*||b||)` | 0.09972517246553696 |
| 总 Newton 迭代 | 114（其中直接参考的18次没有额外线性残差日志） |
| solver_node 记录 | 798，KSP reason 全部 >0、PC failure 全部为0 |
| adaptive 完整 Jacobian / PC refresh / PC reuse | 12 / 8 / 4 |

独立复核不复跑求解、不调用生产因子，直接重读 VTU、CSV、MSH、日志。
它另外重积了出口面积、有向通量和 TET4 体积，最大缺陷分别为约
`5.55e-17`、`1.08e-19`、`2.22e-16`，最小已记录变形 J 为 `0.9961542`。
全部断言和输入摘要见 [FSI 独立审计](independent-fsi-audit.json)；
[代数审计](independent-algebra-audit.json)明确复用与实际重跑的区别。
直接参考未启用 solver_report/linear_report，不能将其18次 Newton 迭代写成额外观测的真残差。

## 性能范围

| 同一算例、2 rank | 未包装 GAMG 外层迭代 | 包装 GAMG 外层迭代 | 包装 BoomerAMG 外层迭代 |
| --- | ---: | ---: | ---: |
| 单出口，4 步 | 145 | 144 | 147 |
| 双出口，3 步 | 53 | 53 | 55 |

[metrics.json](metrics.json)同时保留线性、Schur setup 和全求解耗时；它们只是短小正确性
案例的一次样本，没有预热/重复配对，不用于稳健 wall speedup 推断。能确定的是端口层
合并归约、每代 k 响应缓存和真实 8/4 刷新复用机制；不能推出网格无关 AMG、多节点强弱
扩展或任意参数下优于原 PC。新路径保持显式可选。

## 原件、归档与远程检查

[evidence.tar.xz](evidence.tar.xz)包含 683 个普通文件：最终 FSI372、首次失败 FSI294、
日志/XML16、首版来源记录1。原始总量8,321,522 B，压缩354,384 B；SHA256
`50e69135f587a94235e1973d8cb90f5ab305e7f3501f53faf161d2981765628c`。
[manifest](archive-manifest.json)记录每个原件和归档路径及摘要；
[integrity](archive-integrity.json)从压缩包逐项读取并核对全部683项，原件保留且未变化。
最终 provenance、两份独立审计及只读审计脚本在压缩包旁边独立保存。

最终源码 [CI 45776829333](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45776829333)
实际选中并执行 **65/65 Release CTest，0 failed / skipped / reused**，以及选测阶段
**54/54 Python**；JUnit、CTest Test.xml、CTest.log、summary 和成功 receipt 五者一致。
CI checkout 的合并预览 commit 为 `cf648a39c3223641898e91983a8ae2f1110179b2`，其 tree
`d537b74017181bdc279e97da96db6caabf271b73` 与源码 head `ad08887` 完全相同。
三个必需 core job（selection、Release、Record incremental evidence）及相应 Website
Build Check 全部成功。手动 Debug / PETSc 3.19.6 两个 job 按配置未执行，不能混算为
这65项中的跳过，也不宣称本轮具备它们的新验证。

[CI 原件与审计](source-ci.json)、[选测](source-ci.selection.json)、
[验收收据](source-ci.receipt.json)、[环境和结果摘要](source-ci.summary.json)分别保留。
官方 artifacts 为 plan `15096278424`、numerics `15097207156`、receipt `15097635900`，
三个 ZIP 实际 SHA256 均与 GitHub digest 匹配。提交的 [source-ci.tar.xz](source-ci.tar.xz)
保留56个必要原件/元数据，191,528 B，SHA256
`20b91d875e12ea9fb3c69b76e55f89f70217141f3334683c9125131c4ecbb849`；
[manifest](source-ci.manifest.json)记录原 ZIP member 到归档路径的对应，
[integrity](source-ci.integrity.json)重开逐项核对全部56项通过。没有将临时签名下载URL或
凭据写入证据。完整数值 ZIP 在本地原件目录保留，提交包只保留本轮必要证据。其中RCR为13份求解
日志和4份准备日志；远程工作流没有上传RCR的CSV/HDF5/metrics.json，完整物理场与
历史由本地冻结的evidence.tar.xz提供，不将远程ZIP称为完整FSI字段档案。

首版 core run `45776194881` 和中间源 run `45776473707` 被后续 head 取代而取消，
不计为通过或失败。后续文档提交通过成功收据复用不受影响证据，不计为再次执行65项。
最终文档 head 的四项必需检查和合并状态以 GitHub 对应记录为准。
