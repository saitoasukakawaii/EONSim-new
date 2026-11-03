# FSI-NEXT-03 环境中断恢复点

原工作目录 /workspace/scratch/b8438b07bb94/EONSim-new，分支 codex/fsi-next-03-periodic-convergence，main基线4f3a995。2026-11-03环境unavailable；不要报告后台仍在运行。本记录来自已返回的工具输出，不替代尚未上传的原始证据。

## 恢复动作

1. 核对最新main/分支，保留本地未提交内容；不得hard reset。远端20ac3af保有全部此前源码、时间精度矩阵和默认三网格可恢复归档。本提交保存断开前两项Python修改；如本地相同则合并文档即可，切勿改动正在运行研究的冻结源码指纹。
2. 检查所有MPI进程和build/fsi-next-03/release-worker.log；只有一个MPI队列允许运行。原worker会话70319，最后任务010是默认n4半步长，第28周期。旧worker91757已退出，不重启。
3. release-queue/011..018已写取消结果：默认n2半步长污染明确超标，无须为已拒绝候选继续昂贵完整矩阵。010a固定n2 dt=.0005；010b重放旧固定n2；019仓库编译脚本串行补验失败4项；020/021固定n4/n8 dt=.001；022/023对应dt=.0005；024..035六状态各三块10周期尾项和100相位采样；036固定策略完整10%预算。检查队列内容后续跑，不能因已有文件就假定成功。
4. 默认n2 dt=.0005已136周期converged；其目录space-auto-n2-dt0005。保留而不改写旧receipt。固定粗网格基线full-n2在77周期converged，旧构建需010b完整周期兼容重放。其本轮独立历史审计7700行通过。
5. 后续所有MPI进程使用唯一TMPDIR、OMP_NUM_THREADS=1、OPENBLAS_NUM_THREADS=1、MKL_NUM_THREADS=1及run-isolated.py PID隔离。若构建丢失，仅用scripts/cloud/run.sh恢复PETSc3.23.7 Debug/Release，不直接替换活动研究的可执行文件。恢复/失败重试必须保留failed-attempt原件；只有定义/完整历史相容才--resume。
6. 固定策略预算若失败，依据实际结果继续加密，不放宽周期1e-3、污染10%、质量和无滑移阈值。固定tau研究不能宣称默认稳定化或连续模型空间收敛已证实。
7. 收齐验收证据、最终自审、4项回归补验、文档/草稿后才创建唯一汇总PR；同PR处理自动CI，不合并main。

## 已观察到但需从原工作区回收的证据

- docs/research/data/fsi-next-03/failures/duplicate-worker-release：完整重复任务失败日志；4失败为fsi_periodic、fsi_flow、fsi_inlet、fsi_pressure_state，3通过为fsi_diagnostics、fsi_diagnostics_mpi、elastic_fsi_verification。最后可执行SHA b4de28ffc6481701b533ec4772f4f0f604cfc18bc15bc63c858ebebae38352da未变。
- latest-periodic-debug-final、space-checkpoint/n4-replay.json、space-checkpoint/space-100-phases.json已本地复制成功，未上传。n4重放所有场差0。
- failures/automatic-time-contamination及四记录写入命令在会话93104断开，完成状态未知；不得假定落盘。
- baseline sampling-n2/n4/n8和tail-n2/n4/n8完成，后两尾项/密集场未完整归档。默认半步长及新固定研究原始文件未上传。
- 空间100相位末档差：流速0.001745799121672042、压力0.03898703699680914、ALE位移0.00008770872288936991、固速0.0029171097442762008、固位移0.00022307758614858206。50/100相位相对变化分别4.9937e-8、2.0051e-6、3.2448e-8、1.3159e-7、1.2471e-7。不是整体预算通过。
- 默认n2时间20相位差：流速0.0007516501826300894、压力0.08907798954519439、ALE位移0.00000833566896659876、固速0.0011993333986404404、固位移0.000020821606650388855。这是拒绝候选的初筛，不是完整密集误差审计。

## 剩余验收

固定算子三网格和半步长完整周期、三块尾项衰减、100相位采样、逐字段严格10%误差预算；4项Release串行补验；全部原始证据SHA归档和图表；最终代码审查、四项记录和草稿收敛；最后才PR和CI。48小时预算未声称耗尽。若原环境不可恢复，缺失原始证据必须真实重算，不能由本记录重建或伪造。
