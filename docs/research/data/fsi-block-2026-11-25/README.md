# FSI block preconditioner：实现与验收记录

本轮补齐当前共形单体 FSI 的完整流体结构 Schur、联合速度两层校正及独立
Schur main/inner/upper 路径。实现、数值验证和性能结论分别记录。
**本地验收及源码 CI 已通过；PR #49 待用户审核确认，未合并。**

- 基线：`f50a4a4338689c9a065bee30ae4a7f3f52c5002e`，已合并的 #48。
- 生产求解器最后改动：`b8ac03ab162715fca24009f18903da8116ef4ecc`。
- 最终验证源码：`b52281d7585ead08e545f29f8d83eca9177e7eac`。
  从 b8 到 b522 仅改测试与执行预算，`src/`、`include/` 没有差异。
- 用户要求的顺序：每次待测源码先推送，再运行对应验证；由用户确认合并。
- [PR #49](https://github.com/saitoasukakawaii/EONSim-new/pull/49)
  保持 `manual-review`、`no-automerge`。

使用选项、数学定义和适用范围见
[配置指南](../../../development/FSI_BLOCK_PRECONDITIONER.md)；
算法推导见[未发布草稿](../../../../website/drafts/fsi-nested-schur-twolevel.md)。

## 1. 验证来源

| 范围 | 结果 | 来源与说明 |
|---|---|---|
| 最终本地 Release | 8/8 通过 | b522 干净工作树，实际重跑，见 `validation.json` 的最后一个 stage |
| 代数 oracle | 3/3 通过 | b8 的 MPI 1/2/4；生产求解器不变，本地沿用原收据 |
| 通用 PC restart | 1/1 通过 | b8，覆盖原 recipe 及新增 FSI 路径；本地沿用原收据 |
| 验证器正反对照 | 23/23 通过 | ff81e5b；12 个正常输入接受，11 个损坏输入拒绝，没有额外求解 |
| 远端 Release 数值 | 53/53 通过，0 失败、0 跳过 | b522 的 PR 合并预览，重新执行的增量选测 |
| 远端 Python | 58/58 通过 | 选测、收据和相关几何/分析辅助检查 |
| 必需 CI | 4/4 成功 | Select affected checks、Release、Record incremental evidence、Build VitePress |

本地有效验收共 12 个不同 CTest 名称：本轮最后重跑 8 项，加上同一生产源码的
3 项代数检查和 1 项 restart 证据。没有把历史复用写成新运行，也没有把 23 项
纯数据检查、58 项 Python 与 CTest 混为一个通过数量。

[数值 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45606963270)
执行提交为 `630be2000e946417683410ad5d9793fc6951e740`；其 Git tree
`65bb8e65d5e3d896dc3382043cd05aa189db73d8` 与 b522 完全一致。
[网站 CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45606963330)
也已成功。[API 状态与原始数值 notice](ci-source-b522.json)保留该对应关系。
Debug 和 PETSc 3.19.6 未执行，工作流中的两个手动 job 为预期 skipped。

## 2. 实际检查了什么

代数验收使用独立稠密消元核对完整流体结构 Schur，明确区分包含压力反馈的
消元与仅速度消元；另用手写语义分组核对插值和 Galerkin 粗矩阵。
测试覆盖两次数值更新、独立 main/inner/upper、USER 压力矩阵共享、非连续分量、
恒等约束行、空 owned rank、全恒等退化、零残量时非法配置拒绝，以及故障后的恢复。

物理检查包括刚体、弹性双域及 Neo-Hookean FSI 的直接解全场对照，原始矩阵真实
残量，RCR 端口/电容状态，同分区重启，以及真实 Newton 失败后的回滚缩步。
外层 Jacobian、非线性接受条件、时间积分及物理参数没有为预条件器修改。

新增 RCR 路径的专项范围是 **generalized-alpha、2 rank、两步及分步重启**。
原有 BE/BDF2/generalized-alpha 直接解回归继续运行；不将它们描述成所有新 recipe
与所有时间格式的交叉矩阵验证。

| 新 RCR 路径 | 相对直接解的字段最大绝对差 | 重启字段差 | 真实残量检查 full / start / resumed |
|---|---:|---:|---:|
| `added_mass` | 5.8240910428e-9 | 0 | 4 / 2 / 2 |
| `twolevel` + nodal | 1.8453738537e-11 | 0 | 4 / 2 / 2 |

这里使用原测试的绝对差门槛 `2e-8`。它与下一节动脉管的相对峰值误差是不同指标。

## 3. 两套动脉管的完整轨迹

固定原有 20 mm 管输入档及 SHA256，在 1027 DoF / 1 rank 和 3024 DoF / 2 rank
上分别运行 direct、physics_lower、coupled_diagonal、coupled_nodal、
twolevel_nodal、added_mass。每种模式完整运行 32 步，保存每四步的两域节点场。
输入采用 rho=1060、rho_s=1100、mu=0.004、E=400000、nu=0.45、dt=1/32、
80 Pa 光滑压力加载及 generalized-alpha；精确输入随归档保留。

**12 条完整轨迹均通过：384 个接受步、768 次线性修正。**
每种模式另做一次四步预热和三次交错四步计时，合计 **60 次运行、576 个接受步、
1152 次线性修正**，全部通过。

每次修正重新计算原始矩阵的残量，要求

\[
\lVert J\delta x-b\rVert_2\leq1.00001\max(10^{-23},10^{-10}\lVert b\rVert_2).
\]

还用四组物理行的 RMS 和实际行数重构该范数。所有运行的最大
“真实残量 / 目标”比为 **0.5600385064**，没有以 PETSc 收敛标记代替真实残量。

五类场为流体速度、压力、网格位移，以及壁速度、位移。
以同分区直接解为参考，按 owned 节点 ID 比较全部保存时相，指标为

\[
\epsilon_q=\frac{\max_{t,i}|q(t,i)-q_{\rm direct}(t,i)|}
 {\max_{t,i}|q_{\rm direct}(t,i)|}.
\]

门槛为 `2e-6`，所有五场和所有运行的最大值为 **1.0712628633e-11**。
已检查 324 份完整轨迹 volume VTU 的文件新鲜性，均来自本轮运行；60 份原始日志
的 SHA256 均与运行记录一致。精确每次修正及每次运行指标见
[arterial-results.json](arterial-results.json)。

## 4. 性能：新路径没有在这些小算例上提速

下表为一次预热后的三次交错四步计算中位数。每个四步样本有八次 Newton 线性修正。
线性时间取求解器报告的线性区间，墙钟还包含进程启动、装配和输出等开销。
所有模式保持相同物理、输出和准确性要求；没有速度通过门槛。

| 模式 | 1 rank 线性时间 / s | 2 rank 线性时间 / s | 2 rank 墙钟 / s | 2 rank 外层迭代 |
|---|---:|---:|---:|---:|
| direct | 0.059785 | 0.303184 | 0.767447 | 8 |
| physics_lower | 0.384190 | 3.015633 | 3.627327 | 766 |
| coupled_diagonal | 0.177158 | 1.032484 | 1.619708 | 646 |
| coupled_nodal | 0.159509 | 0.928008 | 1.521485 | 645 |
| twolevel_nodal | 0.588150 | 3.795757 | 4.378000 | 563 |
| added_mass | 6.839241 | 45.805123 | 46.404431 | 354 |

twolevel 和 added_mass 降低了外层迭代次数，但内层工作增加，总耗时更长。
此规模上 direct 最快；迭代候选中 coupled_nodal 更快。完整 added_mass 32 步墙钟
分别为 59.382126 s 和 408.075013 s，不把较少迭代写成加速。

本地为单机 Linux、锁定 PETSc 3.23.7 / Open MPI 5.0.8 / GCC 15.3.0，
OMP/OpenBLAS/MKL 各一线程；动脉 MPI 命令请求按核映射和绑核。
收据记录 cpu_budget=9、可用内存约 10.45 GB；这是当前执行环境，不能据此宣称
独占硬件或多节点扩展性。原始 argv、依赖锁和各样本耗时均保留。

## 5. 保留的失败与修改理由

1. **d9f5857 / 0f16d56 代数失败。** 首轮 0/3，增加诊断后定向复测 0/2。
   首轮收据 `dirty=true`，保留原值。MPI BJacobi 误用隐式 Schur 的原因是创建 GAMG
   后 `useAmat` 状态残留；修复明确默认使用已装配 P。全恒等案例的压力 GAMG
   问题由严格对角 P 默认采用 Jacobi 解决。原断言未放宽，b8 的 3/3 通过。
2. **b8 物理批次为 5/7。** 双 rank added_mass 在旧的 130 s 执行预算内只完成
   10/32 步；不能将它记为整段通过。四个定向性能候选也在各自 80 s 预算内超时，
   全部保留且未采用。为完成新增覆盖，最终完整 added_mass 的执行预算为 600 s，
   整项 fsi_tube 为 1200 s；32 步、误差及真实残量标准不变。
3. **两次 Newton 的缩步 fixture。** 原外层 RTOL/ATOL=1e-9/1e-13 下，fixture
   在后续步失败；线性字段残量诊断及仅收紧外层精度的复测支持精度不足的判断。
   失败尝试未输出最终非线性字段残量，不能把线性残量当作该量的直接测量。
   只把此测试的外层线性精度收紧至 1e-11/1e-15，
   保留两次 Newton 上限和物理条件，即完成原 32 步轨迹及 1/2 rank 重启对照。
   全局求解默认值没有因此修改。
4. **防止假通过。** 补充 VTU 数组名称/数量/长度/有限性检查；RCR 对 full、start、
   resumed 全部核对真实残量及报告数量。缺字段、截断数组、NaN、无限 RHS 和
   缺报告的负对照均拒绝。23 项检查不计作新的 MPI 物理求解。

全部阶段的提交、命令、退出码及通过/失败/超时分类见
[validation.json](validation.json)；原始日志在归档中，不覆盖为成功记录。

## 6. 归档与复现

[evidence.tar.xz](evidence.tar.xz) 为 7,180,452 bytes，保存 2,557 份数据文件，
另有三份清单/生成文件。SHA256 为
`03990426bfc193038353da504f38119cd006cf8ea7fd95743cb1ccb66f4bccdf`，
也见 [evidence.sha256](evidence.sha256)。归档保留原始 `build/…` 路径。

保留了历次收据、失败诊断、最终 60 份日志及每次修正历史、12 条完整动脉轨迹
的全部保存体字段、RCR/重启/缩步相关字段和 CSV、输入固定档及验收源码。
省略可重建的分区/网格副本、二进制依赖、原生 checkpoint、重复边界 VTU，以及
短计时样本的重复 VTU；短样本日志、指标和 CSV 仍保留。原始非动脉 tube 回归
保留日志/CSV/指标，其重复 volume VTU 不在此精简包中。

归档可用标准库脚本复核，不需要 PETSc、MPI 或重新求解：

```bash
python3 docs/research/data/fsi-block-2026-11-25/replay.py
```

脚本检查归档摘要和每个文件的哈希/大小，再从存档日志及体字段重算残量、范数
一致性和完整轨迹场差；不执行归档中的任何代码。这是存档审计，不作为额外数值运行。

**推送后的独立复核已通过。** 脚本及归档先推送为
`370358f3c9210eec8a1699dcd1db2c67f7702d74`，随后执行上述脚本并写出
[复核结果](replay-result.json)。2,557 份文件逐一匹配；重新解析 60 份日志中的
1,152 次线性修正，并从 288 份完整轨迹体 VTU 重算 96 个保存状态的 480 项
字段对照。最大残量比和相对场峰值差均与原记录一致。脚本来源及摘要另记于
`validation.json` 的 `archive.replay`。

重新运行原算例时，先按仓库说明恢复锁定环境，在仓库根目录建立选测文件：

```bash
cat > /tmp/fsi-block-tests.json <<'JSON'
{"tests":["fsi_tube","fsi_tube_rcr","pc_added_mass_retry","pc_twolevel_retry","pc_recipe_retry","time_retry_verification","pc_recipe_hybrid","schur_verification"]}
JSON
scripts/cloud/run.sh 3.23.7 release explicit .cloud /tmp/fsi-block-tests.json
```

本轮实际使用已有锁定环境前缀；完整命令位于原收据。代数验收可将 JSON 的 tests
换为 `pc_plan_mpi1`、`pc_plan_mpi2`、`pc_plan_mpi4`。不要把文档示例当作额外执行记录。

## 7. 适用边界

- added_mass 要求完整流体子块可解；程序不自动添加压力钉点。
- 有界流体 Krylov 响应使结构 Schur 作用不精确，外层 FGMRES 不能把它自动变成
  精确线性逆。最终仍核对完整系统真实残量及原非线性条件。
- twolevel 使用按 rank/语义建立的分区常数粗空间，未实现完整耦合多层 AMG、
  弹性旋转近零空间或谱富集，未证明网格无关收敛。
- 这里只验证单机最多四个 MPI rank、固定布局和同分区重启；没有多节点扩展、
  跨分区重启或更大参数范围的新增证据。
- 本轮是预条件器的离散解等价性及恢复行为验收，不替代模型与空间/时间误差研究。

这些限制属于当前交付边界；没有将未实现能力或未执行的验证写成完成。
