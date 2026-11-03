"""Offline reference-volume lumped field norms for conforming Tet4 FSI outputs."""
import math
from pathlib import Path
import xml.etree.ElementTree as ET


def read_snapshot(path, solid=False, include_cells=False):
    path=Path(path)
    if path.suffix=='.pvtu':
        pieces=[path.parent/p.attrib['Source'] for p in ET.parse(path).findall('.//Piece')]
    else:pieces=[path]
    nodes={};weights={};cells=set()
    for piece in pieces:
        root=ET.parse(piece)
        arrays={a.attrib['Name']:(int(a.attrib.get('NumberOfComponents',1)),list(map(float,(a.text or '').split()))) for a in root.findall('.//PointData/DataArray')}
        ids=[int(x) for x in arrays['mesh_node_id'][1]]
        xyz=list(map(float,root.find('.//Points/DataArray').text.split()))
        conn=list(map(int,(root.find('.//Cells/DataArray[@Name="connectivity"]').text or '').split()))
        disp=arrays['displacement' if solid else 'mesh_displacement'][1]
        ref=[[xyz[3*i+j]-disp[3*i+j] for j in range(3)] for i in range(len(ids))]
        names=('velocity','displacement') if solid else ('velocity','pressure','mesh_displacement')
        for i in set(conn):
            node=ids[i];value={name:arrays[name][1][i*arrays[name][0]:(i+1)*arrays[name][0]] for name in names}
            if node in nodes and any(abs(a-b)>2e-9 for name in names for a,b in zip(value[name],nodes[node][name])):
                raise ValueError('Inconsistent duplicate node')
            value['reference_position']=ref[i]
            nodes[node]=value
        for i in range(0,len(conn),4):
            c=conn[i:i+4];key=tuple(sorted(ids[j] for j in c))
            if key in cells:raise ValueError('Duplicate owned cell')
            cells.add(key)
            a,b,d=[[ref[c[k]][j]-ref[c[0]][j] for j in range(3)] for k in (1,2,3)]
            volume=abs(a[0]*(b[1]*d[2]-b[2]*d[1])-a[1]*(b[0]*d[2]-b[2]*d[0])+a[2]*(b[0]*d[1]-b[1]*d[0]))/6
            if not math.isfinite(volume) or volume<=0:raise ValueError('Invalid reference volume')
            for j in c:weights[ids[j]]=weights.get(ids[j],0)+volume/4
    if not nodes:raise ValueError('Empty physical domain')
    return (nodes,weights,tuple(cells)) if include_cells else (nodes,weights)


def difference(a,b,scales):
    na,wa=a;nb,wb=b
    if na.keys()!=nb.keys() or wa.keys()!=wb.keys():raise ValueError('Incompatible snapshot nodes')
    if any(abs(wa[k]-wb[k])>1e-10*max(wa[k],wb[k]) for k in wa):raise ValueError('Reference geometry changed')
    total=sum(wa.values())
    result={}
    for field,scale in scales.items():
        if not math.isfinite(scale) or scale<=0:raise ValueError('Invalid physical scale')
        value=sum(wa[k]*sum((x-y)**2 for x,y in zip(na[k][field],nb[k][field])) for k in wa)/total
        if not math.isfinite(value):raise ValueError('Nonfinite field difference')
        result[field]=math.sqrt(value)/scale
    return result


def series(path):
    path=Path(path)
    return [(float(p.attrib['timestep']),path.parent/p.attrib['file']) for p in ET.parse(path).findall('.//DataSet')]


def compare_series(entries,period,end,scales,solid=False,phases=20):
    """Compare common physical phases using bounded linear time interpolation.

    No extrapolation is allowed. Gaps exceeding T/16 are rejected; studies must
    additionally quantify phase-sampling error before using convergence results.
    """
    import bisect
    entries=sorted(entries);times=[t for t,_ in entries]
    if phases<16 or len(entries)<2:raise ValueError('At least 16 phases per cycle required')
    if any(b<=a for a,b in zip(times,times[1:])):raise ValueError('Nonincreasing snapshot times')
    if not all(math.isfinite(t) for t in times) or not math.isfinite(period) or period<=0:raise ValueError('Invalid phase times')
    tol=1e-10*period;cache={}
    def snapshot(i):
        if i not in cache:cache[i]=read_snapshot(entries[i][1],solid)
        return cache[i]
    def sample(t):
        i=bisect.bisect_left(times,t)
        for j in (i,i-1):
            if 0<=j<len(times) and abs(times[j]-t)<=tol:return snapshot(j)
        if i==0 or i==len(times):raise ValueError('Missing matching phase coverage; extrapolation forbidden')
        if times[i]-times[i-1]>period/16+tol:raise ValueError('Undersampled phase bracket')
        a,wa=snapshot(i-1);b,wb=snapshot(i)
        if a.keys()!=b.keys() or wa.keys()!=wb.keys():raise ValueError('Snapshot topology changed')
        if any(abs(wa[k]-wb[k])>1e-10*max(wa[k],wb[k]) for k in wa):raise ValueError('Reference geometry changed')
        f=(t-times[i-1])/(times[i]-times[i-1])
        blended={k:{name:[(1-f)*x+f*y for x,y in zip(a[k][name],b[k][name])] for name in a[k]} for k in a}
        return blended,wa
    result={name:0. for name in scales}
    for j in range(1,phases+1):
        t=end-period+j*period/phases
        error=difference(sample(t-period),sample(t),scales)
        for name,value in error.items():result[name]=max(result[name],value)
    return result


def pressure_drop(snapshot,axis=0):
    """Area-averaged inlet minus outlet pressure on the fixed reference planes."""
    import itertools
    nodes,_,cells=snapshot
    bounds=[min(v['reference_position'][axis] for v in nodes.values()),max(v['reference_position'][axis] for v in nodes.values())]
    means=[]
    for plane in bounds:
        area=0.;integral=0.;faces=set()
        for cell in cells:
            for face in itertools.combinations(cell,3):
                if face in faces:continue
                xyz=[nodes[k]['reference_position'] for k in face]
                if not all(abs(x[axis]-plane)<1e-10 for x in xyz):continue
                faces.add(face)
                a,b=[[xyz[k][j]-xyz[0][j] for j in range(3)] for k in (1,2)]
                cross=[a[(j+1)%3]*b[(j+2)%3]-a[(j+2)%3]*b[(j+1)%3] for j in range(3)]
                weight=.5*math.sqrt(sum(x*x for x in cross))
                area+=weight;integral+=weight*sum(nodes[k]['pressure'][0] for k in face)/3
        if area<=0:raise ValueError('Missing pressure observation plane')
        means.append(integral/area)
    return dict(inlet_pressure=means[0],outlet_pressure=means[1],pressure_drop=means[0]-means[1])
