"""Prepare report tables only after the complete, restored study passes."""
import json
from pathlib import Path

root=Path.cwd();run=root/'build/resume-20261105'
work=Path('/home/tfblab633/EONSim-next03-20261105')
budget=json.loads((run/'fixed-budget.json').read_text())
relocation=json.loads((run/'relocation-audit.json').read_text())
continuations=json.loads((run/'continuation-history-audit.json').read_text())
assert budget['budget']['passed'] and relocation['complete_budget']['passed']
assert relocation['complete_budget']['numerical_results_exactly_equal']
assert len(relocation['archives'])==18 and len(continuations)==12
fields=[('fluid_velocity','流体速度'),('fluid_pressure','压力'),
        ('fluid_mesh_displacement','ALE位移'),('solid_velocity','固体速度'),
        ('solid_displacement','固体位移')]
rows=[]
for n in (2,4,8):
    for suffix in ('001','0005'):
        label=f'fixed-n{n}-dt{suffix}'
        receipt=json.loads((work/label/'periodic-result.json').read_text())
        tail=json.loads((work/('tail-'+label)/'transient-result.json').read_text())
        definition=json.loads((work/label/'study-definition.json').read_text())
        assert receipt['converged'] and receipt['metrics'][-1]['consecutive_passes']>=3
        rows.append(dict(n=n,dt=receipt['config']['fsi']['dt'],
                         cycles=receipt['metrics'][-1]['cycle'],
                         max_tail_contraction=max(v['contraction'] for v in tail['estimate'].values()),
                         ranks=definition['ranks']))
histories=[*budget['checks'].values(),*[c for values in continuations.values() for c in values]]
summary=dict(states=rows,phases=budget['phases'],
             periodic_accepted_rows=sum(c['accepted_rows'] for c in budget['checks'].values()),
             continuation_accepted_rows=sum(c['accepted_rows'] for v in continuations.values() for c in v),
             maximum_budget_ratios={name:max(values.values()) for name,values in budget['budget']['ratios'].items()},
             observed_spatial_orders=budget['observed_spatial_orders'],
             flow_balance={k:(min if k=='minimum_j' else max)(c['flow_balance'][k] for c in histories)
                           for k in histories[0]['flow_balance']},
             maximum_boundary_error=max(v for b in budget['dense_boundary_errors'].values() for v in b.values()),
             archives_verified=len(relocation['archives']),
             files_verified=sum(a['files_verified'] for a in relocation['archives']),
             exact_relocated_budget=True)
(run/'final-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=['## 实测结果（固定 τ=0.05）','',
       '六状态均达到完整场与标量连续三周期的1e-3判据，再各追加三个十周期区间和两周期100相位输出。',
       '以下阶段与采样采用独立真实求解；不是把20相位结果插值为100点。','',
       '| n | dt | 达标周期数 | 三块尾项最大实测收缩率 |',
       '|---:|---:|---:|---:|']
lines += [f"| {r['n']} | {r['dt']:g} | {r['cycles']} | {r['max_tail_contraction']:.6f} |" for r in rows]
lines += ['', '正式空间差采用100个真实相位；范数为参考体积归一化的lumped节点L2，再取相位RMS。各场保留本身量纲。',
          '压力出口给定零自然压力，比较原始压力，不做任意均值平移。', '',
          '| 场 | n=2→4差 | n=4→8差 | 观测阶 | 时间/空间差 | 瞬态/空间差 | 采样/空间差 |',
          '|---|---:|---:|---:|---:|---:|---:|']
for field,label in fields:
    ratios=[budget['budget']['ratios'][kind][field] for kind in ('temporal','transient','sampling')]
    lines.append(f"| {label} | {budget['difference_2_4'][field]:.9g} | {budget['difference_4_8'][field]:.9g} | "
                 f"{budget['observed_spatial_orders'][field]:.6f} | "+' | '.join(f'{v:.6%}' for v in ratios)+' |')
lines += ['', '三个预算分别严格小于10%。时间估计包含dt与dt/2差及两端状态的经验瞬态估计；',
          '对末档空间差涉及的n=4/8不确定量取和，并与n=2估计取最大值。',
          '采样项是50/100真实相位下所报告场差的变化；20相位波形重建误差另存原receipt，不冒充严格采样误差界。', '',
          f"全部周期状态共审计{summary['periodic_accepted_rows']}行接受历史，12组追加研究共{summary['continuation_accepted_rows']}行。",
          f"最大stage质量残差{summary['flow_balance']['stage_mass']:.9g}，表面/体散度差{summary['flow_balance']['surface_divergence']:.9g}，",
          f"入口流量误差{summary['flow_balance']['inlet_flow']:.9g}，最小几何Jacobian比{summary['flow_balance']['minimum_j']:.9g}。",
          f"100相位无滑移/界面相容最大误差{summary['maximum_boundary_error']:.9g}。", '',
          f"18个归档迁移后逐一核对{summary['files_verified']}个文件；尾项实际场和完整预算重算与原结果一致，原receipt未改写。", '',
          '![周期达标轨迹](figures/periodic-convergence.png)', '',
          '![分场误差预算](figures/error-budget.png)', '',
          '![压力及壁位移响应](figures/periodic-responses.png)', '']
(run/'result-tables.md').write_text('\n'.join(lines))
print(json.dumps(summary),flush=True)
