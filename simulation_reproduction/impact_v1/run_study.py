"""Run reproducible truncation, time-step and one-factor sensitivity studies."""
from pathlib import Path
import copy
import argparse
import hashlib
import json
import numpy as np
from solve_impact import run, basis, build

ROOT=Path(__file__).resolve().parent


def compare(a,b):
    a=np.column_stack([np.interp(b[:,0],a[:,0],a[:,j]) for j in range(a.shape[1])])
    ids=[1,2,6,7,8,9]
    return dict(zip(['force','impact_w','S1_strain','S2_strain','S3_strain','S4_strain'],
                    (np.linalg.norm(a[:,ids]-b[:,ids],axis=0)/np.maximum(np.linalg.norm(b[:,ids],axis=0),1e-30)).tolist()))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=ROOT/'study')
    parser.add_argument('--orders',type=int,nargs='+',default=[6,10,14,18,22,30,38,46])
    args=parser.parse_args()
    cfg=json.loads((ROOT/'simulation_config.json').read_text(encoding='utf8'))
    output=args.out
    output.mkdir(exist_ok=False)
    records={}; arrays={}; checks={}
    for order in args.orders:
        tag=f'order{order}'
        data,s,_=run(cfg,order=order,dt=2.5e-7 if order<=22 else 6.25e-8,out=output/tag)
        arrays[tag]=data; records[tag]=s
        print(tag,s['peak_contact_force_N'],s['patch_peak_strain_trace'][0],flush=True)
    for a,b in zip(args.orders[:-1],args.orders[1:]):
        checks[f'order{a}_to_{b}_relative_L2']=compare(arrays[f'order{a}'],arrays[f'order{b}'])
    if 22 not in args.orders: raise ValueError('Include order 22 for paired time-step and sensitivity checks')
    data,s,_=run(cfg,order=22,dt=1.25e-7,out=output/'halfdt')
    records['halfdt']=s
    checks['halfdt_relative_L2']=compare(arrays['order22'],data)
    finest=max(args.orders)
    fine_dt=2.5e-7 if finest<=22 else 6.25e-8
    data,s,_=run(cfg,order=finest,dt=fine_dt/2,out=output/'finest_halfdt')
    records['finest_halfdt']=s
    checks['finest_halfdt_relative_L2']=compare(arrays[f'order{finest}'],data)
    edge=basis([0.,1.],22,.46)
    checks['clamped_basis_max_edge_w_slope']=float(max(abs(edge[0]).max(),abs(edge[1]).max()))
    # Independent textbook isotropic square clamped-plate frequency parameter:
    # omega*a^2*sqrt(rho*h/D) ~= 35.99. Use an isotropic Q exactly.
    iso=copy.deepcopy(cfg); iso['outer_size_m']=[.5,.5]; iso['clear_span_m']=[.46,.46]
    iso['substitute_material']={'E1_Pa':70e9,'E2_Pa':70e9,'G12_Pa':70e9/2.6,'nu12':.3}
    eig,*_=build(iso,10)
    diso=70e9*iso['thickness_m']**3/(12*(1-.3**2))
    checks['isotropic_square_frequency_parameter']=float(np.sqrt(eig[0])*.46**2*np.sqrt(iso['rho_kg_m3']*iso['thickness_m']/diso))
    assert abs(checks['isotropic_square_frequency_parameter']-35.99)<.03
    assert checks['clamped_basis_max_edge_w_slope']==0
    assert max(checks['halfdt_relative_L2'].values())<.01
    assert max(checks['finest_halfdt_relative_L2'].values())<.01
    assert all(v['energy_max_relative_error']<.001 for v in records.values())
    for tag,change in [
        ('stiffness075',{'stiffness_scale':.75}),('stiffness125',{'stiffness_scale':1.25}),
        ('clamp10mm',{'clamp_width_m':.01,'clear_span_m':[.48,.38]}),
        ('clamp30mm',{'clamp_width_m':.03,'clear_span_m':[.44,.34]}),
        ('contact050',{'contact_scale':.5}),('contact200',{'contact_scale':2.}),
        ('offcentre',{'impact_xy_m':[.2,.15]})]:
        c=copy.deepcopy(cfg); c.update(change)
        _,s,_=run(c,order=22,out=output/tag)
        records[tag]=s
        print(tag,s['peak_contact_force_N'],flush=True)
    results={'summaries':records,'checks':checks,
             'scope':'4 ms mechanical proxy, raw unfiltered substrate strain; not sensor voltage or validated damage simulation'}
    (output/'study_metrics.json').write_text(json.dumps(results,indent=2),encoding='utf8')
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob('*')) if p.is_file() and '__pycache__' not in str(p) and p.name!='manifest.json'}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps(checks,indent=2),flush=True)


if __name__=='__main__': main()
