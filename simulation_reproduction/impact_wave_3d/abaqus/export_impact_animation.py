"""Export actual first-impact ODB frames for a section/plan-view animation.

abaqus python export_impact_animation.py <odb> <output.npz>
No spatial or temporal interpolation; ball uses its reference-node displacement.
"""
import json
import sys
from pathlib import Path
import numpy as np
from odbAccess import openOdb


def main():
    source, target = Path(sys.argv[1]), Path(sys.argv[2])
    meta = json.loads(source.with_suffix('.sensors.json').read_text())
    ball = meta['impact']['ball_node']
    odb = openOdb(str(source), readOnly=True)
    try:
        step = odb.steps['IMPACT']
        assert abs(step.frames[-1].frameValue - .0005) < 1e-9
        assert len(odb.rootAssembly.instances) == 1
        instance = list(odb.rootAssembly.instances.values())[0]
        plate = set(n for e in instance.elements if e.type.startswith('C3D') for n in e.connectivity)
        coords = {n.label: tuple(n.coordinates) for n in instance.nodes}
        top = sorted(n for n in plate if abs(coords[n][2]-.002)<1e-8)
        section = sorted(n for n in plate if abs(coords[n][1]-.05)<1e-8)
        labels = np.array(sorted(set(top+section+[ball])),dtype=int)
        rows = {int(n):i for i,n in enumerate(labels)}
        lookup = np.full(max(coords)+1,-1,dtype=int)
        lookup[labels] = np.arange(len(labels))
        displacement=[]
        for frame in step.frames:
            u=np.full((len(labels),3),np.nan)
            for block in frame.fieldOutputs['U'].bulkDataBlocks:
                ids=np.asarray(block.nodeLabels,dtype=int)
                ii=lookup[ids]
                valid=ii>=0
                u[ii[valid]]=np.asarray(block.data)[valid,:3]
            assert np.isfinite(u).all(), 'Missing displacement samples'
            displacement.append(u)
        all_u=np.array(displacement)
        energy=next(r for r in step.historyRegions.values() if 'ALLDMD' in r.historyOutputs)
        ball_region=next(r for r in step.historyRegions.values()
                         if r.name.endswith('.%d'%ball) and 'V3' in r.historyOutputs)
        target.parent.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(str(target),times=np.array([f.frameValue for f in step.frames]),
            top_xyz=np.array([coords[n] for n in top]),top_u=all_u[:,[rows[n] for n in top]],
            section_xyz=np.array([coords[n] for n in section]),section_u=all_u[:,[rows[n] for n in section]],
            section_plane=(np.array(section,dtype=int)-1)//len(top),
            ball_xyz=np.array(coords[ball]),ball_u=all_u[:,rows[ball]],
            damage_history=np.array(energy.historyOutputs['ALLDMD'].data),
            ball_velocity=np.array(ball_region.historyOutputs['V3'].data))
        target.with_suffix('.json').write_text(json.dumps(dict(source=str(source.resolve()),
            step='IMPACT',frames=len(step.frames),end_us=step.frames[-1].frameValue*1e6,
            section_y_mm=50,geometry_scale=1,ball_radius_mm=4,
            top_nodes=len(top),section_nodes=len(section),interpolation='none'),indent=2))
        print('EXPORTED',len(step.frames),'frames to',target)
    finally:
        odb.close()


if __name__=='__main__':
    main()
