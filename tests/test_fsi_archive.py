"""Lossless evidence transport and preservation on failed reconstruction."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from split_fsi_archive import split,join


class EvidenceArchive(unittest.TestCase):
    def test_round_trip_and_corruption_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'archive.gz';data=bytes(range(256))*20480;source.write_bytes(data)
            manifest=split(source,root/'parts');output=root/'restored.gz';join(manifest,output)
            self.assertEqual(output.read_bytes(),data)
            definition=json.loads(manifest.read_text());self.assertEqual(len(definition['parts']),2)
            part=manifest.parent/definition['parts'][-1]['file'];part.write_bytes(b'corrupted')
            output.write_bytes(b'previous accepted archive')
            with self.assertRaisesRegex(ValueError,'checksum'):join(manifest,output)
            self.assertEqual(output.read_bytes(),b'previous accepted archive')

    def test_temporary_output_cannot_replace_input_chunk(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);part=root/'result.tmp';data=b'original chunk';part.write_bytes(data)
            digest=hashlib.sha256(data).hexdigest();manifest=root/'parts.json'
            manifest.write_text(json.dumps(dict(bytes=len(data),sha256=digest,parts=[dict(file=part.name,bytes=len(data),sha256=digest)])))
            with self.assertRaisesRegex(ValueError,'replace an input'):join(manifest,root/'result')
            self.assertEqual(part.read_bytes(),data)


if __name__=='__main__':unittest.main()
