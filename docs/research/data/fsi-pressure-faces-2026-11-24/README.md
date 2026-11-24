# 厚壁圆管加载后第一秒的端面功与截面扩张

在相同的 48 扇区网格上，将步长从 0.5 s 减至 0.125 s，EONSim 与 svFSI 在 1 s 的最大截面扩张差由 5.32% 增至 9.03%。分母为 Lamé 解析稳态面积应变 0.00217454545。两套程序在同一物理时刻、相同的七个轴向截面比较。此结果限定于启动瞬态。详细数值见[逐步端面记录](traces.csv)和[误差及累计量](results.json)。

## 算例与时间层

采用 PR #42 的四分之一圆管，内外半径分别为 1 和 1.2 m，长 2 m。流体与固体密度均为 1 kg/m³，动力黏度 1 Pa·s，线弹性壁的杨氏模量为 100 Pa、泊松比 0.3。流体 1512 个、管壁 1728 个 Tet4，圆周方向的 48 扇区按整圆计。初始状态静止，两端同时施加 0.02 Pa，轴向滚动支承，外壁自由。端面允许沿径向运动。面积、流量、体积和功对应四分之一模型。[原始网格、材料与边界](https://github.com/saitoasukakawaii/EONSim-new/blob/0c8f6fbd057028021fe8b598e037ebc0956254a9/docs/development/PRESSURIZED_ELASTIC_TUBE.md)

两程序使用 generalized-α，谱半径 0.5。EONSim 的第一步使用 BE，后续步的载荷阶段为步内的 2/3 处。EONSim 在三个步长上各运行四组组合，涵盖阶跃和 1 s 五次光滑升载，以及默认单元稳定化和统一固定 τ=0.007716762652107021。该固定值取静止初态、BE 步长 0.25 s 时全部流体单元默认 τ 的中位数。统一固定值同时改变了系数的空间分布。所有 12 个 EONSim 算例均在同一个 MPI 进程上计算，沿用输入的 Newton 容差 1e−11/1e−13。[EONSim 计算脚本](run.py)

svFSI 对照使用恒定阶跃压力。0.5 s 和 0.25 s 取原归档场。以 GNU 15.3.0、Open MPI 5.0.8、CMake 3.31.8 重新构建固定版 Fortran svFSI，先重放 0.25 s 的前四步，再完成 0.125 s 的八步。比较重放与归档的逐节点场，两域的位移及速度、流体域压力的最大差均为零。流固及网格两个方程的逐步收敛记录均通过原检查。外部表格的 endpoint 列对应 VTU 的输出时刻，stage 列留空。[固定版源码](https://github.com/SimVascular/svFSI/tree/94a2ff5cab2ad9e89e9bf12e0de36eaaa9b85571) · [重建与细化运行](run_external.py)

## 三档步长

在各轴向截面，对参考截面多边形面积沿实际位移求一阶导数，得到线性化面积应变。表中两列百分数均取两程序之差的绝对值，再在七个截面中取最大值。压力功取两端面之和。

| 步长 (s) | 0.5 s 的截面扩张差 | 1 s 的截面扩张差 | 0–1 s EONSim 压力功 (µJ) | 0–1 s svFSI 压力功 (µJ) |
|---:|---:|---:|---:|---:|
| 0.500 | 9.947% | 5.321% | 35.33 | 47.27 |
| 0.250 | 6.196% | 8.429% | 45.04 | 47.78 |
| 0.125 | 6.163% | 9.028% | 49.15 | 48.06 |

两列功都对端点功率使用梯形求积，初始流量为零。改变首步求积能解释一部分累计量偏差。以 0.125 s 阶跃工况为例，EONSim 端面累计净流入比几何体积增量小 5.406%。仅将首步改为与 BE 对应的右端点求积，1 s 的差变为 +0.365%。这是对同一组速度和位移的重新积分。截面扩张差来自独立保存的位移场，数值仍为 9.028%。此累计差包含移动几何和时间求积的影响，瞬态根因还需进一步分解。

在 EONSim 的 0.125 s 步长下，把阶跃换为 1 s 光滑升载，1 s 中截面应变从解析稳态值的 80.33% 降至 47.73%。在同一阶跃下把默认 τ 换成上述固定值，中截面从 80.33% 变为 80.19%，七个截面中最大的变化为解析稳态扩张量的 0.327%。这些是分别改变载荷或稳定化得到的同程序对照。跨程序的光滑加载和相同启动算法仍待验证。

## 独立积分检查

单元法向应力取当前构形上流体侧的 Cauchy 应力，拉为正，功率取外压乘流入量。两端共 112 条 EONSim 接受步记录各包含 stage 和 endpoint 两个样本。审计从端点 VTU 重建每个阶段的节点坐标、速度和压力，按边界三角面与相邻四面体重新积分。面积、压力均值、法向应力均值、流量、功率的最大绝对差依次为 5.56e−16 m²、1.22e−17 Pa、1.39e−17 Pa、1.31e−18 m³/s 和 3.39e−20 W。第一步和两端分别核对。此项检查验证时间层、面定向和归约。Lamé 公式只提供静态归一化尺度。[独立场积分脚本](audit.py) · [输出定义](../../../development/FSI_PRESSURE_HISTORY.md)

以 0.5 s 步长的首步为例，标签 1 的施压为 0.02 Pa、面均静压为 0.012406 Pa、恢复法向应力为 −0.014816 Pa。流量为 −0.0012331 m³/s，外压向流体输入 24.66 µW。弱式载荷、压强迹与应力迹分别测量。

## 重现

以下命令从仓库根目录执行。审计使用 NumPy 和 VTK 9.3.1。第一次解包应提取完整参考归档，以便恢复跨目录的硬链接。新的算例目录应为空。

```bash
data=docs/research/data/fsi-pressure-faces-2026-11-24
work=build/pressure-face-study
mkdir -p "$work/reference" "$work/external"
git fetch origin refs/pull/42/head
git worktree add --detach "$work/wall-source" 0c8f6fbd057028021fe8b598e037ebc0956254a9
tar -xJf "$work/wall-source/docs/research/data/lame-wall-2026-11-20/raw.tar.xz" -C "$work/reference"
tar -xJf "$data/svfsi-one-second.tar.xz" -C "$work/external"
bash scripts/cloud/restore.sh 3.23.7
python3 -c 'import json,sys; json.dump({"tests":["fsi_pressure_state","fsi_tube","fsi_diagnostics","fsi_diagnostics_mpi"]},sys.stdout)' > "$work/selection.json"
bash scripts/cloud/run.sh 3.23.7 release explicit .cloud "$work/selection.json"
LD_LIBRARY_PATH="$PWD/.cloud/petsc-3.23.7/lib" python3 "$data/run.py" \
  --archive "$work/reference" --executable build/cloud-3.23.7-release/eonsim --work "$work/cases"
OPENBLAS_NUM_THREADS=1 python3 "$data/audit.py" --reference-scripts "$work/wall-source/scripts" \
  --archive "$work/reference" --work "$work/cases" --external-work "$work/external" --output "$work/results"
```

要重新执行独立程序，使用包含 GNU C/C++/Fortran 15.3、Open MPI 5.0.8、Ninja、CMake 3.31.8、BLAS、LAPACK、zlib 的独立环境。将 `svsrc` 设为固定提交的检出目录、`svprefix` 设为该依赖环境的绝对路径。

```bash
bash "$data/build-svfsi.sh" "$svsrc" "$svprefix" "$work/sv-build"
LD_LIBRARY_PATH="$svprefix/lib" python3 "$data/run_external.py" --archive "$work/reference" \
  --executable "$work/sv-build/bin/svFSI" --work "$work/external-rebuilt"
```

新归档包含两个重算的输入、12 个逐步 VTU、两组收敛历史和可执行文件摘要。归档 SHA-256 为 `06ee3aed025aba8a3d3f01cab3a4e1cace2e31bca6b02e36d8772217996d2399`。原 PR #42 的参考归档为 `f7047b66e0d67fcf6bf966ed21754e666a5bb9dd65ba249ed0541700c51a7b77`。[新外部原始场](svfsi-one-second.tar.xz)

## 软件回归证据

从 `main@951064d` 检出旧代码，增添单元解析断言，运行原压力缩步检查及新断言。旧代码两项均失败。两次 Newton 迭代后，第 16 次缩步的主线残量为 9.38e−11。数值修复先在节点对两时间层的速度作差，再将增量插值到积分点。相同试验在 Δt=6.103515625e−8 s 达到残量 3.81e−11，写出一个接受步。另以恒定速度的一个可表示浮点增量构造单位加速度，检验 Tet4 各节点的解析惯性力。

锁定 PETSc 3.23.7，用 `scripts/cloud/run.sh` 执行了 36 项 Release 增量选测，随后在最终代码上单独复核 4 项端面相关检查。四进程圆管的端面流量还与已有移动域质量预算相符。单进程时间步重放、同分区恢复、缩步及关闭输出的路径均覆盖。实测范围为单节点 CPU。[逐项测试和原失败](validation.json) · [数值修复](https://github.com/saitoasukakawaii/EONSim-new/commit/ae6c8f61ca882ed7baa7c4296eb99d03e66e60e9) · [最终源码](https://github.com/saitoasukakawaii/EONSim-new/commit/369720401450298b18808e50ec6a31423c3500ce)
