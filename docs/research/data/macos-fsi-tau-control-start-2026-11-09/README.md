# FSI N800 tau时间项对照已启动

源码提交c3215a2；独立诊断binary SHA与输入绑定见definition.json，准备/启动/控制脚本与日志保留。原生产binary未改。

rho_infinity=0.5的一阶流体alpha_m=5/6、alpha_f=2/3、gamma=2/3，因此N400有效时间为(8/15)*(2*pi/400)=0.008377580409572784。此值仅进入tau时间项；实际N800步长2*pi/800、32周期、16周期加载、相同细网格和材料均保持。固定值也作用于首个BE步，不能声称启动tau与默认N400完全相同。

实际执行：

```sh
build/analysis-venv/bin/python build/recompute-20261109/prepare-fsi-tau-control.py
build/analysis-venv/bin/python build/recompute-20261109/run-elastic-tau-control.py --work build/recompute-20261109/elastic-s24-l1-n800-tautime-n400 --level 1 --n 800
```

99794启动检查退出0，8步完整且所有端点J为正；最大压力约4.42e-11，明确只证明近零加载启动，不作为加载后资格。60952长程handle启动后再次轮询仍live。20GiB磁盘底线、3GiB RSS、每阶段24h保护；启动前free>40GiB，后续多个任务共同增长须继续管理存储。所有步从零计算，仅早期输出稀疏；最后三周期保存每步场，收集使用真实restart命名。

目标是与默认细N400/N800实际场分解对比，尚未有长程结果。该对照不能替代默认时间误差预算，不改变原10%门槛。参考细网格、长度/几何控制与Womersley任务继续，未push/PR。
