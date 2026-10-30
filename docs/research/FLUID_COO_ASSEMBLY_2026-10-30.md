# HPC-02：独立流体固定 COO Jacobian 装配

日期：2026-10-30（Asia/Shanghai）。基线 `24eae62`，实现及测量脚本 `ceea57d`。
用户要求依据规划设计一个 5 小时以上的任务并完成后才创建 PR；领取范围与预计 7–9 小时
工程工作量已登记在任务队列。该估计不是实际耗时记录。

## 问题、实现与边界

HPC-01D/E 已分离独立流体 kernel 与插入成本，但每个 Jacobian 仍逐单元调用
MatSetValues。当前 fixed-mesh Tet4 的代数编号和图在时间步之间不变，因此新增显式
`-fluid_coo`，在同一 NonlinearSystem 中缓存贡献图，仅更新每单元 16×16 的切线数值。
默认路径保留。残量、边界载荷、材料、稳定化 tau、BE、停止准则、约束/反力均未改变。
图改变必须重建系统；FSI、移动 ALE、固体和其它入口明确拒绝该流体选项。

`set_jacobian_coo` 共同检查索引及长度，补齐 owned 对角项，保留原始贡献次序；PETSc
处理重复坐标与远程贡献。回调只计算/打包本地切线。错误同步在 collective COO 更新之前，
失败时排空已插入的 Vec stash，拒绝发布部分矩阵。下次评价清零完整缓冲并用
INSERT_VALUES 覆盖，所以旧 off-diagonal 和约束对角不会混入新算子。
细节与计时口径见 [L2 契约](../architecture/L2_DISCRETIZATION_AND_OPERATORS.md)。

## 构建与数值证据

验证环境为 Ubuntu 24.04 / WSL2、GCC 13.3、PETSc 3.19.6（real-double / 32-bit PetscInt）、
OpenMPI 4.1.6、OpenBLAS，使用 SuperLU_DIST 直接参考及 Schur/GAMG。
这是本次实际验证环境，不沿用既有 Cloud 的 PETSc 3.23.7 验证声明。

```sh
cmake --preset release -DBUILD_TESTING=ON -DMPIEXEC_EXECUTABLE=/usr/bin/mpiexec
cmake --build --preset release --parallel 4
ctest --preset release -R 'coo_jacobian|fluid_coo_verification|nonlinear_acceptance|solver_failures' --output-on-failure
cmake --preset debug -DBUILD_TESTING=ON -DMPIEXEC_EXECUTABLE=/usr/bin/mpiexec
cmake --build --preset debug --parallel 4
ctest --preset debug -R 'coo_jacobian|fluid_coo_verification|nonlinear_acceptance' --output-on-failure
```

- Debug：6/6 通过；Release：上述 8 项中 7 项通过，1 项已有 MPI 故障测试超时，见下节。
- 新 COO 数值回归覆盖 1/2/4 rank：重复/远程行、空贡献 rank、缺省约束对角、切换约束和
  新算子的零项、已知解及反力、局部可恢复/不可恢复错误、同对象恢复、首次 solve 后禁止改图。
- 真实案例包括 Stokes、steady、transient、旋转通道、牵引出口、双黏度 Couette、零均压。
  每例 1/2/4 rank 对照原装配；旋转通道/瞬态另对照 Schur 的真实线性残量；瞬态验证
  原装配↔COO checkpoint 双向切换及未收敛无输出。每种构建执行 87 个命令，最大字段差
  `5.190625707029994e-12`（含速度、压力和动量反力）。两种构建各自与同模式原路径比较；
  未额外进行 Debug 与 Release 间的逐点字段比较。
- 原有 nonlinear_acceptance 的 1/2 rank 检查仍通过。未运行完整 CTest，也未声称全部测试通过。
- 共用求解器的额外 Release 检查 `schur_verification|time_retry_verification|fluid_element_report|profile_log_validation`
  为 4/4 通过，覆盖原有 FSI、真实缩步、计时开关及日志校验；见 [日志](data/fluid-coo-2026-10-30/shared-regression.log)。
- 独立只读 deep review 对实现提交 `ceea57d` 给出 PASS，无阻塞发现；[记录](data/fluid-coo-2026-10-30/review.json)
  同时保留未直接测试零 owned 行和极限计数的证据边界。后续仅有文档与测量元数据修订。

原始构建/验证日志及逐命令记录见 [data/fluid-coo-2026-10-30](data/fluid-coo-2026-10-30)。

### 已有故障测试限制

`solver_failures_mpi` 在本机 PETSc 3.19.6 下 60 秒超时。将未修改的主分支
`24eae624ee93b3e1989312e1b1b273217571310f` 用 git archive 独立展开并构建同一目标，
得到相同超时和最后输出；[独立构建日志](data/fluid-coo-2026-10-30/baseline-petsc319-timeout.log)
保留证据。该测试未被删除、跳过注册或放宽时限，本任务不修改其失败处理逻辑。
证据只证明此问题在该环境的原基线已存在，尚未确定根因或证明其它 PETSc 版本不存在问题。
COO 自身的 MPI callback 失败与恢复测试全部通过；不能将此代替该旧测试的通过结果。

## Release 配对测量协议

```sh
python3 scripts/benchmark_fluid_coo.py --executable build/release/eonsim \
  --mpiexec /usr/bin/mpiexec --work build/fluid-coo-benchmark --repeats 3
```

work 必须不存在。固定 transient 通道：rho=mu=1、pressure_drop=1、dt=.05、10 步、
ramp_time=.1；SNES rtol=1e-10、atol=1e-12、max_it=30，PREONLY/LU SuperLU_DIST。
两档规则网格 4³/8³：384/3072 Tet4、500/2916 DoF。每档 1/2/4 rank，双方始终打开
solver_report，不开 linear_report 或 fluid_element_report；只切换 fluid_coo。
每配置两种方式各预热一次，再做 3 对交替顺序测量；共 36 个计量运行、12 个预热、6 个预处理。

机器为 i9-12900K，WSL 可见 24 逻辑 CPU、约 32 GiB RAM，所有 rank 的
OMP/OPENBLAS/MKL 线程数均固定 1。源/构建/输出位于 Windows 挂载盘；未独占主机、未手动
固定核心，不作多节点或稳健统计显著性声明。raw logs、命令、网格哈希、环境、CMakeCache、
可执行哈希、逐步数据和每对变化保存在 [results.json](data/fluid-coo-2026-10-30/results.json)。

48 次物理运行全部通过既定日志与字段验收；36 个计量运行的逐步 SNES/KSP 迭代轨迹相同。
包含预热的同模式/同 rank/跨 rank 最大字段差均不超过 `6.661338147750939e-16`。
每 rank 每次进程只输出一个 COO plan，10 步复用；未在每步重新建图。

Windows checkout 的 CRLF 使原始 WSL Git status 将多个未改内容文件报告为 modified。
原始 JSON 保留原样；[source-provenance.json](data/fluid-coo-2026-10-30/source-provenance.json)
逐文件验证 58 个 src/include/cmake/CMakeLists.txt 内容归一化后与测量提交完全相同，并核对
可执行哈希。后续脚本仅把 status 命令改为临时 `-c core.autocrlf=true`，不改变实验或全局设置。

### 统计结果

下表绝对时间为各模式 3 次运行的中位数。solve/assembly 为 10 个逐步 rank-max 时间之和，
不是整个运行中单个 rank 累计时间的最大值。变化为每对 `T_COO/T_old−1` 的中位数及范围，
不是绝对中位数之比。wall 包含 MPI 启动、输入/输出、诊断及一次性 COO 准备；因此 solve
下降不等于端到端同比下降，阶段之间也不可相加。

| 网格 / DoF | ranks | assembly ms 旧/COO | solve 配对变化 % [min,max] | wall 配对变化 % [min,max] |
|---|---:|---:|---:|---:|
| 4³ / 500 | 1 | 31.66/14.19 | -43.75 [-48.71, -26.80] | -10.95 [-17.84, 0.14] |
| 4³ / 500 | 2 | 25.05/10.33 | -18.05 [-30.93, -7.90] | -0.03 [-10.66, 12.02] |
| 4³ / 500 | 4 | 21.69/8.61 | -24.67 [-32.96, -21.89] | -0.01 [-0.07, 0.00] |
| 8³ / 2916 | 1 | 230.87/124.47 | -12.66 [-17.50, -11.88] | -4.33 [-8.24, 0.15] |
| 8³ / 2916 | 2 | 165.39/86.98 | -11.40 [-12.13, -2.47] | -4.93 [-4.93, -0.13] |
| 8³ / 2916 | 4 | 117.48/61.64 | -8.16 [-22.94, -7.03] | -5.28 [-10.31, 0.06] |

| 网格 | ranks | 首步 solve ms 旧/COO | 后续单步 mean ms 旧/COO | 峰值 rank-max MiB 旧/COO | COO 准备 rank-max ms |
|---|---:|---:|---:|---:|---:|
| 4³ | 1 | 17.40/9.89 | 7.55/4.72 | 50.19/51.98 | 4.56 |
| 4³ | 2 | 12.63/9.25 | 5.43/4.17 | 50.34/52.09 | 3.31 |
| 4³ | 4 | 11.51/9.17 | 4.92/3.63 | 48.52/49.71 | 2.67 |
| 8³ | 1 | 137.97/123.37 | 74.13/63.53 | 89.64/102.74 | 45.09 |
| 8³ | 2 | 106.83/100.83 | 56.81/51.03 | 78.77/86.91 | 27.17 |
| 8³ | 4 | 98.83/81.68 | 44.73/41.76 | 66.29/71.12 | 19.82 |


后续单步先对一运行的第 2–10 步求均值，再对 3 个运行取中位数；RSS 是进程高水位的
rank 最大值。它包含求解器及临时图准备，不能将差值全部归因于数值缓冲。
8³ 单 rank 持久 COO 数值缓冲为 6,314,784 bytes，另有 PETSc 图/通信存储及准备索引。

## 结论和未覆盖范围

在这组测量中，装配配对耗时中位数下降约 45–62%，solve 下降约 8–44%；端到端 wall
中位变化约 -11% 到 0%，多组范围跨越零。COO 的准备和内存成本实际存在，不能只报告
局部插入加速。默认仍保留原装配，按问题规模显式选择新路径；不据此推广网格无关性能。
尚未覆盖 FSI/ALE COO、残量 COO、GPU、多节点、大网格以及其它 PETSc 版本。

## 依据

- [HPC-01E 插入测量](FLUID_ELEMENT_OVERHEAD_2026-10-30.md)。
- [PETSc MatSetPreallocationCOO](https://petsc.org/release/manualpages/Mat/MatSetPreallocationCOO/)：图准备、重复/远程坐标与索引数组可被修改。
- [PETSc MatSetValuesCOO](https://petsc.org/release/manualpages/Mat/MatSetValuesCOO/)：重复值先求和、INSERT_VALUES 覆盖及自动装配。
- [实现提交](https://github.com/saitoasukakawaii/EONSim-new/commit/ceea57d568db08c5181122cea66f5b9458c6200c)：非线性驱动、流体接线、回归与测量脚本。
