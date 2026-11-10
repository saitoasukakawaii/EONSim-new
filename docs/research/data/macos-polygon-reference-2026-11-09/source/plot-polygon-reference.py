from pathlib import Path
import json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[2];e=root/'docs/research/data/macos-polygon-reference-2026-11-09'
fig,axes=plt.subplots(1,2,figsize=(10.4,4.2),layout='constrained')
for sectors,marker in [(48,'o'),(96,'s')]:
 rows=json.loads((e/f's{sectors}-completion.json').read_text())['reports']
 for alpha,color in [(1,'#2563eb'),(2,'#c2410c')]:
  r=[v for v in rows if v['alpha']==alpha];label=f'S{sectors}, alpha={alpha}'
  axes[0].loglog([v['nodes'] for v in r[1:]],[v['successive_field_change'] for v in r[1:]],marker=marker,color=color,ls='-' if sectors==96 else '--',label=label)
  axes[1].semilogx([v['nodes'] for v in r],[100*v['metrics']['velocity_relative_l2'] for v in r],marker=marker,color=color,ls='-' if sectors==96 else '--',label=label)
axes[0].axhline(1e-4,color='#555555',ls=':',label='Increment gate 1e-4')
axes[0].set(xlabel='P2 degrees of freedom',ylabel='Successive field difference / fine norm',title='Observed reference refinement')
axes[1].set(xlabel='P2 degrees of freedom',ylabel='Velocity difference (%)',title='Polygon versus circle (polygon norm)')
for ax in axes:ax.grid(True,alpha=.2);ax.legend(fontsize=8)
fig.suptitle('Fresh polygon reference — geometry diagnostic, not 3D qualification',fontsize=11)
for ext in ['png','svg']:fig.savefig(e/f'polygon-reference.{ext}',dpi=180)
proof=dict(inputs={f's{s}-completion.json':hashlib.sha256((e/f's{s}-completion.json').read_bytes()).hexdigest() for s in [48,96]},outputs={f'polygon-reference.{ext}':hashlib.sha256((e/f'polygon-reference.{ext}').read_bytes()).hexdigest() for ext in ['png','svg']},source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),matplotlib=matplotlib.__version__)
(e/'figure-provenance.json').write_text(json.dumps(proof,indent=2)+'\n')
