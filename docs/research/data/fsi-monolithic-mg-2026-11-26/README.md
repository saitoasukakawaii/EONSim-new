# FSI-MG-01：整体多重网格与 Matrix-free 优化证据

交付 [PR #61](https://github.com/saitoasukakawaii/EONSim-new/pull/61)，基线为
`main@3472a18a5c7ad112084ec551a28a11d84bd3c4e7`（已合并 #59）。最终生产源码为
`3b5cbddb928dfa789dc1f3f424dba451f33107e6`，完整 tree 为
`2cca4aba25978f91a557dae538b2e056c2ab80c3`。后续文档和证据提交不算新的数值执行。

[使用与完整参数](../../../development/FSI_MONOLITHIC_MULTIGRID.md)、
[未发布算法草稿](../../../../website/drafts/fsi-monolithic-multigrid-matrix-free.md)、
[机器可读汇总](summary.json)、[来源](provenance.json)、[原日志成本表](measured-costs.csv)。

## 1. 范围与源码同步顺序

本次实现全部十二条请求：完整混合 Galerkin 多重网格、逐层 Vanka、结构顺应性压力 Schur、
受约束插值能量下降、局部自适应谱粗空间、PCD Robin/速度质量增强、patch 批量分解与
精确缓存、正规方程 Chebyshev/Block Chebyshev、FP32 稀疏 V-cycle、粗层 MPI 聚合、
PIPEFGMRES、精确 matrix-free FSI 及独立刷新 assembled P。

物理残量、约束、接口消元和历史接受规则保持。新能力均显式选择，没有把性能研究中的参数
替换成默认物理求解设置。局部谱增强不等于全局误差学习；完整层级不证明一般 inf-sup
稳定性或网格无关性；当前 P 仍完整存储。性能事实见下文，不由算法名称推断。

| 远端源码 | tree | 同步后执行 |
|---|---|---|
| `03b922c5070bd444180d23868c20482c93701e18` | `44afb4e53f30f16fd814bf21e921b21fc6b51d3c` | 首版完整源已同步；尚未执行构建，随后补 Mat 生命周期引用 |
| `4d3fd8e4e4779f6e03858f7865ec4b2b4c7df176` | `506545f287d36f6b2ddfdfaca1cd55d2fd953062` | 首次 Release 构建；压力/平滑/方向导数/环境检查；MG 与 MF 故障检查；4 次物理解 |
| `87c2456e714bc9853b7d112f69964af7e1fbb0c1` | `280de1ec744c228ca43048d0f6fb908357761415` | MG 缓存及残量锁修复；MG 3/3；扩展 MF 暴露流水线问题；21 次全模式及 15 次规模/耦合研究 |
| `3b5cbddb928dfa789dc1f3f424dba451f33107e6` | `2cca4aba25978f91a557dae538b2e056c2ab80c3` | 有界粗层及流水线错误协议；受影响 12 项 CTest；28 次物理复验；远端 95 项 Release |

每次生产/测试修改都先通过已连接的 GitHub API 同步，并核对完整 tree，再构建或运行。
本地 Git 缺少 HTTPS 写凭据，没有修改权限或保护。第一条记录的 CLI 构建尝试因 wrapper
执行权限在运行前失败，改为显式 `bash` 后配置成功；原日志保留。完整同步时间在来源 JSON。

最终本地 eonsim SHA256 为
`e36709e019aa2312e4f5da3145a0c1ac59650d3086841554f228f5a91584e83e`，最终驱动 SHA256 为
`b09fc5e4f3a32f759b59c81f695b3f992e3d6f9da460f0709ea434755b833667`。旧二进制已经被
后续构建替换，其身份只能由当时 receipt/build 记录固定；没有假称重新读取了旧 ELF。

## 2. 当前有效定向验证与失败闭环

环境：Linux 单个共享容器、AMD EPYC 9V74、可见 affinity 9 CPU，锁定 PETSc 3.23.7，
real/double/32-bit PetscInt，Open MPI 5.0.8、GNU 15.3.0、OpenBLAS、Release。
构建并行 2，每个 MPI rank 的 OMP/BLAS/MKL 线程均为 1；最多 4 rank，仅用于正确性。

| 当前有效本地检查 | 结果与来源 |
|---|---|
| pressure Schur MPI 1/2/4；added-mass pressure MPI 1/2/4；物理压力 SELF/WORLD 两项 | `4d3fd8e` 8/8，通过后相关生产代码未变，复用原证据 |
| interface patch、FSI level smoother、monolithic MG，各 MPI 1/2/4 | `3b5cbdd` 9/9，包含 cap=12 完整混合粗块覆盖与显式粗 overlap=1 超限拒绝 |
| matrix-free MPI 1/2/4 | `3b5cbdd` 3/3，FGMRES/PIPEFGMRES × insertion/COO × 第一次/第二次 action 故障及恢复 |
| runtime MPI；FSI element Jacobian/精确方向作用 | `4d3fd8e` 2/2，后续修改没有改变局部物理算子或运行依赖 |
| CI 路径选择 Python | `3b5cbdd` 本地 26/26 |

共 22 项当前有效 CTest 覆盖，不是 22 项在最后提交全部重跑。原始失败分别保留：

1. **MG 精确缓存，4 rank。** 第一轮 MPI 1/2 通过，4 rank 因深层重复 `MatPtAP` 的舍入
   变化不满足精确缓存命中断言。修复使用共同的源 Mat 数值状态判断，未变化时保留粗算子
   和分解。没有放宽数值相等判断；`87c2456` 三档通过。
2. **MF 残量只读锁。** 正常求解后注入 action 异常，下一次调用写残量失败。PETSc 的
   RHS 锁可能因错误码提前返回而未释放；先修复为隔离 trial 与残量，并重建残量 COO。
3. **PIPEFGMRES 未完成归约。** 扩展到第二次 action 后，`87c2456` 的普通 FGMRES 通过，
   PIPEFGMRES 报 `Operation done in wrong order`。最终错误粘滞，临时有限输出只用于完成
   已启动归约，再由 convergence callback 失败退出；错误后不再执行物理装配或接受状态。
   所有 1/2/4-rank 组合通过，没有访问 PETSc 私有锁/归约字段。
4. **物理粗层 patch 过大。** `87c2456` 的 n6/n8、FP64/FP32 共四次 setup 超限失败。
   默认细层重叠 1、粗层额外重叠 0 后，每个粗 patch 保留完整混合聚合体基，完整 Galerkin
   耦合保持，256 上限保持。两档网格复验通过，没有截断 patch 行。

压力独立 oracle：added-mass 全动量消元最大归一化差 `8.11727e-14`；Robin 三次面
积分差 `1.29694e-16`；增强 PCD action 差 `8.46431e-16`；含 D 的 Stokes 模型作用差
`7.64809e-13`，小于原 `2e-12` 门槛。

## 3. 真实 FSI 和独立原件审计

所有成功轨迹对照相同模型的 MUMPS 直接解。门槛未变：保存场和历史绝对差 `2e-9`，
原算子真实线性残量 `1e-12 + 1e-10*rhs_norm`。包含 generalized-alpha、非等步长、
移动 RCR、流固密度比与时间步变化。求解状态、保存状态、接受时间和电路一致检查。

| 批次 | 源码 | 成功 / 保留失败 | 接受步 | 实测线性残量 |
|---|---|---:|---:|---:|
| physical-01：首次 mono/direct 1/2 rank | `4d3fd8e` | 4 / 0 | 12 | 24 |
| physical-02：全部模式及移动 RCR | `87c2456` | 21 / 0 | 63 | 135 |
| physical-03：规模及耦合 | `87c2456` | 11 / 4 | 33 | 66 |
| physical-04：受影响 MG、MF、MF+PIPEFGMRES 及移动 RCR | `3b5cbdd` | 15 / 0 | 45 | 99 |
| physical-05：703/2299/5367 DoF 及两组耦合 | `3b5cbdd` | 13 / 0 | 39 | 78 |
| **累计本地** | 分别固定来源 | **64 / 4** | **192** | **402** |

最后 28 次复验的最大保存数组/坐标差 `5.666578317686799e-13`、历史差
`7.993605777301127e-15`、真实残量/门槛比 `0.009043886409524391`。
累计最大场差 `6.439737632035758e-12`，残量比 `0.009155881912702717`。
RCR 方程最大缺陷 `4.0766001685454967e-17`，全部 11,216 个已检查 owner/ghost 副本差为 0。

独立标准库解析器没有调用原驱动的 audit 函数，重读 log/CSV/VTU/PVTU/PVD、全部保存
流体/固体状态、边界 piece、全局身份及有向拓扑。最终两批 1,303 条原 artifact
哈希/长度与 36 条 command log 哈希均一致；累计 2,872 与 86 条，清单 2,881 个唯一文件。
文件读取次数、断言数和独立文件数分开记录，未相互替代。

**没有保存 J、b 和 Newton 增量。** 审计重新核查求解时真实残量诊断的 norm/rhs 标量，
不是离线再次计算 `J*dx-b`。这个限制也写在各 JSON 中。

## 4. 已测收敛、成本与存储

下表均为 2 rank、三步六次线性修正的累计数；一次运行的时间不能视为受控重复 benchmark。

| DoF | 模式 | 外层迭代 | solve 秒 | linear 秒 |
|---:|---|---:|---:|---:|
| 703 | direct | 6 | 0.065423 | 0.037590 |
| 703 | mono | 104 | 0.741733 | 0.387775 |
| 703 | mono_fp32 | 104 | 1.118293 | 0.770415 |
| 2299 | direct | 6 | 0.211388 | 0.127057 |
| 2299 | mono | 151 | 4.074699 | 2.524272 |
| 2299 | mono_fp32 | 151 | 5.787781 | 4.199273 |
| 5367 | direct | 6 | 0.578674 | 0.382512 |
| 5367 | mono | 206 | 15.203076 | 10.205967 |
| 5367 | mono_fp32 | 206 | 20.281251 | 15.263721 |

迭代增长接近两倍，不能宣布网格无关。在所测窗口中直接解更快，FP32 也未加速。
首个 n3 例的 Chebyshev/Block Chebyshev 为 1-rank 1441/1487、2-rank 1298/1020 次，
当时 Vanka 为 75 次，因此多项式只作为可选并行平滑方式，不被称为普遍优选。

有界粗 patch 改变前后，703 DoF mono 从 102→104 次、solve 2.321530→0.741733 秒；
FP32 从 102→104 次、3.436850→1.118293 秒。对应物理配置及输入 mesh 哈希一致。
n6/n8 修复前失败，不能为其编造成功耗时比；共享主机及并行验证活动限制配对时间的解释。

最终 5367 DoF 层次实际为 **5367→1354→178→42**，最粗层进程数 1。中间两层实际
覆盖行数分别恰为 1354 和 178，最大 coarse patch 都为 21；跨聚合体项仍在完整矩阵中。

| DoF | 全部 smoother LU 系数字节 FP64 / FP32 | FP32 层矩阵/插值 CSR 系数字节 |
|---:|---:|---:|
| 703 | 3,626,056 / 1,813,028 | 522,284 |
| 2299 | 15,225,352 / 7,612,676 | 2,777,068 |
| 5367 | 40,025,728 / 20,012,864 | 8,209,604 |

上述为全 ranks 合计的系数数组，不含 FP64 setup 矩阵、粗层直接因子、索引、pivot、向量及
通信缓冲。5367 DoF 的最大 rank peak RSS 为 FP64 198.668 MiB、FP32 214.629 MiB；
局部系数减半没有减少总内存。

最终 2-rank n3 中 mono、mono_mf、mono_mf_pipe 都为 76 次外迭代；P 组装从 6 次降为
3 次，后两种实际方向作用为 88/94 次，均复用 P 3 次。移动 RCR 后两种均 155 次外迭代，
P 组装 6 次/callback 9 次/复用 3 次。精确 Jv 和 P 的状态分离已实际覆盖，但当前完整 P
仍存储，不能据此宣布全局 Jacobian/预条件器总存储减少。

## 5. 远端 CI

源码 CI [45819157827](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45819157827)
实际 **95/95 Release、54/54 Python 通过**，Release 无失败、无跳过、无历史数值复用。
测试名称与成功 incremental receipt 一一对应。合并预览 `29f1ed80453b49098de0b8e2e00658d15cb2f636`
的 tree 与最终生产源码完整一致；源码网站检查也通过。

[CI 来源和收据](ci-source.json)记录官方 artifact ID、ZIP 摘要、完整覆盖清单和 tree 核对；
[CI 精简原件](ci-source-evidence.tar.xz)保留完整 summary、JUnit、CTest 输出、receipt 和
下载的 source job 日志。官方 4,814,125-byte 数值 ZIP 的 SHA256 为
`96ea8d026a2e19be3a4db589e646713a5b4acd6f314690a9c19d2d95f3fbe708`，已下载并重新核实。
手动 Debug/旧 PETSc job 的预期 skipped 不混作 Release 测试跳过。后续文档 head 的
数值证据复用与精确 head 合并以 PR 权威记录为准，不再算作新的 95 次执行。

## 6. 重现与归档

本地使用既有锁定依赖，未重建上游库。按仓库构建指南恢复同一环境后，在相应 source
checkout 执行相同驱动；绝对 wrapper/依赖路径需替换为自己的环境位置。

```bash
cmake --preset release -B build/cloud-3.23.7-release -DBUILD_TESTING=ON \
  -DEONSIM_PETSC_ROOT="$PETSC_DIR" -DCMAKE_PREFIX_PATH="$PETSC_DIR" \
  -DEONSIM_BLAS_LAPACK_PROVIDER=OPENBLAS -DEONSIM_VERIFY_LOCKED_RUNTIME=ON
cmake --build build/cloud-3.23.7-release --parallel 2 \
  --target eonsim verify_matrix_free verify_monolithic_fsi_mg verify_interface_patch verify_fsi_level_smoother
ctest --test-dir build/cloud-3.23.7-release -V \
  -R '^(matrix_free|monolithic_fsi_mg|interface_patch|fsi_level_smoother)_mpi[124]$'
python tests/verify_fsi_multigrid.py \
  --executable build/cloud-3.23.7-release/eonsim --mpiexec "$PETSC_DIR/bin/mpiexec" \
  --work build/reproduce-mg --build-source 3b5cbddb928dfa789dc1f3f424dba451f33107e6 \
  --modes mono mono_fp32 mono_pipe mono_mf mono_mf_pipe
python tests/verify_fsi_multigrid.py \
  --executable build/cloud-3.23.7-release/eonsim --mpiexec "$PETSC_DIR/bin/mpiexec" \
  --work build/reproduce-scaling --build-source 3b5cbddb928dfa789dc1f3f424dba451f33107e6 \
  --sections scaling coupling --modes mono mono_fp32
```

[本地原件包](local-evidence.tar.xz)含全部五批物理配置、网格、分区、输出、成功/失败日志、
receipt、定向 JUnit、构建日志和独立审计脚本/结果，共 3,045 个文件、53,310,247 原始字节。
没有打包第三方 PETSc 源码全文；故障推导保留标记源码链接。包大小 3,085,108 字节，SHA256：
`8d46a7d85be1b5784eb092e8f29fd2612cb132f693f70e181d858e3d309aa644`。
[逐文件清单](archive-manifest.json)的相对路径以 `build/cloud-3.23.7-release` 为根，已逐个
解包读取验证长度和 SHA256。原 receipt 中的绝对路径用于保留当时来源；离线换目录审计需
映射该前缀，不能修改原文件再宣称原 hash 未变。

没有本地全量 CTest、常规 Debug、旧 PETSc、多节点、百万自由度或长期生理实验验证。
源码 CI 按既有路径规则选择 95 项，不把这些边界描述成已经覆盖。
