# L3：Doxygen 文档与代码注释规范

状态：采用。面向当前单体 FSI 开发路线，目标是让后来的人能正确使用、修改和组合数值代码。只记录有价值的契约，不要求逐行注释、注释覆盖率或每次构建文档。

## 分工：每类信息只维护一个主要来源

| 位置 | 保存内容 | 更新时机 |
|---|---|---|
| docs/architecture 的 L1/L2 Markdown | 模块边界、完整数学约定、耦合算法和设计原因 | 架构或数学选择改变时 |
| 头文件中的 Doxygen 注释 | 调用者必须知道的 API 契约、参数语义和副作用 | 接口或实际行为改变时，同步修改 |
| .cpp 内普通注释 | 不明显的实现原因、符号/变换推导、性能取舍 | 相邻实现改变时 |
| case 说明 | 运行命令、模型范围、观测量、实际验证结果 | 案例能够运行或配置改变时 |
| Doxygen HTML | 从以上已选输入生成的浏览视图 | 需要查看、交接或阶段交付时 |

长推导留在架构文档。API 注释指出对应文件/章节，写清当前函数的必要约定；不把整套 FSI 理论复制到每个 kernel。Doxygen 输入只纳入需要展示的源码和页面，历史审查、skill 和生成目录不整仓递归导入。

当前仓库尚无求解器代码。下面所有 C++ 声明都是**注释示例，不是已实现 API**；Doxygen 的模块列表是分类方案，不代表相应能力已经完成。

## 注释写到什么程度

| 对象 | 默认要求 |
|---|---|
| 跨模块 API、局部数值核、状态更新、MPI/设备边界 | 说明会影响正确调用的语义；按需使用参数、布局、状态、并行段落 |
| 重要类型/视图 | 职责、所有权/借用、布局、生命周期 |
| 普通 getter、显然的私有小函数 | 名称和类型足够时不加模板化文档 |
| 数值/性能上的非直观实现 | 一到数行解释原因，必要时关联公式或来源 |
| 简单循环、赋值、构造转发 | 不复述代码 |
| 未实现能力 | 在路线或任务中记录，不写成 API 已支持的功能 |

默认采用中文说明、英文标识符和统一数学符号；不要求每段中英双写。一个文件保持一致。通过类型/变量名表达的信息，不再机械重复。

## HPC 与 FSI 中应明确的契约

只选择当前函数真正涉及的项目，不要求每个函数填满以下各项：

- **数学：** 残量定义及正负号、未知量和测试空间、切线相对什么变量求导、哪些系数被冻结。
- **布局：** 分量顺序、矩阵行/列含义、局部或全局编号、owned/ghost 范围、张量/Voigt 顺序及剪切分量约定。
- **物理：** 单位、时间层、参考/当前构形、压力基准、法向和界面力方向。只写“SI”不能替代关键参数的单位。
- **写入：** 覆盖还是累加、由谁清零、是否允许输入输出别名、输出缓冲是否由调用者提供。
- **状态：** accepted/trial 的读写权限、材料历史是否更新、失败后哪些结果有效。
- **生命周期：** owner 还是 view；借用 PETSc 数组/设备缓冲何时失效；函数是否保存输入引用。
- **并行：** local / neighbor communication / collective / logically collective；communicator、调用参与者、ghost 就绪条件、返回时通信是否完成。
- **执行：** host/device 可访问性、异步完成条件、线程共享限制。没有设备实现时不声称 GPU-safe。
- **代价：** 内部是否分配、是否装配矩阵、是否包含规约/同步。只有实测过才写性能结论。

例如“const 函数”不自动意味着线程安全，“读取向量”不自动意味着 ghost 已同步，“MPI 函数”也不自动意味着全体 rank 都必须调用。必须按真实调用链说明，不能凭名称推断。

## Doxygen 的写法

采用 `/** ... */` 写较长契约、`///` 写简短说明、`///<` 写非平凡成员语义。主要使用 `@brief`、`@param[in/out/in,out]`、`@return`、`@pre`、`@post`、`@note`、`@par`、`@ingroup`、`@see`。公式需要时使用 `@f$ ... @f$` 或 `@f[ ... @f]`；无需自定义大量命令。[官方命令说明](https://www.doxygen.nl/manual/commands.html)

`@pre` 描述调用者应满足的条件，不等于必须再加一遍运行时检查；`@post` 描述成功返回后的保证。只在实现确实抛异常时写 `@throws`；返回 PETSc 错误码的函数描述该约定，不伪装成 exception API。

公共头文件有一个简短的 `@file`；namespace、重要类型也给出简短说明。Doxygen 提取自由函数等全局实体时需要文件文档；不要依赖 `EXTRACT_ALL=YES` 掩盖遗漏。[官方注释说明](https://www.doxygen.nl/manual/docblocks.html)

声明和实现只保留一份完整 API 文档，通常放声明前。实现中补充算法原因；不要再复制整份 `@param`。接口重写确需复用文档时才考虑 `@copydoc`，避免在尚未稳定的继承体系里积累间接引用。

## 示例一：一个值得详细说明的局部数值核

下面类型是概念占位；实现时替换为项目真实类型、尺寸和返回语义，不为迁就注释而创建这些类。

```cpp
/** @file
 *  @brief ALE 流体单元的局部残量与一致切线。
 */

/// 有限元物理核；不负责全局通信和状态提交。
namespace mhpc {

/**
 * @brief 覆盖写入一个 Tet4 单元的流体残量及可选切线。
 * @ingroup mhpc_numerics
 *
 * @param[in] geometry 当前试算几何；与 trial 的网格位移来自同一候选点。
 * @param[in] trial 当前单元 u、p、网格速度；采用 BE 的 n+1 时间层。
 * @param[in] accepted 上一个已接受时间层，只读。
 * @param[in] dt 时间步长，单位 s，dt > 0。
 * @param[out] residual 16 项；每节点依次为 [u_x, u_y, u_z, p]。
 * @param[out] tangent 可为空；非空时覆盖写入 16×16 的流体对角块。
 *
 * @par 数学与布局
 * Newton 约定为 J*dx = -R。矩阵为 row-major：
 * tangent[16*i+j] = d residual[i] / d local_unknown[j]。
 * 此入口固定 geometry 和网格速度，仅返回对 u、p 的导数；
 * 它不是包含 ALE/界面导数的完整单体 FSI Jacobian。
 *
 * @par 状态与执行
 * 不修改 accepted，不保存输入引用，不通信、不分配持久缓冲。
 * 输入输出不得重叠；不同调用使用独立输出时才可并行调用。
 *
 * @pre 调用者已准备有效几何与足够大的输出缓冲。
 * @post residual 及请求的 tangent 已覆盖写入，不累加旧内容。
 */
void evaluate_fluid_cell(
    const GeometryView& geometry, const FluidTrialView& trial,
    const FluidAcceptedView& accepted, double dt,
    double* residual, double* tangent);

} // namespace mhpc
```

重点是区分“局部流体对角块”与“完整耦合切线”。全局单体装配还要加入 ALE、接口映射和结构/刚体等导数，不能凭函数名含 Jacobian 就假定已经完整。

上述参数名、16 项布局、是否分配等必须随真正实现调整；不能照抄后留下不真实的保证。预分配缓冲可以后续改成已有 view 类型，不为文档示例引入额外容器。

## 示例二：MPI 边界写清参与者和完成条件

```cpp
/**
 * @brief 从 owner 更新本 rank 的 ghost 值，返回时完成交换。
 * @ingroup mhpc_parallel
 * @param[in,out] values 前 n_owned 项不变；后 n_ghost 项被覆盖。
 *
 * @par 并行约定
 * 按该示例接口的约定，plan.comm() 内所有 rank 以相同顺序调用，
 * 包括没有本地 ghost 的 rank；请求在返回前全部完成。
 * 本函数不执行 ghost 到 owner 的反向求和。
 *
 * @pre 所有权/通信计划已建立；没有使用 values 的未完成通信。
 * @note 同一 plan 不支持重入；不与写入同一缓冲的线程并发执行。
 */
void update_ghosts(const HaloPlan& plan, VectorView values);
```

这里描述的是拟定 wrapper 的契约，并不宣称所有 halo 实现都是 MPI collective。实际只需相邻 rank 参与时应改写为真实要求；若是异步 begin/end，则分别说明发送/接收缓冲何时可读写和由谁完成请求。不要使用笼统的“MPI-safe”。

## 示例三：实现注释解释原因

```cpp
// 在 Dirichlet 行被替换前保存界面动量贡献；刚体广义力由此投影。
// 后续不再把应力积分结果作为第二份载荷加入刚体方程。
capture_interface_reaction(raw_residual, interface_rows);

// BE 下 d_s = d_s_n + dt*v_s，因此材料对速度的切线含 dt 链式系数。
add_material_tangent(dt, material_tangent, solid_block);

// 材料 trial 必须从 accepted 历史重新评价，避免线搜索重复推进历史。
evaluate_material(accepted_history, trial_strain, trial_history);

// 更新 ghost 与内部单元计算重叠；边界单元需要等待接收完成。
begin_halo();
assemble_interior_cells();
end_halo();
assemble_boundary_cells();
```

不用写 `// 遍历所有单元`、`// 把 a 加到 b`、自动生成的大段函数签名说明。符号不直观时就地解释；算法来源使用稳定论文/文档链接及公式编号，不只写“参考某论文”。保留复制代码原有的许可证和来源声明。

## 模块与页面组织

模块分类按职责，而非每个目录/类一个 group。当前只建立三个稳定大组：

| group | 内容 | 细分时机 |
|---|---|---|
| `mhpc_numerics` | mesh/DoF、几何、局部核、装配与代数接口 | 实际 API 数量增长后再按职责细分 |
| `mhpc_parallel` | owner/ghost、通信、内存/设备边界 | 设备路径真正实现后再细分 |
| `mhpc_fsi` | 时间/状态、刚体/固体接口、单体组合残量 | 两类 FSI 实际实现后再增加子组 |

在 `docs/doxygen/groups.dox` 用 `@defgroup` 定义，API 用 `@ingroup` 关联。主页保留当前实现状态、导航和主要阅读顺序；不要提前生成所有未来模块的空类页面。

当前 Doxygen 只展示主页、注释规范和上述组。完整架构仍从仓库 L0/L1/L2 阅读，不在 API 站点维护第二份。需要把架构页纳入网站时，再显式添加相应 Markdown 到 INPUT，并核对其相对链接；未导入的本地文件路径不是网站页面。

代码示例先放代码块即可；真实可运行示例出现后用 `@snippet` 引用同一份源码，减少两套代码漂移。不要把注释示例当成已经编译/验证过的求解程序。

## 已提供的轻量配置

实际配置在 `docs/doxygen/Doxyfile`。它只生成 HTML，不依赖 Graphviz、LaTeX、Sphinx 或 Clang 解析器；当前源代码目录还未创建，因此没有把不存在的 include/src/apps 放进 INPUT。P0 出现源码后按需追加这些已存在目录，保持排除 build、external/third_party 和模板目录。

配置原则：

- 保留文档语法/参数名错误提示；关闭未注释实体和不完整参数说明的覆盖率式告警，不把 warning 当构建失败。
- `EXTRACT_ALL=NO`，按显式文档提取；保持源码浏览，避免所有私有实现进入公共 API。
- 不开启全量调用图；人工架构图继续在已有 Markdown 维护。
- 采用同一份文档，预处理默认按 `MHPC_DEBUG=0`、`NDEBUG` 看公开 API。Debug 额外断言/诊断在行为说明中指出，不维护两份数学语义。
- 公式使用 MathJax，生成 HTML 无需本机 LaTeX；当前浏览公式使用 CDN。离线部署时再将 MathJax 随站点提供并调整路径，HTML 生成成功不代表离线公式渲染已经验证。

这些选择和告警含义对应 [Doxygen 配置文档](https://www.doxygen.nl/manual/config.html)。当前配置已在本机 Doxygen 1.14.0 生成验证；换用其他版本时以该版本支持的配置项为准。

在仓库根目录运行：

```sh
cmake -E make_directory build/docs
doxygen docs/doxygen/Doxyfile
```

输出为 `build/docs/html/index.html`；生成物不纳入 Git。第一条命令准备输出目录，重复执行无妨；也可用操作系统的目录创建命令完成。两条命令的工作目录都是仓库根目录，不是 Doxyfile 所在目录。

## P0 的可选 CMake 接线

以下片段在真正建立顶层 CMake 工程时加入；当前尚无顶层 CMakeLists.txt，不能把它当作已经存在的构建目标：

```cmake
option(MHPC_BUILD_DOCS "Enable the optional documentation target" OFF)
if(MHPC_BUILD_DOCS)
  find_package(Doxygen REQUIRED COMPONENTS doxygen)
  add_custom_target(docs
    COMMAND "${CMAKE_COMMAND}" -E make_directory
            "${CMAKE_CURRENT_SOURCE_DIR}/build/docs"
    COMMAND Doxygen::doxygen
            "${CMAKE_CURRENT_SOURCE_DIR}/docs/doxygen/Doxyfile"
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    COMMENT "Generating HPC API documentation"
    VERBATIM)
endif()
```

没有 `ALL`，所以普通编译不会生成文档；未打开选项时不要求安装 Doxygen。需要时配置 `-DMHPC_BUILD_DOCS=ON`，再显式构建 docs target。该片段是顶层用法；若移入子目录，需将路径改成实际仓库根目录。Imported executable target 的用法见 [CMake 3.23 FindDoxygen](https://cmake.org/cmake/help/v3.23/module/FindDoxygen.html)。

## 最小维护流程

开发一个功能时同步写好必要的调用契约和非直观实现原因；日常仅阅读受影响注释。首次建立配置、批量修改文档语法、交接或阶段交付时生成一次 HTML，关注新增参数名错误、失效引用和实际展示。无需每次 commit 运行 Doxygen，更不因注释改动跑 CFD/FSI 数值测试。

不添加作者/日期/修改历史模板，交给 Git；TODO 只用于明确未完成项，不写泛泛的“以后优化”。注释落后于实现时，在本次触及范围内修正，不扩大成全仓注释重写。

