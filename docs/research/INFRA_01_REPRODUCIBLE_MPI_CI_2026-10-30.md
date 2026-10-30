# INFRA-01：云端恢复、MPI失败与核心CI

日期：2026-10-30（Asia/Shanghai）。基线 `38a5e516ffe129d1b70c7c1bd8365deb5ded101a`（PR #21已合并）。
工程量估计14–18小时；本报告不将估计当作实际耗时。全部本轮构建和执行位于远程Linux云环境，未使用历史WSL或用户电脑。

证据时间范围：以下运行记录来自原 INFRA-01 分支的开发会话。2026-10-30 后续分支整合会话遵循用户“不编译”要求，只读取已有证据并做静态/脚本检查；其修改与未执行的验证见文末，不继承原分支的通过状态。

## 基线与可恢复环境

已有Debug/Release presets、PETSc/BLAS provider、34项CTest及HPC-02 COO实现，均复用；本任务增加runtime MPI预检后为35项。历史诊断的26项及B5的20项是各自提交时的数量，不代表当前注册数。
用户指定的 `docs/architecture/MULTIPHYSICS_HPC_DESIGN_PRINCIPLES.md` 不存在，实际入口为仓库根目录同名文档。

本轮云机Debian13、CPU quota=400000/100000（4CPU），memory.max=34359738368（32GiB）。
工作区约32GiB overlay，临时目录约17GiB；运行期间没有扩展为多节点或大规模验证。
主工具链GCC15.3/OpenMPI5.0.8/PETSc3.23.7；兼容组合GCC12.4/OpenMPI4.1.6/PETSc3.19.6。
所有包URL、build和SHA256见[锁清单](../../environments/README.md)。两者均real/double/32位PetscInt、优化PETSc。

恢复入口使用固定micromamba二进制及显式锁，没有每次求解最新版依赖。
主锁在新目录 `/tmp/infra-pristine` 恢复，且全新构建 `build/cloud-3.23.7-*`；随后显式设置CONDA_PKGS_DIRS排除用户级后备缓存，在唯一新目录 `/tmp/eonsim-cold-I3bOY2` 及独立检出 `/tmp/infra-clean-checkout` 再验证。
独立检出c07f94a干净恢复/构建后7/7通过；重复restore使用已下载包，再构建/测试7/7通过。没有依赖旧 `/workspace/.eonsim-tools` 才能运行的提交内容。
预检检查锁元数据、编译器/MPI路径、实际动态库前缀、标量类型/位宽及两rank求和；证据包含PETSc配置文件。

旧OpenMPI内置hwloc在新CPU探测时除零，关闭x86 CPUID组件后Linux拓扑可用；受限容器的CMA系统调用不支持另以vader普通共享内存路径处理。这是启动层适配，与下面PETSc控制流缺陷分开记录。

## PETSc 3.19.6 超时根因

将未修改main用git archive展开到独立目录，在锁定3.19.6环境构建 `verify_solver_failures`。
原 `solver_failures_mpi` 保持60秒超时，实际60.07秒失败，最后停在局部PC故障阶段。
给同一基线仅加入rank/reason打印，最后两条为rank0 reason=4、rank1 reason=-11。

[独立最小复现](reproductions/petsc319-preonly.cpp)只创建2×2对角矩阵：rank0对角1，rank1对角0，
PREONLY/BJACOBI＋局部LU，未使用EONSim或SNES。两rank的postsolve分别观察：

```text
postsolve rank=0 ksp_reason=4
returned rank=0 error=0
postsolve rank=1 ksp_reason=-11
returned rank=1 error=0
```

从仓库恢复兼容环境并执行：

```bash
scripts/cloud/restore.sh 3.19.6
export MAMBA_ROOT_PREFIX="$PWD/.cloud/mamba"
eval "$(.cloud/micromamba shell hook -s bash)"
micromamba activate "$PWD/.cloud/petsc-3.19.6"
mpicxx docs/research/reproductions/petsc319-preonly.cpp $(pkg-config --cflags --libs PETSc) -o /tmp/preonly-repro
HWLOC_COMPONENTS=-x86 OMPI_MCA_btl_vader_single_copy_mechanism=none \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout --kill-after=3 15 mpiexec -n 2 /tmp/preonly-repro
```

上游[3.19.6 PREONLY](https://github.com/petsc/petsc/blob/v3.19.6/src/ksp/ksp/impls/preonly/preonly.c#L22)
读取rank-local PC失败并注明可能只有部分rank设置原因码。
[3.19.6 KSP接口](https://github.com/petsc/petsc/blob/v3.19.6/src/ksp/ksp/interface/itfunc.c#L939)
在返回SNES前调用postsolve；EONSim原linear_end在reason正时执行MatMult/VecNorm，负时跳过。
因此rank0进入collective、rank1跳过；即使关闭诊断，旧[SNESCheckKSPSolve](https://github.com/petsc/petsc/blob/v3.19.6/include/petsc/private/snesimpl.h#L321)也按本地reason分支。
[3.20.0 PREONLY](https://github.com/petsc/petsc/blob/v3.20.0/src/ksp/ksp/impls/preonly/preonly.c#L26)已加入PCReduceFailedReason，支持本次<3.20适配边界。

修复在顶层KSP postsolve、诊断和SNES分支之前共同归约 `PCFailedReason != PC_NOERROR`。
失败时所有rank返回PETSC_ERR_NOT_CONVERGED，由NonlinearSystem抛线性求解异常。
布尔标志与原始本地原因分开，避免 `PC_SETUP_ERROR=-1` 被MAX枚举吞掉。
诊断不做PC setup或新的collective；报告rank、phase、PETSc/SNES/KSP/PC原因及已有子树。

这属于有上游证据的应用边界适配，不改变方程/停止条件，不删除失败测试，不延长超时，也不新增无条件MPI_Abort。
验证限于正常顶层KSPSolve与本项目配置，不宣称修复任意PETSc提前异常、用户error_if_not_converged、transpose/MatSolve或所有嵌套PC。

## 完整验证进一步发现的问题

主环境首轮完整测试暴露COO失败后恢复错误：`VecGetArray: Object is in wrong state`。
[PETSc3.23.7 SNESComputeJacobian](https://github.com/petsc/petsc/blob/v3.23.7/src/snes/interface/snes.c#L2718)
在callback前VecLockReadPush，callback返回错误时可早退而未执行Pop；这与旧版PC reason缺陷不同。
修复在已共同传播的callback错误返回后Duplicate并交换trial Vec，保持accepted输入及COO矩阵/图；
旧Vec仍按SNES/Mat引用生命周期保留，不手动更改PETSc内部锁，下次求解重新覆盖owned并更新ghost。
新增普通装配fatal Jacobian恢复回归，原COO回归继续检查1/2/4rank远程贡献和同对象恢复。

另外，checkpoint测试rank0可能在其他rank尚未读完时写入故意损坏的current，导致 `Bad current pointer format`。
在破坏阶段前增加测试barrier，符合“读取期间指针稳定”的既有契约；未改变checkpoint生产实现。

## 验证记录与CI

完整命令及证据目录见[构建说明](../development/BUILD_AND_VALIDATION.md)。本轮使用每rank单线程、按配额最多4编译进程、CTest逐项调度；4rank测试正常执行。

- 两环境针对性选择 `mpi-failure` 已各7/7通过，含runtime、失败分类、接受状态和COO的1/2rank检查。
- 失败回归区分预期catch后成功、应用错误退出和超时；PC三种诊断模式、初态零迭代、accepted不变及恢复解0.1有断言。
- 主环境Debug完整35/35通过（b4d7c5a），474.17秒；Release完整35/35通过（d3f69d1），409.08秒；均无失败或跳过。COO实际字段最大差均约3.31e-12。Release测试开始时工作区包含文档/入口修改，核心源码与该提交相同；最终干净检出的分支CI另行验收。
- Poisson L2/H1阶2/1，仿射L2误差1.060e-11，1/2rank最大差3.553e-15；原流体、固体、刚体/弹性FSI、checkpoint/restart及COO全部由现有数值断言验收。
- 真实两rank故障程序的2秒超时清理实验确认CTest非零并归类Timeout，子进程全部终止并reap；这是刻意失败的基础设施负例，不纳入数值套件通过数量。
- Linux subreaper及忽略TERM/多层后代检查已执行；清理仅针对本次验证的后代，不处理其它作业。

CI仅缓存包，键含锁/平台/编译器/ABI。JUnit和summary检查非预期skip、空测试集和不完整结果，Python优化被拒绝。
失败仍上传日志；当前云代理不允许GitHub artifact重定向的Azure Blob域，下载受限不等于CI未产生artifact。
[分支CI 41060786421](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41060786421)在d3f69d1三个任务全部成功，Debug/Release及兼容环境均产生artifact。
[精简机器证据](data/infra-01-2026-10-30/validation-summary.json)保留本机提交/工作区状态、资源和逐测试结果；完整原始日志由CI artifact提供，保留14天。5745fd3 的 [CI 41063030121](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41063030121) 随后三个 job 全部成功，详见精简证据中的 final_pre_pr_ci。本分支曾创建 [PR #22](https://github.com/saitoasukakawaii/EONSim-new/pull/22)；本次依用户要求整合，合并提交的验证范围见文末。

## 审查与边界

独立源码审查发现并修正负PC枚举、嵌套cgroup配额和超时子进程问题；随后对trial Vec引用、checkpoint同步和CI入口复核，无剩余源码阻塞。最终运行结果仍独立验收。

主锁要求Linux x86-64-v3，资源自动探测面向cgroup v2；不声明任意硬件/外部MPI兼容。
全部数值基线仍为小网格、1/2/4rank，同分区重启。没有新物理模型、FSI/ALE COO、缩放、GPU、AMR或性能收益声明；没有新的性能基准。

CI适配补充：OpenMPI5的PRRTE不读取旧 `OMPI_MCA_rmaps_base_oversubscribe`。
本机显式 `--host localhost:2 -n 4 /bin/hostname` 在旧变量下退出1并报告槽位不足，
使用 `PRTE_MCA_rmaps_default_mapping_policy=:oversubscribe` 后4进程正常返回。
入口保留4.x变量并增加5.x变量及4rank预检，不减少任何测试的rank数。

PR 后 1497137 的 [Release 作业](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41064780711/job/124093224914) 在 MPI 预检发生 UCX/Azure MANA 的 UD 队列创建错误；787372e 将单机入口固定为 ob1 与 self/shared-memory/TCP。OpenMPI 4 使用 vader，5 使用 sm，符合 [上游组件命名与选择说明](https://docs.open-mpi.org/en/v5.0.x/tuning-apps/networking/shared-memory.html)。该修复只限定云端单机验证入口，不声明 RDMA/多节点性能；本次没有重新执行 MPI，不能把 5745fd3 的成功结果覆盖到该增量。

## 后续合并审查（不编译）

集成范围包括源分支 `787372e746a3523194a8139bc36c70cee9e21f13` 的环境隔离、单机传输适配及证据补充。以下修正新增于合并审查，不在上文原分支 CI 的验证范围内：

- `verify_runtime` 检查固定 OpenMPI/int32 ABI，不能随普通 BUILD_TESTING 无条件启用。新增默认 OFF 的 `EONSIM_VERIFY_LOCKED_RUNTIME`；仅云入口显式开启，保留原锁定环境的探针和数值测试。
- JUnit 必须与 CTest inventory 的测试名逐一对应；拒绝重复、未知、缺失结果及无效时长，将 `error` 与 `failure` 均归为失败，跳过不能算成功。6 项纯 Python 合成证据回归通过；没有运行 CTest 或 MPI。
- 对照 CMake 修正 Doxygen target 文档，并核实 PETSc 3.20 PREONLY 的上游失败归约与 3.23.7 SNES 的锁作用域。

最终集成提交的构建、运行时 ABI、数值回归、恢复脚本执行与性能均未验证；本次提交使用 `[skip ci]` 避免 push 触发构建。详见 [分支整合记录](../development/BRANCH_INTEGRATION_2026-10-30.md)。
