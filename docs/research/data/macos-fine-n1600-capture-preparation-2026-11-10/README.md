# 精细 N1600 最终证据入口准备

基线9c9b7f7。由既有N800 capture适配20个分段的51200接受步、末4800审计相位；核对原输入与二进制SHA、各段receipt/连续日志、两域4829个PVD条目和真实文件，物理门槛按实际结果记录，失败不改为成功。无新的数值公式或求解器更改。

脚本通过语法编译；实际运行 `build/analysis-venv/bin/python build/recompute-20261109/capture-elastic-fine-n1600.py` 返回预期退出1：缺少最终completion/audit，明确Incomplete且最终证据目录未创建。仅完成不完整输入拒绝检查；完整终态路径尚未执行，不能称为通过。

34110终态成功后，先执行 `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case build/recompute-20261109/elastic-s24-l1-n1600/case.json --work build/recompute-20261109/elastic-s24-l1-n1600 --first-step 46401 --output build/recompute-20261109/elastic-s24-l1-n1600-audit.json`，再运行本capture及原N1600预算。预算所需N800体场需按当前归档收据恢复，不得略过。若此后回收本研究原始场，则必须先适配capture清单为archive-aware或恢复全部输入，不能静默缩减清单。当前未回收该研究场文件，仅透明压缩。

主计算与参考及监测继续，无push/PR。复用现有证据方法，无新文章。
