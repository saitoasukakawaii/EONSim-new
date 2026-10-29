# L3：构建模式与最小验证

状态：采用。适用范围：构建、诊断、错误传播和验证。当前仓库尚无求解代码；下列命令与片段是目标实现，不表示已存在可构建目标。

## Debug / Release 的明确设计

### 编译模式与运行诊断分开

| 项目 | Debug | Release |
|---|---|---|
| 用途 | 开发、定位数值/内存问题 | 实际计算、扩展性与性能测量 |
| 优化/符号 | CMake 对应工具链的 Debug 默认值 | CMake Release 优化；需要采样时可另用 RelWithDebInfo |
| `MHPC_DEBUG` | `1` | `0` |
| 索引、尺寸、owner、稀疏图断言 | 开启 | 去掉重复内部断言 |
| 完整向量扫描、Jacobian 差分、矩阵导出 | 显式选择后运行 | 默认关闭；保留按需诊断入口 |
| 输入有效性、文件错误、求解失败 | 保留 | 保留 |
| 数学公式、边界条件、停止准则 | 同一实现 | 同一实现 |
| 日志 | 默认较详细，可降低 | 默认简洁，可提高 |

`--diagnostics basic|full` 是运行期开关，不改变编译模式。Release 开启详细日志不会自动变成 Debug；`RelWithDebInfo` 也不能代替 Debug。`NDEBUG` 与自定义宏统一由构建设置，禁止在不同源文件各自定义。

**CMake 接线示意**（后续建工程时采用；不是当前工作区已有目标）：

```cmake
cmake_minimum_required(VERSION 3.23)
project(MultiPhysicsHPC LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Debug CACHE STRING "Build type" FORCE)
endif()
option(BUILD_TESTING "Build focused verification tools" OFF)

add_library(mhpc_build_options INTERFACE)
target_compile_definitions(mhpc_build_options INTERFACE
  MHPC_DEBUG=$<IF:$<CONFIG:Debug>,1,0>)
# 所有包含相关实现/头文件的工程 target 继承同一配置。
# 不在这里覆盖 CMAKE_CXX_FLAGS_RELEASE 或 CMAKE_CXX_FLAGS_DEBUG。
# target_link_libraries(mhpc_core PUBLIC mhpc_build_options)
# target_link_libraries(mhpc PRIVATE mhpc_core)
```

```cpp
// 只把无副作用的内部不变量放在 Debug 断言中。
#if MHPC_DEBUG
assert(local_dofs_are_valid(cell_dofs, local_state_size));
#endif

// 必需调用不放进 assert：Release 也必须执行求解及错误传播。
PetscCall(KSPSolve(ksp, rhs, dx));
PetscCall(KSPGetConvergedReason(ksp, &reason));
// 由调用者把 reason <= 0 转为失败状态，统一决定作业退出或时间步策略。
```

上面的 PETSc 片段应位于遵循 PETSc 返回码约定的函数内。API 调用成功不等于数值收敛，必须读取 KSP/SNES 的停止原因；这项检查在 Release 保留。[PETSc 收敛原因](https://petsc.org/release/manualpages/KSP/KSPGetConvergedReason/)

初期不默认启用 `fast-math`，也不使用与目标节点不兼容的本机专用指令集。Debug 可在排查内存错误时使用 ASan/UBSan，不把 sanitizer 变成每次开发的强制环节。

### 构建与依赖配置

建议后续建立 `debug`、`release` 两个 CMake preset，分别指向 `build/debug`、`build/release`。它们创建之前，可使用以下等价命令：

```sh
cmake -S . -B build/debug -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build/debug --parallel
cmake -S . -B build/release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/release --parallel
```

这些是目标工程建立后的命令。Visual Studio/Ninja Multi-Config 使用 `cmake --build <dir> --config Debug` 或 `--config Release`，不能只设置 `CMAKE_BUILD_TYPE`。[CMake 构建类型](https://cmake.org/cmake/help/latest/variable/CMAKE_BUILD_TYPE.html)

PETSc 调试构建与优化构建分别记录。应用 Debug 可在 ABI 相容时使用优化依赖以降低环境成本；排查 PETSc 内部问题再切换其调试构建。正式性能数据使用优化 PETSc，不能只把应用设为 Release。[PETSc 性能文档](https://petsc.org/release/manual/performance/)

尤其在 Windows，确认编译器、CRT/迭代器 ABI、MPI 和 PETSc 相容；应用宏不能修复依赖 ABI 不匹配。借鉴 EONSim 的环境启动入口，但不把其完整 provider/预检体系照搬为首版前置流程。审查发现其主 preset 是 `RelWithDebInfo`，并对 Fortran 指定了 `/Od`，因此不能仅凭 preset 名称判断整套程序已优化。[本地构建审查](../research/EONSIM_PERIGEE_REVIEW.md)

## 精简测试与不过度防御的执行规则

### 日常验证只有必要的两三步

| 改动类型 | 默认动作 |
|---|---|
| 文档、注释、排版 | 阅读/链接检查，不跑求解测试 |
| 普通功能、边界参数或 I/O | 编译受影响目标＋一个相关小算例 |
| 通信、编号、装配所有权 | 上述动作＋同算例 1/2 rank 对照 |
| 材料、稳定化、残量/切线公式 | 一个局部方向导数或解析/制造解检查＋相关算例 |
| 性能改动 | 同一代表算例在 Release 下对比耗时、迭代数和结果 |

不强制测试先行、全量 CTest、覆盖率指标、全平台矩阵或重复验收。普通小改动不新增只复述实现的单元测试。已通过的检查仅在代码继续变化、失败或出现具体疑点时重跑。

长期案例随当前路线逐个增加：标量基础、低 Re 通道、独立弹性体、给定运动 ALE、单轴刚体 FSI、弹性 FSI。同一几何的静态/动态或材料变化优先作为配置变体；案例兼作示例与回归，不另建几乎相同的三套数据。完整短套件只在版本交付或共同基础设施大改时运行。

### 少而有价值的数值检查

- 单纯“退出码为零”不足以判定成功：同时看求解收敛与该算例的一个主要物理量，例如质量平衡、热流或位移。
- 新离散项首次接入时，做一次小网格解析/制造解或加密比较；此后不在每次普通改动重做收敛研究。
- 新 Jacobian 做少量方向上的 `Jv` 与残量差分比较，优先覆盖边界/耦合项；不默认对完整大矩阵逐列差分。
- 首次加入单体 FSI 的接口或 ALE 导数，选择包含跨场扰动的整体方向；仅验证单场对角块不足以确认组合切线。Debug 按需检查即可，不在每步生产求解中重复执行。
- 并行与 Debug/Release 对比使用同一离散问题、规范及容差；允许浮点归约顺序导致的差异，不要求逐位相同。容差按量纲、离散误差和 solver tolerance 写入对应 case，不全工程统一一个数。
- 短算例用于日常反馈；长期稳定性、极端网格与实验验证随实际版本用途再做，不阻塞无关功能。

### 检查放对位置

配置、网格、分区包和依赖兼容性在读入/准备阶段检查一次；内部索引和结构不变量主要放 Debug。Release 保留会使结果无效的事件：不可逆文件失败、非法单元几何、非有限求解结果、线性/非线性/耦合未收敛。

利用已有几何计算及残量规约完成这些检查，不为每个数组访问附加分支，不每次迭代扫描整张稀疏图，不创建多层 bool/status/exception 的重复包装。未实现功能在配置阶段明确报错，不静默退化到另一种方程、时间格式或松弛容差。

首版默认失败即停止并保留已接受状态。以后确有长任务恢复需求时，增加有次数上限的时间步缩小/回退；不要先开发通用恢复策略管理器。

## 引入上游库时保持同一验证尺度

记录实际采用的发行版本/commit、标量精度、索引位宽、编译器和必要后端选项；不把研究快照默认分支当作已验证的依赖组合。使用 Kokkos 时，按所选版本同时更新语言标准和工具链，不能只添加链接库。

上游库自带的大型测试套件不成为每次应用开发的门禁。首次接入只确认目标配置和一个实际使用该能力的算例；后续依赖升级时验证本项目受影响路径。只有修改上游库自身实现或出现具体缺陷时，才运行相关上游测试。

增加某个 Debug 检查后，确认其副作用不会成为 Release 必需步骤；编译器优化后出现差异时，优先排查未初始化值、越界、共享状态和实际依赖配置，不以两套数学代码掩盖差异。

## 文档生成

Doxygen 是可选开发工具，单独生成 HTML；不加入默认 build，也不挂接数值测试。首次配置、文档语法批量变更或交接时生成一次，修正实际错误；普通注释变更按阅读和必要链接检查处理。没有注释覆盖率门禁，文档 warning 不默认阻断开发。

目前已提供可运行的 Doxyfile；顶层 CMake 的可选 docs target 待 P0 建工程时接入。具体命令、配置和源码契约写法见 [文档与注释规范](DOCUMENTATION_AND_COMMENTS.md)。Debug/Release 共享 API 文档，诊断差异在契约中说明。

