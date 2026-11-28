# svFSI B 的第四次网格校正

32-rank B 对照尚未完成 20 步。旧作业 438 在 780 s 内接受两步。作业 467 保留 FS 子空间 850，单独给网格 CG 启用原生 RCS。前三次 MS 用 922、881、815 次迭代达到其原生判据，随后第四次 FS 耗尽 17,020 次迭代，第四次 MS 耗尽 2,000 次。作业 494 测试原生 FS BIPN，也没有产生合格轨迹。EONSim/svFSI 外部配对缺失。原生作业使用 svFSI 的缩放残量设置，EONSim 的 STRICT-v1 与 CALIBRATED-v2 资格另行记录。

## 相同方程与返回向量

作业 527 复用 467 的二进制对象、完整输入和分区。先重新链接原始对象并对二进制做 SHA-256 相等检查，再仅替换 `LS.f.o`，围绕原始 `FSILS_SOLVE` 保存 MS1、MS4 各 rank 的输入、约束权重、映射、原始块矩阵、缩放后块矩阵与实际返回解。采集程序在 MS4 返回后退出，接受步数为零。首次外部解析误将分布式 Dirichlet 正权重限制为 1，保留失败日志。原生 `PRECONDRCS` 先对共享结点求和再以 0.5 区分固定和自由分量。按该实现重读相同 128 个分片得到作业 545 和 555 的结果。[原生预条件器](https://github.com/SimVascular/svFSI/blob/7bdb74cdd517310d6bf32c0bb7d42072aeac8658/Code/Source/svFSILS/PRECOND.f)

两次自由矩阵及其 RCS 矩阵逐项相同，32,256 个自由分量、26,439 个约束分量完全一致，所有被约束返回分量均为零。原矩阵与缩放矩阵的相对对称缺陷分别为 4.22e-17 与 6.32e-17。Jacobi 对称归一化后的最小 Ritz 估计为 2.47e-4，特征残量为 2.36e-9，此项只提供当前试探子空间上的证据。

| 量 | 第一次 MS | 第四次 MS |
|---|---:|---:|
| 原生 CG 迭代 | 922 | 2,000 |
| 原生缩放残量，首 → 末 | 3.95256e-2 → 3.89443e-12 | 5.13113e-9 → 7.30115e-4 |
| 原始自由行 RHS 二范数 | 1.50774 | 1.84757e-7 |
| 用 owner 向量重算的原方程残量二范数 | 4.05345e-10 | 35.0627 |
| 同一残量除以原始 RHS | 2.68842e-10 | 1.89777e8 |
| 用实际 rank-local 返回副本装配的残量二范数 | 4.05350e-10 | 7.42663e-2 |
| 分量后向误差最大值 | 3.04565e-10 | 9.88742e-1 |
| 求解前共享自由 RHS 最大副本差 | 1.38778e-17 | 3.46945e-18 |
| 共享自由返回向量最大副本差 | 3.47704e-16 | 2.37875e-3 |

第四次返回中，全局结点 7591 的 z 分量在 owner rank 24 为 −1.54688641998e-3，在 rank 21 为 +8.31865930542e-4。单副本复算从两个矩阵的对角比得到正缩放 D，验证自由矩阵的 `D A D` 与原生缩放矩阵相对差为 9.63e-17，`||D b||` 与原生初始范数之比为 0.9999999999999993。在同一缩放方程、原 2,000 次上限下，单副本 CG 用 797 次达到缩放真相对残量 9.90839e-11，原变量真相对残量为 3.14348e-10。第一次同法用 922 次，缩放真相对残量为 9.71518e-11。

原生稀疏乘使用本地副本，再通信求和。CG 的全局内积只累计 owner 分量，各 rank 则保留和更新本地的搜索方向、残量与解。作业 555 直接证实了第四次终端解的共享副本分歧，单副本 CG 时间没有计入任何配对样本。要让原生 B 获得配对资格，第四次 FS 和 MS 两个失败都要通过，并完成独立物理验收。[原生通信](https://github.com/SimVascular/svFSI/blob/7bdb74cdd517310d6bf32c0bb7d42072aeac8658/Code/Source/svFSILS/INCOMMU.f) [原生 CG](https://github.com/SimVascular/svFSI/blob/7bdb74cdd517310d6bf32c0bb7d42072aeac8658/Code/Source/svFSILS/CGRAD.f)

## 复核

在开发节点用带 NumPy/SciPy 的 Python 复核，保留独占分配。第一条命令从同一服务器上归档的 467 输入重新采集。第二条命令可直接核验原始 527 分片的 SHA-256 并重算所有表中指标。

```bash
tools=docs/research/data/fsi-scalable-05
root="$HOME/workspace/fsi-scalable-05-native-ms"
py="$HOME/miniforge/envs/moose/bin/python"
sbatch --exclusive -N1 -n32 -c1 -t 00:08:00 \
  --wrap="exec '$py' '$tools/native_ms_snapshot.py' '$root/new-capture'"
sbatch --exclusive -N1 -n1 -c1 -t 00:03:00 \
  --wrap="OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 '$py' '$tools/native_ms_system.py' '$root/observe-527' '$root/recomputed.json'"
```

采集提交 `13b7ea59d`，约束重读 `63563b92f`，单副本复算 `517abf84f`。内含 128 个分片 SHA-256、输入、运行命令、工具链来源和二进制 SHA-256 的原始收据以 gzip 存储，原文件 SHA-256 为 `0f4caae6a841c0df607cbef076111042029bfc3eed137da640c9f0fb4a0d8796`。[采集收据](native-ms-527.json.gz) [约束与原方程复核](native-ms-545.json) [单副本与分布式返回向量复核](native-ms-555.json)

| 服务器文件，以 `$HOME/workspace/fsi-scalable-05-native-ms` 为根 | SHA-256 |
|---|---|
| `observe-527/solve.log` | `8936ce4d36aff96f1328d19550d2754924fc0bdf9ccf202cfc8501a3d1a10b57` |
| `observe-527/32-procs/histor.dat` | `aa3c2d39e7cd7d14a73498bd44c8da68116295496bc93454c6b610688ec7abd1` |
| `native-ms-527.log` | `6b19fe250d456f37c2788f20c15a92a5b6dc3cc27df3f4efbc5af0d2a2a50d42` |
| `ms-system-545.json` | `10787d3882b4d078cf858d8ba61c3359b6c37f8fc81a2a710648c19bd4acfd3e` |
| `ms-system-555.json` | `9839563d6a8a24d90e4b893f64494c211fd03624f45c641b5049f9b2b1c3309d` |
