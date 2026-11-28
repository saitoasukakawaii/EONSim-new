# FSI-SCALABLE-05 · 真实弹性管的容差校准

起点为 PR #72 的合并提交 `5925195865fc6053d786d7a1edf2d609c6b74cf1`。独占单节点，双路 EPYC 7763，128 个物理核、两个 NUMA 域，约 251 GiB 可见内存。PETSc 3.23.7，assembled CPU，单线程 BLAS。沿用[冻结 benchmark](FSI_SVFSI_BENCHMARK.md)的四分之一管、零牵引外壁、材料、RCR、初态和每四步输出，固定 $\Delta t=1/32$ s。阶段运行目录为服务器上的 `$HOME/workspace/fsi-scalable-05-runs`。

## 生产与验收

作业 466 从 #72 的已验哈希静态库增量重建，编译器扫描当前源树和公共头依赖，重编五个 core 翻译单元及主程序、定向测试，校验归档成员唯一性。Release 编译提交为 `d672e1ea9a4448658c48f212cac5f71cdffc3793`，1/2 rank 的零 owner、返回 FP64、失败传播及跨步 forcing 复位测试通过。二进制 SHA256 为 `efaad5cc91437ac022606dcf40bded9e9b504a39be8eac84611db44c3156eb05`。[逐目标构建收据](../research/data/fsi-scalable-05/release-build.json)

阶段显式协议将返回校正的 $\|b-Ax\|_2$ 与 $\max(a,\eta\|b\|_2)$ 比较。非零初猜仍用原 RHS 范数，零 RHS 使用绝对容差，原残量比较余量为零。固定模式取声明的 rtol，已有 fresh inexact Newton 取每次 KSP 实际使用的 forcing。参考用 PREONLY/SuperLU_DIST 和显式 LU 精化容差，在实际写回的 FP64 向量上同时核验 PETSc 和扩展精度残量。迭代生产以 PETSc 原算子范数判停，诊断另记录扩展精度与最大分量后向误差。运行前选定的协议及 profile 一起生成 SHA-256。筛选器核对命令、PETSc 有效 options 及来源、实际 KSP/SNES 设置、校正标识、每步非线性场和约束、所有期望历史与保存场。[协议](../research/data/fsi-scalable-05/CALIBRATED-v2.json) · [验收实现](../research/data/fsi-scalable-05/tube_protocol.py)

完整场逐相位比较结点 RMS 和局部最大差，压力以 20 Pa、流量以四分之一域幅值、速度以抛物线中心速度、位移以 20 Pa 的 Lamé 位移为特征尺度。入口、质量、界面、RCR 和外部物理预算按原冻结定义。单独登记了 generalized-alpha 的加速度、网格速度及坐标输出，用相应谐波导数尺度验收。该补充检查在比较这些附加量前冻结，原始主变量预算和原始运行收据保留。[附加场声明](../research/data/fsi-scalable-05/output-fields-v2.1.json)

## STRICT-v1

复用 #72 的 A4 直接、ASM、physics 20 步和 40 次校正。B 作业 456 零接受步，末次扩展/PETSc 残量分别为 2.83488e-18/6.15887e-18，门槛 5.52652e-19；离线最佳返回向量的 1.152686e-18 单列。C 的旧 64-rank ASM 首校正相对残量约 0.983。B/C 的原压力常向量左右作用非零。原始状态及 2e-9 同配置回归门槛见[STRICT-v1](../research/data/fsi-scalable-05/STRICT-v1.json)和[失败原件](FSI_SCALABLE_04.md)。

## CALIBRATED-v2 的 A/B 固定容差

保持网格、时间积分、非线性容差、physics fieldsplit/FGMRES 与输出策略一致。各档先跑首步和 4 步，再进行 20 步冷启动。LU 自身与独立 fieldsplit 迭代均核验返回校正，然后比较流体、壁、网格、压力面、端口与时间历史。下表是单次诊断作业的 MPI 启动至输出关闭时间。所有候选都采用 `atol=1e-23`。

| 算例 / 方法 | rtol | Slurm | 接受步 | Newton 校正 | KSP 次数 | T_job（s） |
|---|---:|---:|---:|---:|---:|---:|
| A4 / LU | 1e-8 | 482 | 20 | 40 | 40 | 0.717 |
| A4 / physics | 1e-8 | 483 | 20 | 40 | 1536 | 2.409 |
| A4 / physics | 1e-6 | 484 | 20 | 45 | 1437 | 2.371 |
| A4 / physics | 1e-4 | 485 | 20 | 60 | 1428 | 2.440 |
| B32 / LU | 1e-8 | 490 | 20 | 40 | 40 | 97.160 |
| B32 / physics | 1e-8 | 491 | 20 | 40 | 3061 | 66.891 |
| B32 / physics | 1e-6 | 492 | 20 | 40 | 2359 | 53.297 |
| B32 / physics | 1e-4 | 493 | 20 | 60 | 2649 | 62.919 |

B32 首步的 LU 作业 469 有两次合格校正。第一次原 RHS 为 5.52652092799e-9，PETSc 原残量为 1.58077e-17，扩展精度为 1.48123e-17，显式上限为 5.52652e-17。B20 三档固定容差在全部保存相位对独立 LU 的最大绝对差如下。出口流量列使用整圆入口流量幅值归一化。

| rtol | 压力场（Pa） | 流体速度（m/s） | 壁位移（m） | 网格位移（m） | 出口流量 | 压差（Pa） | 面积应变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1e-8 | 1.120e-10 | 1.824e-13 | 4.132e-18 | 1.467e-17 | 1.527e-12 | 5.578e-11 | 7.379e-16 |
| 1e-6 | 1.011e-8 | 7.155e-12 | 2.169e-16 | 3.936e-15 | 1.245e-10 | 2.616e-9 | 3.991e-14 |
| 1e-4 | 1.829e-9 | 3.107e-12 | 8.219e-17 | 1.165e-15 | 1.041e-10 | 1.213e-9 | 1.528e-14 |

B20 选择固定 `1e-6`。改用 `1e-4` 后，每步多一次 Newton 校正，总 KSP 次数与总耗时都上升。比较限于本次网格和 dt；网格、时间离散误差未独立估计。

## Inexact Newton

基线和 inexact 共用 `ksp_rtol=1e-6`、`ksp_atol=1e-23`。inexact 使用已有算法，初值 0.1、上界 0.5、gamma 0.9、alpha 1.5。B 的第一步实测四次 eta 依次为 0.1、0.03112、0.004149、0.0002240。每次原式允许值均由该次 eta 和原 RHS 独立复算。A20 作业 498 和 B20 作业 501 的场、历史、质量、界面和 RCR 检查均通过。作业 504 独立复查 A/B 全部 26 份窗口，18 份 4/20 步收据具有算法独立的配对资格，8 份首步收据只作线性窗口验证。

| 诊断窗口 | 固定 / inexact Newton | 固定 / inexact KSP | 固定 / inexact T_job（s） |
|---|---:|---:|---:|
| A20，4 MPI | 45 / 79 | 1437 / 1560 | 2.371 / 2.772 |
| B20，32 MPI | 40 / 80 | 2359 / 2578 | 53.297 / 64.894 |

B 第二步的第一次 inexact 校正仅用两次 Krylov 迭代，但该步总共需要四次 Newton 校正。该组 forcing 两个网格上的线性迭代总数和总时间都增加。

## 合格窗口的正式性能

每一侧独立预热一次，再交错运行三对冷启动样本。每份收据都通过同一个直接参考、完整保存场和历史检查。独占 128 核，A 用 4 个、B 用 32 个单线程 MPI 进程。表中资源列取正式样本中位数，core-hours 计入全部分配核。所有原始样本的活跃 rank-hours、绑定、内存和校正明细保存在[运行收据](../research/data/fsi-scalable-05/run-receipts.json.gz)，[校准表](../research/data/fsi-scalable-05/calibration.csv)按窗口列出结果。

| 作业 | 对照 → 候选 | T_job（s） | 时间变化 | Newton | KSP | 进程树峰值（GiB） | 分配 core-hours |
|---|---|---:|---:|---:|---:|---:|---:|
| 506 · A20 | 固定 1e-8 → 1e-6 | 2.408 → 2.321 | −3.60% | 40 → 45 | 1541 → 1433 | 0.107 → 0.107 | 0.0856 → 0.0825 |
| 502 · B20 | 固定 1e-8 → 1e-6 | 67.377 → 53.450 | −20.67% | 40 → 40 | 3060 → 2360 | 1.961 → 1.929 | 2.396 → 1.900 |
| 507 · A20 | 固定 1e-6 → inexact | 2.321 → 2.773 | +19.45% | 45 → 79 | 1434 → 1553 | 0.109 → 0.107 | 0.0825 → 0.0986 |
| 503 · B20 | 固定 1e-6 → inexact | 53.349 → 64.271 | +20.47% | 40 → 80 | 2360 → 2578 | 1.941 → 1.923 | 1.897 → 2.285 |

B20 的固定候选达到主要算例 15% 目标，A20 也满足代表算例退化不超过 5% 的要求。两组 inexact 计时支持在这两个窗口继续采用固定配置。上述降幅来自改变线性容差。通信收益的资格单独核验。B 的实际 RCR pressure-MG 作业 505 在第一步预算内原残量仍为 3.6762e-9，原 RHS 为 5.5265e-9，接受零步。A/B 正式样本采用 physics fieldsplit，无法据此计算 owner 或 Telescope 在真实管上的收益。第 4 阶段合成样本保留原基线和原结果。[作业与输出哈希](../research/data/fsi-scalable-05/log-index.json.gz)

## C 的首系统与独立窗口

C 有 924,953 个自由度。作业 470 在重组系统上使用 physics，486 次 FGMRES 达到原残量 1.88385e-17，目标为 1.90849e-17。作业 495 在保存的原 AIJ 上重算同一 FP64 返回向量，55,761,870 个 CSR 列位置相同，4,796 个系数存在末位差异。保存阵的扩展精度残量为 1.73907e-17，串行 FP64 CSR 为 1.92946e-17。按运行前的双重离线判据，该返回向量未通过严格的首系统诊断档 `CALIBRATED-v2/fixed-1e-8`。

作业 471 的 RCR 压力粗化 MG 用完 500 次，原残量约 1.740e-9。最粗矩阵 1,190 行，实际 Telescope 使用 32 rank；第一级和第二级散度像投影缺陷分别为 0.708 和 0.899。粗求解实际被调用，根迭代仍停滞。

作业 510 直接读取作业 409 的原矩阵和原 RHS。physics 在 479 次 FGMRES 后达到 PETSc 原残量 1.86807e-17，同一返回向量的串行 FP64 CSR 残量为 1.90520e-17，扩展精度为 1.72291e-17，均通过 1.90849e-17 的门槛。选定的固定 `1e-6` 在作业 515 用 384 次迭代通过，PETSc、串行 FP64 和扩展精度残量分别为 1.88404e-15、1.88400e-15、1.88399e-15，门槛为 1.90849e-15。作业 511/512 对这份矩阵比较 MG 内部场缩放，100 次后原残量为 1.80714e-9 / 1.80827e-9。此缩放对该停滞无实质改善。[原 CSR 与返回向量核验](../research/data/fsi-scalable-05/c-native-receipts.json)

C64 的直接参考候选 496/497 用显式 `1e-8/1e-23`，完成 1/4 步。4 步用时 613.525 s，进程树峰值 134.410 GiB，预算 140 GiB。固定 physics `1e-6/1e-23` 作业 499/500 完成相同窗口，4 步为 142.225 s，全部场、历史及物理量通过独立比较。[首系统与外部原件](../research/data/fsi-scalable-05/c-native-receipts.json)

### C20 直接法的内存预算与续算核验

直接参考作业 513 完成前四步，步末进程 RSS 合计依次为 70.67、73.03、73.15、73.29 GiB。第五步第一次线性校正期间，采样进程树 RSS 达 151,229,960,192 B，超过预声明的 140 GiB。作业在 632.93 s 停止，前四步和全部日志保留。该作业计为资源失败。原节点有约 251 GiB 实体内存，作业退出后可用约 237 GiB。直接法的独立重试预声明 180 GiB 上限，启动时核对节点及作业实际 cgroup 余量并额外留出 32 GiB，每 5 s 记录进程树 RSS、最大单进程 RSS 及对应的日志位置。迭代路径继续使用原 140 GiB 上限。[作业 513 原收据](../research/data/fsi-scalable-05/c20-lu-513.json.gz)

A 上的原生 checkpoint 回归将 4 步结果续至 20 步，并逐相位与冷启动比较。作业 516 的固定 `1e-6` 在旧 2e-9 同配置门槛下失败，压力场最大差 2.729e-8 Pa，两次冷启动之间也有 1.054e-8 Pa。两者分别通过预冻结的 v2 物理预算。作业 520 的 LU、固定 `1e-8` 同配置续算均通过旧门槛，场最大差为 1.626e-14、1.365e-10，历史最大差为 2.842e-14、9.264e-10。后继 C 窗口将固定与 LU 各自从相应参考对的原生状态续算。[含冷启动对照的回归收据](../research/data/fsi-scalable-05/restart-520.json.gz)

## svFSI 原版 B

历史作业 438 的 14 次 MS 全部达到 2,000 次。按相同网格重建初始 MS 的约束后自由块，得到 32,256 个自由分量，初始对角最大/最小约 224.53。原生 CG 改用 RCS 后，作业 467 的首个 MS 校正 922 次达到 9.8e-11，首个 FS 仍需 3,718 次。第 4 次 MS 达到 2,000 次且线性残量比升至 1.422e5，第 4 次 FS 也超出其门槛。作业 494 保留原生 MS 选择，测试 FS 原生 BIPN，首个 FS 残量比约 0.866，随后多次接近 1。这两个未合格的作业均排除在外部配对之外。[日志索引](../research/data/fsi-scalable-05/c-native-log-index.json)

## 复跑

以下命令在上述节点上用新的输出目录运行。保留旧包与脚本提交的对应关系；后续只有脚本变化时，入口会检查生产源码树和二进制哈希。

C 强扩展使用纯 MPI 分区。等 128 核的混合诊断另要求同一窗口已有合格的 128×1 样本，沿用其 64-rank 参考的原分区，启动时显式设置 `-fsi_threads 2`。每个 MPI rank 先记录实际分配的两核掩码，再用 GNU OpenMP 报告工作线程号、实际队伍大小与各线程亲和性。验收将 128 个线程位置与操作系统的物理核/插槽编号逐一对应，检查 64 个队伍、每个队伍两个线程以及跨 rank 无核重叠。该对照为一次诊断计时。[GNU OpenMP 亲和性格式](https://gcc.gnu.org/onlinedocs/libgomp/OMP_005fAFFINITY_005fFORMAT.html)

```bash
root="$HOME/workspace/fsi-scalable-05-runs"
data="$root/source/docs/research/data/fsi-scalable-05"
exe="$root/build/eonsim"
sbatch -n32 -t 00:15:00 "$data/run_case.sh" B 20 lu "$exe" "$root/recheck-B20-lu" --limit 420
# 独立 LU 窗口实际完成后执行
sbatch -n32 -t 00:30:00 "$data/run_case.sh" B 20 fixed-1e-6 "$exe" "$root/recheck-B20-fixed" \
  --limit 1500 --reference "$root/recheck-B20-lu"
# 下列三个输入目录来自上表已经通过的独立 B20 窗口
sbatch -n32 -t 00:30:00 "$data/run_case.sh" B --timing \
  "$root/B20-fixed-1e-8" "$root/B20-fixed-1e-6" "$root/B20-lu" "$exe" \
  "$root/recheck-B20-rtol-pairs" --change fixed-tolerance
sbatch -n32 -t 00:30:00 "$data/run_case.sh" B --timing \
  "$root/B20-fixed-1e-6" "$root/B20-inexact-1e-6" "$root/B20-lu" "$exe" \
  "$root/recheck-B20-forcing-pairs" --change forcing
python -B "$data/test_tube_protocol.py" -v
# 已有窗口 C20-lu-180、C20-fixed-1e-6 和合格 C20-r128 后执行
sbatch -n64 -c2 -t 00:35:00 "$data/run_case.sh" C 20 fixed-1e-6 "$exe" "$root/recheck-C20-64x2" \
  --limit 1500 --reference "$root/C20-lu-180" --hybrid-from "$root/C20-r128"
```
