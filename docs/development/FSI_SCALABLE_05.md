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

### C20 独立验收

| 作业 | C64 配置 | 实际接受步 | Newton / KSP | 最大原残量 / 当次门槛 | T_job（s） | 进程树峰值（GiB） |
|---|---|---:|---:|---:|---:|---:|
| 525 | PREONLY/LU，显式原式 1e-8 | 20/20 | 40 / 40 | 0.43605 | 3059.197 | 147.414 |
| 526 | physics/FGMRES，固定 1e-6 | 20/20 | 40 / 6762 | 0.99800 | 630.015 | 10.675 |

五个保存相位均完成 11 种输出量的 RMS 与局部最大值核验。固定迭代相对独立直接参考的压力、流体速度、壁位移、网格位移最大差依次为 6.746e-9 Pa、4.528e-12 m/s、3.425e-17 m、1.587e-15 m。归一化出口流量、压差及面积应变最大差分别为 2.693e-11、1.142e-10 Pa、2.308e-15。两条轨迹各自满足非线性、质量、界面和 RCR 门槛，并各自保存了通过核验的 64 份第 20 步 rank 状态。表中是含详细诊断的冷启动实测时间。[C20 校准表](../research/data/fsi-scalable-05/c20/calibration.csv) · [两个窗口的完整收据](../research/data/fsi-scalable-05/c20/run-receipts.json.gz) · [3,276 项原件哈希](../research/data/fsi-scalable-05/c20/log-index.json.gz)

## svFSI 原版 B

历史作业 438 的 14 次 MS 全部达到 2,000 次。按相同网格重建初始 MS 的约束后自由块，得到 32,256 个自由分量，初始对角最大/最小约 224.53。原生 CG 改用 RCS 后，作业 467 的首个 MS 校正 922 次达到 9.8e-11，首个 FS 仍需 3,718 次。第 4 次 MS 达到 2,000 次且线性残量比升至 1.422e5，第 4 次 FS 也超出其门槛。作业 494 保留原生 MS 选择，测试 FS 原生 BIPN，首个 FS 残量比约 0.866，随后多次接近 1。这两个未合格的作业均排除在外部配对之外。[日志索引](../research/data/fsi-scalable-05/c-native-log-index.json)

## 复跑

以下命令在上述节点上用新的输出目录运行。保留旧包与脚本提交的对应关系；后续只有脚本变化时，入口会检查生产源码树和二进制哈希。

原实验的 Release 来自 `d672e1ea9a4448658c48f212cac5f71cdffc3793`。C 的续算入口固定为 `cdbe3e96da4dbbeef4a52920d638ca113301d8bc`，相对该 Release 的 `src`、`include`、`cmake` 和顶层构建文件均相同。主线另外合并了 RCR 内层选项补丁；其独立回归和 C 的历史二进制分别归档。旧窗口复核可使用服务器原目录和收据指定的可执行文件。用不同源码构建后开展新对照时，需要该新二进制自己的独立参考窗口。[生产协议和 A/B 原始校准](https://github.com/saitoasukakawaii/EONSim-new/pull/73) · [RCR 局部 KSP 修复](https://github.com/saitoasukakawaii/EONSim-new/pull/74)

C 强扩展使用纯 MPI 分区。等 128 核的混合诊断另要求同一窗口已有合格的 128×1 样本，沿用其 64-rank 参考的原分区，启动时显式设置 `-fsi_threads 2`。每个 MPI rank 先记录实际分配的两核掩码，再用 GNU OpenMP 报告工作线程号、实际队伍大小与各线程亲和性。验收将 128 个线程位置与操作系统的物理核/插槽编号逐一对应，检查 64 个队伍、每个队伍两个线程以及跨 rank 无核重叠。该对照为一次诊断计时。[GNU OpenMP 亲和性格式](https://gcc.gnu.org/onlinedocs/libgomp/OMP_005fAFFINITY_005fFORMAT.html)

```bash
root="$HOME/workspace/fsi-scalable-05-runs"
data="$root/source/docs/research/data/fsi-scalable-05"
exe="$root/build/eonsim"
(cd "$root/source" && git diff --quiet d672e1ea9a4448658c48f212cac5f71cdffc3793 HEAD -- src include cmake CMakeLists.txt)
printf '%s  %s\n' efaad5cc91437ac022606dcf40bded9e9b504a39be8eac84611db44c3156eb05 "$exe" | sha256sum -c -
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
# C20 的两种算法分别从冻结初态开始
lujob=$(sbatch --parsable -n64 -t 01:16:00 "$data/run_case.sh" C 20 lu "$exe" "$root/recheck-C20-lu" \
  --direct-rss-gib 180 --limit 4200)
sbatch --dependency="afterok:$lujob" -n64 -t 01:05:00 "$data/run_case.sh" C 20 fixed-1e-6 \
  "$exe" "$root/recheck-C20-fixed" --limit 3000 --reference "$root/recheck-C20-lu"
# 原作业链每次提交前写出依据、内存/时间上限、完整命令和作业 ID
cat "$root/C32-plan/continuation.json"
# 已有窗口 C20-lu-180、C20-fixed-1e-6 和合格 C20-r128 后执行
sbatch -n64 -c2 -t 00:35:00 "$data/run_case.sh" C 20 fixed-1e-6 "$exe" "$root/recheck-C20-64x2" \
  --limit 1500 --reference "$root/C20-lu-180" --hybrid-from "$root/C20-r128"
```

## 固定精度的真实管 GAMG 粗层通信

B 的作业 505 用 RCR 包装的整体 MG。已启用 owner 本地 Braess-Sarazin smoother 和内部场缩放，最粗的 608 行交给 16 rank。500 次外迭代后，返回校正的原残量为 3.67620e-9，目标为 5.52652e-15，接受零步。速度、结构、压力、网格块的残量分别为 3.039e-9、2.012e-9、4.700e-10、1.082e-10。owner 路径位于 `src/algebra/fsi_level_smoother.cpp` 的 Braess-Sarazin setup/apply。合格的 physics 路径以 field split 调用各个 GAMG。在这条路径中可单独缩减粗层 Krylov 所用的通信域。[作业 505 及原 B20 子树](../research/data/fsi-scalable-05/B-coarse-baseline.json)

在 B20 的 20 个基线快照中，速度、压力、结构、网格粗层各有 42、12、39、10 行。所有行始终位于 rank 0，其余 31 个 rank 各持有零行。为这四个粗层显式启用 PETSc Telescope，设置 reduction factor 为 32，内层继续使用 GMRES/Jacobi、未预条件范数、相对容差 1e-10、最多 200 次迭代。每一步检查四个父求解器的实际通信域和行所有权，逐一检查缩减后内层的类型、范数、有效 options、收敛原因及最后一次迭代数。作业 523 在四个单 rank 子树上的最后一次 GMRES 迭代数分别为 20–22、12、17–18、8–9。[选项和核验逻辑](../research/data/fsi-scalable-05/physics_telescope.py)

作业 521 通过首步两次校正。522 和 523 分别完成 4/20 步并通过同期独立 LU、全部历史与保存场检查。B20 的 40 次 Newton 校正累计 2,362 次 KSP 迭代，最大原残量与允许值之比为 0.991232。压力、流体速度、壁位移和网格位移的最大局部差分别为 9.790e-9 Pa、7.075e-12 m/s、2.150e-16 m 和 3.844e-15 m。每个输出相位的 RMS 和局部最大差均可查。[原始窗口、选项与输出核验](../research/data/fsi-scalable-05/physics-telescope/run-receipts.json.gz)

作业 524 对 B20 双方各预热一次，再交错三对冷启动。双方固定 `CALIBRATED-v2/fixed-1e-6`、相同 LU 参考、分区、二进制、绑核、32 个单线程 MPI 进程和独占单节点 128 核分配。正式计时关闭详细监测，保留生产验收所需的原残量和每步求解器树输出。下表只取三次正式运行的中位数。[样本与资源用量](../research/data/fsi-scalable-05/physics-telescope/calibration.csv)

| B20 的粗层 Krylov 通信域 | 三次 T_job（s，按对次） | 中位 T_job（s） | Newton / KSP 中位数 | 进程树峰值中位数（GiB） | 活跃 rank-hours | 分配 core-hours |
|---|---|---:|---:|---:|---:|---:|
| 32 rank | 53.185 / 53.538 / 53.264 | 53.264 | 40 / 2360 | 1.938 | 0.4735 | 1.8938 |
| 1 rank | 36.843 / 37.291 / 37.275 | 37.275 | 40 / 2360 | 1.931 | 0.3313 | 1.3253 |

B20 的同精度通信收益为 30.02%，达到该主要算例的 15% 目标。上文的 20.67% 来自单独改变线性相对容差的作业 502。配置以 `--gamg-telescope single-rank-v1` 显式选择。A 和 C 分别在原合格的 A20、C4 基线测得单 owner 布局。各自 20 步窗口的通信性能须按该网格的合格轨迹核对。A 四个粗层行数为 8、5、8、18，C 为 11、3、14、50。B 的通信结果仅覆盖该 32 MPI 分区。运行源码为 `12e68f0cc`，后验逐步和有效容差复核为 `8fbc63546`，沿用作业 466 的生产二进制。[服务器原始文件索引及 SHA-256](../research/data/fsi-scalable-05/physics-telescope/log-index.json.gz)

复跑需在独立 checkout 中保留合格基线的编译提交，以便入口核对二进制和实际 C++ 源树。以下以 B20 为例，先按同样的参数在 1 和 4 步完成筛选，4 步使用同期直接参考。正式计时输入须为已完成独立验收的两个 20 步窗口。

```bash
root="$HOME/workspace/fsi-scalable-05-runs"
export FSI05_ROOT="$HOME/workspace/fsi-scalable-05-telescope/representative"
data="$FSI05_ROOT/source/docs/research/data/fsi-scalable-05"
exe="$root/build/eonsim"
candidate="$FSI05_ROOT/recheck-B20-gamg"
sbatch -n32 -t 00:30:00 "$data/run_case.sh" B 20 fixed-1e-6 "$exe" "$candidate" \
  --limit 1500 --gamg-telescope single-rank-v1 --gamg-baseline "$root/B20-fixed-1e-6" \
  --reference "$root/B20-lu"
sbatch -n32 -t 00:35:00 "$data/run_case.sh" B --timing \
  "$root/B20-fixed-1e-6" "$candidate" "$root/B20-lu" "$exe" \
  "$FSI05_ROOT/recheck-B20-pairs" --change gamg_telescope
python -B "$data/test_tube_protocol.py" -v
```

## A20 的两种通信比较

A 管有 869 个自由度，使用 4 个单线程 MPI 进程。作业 529 在 physics 分裂预条件器的四个 GAMG 粗层上将 Krylov 子通信器从 4 rank 缩减到 1 rank。20 步、45 次 Newton 校正、1,434 次外层 KSP 迭代通过同期 LU、原残量和完整物理验收。速度、压力、结构、网格的粗层行数分别为 8、5、8、18，所有行均由 rank 0 持有。压力、流体速度、壁和网格位移的最大局部差分别为 2.328e-8 Pa、6.394e-12 m/s、1.533e-15 m 和 1.060e-14 m。[场与历史收据](../research/data/fsi-scalable-05/A-communication/run-receipts.json.gz)

第二组使用 RCR 包装的整体 pressure-MG，比较 Braess-Sarazin 原有分量子向量读写和显式 owner 本地读写。先核对了阶段 02 的真实 A20。其 case.json、流体网格和固体网格与本轮完全相同，1 MPI 的 RCR bulk 层级为 868→305→46 行。40 个实际校正按原 RHS 重算均过旧严格门槛，20 个树快照中的首末累计 smoother 调用数为 2,148 和 35,996。该原始日志的 SHA-256 为 `5baa76e341031141d85e4ed4f43f7ed45eab43c1e31fcd4651f362178f66fb67`。[早期筛选收据](../research/data/fsi-scalable-02/final-validation.json)

本轮 533/534/535 在 4 MPI 上依次验证 1、4、20 步。两个 owner 配置沿用相同的压力粗化、V 循环、未启用的内部场缩放和粗层行预算。每一侧的 4/20 步都完成独立 LU 与完整场、历史、质量、界面和 RCR 对照。实际层数为 5，粗求解器通信域含 2 rank。20 步诊断两侧各有 40 次校正，owner 关闭与开启时每个 rank 的末次累计平滑及 Schur 调用数分别为 49,936 和 50,120。作业 535 的 owner-on 压力、速度、壁和网格位移最大差分别为 8.050e-12 Pa、2.951e-14 m/s、2.327e-18 m 和 6.422e-16 m。归档器逐步检查实际 `root/rcr_bulk` 子树、每个 rank 的有效调用以及 PETSc 有效选项。[运行原件索引](../research/data/fsi-scalable-05/A-communication/log-index.json.gz)

两组均固定 `CALIBRATED-v2/fixed-1e-6`、独占 128 核，分别预热一次并交错三对。在每组自己的对照中，只改变表内的通信选项。所有正式样本均通过与作业 529 相同的 A20 直接参考及物理验收。[逐次样本](../research/data/fsi-scalable-05/A-communication/calibration.csv)

| 20 步正式配置 | 作业 | 三次 T_job（s，按对次） | 中位 T_job（s） | Newton / KSP 中位数 | 峰值 RSS 中位（MiB） | 活跃 rank-hours | 分配 core-hours |
|---|---:|---|---:|---:|---:|---:|---:|
| physics，4 rank 粗层 | 530 | 2.3213 / 2.3214 / 2.3212 | 2.3213 | 45 / 1432 | 111.65 | 0.00258 | 0.08254 |
| physics，1 rank 粗层 | 530 | 1.8135 / 1.8059 / 1.8059 | 1.8059 | 45 / 1434 | 111.52 | 0.00201 | 0.06421 |
| pressure-MG，owner off | 536 | 6.3350 / 6.3342 / 6.2366 | 6.3342 | 40 / 6187 | 125.23 | 0.00704 | 0.22522 |
| pressure-MG，owner on | 536 | 2.9739 / 2.9237 / 2.9739 | 2.9739 | 40 / 6217 | 129.13 | 0.00330 | 0.10574 |

physics 粗层缩核在主要 B20 上的中位降幅为 30.02%，在代表网格 A20 上为 22.20%，达到主要算例 15% 和代表算例退化不超过 5% 的门槛。pressure-MG 的 owner 本地读写在真实 A20 上取得 53.05% 的同精度降幅。四个 A 配置中，physics 单 rank 粗层的 1.8059 s 最快。B/C 的 Braess owner 性能仍需其合格整体 MG 解。作业 529–536 的脚本为 `8fbc63546`，沿用作业 466 的生产二进制。

复跑沿用上节的 `root`、`FSI05_ROOT`、`data`、`exe`。A 的 physics 比较按上节命令使用 4 MPI 和相应 A20 基线。以下为 owner 比较的两个诊断窗口及正式组，1/4 步首筛分别使用同窗直接参考和 35/60 s 预算。正式作业须在两个独立诊断窗口就绪后执行。

```bash
for mode in off on; do
  sbatch -n4 -t 00:08:00 "$data/run_case.sh" A 20 fixed-1e-6 "$exe" \
    "$FSI05_ROOT/recheck-A20-owner-$mode" --limit 150 --pc pressure-mg --owner "$mode" \
    --reference "$root/A20-lu"
done
sbatch -n4 -t 00:24:00 "$data/run_case.sh" A --timing \
  "$FSI05_ROOT/recheck-A20-owner-off" "$FSI05_ROOT/recheck-A20-owner-on" \
  "$root/A20-lu" "$exe" "$FSI05_ROOT/recheck-A20-owner-pairs" --change owner
```

## C20 的纯 MPI 强扩展

在作业 525/526 已独立验证同一 C64 窗口后，537/538 分别对原始 C 网格生成 32 和 128 份新分区。采用同一个 `CALIBRATED-v2/fixed-1e-6`、physics 配置、Release 二进制和 64-rank LU 参考。每个布局冷启动一次，实际绑定逐 rank 核实为一个独占物理核，OpenMP 和 BLAS 各设一个线程。20 步历史、五个保存相位的全部节点场、质量、界面及 RCR 均通过。32/128 rank 的分区准备分别为 6.023/6.087 s，单列于求解 T_job 之外。64 rank 沿用已归档分区。[独立参考及 64-rank 原件](../research/data/fsi-scalable-05/c20/run-receipts.json.gz)

| MPI rank | 作业 | T_job（s） | T32/Tn | 相对 32 rank 效率 | Newton / KSP | 峰值 RSS（GiB） | 活跃 rank-hours | 分配 core-hours |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 32 | 537 | 928.545 | 1.000 | 100.00% | 40 / 6779 | 10.558 | 8.254 | 33.015 |
| 64 | 526 | 630.015 | 1.474 | 73.69% | 40 / 6762 | 10.675 | 11.200 | 22.401 |
| 128 | 538 | 460.145 | 2.018 | 50.45% | 40 / 6842 | 13.518 | 16.361 | 16.361 |

效率为 $(T_{32}/T_n)/(n/32)$。三次诊断都独占整台 128 核节点，所以将求解耗时乘以 128 计算分配核时。活跃核时则乘以实际 MPI 数。32、64、128 rank 的压力场相对同一 LU 的局部最大差分别为 4.709e-9、6.746e-9、5.926e-9 Pa。窗口包含相同的原式诊断、场输出与原生 checkpoint。完整场文件、运行前的分区 SHA、实际绑核记录和原始求解器输出保留在服务器。归档汇总包含新分区的独立原件索引与逐窗收据。[尺度汇总](../research/data/fsi-scalable-05/c20-scaling/strong-scaling.json) · [原件 SHA-256](../research/data/fsi-scalable-05/c20-scaling/log-index.json.gz)

跨分区的参考界面面积从流体网格中 13,824 个原始三角面独立求和，得到 0.0018848714833712772 m²。冻结的 32 与 128 rank 绝对核验界限分别为 5.826e-15 和 5.853e-15 m²。每个布局的原方程、不同分区下的完整保存场和历史都按既有容差核验。这些数值来自每种布局一次冷启动。通信选项的正式三对计时另行报告。[完整场、历史及几何收据](../research/data/fsi-scalable-05/c20-scaling/run-receipts.json.gz)

现场复跑使用作业 466 的编译提交、同源二进制和具备这份源码对象的独立 checkout。原两份窗口的脚本为 `8fbc63546`，64-rank 基线取作业 526。使用新的输出目录保留原记录。

```bash
root="$HOME/workspace/fsi-scalable-05-runs"
export FSI05_ROOT="$HOME/workspace/fsi-scalable-05-telescope/representative"
data="$FSI05_ROOT/source/docs/research/data/fsi-scalable-05"
exe="$root/build/eonsim"
for ranks in 32 128; do
  if [ "$ranks" = 32 ]; then wall=00:36:00; limit=1800; else wall=00:26:00; limit=1200; fi
  sbatch -n "$ranks" -t "$wall" "$data/run_case.sh" C 20 fixed-1e-6 "$exe" \
    "$root/recheck-C20-r$ranks" --limit "$limit" --scaling-from "$root/C20-fixed-1e-6" \
    --reference "$root/C20-lu-180"
done
# 两个新窗口取得独立资格后，使用本提交的汇总入口。
python docs/research/data/fsi-scalable-05/summarize_scaling.py "$root/C20-lu-180" \
  "$root/recheck-C20-r32" "$root/C20-fixed-1e-6" "$root/recheck-C20-r128"
```

## C20 的等核混合布局

作业 541 保留 C20 物理和冻结容差，将 128 个物理核分配给 64 个 MPI rank，每个 rank 运行两个实际 OpenMP worker。Release 二进制使用现有 FSI 装配的 `-fsi_threads 2` 实现。OpenMP 启用核绑定，关闭动态线程调整，BLAS 各用一个线程。按进程输出的亲和记录核对了 64 份两核 MPI 掩码以及全部 128 个 worker 的物理核映射，且各组互不重叠。分区沿用原 C64，直接参考仍为作业 525。作业 541 绑定的 128×1 对照是作业 538，原收据 SHA-256 为 `7fc898a4439c62ea384fee0f71442877d7be05d55dc24e1b6a98a9b10798be32`。[两核 worker 与实际亲和记录](../research/data/fsi-scalable-05/c20-hybrid/run-receipts.json.gz)

| 布局 | 作业 | T_job（s） | Newton / KSP | 进程树峰值（GiB） | 活跃 rank-hours | 活跃物理核及分配 core-hours |
|---|---:|---:|---:|---:|---:|---:|
| 128 MPI × 1 线程 | 538 | 460.145 | 40 / 6842 | 13.518 | 16.361 | 16.361 |
| 64 MPI × 2 线程 | 541 | 432.632 | 40 / 6787 | 10.713 | 7.691 | 15.382 |

这是同核数下每种布局一次冷启动诊断。混合布局在这两个样本中用时缩短 5.98%，两者时间比为 1.0636。它包含分区数和装配线程安排的共同变化。两侧均核验全部原校正、20 步历史和五个保存相位，混合布局的压力、流体速度、壁位移和网格位移最大差分别为 5.118e-9 Pa、3.065e-12 m/s、4.096e-17 m 和 1.413e-15 m。作业 541 的运行脚本提交为 `cdbe3e96d`，沿用作业 466 的二进制与编译源码。[混合布局原件索引](../research/data/fsi-scalable-05/c20-hybrid/log-index.json.gz)
