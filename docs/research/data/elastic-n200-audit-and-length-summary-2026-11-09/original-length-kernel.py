metrics={}
for field in ['mid_radial_displacement','mid_ring_projected_area','mid_pressure']:
    a=short['harmonics'][field];b=audit['harmonics'][field]
    metrics[field]=dict(L12=a,L24=b,mean_difference=b['mean']-a['mean'],
        amplitude_relative_difference=abs(b['amplitude']-a['amplitude'])/b['amplitude'],
        phase_difference_degrees=(b['phase_degrees']-a['phase_degrees']+180)%360-180)
lame=.02*geometry['infinite_plane_strain_inner_wall_compliance']
means={label:dict(relative_lame_mean_error=abs(a['harmonics']['mid_radial_displacement']['mean']-lame)/lame,
    periodic=a['periodic'],quality=all(v['passed'] for v in a['quality_gates'].values())) for label,a in [('L12',short),('L24',audit)]}
dump(out/'length-comparison.json',dict(harmonics=metrics,mean_checks=means,mean_limit=.02,
    mean_change_over_lame_scale=abs(audit['harmonics']['mid_radial_displacement']['mean']-short['harmonics']['mid_radial_displacement']['mean'])/lame,
    input_audits={str(p):sha(p) for p in [base/'eonsim-audit.json',out/'eonsim-audit.json']},
    scope='Dynamic finite-length sensitivity, including distributed fluid/solid response. Not a pure boundary error or cross-reference qualification.'))
