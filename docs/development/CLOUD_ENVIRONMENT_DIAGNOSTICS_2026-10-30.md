# EONSim-new 云端基础设施诊断报告

> 归档说明：本报告记录 2026-10-30 对提交 `29df3e240fe3bb06a63ddd0ac915f21aa8df39c1` 的基础设施检查。其后已同步到 `a2dfb602bd228fc21ea9be2ee187972177833585`，该新提交未在本次检查中重新构建或测试。文中“未提交或推送”描述检查阶段；本文件随后按用户要求归档并推送。原始日志及临时构建保存在检查会话的 `/tmp/eonsim-infra-check/`，未纳入本次提交，也不保证跨会话保留。

检查时间：2026-10-30T15:25:29+08:00（Asia/Shanghai）

范围：仅检查现有环境；未安装/升级软件，未修改系统或项目配置、C++ 源码、设计文档、Git 分支；没有提交或推送。构建产物、诊断 C 程序和原始日志均位于本临时目录。

仓库：/workspace/EONSim-new；HEAD：29df3e240fe3bb06a63ddd0ac915f21aa8df39c1

## 资源及实际限制

- 内核：Linux 146200b616fe 6.18.57 #1 SMP Tue Oct 20 21:56:04 UTC 2026 x86_64 GNU/Linux
- CPU：Intel Xeon Platinum 8573C；x86_64；KVM 虚拟机。lscpu/nproc 可见 5 个逻辑 CPU，cpuset 为 0–4，但 cpu.max=400000/100000，实际持续 CPU 配额为 4 核。不能按 nproc=5 判断可持续算力。
- 内存：memory.max=34359738368，即 32 GiB。free 显示约 33 GiB，但 cgroup 硬限制优先；无活动 swap。memory.high=max，memory.swap.max=max 不代表已有可用交换空间。
- 磁盘：/workspace 位于约 32 GiB overlay 文件系统，检查时约 28 GiB 可用；不是独享容量或持续 I/O 性能保证。/tmp 为约 17 GiB 的临时内存文件系统，临时构建/日志会消耗内存且不应视为持久存储。
- 本次采用编译 --parallel 4、CTest --parallel 2、OMP/OPENBLAS/MKL_NUM_THREADS=1；Debug/Release 顺序运行，避免同时消耗两套测试资源。4 Rank 专项带 PROCESSORS=4，CTest 会等待其他测试退出后运行。
- 原始命令完整输出：uname.txt、lscpu.txt、nproc.txt、memory.txt、disk.txt、cgroup.txt、cgroup-mounts.txt。CPU 配额曾发生节流，属于限额行为；检查前 memory.events 的 OOM/kill 为 0。

## 软件及依赖版本

| 组件 | 激活环境中的版本 |
|---|---|
| cmake | 4.4.5 (`hff7ac6b_0`) |
| gcc | 15.3.0 (`hc6a0c74_7`) |
| gxx | 15.3.0 (`hc6a0c74_7`) |
| hdf5 | 1.14.6 (`mpi_openmpi_h8367ee7_6`) |
| hypre | 2.32.0 (`mpi_openmpi_h398ea61_1`) |
| libblas | 3.11.0 (`11_h4a7cf45_openblas`) |
| liblapack | 3.11.0 (`11_h47877c9_openblas`) |
| libopenblas | 0.3.34 (`openmp_h156ec52_2`) |
| metis | 5.1.0 (`h86e3903_1008`) |
| mumps-mpi | 5.8.1 (`hcd43f66_3`) |
| ninja | 1.13.2 (`h171cf75_1`) |
| openblas | 0.3.34 (`openmp_hd0bf9d2_2`) |
| openmpi | 5.0.8 (`h2fe1745_110`) |
| petsc | 3.23.7 (`real_h5e9295b_0`) |
| python | 3.12.16 (`h5f976f7_0_cpython`) |
| superlu_dist | 9.1.0 (`h3349319_0`) |
| yaml-cpp | 0.8.0 (`h54a6638_1`) |
| Git | 2.52.0（系统 /usr/local/bin/git） |

默认系统 GCC/G++ 为 14.2.0、Python 为 3.12.14、OpenMPI 为 5.0.7，默认 PATH 中没有 CMake/Ninja。这不是激活环境中的依赖缺失；正式开发每个 Bash 会话先执行：

```bash
source /workspace/.eonsim-tools/activate.sh
cd /workspace/EONSim-new
```

激活后 GCC/G++/mpicc/mpicxx 均解析到 /workspace/.eonsim-tools/env。不要混用系统 /usr/bin/mpirun 和该前缀内的 MPI 库。版本和路径完整记录在 system-tools.txt、active-tools.txt、packages.json。

## PETSc、BLAS 与 MPI ABI

- PETSc 3.23.7，shared library，real/double；运行时 sizeof(PetscScalar)=64 bit、sizeof(PetscReal)=64 bit、sizeof(PetscInt)=32 bit。非复数、非 64 位 PetscInt。METIS idx_t 也是 32 bit；EONSim 原始网格 ID 为 64 bit，但代数编号仍受 PETSc 32 bit 限制。
- PETSc 配置 --with-debugging=0；应用 Debug 仍链接优化版 PETSc，不包含 PETSc 自身 Debug 检查。
- PETSc BLASLAPACK_LIB=-llapack -lblas；libblas.so.3、liblapack.so.3 和应用的 libopenblas.so.0 均为同一个 libopenblasp-r0.3.34.so 的符号链接。实际配置：OpenBLAS 0.3.34 DYNAMIC_ARCH USE_OPENMP，当前 CPU 内核选择 Cooperlake；库支持最多 128 线程，但本次限制为 1。
- PETSc 已配置 MPI、HDF5、METIS、ParMETIS、HYPRE、MUMPS、SuperLU、SuperLU_DIST、ScaLAPACK、SuiteSparse；配置存在不等于逐个外部求解器均经过本项目测试。
- MPI 为同一前缀的 OpenMPI 5.0.8；mpicc/mpicxx 使用 conda-forge GCC/G++ 15.3.0。PETSc 构建元数据声明 CC=mpicc、CXX=mpicxx、--with-mpi=1、PETSC_HAVE_OPENMPI；未从元数据确定历史构建时 GCC 的精确版本，因此不声称其与当前编译器版本完全相同。
- 全新 Debug/Release 可执行文件和 PETSc 的 ldd 均加载该前缀下同一个 libmpi.so.40 和兼容的 libstdc++.so.6，无 not found 项。PETSc 的稳定 C API、同一 MPI 动态库、实际编译链接和 1/2 Rank 初始化均通过，支持当前 ABI 兼容结论。
- 临时 C 探针通过 PetscInitialize、MPI_Get_library_version、H5get_libversion，1/2 Rank 均退出 0，确认实际运行的是 OpenMPI 5.0.8 / HDF5 1.14.6 / METIS 5.1.0。
- HDF5 1.14.6 为 mpi_openmpi 构建，H5_HAVE_PARALLEL=1；yaml-cpp 为 0.8.0。
- 可用性细节：该 HDF5 包未提供 hdf5.pc，pkg-config --modversion hdf5 失败。CMake 使用头文件/动态库直接查找，成功找到依赖；运行时探针也成功，因此不属于缺少 HDF5。未修改 PKG_CONFIG_PATH 或创建补丁元数据。
- 普通沙箱中 mpirun --version 会附带 pmix_ifinit socket errno=1 诊断（即使返回 0）；提权执行模式下的 1/2 Rank 和测试才是 MPI 功能验证证据。未修改系统权限。

PETSc 原始证据：petscconf.h、petsc-build.txt、petsc-ldd.txt、blas-runtime.txt、probe-rank1.txt、probe-rank2.txt、debug-fresh-ldd.txt、release-fresh-ldd.txt。

## CMake 配置、构建及测试

已完整读取 CMakeLists.txt、CMakePresets.json、README.md、AGENTS.md，并读取总原则及构建验证说明。README 的原机器版本（GCC 13.3 / PETSc 3.23.2 / OpenMPI 4.1.6）与当前实例不同，以本次实测为准。

使用仓库 presets，通过 -B 仅将产物放在 /tmp/eonsim-infra-check/build-debug 和 build-release，未改动原有 build/debug、build/release 或预设文件。两个模式均开启 BUILD_TESTING，指定现有依赖前缀、同前缀 MPI 启动器和 OPENBLAS provider。全新构建各含 45 个 Ninja 步骤，没有复用原有对象文件。

| 步骤 | 退出码 | 耗时（秒） |
|---|---|---|
| debug-configure | 0 | 2.14 |
| debug-build | 0 | 16.49 |
| release-configure | 0 | 1.93 |
| release-build | 0 | 18.32 |
| debug-ctest | 0 | 247.65 |
| release-ctest | 0 | 189.36 |

完整执行命令和退出状态：validation-results.json；逐步日志：*-configure.log、*-build.log、*-ctest.log。构建日志未发现 warning:/error:。

- debug: 共 26 项，成功 26，失败 0，跳过 0；JUnit：debug-junit.xml。
- release: 共 26 项，成功 26，失败 0，跳过 0；JUnit：release-junit.xml。

## 失败、缺失项与建议

- 当前必需开发依赖没有缺失，未进行任何安装或配置修复。
- 诊断性失败：hdf5.pc 缺失导致 pkg-config 查询失败；普通沙箱限制 MPI socket。两者原因已定位，不归为应用测试失败。默认 PATH 中缺少 CMake/Ninja，通过已有激活脚本使用，不需要重复安装。
- 若后续确有软件缺失，建议先复用 /workspace/.eonsim-tools 下已有清单并在独立前缀中恢复匹配的 real-double PETSc/OpenMPI 依赖；安装或更改配置前应另外取得授权。本次未执行该方案。

## 能力边界与开发结论

- 适用于当前 C++17 EONSim 的编辑、Debug/Release 编译、小型数值与 MPI 回归开发；需要先激活环境并在允许本地进程通信的执行模式下运行 MPI。
- 资源上限为单机约 4 核、32 GiB 内存，适合 1/2 Rank 日常验证和 4 Rank 小算例；不代表多节点、大网格、HPC 扩展性或生产吞吐验证。无 GPU 工作流验证。
- 本次未进行磁盘吞吐、长期稳定性、网络/GitHub 读写或跨任务快照恢复测试；未修改分支、提交或推送。
- 本项目已有能力不应延伸解释为非匹配界面、自动重网格或大规模生产保证。
- 本报告和构建位于 /tmp，属于临时产物。

最终结论：在上述资源和执行权限边界内，适合开展 EONSim 正式开发。Debug/Release 全新构建与本轮完整测试结果见上文。

## 最终状态核对

- 本轮 Debug 26/26、Release 26/26，合计 52/52，失败 0、跳过 0；JUnit 已逐项核对。
- git status 与检查前相同且为空，git diff HEAD 为空。
- 最终 memory.events：

```text
low 0
high 0
max 0
oom 0
oom_kill 0
oom_group_kill 0
```

- cgroup memory.peak=4209438720 bytes（容器生命周期高水位，不能当作本次检查独立峰值）；最终 memory.current=3368628224 bytes。完整最终资源快照：cgroup-final.json。
- 安装/环境配置/源码/分支变更：无。
