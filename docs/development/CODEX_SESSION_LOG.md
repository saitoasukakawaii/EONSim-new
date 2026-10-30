# EONSim Codex Session Log

本文件记录有实质代码、算法、验证或知识产出的开发会话。只记录事实，不写无法复现的“已优化”“性能显著提升”等结论。

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
