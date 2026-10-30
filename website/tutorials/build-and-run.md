# 构建与运行 EONSim

本教程对应公开仓库当前的 CMake presets 和 README。依赖版本、平台和编译器组合可能变化；遇到配置问题时，先检查 PETSc、MPI、BLAS/LAPACK 的 ABI 是否一致。

## 1. 主要依赖

- C++17 编译器；
- CMake 3.21 或更高版本；
- Ninja；
- 实数双精度 PETSc；
- 与 PETSc 匹配的 MPI；
- METIS、HDF5、BLAS/LAPACK 和 yaml-cpp；
- Python 3（运行部分验证脚本需要）。

## 2. Debug 构建

在仓库根目录执行：

```bash
cmake --preset debug -DBUILD_TESTING=ON
cmake --build --preset debug --parallel 2
ctest --preset debug
```

## 3. Release 构建

```bash
cmake --preset release -DBUILD_TESTING=ON
cmake --build --preset release --parallel 2
ctest --preset release
```

并行编译任务数应根据可用 CPU 和内存限制调整，不要盲目使用全部逻辑 CPU。

## 4. 运行基础算例

```bash
./build/release/eonsim -case cases/poisson/case.yaml
```

## 5. 运行 MPI 分区算例

```bash
./build/release/eonsim -case cases/poisson/case.yaml -prepare results/poisson2 -parts 2
mpirun -n 2 ./build/release/eonsim -case cases/poisson/case.yaml -partition results/poisson2
```

某些云端容器会限制 MPI 进程启动或共享内存传输；若出现 MPI runtime 错误，应先检查容器限制和 MPI 配置，不要把它误判为数值求解失败。

## 6. 验证与结果

建议记录：
- Git commit；
- 编译器、PETSc、MPI 和 BLAS/LAPACK 版本；
- 网格规模、DOF 数量和 MPI rank；
- 求解器停止原因、迭代次数和真实残量；
- 解析解误差、守恒量和运行时间。

完整依赖及当前验证状态以 [仓库 README](https://github.com/saitoasukakawaii/EONSim-new/blob/main/README.md) 和 [构建验证规范](https://github.com/saitoasukakawaii/EONSim-new/blob/main/docs/development/BUILD_AND_VALIDATION.md) 为准。
