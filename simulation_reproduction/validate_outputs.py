"""Validate saved experiment provenance, splits, checkpoints and report assets."""
import sys,json,hashlib,os
from pathlib import Path
root=Path(__file__).resolve().parent;out=root/'results'
os.environ['MPLCONFIGDIR']=str(out/'.mplconfig')
sys.path.insert(0,sys.argv[1] if len(sys.argv)>1 else str(root/'vendor'))
import numpy as np
import torch
from transfer import Network
torch.set_num_threads(2)
checks=[]
def check(name,value):
    assert value,name
    checks.append({'check':name,'passed':True})
for f in out.glob('*.json'):
    json.loads(f.read_text(encoding='utf8'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
checks.append({'check':'All JSON files valid, no NaN/Infinity','passed':True})
for seed in range(3):
    d=np.load(out/f'transfer_dataset_seed{seed}.npz')
    check(f'seed{seed}: data dimensions',d['source'].shape==(200,1,4,300) and d['target_pool'].shape==(144,1,4,300) and d['test'].shape==(80,1,4,300))
    sets=[set(d[k].tolist()) for k in ['source_event_ids','target_event_ids','test_event_ids']]
    check(f'seed{seed}: disjoint event IDs',all(not sets[i]&sets[j] for i in range(3) for j in range(i)))
    check(f'seed{seed}: finite signals',all(np.isfinite(d[k]).all() for k in ['source','target_pool','test']))
trials=json.loads((out/'transfer_trials.json').read_text(encoding='utf8'))
d=np.load(out/'transfer_dataset_seed0.npz')
for method in ['target_only','pooled','DANN']:
    model=Network();model.load_state_dict(torch.load(out/f'cnn_{method}_seed0_k8.pt',map_location='cpu',weights_only=True));model.eval()
    with torch.no_grad():pred=model(torch.from_numpy(d['test']))[0].argmax(1).numpy()
    expected=next(r for r in trials if r['seed']==0 and r['k_per_class']==8 and r['method']==method)
    check(method+': saved checkpoint reproduces reported accuracy',abs(np.mean(pred==d['test_y'])-expected['accuracy'])<1e-12)
cases=json.loads((out/'hsp_1620_planned_cases.json').read_text(encoding='utf8'))
check('Exactly 1620 planned FE cases, none falsely marked solved',len(cases)==1620 and all(c['status']=='planned_not_solved' for c in cases))
locations={c['location_id']:c['xy_m'] for c in cases};pts=np.array(list(locations.values()));dist=np.linalg.norm(pts[:,None]-pts[None],axis=2);np.fill_diagonal(dist,np.inf)
check('90 FE locations, all distinct by at least 10 mm',len(pts)==90 and dist.min()>=.01)
ae=np.load(out/'ae_dataset.npz')
check('AE saved baseline contains 25 events x 4 channels',ae['waveforms'].shape==(100,2048) and ae['event_metadata'].shape==(100,3))
doc=(root/'复现实验报告.html').read_text(encoding='utf8')
check('Report has embedded figures, no unfilled result placeholders','{{' not in doc and doc.count('data:image/png;base64,')==11)
(out/'validation.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf8')
print('PASSED',len(checks),'saved-output validations')
