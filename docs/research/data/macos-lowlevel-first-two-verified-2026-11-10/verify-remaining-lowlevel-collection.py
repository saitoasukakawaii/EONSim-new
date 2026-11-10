"""Read-only full-member verification of one completed selected collection."""
from pathlib import Path
import argparse,json,hashlib,subprocess,tarfile,time
b=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
selection=json.loads((b/'remaining-lowlevel-recompression-selection.json').read_text());item=next(x for x in selection if x['name']==a.name)
assert not a.output.exists()
receipts=sorted((b/'archives'/a.name).glob('*.json'));assert len(receipts)==item['chunks']
# Require every transaction complete before decoding; never race publication.
for rp in receipts:
 r=json.loads(rp.read_text());assert json.loads(Path(r['recompression']['journal']).read_text())['status']=='committed'
seen=set();proof=[];source=None;rows=None;old_total=0;new_total=0
for rp in receipts:
 raw=rp.read_bytes();r=json.loads(raw);archive=Path(r['archive']);jp=Path(r['recompression']['journal']);j=json.loads(jp.read_text())
 assert j['status']=='committed' and not (jp.parent/'old-archive.backup').exists() and not (jp.parent/'new-archive.pending').exists()
 assert sha(archive)==r['archive_sha256']==j['new_archive_sha256'];assert archive.stat().st_size==r['archive_bytes']==j['new_bytes']
 mp=Path(r['source_manifest']);assert sha(mp)==r['source_manifest_sha256']
 if source is None:
  source=str(mp);m=json.loads(mp.read_text());rows={x['path']:x for x in m['files']};assert len(rows)==len(m['files'])
 assert str(mp)==source and r['status']=='evicted'
 selected=r['selected'];assert set(selected)<=rows.keys() and not seen.intersection(selected)
 proc=subprocess.Popen(['zstd','-q','-d','-c',str(archive)],stdout=subprocess.PIPE);actual=set()
 try:
  with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:
   for member in tar:
    assert member.isfile() and member.name in selected and member.name not in actual
    row=rows[member.name];s=selected[member.name]
    assert member.size==row['bytes']==s['bytes']
    assert hashlib.file_digest(tar.extractfile(member),'sha256').hexdigest()==row['sha256']==s['sha256']
    actual.add(member.name)
  proc.stdout.read();assert proc.wait()==0
 finally:
  proc.stdout.close()
  if proc.poll() is None:proc.terminate();proc.wait()
 assert actual==set(selected) and rp.read_bytes()==raw and sha(archive)==r['archive_sha256']
 seen.update(actual);old_total+=j['old_bytes'];new_total+=j['new_bytes'];proof.append(dict(receipt=str(rp),receipt_sha256=sha(rp),archive_sha256=r['archive_sha256'],members=len(actual)))
assert seen==set(rows) and len(seen)==item['members'] and old_total==item['bytes']
a.output.write_text(json.dumps(dict(status='verified',collection=a.name,members=len(seen),old_bytes=old_total,new_bytes=new_total,saved_bytes=old_total-new_total,verified_unix=time.time(),verifier_sha256=sha(Path(__file__)),chunks=proof),indent=2)+'\n')
print(a.name,len(seen),'verified; saved',old_total-new_total,flush=True)
