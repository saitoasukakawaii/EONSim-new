# HPC-06：自适应 PC 重建重试保留总求解预算

交付 [PR #56](https://github.com/saitoasukakawaii/EONSim-new/pull/56)，从已合并 #55 的
`2d0e9b79e90ac0b7332b22e900e50e3306a68a35` 接续。生产源码与新增回归测试均为
`bce292a1870c38686e44514e2879009ebb9a736a`；远端 tree 与本地完整 tree 一致后才开始
构建/验证，见 [同步收据](sync-before-validation.json)。后续证据/文档提交不是新数值执行。

## 缺陷、修复与负对照

旧 PC 若在已经接受 Newton 更新后耗尽 KSP 次数，第二次 SNESSolve 会重置内部计数，
仍取得原来的完整上限。原有线性回归在第一轮修正失败，消耗的 Newton 步为零，未检出
这一求解级预算漏洞。它不是错误物理场已被接受的证据；最终物理验收一直保留。

修复从 SNESGetTolerances 读取实际设置（含命令行覆盖），第二次求解只取得剩余 Newton
与 PETSc 计数的函数评价额度，负的无限函数上限保持。重试退出后恢复原设置，保留会话
不会把减少的预算传到下一时间步。只重试原先合资格的一次旧 PC/KSP 耗尽。

为证明测试识别原缺陷，重新编译固定旧 main 的 nonlinear_system.cpp，以相同 Release
编译参数替换保留 core archive 中的该对象，再链接新回归测试。**1 rank 退出 1**，且
准确命中 `Fresh-PC retry reset the caller's total Newton iteration budget`，见
[负对照收据](negative-control.json)。这是预期失败，不计作成功求解。编译、链接命令及
原日志均在证据包内；ELF 不入包，以 SHA256 固定身份。

## 本次实际执行的验证

环境：PETSc 3.23.7、GCC 15.3.0、OpenMPI 5.0.8，应用 Release；OMP/OpenBLAS/MKL
每 rank 一线程。复用现有 build/cloud-3.23.7-release，未重新恢复依赖或运行全量。

```bash
bash build/locked.sh cmake --build build/cloud-3.23.7-release \
  --target eonsim verify_adaptive_pc verify_nonlinear_acceptance --parallel 4
bash build/locked.sh ctest --test-dir build/cloud-3.23.7-release -N \
  -R '^(adaptive_pc_mpi[124]|nonlinear_acceptance(_mpi)?)$'
bash build/locked.sh ctest --test-dir build/cloud-3.23.7-release \
  -R '^(adaptive_pc_mpi[124]|nonlinear_acceptance(_mpi)?)$' \
  --output-on-failure -V -j 1 \
  --output-junit build/adaptive-retry-budget/junit.xml
```

实际 **5/5**：adaptive_pc_mpi1/2/4 与 nonlinear_acceptance、nonlinear_acceptance_mpi。
新回归在第一步已接受后实际触发 KSP 迭代耗尽，验证 Newton 总上限4拒绝、上限5成功，
函数评价上限4拒绝、PETSc选项覆盖配置，以及下一物理context复用同会话时恢复原预算。
4 rank 含一个空 owner。构建/inventory/CTest 均退出0，无跳过；[构建及执行收据](focused-receipt.json)。

```bash
bash build/locked.sh python tests/verify_fsi_block_efficiency.py \
  --executable build/cloud-3.23.7-release/eonsim \
  --mpiexec .cloud/petsc-3.23.7/bin/mpiexec \
  --work build/adaptive-retry-budget/fsi-quick --stage quick \
  --grids coarse fine --modes aggregate_rigid aggregate_rigid_adaptive \
  --outer-rtol 1e-11
```

驱动自动加入直接解。coarse/fine分别为1/2 rank、1,027/3,024消元后DoF，各模式四步，
合计 **6/6 runs、24接受步、48次显式线性修正**。原真残差门槛
`max(1e-23, 1e-10*rhs_norm)`（原margin1.00001）与五场门槛2e-6保持；共同outer rtol
沿用上一轮的1e-11。

| 指标 | 本次实测/独立复核 |
| --- | ---: |
| 最大显式线性残差 / 原门槛 | 0.7453555129217156 |
| 五场最大归一化峰值差 | 4.682969483404888e-13 |
| 独立哈希断言 | 22/22 |
| coarse adaptive实际刷新 / 复用 | 7 / 1 |
| fine adaptive实际刷新 / 复用 | 8 / 0 |
| 动脉自然触发的重建重试 | 0 |

独立审计重读原日志的RMS/方程数并重构真残差，按owner与mesh_node_id读取VTU五场后
与直接解重新比较；与驱动汇总精确一致，见[审计结果](independent-audit.json)。预算缺陷
由定向非线性问题触发；这六条动脉轨迹证明实际物理路径无回归，不能混称其自然触发了重试。
本轮没有预热/重复性能样本，不作新的加速结论。

候选eonsim SHA256为 `6efb5845aee29e3d7e3c47860ce35aac5c35950367f5ac9f6cef86f591754289`。
原始驱动记录source_dirty=false；独立核对生产源、测试、驱动与bce292a一致。

## CI、证据和适用范围

[源码Core run 45757133771](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45757133771)
实际 **17/17 Release，0 failed、0 skipped、0复用**；merge checkout为063c7e9c，Git tree
与bce292a一致。[源码网站检查](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45757133658)
成功，但本源码提交没有网站改动，不把成功门禁描述成新增网站构建。
[CI选测、执行摘要及逐项来源](source-ci.json)保留本轮执行身份。最终文档head按原规则
复用这些通过结果；合并状态以PR#56的GitHub记录为准，不跳过四项必需检查。

[evidence.tar.xz](evidence.tar.xz)包含原始构建/CTest/负对照日志、JUnit、环境包装脚本、
源与二进制身份、全部六次FSI输入/分区/输出及只读独立审计脚本。
[archive.json](archive.json)记录归档和每个成员的SHA256/大小；解压后根目录为
adaptive-retry-budget。复现须重映射历史工作区路径并使用独立输出目录。

编排失败如实保留：环境包装脚本没有可执行位，使用bash调用；负对照首次引用不存在的
bin/ar，随后用配置的gcc-ar处理已成功编译的对象。两者未执行失败数值算例，也未更改
数学代码或通过门槛。

其余四项及AMG算法复用[HPC-05历史证据](../hpc-five-track-2026-11-26/README.md)，本次未
重跑。没有全量、Debug、旧PETSc、多节点、百万DoF或并行文件系统新验证；五项优化此前
记录的性能和规模限制继续有效。[知识草稿](../../../../website/drafts/adaptive-pc-retry-budgets.md)保持未发布。
