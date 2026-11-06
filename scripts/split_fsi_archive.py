"""Lossless transport chunks for large numerical evidence archives."""
import argparse
import hashlib
import json
from pathlib import Path


def split(source,directory):
    directory.mkdir(parents=True,exist_ok=True);parts=[];whole=hashlib.sha256();total=0
    with source.open('rb') as stream:
        while data:=stream.read(4*1024*1024):
            name=source.name+f'.part-{len(parts):03d}'
            (directory/name).write_bytes(data);whole.update(data);total+=len(data)
            parts.append(dict(file=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    if not parts:raise ValueError('Empty archive')
    result=dict(archive=source.name,bytes=total,sha256=whole.hexdigest(),parts=parts)
    path=directory/(source.name+'.parts.json');temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,indent=2)+'\n');temporary.replace(path)
    return path


def join(manifest,output):
    definition=json.loads(manifest.read_text());output.parent.mkdir(parents=True,exist_ok=True)
    whole=hashlib.sha256();total=0;temporary=output.with_name(output.name+'.tmp')
    if not definition['parts']:raise ValueError('Empty chunk list')
    paths=[]
    for part in definition['parts']:
        name=part['file'];path=manifest.parent/name
        if Path(name).name!=name or path.resolve().parent!=manifest.parent.resolve():raise ValueError('Invalid chunk path')
        paths.append(path)
    inputs={manifest.resolve(),*(path.resolve() for path in paths)}
    if output.resolve() in inputs or temporary.resolve() in inputs:raise ValueError('Output would replace an input')
    with temporary.open('wb') as stream:
        for part,path in zip(definition['parts'],paths):
            data=path.read_bytes()
            if len(data)!=part['bytes'] or hashlib.sha256(data).hexdigest()!=part['sha256']:raise ValueError('Chunk checksum mismatch')
            stream.write(data);whole.update(data);total+=len(data)
    if total!=definition['bytes'] or whole.hexdigest()!=definition['sha256']:raise ValueError('Archive checksum mismatch')
    temporary.replace(output)
    return output


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True)
    s=sub.add_parser('split');s.add_argument('source',type=Path);s.add_argument('--directory',type=Path,required=True)
    j=sub.add_parser('join');j.add_argument('manifest',type=Path);j.add_argument('--output',type=Path,required=True)
    a=p.parse_args();path=split(a.source,a.directory) if a.action=='split' else join(a.manifest,a.output)
    print(path)


if __name__=='__main__':main()
