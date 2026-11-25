"""Compare independently measured complex area compliance and total cap admittance."""
import argparse
import cmath
import csv
import hashlib
import json
import lzma
import math
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pack(root):
    reference={}
    for receipt in sorted((root/'harmonic-reference').glob('*.ok')):
        p=receipt.with_suffix('.json');reference[digest(p)]=json.loads(p.read_text())
    data=[]
    sources=list((root/'harmonic-3d').glob('*/result.json'))+list((root/'harmonic-3d-controls').glob('*/result.json'))
    for p in sorted(sources):
        r=json.loads(p.read_text())
        if r['reference_sha256'] not in reference or r['mesh_sha256']!=[digest(p.parent/f'{dom}.msh') for dom in ('fluid','solid')]:
            raise ValueError('Input reference or 3D mesh differs in '+p.parent.name)
        n=round(r['cycles']*r['steps_per_cycle'])
        if not ((p.parent/'warm.log').read_text().splitlines()[-1:]==['status=success'] and
                (p.parent/'measure.log').read_text().splitlines()[-1:]==['status=success']):
            raise ValueError('Incomplete warmup or measurement')
        config=json.loads((p.parent/'measure.json').read_text())
        if config['fsi'].get('stabilization_time_scale')!=r.get('stabilization_time_scale'):
            raise ValueError('Changed stabilization time in the deck')
        if config['fsi']['steps']!=n:
            raise ValueError('Changed number of harmonic steps')
        data.append(dict(case=p.parent.name,report=r,case_sha256=digest(p.parent/'measure.json')))
    return dict(references=reference,three_dimensional=data)


def cpair(values):
    if len(values)!=2 or not all(map(math.isfinite,values)):raise ValueError('Invalid complex observation')
    return complex(*values)


def stage(reference,hz):
    found=[r for r in reference['frequencies'] if r['frequency_hz']==hz]
    if len(found)!=1:raise ValueError('Missing frequency')
    r=found[0]
    if not (0<=r['complex_power_defect_fraction']<1e-7 and 0<=r['mass_defect_over_flux']<1e-7):
        raise ValueError('Unbalanced harmonic reference')
    c=[cpair(z) for z in r['area_strain_per_pa']]
    y=cpair(r['inward_flux_per_radian_per_pa'])*(math.pi/2 if reference['full_length'] else math.pi)
    return c,y


def positions(grid,samples):
    ids=[]
    for x in samples:
        found=[j for j,p in enumerate(grid) if math.isclose(x,p,rel_tol=0,abs_tol=1e-11)]
        if len(found)!=1:raise ValueError('Axial location missing from independent reference')
        ids.append(found[0])
    return ids


def tables(data):
    by_support={}
    for r in data['references'].values():
        k=tuple(r['parameters'][p] for p in ('support_stiffness','support_damping'))
        by_support.setdefault(k,[]).append(r)
    continuum=[]
    for support,items in sorted(by_support.items()):
        ordered=sorted((r for r in items if not r['full_length']),key=lambda r:r['unknowns'])
        prev,fine=ordered[-2:]
        if fine['sections']!=prev['sections']:raise ValueError('Meridian stations changed')
        grid=fine['sections'];mid=positions(grid,[1.])[0]
        pairs=[]
        for full in items:
            if not full['full_length']: continue
            half=[r for r in ordered if r['mesh']==full['mesh'] and r['corner_levels']==full['corner_levels']]
            if len(half)!=1 or full['sections']!=half[0]['sections']:
                raise ValueError('No matching half mesh for the full-length symmetry control')
            pairs.append((full,half[0]))
        for sample in fine['frequencies']:
            hz=sample['frequency_hz']
            c,y=stage(fine,hz);old,old_y=stage(prev,hz)
            symmetry_area=symmetry_flux=None
            if pairs:
                gaps_area=[]
                gaps_flux=[]
                for full,half in pairs:
                    ca,ya=stage(full,hz);cb,yb=stage(half,hz)
                    gaps_area.append(max(abs(a-b) for a,b in zip(ca,cb))/fine['static_area_strain_per_pa'])
                    gaps_flux.append(abs(ya-yb)/abs(yb))
                symmetry_area=100*max(gaps_area)
                symmetry_flux=100*max(gaps_flux)
            continuum.append(dict(stiffness=support[0],damping=support[1],hz=hz,unknowns=fine['unknowns'],
                static_area_per_pa=fine['static_area_strain_per_pa'],end_area_modulus_per_pa=abs(c[0]),end_phase_deg=math.degrees(cmath.phase(c[0])),
                mid_area_modulus_per_pa=abs(c[mid]),mid_phase_deg=math.degrees(cmath.phase(c[mid])),
                total_quarter_influx_modulus_m3_per_s_pa=abs(y),influx_phase_deg=math.degrees(cmath.phase(y)),
                previous_grid_max_area_change_pct_static=100*max(abs(a-b) for a,b in zip(c,old))/fine['static_area_strain_per_pa'],
                previous_grid_influx_change_pct=100*abs(y-old_y)/abs(y),complex_power_defect=sample['complex_power_defect_fraction'],
                mass_defect=sample['mass_defect_over_flux'],matching_full_half_pairs=len(pairs),
                full_half_max_area_difference_pct_static=symmetry_area,full_half_influx_difference_pct=symmetry_flux))
    results=[]
    for item in data['three_dimensional']:
        r=item['report'];support=tuple(r['support']);hz=r['frequency_hz'];n=r['samples_per_cycle'];frames=r['samples']
        if len(frames)!=2*n or n<4:raise ValueError('Need two full periods')
        w=2*math.pi*hz
        for i,s in enumerate(frames):
            if i and abs(s['time']-frames[i-1]['time']-1/(hz*n))>1e-9/hz:raise ValueError('Incomplete sampled period')
            if len(s['strains'])!=len(r['stations']) or not all(map(math.isfinite,[s['influx'],s['pressure'],*s['strains']])):
                raise ValueError('Invalid harmonic sample')
        def phasor(values):
            return 2*sum(v*cmath.exp(-1j*w*s['time']) for v,s in zip(values,frames[-n:]))/n
        pressure=phasor([s['pressure'] for s in frames[-n:]])
        if abs(abs(pressure)-r['pressure_amplitude'])>1e-10*r['pressure_amplitude']:raise ValueError('Wrong drive amplitude')
        z=[phasor([s['strains'][j] for s in frames[-n:]])/pressure for j in range(len(r['stations']))]
        flux=phasor([s['influx'] for s in frames[-n:]])/pressure
        if max(abs(v-cpair(p)) for v,p in zip(z,r['area_strain_per_pa']))>1e-12 or abs(flux-cpair(r['influx_admittance']))>1e-12:
            raise ValueError('Measured phasors could not be reconstructed')
        previous=max(abs(a['strains'][j]-b['strains'][j])/(abs(z[j])*abs(pressure))
                     for a,b in zip(frames[:n],frames[n:]) for j in range(len(z)))
        flux_change=max(abs(a['influx']-b['influx']) for a,b in zip(frames[:n],frames[n:]))/(abs(flux)*abs(pressure))
        ref=max((d for d in by_support[support] if not d['full_length']),key=lambda d:d['unknowns'])
        c,y=stage(ref,hz);static=ref['static_area_strain_per_pa']
        idx=positions(ref['sections'],r['stations'])
        errors=[abs(v-c[j])/static for j,v in zip(idx,z)]
        phases=[math.degrees(cmath.phase(v/c[j])) for j,v in zip(idx,z)]
        results.append(dict(case=item['case'],stabilization_time_s=r.get('stabilization_time_scale'),hz=hz,stiffness=support[0],damping=support[1],steps_per_cycle=r['steps_per_cycle'],
                    cycles=r['cycles'],stations=len(z),meridian_unknowns=ref['unknowns'],end_area_modulus_per_pa=abs(z[0]),
                    end_phase_deg=math.degrees(cmath.phase(z[0])),end_phase_difference_deg=phases[0],
                    max_area_difference_pct_static=100*max(errors),worst_station_m=r['stations'][errors.index(max(errors))],
                    influx_modulus_m3_per_s_pa=abs(flux),influx_complex_difference_pct=100*abs(flux-y)/abs(y),
                    influx_modulus_difference_pct=100*(abs(flux/y)-1),influx_phase_difference_deg=math.degrees(cmath.phase(flux/y)),
                    previous_period_max_area_change_pct_local_harmonic=100*previous,previous_period_flux_change_pct_harmonic=100*flux_change,
                    periodic_within_0p1_pct=max(previous,flux_change)<1e-3))
    return continuum,results


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    src=cli.add_mutually_exclusive_group(required=True)
    src.add_argument('--runs',type=Path);src.add_argument('--archive',type=Path)
    cli.add_argument('--write-archive',type=Path)
    cli.add_argument('--meridian-csv',type=Path,required=True);cli.add_argument('--eon-csv',type=Path,required=True)
    args=cli.parse_args()
    data=pack(args.runs) if args.runs else json.loads(lzma.decompress(args.archive.read_bytes()))
    grids,actual=tables(data)
    for path,rows in ((args.meridian_csv,grids),(args.eon_csv,actual)):
        if not rows:raise ValueError('No completed curves')
        with path.open('w',newline='') as out:
            writer=csv.DictWriter(out,fieldnames=rows[0],lineterminator='\n');writer.writeheader();writer.writerows(rows)
    if args.write_archive:
        temporary=args.write_archive.with_suffix('.partial')
        temporary.write_bytes(lzma.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode()))
        temporary.replace(args.write_archive)
    print(len(grids),'reference frequencies/supports;',len(actual),'3D histories')


if __name__=='__main__':main()
