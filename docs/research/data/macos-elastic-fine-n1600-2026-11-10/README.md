# Fresh elastic fine N1600 physical audit

All51200steps/32cycles from zero,16-cycle ramp. All20segmented phases completed0; every accepted step and all4829PVD phases per domain independently checked against logs, receipts, actual paths and original input/binary hashes. No numerical rerun. Full last4800frames plus preceding46400endpoint audited. summary.json records actual passed/failed physical gates without changing any threshold. Full audit compressed and decoded readback exact, complete raw manifest retained.

Audit command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 build/analysis-venv/bin/python scripts/audit_pressure_tube.py --case build/recompute-20261109/elastic-s24-l1-n1600/case.json --work build/recompute-20261109/elastic-s24-l1-n1600 --first-step 46401 --output build/recompute-20261109/elastic-s24-l1-n1600-audit.json`. All physical checks passing would still not establish independent budgets or final production qualification.

## 2026-11-10：精细N1600完整物理审计通过，独立预算启动

[证据](../research/data/macos-elastic-fine-n1600-2026-11-10/README.md)：94137审计退出0，56006完整capture退出0。51200步、末4800相位全部核验；周期差最大2.4428281e-7，界面运动学5.4210e-20、质量9.7578e-18、散度9.8484e-18，Jsolid最低0.9999772/Jfluid最低1.0000041，Lamé误差1.2375858%<2%，本地物理检查全部通过。原始清单19672成员，含五组边界归档完整重新解码核验；审计SHA5437bea4958c35c4a9ad4a1dd21b2fd60d444a6b5d330b724bdc2799765fd2b7。65569已运行analyze-elastic-n1600-budget-streaming.py，原1600/800相位与10%门槛不变，完整预算尚无结论；不得将物理通过当作生产资格。参考38893及其余待办继续，无push/PR。

完整预算命令：OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/analyze-elastic-n1600-budget-streaming.py --solver eonsim --output build/recompute-20261109/elastic-n1600-budgets-streaming。尚未结束；后续必须核对完整结果及恢复覆盖，不能根据启动/退出状态推断数值门槛。
