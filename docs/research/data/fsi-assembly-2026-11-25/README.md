# FSI-ASSEMBLY-01：稀疏图与单元装配的实现、验证和成本

日期：2026-11-25。交付 [PR #51](https://github.com/saitoasukakawaii/EONSim-new/pull/51)，保持 Draft，待用户审核合并。

本轮完成最终 AIJ 图转移、固定单元映射缓存、残量/AD 切线融合、界面相邻单元力重放，以及显式 `-fsi_coo` 的压缩贡献计划。
默认仍为 MatSetValues。正式样本的默认 assembly 配对中位数下降 2.72%–11.81%；COO 下降 30.16%–43.37%。
**COO 四组的整次 wall 样本范围均跨过零，并增加峰值内存，因此没有将其默认开启，也没有宣称可靠的整次加速。**

## 固定来源

| 对象 | 来源 |
|---|---|
| 开发起点 | main `f7acccb7a8239c60a2d2be193a158ac430851dcf` |
| 实际基线二进制的构建源码 | `c4fb266edec94afbf610cb1379dd1595ed96ae40`；与开发起点的 src/include/tests、CMake、依赖锁和 cloud 构建脚本无差异 |
| 实现、候选二进制和本地 Release 验证源码 | `df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e` |
| 最终计时驱动 | `b2ccd96419091c669b8dceae4369c5b255f47f57`；只修正墙钟等待方式，未改生产 C++ |
| 基线 SHA-256 | `850a2fdbc751db4e865dfb954efe9cb4d301f29a4a80ea845af6b1ce05dde6f9` |
| 候选 SHA-256 | `b782a4e043b5e91a4e53652ce325ccf79bfac7696522f90a50f61f6fb3f6d9a0` |

源码和驱动每次均先推送再执行。df6e9ac 构建收据和 b2ccd 的两个正式 campaign 均记录干净工作树。
文档、归档及独立证据审计后续提交不冒充新的数值执行。

## 改动及正确性边界

1. `ReducedLayout` 直接保留 PREALLOCATOR 填零的最终 AIJ，`NonlinearSystem` 接管其唯一所有权；删除反查逐行 d/o 容量及第二次创建 AIJ。
2. physical-slot ghost 编号交换不再生成无用的 nodal 图和 field 数据；本地小集合用有界数组或排序 vector，避免大量树节点分配。
3. `FsiAssemblyPlan` 缓存活动分量、测试行、试探列和 mesh trace 标记。时间步、BDF2/generalized-alpha、缩步改变的 `mesh_dt` 每次尝试重新使用。
4. 解析 Jacobian 从同一次 Dual 残量取 primal 与导数；独立 double 残量和 FD 参考仍保留。接口力重算使用未投影的物理残量，并只遍历接触接口的两域单元。
5. COO 的掩码来自物理方程依赖：flow 行→flow/ALE 列、mesh 行→同一 mesh 分量、solid 行→solid 列。随后分别应用 test/trial 映射，保留重复 alias，由 PETSc 求和。
6. 刚体对角、固定和移动 RCR 的压力、速度及面积导数共用固定枚举顺序。局部失败仍先同步并排空残量 stash，成功后才共同发布 COO 矩阵；历史只在完整接受步提交。

拓扑、分区或约束支撑变化必须重建计划。本轮未引入在线重分区、GPU、matrix-free、SNES 跨步持久化或新的物理近似。
[完整算子/计时契约](../../../architecture/L2_DISCRETIZATION_AND_OPERATORS.md#fsi-固定装配计划与可选-coo) ·
[未发布算法草稿](../../../../website/drafts/fsi-sparse-assembly-plan.md)。

## 实际 Release 选测

锁定 PETSc 3.23.7、Open MPI 5.0.8、GCC 15.3.0、SuperLU_DIST 9.1.0；Release。
命令由仓库 `scripts/cloud/run.sh` 执行；[原始收据](release-summary.json)记录完整命令、依赖、退出状态和源码。

```bash
OMPI_MCA_smsc=^cma bash scripts/cloud/run.sh 3.23.7 release explicit \
  /workspace/scratch/6d25aa929185/pr42/.cloud \
  /workspace/scratch/d56ec93a621c/assembly-tests.json
```

**8/8 通过，零失败、跳过或超时。** 构建 41.02 s，CTest 35.44 s。

| 实际检查 | 覆盖 |
|---|---|
| nonlinear_acceptance / nonlinear_acceptance_mpi | 远程产生图、同一 Mat 对象所有权转移、多次 solve、约束与反力，1/2 rank |
| fsi_element_jacobian | 24 组变形配置，48 个 fluid/ALE 方向导数，metric 稳定化及压力面 |
| fsi_coo_verification | 27 次 solve，刚体/共享网格弹性/独立双域 Neo-Hookean，1/2 rank，RCR、Jfd、retry、跨后端 restart、失败不污染 checkpoint |
| fsi_metric_stabilization | BE/BDF2/generalized-alpha、1/2 rank、变步长和 restart |
| time_retry_verification | Neo-Hookean 拒绝步、回滚和恢复，1/2 rank |
| domains_verification | 独立共形两域、接口、整体 Jacobian 与 restart，1/2 rank |
| fluid_coo_verification | 共享 NonlinearSystem 的普通计数预分配和原独立流体 COO，1/2/4 rank |

新增 COO 测试最大 owned 字段差 `4.617972670928339e-13`，归一化历史差 `5.920530605376608e-14`，
移动 RCR 完整 Jacobian 相对 FD 差 `1.98755e-08`。真实 retry 发生 3 次缩步，最终接受 dt=0.0125。
融合单元 48 个方向比较最大相对差 `2.23866e-10`。本地未运行默认全量、Debug 或 PETSc 3.19.6。

远端 [Core numerical validation](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45632206852)
在 b2ccd964 对应的 PR merge commit `ad0cbf5965c6d83e7d578d9ffe549f0e6c84e9b0` 上
实际执行 **55/55 项 Release 数值选测通过**，未复用历史测试；选择脚本的 65 项 Python 检查通过。
网站构建通过；Debug 和 PETSc 3.19.6 手动 job 跳过。[CI 来源收据](ci-source-b2.json)。

## 正式性能方法

CPU `/proc/cpuinfo` 标识为 Intel Xeon Platinum 8573C，可见 CPU 0–8；共享 Linux 主机，未验证独占物理核绑定。
每 rank 一个线程，相同的 PETSc/MPI/编译器/BLAS 环境。选择两个独立流固网格，使用五个 BE 步，dt=0.02、E=100、ν=0.3、压力=1。
保持原物性默认和原边界，solver rtol=1e-10、atol=1e-12、最大 Newton=30；四个物理字段分别验收。
每次显式设置 PREONLY/LU/SuperLU_DIST，双方都启用 solver_report 与真实 linear_report，不启用 log_view。
候选额外启用一次 fsi_assembly_report，其少量启动归约计入候选 wall。

每组 1 对预热 + 3 对交替测量；两网格 × 1/2 rank × 默认/COO 两个 campaign，
合计 **64 次正式 campaign 运行（48 次测量、16 次预热），320 个接受步，640 次线性修正**。
所有步均为 2 次 SNES、2 次累计 KSP 迭代；逐步时刻、字段接受、真实线性残量、全部保存的两域节点场和 ghost、接口力/功率及 CSV 历史全部检查。
默认路径最大字段与历史差为 0；COO 最大字段差 `2.220446049250313e-16`，历史差 `1.8158547268845473e-15`。
真实线性残量界限为 `1e-12+1e-10*rhs_norm`，最大 residual/limit 为 `0.000160287150638544`。

以下均为 **逐对百分比变化的中位数 [最小, 最大]**，负数表示时间减少；它与“双方中位数的比值”是不同统计量。
`assembly` 为 SNES 内正常完成评价的 rank 最大时间之和，包含局部计算、插入与最终装配；
`solve` 还含线性求解等工作；`wall` 包括进程启动、全部准备、求解、输出和退出。
这些范围不是置信区间；不能把三个样本外推到大规模生产。

### 默认装配 vs 原基线

| 总单元 / DoF | MPI ranks | assembly 配对变化 | solve 配对变化 | 整次 wall 配对变化 |
|---|---:|---:|---:|---:|
| 771 / 703 | 1 | -11.81% [-12.38, -8.81] | -5.10% [-9.88, -1.97] | -2.18% [-4.44, -1.77] |
| 771 / 703 | 2 | -7.75% [-9.02, -3.77] | -9.30% [-12.93, +0.59] | -3.67% [-8.81, +2.86] |
| 6,147 / 5,367 | 1 | -2.72% [-3.84, -1.79] | +1.08% [-0.85, +1.12] | +0.60% [-1.23, +0.85] |
| 6,147 / 5,367 | 2 | -3.04% [-16.79, -1.49] | -0.00% [-5.55, +4.25] | -0.80% [-4.11, +3.04] |

四组的 assembly 全部配对样本均有下降。整次收益较小，多数组别范围跨过零。

### 显式 COO vs 原基线

| 总单元 / DoF | MPI ranks | assembly 配对变化 | solve 配对变化 | 整次 wall 配对变化 |
|---|---:|---:|---:|---:|
| 771 / 703 | 1 | -43.37% [-44.47, -32.05] | -21.43% [-22.27, -10.24] | -1.02% [-2.93, +0.94] |
| 771 / 703 | 2 | -30.16% [-42.71, -27.74] | -13.58% [-20.67, -6.58] | +6.59% [-2.57, +13.95] |
| 6,147 / 5,367 | 1 | -39.18% [-46.12, -35.39] | -2.39% [-20.35, +4.83] | -0.26% [-15.99, +5.43] |
| 6,147 / 5,367 | 2 | -38.50% [-47.80, -34.41] | -5.95% [-6.74, +16.13] | -3.01% [-7.05, +23.30] |

COO 的局部组装收益明确，但本次五步、共享主机的小算例没有建立可靠的整次收益。
线性求解仍占主要成本，COO 还有一次性计划构造和更多缓存；本实验未分离这些因素的全部因果贡献。
保持 COO 为显式选项，按实际运行长度、求解器和内存预算决定。

## 稀疏存储与内存

| 总单元 | 默认唯一 nnz | COO 唯一 nnz | nnz 减少 | COO 单元/端口贡献数 | COO 值缓冲合计 |
|---|---:|---:|---:|---:|---:|
| 771 | 36,643 | 27,226 | 25.70% | 158,282 | 1,271,880 B |
| 6,147 | 364,635 | 260,010 | 28.69% | 1,590,346 | 12,765,704 B |

所有候选主矩阵记录 `matrix_mallocs=0`、`nnz_unneeded=0`；后者是多余容量，不是结构或数值零的数量。
COO contributions 不等于唯一 nnz。值缓冲之外，还有缓存 local slots、临时坐标和 PETSc 内部计划。

| 总单元 / MPI ranks | 基线峰值单 rank RSS | COO 峰值单 rank RSS | 配对变化 |
|---|---:|---:|---:|
| 771 / 1 | 48.164 MiB | 49.566 MiB | +2.91% [+2.54, +3.08] |
| 771 / 2 | 47.805 MiB | 49.410 MiB | +3.54% [+2.97, +4.52] |
| 6,147 / 1 | 119.742 MiB | 153.074 MiB | +27.81% [+27.77, +27.86] |
| 6,147 / 2 | 104.727 MiB | 117.602 MiB | +12.29% [+10.16, +17.69] |

6,147 单元、2 rank 的最大 rank 值缓冲为 9,610,048 B，超过平均值 6,382,852 B；
这是当前分区贡献量不均衡的线索，不是独立测得的计算负载比。
候选默认/COO 新初始化总时间在四个配置的中位数分别为 10.522/16.299、9.308/15.129、121.100/167.214、104.095/166.425 ms。
两种模式在不同 campaign 中测量，不能将其比值称为配对加速；旧基线没有新初始化细分，未宣称图初始化的百分比收益。

## 计时缺陷与原始记录

最初驱动使用 POSIX `Popen.wait(timeout=...)`，给短命令的外部 wall 加入约 50 ms 轮询粒度。
源码审查和输出分布发现该问题后，在 b2ccd 改为阻塞 wait + 独立 watchdog，先推送再重复两个最终 campaign。
原始 `perf-default` 和 `perf-coo` 共 64 次 pilot 仍保留；其数值检查通过，但墙钟数据不进入上述结论。
生产 C++ 未变，因此复用 df6e9ac 的 8 项通过收据，没有无故重新编译或重复数值选测。

## 归档和复现

- [performance-summary.json](performance-summary.json)：正式统计、原始计数、内存和二进制来源。
- [release-summary.json](release-summary.json)、[selected-tests.json](selected-tests.json)：实际 Release 收据和选测。
- [evidence.tar.xz](evidence.tar.xz)、[archive.json](archive.json)：去重原始文件、完整哈希与计数。
- [independent-audit.json](independent-audit.json)：独立重算、字段复核和归档审计。
- [ci-source-b2.json](ci-source-b2.json)：远端实际执行的 55 项数值检查、65 项 Python 检查与来源。

归档内 `manifest.json` 将原始相对文件名映射到 SHA-256；每份唯一内容位于 `objects/<sha256>`。
其中保留全部 pilot/final 日志、输入、分区、逐步 VTU、CSV、结果 JSON、Release 证据、环境及两个实际计时二进制。
独立审计先完成数值与初版归档复核；随后加入两份二进制、审计本身和 CI 收据。
`archive.json` 的最终打包复核已核对每个对象、引用、长度及二进制摘要，完成审计中标记的打包待办。
二进制依赖上述动态链接运行环境，并不是脱离依赖的安装包。正式性能入口如下（BASE/CANDIDATE 使用固定构建版本）：

```bash
python scripts/benchmark_fsi_assembly.py \
  --baseline BASE --candidate CANDIDATE \
  --baseline-commit c4fb266edec94afbf610cb1379dd1595ed96ae40 \
  --candidate-commit df6e9ac63f8b2d47c05b98ac3839c07c28e40a2e \
  --mpiexec mpiexec --work NEW_DIRECTORY \
  --subdivisions 4 8 --ranks 1 2 --steps 5 --repeats 3
# COO campaign 在最后追加 --candidate-options -fsi_coo
```

所有实际命令保存在归档各 campaign 的 results.json 中；不要覆盖既有结果目录。
从归档读取任意原文件时先核验其哈希，例如：

```python
import hashlib, json, tarfile
with tarfile.open('evidence.tar.xz', 'r:xz') as archive:
    manifest = json.load(archive.extractfile('manifest.json'))
    ref = manifest['files']['perf-coo-final/results.json']
    payload = archive.extractfile('objects/' + ref['sha256']).read()
    assert hashlib.sha256(payload).hexdigest() == ref['sha256']
    result = json.loads(payload)
    assert result['status'] == 'passed'
```

本轮验证最多单机 4 rank；本次 FSI 性能仅 1/2 rank、两套小网格。
没有证明多节点扩展性、GPU 收益、网格无关求解迭代或长时间生产算例的普遍加速。
