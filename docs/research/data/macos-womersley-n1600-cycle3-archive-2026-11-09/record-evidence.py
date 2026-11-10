from pathlib import Path
import json,shutil,hashlib,math
r=Path('.');b=r/'build/recompute-20261109';e=r/'docs/research/data/macos-womersley-n1600-cycle3-archive-2026-11-09';e.mkdir()
for n in ['prepare-womersley-n1600-cycle3-archive.py','archive-womersley-n1600-cycle3-chunks.py','verify-womersley-n1600-cycle3-archives.py','capture-womersley-n1600.py','womersley-n1600-cycle3-prepare.log','womersley-n1600-cycle3-incomplete-rejection.log','womersley-n1600-cycle3-archive.log','womersley-n1600-cycle3-verification.log','womersley-n1600-cycle3-restore-probe.json']:shutil.copy2(b/n,e/n)
shutil.copy2(b/'alpha2-s96-l1-n1600-cycle3-before-archive.json',e/'cycle3-before-archive.json')
d=b/'archives/alpha2-s96-l1-n1600-cycle3-chunks';shutil.copytree(d,e/'receipts',ignore=shutil.ignore_patterns('*.tar.zst'));rs=[json.loads(p.read_text()) for p in d.glob('*.json')];assert len(rs)==39 and all(x['status']=='evicted' for x in rs)
s=dict(chunks=len(rs),members=sum(len(x['selected']) for x in rs),removed_allocated_bytes=sum(x['removed_allocated_bytes'] for x in rs),archive_bytes=sum(x['archive_bytes'] for x in rs));s['net_reclaimed_bytes']=s['removed_allocated_bytes']-s['archive_bytes'];(e/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
assert 'Verified archived cycle3 1599 5182563672' in (e/'womersley-n1600-cycle3-verification.log').read_text()
(e/'README.md').write_text('''# Active N1600 immutable cycle3 archival

Baseline7ad2dfb. Controller/binary unchanged. study_womersley.py only loads checkpoint/current between stages; final analyze_womersley.py uses cycles6/5/4. Internal cycle3 states3201..4799 archived; endpoint4800 and later states retained. Future cycle3 consumers must restore first.

31349capture exited0:1599states; completed attempt003 contiguous log ends success, receipt>=4800/current>4800, hashes/stable size/mtime verified.24343archive exited0:39chunks/1599HDF, every member decoded/SHA checked before deletion.82079full independent archive reread exited0; original1599HDF bytes and generation manifests verified. Two actual HDF restored separately and SHA checked. Net reclaimed1192696188B. Missing archive negative check rejected. Final capture now verifies archived members plus materialized files, still requires9600steps/full analytic report; actual final capture NOT run.

Actual commands: python3 build/recompute-20261109/prepare-womersley-n1600-cycle3-archive.py; python3 build/recompute-20261109/archive-womersley-n1600-cycle3-chunks.py; python3 build/recompute-20261109/verify-womersley-n1600-cycle3-archives.py; python3 build/recompute-20261109/restore-womersley-materialization.py build/recompute-20261109/womersley-n1600-cycle3-restore-probe.json.

39receipts/logs/source retained; raw archives local. No new numerical claim/article; no push/PR. First evidence-recording inline Python had SyntaxError and made no changes; corrected recording script retained.
''')
g=r/'docs/research/data/macos-elastic-geometry48-n800-2026-11-09';summary=json.loads((g/'summary.json').read_text());assert summary['all_local_physical_checks_passed']
for name,target in [('elastic-geometry48-response.json','response.json'),('elastic-geometry48-response.log','response.log'),('compare-elastic-control-response.py','compare-response.py'),('geometry48-capture.log','capture.log')]:shutil.copy2(b/name,g/target)
response=json.loads((g/'response.json').read_text());reports=[json.loads((b/n).read_text()) for n in ['elastic-s24-l1-n800-audit.json','elastic-s24-l1-n800-geometry48-audit.json']]
for field,rr in response['observables'].items():
 left,right=[a['harmonics'][field] for a in reports];assert rr['baseline']==left and rr['control']==right
 assert abs(right['amplitude']/left['amplitude']-1-rr['amplitude_relative_to_baseline'])<1e-14
 delta=math.radians(right['phase_degrees']-left['phase_degrees']);phase=math.degrees(math.atan2(math.sin(delta),math.cos(delta)));assert abs(phase-rr['phase_difference_degrees'])<1e-12
for path,digest in response['input_sha256'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest
(g/'response-independent-check.json').write_text(json.dumps(dict(fields_checked=5,amplitude_ratio_and_atan2_phase_checked=True,consumed_input_hashes_verified=True,source_baseline='7ad2dfb',scope='Scalar response arithmetic and hash checks; no new acceptance gate.'),indent=2)+'\n')
p=g/'README.md';p.write_text(p.read_text()+'''
Audit81210/capture11179 exited0. All9815raw members verified, including decoded boundary chunks. Geometry response command: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 build/analysis-venv/bin/python build/recompute-20261109/compare-elastic-control-response.py --mode geometry --baseline-work build/recompute-20261109/elastic-s24-l1-n800 --control-work build/recompute-20261109/elastic-s24-l1-n800-geometry48 --baseline-audit build/recompute-20261109/elastic-s24-l1-n800-audit.json --control-audit build/recompute-20261109/elastic-s24-l1-n800-geometry48-audit.json --output build/recompute-20261109/elastic-geometry48-response.json ; exit0. Five harmonic amplitude ratios/atan2 wrapped phases independently recalculated; all consumed hashes rechecked. Source baseline7ad2dfb; frozen production binary unchanged.

Lamé error0.8225094331% passes original2%. Radial displacement amplitude increases1.1763678447%, pressure amplitude0.7447735614%, phase+0.3801927176/+0.3985159915degrees versus24-sided baseline. Fixed-topology geometry sensitivity includes basis interaction; not exact continuum geometry error. Original failed time budgets unchanged. Length control, fine reference and N1600 qualification remain pending.
''')
shutil.copy2(b/'record-cycle3-and-geometry.py',e/'record-evidence.py')
print('39chunks and full geometry result captured;5response pairs checked')
