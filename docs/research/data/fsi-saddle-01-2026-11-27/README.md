# FSI-SADDLE-01：执行证据、失败与适用范围

对应 [PR #65](https://github.com/saitoasukakawaii/EONSim-new/pull/65)。最终生产及验证驱动源码为
`ccf1bd7b3727a6b3ddd3a85954a3a78c51a652ba`，完整 tree 为
`014a1de3199b7e476aec00aa63078a13adb60610`。所有实现和修复均先同步远端并核对完整 tree，
再编译和执行；后续文档提交不改变二进制身份。

机器可读汇总见 [summary.json](summary.json)，逐文件 SHA256 见
[archive-manifest.json](archive-manifest.json)，压缩包整体校验见
[archive-integrity.json](archive-integrity.json)。每个归档成员均已从压缩包回读，逐字节长度和
SHA256 与原件比较。原 failed 收据没有被改写为 passed。

## 环境与源码链

主锁为 PETSc 3.23.7、GCC 15.3.0、Open MPI 5.0.8，Release，FP64/real/int32。
锁文件 SHA256 为 `4b83ceb31a805aab979b5f14fd6cb22ccf777659767f27b44c08ed73ac186892`。
本地为一个 Linux host，验证器报告 CPU budget 9、内存预算 10,451,423,232 bytes，最多四个编译
任务；数值算例 `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=1`。
代数检查用 1/2/4 MPI rank，物理算例用 1/2 rank。时间是单次测量，不是统计稳定的跨机器加速比。

| 提交 | 内容 | 后续实际执行 |
| --- | --- | --- |
| `036f865e` | 已合并 #64 的 main 基线 | 本轮从该状态接续 |
| `bfb5d0c` | 十三项方向初版实现、独立检查及物理模式 | 16 项 CTest：13 通过、3 个 MG 失败；19 个 Python runner 检查通过 |
| `bd2f010` | 不变散度块下复用 compatible transfer；补真实计数 | 4/4 CTest（MG 1/2/4、原有物理回归）；新增 48 轨迹中 45 通过、3 失败 |
| `24b8056` | 分布式 coarse 局部主元；复用失效原因审计 | 3/3 MG；受影响物理 12/12；网格 18 次中 17 通过、1 个 Braess 失败 |
| `ccf1bd7` | Braess 默认 alpha=2，独立块 oracle 覆盖默认值 | 6/6 MG/smoother；Braess-only 物理及网格 12/12 |

完整提交和各二进制 SHA256 在收据及各 `binary.json` 中。源码前缀只是本表的显示简写。
原有 `monolithic_fsi_physical` 的 24 条轨迹在 `bd2f010` 上通过；CTest 驱动未传
`--build-source`，原收据该字段保持 null，实际 binary/source 绑定另由同一归档的构建记录及
`binary.json` 给出，不事后改写原收据。

## 最终有效覆盖与证据复用

本地 17 个不同 CTest 的最终有效记录全通过：最终源码新跑 6 项，未受后续算法修改影响的
10 项保留 `bfb5d0c` 原通过记录，原有物理回归 1 项保留 `bd2f010`。这是覆盖集合，不是声称
最终提交重新执行了全部 17 项。每次实际执行的完整命令、通过/失败状态和耗时分批保留。

新增物理覆盖为 15 个显式模式加 direct，分别运行双域 1 rank、双域 2 rank、运动 NH-RCR
2 rank，共 **48 条有效轨迹**。其中 33 条来自 `bd2f010`，9 条来自 `24b8056`，6 条来自
最终 `ccf1bd7`。网格窗口每个网格包含 direct 与五种模式，共 **18 条有效轨迹**；其中 12 条
来自 `24b8056`，Braess 与其 direct 参考的 6 条在最终源码重跑。

复用边界经过逐项核对：`24b8056` 的数值变化是多 rank coarse 的局部 LU，其余保留模式明确
使用单 rank coarse；复用/重建诊断的变化不改变算法阈值。`ccf1bd7` 只改变 Braess 的默认
alpha 和其 oracle，其他平滑器和物理算子不变。汇总每一行标记原始 source、binary hash、
receipt 和是否复用，不能把跨源码记录计作一个最终源码全量新跑。

| 验收量（48+18 条有效轨迹） | 实测最大值 | 原门槛 |
| --- | ---: | ---: |
| 原算子残量 / 当次严格 gate | 0.009489329701 | ≤1；gate=`1e-12+1e-10*rhs_norm` |
| 全部保存场与 direct 的最大绝对差 | 4.316880187e-12 | 2e-9 |
| 历史量与 direct 的最大绝对差 | 7.993605777e-15 | 2e-9 |
| 强闭包独立交换缺陷 | 1.245817331e-15 | 1e-10 |

还保留了逐步字段/约束接受、RCR circuit 检查、层级压力语义、实际中间层 supremizer、跨
owner 聚合、着色冲突、真实 Schur/精确细层/deflation 动作等证据。原始单元 oracle 包含非对称
矩阵、变化算子、可变 PC、空 owner 和单 rank PC 失败传播及恢复。

## 真实失败与修复

1. **compatible transfer 复用过度保守。** 初版 3 个 MG rank 档均拒绝复用未改变 B 的更新。
   修复严格逐项比较所有活动压力到 primal 系数，含远端列和显式零；固定 scaling/typed
   transfer 下 B 不变允许复用。新增改 B 的反例仍必须重建并满足同一交换门槛。
2. **配置启用不等于每次都复用。** 初始物理审计误拒绝全开模式的数值漂移重建，以及
   adaptive 模式的实测收缩重建。补充真实 `drift_rebuilds`、`age_rebuilds`、
   `divergence_rebuilds`、`adaptive_rebuilds`，允许组合模式如实记录 guard 拒绝；单独
   `mono_reuse` 仍必须实际复用粗空间和 Galerkin symbolic product。
3. **粗层局部无主元 LU。** moving RCR 全开模式的 128×128 ASM 局部矩阵在第 70 行产生
   约 `1.30104e-18` 主元；原门槛 `2.22045e-14`，粗层第 0 次迭代 `DIVERGED_PC_FAILED`。
   旧 binary 唯一算法配置变更为局部 MUMPS 后完整三步通过。正式实现先共同检测 sequential
   MUMPS 能力，再给未显式指定的多 rank ASM LU 选用该后端。未改矩阵、shift、压力约束、
   零主元门槛或 coarse rank 数。诊断中 GDB/LLDB 不可用，安装 GDB 被系统包管理权限拒绝；
   使用 PETSc 原始 `-info`、`ksp_view`、`ksp_converged_reason` 定位并保留原件。
4. **Braess 默认阻尼不足。** 5367 DoF 网格原 alpha=1 在首修正 1500 次后真实残量为
   `4.209901562e-4`。只将 alpha 改 2、Schur 仍 3 次，首修正 83 次后残量
   `8.804872969e-14`，三步总迭代 404，保存场也通过 direct 对照。新默认经独立稠密块
   oracle 和完整 Braess 物理/网格窗口复验；没有通过加大外层上限或降低精度掩盖失败。

## 网格窗口与性能代价

固定两个 rank、703/2299/5367 DoF，每条轨迹 3 步、6 次 Newton 修正，沿用预声明的
平均迭代最大/最小比 **≤1.3**。原门槛没有调整；以下五种模式全部 **OPEN**。

| 模式 | 三个网格总外层迭代 | 平均迭代 max/min | n8 总求解时间（s） |
| --- | --- | ---: | ---: |
| `mono` | 103 / 151 / 206 | 2.000000 | 11.083586 |
| `mono_saddle` | 104 / 151 / 204 | 1.961538 | 10.798841 |
| `mono_braess`，alpha=2 | 214 / 314 / 404 | 1.887850 | 6.817998 |
| `mono_colored` | 28 / 39 / 50 | 1.785714 | 7.263816 |
| `mono_saddle_all` | 27 / 36 / 46 | 1.703704 | 18.838563 |

n8 colored 相对同批 baseline 总迭代减少 75.73%，线性时间减少 59.86%，总求解时间减少
34.46%。全开模式总迭代减少 77.67%，但总求解时间增加 69.97%，各 rank 峰值 RSS 的最大值
从 214,499,328 增至 399,372,288 bytes（+86.19%）。不能由迭代减少推出总体加速或内存下降。
Braess 的单步作用较便宜，因此其迭代较多也不直接等同于较慢；该时间与其余四个模式分批测得。

全开模式的 n8 压力空间为 **729→729→729**，总行数初次为 5367→2314→1040，重建后为
5367→2344→1057；复杂度上限阻止继续粗化。交换缺陷约 2.03e-16～3.89e-16，兼容性成立，
压力粗化代价也真实存在。算子复杂度为 6.7653～6.8603；比较 baseline 4.8283 时必须同时
说明 fine nnz 分母不同：reduced P 为 187,148，baseline 为 260,010。两者全部层矩阵 nnz
总量分别约 1,266,120～1,283,884 与 1,255,404；这个量不含全部 transfer、局部因子及缓存。

全开组合同时改变多个机制，不能将其净收益/代价归因于单个选项。百万 DoF、多节点、
生产扩展效率及全局 inf-sup 界均未验证；本轮最大实际物理网格为 5367 DoF，旧任务的
10387 DoF 单机结果仍只是旧证据。

## 归档内容

- `initial-unit.tar.xz`：初版 16 项及原始失败、19 项 Python 终端观察记录、初版 CI job log。
- `reuse-fix-validation.tar.xz`：复用修复后的 MG 和原有 24 条物理回归。
- `coarse-fix-validation.tar.xz`：主元修复后的 3 项 MG。
- `final-unit.tar.xz`：最终源码 6 项 MG/smoother、环境 wrapper、二进制身份。
- `physical-initial.tar.xz`：新增 48 次初始执行，45 通过、3 原始失败。
- `physical-coarse-fix.tar.xz`：受影响模式 12 次正式复验，全部通过。
- `grid-initial.tar.xz`：五模式网格 18 次初始执行，17 通过、1 原始 Braess 失败。
- `braess-final-physical-grid.tar.xz`：最终源码 Braess-only 12 次正式对照，全部通过。
- `rcr-pivot-diagnostics.tar.xz`、`braess-diagnostics.tar.xz`：两项独立单因子诊断，和正式复验分开。

归档包含原日志、输入配置、mesh/partition、保存场、历史、命令和收据；构建 binary 本体
不重复加入 Git，实际 SHA256 随记录保存。`source-ci.tar.xz` 另保存最终源码 CI 的全部
975 个数值工件成员、选测计划、增量收据、三个 job 原日志及 GitHub 元数据；原 ZIP 的
大小与 SHA256 已和 GitHub digest 核对，解包内容逐文件相等。

## 最终源码 CI

[源码 CI 45931896224](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45931896224)
实际新执行 **83/83 Release、54/54 Python**，没有复用数值记录；主锁仍为 PETSc 3.23.7。
其合并预览 `75bb86a0c5e668d497d0e95eb5ed0be4df824550` 与源码 `ccf1bd7` 的完整
tree 均为 `014a1de3199b7e476aec00aa63078a13adb60610`，构建记录 dirty=false。
[源码网站检查 45931896258](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45931896258)
也通过。结构化来源见 [source-ci.json](source-ci.json)。这批远端检查与上述本地分源轨迹
分别计数；最终文档 head 的四项必需检查及锁定 SHA 合并状态以 PR #65 为准。

## 复现命令

使用仓库主锁恢复环境和 Release 构建；`FSI_SOURCE` 必须填写实际构建的 40 位源码 SHA。
本次执行的原绝对命令保留在各 `results.json`，下列入口用于新目录复现。

```bash
python tests/verify_fsi_multigrid.py \
  --executable "$FSI_BIN" --mpiexec "$FSI_MPI" --build-source "$FSI_SOURCE" \
  --work results/saddle_physical --sections default moving \
  --modes mono_saddle mono_divergence mono_commuting mono_multilevel mono_braess \
          mono_colored mono_multiplicative mono_distributed mono_reuse \
          mono_adaptive_hierarchy mono_mf_fine mono_coarse_distributed \
          mono_deflated mono_communication mono_saddle_all

python tests/verify_fsi_multigrid.py \
  --executable "$FSI_BIN" --mpiexec "$FSI_MPI" --build-source "$FSI_SOURCE" \
  --work results/saddle_grid --sections scaling \
  --modes mono mono_saddle mono_braess mono_colored mono_saddle_all
```

`git checkout` 到对应源码后再复现，不能把后来的代码/默认值用于改写早期失败。新运行的时间、
少量舍入和迭代差异应如实保留，真实残量与物理接受门槛保持。
