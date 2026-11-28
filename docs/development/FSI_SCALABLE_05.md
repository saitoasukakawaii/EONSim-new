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

## 复跑

以下命令在上述节点上用新的输出目录运行。保留旧包与脚本提交的对应关系；后续只有脚本变化时，入口会检查生产源码树和二进制哈希。

```bash
root="$HOME/workspace/fsi-scalable-05-runs"
data="$root/source/docs/research/data/fsi-scalable-05"
exe="$root/build/eonsim"
sbatch -n32 -t 00:15:00 "$data/run_case.sh" B 20 lu "$exe" "$root/recheck-B20-lu" --limit 420
# 独立 LU 窗口实际完成后执行
sbatch -n32 -t 00:30:00 "$data/run_case.sh" B 20 fixed-1e-6 "$exe" "$root/recheck-B20-fixed" \
  --limit 1500 --reference "$root/recheck-B20-lu"
python -B "$data/test_tube_protocol.py" -v
```
