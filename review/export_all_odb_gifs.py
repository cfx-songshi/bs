"""Read-only ODB export for the GIF catalogue; run with abaqus python.

Writes one compact NPZ/JSON per available step, never reads an active job.
Frames and nodes may be subsampled, with no invented/interpolated solution fields.
"""
import hashlib
import json
import re
import sys
import traceback
from pathlib import Path
import numpy as np
from odbAccess import openOdb

ROOT=Path('D:/bs_thesis')
OUT=Path(sys.argv[1])
DATA=OUT/'_data'
DATA.mkdir(parents=True,exist_ok=True)


def save_json(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')


def classify(path,step,kind,complete):
    name=path.stem
    text=str(path).replace('\\','/')
    if not complete:return '90_incomplete','未完成，仅供诊断；不得作为完整结果'
    if '/repeat_validation' in text or '/restart_probe' in text or '/damping_switch/' in text:
        return '50_workflow_tests','小模型/流程验证，不代表正式板损伤结论'
    if name in ('imp_lo','imp_mid','imp_hi') and step=='IMPACT':
        return '01_current_impact','显式黏聚刚度 2.37e13 下的单次标定；应力场未收敛、材料为替代参数'
    if name=='acc_n01':return '01_current_impact','正式累积序列第1次；尚不能代表三次累积完成'
    if name in ('wav_base','wav_d03_r08','wav_d08_r31'):
        return '02_current_wave','修正半径后的导波；机械位移而非电压；0.8 mm 档仍有4/5受损界面映射差异'
    if 'guided_wave' in text or 'D:/abaqus_runs' in text:
        note='Abaqus 独立求解器对照；按交接文档区分线源、点源和网格'
        if 'c3d8r' in name:note+='；减缩积分/沙漏对照，不得当作已验证推荐结果'
        return '30_abaqus_validation',note
    if kind=='probe':return '40_material_probes','材料/关键词能力探针，不等于实物材料标定'
    return '20_historical','历史参数/网格/精度对照；不得替代交接文档的最终标定；同作业冲击后的 WAVE 含残余振动'


def export(path):
    status={'source':str(path),'type':'odb','outputs':[]}
    archived=any(p.startswith('interrupted_') for p in path.parts)
    if path.with_suffix('.lck').exists() and not archived:
        status.update(status='skipped_active',reason='lock exists: active or unverified job')
        return status
    sta=path.with_suffix('.sta')
    complete=sta.exists() and 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in sta.read_text(errors='replace')
    odb=openOdb(str(path),readOnly=True)
    try:
        if not len(odb.rootAssembly.instances):
            status.update(status='no_data',reason='no instances');return status
        if len(odb.rootAssembly.instances)!=1:
            raise RuntimeError('multiple instances require explicit mapping; not silently merged')
        inst=list(odb.rootAssembly.instances.values())[0]
        xyz={n.label:tuple(n.coordinates) for n in inst.nodes}
        if not xyz:
            status.update(status='no_data',reason='no nodes');return status
        inp=path.with_suffix('.inp')
        text=inp.read_text(errors='replace') if inp.exists() else ''
        match=re.search(r'\*Rigid Body,\s*ref node=(\d+)',text,re.I)
        ball=int(match.group(1)) if match else None
        if ball is None:
            for name,ns in inst.nodeSets.items():
                if name=='BALLREF' and len(ns.nodes)==1:ball=ns.nodes[0].label
        if ball:
            plate_ids=set(n for e in inst.elements if e.type.startswith(('C3D','SC8')) for n in e.connectivity)
            if not plate_ids:raise RuntimeError('no solid plate for ball model')
        else:plate_ids=set(xyz)
        pxyz=np.array([xyz[n] for n in sorted(plate_ids)])
        bounds=np.ptp(pxyz,axis=0)
        top_z=pxyz[:,2].max()
        top=sorted(n for n in plate_ids if abs(xyz[n][2]-top_z)<max(1e-9,bounds[2]*1e-6))
        full_top=len(top)
        xx=np.unique([xyz[n][0] for n in top]); yy=np.unique([xyz[n][1] for n in top])
        # Preserve a structured grid and the midpoint, capped at about 130^2 nodes.
        xkeep=set(xx[np.unique(np.r_[np.arange(0,len(xx),max(1,int(np.ceil(len(xx)/130)))),len(xx)-1,len(xx)//2])])
        ykeep=set(yy[np.unique(np.r_[np.arange(0,len(yy),max(1,int(np.ceil(len(yy)/130)))),len(yy)-1,len(yy)//2])])
        top=[n for n in top if xyz[n][0] in xkeep and xyz[n][1] in ykeep]
        ycentre=float(yy[np.argmin(abs(yy-(yy.min()+yy.max())/2))])
        sec=sorted(n for n in plate_ids if abs(xyz[n][1]-ycentre)<1e-9)
        kind='impact' if ball else ('probe' if len(plate_ids)<100 else ('line' if bounds[0]>5*max(bounds[1],1e-15) else 'plan'))
        if kind=='probe':top=sorted(plate_ids);sec=top
        wanted=np.array(sorted(set(top+sec+([ball] if ball else []))),dtype=int)
        lookup=np.full(max(xyz)+1,-1,dtype=int);lookup[wanted]=np.arange(len(wanted))
        rows={int(n):i for i,n in enumerate(wanted)}
        edges=[]
        if kind=='probe':
            pairs=((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7))
            for e in inst.elements:
                c=list(e.connectivity)
                if len(c)==8:
                    edges.extend((rows[c[a]],rows[c[b]]) for a,b in pairs if c[a] in rows and c[b] in rows)
        for stepname,step in odb.steps.items():
            if len(step.frames)<2:
                status['outputs'].append({'step':stepname,'status':'no_animation','reason':'fewer than two field frames'});continue
            uid=hashlib.sha1((str(path)+'#'+stepname).encode()).hexdigest()[:8]
            key=re.sub('[^A-Za-z0-9_-]','_',path.stem+'__'+stepname)+'__'+uid
            dest=DATA/(key+'.npz')
            if dest.exists() and dest.with_suffix('.json').exists():
                status['outputs'].append(json.loads(dest.with_suffix('.json').read_text(encoding='utf-8')));continue
            indices=np.unique(np.linspace(0,len(step.frames)-1,min(51,len(step.frames))).round().astype(int))
            field='U' if 'U' in step.frames[-1].fieldOutputs else ('V' if 'V' in step.frames[-1].fieldOutputs else None)
            if not field:
                status['outputs'].append({'step':stepname,'status':'no_animation','reason':'no U or V nodal field'});continue
            values=[];times=[]
            for index in indices:
                frame=step.frames[int(index)]
                if field not in frame.fieldOutputs:continue
                data=np.full((len(wanted),3),np.nan)
                for block in frame.fieldOutputs[field].bulkDataBlocks:
                    labels=np.asarray(block.nodeLabels,dtype=int)
                    loc=lookup[labels];valid=loc>=0
                    arr=np.asarray(block.data)
                    data[loc[valid],:arr.shape[1]]=arr[valid]
                    if arr.shape[1]<3:data[loc[valid],arr.shape[1]:]=0
                if not np.isfinite(data).all():raise RuntimeError('missing requested nodal values')
                times.append(frame.frameValue);values.append(data)
            if len(times)<2:continue
            values=np.array(values)
            histories={}
            for region in step.historyRegions.values():
                for name,out in region.historyOutputs.items():
                    if name in ('ALLDMD','ALLKE','ALLIE','ALLAE','ETOTAL','ALLVD'):
                        histories[name]=np.array(out.data)
            group,caveat=classify(path,stepname,kind,complete)
            if archived:caveat+='；中断归档，终止原因未定'
            info=dict(key=key,source=str(path),step=stepname,kind=kind,group=group,caveat=caveat,
                      complete=complete,status='exported',frames=len(times),source_frames=len(step.frames),
                      start_s=times[0],end_s=times[-1],field=field,full_top_nodes=full_top,
                      displayed_top_nodes=len(top),section_y_m=ycentre,geometry_scale=1,
                      sampling='selected saved frames and nodes; no solution interpolation',
                      scalar_units='mm' if field=='U' else 'm/s',source_mtime=path.stat().st_mtime,
                      data=str(dest),ball_node=ball)
            np.savez_compressed(str(dest),times=np.array(times),xyz=np.array([xyz[n] for n in wanted]),values=values,
                top_rows=np.array([rows[n] for n in top]),section_rows=np.array([rows[n] for n in sec]),
                section_planes=(np.array(sec)-1)//full_top if ball else np.zeros(len(sec),dtype=int),
                ball_row=np.array(rows[ball] if ball else -1),edges=np.array(edges,dtype=int).reshape(-1,2),
                **{'hist_'+k:v for k,v in histories.items()})
            save_json(dest.with_suffix('.json'),info);status['outputs'].append(info)
            print('EXPORTED',key,len(times),flush=True)
        status['status']='processed'
        return status
    finally:odb.close()


sources=sorted(list((ROOT/'simulation_reproduction').rglob('*.odb'))+list(Path('D:/abaqus_runs').rglob('*.odb')))
inventory=[]
for path in sources:
    try:result=export(path)
    except Exception as e:result=dict(source=str(path),status='error',reason=str(e),traceback=traceback.format_exc())
    inventory.append(result)
    save_json(OUT/'odb_inventory.json',inventory)
print('EXPORT_FINISHED',len(inventory),flush=True)
