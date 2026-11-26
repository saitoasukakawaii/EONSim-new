# FSI-MF-02：直接固体方向核与零初值 MG 的证据

交付 [PR #62](https://github.com/saitoasukakawaii/EONSim-new/pull/62)，基线
`main@6bb6f438b63c4a375cb143532640532cbb47921d`（#61）。生产/测试源码
`b7d727bd10231c22987b18114d1e25d622b2b8f1`，完整tree
`f62deb159dcadde5a48aca8a7af4063bc4628204`。远端tree先核对相等，再构建与验证。
本次文档和原件归档提交不记作新的数值执行。

[机器可读汇总](summary.json)、[独立原件审计](audit.json)、[来源](provenance.json)、
[文件清单](manifest.json)、[完整原件压缩包](raw-evidence.tar.xz)、
[未发布草稿](../../../../website/drafts/fsi-direct-solid-action.md)。

## 实现范围

直接计算固体δF→δP→节点力及一致质量；固定参考面壁支撑直接作用。matrix-free不再
为一个方向形成9×9材料或12×12单元切线。原装配残量/切线保持独立，非正NH构形继续
可恢复拒绝、非有限F继续fatal；零方向不能跳过这些检查。静力与动态、惯性有效步长
和位移链系数保持原模型含义。

MG每个非粗层已知x=0时直接构造r=b，省一次层残量matvec及相应halo；默认每层3→2。
此计数不含平滑器内部作用、传递或粗解，不能解释为全部MG成本减少三分之一。
预平滑关闭、多次预平滑、无后平滑、FP32、空owner、数值刷新、谱重建均有检查。

## 实际验证与命令

工作目录为仓库根。使用原锁定环境PETSc3.23.7、Release、编译并行2、各rank单OMP/BLAS线程。
原执行环境wrapper、编译命令和日志均在压缩包的`fsi-mf-02/`内；依赖目录按本机位置替换。

```bash
mkdir -p build
tar -xJf docs/research/data/fsi-mf-02-2026-11-26/raw-evidence.tar.xz -C build
# 按本机依赖位置调整解包后的run-env.sh，再执行以下命令。
bash build/fsi-mf-02/run-env.sh cmake --build build/cloud-3.23.7-release \
  --target eonsim verify_solid_element verify_monolithic_fsi_mg --parallel 2
bash build/fsi-mf-02/run-env.sh ctest --test-dir build/cloud-3.23.7-release \
  -R '^(solid_element_jacobian|monolithic_fsi_mg_mpi(1|2|4))$' --output-on-failure -V
# 两个真实算例campaign的其余精确参数见results.json的commands。
bash build/fsi-mf-02/run-env.sh bash <<'SH'
python tests/verify_fsi_multigrid.py --executable build/cloud-3.23.7-release/eonsim \
  --mpiexec "$PETSC_DIR/bin/mpiexec" --work build/fsi-mf-02/physical-default \
  --build-source b7d727bd10231c22987b18114d1e25d622b2b8f1 \
  --sections default --modes mono mono_fp32 mono_mf
python tests/verify_fsi_multigrid.py --executable build/cloud-3.23.7-release/eonsim \
  --mpiexec "$PETSC_DIR/bin/mpiexec" --work build/fsi-mf-02/physical-moving \
  --build-source b7d727bd10231c22987b18114d1e25d622b2b8f1 \
  --sections moving --modes mono_mf mono_mf_pipe
SH
bash build/fsi-mf-02/run-env.sh build/cloud-3.23.7-release/verify_solid_element --benchmark-actions
```

| 证据 | 实际结果 |
| --- | --- |
| 固体方向核+MG MPI1/2/4 | 4/4 CTest通过，0数值失败/跳过；JUnit与原log一致 |
| 固体双参考 | 14组，对完整切线最大归一化差3.3998581e-16；残量FD最大4.1289323e-9 < 2e-8 |
| 支撑双参考 | 12组，对完整切线差1.4946835e-16；残量FD最大2.1770198e-11 < 2e-9 |
| 受影响真实FSI | 11/11 run，33接受步，75条真残量，1/2rank |
| 固定输入成本测量 | 9/9 run：1直接参考、2未计时warmup、3对旧/新；27步、81真残量 |

两个campaign没有改物理或数值门槛：保存场/历史差限2e-9，原算子真实线性残量限
`1e-12 + 1e-10*rhs_norm`。带支撑的350DoF移动NH血管采用GA(rho∞=.5)、
dt=.015/.013/.017、RCR、FGMRES/PIPEFGMRES。默认双域还检查FP64/FP32和1/2rank。

独立标准库重读全部log/CSV/VTU和哈希，不调用原driver的audit函数，也不重跑求解。
合计20run/60步/156条真残量；其中候选源码16run/48步/120条，旧二进制4run/12步/36条。
576份VTU含所有步、终点及边界，444,592浮点值、391,872整数拓扑/身份值；947原件hash
全部吻合。最大字段差3.1985525e-13、主history差7.9936058e-15、pressure-face差7.8131945e-15，
owner/ghost差0，真残量/原门槛最大0.0090438864，RCR缺陷最大4.0766002e-17。
这些是实测日志残量标量的独立核查；没有保存J/b/dx，不声称离线再次计算Jdx−b。

## 成本与环境

环境为Linux共享单机、AMD EPYC9V74、affinity9CPU、GNU15.3.0、OpenMPI5.0.8、PETSc3.23.7，
FP64/32位PetscInt；只证明最多4rank正确性，不能证明多节点扩展。
基线exe SHA256 `e36709e019aa2312e4f5da3145a0c1ac59650d3086841554f228f5a91584e83e`
与#61归档一致；新exe SHA256
`23b386741ba1cf7efb5cfa0bc9b65569f6dc06a8d255323ab3608a71186f1549`。

局部核线性/NH×有/无支撑，每配置7对、每条路径每对20,000次，变化状态、交替次序、
核对checksum，配对耗时降低中位75.75%–82.08%。原路径包括原来实际执行的切线生成和
矩阵乘，新路径直接作用；没有把无效结果或更松容差当作加速。

同输入350DoF、2rank的3对测量均155次外层迭代、173次MF作用，P复用次数也相等：

| 指标 | 新/旧比值中位 | 三对范围 |
| --- | ---: | ---: |
| matrix-free作用阶段rank0耗时 | 0.76733 | 0.67741–0.77602 |
| 线性阶段耗时 | 0.96854 | 0.89307–1.02320 |
| 求解阶段耗时 | 0.99456 | 0.88733–1.07701 |
| 整程序wall | 1.01437 | 0.91315–1.06991 |

阶段数值由原solver_report重新求和；wall来自进程计时收据，其比值可复算，但不能从
solver文本独立恢复外部秒数。局部收益成立，整程序wall没有稳定收益；完整P仍存储，
没有宣称总内存下降、近似网格无关或大规模生产就绪。不继续追加无边界采样。

## 远端检查与边界

源码CI [45832884735](https://github.com/saitoasukakawaii/EONSim-new/actions/runs/45832884735)
实际 **42/42 Release、6/6 Python** 通过，0数值失败/跳过/复用；采用原PR受影响选测。
[选测清单](ci-plan.json)、[成功收据](ci-receipt.json)、[实际结果](ci-validation.json)与
[官方artifact信息](ci-artifacts.json)直接来自GitHub日志/API。merge-preview 7eb6830与
生产b7d727b的完整tree一致；job原日志也放在压缩包中。PR#62已于北京时间21:57合入
`194c96eda208ae49de1b0a65e5a36d60acca76b6`，四项必需检查成功，无保护绕过。
原件归档使用基于该main的纯文档PR，不运行新数值检查；引用既有证据不算新的数值执行。
本地没有全量、常规Debug、旧PETSc或多节点追加验证。未受影响的通用MF会话/流水线
错误恢复复用#61的3b5cbdd证据，本次未重跑；本次新固体接线由真实FSI而非人工小矩阵证明。
