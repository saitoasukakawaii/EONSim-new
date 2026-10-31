# L3：构建模式与最小验证

状态：采用。适用范围：构建、诊断、错误传播和验证。实际入口为现有debug/release presets、eonsim及CTest目标；INFRA-01新增锁定云环境入口，复用原provider与测试。

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

`-diagnostics basic|full` 是运行期开关，不改变编译模式。Release 开启详细日志不会自动变成 Debug；`RelWithDebInfo` 也不能代替 Debug。`NDEBUG` 与自定义宏统一由构建设置，禁止在不同源文件各自定义。

实际CMake目标为 `eonsim_build_options`、`eonsim_core`、`eonsim` 和 `verify_*`；
`BUILD_TESTING=ON` 才注册验证。Debug/Release presets分别使用Ninja独立目录，
`MHPC_DEBUG` 由配置生成，不覆盖两种构建的数学模型。

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

仓库已提供 `debug`、`release` presets，手工环境可执行：

```sh
cmake --preset debug -DBUILD_TESTING=ON
cmake --build --preset debug --parallel 2
ctest --preset debug -R 'solver_failures|nonlinear_acceptance' --output-on-failure
```

手工并行度需按机器配额调整；云端优先使用下节自动配额入口。Release将preset换为release。

PETSc 调试构建与优化构建分别记录。应用 Debug 可在 ABI 相容时使用优化依赖以降低环境成本；排查 PETSc 内部问题再切换其调试构建。正式性能数据使用优化 PETSc，不能只把应用设为 Release。[PETSc 性能文档](https://petsc.org/release/manual/performance/)

### 从干净云机恢复与验证

需要Linux x86_64云端主机、bash、curl、sha256sum、Git、系统CA，以及GitHub release和conda-forge下载权限。主锁要求x86-64-v3 CPU；建议至少4CPU、8GiB内存及12GiB可用磁盘。云端与本地环境的验证证据分开记录；PR #23 另有用户授权的 WSL2 运行记录，不代表原生 Windows 已验证。

```bash
git clone https://github.com/saitoasukakawaii/EONSim-new.git
cd EONSim-new
# 可指定任意可写的云端前缀；不依赖/workspace/.eonsim-tools。
scripts/cloud/restore.sh 3.23.7 /opt/eonsim-cloud
scripts/cloud/run.sh 3.23.7 debug core /opt/eonsim-cloud
scripts/cloud/run.sh 3.23.7 release core /opt/eonsim-cloud
# 公共基础设施交付：一次完整现有短套件
scripts/cloud/run.sh 3.23.7 debug all /opt/eonsim-cloud
scripts/cloud/run.sh 3.23.7 release all /opt/eonsim-cloud
# 仅当本次修改涉及 PETSc 3.19.6 兼容路径时，才按需运行旧版专项检查
scripts/cloud/restore.sh 3.19.6 /opt/eonsim-cloud
scripts/cloud/run.sh 3.19.6 release mpi-failure /opt/eonsim-cloud
```

`/opt/eonsim-cloud`必须由执行用户可写；省略最后参数使用仓库忽略的 `.cloud/`。
干净恢复验证使用新的空目录；再次执行同一restore命令验证包缓存复用，再实际执行run。
缓存不包含编译产物或测试结果。锁及来源见[依赖清单](../../environments/README.md)。

入口复用原preset但以 `-B build/cloud-版本-模式` 隔离ABI，显式开启原PETSc provider及OpenBLAS。
云入口同时显式设置 `EONSIM_VERIFY_LOCKED_RUNTIME=ON`，才注册仅适用于锁定 OpenMPI/32 位 PetscInt 的 `runtime_mpi` 探针。
该选项默认 OFF；普通 `BUILD_TESTING=ON` 不附带锁定环境的 ABI 限制。PR #23 检查点启用探针时为 60 项，普通配置少一个 runtime_mpi。数量随源码和配置变化，执行前使用 `ctest --test-dir <构建目录> -N` 读取实际 inventory，不硬编码测试总数。
清除编译器激活脚本的优化flags，让Debug/Release采用自身CMake标志；清除PYTHONOPTIMIZE以保留数值断言。
编译线程取CPU affinity、可见cgroup v2当前组/祖先配额、内存每任务2GiB预算及上限4的最小值。
当前未实现cgroup v1探测；这类部署应先迁移到v2或手工受控构建，不宣称已自动识别其配额。
CTest串行调度测试，各MPI rank的OMP/OpenBLAS/MKL线程均1；既有4rank小测试允许在较少CPU上oversubscribe，仅用于正确性，不作性能结论。

证据保存在 `build/cloud-版本-模式/evidence/`：

- `summary.json`：SHA/dirty、平台/配额、依赖版本/包源/锁哈希、构建模式、选择、命令退出码/超时、逐测试rank/通过/失败/跳过及日志位置。
- `junit.xml`：CTest实际结果及测试输出；`ctest.log`保留成功与失败的数值验证输出。
- `configure.log`、`build.log`、工具版本、runtime-preflight/linkage日志、petscconf.h与petscvariables。
- `Testing/`、CMakeCache及测试生成的原始日志随CI artifacts保留14天；长期引用需另归档精简结论。

```bash
cat build/cloud-3.23.7-release/evidence/summary.json
cat build/cloud-3.23.7-release/evidence/ctest.log
```

任何非预期跳过、空选择、不完整JUnit或非零CTest退出都判失败；预期错误由既有测试断言错误原因、状态和恢复后正常返回，与应用异常退出/超时区分。CTest沿用原超时；外层Linux子进程收养及进程组清理仅处理本次验证后代，不杀无关作业。

GitHub Actions `core-numerics.yml` 在 main、codex 分支 Push 及 PR 上只运行 PETSc 3.23.7 的 Debug/Release 主力矩阵。PETSc 3.19.6 不参与日常 CI；仅在手动触发 workflow_dispatch 并显式勾选 `run_legacy_petsc` 时，运行 Release 的 `mpi-failure` 专项检查。仅依赖包缓存，键含锁、平台、编译器和 ABI；失败仍上传证据。网站构建不是数值 CI 替代品。


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

默认 max_retries=0，失败停止并保留已接受状态；已实现可配置的有限缩步、G5 历史恢复与事件控制。错误是否可重试由具体驱动契约决定，不开发通用恢复策略管理器。

## 引入上游库时保持同一验证尺度

记录实际采用的发行版本/commit、标量精度、索引位宽、编译器和必要后端选项；不把研究快照默认分支当作已验证的依赖组合。使用 Kokkos 时，按所选版本同时更新语言标准和工具链，不能只添加链接库。

上游库自带的大型测试套件不成为每次应用开发的门禁。首次接入只确认目标配置和一个实际使用该能力的算例；后续依赖升级时验证本项目受影响路径。只有修改上游库自身实现或出现具体缺陷时，才运行相关上游测试。

增加某个 Debug 检查后，确认其副作用不会成为 Release 必需步骤；编译器优化后出现差异时，优先排查未初始化值、越界、共享状态和实际依赖配置，不以两套数学代码掩盖差异。

## 文档生成

Doxygen 是可选开发工具，单独生成 HTML；不加入默认 build，也不挂接数值测试。首次配置、文档语法批量变更或交接时生成一次，修正实际错误；普通注释变更按阅读和必要链接检查处理。没有注释覆盖率门禁，文档 warning 不默认阻断开发。

目前已提供可运行的 Doxyfile；顶层 CMake 在 `MHPC_BUILD_DOCS=ON` 时注册可选 `docs` target，默认关闭，也可以直接调用 Doxygen。具体命令、配置和源码契约写法见 [文档与注释规范](DOCUMENTATION_AND_COMMENTS.md)。Debug/Release 共享 API 文档，诊断差异在契约中说明。


## 已执行的阶段交付验证

最新功能交付见 [PR #23 集成验收](FEM_INTEGRATION_VALIDATION.md)：主锁 Debug/Release 各 60 项、兼容专项 13 项通过，最多 4 rank。这是归档结果，本次文档同步未重新运行。PR #24 后旧版不进入日常 CI。以下为历史基线。

2026-10-29：Debug 和 Release 均通过 13 项 CTest，涵盖 Poisson、分布式布局、
流体/固体/ALE、刚体/弹性/超弹性 FSI 的局部与总系统导数、接受状态、失败退出和重启。
重启检查使用 1/2 rank；有限变形 FSI 的直接解/FGMRES 块解使用 1/2/4 rank。
`-solver_report` 输出有效 DoF、非零元、线性迭代、SNES 内部总耗时、装配和 ghost 更新时间。
Linux 下 `peak_rss_*` 使用 getrusage 的进程高水位值；`rss_*` 是求解后的驻留内存采样。
这些是诊断数据，不增加日常测试门禁。性能范围与限制见 PERFORMANCE_BASELINE.md。

## 语义 PC 分组（G0B）

独立流体与现有单体 FSI 可以显式选择 `solver: {pc_recipe: physics}`（也支持
`quantity`、`hybrid`），或使用 `-pc_recipe hybrid`。省略时默认求解和存储编号保持原状；
不能与 `-block_pc` / `-schur_pc` 同时使用。这不是生产存储重排功能。
`-pc_plan_report` 输出owned块大小与实际options prefix；`-linear_report` 继续使用原物理验收字段。

针对索引/故障的快速检查：激活仓库锁定环境后执行
`ctest --test-dir build/cloud-3.23.7-debug -R '^pc_plan_' --output-on-failure`。
真实算例选择 `-R '^pc_recipe_'`，包含三recipe对直接解、COO/重启以及hybrid真实缩步。
公共接口与最终集成仍使用 `scripts/cloud/run.sh 3.23.7 debug all` 和release对应命令，
不能用索引测试代替数值验收。索引/故障测试同时标记mpi-failure以覆盖旧锁定环境。
实现边界与证据见 [整体实施记录](FEM_INTEGRATION_VALIDATION.md)。
