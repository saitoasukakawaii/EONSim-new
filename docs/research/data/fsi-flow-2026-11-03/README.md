# FSI-NEXT-02 本地验收

2026-11-03；基线 `b2755b671ebffc4ad858d560214d4a7377eaf05e`，实现 `9bde79765ee57a2c42eb2964ac8297ec6246e3a7`，分支 `codex/fsi-next-02-periodic-flow`。本地代码审查与本节验收完成后创建唯一 [PR #33](https://github.com/saitoasukakawaii/EONSim-new/pull/33)；[数值CI](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424335) Debug/Release各29/29通过，零失败/零跳过；[网站/草稿隔离](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/41626424264)通过。 未合并，不自动合并。
20 小时是预算上限，不是实际运行时间或通过证据。未能检索到此前计划原文；本次具体验收条目见队列和 [能力说明](../../../development/FSI_PERIODIC_FLOW.md)。

## 环境和构建

Linux x86_64，当前配额 8 CPU / 8 GiB；构建脚本使用 4 jobs，MPI 每 rank 一线程，最多 2 rank。本次不作性能或扩展性结论。PETSc 3.23.7、OpenMPI、编译器和精确依赖/命令/退出码见 `debug-summary.json`、`release-summary.json`。

```bash
scripts/cloud/restore.sh 3.23.7 /workspace/scratch/b8438b07bb94/eonsim-cloud
# selection.json = {"tests":["fsi_flow","fsi_inlet","fsi_pressure_state"]}
scripts/cloud/run.sh 3.23.7 debug explicit /workspace/scratch/b8438b07bb94/eonsim-cloud selection.json
scripts/cloud/run.sh 3.23.7 release explicit /workspace/scratch/b8438b07bb94/eonsim-cloud selection.json
# 后续只复跑有修改/失败的 fsi_flow，不重复已通过的两项旧路径。
```

容器 root 额外设置 `OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 PRTE_ALLOW_RUN_AS_ROOT=1 PRTE_ALLOW_RUN_AS_ROOT_CONFIRM=1`。这只允许容器用户启动 MPI，不修改数值模型或容差。

Git CLI push 没有凭据。使用已授权 GitHub Git Data API 保存同一代码树；本地测试 receipt 的 `f378e92` 与远程实现提交不同但 tree **完全相同**：`991b394efc84f3e9c121cca346802ae38f5ce318`。详情和源文件 SHA256 见 `provenance.json`，不因提交元数据变化重跑数值检查。

## 必交结果

| 检查 | 结果/阈值 |
|---|---|
| BE/BDF2/generalized-alpha 终点及阶段目标流量 | 独立波形表达式误差 <1e-12，通过 |
| 刚性壁三分量无滑移、界面速度和位移一致 | 每个接受步 VTU 检查 <1e-12，通过 |
| 1/2 rank 与同分区重启 | 全部最终字段差 <2e-9，通过；恢复质量行亦对照 |
| 阶段表面通量 vs 体散度 | 独立积分相符 <1e-12；短算例质量残差最大 5.21e-18 |
| 正几何、结构非零响应 | 所有阶段/终点 J>0；排除只有给定位移的单向案例 |
| Neo-Hookean 整体 Jv | 最大相对差 1.03756e-7 <1e-6 |
| 真实拒绝/缩步重放 | 从 t=.008、dt=.004 起拒绝9次，接受 dt=7.8125e-6；与直接小步重放全字段差 <2e-9 |
| 非法周期、轴、矩形、互斥参数、越界 | 指定诊断拒绝，通过；不能只以非零退出当作测试成功 |
| 仅周边节点的零离散入口形状 | n=1 明确拒绝；n>=2 正确归一化 |
| 零 ramp | 初始非零入口和后续目标流量，通过 |
| 旧仿射入口/周期压力 | Debug/Release 各两项通过；没有重跑全量或 PETSc 3.19.6 |
| CI 选测映射 | `python tests/test_ci_selection.py` 26 项通过 |

最终增强版 `fsi_flow` 在 Debug/Release 各 1/1 通过，见各 `*-flow-ctest.log` 和 `*-metrics.json`。Debug 旧两项通过证据保留在 `failures/debug-mixed-ctest.log`（其中较早版新 flow 测试失败，不能把整个旧 run 标为通过）；Release 早期三项 run 成功见 `release-regression-driver.log`，最终新 flow 测试单独补验。小版本没有声明兼容验证。

## 六周期与分辨率研究

已在 Release、2 rank 执行：

```bash
python scripts/study_fsi_flow.py --executable build/cloud-3.23.7-release/eonsim \
  --mpiexec <prefix>/petsc-3.23.7/bin/mpiexec --work build/fsi-flow-study
# 后处理扩充梯形积分，仅分析已有 CSV，不重跑求解：
python scripts/study_fsi_flow.py --executable build/cloud-3.23.7-release/eonsim \
  --mpiexec <prefix>/petsc-3.23.7/bin/mpiexec --work build/fsi-flow-study --analyze-only
```

运行环境同编译脚本（`LD_LIBRARY_PATH=<prefix>/petsc-3.23.7/lib`、单线程、OpenMPI ob1/self,sm,tcp）。周期 .1，启动 .02，终点 .62；n 为每方向 subdivisions，流/固分别 6*n³ 个 Tet4。每个 case JSON、完整接受步 CSV 和求解日志分别保存，gzip 仅压缩存储；数值汇总 `study-summary.json`。

| n | dt | 步数 | 最大阶段质量残差 | 后两周期最大 stage/secant 差 | 梯形积分累计体积误差 |
|---:|---:|---:|---:|---:|---:|
| 2 | .002 | 310 | 5.20e-18 | 5.175e-5 | -4.972e-8 |
| 2 | .001 | 620 | 5.64e-18 | 2.623e-5 | -4.264e-9 |
| 2 | .0005 | 1240 | 5.64e-18 | 1.305e-5 | -6.247e-10 |
| 3 | .001 | 620 | 7.20e-17 | 2.640e-5 | -4.721e-9 |
| 4 | .001 | 620 | 3.08e-16 | 2.217e-5 | -4.529e-9 |

累计体积误差定义为 `sum(dt*(netQ_n+netQ_(n+1))/2)-(V_final-V_initial)`，初态流量0、体积1。另保留阶段矩形积分误差，不将后处理梯形积分冒充求解器的时间格式。阶段守恒达到舍入精度，有限步体积预算误差随时间加密下降。所有量采用实际当前几何及接受步长。

**局限：** n=2/3/4 最终面积平均壁位移约 .0004355/.0004500/.0004779，网格差尚不单调减小，不宣称空间渐近收敛或网格无关。最后相邻周期位移最大差为 0.94e-6 至 4.20e-6，六周期仍有剩余瞬态，不声称达到严格周期稳态。任务验证的是周期驱动、无滑移和全局质量预算，不是该合成通道的实验标定、高 Re 流动或充分发展解析解。全局守恒不等于逐单元局部强守恒。

## 错误、失败尝试与处置

1. 空执行环境缺 CMake/MPI/PETSc：仓库 `restore.sh` 成功恢复主锁；远程 EONSim 只读工作区工具返回 Internal error，没有依赖该连接执行。
2. 第一次 MPI 预检拒绝 root：显式使用上述 OpenMPI/PRRTE 容器选项后通过，原始第一次编译已成功。
3. 新增非法输入检查遇到 LLVM OpenMP `z_Linux_util.cpp(2125)` assertion/SIGABRT；顺序复跑仍在另一子进程复现，故不是“非法参数已正确拒绝”。原日志在 `failures/`。可见 `/dev/shm/__KMP_REGISTERED_LIB_<pid>_0` 在失败子进程结束后残留，命令执行环境会重复使用低 PID；这与 LLVM 注册流程碰撞路径相符，但未对锁定二进制做调试器回溯，底层断言的精确原因仍未证实。
4. 临时环境处置：不删除共享内存对象、不修改 LLVM/PETSc、不改变容差；在同一个长命令中先启动并回收 `/bin/true` 子进程，直到其 PID 大于已存在的注册文件 PID 最大值（上限20000，超出即停止），再顺序执行 Debug/Release 编译脚本。实际避开已存在注册名字后，两模式全部增强检查通过。此为本会话环境隔离办法，不是生产求解器修复；普通 CI 未预设需要该办法。
5. Git push 缺写凭据：改用已连接 GitHub API，核对树哈希完全一致后同步本地分支到远程提交；未改 main。

## 最终代码审查

本 agent 完成 diff 自审；未使用子代理，不声称独立外部审查。

- 对照当前主线：原仿射入口默认行为、签名和 CSV 字段保持不变；新参数严格互斥、有限性/周期/矩形检查在读取阶段。
- 归一化用相邻 owned 流体单元的真实外表面与全局标量规约；正方向固定，不依赖节点排列。
- 新诊断与求解时间层一致，拒绝前不提交；恢复从 accepted 位移重算旧体积。
- Jv/恢复/非法参数/几何与无滑移有实际检查；没有调松容差隐藏失败。
- 选测映射与新增测试匹配；研究脚本不进入默认性能矩阵；草稿不发布；长期架构契约未改变，无需改架构文档。

## PR 自动 CI 交付证据

`delivery-ci.json` 保存 PR head `a9d9093626a70db070527534fa2c39085682efb2`、合并预览 `10fb26733432f7c0a5a27d4fe31b5dfdcb6106ba`、job ID与实际计数。预览tree与本地head相同，都是 `9a9d31386b38c649092e720061a74f7785f95f57`。数值run `41626424335`、网站run `41626424264` 均成功，增量证据登记成功；旧3.19.6按策略skipped，不计入29项通过。

随后只补状态/证据文档，不改生产代码、测试、依赖、基线和选测规则；该提交复用同PR成功数值证据，不能写成重新运行29项。没有额外PR、main合并或知识稿发布。
