"""Exercise compact provenance checks using the archived independent C20 pair."""
import gzip
import json
from pathlib import Path
import unittest

from c_archive_lineage import audit_archive_pair, verify_prefix


class ArchiveChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder=Path(__file__).resolve().parent/'c20'
        with gzip.open(folder/'run-receipts.json.gz','rt') as f:
            cls.entries=[e for e in json.load(f) if e['receipt'].endswith('/window.json')]
        with gzip.open(folder/'log-index.json.gz','rt') as f:
            cls.index=json.load(f)
        cls.lineage=audit_archive_pair(cls.entries,cls.index,0,20)

    def test_modified_rank_state_field_or_history(self):
        fixed=self.lineage['fixed-1e-6'][-1]
        root=Path(fixed.descriptor['directory']).name
        gen=fixed.generation.rsplit('/',1)[1]
        for file in (f'checkpoint/{gen}/state_rank63.h5','tube_step4_solid_rank63.vtu','tube.csv',
                     'tube_rank3.vtu','solve.log','fluid.msh','checkpoint/current'):
            index=dict(self.index)
            index[root+'/'+file]={'sha256':'0'*64,'bytes':1}
            with self.subTest(file=file),self.assertRaises(ValueError):
                audit_archive_pair(self.entries,index,0,20)

    def test_continuation_needs_own_pinned_generation_and_qualified_partner(self):
        own=self.lineage['lu']
        partner=self.lineage['fixed-1e-6']
        lu=own[-1]
        fgmres=partner[-1]
        row=dict(profile='lu',command=['eonsim','-restart',lu.generation],
                 restart_generation=lu.generation,prefix_receipt=lu.descriptor['window_sha256'],
                 prefix_segments=[lu.descriptor],prefix_T_job=lu.descriptor['T_job'],
                 prefix_pair_directory=fgmres.descriptor['directory'],prefix_pair_receipt=fgmres.descriptor['window_sha256'])
        verify_prefix(row,20,own,partner)
        for key,wrong in [('command',['eonsim','-restart',fgmres.generation]),
                          ('restart_generation',lu.descriptor['directory']+'/checkpoint'),
                          ('prefix_segments',[]),('prefix_receipt',fgmres.descriptor['window_sha256']),
                          ('prefix_pair_directory',lu.descriptor['directory']),
                          ('prefix_pair_receipt',lu.descriptor['window_sha256'])]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                verify_prefix({**row,key:wrong},20,own,partner)


if __name__=='__main__':
    unittest.main()
