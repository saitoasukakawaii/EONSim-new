# Linux 云端依赖锁

主验证组合使用 `petsc-3.23.7-linux-64.lock`；`petsc-3.19.6-linux-64.lock` 仅用于故障兼容检查。
两者采用同一恢复方法：micromamba 2.10.0-0（恢复脚本固定下载地址与SHA256），
conda-forge显式包URL与SHA256。恢复不重新求解依赖，不使用系统MPI或旧oneAPI/PARDISO流程。

| 组件 | 主环境 | 旧版故障复现 |
|---|---|---|
| GCC/G++ | 15.3.0 | 12.4.0 |
| PETSc | 3.23.7 real | 3.19.6 real |
| OpenMPI | 5.0.8 | 4.1.6 |
| OpenBLAS | 0.3.34 OpenMP | 0.3.34 pthreads |
| HDF5 | 1.14.6 OpenMPI | 1.14.2 OpenMPI |
| METIS | 5.1.0 | 5.1.0 |
| yaml-cpp | 0.8.0 | 0.8.0 |
| CMake | 4.4.5 | 3.28.4 |
| Ninja | 1.13.2 | 1.13.2 |
| Python | 3.15.2 | 3.12.3 |
| pkg-config | 0.29.2 | 0.29.2 |

全部传递依赖及build字符串以锁文件为准。主环境含x86-64-v3 SuiteSparse构建，需要支持AVX2等v3指令的Linux x86_64云机；恢复脚本提前检查CPU特征。只验证Linux，未验证ARM、Windows、WSL或macOS。本次不支持从锁文件替换MPI厂商、复数、单精度或64位PetscInt。

两个PETSc包均为优化依赖，应用Debug仍使用同一依赖ABI。运行探针检查real/double/32位PetscInt和两rank通信，`ldd`检查应用加载的PETSc/MPI来自所选前缀；环境清单保存完整包版本、来源和PETSc构建配置。不声称知道历史PETSc包编译时GCC的精确版本。

旧OpenMPI 4.1.6内置hwloc的x86 CPUID探测在当前Xeon云机上除零，入口对旧环境禁用该探测组件，保留Linux/sysfs拓扑；同时禁用旧vader CMA单拷贝，避免受限容器不支持process_vm_readv。两项均不改变PETSc或MPI ABI，也不修复/掩盖应用的局部PC失败；其超时在相同环境中仍被复现。

完整恢复、验证和证据命令见[构建说明](../docs/development/BUILD_AND_VALIDATION.md)。锁升级应重新完成干净恢复、ABI预检和相应数值测试，不手改版本号后沿用旧证据。

单机验证入口固定OpenMPI `ob1` PML和self/shared-memory/TCP BTL（5.x为sm，4.x为vader），不自动选择UCX/RDMA。PR后CI的Azure MANA设备曾在MPI_Init阶段拒绝UCX UD队列创建；这是runner传输能力差异，发生在数值测试之前。此入口不用于宣称RDMA或多节点性能。
