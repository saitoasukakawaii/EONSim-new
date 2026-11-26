# FSI-PC-04：联合速度 GAMG 与参考旋转粗空间

本轮从已合并 PR #53 的 `main@858f021a34ff5bd178287430d8cd45e52ec19f48` 接续，
交付 [PR #54](https://github.com/saitoasukakawaii/EONSim-new/pull/54)。
实现和本地验收已完成；最终实现/验证驱动为
`88e6c3359b742735877177eb4584b987caae1790`，所有实现及修复均先同步远程，后构建或执行。
本页记录固定来源的实验，不将后续文档提交、证据复用或 PR 合并计作新的数值执行。
合并状态以该 PR 的 GitHub 记录为准。

## 实现与采用结论

- 在完整流固联合速度块上增加可选 PETSc GAMG，保留流固非对角项，默认 PREONLY
  应用一次 V-cycle。外层 FGMRES、ASM/ILU 平滑、GMRES/Jacobi 粗解及数值更新有明确配置。
- 为现有 twolevel 增加 `rigid` 粗空间：在 owned 语义行上由真实固体参考位置构造旋转，
  保留流体常数和 body 标量；约束恒等行置零，缺分量及空 rank 合法，相关/零模态剔除。
- 坐标经过完整/缩减布局传递，界面 alias 仅保留一个代表；旧镜像弹性例采用与固体核一致的
  `x=1+thickness*(1-x)` 参考域映射。参考坐标不改变残量、Jacobian 或物理接受标准。
- GAMG 使用所有活动标量行上的单个常数近模态。`gamg + rigid` 明确拒绝；不把不规则
  reduced scalar AIJ 强行设为三分量块，也不将此实现宣称为完整向量弹性 AMG。
- 默认复用插值时仍刷新 Galerkin 数值和平滑器。独立代数检查直接比较更新前后的
  `P^T A P`；全恒等矩阵使用精确 Jacobi。main/inner/upper 的选项与语义一致。
- 修复 GAMG 层级创建前调用 `PCMGSetCycleType` 的顺序错误、故障注入标记与 MPI 错误输出
  交错，以及短命令外部计时的 timeout 轮询偏差。计时驱动的超时/取消清理有独立控制。

本轮**不切换现有默认 recipe 或粗空间**。旋转模式在细网格减少迭代，计时中位数改善，
但三次配对范围跨零；粗网格没有速度收益。GAMG 在两套小网格均没有显示速度优势。
两条新路径均保留为显式选项，不能仅依据更多模态或更多层级断言优化有效。

```text
# 完整速度 GAMG
-pc_recipe hybrid -pc_plan_schur_approx nodal
-pc_plan_velocity_solver gamg -pc_plan_velocity_coarse_space constants

# twolevel 固体参考旋转富集
-pc_recipe hybrid -pc_plan_schur_approx nodal
-pc_plan_velocity_solver twolevel -pc_plan_velocity_coarse_space rigid
```

## 固定来源与环境

| 来源 | 实际执行 | 结果与边界 |
|---|---|---|
| `e0703466d73bfa1cf240eef201739c91383e6bca` | 首次实现构建及代数选测 | 构建成功；3 个代数检查均因 GAMG 初始化顺序失败，原件保留 |
| `a7e0e2845f191e11729458aeaaaa25afc815bd5a` | 修复初始化顺序、增量构建、代数和物理选测 | 3+4 个 CTest 全部通过；初始动脉 20 runs 通过；两种新路径的实际缩步/重启通过 |
| `1ab19ea6dabe081dace1448a3e5661d4a96e0bb2` 驱动 / a7e0 二进制 | 阻塞式精确外部计时、8 个短程准入、7 个进程控制 | 均通过；不使用该中间单次计时宣称性能收益 |
| `88e6c3359b742735877177eb4584b987caae1790` | 故障标记刷新、取消清理、重编 eonsim、受影响 COO 检查 | 1/1 CTest 与最终 9/9 进程控制通过 |
| 同一 88e6 来源/二进制 | 最终 quick、full、robustness | **78/78 runs，656 接受步，1,282 次线性修正**；独立重放通过 |

原 a7e0 二进制 SHA256：
`e9874a768deba2d5cf350ec4f43859bf19ce0430aa1f2ed76bb07fabbdf98e43`。
最终 88e6 二进制 SHA256：
`c57ab409a125d759fd51513cf5c03024feec2f67a0f224fd1aa40cc87be1cf09`。
归档的两个 binary-source 收据分别保留实际来源，旧二进制被替换后没有声称重新计算其摘要。

环境为 PETSc **3.23.7 / Release**、Open MPI **5.0.8**、GCC **15.3.0**、CMake **4.4.5**，
共享 AMD EPYC 9V74 主机、可用 CPU 0–8。性能运行串行调度，MPI 显式绑定 core；
OMP/OpenBLAS/MKL 均为 1 线程。COO 故障检查另显式使用 2 rank × 2 element threads。
精确环境、配置与二进制摘要在归档的 `build/fsi-amg-validation/environment.json`。

## 本地定向验收

| 检查 | 来源与结果 | 实际覆盖 |
|---|---|---|
| `pc_plan_mpi1/2/4` | a7e0，3/3 | 24 行独立制造矩阵；缺分量、约束行、body、4 rank 中两个空 owner；旋转空间及平移原点不变性；退化模态剔除；真实多层 GAMG、数值 Galerkin 更新、PREONLY/PCApply、全恒等回退、选项及 collective 元数据拒绝 |
| `fsi_tube_rcr` | a7e0，通过 | 新 twolevel-rigid 与 GAMG 连续运行、检查点、重启和 RCR 历史；最大场差约 `1.98e-11`，重启差约 `2.01e-12` |
| `fsi_block_efficiency` | a7e0，通过 | 两网格、10 模式共 20 次短程；全部真实残量和五场直接解对照通过 |
| `pc_recipe_hybrid`、`domains_verification` | a7e0，2/2 | 原 recipe 与不同流固域布局兼容路径 |
| `verify_time_retry.py` 两种新选项 | a7e0，两次入口均通过，每次 1/2 rank | 实际失败后 `.04` 初始尝试缩至接受 `dt=.00125`，同小步长直接解、32 步完成、检查点与重启、耗尽重试及 fatal 分类 |
| `fsi_coo_verification` | 88e6，1/1，8.97 s | 默认/COO、线程、四类第二批故障；保持 `team=2,batch=1` 和实际线程检查；fatal 不重试、不发布接受步 |
| 驱动离线检查 | e070 的 29 项 + 88e6 的 9 项控制通过 | 实际 dt/pressure-stage/rank/PC/字段拒绝；阻塞成功、非零退出、超时部分日志、TERM/KILL、父驱动取消及 timer 启动失败清理 |

局部最终验收采用 **7 个 a7e0 通过检查 + 1 个 88e6 受影响检查**，不是在 88e6 上重新跑了 8 项。
a7e0→88e6 的生产变化只有故障注入诊断刷新，不影响已通过的代数/RCR/retry 路径；
这些项目**复用本轮此前通过证据，88e6 本地未重跑**。未运行本地全量、Debug 或 PETSc 3.19.6。

重启 helper 没有把每个子进程 stdout 保存到磁盘。真实 cutback 次序、耗尽重试和 fatal 分类由
已执行 helper 的断言及完成摘要支持；独立重放只直接证明保留的全程/参考/重启 VTU、拓扑和
checkpoint 一致。最大独立 float-array 差 `3.2685e-12 < 2e-8`，不将这些原件描述为完整日志重放。
成功代数测试的 JUnit stdout 受 CTest 截断；退出状态与无条件执行的源码检查共同界定覆盖。

## 动脉轨迹与参数范围

最终三个阶段均使用干净的 88e6 来源，直接解与候选采用相同输入、分区、时间步和压力 ramp。

| 阶段 | 运行数 | 接受步 / 线性修正 | 最大真实残量/门槛 | 最大五场相对峰值差 |
|---|---:|---:|---:|---:|
| quick | 8 | 32 / 64 | 0.502037 | `3.3161e-12` |
| full | 40 | 384 / 768 | 0.601025 | `1.0017e-11` |
| robustness | 30 | 240 / 450 | 0.501009 | `2.6171e-9` |

每次修正仍要求 `true_residual <= 1.00001*max(1e-23,1e-10*rhs_norm)`，
每场相对直接参考峰值差仍要求 `<=2e-6`，并检查正收敛理由和每步报告。未放宽任何门槛。
五场为流体速度、压力、网格位移，以及壁速度、位移。两个网格为 1,027 DoF/1 rank/natural
与 3,024 DoF/2 rank/RCM；GAMG 两例实际均为 2 层，最粗矩阵分别 14/39 行。

full 包括 8 条完整 32 步轨迹，外加各配置一次四步预热和三次交替四步测量。
robustness 在细网格上比较直接解、twolevel 常数、twolevel rigid、GAMG 与
added_mass 单次流体响应。`rho_s/rho_f = 1,0.1,0.01`，`rho_f=1060`，
`dt=1/32,1/128` 秒；六组配置各 5 次运行、8 个接受步。
使用 generalized-alpha、`rho_infinity=0.5`，压力幅值 80、原 1 秒 ramp；
两种 dt 的物理终点分别为 0.25/0.0625 秒，不能当作相同物理时长的精度比较。
密度比变化也不等于已量化的附加质量数或任意高 Re 鲁棒性证明。

另外保留 a7e0 的 20 次筛选与 1ab 的 8 次中间准入；连同最终阶段，共有 **106 次已通过动脉运行**。
这些不是 106 次独立性能样本。初始 e070 的远端失败保留为失败，未混入通过计数。

## 性能结果与选择

基线为 `twolevel_onecycle`。下表时间取同一交错轮次的候选/基线百分比变化，
报告三个配对的中位数及最小/最大；预热排除。32 步迭代数来自完整轨迹，
不能把四步重复计时写成重复完整 32 步计时。

| 网格 / 候选 | 32 步外迭代（基线→候选） | 四步 wall 配对中位变化 [最小,最大] | 四步 linear 配对中位变化 [最小,最大] |
|---|---:|---:|---:|
| 1,027 / rigid | 2,992→2,913 | +1.03% [-1.24%,+15.14%] | +6.99% [-2.08%,+39.11%] |
| 3,024 / rigid | 5,445→5,050 | -10.79% [-13.14%,+0.44%] | -15.10% [-18.45%,+4.04%] |
| 1,027 / GAMG | 2,992→3,076 | +5.35% [-2.21%,+5.58%] | +9.72% [-1.41%,+14.17%] |
| 3,024 / GAMG | 5,445→5,683 | +4.83% [+4.34%,+8.54%] | +7.05% [+3.33%,+11.69%] |

“配对变化的中位数”和“各组中位数的比值”不同：细网格 rigid 的两者 wall 分别
为 -10.79% 与 -8.42%。全部原样本、两个统计量及重算脚本均归档，未挑选更有利的一种。
刚体粗模态的细网格迭代减少约 7.25%，但共享主机三次样本不足以建立稳定通用加速。
GAMG 的层级能力和数值正确性已验收，当前小网格的收益为负，保留可选配置。

wall 使用包含启动和退出的阻塞 child wait，独立 watchdog 负责截止时间，排除日志解析；
包含很小的 watchdog/file-close 收尾。`linear_seconds` 为各 KSP 区间的 rank 最大值，
包含 PC setup/内部响应；`setup_seconds` 只是 nonlinear 初始化，不能叫作全部预条件建立时间。
不同阶段的 rank 最大值不能相加为 wall，迭代数下降也不自动意味着总耗时下降。

## 失败与修复没有抹去

1. 初次直接调用不可执行的 `build/locked.sh` 得到权限错误；后续通过 `bash build/locked.sh` 使用原环境。
2. e070 在 GAMG 创建层级前调用 `PCMGSetCycleType`，PETSc 返回 wrong order。
   a7e0 将 V-cycle 默认配置交由 setup 时应用；代数 3/3 和相关物理路径随后通过。
3. 初轮远端 run [45739848423](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45739848423)
   最终 workflow 为 cancelled，但其数值命令已经返回 exit 8：**50 通过、6 失败**。
   五个测试属于上述 GAMG 顺序错误；第六个 COO 失败是正确标记被 stderr 前缀拼接，
   `records()` 的行首匹配漏读。88e6 在进入 collective 错误传播前显式刷新标记；原解析门槛保持。
4. `subprocess.run(timeout=...)` 的等待轮询影响亚秒算例 wall。1ab 改用阻塞等待，
   88e6 再补父 SIGTERM 与 timer 启动失败清理。原始计时作为历史原件保留，性能结论仅用最终重复样本。

初轮完整 CI artifact 的 SHA256 为
`4070e9e8002f87ef4f9bb65c8a0ac5993beb6659f1be130823dad60b0f386e73`。
本地归档保留原始 job log、六项失败输出、原交错日志和摘要；没有重复纳入完整 CI zip。
精确 PR head、CI synthetic merge checkout、命令及分类见归档中的 `ci-initial-failure.json`。

## 源码 CI 与最终提交的区别

88e6 源码的 [Core numerical validation 45741570996](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45741570996)
和 [Website Build Check 45741571017](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45741571017)
均为 completed/success。三个 core jobs 与 `Build VitePress` 四项必需检查均成功；
本次实际新执行 **56/56 Release CTests、10/10 Python 检查**，历史数值复用为 0。
Debug 与 PETSc 3.19.6 的手动 job 未执行，不计入通过数。

CI 检出 PR synthetic merge `3d83542bfd8211900e6fe429e22163e526cd31c2`，父提交为原 main
和 88e6，tree `76b429a0eec70921d286849854948e559e782bfc` 与 88e6 完全一致。
精确 job 状态、测试清单、命令及日志摘要见 [源码 CI 收据](ci-source-88e6.json)。
这不预先代表后续证据/文档提交的检查状态；合并还必须核验最新 PR head 的四项必需检查。
没有修改分支保护、CI 规则、测试映射或数值门槛。

较早 a7e0 的 56/56 Release、10/10 Python 和 receipt jobs 也成功，
但其 workflow 最终为 **cancelled**；[原记录](ci-a7e0.json)保留该区别，不写作整个 workflow 通过。
后续文档提交若复用 88e6 数值证据，只是复用通过来源，不是再执行 56 项。

## 实际命令与可复查材料

仓库根目录执行；`build/locked.sh` 固定依赖、线程环境及 MPI 设置。

```bash
bash build/locked.sh cmake --build build/cloud-3.23.7-release --target eonsim verify_pc_plan --parallel 2
bash build/locked.sh ctest --test-dir build/cloud-3.23.7-release -R '^pc_plan_mpi(1|2|4)$' --output-on-failure
bash build/locked.sh ctest --test-dir build/cloud-3.23.7-release -R '^(fsi_tube_rcr|fsi_block_efficiency|pc_recipe_hybrid|domains_verification)$' --output-on-failure
# 88e6 的受影响复验；之前先以同一正则 ctest -N 核对清单
bash build/locked.sh ctest --test-dir build/cloud-3.23.7-release -R '^fsi_coo_verification$' --output-on-failure
```

最终三阶段使用以下实参；日志与每个 MPI command、输入/分片摘要保留在 results JSON 和归档中。

```bash
bash build/locked.sh python tests/verify_fsi_block_efficiency.py \
  --executable build/cloud-3.23.7-release/eonsim \
  --mpiexec /workspace/scratch/ae740e1dde63/EONSim-new/.cloud/petsc-3.23.7/bin/mpiexec \
  --work build/fsi-amg-final --stage quick \
  --modes twolevel_onecycle twolevel_rigid gamg_constants
bash build/locked.sh python tests/verify_fsi_block_efficiency.py \
  --executable build/cloud-3.23.7-release/eonsim \
  --mpiexec /workspace/scratch/ae740e1dde63/EONSim-new/.cloud/petsc-3.23.7/bin/mpiexec \
  --work build/fsi-amg-final --stage full \
  --modes twolevel_onecycle twolevel_rigid gamg_constants \
  --quick-results build/fsi-amg-final/results-quick.json
bash build/locked.sh python tests/verify_fsi_block_efficiency.py \
  --executable build/cloud-3.23.7-release/eonsim \
  --mpiexec /workspace/scratch/ae740e1dde63/EONSim-new/.cloud/petsc-3.23.7/bin/mpiexec \
  --work build/fsi-amg-robustness --stage robustness
```

实际重试入口的两个调用另使用 `--recipe hybrid`，分别设置
`--velocity-solver twolevel --velocity-coarse-space rigid` 与 `--velocity-solver gamg`，
work 分别为 `build/fsi-amg-validation/retry-twolevel-rigid` 和 `retry-gamg`。
归档保留这些输入和输出、两个 JUnit 阶段、最终 COO JUnit、全部 campaign JSON/log/VTU、
输入网格及 partition、源快照、独立 replay 脚本/结果、环境和最终二进制。

- [原始证据归档](evidence.tar.xz)：8,777,620 bytes，SHA256
  `d714a522f383522aa4961c7e6b98caf6c1ab46584c38cd3dbc6317a9169325e9`。
- [逐文件清单](archive-manifest.json)与[校验摘要](evidence.sha256)：6,314 个成员的
  SHA256/大小/模式以及排序/归一化元数据均已完整验证，含 68 份版本化源/依赖快照。
- [独立完整轨迹重放](independent-final-full.json)、[参数对照重放](independent-final-robustness.json)、
  [最终故障日志复核](independent-final-coo.json)、[重启字段审计](independent-retry-audit.json)。
- [性能原样本及配对统计](performance-summary.json)、[初始失败审计](ci-initial-failure.json)、
  [a7e0 CI 记录](ci-a7e0.json)、[最终二进制](binary-source.json)与[环境](environment.json)。

归档使用仓库相对路径；`package-evidence.py --verify` 可不依赖 Git/PETSc 校验成员完整性。
源码/数值独立 replay 还包含 Git blob/祖先检查，应在对应仓库 checkout 下执行，
不把单纯归档哈希校验等同于重新运行求解器或重新测量 wall。

## 验证边界

证据限于上述共享单机、性能 1/2 rank 与代数/部分正确性 4 rank、小型共形 P1 约束消元 FSI。
没有多节点、GPU、百万自由度、任意密度/Re 的普适收敛或网格无关复杂度结论。
默认 `reuse_interpolation=true` 的真实数值更新已覆盖；`false` 强制重建未单独执行实验。
原始日志和场可重放不等于可以从日志重新测量过去的 wall；计时只保留当时观测。

算法依据为固定版本 [PETSc v3.23.7 agg.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/gamg/agg.c)
及 [gamg.c](https://github.com/petsc/petsc/blob/v3.23.7/src/ksp/pc/impls/gamg/gamg.c)。
[知识文章](../../../../website/drafts/fsi-reference-modes-and-gamg.md)保留为未发布草稿。
