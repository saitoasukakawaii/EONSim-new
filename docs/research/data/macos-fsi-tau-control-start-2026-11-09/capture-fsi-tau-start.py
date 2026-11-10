from pathlib import Path
import shutil,json,hashlib,re
r=Path.cwd();b=r/'build/recompute-20261109';out=r/'docs/research/data/macos-fsi-tau-control-start-2026-11-09';out.mkdir()
for name in ['prepare-fsi-tau-control.py','run-elastic-tau-control.py','capture-fsi-tau-start.py']:shutil.copy2(b/name,out/name)
for src,dst in [('elastic-tau-time-preparation/preparation.json','preparation.json'),('elastic-tau-time-preparation/case.json','case.json'),('elastic-tau-time-preparation/probe/solve.log','startup.log'),('elastic-s24-l1-n800-tautime-n400/definition.json','definition.json'),('elastic-s24-l1-n800-tautime-n400/live.json','live-at-start.json')]:shutil.copy2(b/src,out/dst)
rows=[dict(x.split('=',1) for x in line.split()) for line in (out/'startup.log').read_text().splitlines() if line.startswith('fsi_step=')]
assert len(rows)==8
j=min(float(v[k]) for v in rows for k in ['endpoint_min_fluid_j','endpoint_min_solid_j']);assert j>0
record=dict(startup_min_j=j,startup_max_pressure=max(float(v['applied_pressure']) for v in rows),scope='Near-zero-load startup only, no loaded acceptance claim.',files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir())})
(out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
(out/'README.md').write_text('''# FSI N800 tau时间项对照已启动

源码提交c3215a2；独立诊断binary SHA与输入绑定见definition.json，准备/启动/控制脚本与日志保留。原生产binary未改。

rho_infinity=0.5的一阶流体alpha_m=5/6、alpha_f=2/3、gamma=2/3，因此N400有效时间为(8/15)*(2*pi/400)=0.008377580409572784。此值仅进入tau时间项；实际N800步长2*pi/800、32周期、16周期加载、相同细网格和材料均保持。固定值也作用于首个BE步，不能声称启动tau与默认N400完全相同。

实际执行：

```sh
build/analysis-venv/bin/python build/recompute-20261109/prepare-fsi-tau-control.py
build/analysis-venv/bin/python build/recompute-20261109/run-elastic-tau-control.py --work build/recompute-20261109/elastic-s24-l1-n800-tautime-n400 --level 1 --n 800
```

99794启动检查退出0，8步完整且所有端点J为正；最大压力约4.42e-11，明确只证明近零加载启动，不作为加载后资格。60952长程handle启动后再次轮询仍live。20GiB磁盘底线、3GiB RSS、每阶段24h保护；启动前free>40GiB，后续多个任务共同增长须继续管理存储。所有步从零计算，仅早期输出稀疏；最后三周期保存每步场，收集使用真实restart命名。

目标是与默认细N400/N800实际场分解对比，尚未有长程结果。该对照不能替代默认时间误差预算，不改变原10%门槛。参考细网格、长度/几何控制与Womersley任务继续，未push/PR。
''')
entry='''\n## 2026-11-09：FSI N800稳定化时间对照从零启动\n\n[启动记录](../research/data/macos-fsi-tau-control-start-2026-11-09/README.md)：c3215a2诊断binary完成真实细网格8步近零加载检查（99794退出0），60952从零推进32周期。仅tau时间项固定为N400 generalized-alpha流体有效时间0.008377580409572784，实际N800步长与16周期加载保持；初始BE也使用此值，启动差异明确保留。启动后handle再次确认live；20GiB磁盘保护不变，存储需持续管理。尚无完整物理/预算结论，原默认失败仍保留，未push/PR。\n'''
for name in ['CODEX_PROGRESS.md','CODEX_TASK_QUEUE.md','CODEX_SESSION_LOG.md']:
 p=r/'docs/development'/name;s=p.read_text();i=s.find('\n');p.write_text(s[:i+1]+entry+s[i+1:])
p=r/'docs/research/KNOWLEDGE_LOG.md';s=p.read_text();i=s.find('\n');p.write_text(s[:i+1]+'\n## 2026-11-09：FSI tau控制启动\n\n[证据](data/macos-fsi-tau-control-start-2026-11-09/README.md)补充[诊断草稿](../../website/drafts/fsi-stabilization-time-control.md)：有效时间系数8/15及初始BE干预范围已记录，长程结果尚未产生，不新增重复文章。\n'+s[i+1:])
