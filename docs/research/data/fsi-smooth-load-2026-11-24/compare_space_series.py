"""Compare directly coincident physical cross sections in 3D FSI and axisymmetric Radau runs."""
import argparse
import csv
import hashlib
import json
import lzma
import math
from pathlib import Path
import re


GROUPS=('spatial','extra-space','controls','symmetric','symmetric-tight','time-tail','time-tight','current-time','reference-div','vertex-order','regular-metric','mesh-increment')
VARIANTS={'native':'svfsi-observer-build','grad-div-off':'svfsi-no-grad-div-build',
          'current-equations':'sv-current-native-build','current-equations-grad-div-off':'sv-current-zero-build',
          'current-equations-grad-div-time-1over128':'sv-reference-div-build',
          'current-equations-regular-simplex':'sv-regular-metric-build',
          'current-equations-relative-mesh-stage':'sv-mesh-increment-build'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pack(directory):
    hashes={digest(directory/d/'bin/svFSI'):label for label,d in VARIANTS.items() if (directory/d/'bin/svFSI').is_file()}
    records=[]
    for group in GROUPS:
        for p in sorted((directory/group).glob('*/results.json')):
            row=json.loads(p.read_text())
            eon=json.loads((p.parent/'eon/case.json').read_text())
            deck=(p.parent/'matched/svFSI.inp').read_text()
            for domain,name in enumerate(('fluid.msh','solid.msh')):
                if digest(p.parent/'reference'/name)!=row['mesh_sha256'][domain]:
                    raise ValueError(f'Mesh hash changed in {p}')
            abss=[float(v) for v in re.findall(r'^\s*Absolute tolerance:\s*(\S+)\s*$',deck,re.M)]
            if len(abss)!=2 or len(set(abss))!=1:
                raise ValueError('Expected equal FS and MS linear absolute tolerances')
            rec=dict(group=group,case=p.parent.name,sv_variant=hashes[row['source_executables']['svfsi']],
                     eon_case_sha256=digest(p.parent/'eon/case.json'),sv_deck_sha256=digest(p.parent/'matched/svFSI.inp'),
                     linear_atol=abss[0],peak_pressure=eon['fsi']['pressure'],report=row)
            records.append(rec)
    return records


def continuum(reference):
    d=json.loads(reference.read_text())
    selected=max(d['runs'],key=lambda run:run['steps'])
    if selected['max_power_residual_over_peak']>1e-7 or selected['max_flux_residual_over_peak']>1e-7:
        raise ValueError('Invalid continuum stage power or flow balance')
    samples={s['time']:s['section_area_strain'] for s in selected['samples']}
    if set(samples)!={.5,1.} or any(len(s)!=len(d['sections']) for s in samples.values()):
        raise ValueError('Incomplete continuum section histories')
    if d['parameters']['support_stiffness'] or d['parameters']['support_damping']:
        raise ValueError('Expected a freely expanding wall')
    return d,selected,samples


def indices(source,target):
    result=[]
    for position in source:
        matching=[j for j,x in enumerate(target) if math.isclose(position,x,abs_tol=1e-11,rel_tol=0)]
        if len(matching)!=1:raise ValueError(f'No unique reference at x={position}; interpolation disabled')
        result.append(matching[0])
    return result


def compare(records,reference):
    d,run,samples=continuum(reference)
    material=d['parameters']
    a,b=material['radius'],material['outer_radius']
    nu=material['poisson']
    compliance=2*(1+nu)*((1-2*nu)*a*a+b*b)/(material['young']*(b*b-a*a))
    rows=[]
    for record in records:
        raw=record['report']
        physical=raw['axial_sections'];pos=indices(physical,d['sections'])
        special=indices([0.,1.,2.],physical)
        peak=record['peak_pressure'];scale=peak/d['pressure']
        equilibrium=peak*compliance
        if not math.isclose(raw.get('equilibrium_area_strain',equilibrium),equilibrium,rel_tol=1e-12):
            raise ValueError('Inconsistent static normalization')
        if (raw['matched_pressure_max_abs']>1e-12*peak
                or set(raw['sv_convergence'])!={'FS','MS'}
                or any(v[0]>1e-8 for v in raw['sv_convergence'].values())
                or [s['time'] for s in raw['results']]!=[.5,1.]):
            raise ValueError(f'Incomplete paired solve {record["case"]}')
        for rec in raw['results']:
            a,b=(rec[solver]['strains'] for solver in ('eon','svfsi'))
            target=[scale*samples[rec['time']][j] for j in pos]
            if not len(a)==len(b)==len(target) or not all(math.isfinite(v) for v in a+b+target):
                raise ValueError('Missing or nonfinite cross-section result')
            gap=[(x-y)/equilibrium for x,y in zip(a,b)]
            if (abs(max(map(abs,gap))-rec['max_abs_gap_all_sections'])>1e-11 or
                    abs(max(abs(gap[j]) for j in special)-rec['max_abs_gap_common_sections'])>1e-11):
                raise ValueError('Original spatial comparison could not be reproduced')
            out=dict(group=record['group'],case=record['case'],sv_variant=record['sv_variant'],
                     sectors=raw['mesh'][0],fluid_radial=raw['mesh'][1],wall_layers=raw['mesh'][2],axial=raw['mesh'][3],
                     steps=raw['steps'],peak_pressure=peak,time=rec['time'],reference_steps=run['steps'],
                     max_intercode_all_pct_static=100*max(map(abs,gap)),
                     max_intercode_ends_mid_pct_static=100*max(abs(gap[j]) for j in special))
            for name,values in [('eon',a),('svfsi',b)]:
                errors=[100*(x-y)/equilibrium for x,y in zip(values,target)]
                j=max(range(len(errors)),key=lambda k:abs(errors[k]))
                out[name+'_max_abs_error_pct_static']=abs(errors[j])
                out[name+'_max_error_x']=physical[j]
                out[name+'_x0_error_pct_static']=errors[0];out[name+'_xL_error_pct_static']=errors[-1]
                out[name+'_x0_strain_pct_area']=100*values[0];out[name+'_xL_strain_pct_area']=100*values[-1]
                out[name+'_mid_strain_pct_area']=100*values[special[1]]
            rows.append(out)
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    inputs=parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--runs',type=Path,help='Root containing the original paired run directories and matching compiled svFSI variants')
    inputs.add_argument('--archive',type=Path,help='Compressed authenticated run summaries')
    parser.add_argument('--write-archive',type=Path)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--csv',type=Path,required=True)
    args=parser.parse_args()
    records=pack(args.runs) if args.runs else json.loads(lzma.decompress(args.archive.read_bytes()))
    if not records:raise ValueError('No paired results')
    rows=compare(records,args.reference)
    if args.write_archive:
        packed=lzma.compress(json.dumps(records,separators=(',',':'),allow_nan=False).encode())
        temporary=args.write_archive.with_suffix('.partial')
        temporary.write_bytes(packed)
        temporary.replace(args.write_archive)
    with args.csv.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    print(len(records),'paired runs,',len(rows),'sample times')


if __name__=='__main__':main()
