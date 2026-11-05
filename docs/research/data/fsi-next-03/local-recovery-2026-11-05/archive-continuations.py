"""Preserve actual continuation fields as well as their indices and reports."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import xml.etree.ElementTree as ET

p=argparse.ArgumentParser()
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();source=a.source.resolve()
files=sorted(x for x in source.rglob('*') if x.is_file())
if not any((source/name).is_file() for name in ('transient-result.json','sampling-result.json')):
    raise RuntimeError('Missing completed continuation result')
for path in files:
    if path.suffix in ('.pvd','.pvtu'):
        tag,attribute=('.//DataSet','file') if path.suffix=='.pvd' else ('.//Piece','Source')
        for item in ET.parse(path).findall(tag):
            target=(path.parent/item.attrib[attribute]).resolve()
            if not target.is_relative_to(source) or not target.is_file():
                raise RuntimeError('Missing or external field reference: '+str(target))
index={'source':str(source),'files':{}}
a.output.parent.mkdir(parents=True,exist_ok=True)
temporary=a.output.with_suffix('.tmp')
with tarfile.open(temporary,'w:gz') as archive:
    for path in files:
        data=path.read_bytes();name=path.relative_to(source).as_posix()
        index['files'][name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        archive.add(path,arcname=name,recursive=False)
# Verify the compressed bytes before publishing a complete-archive name.
with tarfile.open(temporary) as archive:
    names=[]
    for member in archive.getmembers():
        data=archive.extractfile(member).read();names.append(member.name)
        if index['files'][member.name]!={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}:
            raise RuntimeError('Archive verification failed: '+member.name)
    if len(names)!=len(set(names)) or set(names)!=set(index['files']):
        raise RuntimeError('Archive inventory mismatch')
temporary.replace(a.output)
index['archive_sha256']=hashlib.sha256(a.output.read_bytes()).hexdigest()
a.output.with_suffix(a.output.suffix+'.manifest.json').write_text(json.dumps(index,indent=2)+'\n')
print(json.dumps({'archive':str(a.output),'files_verified':len(files),'bytes':a.output.stat().st_size}),flush=True)
