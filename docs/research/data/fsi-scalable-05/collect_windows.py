"""Collect compact trajectory receipts and content hashes, leaving complete fields on the host."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1<<20), b''):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('out',type=Path)
    args = parser.parse_args()
    root, out = args.root.resolve(), args.out.resolve()
    out.mkdir(exist_ok=True,parents=True)
    summary, index, runs = [], {}, []
    for name in ('window.json','first.json','native-mesh.json','timings.json'):
        for p in sorted(root.rglob(name)):
            if 'source' in p.relative_to(root).parts or out in p.parents:
                continue
            work = p.parent
            row = json.loads(p.read_text())
            if (work/'solve.log').is_file() and 'log_sha256' in row and row['log_sha256']!=digest(work/'solve.log'):
                raise ValueError(f'Log differs from receipt: {work}')
            entry = str(p.relative_to(root))
            runs.append(dict(receipt=entry, data=row))
            if name=='window.json':
                linear = row.get('linear',{})
                summary.append(dict(run=str(work.relative_to(root)), job=row['job'],case=row['case'],steps=row['steps'],
                    profile=row['profile'],protocol=row['policy']['protocol_id'],hash=row['policy']['hash'],
                    accepted=len(row.get('accepted_steps',[])), newton=linear.get('corrections'),
                    ksp=linear.get('ksp_iterations'),max_ratio=linear.get('max_ratio'),
                    seconds=row.get('T_job'),rss_bytes=row.get('rss_peak'),core_hours=row.get('core_hours'),
                    qualification=row['qualification'],error=row.get('error','')))
            for f in sorted(work.rglob('*')):
                key = str(f.relative_to(root))
                if f.is_file() and key not in index:
                    index[key] = dict(bytes=f.stat().st_size,sha256=digest(f))
    for f in sorted(root.glob('*.log')):
        index[f.name] = dict(bytes=f.stat().st_size,sha256=digest(f))
    with (out/'calibration.csv').open('w',newline='') as stream:
        if summary:
            writer = csv.DictWriter(stream,fieldnames=list(summary[0]))
            writer.writeheader()
            writer.writerows(summary)
    for filename, obj in [('run-receipts.json.gz',runs),('log-index.json.gz',index)]:
        with (out/filename).open('wb') as f, gzip.GzipFile(fileobj=f, mode='wb',mtime=0) as z:
            z.write(json.dumps(obj, separators=(',',':'),allow_nan=False).encode())
    print(f'{len(runs)} receipts, {len(index)} artifacts')


if __name__=='__main__':
    main()
