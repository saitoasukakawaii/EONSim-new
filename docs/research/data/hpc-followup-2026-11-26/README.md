# HPC-07：固定节点 Schur 刷新、FSI 场展开与输出校验

交付 [PR #57](https://github.com/saitoasukakawaii/EONSim-new/pull/57)，基线为已合并 #56 的
`55a04f73d2004970184f96ae6a3a1abc540d8076`。本次生产源码与首轮测试源码为
`4c7edc6cc14219acfc97d39b9651c935a1c875ac`，完整远端 tree
`030adfca09ef0edc889350b50dfde635f502670b` 与本地相同后才开始构建与验证。
最终故障日志解析驱动为 `8e6c0137205fd4eb288137e03296d116e920488d`，tree
`9c76144a30848db6a16d942f8402f6ff323247d8`；同样先远端核对，再做受影响复验。
两次解析提交只改测试，生产二进制和先前数值/性能证据保持有效。
后续证据/文档提交不代表重新执行数值检查，合并状态以 GitHub 为准。

## 实际改动

- `NodalSchur` 一次验证固定节点分组的 owner/覆盖，一次准备完整逆块的 COO 图，复用
  值缓冲和分组 offsets。每次数值刷新仍从当前矩阵提取并做原来的主元求逆与混合量纲
  均衡；全部 rank 通过有限性/非奇异性检查后，用 `INSERT_VALUES` 覆盖完整逆块，包括零。
  USER Schur 的 `D-C H B` 数学形式、符号乘积复用和矩阵身份不变。
- `-fsi_overlap true` 在 owned 阶段展开 owned/固定槽位，通信完成后只展开远端别名槽位；
  单次评价不再重复展开 owned 值。空单元阶段不进入 OpenMP 团队，halo 端口/刚体项仍处理。
- 独立 ASCII/HDF5 对照拒绝重复 cell ID、ID/tag/连接长度与形状不符、负数/越界/非整数
  连接、未消费的 mixed 流、缺失或重复域，以及错误的 XDMF 拓扑、属性与数据集绑定。
  比较同时包含 VTK 单元类型。生产 HDF5 writer 未改动。

没有新增运行开关，也未修改物理模型、Jacobian、时间积分或接受门槛。没有采用依赖
内部 CSR 位置的提取缓存：`MatGetValues` 每次读取当前数值，避免引入子矩阵存储假设。

## 来源和构建

保存的主线 ELF SHA256 为
`6efb5845aee29e3d7e3c47860ce35aac5c35950367f5ac9f6cef86f591754289`；与 #56 已归档构建相同，
`bce292a` 与基线 `55a04f7` 的生产源码、头文件和 CMake 内容一致。本次候选 ELF SHA256 为
`9bb74f0df3f44575d2ef5c99c85ed0572e6671f011d2289c169301606f3169c9`。
当前身份使用 `sync-before-validation.json`、`build.log`、`build-identity.json` 和
`baseline.json`；benchmark 自动复制的 `*-build_receipt.json` 仍是历史 `7e8868e` 的收据，
原件保留，不将其视为当前源码的构建证明。

环境为 PETSc 3.23.7、GCC 15.3.0、OpenMPI 5.0.8、Release，复用已有锁定依赖与构建目录。
主机报告 AMD EPYC 9V74，进程 affinity 为 9 个逻辑 CPU，内存约 9.7 GiB；cgroup
配额文件不可见，不推断独占核心。依赖 OMP/BLAS/MKL 每 rank 一线程，配对算例的 FSI
单元团队显式两线程。无本地全量、Debug 或旧 PETSc 验证。

```bash
bash build/locked.sh cmake --build build/cloud-3.23.7-release \
  --target eonsim verify_pc_plan --parallel 4
bash build/locked.sh ctest --test-dir build/cloud-3.23.7-release \
  -R '^(pc_plan_mpi[124]|fsi_coo_verification)$' \
  --output-on-failure -V -j 1 --output-junit build/hpc-followup/focused-junit.xml
bash build/locked.sh python tests/test_profile_validation.py -v
```

实际 **4/4 Release CTest、30/30 Python** 通过。预条件器检查覆盖 1/2/4 rank、空 owner、
节点逆非零→缩放→零非对角→恢复非零，以及混合块的非对称、约束、极端量纲、奇异/非有限
拒绝与恢复。原独立余子式/稠密 Schur oracle 和真实线性残差检查保留。
FSI CTest 使用 `--threads 2 --overlap`。37 次求解为 34 次正常成功、2 次预期 fatal 批次
退出和 1 次预期重试耗尽；另有 3 次不进入求解的 CLI 拒绝，单独计数。共 83 接受步，
20 次成功运行实际使用两线程 overlap。真实非线性回退经过 `.1→.05→.025→.0125`，
两次可恢复 worker/insert 注入各经历 `.008→.004`；两种方向的 AIJ/COO 端口重启均覆盖。
独立回放 24 组字段/历史对照，最大场差 `4.66127136888872e-13`、归一化历史差
`5.920877545347623e-14`，原 `2e-9` 门槛保持。

完整 FSI 原件复制 1,275 文件并逐文件核对。checkpoint 失败前后字节不变由原驱动成功
断言；归档只含最终 checkpoint，不把独立审计说成重建了未另存的失败前 manifest。
每次 MPI 启动命令的成功/预期失败返回状态由原驱动断言；未另存每次启动的数值返回码，
也没有逐 rank 退出码记录。

## 远程故障日志误报与定向复验

首轮源码 [CI 45768153788](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45768153788)
选中 43 项，实际 **42 passed / 1 failed / 0 skipped**。唯一失败是
`fsi_coo_verification` 未读到 `worker_fatal` 注入标记。下载并保留原始 artifact
`15093411877` 后，确认只有一个完整标记，前面拼接了另一个 rank 的 stderr 半行：

```text
EONSim rank fsi_batch_failure mode=worker_fatal thread=1 team=2 batch=1
```

真实注入来自 worker 1、team 2、batch 1，fatal 退出断言在解析前已经通过，且日志没有
接受步或重试。原始文件 SHA256 为
`afee44e61594ad87d379d3870a662510273364f1c2faca4bdcb4b079b6c15913`；不修改失败日志。
旧通用解析器只接受行首标记，独立回放仍得到 0 条。本次保留通用解析器，只对故障
记录容忍前缀，要求恰好一个标记、完整且唯一字段和行尾边界；重复/残缺标记、尾随
重复字段、错误 mode、单线程、错误 worker/master 与 batch 都拒绝。

初稿 `9066411` 同步后，独立审查发现尾随重复字段可能只匹配前缀；在任何本地复验前
补为 `8e6c013` 并再次同步。随后 **8/8 Python 回归、1/1 双线程 overlap FSI CTest**
通过，后者完整执行 37 次求解。没有重新编译生产二进制，也未重复不受影响的性能采样。
原第一次 FSI 原件与本次复验原件分开保存，见压缩包的 `fsi-focused/` 与
`parser-recheck/`，以及[解析复验收据](parser-recheck.json)与
[独立失败原件回放](parser-independent-replay.json)。复验归档 1,287 文件逐一匹配源哈希；
比首轮多出的 12 文件为四组新 checkpoint generation，旧 generation 仍保留。

```bash
bash build/locked.sh python tests/test_fsi_runner.py -v
bash build/locked.sh ctest --test-dir build/cloud-3.23.7-release \
  -R '^fsi_coo_verification$' --output-on-failure -V -j 1 \
  --output-junit /workspace/scratch/ae740e1dde63/EONSim-new/build/hpc-followup/parser-recheck/fsi-junit.xml
```

最终源码 [CI 45769962561](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45769962561)
在 `8e6c013` 上实际执行 **43/43 Release、0 failed、0 skipped、0 复用**，三组 Python
为 **8+6+30=44/44**。CI checkout 是 PR 合并预览 `2175136c5ef510b8c6b237864b652077f4972041`，
tree 与同步源码相同；Release 与增量验收收据两项均成功。
中间提交 `9066411` 的 [CI 45769825200](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45769825200)
也实际执行了 43/43 和 44/44；最终选测启动时前一收据尚未发布，因此按既有规则再次执行
43 项，不能记为复用。两组绿色 CI 的原件另存 [源码 CI 包](source-ci.tar.xz)，身份和
计数见 [源码 CI 收据](source-ci.json)。该包含 **1,698 文件 / 58,040,931 原始字节**，
[清单与摘要](source-ci-archive.json)、[逐文件清单](source-ci-archive-manifest.json)和
[完整性回放](source-ci-archive-integrity.json)均保留。后续文档 head 只继承不受影响的数值证据。

## 有界性能对照

同一生成双域 n8，3,072 个流体和 3,075 个固体 Tet4，消元后 5,367 DoF；五步
`dt=.02`、Young 模量 100、Poisson 比 .3、压力 1。两个二进制使用同一分区、默认 AIJ、
`hybrid + coupled velocity + nodal pressure Schur`，都开启 overlap 和两线程。

```bash
bash build/locked.sh python scripts/benchmark_fsi_assembly.py \
  --baseline build/hpc-followup/baseline/eonsim \
  --candidate build/cloud-3.23.7-release/eonsim \
  --baseline-commit 55a04f73d2004970184f96ae6a3a1abc540d8076 \
  --candidate-commit 4c7edc6cc14219acfc97d39b9651c935a1c875ac \
  --mpiexec .cloud/petsc-3.23.7/bin/mpiexec \
  --work build/hpc-followup/paired --subdivisions 8 --ranks 1 2 \
  --steps 5 --repeats 3 --solver hybrid --baseline-assembly-report --petsc-log \
  --baseline-options='-fsi_overlap true -fsi_threads 2' \
  --candidate-options='-fsi_overlap true -fsi_threads 2'
```

每档 rank 一组预热加三组交替配对，合计 **16 runs / 80 接受步 / 160 线性修正**。
所有运行通过原 `1e-12+1e-10*rhs_norm` 门槛，最大真实线性残差/门槛
**0.09338580138423479**；新旧二进制保存场量与历史最大差均为 **0**，迭代轨迹完全一致。
独立审计重读 96 个状态/288 VTU pieces、320 条字段接受记录，并完成 861 条 SHA/大小
断言；490,176 个 owned 和 16,608 个 ghost 字段向量参与检查。ghost/owner 差为 0，
1/2 rank 间最大场差 `6.5980554e-13`、历史差 `3.3439918e-13`。逐对统计重新计算后与
driver 汇总完全相同，见 [独立审计](independent-paired-audit.json)。

下表为逐对 `candidate/baseline-1` 后的中位数和范围，预热排除；负值表示耗时减少。

| 指标 | 1 rank | 2 ranks |
| --- | ---: | ---: |
| 整次 wall | −0.93% [−6.87%, +7.99%] | −6.42% [−7.08%, +14.38%] |
| 累计线性求解时间 | −1.37% [−8.65%, +11.45%] | −4.49% [−13.28%, −3.67%] |
| 累计装配时间 | +0.40% [−9.88%, +9.17%] | −0.43% [−3.79%, +2.23%] |
| 最大 rank 峰值 RSS | 0.00% [−0.37%, +0.41%] | +1.08% [−0.82%, +1.34%] |

单 rank 的 `FSIElementBatch` **58→29**，与消除空 halo 团队一致；两 rank 的最大计数
仍为 58，max/min 比由 1 变为 2。逆矩阵 COO 准备一次、数值发布十次，`MatZeroEntries`
分别 **28→19 / 58→49**。完整程序的 `MatAssemblyBegin/End` 分别为 **239→239 /
561→563**，没有减少，不把应用层逐节点插入消除说成 MPI 装配调用减少。
两 rank 的线性时间在三对中均下降，但 wall 范围跨零，不能宣称普遍
整程序加速。`schur_setup_seconds` 仅含 SNES 前 setup，不能代表所有后续 Schur 刷新。
各阶段是每步最大 rank 时间，可重叠且可能来自不同 rank，不能直接相加。

## HDF5 校验器的真实文件回放

加强后的校验器新执行 **14/14** 精确对照，覆盖 1/2-rank Poisson 与 FSI 的流体/固体和
时间快照，共 1,298 个点记录、2,226 个体/边界单元。70 份 VTU/XDMF/HDF5 输入均与
已提交 HPC-05 archive 哈希一致，回放后输入未改变。

复用的输出源为 `27889707a3c650d532c2845b2f6da7fc5d2324d4`；没有重新运行这些物理求解。
首个回放在锁定 Python 3.15.2 因缺 NumPy 退出，原日志保留；随后采用已安装的 primary
Python 3.12.14/NumPy 2.3.5，同时通过 `build/locked.sh` 使用原生锁定 `h5dump`，全部通过。
这次环境选择没有源码修改或依赖安装，不能记为数值错误或一次成功回放。

## 证据与边界

[压缩证据包](evidence.tar.xz) 包含 **4,291 文件 / 110,807,517 原始字节**；
[清单](archive-manifest.json)和[完整性收据](archive-integrity.json)确认全部成员的长度、
SHA256 与冻结时原件一致。压缩包 SHA256 为
`c36e478df9d8c18b9b3214123dd46393d3b38358b828d89a6a7ef64a463a3f70`。
原始构建、CTest、输入/分区/逐步输出、配对计时、HDF5 回放命令、首次远程失败及环境
尝试均保留；不重复归档基线可执行文件和已展开的 CI ZIP。后续绿色 CI 收据单独保存。
最终四项必需检查与合并状态依 GitHub 最新 head 核实，不将文档提交的复用记为重新运行。
本轮只优化上述已有路径，不把单机小网格证据外推为网格无关 AMG、多节点、百万 DoF、
GPU 或并行文件系统性能证明。[技术草稿](../../../../website/drafts/hpc-fixed-structure-refresh.md)
保持未发布。
