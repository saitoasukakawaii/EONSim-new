def analyze(solver,plan,receipts):
    directory=out/solver;directory.mkdir();dump(directory/'producer-receipts.json',receipts)
    left=study(solver,plan['coarse']);temporal=study(solver,plan['time']);fine=study(solver,plan['fine'])
    assert left.n==fine.n==800 and temporal.n==400
    assert [s.geometry['red_refinements'] for s in (left,temporal,fine)]==[0,1,1]
    assert all(s.steps//s.n==32 for s in (left,temporal,fine))
    assert all(s.audit['analysis_script_sha256']==EXPECTED_ANALYZER for s in (left,temporal,fine))
    reports={'space':fields.compare(left,fine),'time':fields.compare(temporal,fine),'tail':fields.compare(fine,fine,31,32)}
    for name,report in reports.items():dump(directory/(name+'.json'),report)
    sums={};maxima={};cache={};start=31*fine.n
    def frame(step):
        if step not in cache:cache[step]=fine.frame(step)
        return cache[step]
    for phase in range(1,fine.n+1):
        k=start+phase;lo=k-phase%2;hi=k+phase%2
        actual=frame(k);a=frame(lo);b=frame(hi)
        for i,(mesh,scales) in enumerate(zip(fine.meshes,fine.audit['scales'])):
            for name,scale in scales.items():
                u=np.array([actual[i][int(n)][name] for n in mesh.ids])
                v=.5*(np.array([a[i][int(n)][name] for n in mesh.ids])+np.array([b[i][int(n)][name] for n in mesh.ids]))
                error=mesh.squared(u-v)/mesh.volume/scale**2
                assert math.isfinite(error) and error>=0
                key=('solid_' if i else 'fluid_')+name;sums[key]=sums.get(key,0)+error/fine.n
                maxima[key]=max(maxima.get(key,0),math.sqrt(error))
        # At most the current neighbouring frames survive, not800 Python fields.
        for stale in list(cache):
            if stale<k:del cache[stale]
    sampling=dict(relative_rms={k:math.sqrt(v) for k,v in sums.items()},relative_maximum_phase_rms=maxima,
        dense_phases=800,reconstruction_phases=400,cycle=32,selected_cycle_periodic=fine.periodic_at(32),
        audit_prerequisites=fine.valid,input_files_sha256=fine.files,
        method='Linear reconstruction of actual every-other states, with the real cycle31 endpoint; norms on actual800 dense states')
    dump(directory/'sampling.json',sampling);reports['sampling']=sampling
    prerequisites={name:s.valid for name,s in [('coarse',left),('temporal',temporal),('fine',fine)]}
    eligible=all(all(values.values()) for values in prerequisites.values())
    keys=fields.audit_comparison.FIELD_NAMES;assert all(set(r['relative_rms'])==keys for r in reports.values())
    budgets={}
    for field in sorted(keys):
        denominator=reports['space']['relative_rms'][field];assert math.isfinite(denominator) and denominator>=0
        rows={}
        for name in ('time','tail','sampling'):
            numerator=reports[name]['relative_rms'][field]
            rows[name]=dict(relative_rms=numerator,ratio_to_space=numerator/denominator if denominator>0 else None,
                limit_fraction=.1,passed=denominator>0 and numerator<.1*denominator)
        budgets[field]=dict(space_relative_rms=denominator,terms=rows)
    passed=eligible and all(t['passed'] for f in budgets.values() for t in f['terms'].values())
    report=dict(solver=solver,prerequisites=prerequisites,eligible=eligible,field_budgets=budgets,passed=passed,
        scope='Independent S24 level1/N800 numerical error budget; does not establish remaining physical/cross-code/geometry/end gates')
    dump(directory/'budget.json',report);return report
