"""Replay the measured mirror pair and reject independent corruptions of its cached observations."""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('original','mirrored','reference-scripts','output'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    script=Path(__file__).with_name('audit_reflection.py')
    saved=json.loads((args.mirrored/'results.json').read_text())
    labels={}
    with tempfile.TemporaryDirectory() as tmp:
        mirror=Path(tmp)/'mirror';mirror.mkdir()
        for original in args.mirrored.iterdir():
            if original.name!='results.json':(mirror/original.name).symlink_to(original.resolve(),target_is_directory=original.is_dir())
        for label in ('original','one-strain','missing-station','moved-station','wrong-time'):
            sample=copy.deepcopy(saved)
            if label=='one-strain':sample['results'][1]['svfsi']['strains'][3]+=.001
            if label=='missing-station':sample['results'][0]['eon']['strains'].pop()
            if label=='moved-station':sample['axial_sections'][1]+=.015
            if label=='wrong-time':sample['results'][1]['time']=.75
            (mirror/'results.json').write_text(json.dumps(sample))
            result=Path(tmp)/(label+'.json')
            run=subprocess.run([sys.executable,script,'--original',args.original,'--mirrored',mirror,
                                '--reference-scripts',args.reference_scripts,'--output',result],
                               text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            if label=='original':
                if run.returncode or not result.is_file():raise ValueError(run.stdout)
                labels[label]=json.loads(result.read_text())
            else:
                expected='Cached cross-section' if label in ('moved-station','wrong-time') else 'Cached section strains'
                if run.returncode==0 or expected not in run.stdout or result.exists():raise ValueError(label+' negative control did not fail at its intended check')
                labels[label]=run.stdout.splitlines()[-1]
    args.output.write_text(json.dumps(labels,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
