# EONSim Codex Session Log

本文件记录有实质代码、算法、验证或知识产出的开发会话。只记录事实，不写无法复现的“已优化”“性能显著提升”等结论。

## 2026-10-31 / DOCS-01 — 全仓 Markdown 进度同步

- 用户要求审查全部 Markdown 并按当前进度更新；基线 `a508e3d`，在 `codex/markdown-progress-audit` 工作。本次只修改文档，未推送、合并或部署。
- 清点 88 份既有项目 Markdown，覆盖根入口、架构、研发/研究、Skill、环境、网站正式页面/草稿/模板；逐文件处理清单见 [审查记录](MARKDOWN_AUDIT_2026-10-31.md)。依赖包、构建产物与 Git 内部文件不属于项目文档。
- 根因：多个文档保留不同检查点的“当前”描述。同步 PR #24 已合并、G0/G5/G1 已交付、旧 PETSc 手动专项、Doxygen 实际输入和平台范围；明确 G2/G4 子集及历史 BE/测试计数。
- 按源码确认 checkpoint 容器仍 v3、二维分区 v3/三维 v2，并补充二维标量 LinearSolveFailure 的重试边界，未改数学模型。
- 用 eonsim-knowledge-capture 修订既有草稿和知识索引，补后续验收来源；没有新增数值/算法成果，不另造教学文章，不将草稿转为发布。
- 静态检查脚本首次把数据目录误判为网站页面、把首页 layout: home 判为缺标题；修正检查器的路径/页面分类后复查。旧研究中不可移植的 Windows 链接改为原工程相对路径与行号，保留来源提交。
- 实际执行 `python3 /tmp/eonsim_md_audit.py` 检查全文结构、本地链接/锚点和固定 Git 源码目标，`git diff --check` 检查空白；最终结果见审查记录。`command -v node` 未找到 Node，本次未执行网站构建或产物隔离检查。
- 未运行 CMake、编译、CTest、MPI、数值或性能实验；未访问外部文献链接或远程 PR Checks。PR #23 测试数字引用已归档证据，不是本次新结果。

## 2026-10-31 / G5 — generalized-alpha ALE与单体FSI

- 以25e0945为基线，独立alpha云端CI三环境成功。共同af、一阶流体/二阶运动学、各自算法历史接入单体残量和checkpoint；明确stage力/功率输出。
- 新增提交前端点几何检查，rank局部失效先allreduce再共同拒绝。
- 主锁Debug10项针对性CTest全部通过（324.63秒），rho=0/0.5/1的速度/压力/位移趋二阶，整体J差分约1.8e-9；1/2/4rank完整历史、事件重启、接口运动与功率通过。
- 首次极小步重试对照因时间戳相减及接口位移消减而算法网格加速度不一致；改为17位实际步长重放、接口直接共享stage速度，保持原容差后通过。
- ALE rho0.5粗步启动误差抵消，改用更细同问题网格时间步进入渐近区；未改阶数阈值。
- ALE补充实测stage有效/endpoint反转，坏单元rank分布3/1/2/0；缩步恢复与失败checkpoint哈希不变通过。FSI独立端点反转分支仅审查，未直接触发。
- 独立审查两轮无剩余源码阻塞项；更新知识草稿，未发布。证据alpha-coupled.json。继续G1，G5最终集成验收与整体主线交付仍待完成。

## 2026-10-31 / G5 — 独立场generalized-alpha

- BDF2耦合检查点`bab4fda`云端CI三环境成功（run41192856614）。
- 核对PETSc3.23.7 alpha1/alpha2版本源码、一阶原始预印本§3–4与压力评价论文。Chung1993出版社全文403，仅核实出版信息，不声称读过全文。
- 新时刻权重参数分别实现一阶流体与二阶结构；独立stage速度/压力、端点恢复、完整算法历史及rho checkpoint。接受一个BE启动步的策略明确不同于PETSc探测启动。
- 结构惯性q与位移beta*h/gamma分离；局部线弹性/Neo-Hookean方向导数通过。物理端点加速度由卸载模型一致质量方程恢复，算法加速度独立输出/保存。
- 独立审查发现stage残量与端点输出混用风险，已将流体字段命名stage_momentum_residual，结构保留stage字段但端点反力/残量使用质量恢复方程，日志标记evaluation_time。
- 主锁Debug7项针对性CTest全部通过，26.82秒CTest墙钟；包括rho=0/0.5/1的真实流体早期/终点速度与压力阶、结构位移/速度/物理加速度阶、rho=1启动后能量保持、阻尼、1/2/4rank、事件checkpoint、算法历史和真实拒绝。
- [alpha-standalone.json](../research/data/fem-integration-2026-10-31/alpha-standalone.json)保留实际源码/二进制、命令、退出码和结果。alpha ALE/FSI尚未接入并明确拒绝；G5不关闭，继续下一增量。

## 2026-10-31 / G5 — BDF2 ALE与单体FSI

- 独立场提交`c923387`的云端CI三环境成功（run41181938354）。
- FSI流体惯性、结构/刚体位置与加速度、ALE网格速度、reduced.slot位移试探列和lifting统一使用当前BDF2映射；各层历史只在共同接受后提交。
- ALE新增同分区checkpoint，保存当前与前一流体/网格状态及步长；重试重建trial几何不污染accepted。
- 独立审查指出测试遗漏压力MPI/重启与非均匀接口功率，已补齐。接口功率按全分量离散残量与共享速度内积计算，不声称总能量守恒。
- 主锁Debug6项针对性CTest全部通过，138.35秒CTest墙钟；包括3个新验收和旧motion/刚体FSI/弹性FSI回归。整体Jacobian差分相对误差约1.4e-9，MPI最多4rank。
- 弹性FSI压力阶1.86/1.97、刚体压力阶2.00/2.02，速度与网格位移趋近2；粗时间步压力未达门槛后保持物理问题和容差继续细化。ALE网格速度BE阶0.95/0.98、BDF2阶2.02/2.01，均匀/剪切流保持及重启通过。
- 高压超弹性真实拒绝压力测试：从两步accepted检查点限制Newton为2次，15次缩步后以原容差接受下一BDF2步，并与无拒绝相同轨迹一致。测试显式允许16次重试，只推进一个恢复步；不作为实用步长建议。原8次上限耗尽的结果不是生产回归；3次Newton上限没有触发拒绝，未拿它替代恢复证据。
- [bdf-coupled.json](../research/data/fem-integration-2026-10-31/bdf-coupled.json)保存实际源码/二进制/日志哈希、命令、退出码和数值结果。G5仍未关闭，继续generalized-alpha；G1未实施。

## 2026-10-31 / G5 — 独立流体和固体BDF2增量

- 从`e9e4d30`继续；该G0补强提交云端三环境CI成功（run41180022722）。
- 统一BE/BDF2导数映射、实际历史步长、比率上限2、事件后启动、两层accepted checkpoint；独立固体位移重建同步使用当前格式。
- 真实流体首次320步测试暴露累计舍入制造极短末步，时间控制器补偿求和修复，320/10000步oracle通过。
- 独立审查指出步长相关tau使时间加密同时改变空间离散；新增显式固定tau并保持旧BE默认。压力驱动实测速度/压力BDF2阶约2；不是Python参考替代生产验证。
- 固体粗步未进入渐近区，保持问题和门槛继续细化，位移/速度/加速度BDF2阶接近2。没有声称非线性材料阶数或BDF2逐步物理能量单调。
- 主锁Debug编译退出0；针对性CTest9项全部通过，42.23秒CTest墙钟。选择包含time_integration、fluid/solid_time_verification、fluid/solid_element_jacobian、time_retry_verification、restart_block_verification、fluid/solid_verification。
- 新测试覆盖变步长、1/2/4rank、事件处重启、最后短步、BDF2启动后的真实Newton拒绝与同轨迹对照；签名拒绝更换积分器/候选步计划。独立审查公式与状态无阻塞缺陷，建议的schedule签名已补齐。
- [证据清单](../research/data/fem-integration-2026-10-31/bdf-standalone.json)记录实际dirty源码哈希、基线SHA、二进制哈希、命令、退出码及结果；不是把新结果归给旧提交。新增知识草稿保持draft。
- G5未关闭，后续继续ALE/FSI及两类generalized-alpha，G1尚未实施；此处只记录可复现增量。

## 2026-10-31 / FEM-INTEGRATION — 从已合入的G0检查点接续

- fetch核实main为47b5bd46c992fcf64cf163361053ceb0091fa5a5，工作区起始干净，无开放PR；建立codex/fem-time-mesh。
- 读取主线CI作业日志，主锁Debug/Release各43项、旧锁Release 10项均成功；独立审查核对原g0.json的100份源码哈希全部匹配。
- 本轮明确追加授权WSL2开发验证、CI云端复验。两套仓库依赖锁成功恢复；主锁Debug编译与链接检查通过。首次MPI预检被沙箱socket策略拒绝，沙箱外同命令预检与完整43项通过。
- G0补强真实J/R跨rank置换、已知离散解与真实Newton右端检查，三recipe物理量及压力规范对照；独立审查发现辅助PREONLY失败分叉并修复为共同拒绝。
- 当前Release/兼容检查、受控性能、新提交CI尚待完成。整体任务继续，未将G5/G1标记完成。

## 2026-10-30 — ARCH-01 — 通用 FEM 架构与上游学习规划

- 用户要求审查 EONSim-new，并进一步规划多网格/空间、边界、非一致界面、DoF/预条件、时间格式与高性能执行；明确暂不开发、不编译。本轮遵守此范围。
- 独立本地 checkout 从旧审查基线同步 main 至 `38a5e516ffe129d1b70c7c1bd8365deb5ded101a`，确认 PR #21 已合并；建立 `docs/general-fem-architecture-plan`。未修改只读 sources/。
- 静态阅读当前拓扑、Gmsh、DoF、FSI、COO、VTU 及 L1/L2；确认 Tri3 只是 Tet4 边界、体域仅 Tet4，BE/共形接口仍为实现边界；现有独立流体 COO 与分片 VTU 不重复安排为全新功能。
- 新增 `docs/architecture/GENERAL_FEM_ARCHITECTURE_PLAN.md`：明确拓扑/几何/空间分离、一般 BC、K/W 与非匹配传递、三类 DoF/PC 排列、约束后图、两类 generalized-α 与变步长 BDF2、输出和 native 批次执行；提供 G0–G8 依赖和验收候选。
- 新增 `docs/research/FEM_FRAMEWORK_LEARNING_2026-10-30.md`：访问官方文档和作者论文，覆盖用户列出的 20 组项目（Elmer 与 oomph-lib 分列）；给出具体迁移产物和不照搬部分，没有逐库源码全审或性能横评。
- 同步 L0/L1/L2、下一阶段设计、README、ROADMAP、进度与任务队列；纠正旧文档中持久 SNES/PC 的优先级，保留根据已有测量暂缓的决定。HPC-02 按 PR #21 标 done；所有新增实现任务 deferred，无新增 ready。
- 使用仓库 eonsim-knowledge-capture 技能，新增未发布草稿 `website/drafts/general-fem-dof-architecture.md` 与知识登记。证据为理论/设计和静态实现对应；lastVerifiedCommit 留空。非匹配稳定性、stage 相容性及 PC 语义为后续审阅重点。
- 文档检查：`git diff --check`；以 Python 标准库检查所有变更/新增文件仅为 Markdown、UTF-8、围栏闭合、相对文件/站点路径存在及新文件尾空白；通过。此为文档结构检查，未构建网站或声称渲染验证。
- 未运行 CMake、编译、CTest、MPI、求解器、性能实验、上游原型或网站发布。没有修改 src/include/tests/cases/scripts/CMake 等实现；历史数值与性能记录保持原有证据范围。
- 初次交付为本地文档草案，当时未创建 PR、未推送、未发布。下一步开发需用户另行启动；本轮不擅自领取候选。
- 用户后续明确要求将上述 16 份 Markdown 文档推送远程；交付目标为 origin 的 `docs/general-fem-architecture-plan` 分支，提交范围仍限这 16 份文档。保持不编译、不创建 PR、不合并 main、不发布网站；提交标识及交付结果以 Git 远程引用为准。

## 记录模板

~~~markdown
## YYYY-MM-DD — TASK-ID — 简短标题

- Branch / PR:
- Base commit:
- Objective:
- Changed files:
- Implementation:
- Commands executed:
- Tests and results:
- Performance evidence (if applicable):
- Knowledge draft:
- Limitations / unresolved issues:
- Next task:
~~~

## 2026-10-30 — HUB-01 — 持续研发与知识生产基础设施

- Branch / PR: feat/codex-continuous-development-workflow；[PR #3](https://github.com/saitoasukakawaii/EONSim-new/pull/3)。
- Objective: 为 EONSim 建立跨 Codex Task 的进度恢复、任务队列、会话记录和公开知识草稿模板。
- Changed files: CODEX_PROGRESS.md、CODEX_TASK_QUEUE.md、CODEX_SESSION_LOG.md、website/templates/ 下的文章模板、知识采集 Skill，以及 AGENTS.md 入口。
- Implementation: 定义状态语义、任务领取规则、SOLVER-01 下一任务边界和知识文章证据分级。
- Commands executed: 通过 GitHub 仓库接口创建/更新文档；未在 Codex Cloud 本机执行命令。
- Tests and results: GitHub Actions Website Build Check 在 PR #3 分支上成功；执行了依赖安装和 VitePress 生产构建。未运行 EONSim C++/PETSc/MPI 测试（本次未修改求解器）。
- Performance evidence: 无，本次未进行性能实验。
- Knowledge draft: 本次新增的是模板和工作流，不将其伪装成已验证的数值研究文章。
- Limitations / unresolved issues: 尚未实现自动从测试日志提取数据或自动发布；Codex 需按 Skill 和 AGENTS 规则执行草稿生成。
- Next task: SOLVER-01 PETSc NonlinearSession 生命周期审计。

## 2026-10-30 / SOLVER-01

- 基线：0828f41（PR #3 已合并）；分支 docs/solver-baseline-audit。
- 变更：新增 docs/research/PETSC_LIFECYCLE_AUDIT_2026-10-30.md、website/drafts/petsc-object-lifetime.md；更新 CODEX_PROGRESS、CODEX_TASK_QUEUE、本日志和 KNOWLEDGE_LOG。
- 审计：读取 linear_system/nonlinear_system/schur_solver、PetscOwner 及 fluid/solid/fsi 调用链；主 Vec/Mat 跨步保留，SNES 每次 solve 创建；Context 为借用栈引用；计时不完整覆盖构造析构。结论为需要额外测量，SOLVER-02 保持阻塞。
- 实际验证：仓库根目录 `git diff --check` 通过；`git diff origin/main -- src include CMakeLists.txt CMakePresets.json` 为空；website 目录 `npm run docs:build` 成功；仓库根目录 `test ! -d website/.vitepress/dist/drafts` 成功。
- 数值测试/性能实验：未运行；本任务为静态审计，不能据此声明性能收益。
- 知识沉淀：有，已按 eonsim-knowledge-capture 形成草稿并登记；证据为源码分析，数值与性能仍待测量。
- 下一步：人工审核审计报告，再开展固定 transient case 的重复 profiling。

## 2026-10-30 / SOLVER-01B

- 基线 c1c7508，PR #4 已合并；分支 perf/nonlinear-setup-baseline。
- 新增 scripts/benchmark_nonlinear_setup.py、docs/research/NONLINEAR_SETUP_BASELINE_2026-10-30.md、data/nonlinear-setup-2026-10-30 的结果 JSON/原始日志及 website/drafts/nonlinear-setup-baseline.md；更新进度、队列与知识日志。
- 仓库根目录激活 /workspace/.eonsim-tools/activate.sh；`cmake --preset release -DBUILD_TESTING=ON -DCMAKE_PREFIX_PATH="$CONDA_PREFIX" -DMPIEXEC_EXECUTABLE="$CONDA_PREFIX/bin/mpiexec" -DEONSIM_BLAS_LAPACK_PROVIDER=OPENBLAS` 和 `cmake --build --preset release --parallel 4` 退出0。
- `python3 scripts/benchmark_nonlinear_setup.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-nonlinear-baseline` 退出0：12个样本、2个预热、2个预处理成功；同rank输出差0。raw日志已入Git，不依赖临时目录恢复。
- `ctest --preset release -R '^(solver_failures|solver_failures_mpi|nonlinear_acceptance|nonlinear_acceptance_mpi)$' --output-on-failure`：4/4通过，耗时4.57秒；未运行全套。
- website目录 `npm run docs:build` 成功；草稿目录未进入dist。求解器及CMake未改。
- 知识沉淀：已生成测量边界草稿并登记。构造析构独立计时仍未完成，无持久化优化收益结论；SOLVER-02保持blocked。
- PR：https://github.com/saitoasukakawaii/EONSim-new/pull/7，等待人工审核。文档末尾空行已修正。

## 2026-10-30 / SOLVER-02

- 同步基线8c8a4af，PR #7已合并；分支perf/multistep-setup-profile。按最新队列将旧SOLVER-02“设计原型”表格描述统一为正文规定的测量任务。
- 新增scripts/profile_multistep_setup.py、docs/research/MULTISTEP_SETUP_PROFILE_2026-10-30.md、data/multistep-setup-2026-10-30的JSON及16份原始日志、website/drafts/multistep-setup-profile.md；更新进度/队列/知识日志。
- 仓库根目录激活已有环境后 `cmake --build --preset release --parallel 4` 退出0（no work to do，求解器相对前一基线无变更）。
- `python3 scripts/profile_multistep_setup.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-solver02` 退出0：fluid与elastic、1/2rank、各3次，共120接受步，同rank重复输出差0。
- 对实际日志的解析检查：有效10步通过；删除一条报告、负SNES reason、NaN三个错误输入均被拒绝。website目录 `npm run docs:build` 通过；草稿未进入dist。未运行全套CTest，未改求解器/容差。
- 使用eonsim-knowledge-capture流程形成测量草稿；原始证据入Git。结论为暂缓持久化原型，首步成本不可外推后续；独立构造析构成本仍未知。
- 下一步：人工审核；未来只有业务需求或更大规模测量支持时重新打开优化任务。

## 2026-10-30 / SOLVER-05

- 同步 origin/main 至 a48de95，确认 PR #8 已合并；分支 fix/linear-solve-ksp-lifetime。SOLVER-02 标记 done。
- 修改 src/algebra/linear_system.cpp、include/eonsim/linear_system.hpp，将 KSP owner 从成员移到单次 solve 作用域；新增 tests/verify_linear_lifetime.cpp 和两项 CTest 注册。代码提交 c47f00d。
- 更新进度、队列、本日志、KNOWLEDGE_LOG；使用 eonsim-knowledge-capture 生成 website/drafts/linear-solve-ksp-lifetime.md，记录理论、实现、数值/生命周期验证及性能证据缺失。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target verify_linear_lifetime --parallel 4` 成功。旧实现 `ctest --preset release -R '^linear_lifetime$' --output-on-failure` 预期失败，提示 solve 返回后 PC 未释放。
- 修复后 `cmake --build --preset release --target eonsim verify_linear_lifetime --parallel 4` 成功；`ctest --preset release -R '^(linear_lifetime|linear_lifetime_mpi|poisson_verification|poisson_parallel)$' --output-on-failure` 4/4 通过（14.05 秒）。
- `cmake --build --preset debug --target verify_linear_lifetime --parallel 4` 成功；`ctest --preset debug -R '^linear_lifetime(_mpi)?$' --output-on-failure` 2/2 通过。每 rank 四次 PC 创建/销毁，覆盖成功、失败、恢复和 owned/ghost 解。
- 未运行全套 CTest；未测量内存字节数、耗时收益或大规模并行。下一步人工审核本修复；持久化优化保持延期。
- 文档验证：`git diff --check`、五份 Markdown 的解析/围栏配对检查通过；`npm run docs:build --prefix website` 成功；`test ! -d website/.vitepress/dist/drafts` 成功，草稿未进入生产构建。
- Markdown 检查最初直接导入 markdown-it 失败（非顶层依赖）；改用已安装 VitePress 的 createMarkdownRenderer 后五份文件解析及围栏检查通过，无新增依赖。

## 2026-10-30 / SOLVER-03

- `git fetch origin` 同步 main 至 717b25b；`gh pr view 9 --json state,mergedAt,url` 确认已合并；SOLVER-05 标记 done。新分支 docs/newton-scaling-spec。
- 领取原队列 SOLVER-03 的审查/规格任务；审查 FieldAcceptance、Context、convergence、NonlinearSystem::solve、Schur 配置和非线性验收测试。现有字段尺度仅用于验收，未实现完整 Newton 坐标变换。
- 新增 docs/research/NEWTON_SCALING_SPEC_2026-10-30.md、scripts/verify_newton_scaling.py、website/drafts/newton-scaling.md；更新 CODEX_PROGRESS、CODEX_TASK_QUEUE、本日志及 KNOWLEDGE_LOG。
- `python3 scripts/verify_newton_scaling.py` 通过：两组尺度，Newton/Jv、非零约束、试探点/加权 merit、逆预条件作用和 Schur 恒等式；两个错误公式负对照均被识别。规格/脚本提交 6dc2baf。
- 使用 eonsim-knowledge-capture 形成算法草稿，明确当前实现、候选理论、独立验证及性能证据缺失。未修改 C++、CMake、case 或容差；未运行 C++ 构建/CTest、MPI 或性能实验。
- SOLVER-03 标记 review，新增 deferred 的 SOLVER-03B 并列明实现验收条件与触发需求；不将候选规格描述为已实现能力。
- `python3 -O scripts/verify_newton_scaling.py` 同样通过；`git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功；草稿目录未进入 dist。核对 src/include/CMake/cases 相对 origin/main 无差异。
- 相对链接检查最初误将既有 `/learning/cfd` 网站路由视为本地文件；限定为相对文件链接后通过，未修改已有网站路由。

## 2026-10-30 / SOLVER-04

- `git fetch origin` 同步至 a4957e0；`gh pr view 10 --json state,mergedAt,url` 确认合并，SOLVER-03 标记 done。分支 perf/schur-mesh-profile。
- 新增 scripts/profile_schur_mesh.py（79eb826）、docs/research/SCHUR_MESH_PROFILE_2026-10-30.md、data/schur-mesh-2026-10-30 的 38 个证据文件、website/drafts/schur-mesh-profile.md；更新进度/队列/会话/知识日志。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target eonsim --parallel 4` 退出 0（no work to do）。
- `python3 scripts/profile_schur_mesh.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-schur-mesh` 退出 0：2/4/6 subdivisions、1/2 rank、6 个直接参考及 18 个 Schur 重复；最大字段差 4.0834e-12。
- 对实际日志解析的有效输入、缺报告/NaN/负 SNES reason 三种变异，以及节点集合/非有限值/超阈值差三个负对照检查均通过。
- 版本采集中的非提升权限 mpiexec --version 输出 pmix socket 警告但返回版本；实际 MPI 测量在允许本地通信的执行权限下全部成功。
- 使用 eonsim-knowledge-capture 形成 benchmark 草稿；完整计时范围与限制见报告。未修改求解器、CMake、既有案例或容差；未运行全套 CTest、FSI 或跨节点测试。下一步人工审核；大网格/粗层进一步测量需明确需求。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功，草稿未进入 dist；src/include/CMake/cases 相对 origin/main 无差异。

## 2026-10-30 / SOLVER-04B

- `git fetch origin` 同步至 f1e9594；`gh pr view 11 --json state,mergedAt,url` 确认已合并。SOLVER-04 标记 done，新分支 feat/solver-level-dimensions。
- 修改 src/algebra/nonlinear_system.cpp，使用 KSPGetOperatorsSet 后读取已有 A 的全局/本地行列；修改 tests/verify_schur.py 验证各层尺寸及顶层分布总行数；更新 L2 离散诊断契约。实现提交 124bed3。
- 更新 CODEX_PROGRESS、CODEX_TASK_QUEUE、本日志和 KNOWLEDGE_LOG；按 eonsim-knowledge-capture 生成 website/drafts/solver-level-dimensions.md，区分元数据理论、实现、数值验证与性能证据缺失。
- 激活 `/workspace/.eonsim-tools/activate.sh` 后，`cmake --build --preset release --target eonsim verify_solver_failures --parallel 4` 成功；`ctest --preset release -R '^(schur_verification|solver_failures|solver_failures_mpi)$' --output-on-failure` 3/3 通过（36.97 秒）。Schur 含四类问题的 1/2/4 rank 对照。
- `cmake --build --preset debug --target verify_solver_failures --parallel 4` 成功；`ctest --preset debug -R '^solver_failures(_mpi)?$' --output-on-failure` 2/2 通过（2.36 秒），包含初态收敛和故障路径。
- 未跑全套 CTest、性能基准；不宣称诊断零开销。尚无 P 尺寸/逐层非零元或累计成本；未设置 A 的哨兵分支未单独构造测试。下一步人工审核，本次不调参。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功；草稿未进入 dist。CMake 和 case 未更改。

## 2026-10-30 / HPC-01A

- 同步 origin/main 至 615af36，确认 PR #12 已合并，SOLVER-04B 标记 done；分支 feat/assembly-phase-timers。
- 修改 src/algebra/nonlinear_system.cpp：累计正常完成评价的 callback/failure_sync/assembly_finalize/constraint 时间；在 SNESSolve 后冻结，沿用原有报告规约。修改 tests/verify_schur.py 检查有限非负及外层时间界；更新 L2 计时契约。实现提交 fff4895。
- 更新进度/队列/本日志/知识登记；按 eonsim-knowledge-capture 生成 website/drafts/assembly-phase-timers.md。HPC-01A 是有界实现增量，HPC-01 的纯 kernel/插入分离与重复测量仍未完成。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target eonsim verify_solver_failures --parallel 4` 成功；`ctest --preset release -R '^(schur_verification|solver_failures|solver_failures_mpi)$' --output-on-failure` 3/3 通过（37.19 秒），含 Schur 四类问题的 1/2/4 rank 对照。
- `cmake --build --preset debug --target verify_solver_failures --parallel 4` 成功；`ctest --preset debug -R '^solver_failures(_mpi)?$' --output-on-failure` 2/2 通过（2.28 秒）。
- 未修改物理方程/容差/CMake/案例；未跑全套 CTest 或性能实验；新增时钟读取开销未知。失败评价的细分成本未纳入，详见契约。下一步人工审核，不能将计时接线报告为完整瓶颈结论。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功；草稿未进入 dist。

## 2026-10-30 / HPC-01B

- 同步 origin/main 至 7f2bc51，`gh pr view 13 --json state,mergedAt,url` 确认合并；HPC-01A 标记 done；分支 perf/assembly-phase-baseline。
- 修改 scripts/profile_schur_mesh.py，新增四阶段及 assembly/ghost 汇总、缺字段/阶段越界/拒绝计数检查；脚本提交 d1708e1。
- 新增 docs/research/ASSEMBLY_PHASE_BASELINE_2026-10-30.md、data/assembly-phase-2026-10-30 的 32 个日志/JSON 文件、website/drafts/assembly-phase-baseline.md；更新进度、队列、会话与知识日志。按 eonsim-knowledge-capture 整理证据边界。
- 激活 `/workspace/.eonsim-tools/activate.sh`；`cmake --build --preset release --target eonsim --parallel 4` 退出 0（no work to do）。
- `python3 scripts/profile_schur_mesh.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-assembly-baseline` 退出 0：6 个直接参考、18 个 Schur 样本，无拒绝评价；最大节点字段差 4.0834e-12。
- 有效日志解析及缺 callback/NaN/阶段越界/非零 domain_rejections 四个负对照均通过。本轮未修改 src/include/CMake/cases，未跑全套 CTest 或时钟开销 A/B。
- n=6 callback 中位数由单 rank 25.487 ms 降至双 rank 13.779 ms，最终装配由 0.138 ms 增至 9.609 ms；不把最终装配全解释为网络时间。完整设置与范围见报告。下一步人工审核，HPC-01 未完成的分离与规模测量仍延期。
- `git diff --check`、六份 Markdown 解析/围栏/相对链接检查通过；`npm run docs:build --prefix website` 成功，草稿未进入 dist；已核对 src/include/CMake/cases 相对 origin/main 无差异。

## 2026-10-30 / HPC-01C

- 同步 main 至28c60da，PR #16已合并。用户在上一轮提出 transient fluid/FSI 1/2/4 rank 候选后要求继续，本轮执行该有界任务；分支perf/transient-assembly-profile。
- 修改scripts/profile_multistep_setup.py：新阶段校验/统计、1/2/4 rank参数、主输出按owner/原始节点ID跨rank对照、独立固体输出检查及逐步/逐次分布。新增研究报告、26份日志/JSON证据、知识草稿；更新进度/队列/本日志/知识登记。
- 激活/workspace/.eonsim-tools/activate.sh后 `cmake --build --preset release --target eonsim --parallel 4` 成功（no work to do）。
- `python3 scripts/profile_multistep_setup.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-transient-phases --ranks 1 2 4` 成功：18次运行、180接受步，主输出跨rank最大差6.6614e-16，同rank重复差5.5512e-16。
- 运行启动版本82081d5；确认FSI单独输出固体场后，用0f90585的verify_solid_outputs对全部已生成输出补验，最大跨rank差2.4287e-17。f92e57b的detailed_statistics补充18个逐次和60个逐步统计。无需重新运行物理求解；版本来源分别记录在JSON。
- 有效日志与缺phase/NaN/非零拒绝计数/超外层时间四个负对照通过。采用eonsim-knowledge-capture整理草稿，保留统计与计时边界。未修改C++/CMake/案例，未跑全套CTest；未测量时钟开销。
- 下一步人工审核，性能结论为暂缓重构，必要时按目标规模补更细事件；没有擅自激活其他deferred任务。
- `git diff --check`、六份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功，草稿未进入dist；src/include/CMake/cases相对origin/main无差异。

## 2026-10-30 / HPC-01D

- 同步origin/main至2e7e9a9，PR #17已合并，HPC-01C标记done。用户在上一轮提出独立流体kernel/插入分离建议后要求继续，本轮执行该有界任务，分支feat/fluid-element-timers。
- 修改src/physics/fluid.cpp，新增显式-fluid_element_report开关、单元kernel/Vec+Mat插入时间、逐rank/逐步单元计数；关闭时无单元时钟读取。新增tests/verify_fluid_element_report.py及CMake注册，更新README和L2契约。实现提交1722265。
- 新增website/drafts/fluid-element-timing.md；按eonsim-knowledge-capture区分理论/代码/验证与性能证据缺失；更新进度、队列、会话和知识登记。
- 激活/workspace/.eonsim-tools/activate.sh后，`cmake --build --preset release --target eonsim --parallel 4`及Debug同命令成功。
- `ctest --preset release -R '^fluid_element_report$' --output-on-failure` 1/1通过（21.34秒）；Debug同测试1/1通过（22.73秒）。每个构建覆盖三案例、1/2 rank、开关共12次求解；主物理字段/动量残量保持、计时有限非负、报告和单元计数有效。
- 本轮不跑全套CTest或性能基准；未修改方程、容差或PC策略。计时包含最终验收/原始反力回调，不可与callback_seconds直接相减；整个失败solve不输出，拒绝评价的专门计时路径未新增测试。FSI/ALE与owned/remote插入仍未分离。
- 下一步人工审核，无新增ready任务；如继续测量需明确目标规模并考虑计时扰动。
- `git diff --check`、六份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功，草稿未进入dist；README新增选项说明及契约链接已核对。

## 2026-10-30 / HPC-01E

- 同步main至f232b07，PR #18已合并；HPC-01D标记done。用户在上一轮提出计时开关扰动测量后要求继续，本轮执行该候选；分支perf/fluid-element-overhead。
- 新增scripts/benchmark_fluid_element_report.py（1423b99）：每配置预热两模式，5对交替顺序，固定solver_report，仅切换fluid_element_report；检查字段、逐步迭代轨迹、单元计数及报告完整性。
- 新增研究报告、data/fluid-element-overhead-2026-10-30的41份日志/JSON、website/drafts/fluid-element-overhead.md；更新进度/队列/会话/知识登记。使用eonsim-knowledge-capture标注证据及局限。
- 激活/workspace/.eonsim-tools/activate.sh后 `cmake --build --preset release --target eonsim --parallel 4` 成功（no work to do）。
- `python3 scripts/benchmark_fluid_element_report.py --executable build/release/eonsim --mpiexec /workspace/.eonsim-tools/env/bin/mpiexec --work /tmp/eonsim-element-overhead --repeats 5` 成功：1/2/4 rank，共30个计量样本/15对，另6次预热。最终字段同rank差3.3307e-16、跨rank差4.4409e-16，逐步迭代轨迹及计数一致。
- 有效报告及缺报告、重复报告、NaN、错误单元计数、关闭模式出现报告五个负对照通过。
- 单rank配对solve变化中位数+3.56%，范围-0.10%至+27.68%；2/4rank范围跨零。详细耗时/统计口径见报告；不将负值称为加速，不作纯时钟成本归因。
- 未修改C++/CMake/案例，未跑全套CTest；仅小规模独立流体，完整HPC-01未完成。下一步人工审核，无新增ready任务。
- `git diff --check`、六份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功，草稿未进入dist；src/include/CMake/cases相对origin/main无差异。


## 2026-10-30 / QA-01

- 同步origin/main至25e49af，PR #19已合并；HPC-01E标记done。用户继续上一轮日志校验候选，分支fix/profile-log-validation。
- 实现7b91030修改scripts/profile_multistep_setup.py、scripts/profile_schur_mesh.py，新增tests/test_profile_validation.py与CMake注册。原因/计数严格整数校验、计时和残量有限非负、报告/步顺序配对、稳态必需统计字段及逐rank根节点/重复层级校验。
- 修复前负对照发现NaN原因、非法迭代计数及缺失根节点等误接受；修复后 `python3 tests/test_profile_validation.py` 与 `python3 -O tests/test_profile_validation.py` 均11项通过。真实数据覆盖18份瞬态、18份稳态、36份开关测量/预热日志，共72份。
- 激活/workspace/.eonsim-tools/activate.sh后，`cmake --build --preset release --target eonsim --parallel 4` 与Debug同命令均成功；CMake重新生成，C++无需重编译。
- `ctest --preset release -R '^profile_log_validation$' --output-on-failure` 与Debug同命令均1/1通过（各0.09秒）。未执行全套CTest或新MPI/性能实验，测试读取已提交证据，不重新证明数值正确性。
- 更新进度/队列/本日志/知识登记；使用eonsim-knowledge-capture新增website/drafts/profile-log-validation.md，区分浮点语义、实际实现、解析器验证与性能未测量。
- 待人工审核；无新增ready任务。此解析协议限于现有固定十步、零拒绝评价的测量，不作为任意PETSc运行的通用成功判据。
- `git diff --check`、五份Markdown解析/围栏/相对链接检查通过；`npm run docs:build --prefix website`成功（3.37秒），dist未包含草稿或模板；未修改src/include/cases。

## 2026-10-30 / HPC-02

- 用户要求依据规划设计并完成预计 5 小时以上任务，然后创建 PR。核对指定 EONSim-new 与旧 EONSim 是不同仓库，在独立 checkout 从 `24eae62`（PR #20）建立 `codex/fluid-cached-coo`；旧工作区及未提交修改未改动。
- 任务队列登记 7–9 小时工程工作量估计及具体验收；实现 `ceea57d` 增加独立固定网格流体 `-fluid_coo`，一次准备图、复用数值缓冲，在错误同步后调用 collective COO 更新。默认装配、物理公式、停止条件、残量/反力与 FSI 路径保留。
- WSL Ubuntu24.04/GCC13.3/PETSc3.19.6/OpenMPI4.1.6 下 Release 和 Debug 完整构建成功。新增 COO 代数测试 1/2/4 rank 通过；真实流体每构建 87 个命令，最大字段差 5.190625707029994e-12。
- Debug 6/6 通过；Release 首轮 7/8 通过，`solver_failures_mpi` 60 秒超时在独立未修改基线构建中相同复现。共享求解器的 Schur/FSI、真实缩步、计时及日志回归额外 4/4 通过。不宣称整个 CTest 通过。
- `benchmark_fluid_coo.py` 完成两档网格、1/2/4 rank、36 次计量及12次预热；所有18对迭代轨迹一致，字段最大差 6.661338147750939e-16。装配中位变化约 -45% 至 -62%，solve 约 -8% 至 -44%，wall 约 -11% 至 0%；多组 wall 范围跨零，明确记录准备和内存成本。
- 原始测量使用 `ceea57d`；后续仅修正跨 Windows/WSL Git status 的 CRLF 元数据噪声。58 个编译源文件归一化哈希与提交相符，可执行哈希与测量一致；原始 JSON 未改写。
- 独立 deep review 对 `ceea57d` 为 PASS，无阻塞发现。报告、原始日志、字段证据、审查记录及 source provenance 已归档；按 eonsim-knowledge-capture 添加 website/drafts/fluid-coo-assembly.md 并登记知识日志，未发布网站。
- 代码、验证、性能测量和评审完成后创建 [PR #21](https://github.com/saitoasukakawaii/EONSim-new/pull/21)，人工决定是否合并；无新增 ready 任务。创建后的提交仅登记 PR 链接与 review 状态。此任务不提供 FSI/ALE/残量 COO、GPU、多节点或大规模扩展证明。
- 交付前代码/文档的 `git diff --check`（排除原样归档的日志）、8 份 Markdown 围栏/相对文件及站点路由链接检查、JSON 证据解析、测量脚本语法检查通过。两份构建日志保留 CMake 原始输出中 8 行尾空白，完整 diff 检查因此会报告这些空白；不改写原始证据。后续文档/元数据修改未改变已审查的 src/include/CMake/tests；未重复运行数值测试，未构建或发布网站。


## 2026-10-30 / INFRA-01

- 用户明确授权14–18小时估计工程量的云端基础设施任务；未将估计写实际耗时。仅远程Linux，main基线38a5e51，PR #21已核实合并，纠正HPC-02状态。独立分支codex/infra-reproducible-mpi-ci。
- 读取根AGENTS/L0、工程总纲/路线/构建/进度队列、并行/状态/求解契约及两份历史报告。用户指定architecture下L0路径不存在，实际入口在根目录。
- 新增environments两份SHA256显式锁及版本说明，scripts/cloud恢复/运行/证据入口、核心GitHub Actions、runtime探针；复用presets/provider和34项原测试（新增后35项），添加选择/rank标签。
- src/algebra/nonlinear_system.cpp修复旧PREONLY局部PC失败，在诊断前统一布尔失败标志，保留负枚举原因；本地失败树不额外collective。已共同传播的fatal callback早退后更换trial Vec，隔离PETSc残留读锁，COO图/矩阵保持。
- tests/verify_solver_failures.cpp覆盖三个诊断模式、fatal Jacobian、accepted不变及恢复；tests/verify_checkpoint.cpp补破坏指针前读者同步；tests/verify_runtime.cpp验证real/double/int32及实际MPI运行。
- 未改main隔离构建在PETSc3.19.6下原60秒超时（60.07秒），最小纯PETSc复现rank0 reason4、rank1 reason-11；上游3.20.0已加入归约。保留最小复现源码，详细归因见INFRA-01报告。
- 最终锁在/tmp/infra-pristine恢复；随后在/tmp/eonsim-cold-I3bOY2显式隔离所有包缓存、独立检出c07f94a，完成干净恢复/构建/7项故障回归，再重复restore与7项测试通过；云机4CPU/32GiB。旧hwloc CPUID启动问题及容器CMA限制分别适配，不混同应用死锁。
- 两套环境mpi-failure各7/7通过；主环境Debug全35/35通过474.17秒、Release全35/35通过409.08秒。d3f69d1分支CI三任务全部成功（41060786421），均上传诊断产物。最终入口/文档提交仍须head CI通过，尚无正式PR。
- 首轮主环境全套暴露COO Vec锁与checkpoint竞态并修复；CI四rank失败进一步定位OpenMPI5忽略旧映射变量，模拟两槽位前后验证后加入PRRTE设置及四rank预检。
- 独立审查指出负PC枚举、嵌套cgroup和超时残留，均修正并复核无源码阻塞；真实MPI超时清理与多层后代终止/reap通过。数值Python优化明确禁用。
- 使用eonsim-knowledge-capture新增未发布草稿，更新README/L2契约/BUILD_AND_VALIDATION/进度队列/知识登记。Markdown八文件解析及链接、网站构建3.94秒、草稿排除检查通过。精简机器证据见INFRA-01报告旁data目录；正式PR状态待验收后更新。


## 2026-10-30 / BRANCH-01 — 已合并分支清理与主线整合

- 用户明确授权删除已完全合并的 18 个远程分支，并审查剩余 6 个、优先架构与 CI、合入 main；明确禁止编译。以 38a5e51 为起点，在 integration/review-branches-2026-10-30 逐次整合。
- 18 个 tip 均为原 main 祖先，保存 SHA 后按精确旧值保护原子删除，复核只剩 main 与 6 个待整合分支；没有删除未审查引用或强制改写 main。
- 架构 16 份文档完整保留。CI 审查到 d3f69d1 后，推送前发现远程新增 c07f94a/5745fd3，继续审查并保留环境恢复与证据增量。其余旧分支按整合报告保留有效补充、维护主线状态，不复活过时任务。
- 新修正：锁定 ABI 的 runtime 探针改为云端显式启用；JUnit 解析按名称严格匹配并识别 error；文档检查支持 source-only 与 CRLF；网站 CI 增加模板哨兵；修正文档与真实 CMake target 的不一致。
- 工作目录为 EONSim-new checkout。执行 python -B tests/test_cloud_evidence.py（6 项通过）、node website/scripts/check-content.mjs --source-only（10 文件通过）、Python AST、bash -n、YAML/JSON/锁结构检查、Markdown 围栏和本地链接检查、git diff --check 及祖先关系核验。
- 本轮没有 CMake 配置/编译、CTest、MPI、数值/性能或网站构建；没有启动 GitHub 数值 CI。读取的历史成功状态只对应原分支 d3f69d1。最终推送含 [skip ci]，不把已有证据当作最终集成通过。
- 使用 eonsim-knowledge-capture 更新原 INFRA-01 草稿和知识登记，分开原分支执行记录与本次脚本验证；没有新性能证据，草稿未发布。
- 完整源提交、删除清单、冲突取舍和验证边界见 BRANCH_INTEGRATION_2026-10-30.md。INFRA-01 最终集成验收待执行，G0–G8 均 deferred；不自动开始新开发或构建。

- 推送前又检测到源 CI 分支新增 1497137/787372e：保留 PR #22 与 5745fd3 成功 CI 的证据、以及 ob1 单机传输适配。只读 GitHub 确认 CI 41063030121 三个 job 成功；核对 OpenMPI 官方 sm/vader 命名并检查脚本语法，未执行 MPI。最终整合范围以 branches.json 中的六个 tip 为准，INFRA-01 保留最终集成验收待完成。

- 第一次推送前置检查发现 main 已并发合入 PR #22（281699c2e86eb4eb0f9d0db7ca1bc891892c90dd），因此未执行推送；复核其唯一新增提交为已审查 CI tip 的 merge commit，纳入主线历史后树内容不变。继续采用正常快进推送与 [skip ci]，未覆盖并发提交。


## 2026-10-30 / FEM-G0A — DoF 与 FSI 分块详细设计（本地 review）

- 用户授权预计 10 小时工程量的有界设计/参考验证任务；预算不作实际耗时。开始 fetch origin/main 后 HEAD 与远程均为 `f44c3e0e81f090637f6f21a7b63a9d12d3e30424`，工作区干净；GitHub 开放 PR 查询为空。新建本地分支 `docs/fem-g0a-dof-design`，队列单独登记 in_progress。
- 阅读当前 AGENTS/L0、进度/队列/分支整合、通用 FEM 规划、L1/L2 离散/FSI/状态/并行、INFRA-01/HPC-02 证据边界；逐项审计 DoF/constraint/fields/嵌套 Schur、checkpoint/输出和既有测试源码，未执行既有数值检查。
- 新增 [专题设计](../architecture/FEM_G0A_DOF_AND_BLOCK_DESIGN.md)，固定提交源码映射、六项契约、三种配置/14 行示例、父编号公式、PETSc 3.19.6/3.23.7 官方 tag 静态核对、容量复杂度与 C++ 切片。总纲只加链接和 G0A 范围说明。
- 新增 docs/research/fem_g0a/ 下参考模型、unittest 与只读文档/语法检查器。模型没有求解器/进程调用，全部标准库；Fraction 手算 oracle 含非对称矩阵、非零 lifting、K/W 不同、置换与 dt 更新，另覆盖三树/刚体/1/2/4 模拟分区/空 local block/错误编号。
- 实际执行 `python3 -B docs/research/fem_g0a/test_reference_model.py`：首轮 18/18；交叉审查新增真实语义 alias 键、三层子矩阵元素 oracle 和单孩子拒绝后，最终 20/20 通过。原始输出及源码哈希见 [证据目录](../research/data/fem-g0a-2026-10-30)。这是分区索引逻辑验证，不能称 MPI 测试。
- 同一作者交叉核对源码/契约/手算/反例，修正普通保留行 Dirichlet 与 FSI 消元的区别、结构内部 BE 系数避免双乘、joined ID 和含 rank 的 fingerprint、checkpoint 缺失 reduced 排列版本、旧 PETSc prefix 长度与 Schur 内部 KSP 的接线范围；不冒称独立多人审查。
- 官方源码直接临时下载超时，改用浏览工具读取版本 tag 源码；未安装依赖。`check_artifacts.py` 首次把既有站点路由误当文件路径，补上源码路由解析后通过；没有修改旧文章链接来规避检查。
- 实际执行 `python3 -B docs/research/fem_g0a/check_artifacts.py`（Python AST、7 份 Markdown 围栏/本地文件与站点路由、固定 EONSim SHA/路径/行号、14 份审计源码哈希）、`git diff --check`，并检查新文件空白和生产路径零差异。最终输出见 [checks.txt](../research/data/fem-g0a-2026-10-30/checks.txt)。检查不证明远程链接存活或网站渲染。
- 使用 eonsim-knowledge-capture 的 algorithm-note 模板新增 [未发布草稿](../../website/drafts/dof-semantics-and-nested-fsi-blocks.md)，登记 KNOWLEDGE_LOG；分开理论、基线实现、独立参考验证与性能未测量。值得沉淀的知识是 K/W 区别、共享代表唯一归属与父编号空间，待人工审查。
- 未执行配置/编译器/编译、CTest、MPI、EONSim、性能基准或网站构建；未修改生产 C++、CMake、既有数值测试/算例、CI 或 sources/；未 commit、push、创建 PR、合并或发布。FEM-G0A 转 review（本地交付），FEM-G0 整体和其它阶段仍 deferred，INFRA-01 review 与其真实数值验收状态不变。
- 未解决事项为人工审查、真实 PETSc/MPI 接入及物理验收；下一最小候选 G0-B1 仅将现有语义适配到 IS、保持 root 编号与默认行为，未启动。

## 2026-10-31 / FEM-G0A — 后续提交推送授权

- 用户明确要求将改动推送到远程；提交目标为 `docs/fem-g0a-dof-design`，保持 FEM-G0A review、FEM-G0 deferred 和 INFRA-01 原验收状态。
- 提交前 fetch 确认 origin/main 仍为 `f44c3e0e81f090637f6f21a7b63a9d12d3e30424`，远程目标分支尚不存在；工作区仅含此前 FEM-G0A 交付文件。
- 核对两个工作流：数值工作流 push 仅匹配 main/codex/**，网站工作流 push 仅匹配 main，均不匹配本设计分支；提交另加 `[skip ci]`。不创建 PR、不合并、不运行或重跑构建。
- 更新当前状态中的“本地未提交”说明，保留 2026-10-30 的基线、检查证据与会话历史；不改变参考模型、生产代码或知识草稿的未发布状态。


## 2026-10-31 / BRANCH-02 — 合并 G0A 与清理远程分支

- 用户明确授权合并远程分支并清理多余分支。基线 f44c3e0；6 个历史分支已完全合并，新增 docs/fem-g0a-dof-design 的 b674d5a 多 1 个提交；远程无开放 PR。
- 在 integration/merge-cleanup-2026-10-31 审查合入 G0A 设计、标准库参考模型与历史证据，重跑 20 项参考测试通过；源码、CMake、数值测试、算例和 CI 未变化。
- 检查工具首次执行因 GBK 解码 UTF-8 失败，启用 UTF-8 后发现 14 份源码仅因 CRLF 检出被误判修改。显式 UTF-8 读取并仅归一化 CRLF 后全部基线哈希匹配；代码及其他空白变化的负例仍被识别。没有改写审计源码或旧证据。
- 更新 G0A 的设计交付状态和本轮合并清理清单；G0 生产实现及 G0B/G5/G1 未执行，INFRA-01 最终集成验收仍 review。此次是维护已有知识成果，不新增重复知识文章，原草稿未发布。
- 实际检查：20 项参考测试、AST/Markdown/固定源码引用/14 份哈希、LF/CRLF 与修改负例、Git 差异和祖先关系；结果见 BRANCH_CLEANUP_2026-10-31.md 与对应 checks.txt。
- 远程更新采用原子正常快进 main 加 7 个精确 SHA 保护的分支删除；推送前再次核对各 tip，保留 main 与完整可追溯历史。提交使用 [skip ci]，本轮未配置或编译项目、未运行 CTest/MPI/性能/网站构建。

## 2026-10-31 / FEM-INTEGRATION — 基线恢复与G0检查点

- 用户已明确解除纯设计限制，授权G0B→G0→G5→G1整体实现/测试/推送及按规则主线交付。main复核为72a3356，无开放PR；分支codex/fem-g0-g5-g1。旧快照未提交G0A工作已stash与归档保护。
- 在4CPU/32GiB云环境复用锁恢复3.23.7与3.19.6；移走引用失效临时路径的旧构建目录，从空产物重建。基线主环境35/35各模式、兼容7/7通过。
- 实际修改：DoF语义头、field/reduced布局、显式slot K/W映射、PC树与SNES接入、配置/CMake；新增pc_plan及pc_restart测试，复用schur/time_retry脚本；文档/队列/知识草稿同步。没有G5/G1能力。
- 当前G0主环境 `scripts/cloud/run.sh 3.23.7 {debug,release} all /workspace/eonsim-cloud` 分别43/43通过；兼容mpi-failure 10/10及三recipe/重启7项通过。最后补验状态见实施记录。精简结果、来源清单和原始日志位置见FEM_INTEGRATION_VALIDATION.md。
- quantity首次失败定位为原始压力块AMG粗层问题，固定使用Jacobi后通过；没有改变物理方程、精度门槛或超时。独立审查指出并修正rank局部输入错误、子KSP数组生命周期、Schur命名options漏检、零初态配置绕过与PC负例假通过条件。
- 权限：仓库API报告push可用，main保护规则读取403（integration缺少该端点权限）；尚未尝试合并或绕过规则。正式PR等待全部阶段完成。
- 下一步：保存并推送经验证G0检查点，检查CI，随后统一时间映射/accepted历史，从BE迁移进入G5。预计工程量不是实际耗时。

- 接续验证：主锁Release完整43项通过；旧锁三recipe补验3项通过。主锁Debug及旧锁Release新增奇异诊断失败/恢复10项均通过。性能两算例/1、2、4rank/四模式/三重复共72样本，最大场差3.307e-12，直接解在此小问题中solve中位数较低。证据入g0-supplement.json及pc-recipes-benchmark.json。
- 使用知识采集Skill生成真实装配置换与PC验收草稿并登记；尚未发布。当前准备提交推送检查点并进行新提交云端CI，之后进入G5。

## 2026-10-31 / FEM-INTEGRATION — G5与G1最终集成

- 用户明确授权WSL2真实构建/MPI，并由云端CI复验；继续使用两套Linux显式依赖锁、原presets与恢复入口，没有另建构建系统。实际资源24逻辑CPU、约32GiB，编译并发4、每rank数学库单线程。
- G5依次推送c923387（独立BDF2）、bab4fda（ALE/FSI BDF2）、25e0945（独立一阶/二阶alpha）、2fcd2fd（共同stage ALE/FSI alpha）；四个检查点云端三环境CI均成功。局部/整体切线、速度/压力/结构与网格时间阶、能量/阻尼、接口运动与功、事件/拒绝/完整历史重启见阶段JSON，不能将BE启动或参考ODE单独当作FSI精度证据。
- G1增加独立规范化导入层、Gmsh4.1 ASCII子集、Tri3/P1与Quad4/Q1相容混合二维标量Poisson/扩散；贯通命名材料和D/N/Robin、纯Neumann、METIS/owned/ghost/AIJ、G5时间与checkpoint、VTU/PVTU/PVD。二维分区版本3，三维保留版本2及旧Tet4读取。
- 独立审查发现并修复导入partition tags静默丢弃、名称维数检查、线性PC局部失败集体传播、不连通域零空间和restart输出时间片覆盖。新布局配置独立声明固定语义/存储策略；不把PC树变化或诊断MatPermute称为生产排列。
- 数值检查包括独立解析Q1质量/刚度、角点反转、外部编号/方向、三拓扑patch/MMS/畸变/边界法向通量、双材料、纯Neumann、空间与时间加密、1/2/4rank重启和真实失败恢复。对称矩阵成对计算消除极小步长舍入导致的假非对称；未降低rank、放宽容差或延长失败超时。
- 配置补充前主锁Debug/Release各59项及兼容13项通过；这份中间证据保留于build/pre-layout-policy-evidence。配置补充后的最终清单为主锁各60项、兼容13项，运行结束结果与源码哈希归档fem-final.json；不将中间结果冒充最终通过。
- 使用eonsim-knowledge-capture生成二维规范化/双线性单元草稿并登记，所有文章仍在website/drafts。当前环境没有node，本地网站命令未运行成功；网站构建及草稿隔离交由PR云端检查。Markdown本地链接检查通过。
- 最终主线与PR状态以后续交付记录为准；G2/G4仅实施必要子集，其余阶段不关闭。未测二维性能，也未把G0原检查点72样本性能结果归到新源码。

- 最终配置补充后Debug60/60、Release60/60、兼容13/13全通过；CTest墙钟574.87/213.11/18.50秒。fem-final.json保存109份源码哈希和实际清单，独立审查无确定源码阻塞；准备最终G1提交、PR及云端验证。


## 2026-10-31 / FEM-INTEGRATION — 主线交付完成

- 最终提交9e5a1ed经独立复核：109/109源码哈希一致，实际inventory/JUnit为60/60/13，所有命令退出0，无超时/失败/跳过，日志及二进制哈希匹配。
- PR #23云端三环境同样60/60/13通过（41199182613），push CI成功（41199162462），网站及草稿隔离成功（41199182529）。云端4CPU约16GiB，未混同WSL2资源。PR合并预览300a7544与功能提交tree一致。
- GitHub按expected_head_sha=9e5a1ed正常merge成功，main为9cc2e102e8e32f929de1c9a790c1ae527b931fa2。未绕过检查、未强推、未覆盖他人修改。
- 完成状态、队列、用户指南和交付JSON归档；G0B/G0/G5/G1及INFRA-01关闭，G2/G4只含必要子集，其余阶段保持deferred。知识文章仍为草稿。
- 完成状态归档为文档变更；生产源码及测试保持已验收版本，最终远程同步与main CI由交付时再次核对。

## 2026-10-31 / CI-DEPENDENCY-POLICY — 主力 PETSc 与按需兼容验证

- 按用户要求，将 PETSc 3.23.7 确定为日常主力构建版本；PETSc 3.19.6 不再参与每次 Push/PR 的自动编译和链接检查。
- 更新 `AGENTS.md`：规定第三方差异优先通过能力检测、官方版本宏和集中兼容层处理；需要 Patch 时必须版本限定、可追溯、可重复应用；仅在相关兼容路径变化时做针对性验证。
- 更新 `.github/workflows/core-numerics.yml`：日常矩阵保留 PETSc 3.23.7 Debug/Release；3.19.6 仅在手动触发并勾选 `run_legacy_petsc` 时执行 Release `mpi-failure` 专项检查。
- 更新 `docs/development/BUILD_AND_VALIDATION.md`，使构建说明与工作流一致。保留 3.19.6 锁文件和运行脚本，未删除历史环境。
- 在工作流文件完成调整前，首个内容提交曾短暂触发旧矩阵的一次过渡 Push CI，其中 PETSc 3.19.6 Release 专项 job 已通过；随后最终工作流改为独立可选 job，当前 PR CI 中 3.19.6 job 明确 skipped，不执行编译/链接。最终 3.23.7 Debug/Release CI 正在验收；不将过渡运行解释为未来日常策略。

## 2026-10-31 / DEV-PROCESS-POLICY — 长期知识积累规则

- 用户明确提供“EONSim 持续知识积累要求”，将其固化为根目录 `AGENTS.md` 的项目级规则；Codex 新 Task 应读取该文件执行，不要求用户每次重复粘贴。
- 规则要求每项实质任务记录重要错误与根因、真实测试证据，更新 `CODEX_SESSION_LOG.md`、`CODEX_PROGRESS.md`、`CODEX_TASK_QUEUE.md` 和 `KNOWLEDGE_LOG.md`；有复用价值的技术成果使用 `eonsim-knowledge-capture` Skill 形成 `website/drafts/` 草稿。
- 明确边界：普通 typo/纯格式/机械小改动不强制生成文章；没有复用技术成果时不制造草稿；文章未经人工审核和 PR 合并不得发布。
- 同步更新进度和任务队列，将本项记为 review，并更新知识索引。相关文档提交：AGENTS `54cba2e`、进度 `04b334a`、队列 `389fc5b`；后续会话日志和知识索引提交由本条记录的 Git 历史追溯。
- 验证范围：通过 GitHub 仓库内容接口复读并检查目标文件，确认规则文本和链接路径存在；本任务没有修改 C++/CMake/数值测试，没有运行编译、CTest、MPI 或性能测试。PR #24 的 GitHub Actions 结果以实时 Checks 为准；未完成项目不标记为通过。
- 未生成技术文章草稿：本次交付是研发流程规范，不是新的算法、数值方法或可复用技术错误分析；该决定已登记在 `KNOWLEDGE_LOG.md`。


## 2026-10-31 / DOCS-01 远程交付授权

用户追加要求推送并合并到远程。再次 fetch 后 origin/main 仍为 a508e3d；89 份 Markdown 的静态检查与 git diff --check 通过。准备提交并通过 PR 合并；远程检查结果待实际完成后记录，草稿不转正式栏目。

## 2026-10-31 / DOCS-01 远程交付完成

- 功能提交 `40f87c0989cde56d085f3b05eea31b90116dc9e9` 已推送，并通过 [PR #25](https://github.com/saitoasukakawaii/EONSim-new/pull/25) 合并为 `be21882b589735ff449b472e8efc76555cffb9fb`；没有强推。合并 tree 与功能提交一致，已用 `git diff --exit-code 40f87c0 be21882` 核对。
- [PR 数值 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41207324586) 实际日志确认：PETSc 3.23.7 Debug/Release 各 60 passed、0 failed、0 skipped；测试对象为合并预览 `8e835ecb5b9475e2e70f802b9944554e13f4e2cb`。PETSc 3.19.6 手动兼容 job 本次 skipped，不计为通过。
- [网站 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41207324560) 的生产构建与草稿/模板隔离均成功。此为远程补验，前序本地缺少 Node 的记录仍成立。没有新增性能结论，也没有将草稿转为正式栏目。
- 本地 main 已快进至合并提交；仅补记任务完成状态和上述证据链接。本补记不改源码/网站，静态复核后使用 `[skip ci]` 提交，避免重复数值套件；不把前述结果标记为补记提交的新运行。


## 2026-10-31 / TEST-POLICY-01 — 增量验证与历史证据复用

- 用户明确要求仅改约束，不开发和编译项目，并停止每次开发结束后的全量测试及无关历史测试重跑。源码基线 `3df1c31f8f3b6c995e00368782a94971a92371c3`；本次变更仅为 Markdown；用户随后授权本地提交，分支 `codex/incremental-validation-policy`，未推送。
- 静态检查发现旧规则虽写“最小验证”，仍在基础设施交付、公共接口和最终集成处要求 `all`，且“代码继续变化”重跑条件未限定影响范围。已统一 AGENTS、L0、构建与验证、路线及 Goal 流程：只检查新增/受影响行为，复用未受影响的历史通过证据，全量仅在用户明确要求时运行。
- 历史证据保留原提交、命令/环境/结果或归档链接；本次未运行须明确标注，不计作当前提交新通过。受影响路径不能仅用改动前的通过记录代替必要检查。
- `.github/workflows/core-numerics.yml` 仍配置 Push/PR 的主锁 Debug/Release `selection: all`；本次按“仅改约束”限定未修改工作流、测试或脚本，没有实现 CI 自动选测，也没有触发远程验证。
- 验证仅限文档阅读、`git diff --check`、改动 Markdown 本地链接目标检查和差异范围核对；没有运行 CMake 配置、编译、CTest、MPI、性能实验或网站构建。无数值结果或性能结论，未生成知识文章。
- 进度、队列及知识索引同步；任务为 review（本地分支交付，未推送、未合入 main），不改写历史交付记录。
