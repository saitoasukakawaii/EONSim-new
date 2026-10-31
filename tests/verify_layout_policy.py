"""Policy declarations are independent from PC recipes and do not permute storage."""
import argparse
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def main():
    p=argparse.ArgumentParser();p.add_argument('--executable',required=True);p.add_argument('--mpiexec',required=True);p.add_argument('--work',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    mesh=Path(__file__).resolve().parents[1]/'cases/poisson/cube.msh'
    cfg=dict(mesh=str(mesh),output=str((a.work/'solution.vtu').resolve()),fluid=dict(mode='stokes'),solver=dict(relative_tolerance=1e-11,absolute_tolerance=1e-12))
    case=a.work/'case.json';case.write_text(json.dumps(cfg));part=a.work/'part'
    def run(command,error=None):
        r=subprocess.run(list(map(str,command)),text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
        assert (r.returncode!=0)==bool(error),r.stdout
        if error:assert error in r.stdout,r.stdout
        return r.stdout
    run([a.executable,'-case',case,'-prepare',part,'-parts',2])
    command=[a.mpiexec,'-n',2,a.executable,'-case',case,'-partition',part]
    def read():
        result=[]
        for rank in range(2):
            tree=ET.parse(a.work/f'solution_rank{rank}.vtu')
            result.append({x.attrib['Name']:list(map(float,x.text.split())) for x in tree.findall('.//PointData/DataArray')})
        return result
    run(command);baseline=read()
    cfg['layout']=dict(semantic_order='entity_first',storage_order='owner_node')
    for recipe in ('physics','quantity','hybrid'):
        cfg['solver']['pc_recipe']=recipe;case.write_text(json.dumps(cfg));text=run(command)
        assert 'layout_policy semantic_order=entity_first storage_order=owner_node' in text
        for actual,expected in zip(read(),baseline):
            assert actual.keys()==expected.keys()
            for field in actual:
                if field in ('mesh_node_id','owner','algebra_node_id'):assert actual[field]==expected[field]
                else:assert max(abs(x-y) for x,y in zip(actual[field],expected[field]))<2e-9
    for key,value in (('semantic_order','physics_first'),('storage_order','global_field')):
        cfg['layout'][key]=value;case.write_text(json.dumps(cfg))
        run(command,'Unsupported layout.'+key)
        cfg['layout'][key]='entity_first' if key=='semantic_order' else 'owner_node'
    print('Independent semantic/storage policy and three PC recipes verified')


if __name__=='__main__':main()
