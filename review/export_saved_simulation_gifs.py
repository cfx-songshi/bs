"""Convert existing NumPy/CSV simulation records into the catalogue data schema.

No new simulations are run. Static ML tensors have no physical time axis and are
inventoried explicitly rather than made into fictitious propagation movies.
"""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path('D:/bs_thesis');OUT=Path(sys.argv[1]);DATA=OUT/'_data';DATA.mkdir(parents=True,exist_ok=True)
inventory=[]


def pack(source,kind,group,caveat,times,arrays,tag='',extra=None):
    key=source.parent.name+'__'+source.stem+('_'+tag if tag else '')+'__'+hashlib.sha1((str(source)+tag).encode()).hexdigest()[:8]
    dest=DATA/(key+'.npz');times=np.asarray(times)
    ix=np.unique(np.linspace(0,len(times)-1,min(51,len(times))).round().astype(int))
    selected={}
    for k,v in arrays.items():
        selected[k]=np.asarray(v)[ix] if k in ('values','traces') else np.asarray(v)
    if 'traces' in arrays:selected.update(trace_times=times,traces_full=np.asarray(arrays['traces']))
    np.savez_compressed(dest,times=times[ix],**selected)
    meta=dict(key=key,source=str(source),kind=kind,group=group,caveat=caveat,complete=True,
              status='exported',data=str(dest),step=tag or 'saved data',frames=len(ix),source_frames=len(times),
              start_s=float(times[0]),end_s=float(times[-1]),field='U',geometry_scale=1,
              sampling='saved samples, uniformly selected indices, no temporal interpolation',**(extra or {}))
    dest.with_suffix('.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    return meta


def trace(source,times,traces,names,group,caveat,tag=''):
    return pack(source,'traces',group,caveat,times,dict(traces=np.asarray(traces)),tag,dict(trace_names=names))


def fieldpack(source,times,frames,x,y,group,caveat,quantity='U3'):
    frames=np.asarray(frames)
    if frames.ndim==2 and frames.shape[1]==len(x):
        xyz=np.c_[x,np.zeros(len(x)),np.zeros(len(x))];flat=frames;kind='line'
    else:
        frames=frames.reshape(len(times),len(y),len(x))
        ix=np.unique(np.r_[np.arange(0,len(x),max(1,int(np.ceil(len(x)/130)))),len(x)-1])
        iy=np.unique(np.r_[np.arange(0,len(y),max(1,int(np.ceil(len(y)/130)))),len(y)-1])
        xx,yy=np.meshgrid(np.asarray(x)[ix],np.asarray(y)[iy]);xyz=np.c_[xx.ravel(),yy.ravel(),np.zeros(xx.size)]
        flat=frames[:,iy][:,:,ix].reshape(len(times),-1);kind='plan'
    values=np.zeros((len(times),len(xyz),3));values[:,:,2]=flat
    return pack(source,kind,group,caveat,times,dict(xyz=xyz,values=values,top_rows=np.arange(len(xyz)),
         section_rows=np.arange(len(xyz)),section_planes=np.zeros(len(xyz)),ball_row=-1,edges=np.empty((0,2),dtype=int)),
         extra=dict(component_label=quantity))


for path in sorted((ROOT/'simulation_reproduction').rglob('*.npz')):
    if 'abaqus' in path.parts:continue # derived exports/ODB data handled in the ODB catalogue
    try:
        z=np.load(path,allow_pickle=False);keys=set(z.files);output=[]
        if {'frames','frame_t','x'}<=keys:
            group='30_abaqus_validation' if path.name.startswith('abaqus_') else '60_custom_wave'
            caveat='已保存波场；相速度/群速度与网格验收范围须查交接文档；未做实物验证'
            if 'c3d8r' in path.name:caveat+='；沙漏对照，不作为推荐解'
            output.append(fieldpack(path,z['frame_t'],z['frames'],z['x'],z['y'] if 'y' in keys else [0.],group,caveat))
        elif {'w','t','x','y'}<=keys:
            output.append(fieldpack(path,z['t'],z['w'],z['x'],z['y'],'61_thin_plate',
                '薄板 Rayleigh–Ritz 代理；w 向下为正；局部峰值力/接触应力不可信，非三维损伤预测','w（向下为正）'))
        elif {'nodal_force','force','time'}<=keys:
            output.append(trace(path,z['time'],np.c_[z['force'],np.max(z['nodal_force'],axis=1)],
                ['总接触力（N）','最大节点接触力（N）'],'62_custom_3d','局部三维子模型的接触时程；无损伤演化'))
        elif {'displacement_m','time_s'}<=keys:
            ids=[5,6,9,10];output.append(trace(path,z['time_s'],z['displacement_m'][:,ids]*1e6,
                ['S%d 位移（µm）'%(i+1) for i in ids],'70_surrogate','早期板响应代理/合成演示，不能冒充当前 Abaqus 求解结果'))
        elif {'scores','margin','time_s'}<=keys:
            output.append(trace(path,z['time_s'],np.c_[np.max(z['scores'],axis=1),z['margin'],z['alarm'],z['predicted_sensor']],
                ['最大异常评分','判定裕量','报警标记','预测传感器编号'],'70_surrogate','早期故障检测数值演示；无独立实测验证集'))
        elif {'cycle_time_s','pressure_kPa','resistance_fraction'}<=keys:
            output.append(trace(path,z['cycle_time_s'],np.c_[z['pressure_kPa'],z['resistance_fraction']],
                ['压力（kPa）','电阻相对变化'],'70_surrogate','接头响应替代模型；不是实测曲线；静态强度曲线未伪造时间轴'))
        elif 'gear_example' in path.name:
            for speed in sorted(keys-{'time_s'},key=int):
                output.append(trace(path,z['time_s'],z[speed].T,['通道%d（源文件单位）'%(i+1) for i in range(z[speed].shape[0])],
                    '70_surrogate','齿轮箱合成信号样例，不是实测；速度标签取自保存文件',speed))
        elif {'waveforms','fs_hz'}<=keys:
            w=z['waveforms'][0];output.append(trace(path,np.arange(len(w))/float(z['fs_hz']),w[:,None],['第1条样本（源文件单位）'],
                '70_surrogate','AE 合成数据集第1条示例；数据集样本不能混称独立有限元算例','sample0'))
        else:
            inventory.append(dict(source=str(path),status='not_temporal_simulation',reason='静态训练/迁移张量或无已定义物理时间轴，不补造过程动画',keys=sorted(keys)));continue
        inventory.append(dict(source=str(path),status='exported',outputs=output))
    except Exception as e:inventory.append(dict(source=str(path),status='error',reason=str(e)))

for path in sorted((ROOT/'simulation_reproduction').rglob('*.csv')):
    if 'abaqus' in path.parts:continue
    try:
        z=np.genfromtxt(path,delimiter=',',names=True,encoding='utf-8-sig');cols=z.dtype.names
        if 'time_s' not in cols:continue
        t=np.unique(z['time_s']);out=[]
        if path.name=='sensors.csv':
            series=[];names=[]
            for sensor in np.unique(z['sensor_id'])[:4]:
                v=z[z['sensor_id']==sensor]
                assert np.array_equal(v['time_s'],t)
                series.append(v['eps_impact_dir']*1e6);names.append('S%d 沿冲击方向应变（µε）'%sensor)
            out.append(trace(path,t,np.array(series).T,names,'62_custom_3d','自研三维远场传感器机械应变；不是 PZT 电压；小幅通道仍须关注网格敏感性'))
        elif path.name=='through_thickness.csv':
            zs=np.unique(z['z_m']);sel=zs[np.unique(np.linspace(0,len(zs)-1,min(4,len(zs))).round().astype(int))]
            a=[]
            for h in sel:
                v=z[z['z_m']==h];assert np.array_equal(v['time_s'],t);a.append(v['uz']*1e6)
            out.append(trace(path,t,np.array(a).T,['z=%.3f mm 的 uz（µm）'%(h*1e3) for h in sel],
                '62_custom_3d','仅已保存厚度方向测点的位移时程，不能重建未保存的全场运动'))
        else:
            columns=[k for k in ('contact_force_N','impact_w_m','centre_deflection_m','ball_travel_m','energy_J') if k in cols][:4]
            vals=[];names=[]
            for k in columns:
                scale=1e6 if k.endswith('_m') else 1
                vals.append(z[k]*scale);names.append(k.replace('_m','（µm）') if scale==1e6 else k)
            group='61_thin_plate' if 'study_final' in path.parts else '62_custom_3d'
            out.append(trace(path,z['time_s'],np.array(vals).T,names,group,'已保存响应时程；局部量的可信范围按各模型验收记录，不能跨模型当作同一算例'))
        inventory.append(dict(source=str(path),status='exported',outputs=out))
    except Exception as e:inventory.append(dict(source=str(path),status='error',reason=str(e)))
(OUT/'saved_data_inventory.json').write_text(json.dumps(inventory,indent=2,ensure_ascii=False),encoding='utf-8')
print('saved datasets:',len(inventory),'errors:',sum(x['status']=='error' for x in inventory))
