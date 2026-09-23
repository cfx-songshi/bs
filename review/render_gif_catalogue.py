"""Render every exported temporal dataset and build a portable PPT asset index."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import html
import hashlib
import json
import sys
import traceback
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.collections import LineCollection
from PIL import Image

OUT=Path(sys.argv[1]);DATA=OUT/'_data'
plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':9,'axes.unicode_minus':False})
NAMES={'01_current_impact':'当前有效 · 冲击','02_current_wave':'当前有效 · 导波',
 '20_historical':'历史参数对照','30_abaqus_validation':'Abaqus 独立对照','40_material_probes':'材料能力探针',
 '50_workflow_tests':'流程验证','60_custom_wave':'自研导波','61_thin_plate':'薄板冲击与敏感性',
 '62_custom_3d':'自研三维冲击','70_surrogate':'早期代理/合成数据','90_incomplete':'未完成/中断'}


def gif(images,path):
    strip=Image.new('RGB',(images[0].width,len(images[::5])*80))
    for j,im in enumerate(images[::5]):strip.paste(im.resize((im.width,80)),(0,j*80))
    palette=strip.quantize(colors=192)
    frames=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in images]
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=150,loop=0,disposal=2,optimize=False)
    with Image.open(path) as check:
        assert check.n_frames==len(images),(check.n_frames,len(images))
        return dict(gif_frames=check.n_frames,width=check.width,height=check.height,duration_ms=check.info['duration'])


def render(meta):
    path=Path(meta['data']);d=np.load(path)
    dest=OUT/meta['group']/(meta['key']+'.gif');dest.parent.mkdir(exist_ok=True)
    receipt=dest.with_suffix('.json')
    if dest.exists() and receipt.exists():
        prior=json.loads(receipt.read_text(encoding='utf-8'))
        if prior.get('renderer_version')==(3 if meta['kind']=='traces' else 2):return prior
    times=d['times'];tf=1. if times[-1]-times[0]>.01 else 1e6;tu='s' if tf==1 else 'µs';tt=times*tf;tl='时间（'+tu+'）'
    trace_only=meta['kind']=='traces'
    if not trace_only:
        xyz=d['xyz'];val=d['values'];top=d['top_rows'];sec=d['section_rows']
        comp=int(np.argmax(np.max(abs(val),axis=(0,1)))) if meta['kind']=='probe' else 2
        scalar=val[:,:,comp];maximum=float(np.max(abs(scalar[:,top])))
        multiplier,units=((1e9,'nm') if maximum<1e-6 else (1e6,'µm') if maximum<1e-4 else (1e3,'mm')) if meta['field']=='U' else (1.,'m/s')
        cl=meta.get('component_label',meta['field']+str(comp+1));sc=scalar*multiplier;bound=max(float(np.max(abs(sc[:,top]))),1e-15)
        chosen=int(top[np.argmax(np.max(abs(sc[:,top]),axis=0))])
    fig=plt.figure(figsize=(11.6,7.1),dpi=100,facecolor='#f4f7fb')
    gs=fig.add_gridspec(2,2,left=.08,right=.94,bottom=.12,top=.80,hspace=.48,wspace=.32,height_ratios=[2.1,1])
    a,b,c,e=[fig.add_subplot(gs[i,j]) for i,j in ((0,0),(0,1),(1,0),(1,1))]
    fig.text(.065,.95,NAMES.get(meta['group'],meta['group']),fontsize=19,weight='bold',color='#16324c')
    title=Path(meta['source']).stem+' / '+meta.get('step','time series')
    fig.text(.065,.904,title[:98],fontsize=12,color='#465a70')
    stamp=fig.text(.065,.857,'',fontsize=11,color='#007c88',weight='bold')
    foot=meta['caveat']
    fig.text(.065,.054,foot[:88],fontsize=8,color='#795449')
    fig.text(.065,.025,'原始保存数据慢放；无补造帧；各算例色标固定但跨算例可不同；机械响应不是 PZT 电压。',fontsize=8,color='#536579')
    updaters=[]
    cursors=[]
    if trace_only:
        for ax,j in zip((a,b,c,e),range(4)):
            names=meta['trace_names'];values=d['traces_full'] if 'traces_full' in d else d['traces'];trace_tt=d['trace_times']*tf if 'trace_times' in d else tt
            if j>=values.shape[1]:ax.set_visible(False);continue
            ax.plot(trace_tt,values[:,j],lw=1.5,color=('#007c88' if j%2==0 else '#ac5151'))
            ax.set(xlabel=tl,ylabel=names[j],title=names[j],xlim=(tt[0],tt[-1]))
            cursors.append(ax.axvline(tt[0],color='#e88035',lw=1))
    else:
        kind=meta['kind']
        if kind in ('impact','probe'):
            projection=(0,2) if np.ptp(xyz[:,2])>=np.ptp(xyz[:,1]) or kind=='impact' else (0,1)
            geom=xyz[None,:,:]+(val if meta['field']=='U' else val*0)
            geom=geom*1e3
            if kind=='impact':
                planes=d['section_planes'];groups=[sec[planes==p] for p in sorted(set(planes))]
                groups=[g[np.argsort(xyz[g,0])] for g in groups]
                curves=[a.plot([],[],color='#426d87',lw=.8)[0] for g in groups]
                br=int(d['ball_row']);radius=4.;sphere=Circle((0,0),radius,fc='#a7b1bf',ec='#374a61',lw=1.5);a.add_patch(sphere)
                cx=xyz[br,0]*1e3
                lo=float(np.min(geom[:,sec,2]));hi=float(np.max(geom[:,br,2]))+radius
                a.set(xlim=(cx-15,cx+15),ylim=(lo-1,hi+1),xlabel='x（mm）',ylabel='z（mm）',title='中心截面，变形 ×1；球为圆形显示')
                a.set_aspect('equal')
                def update_geom(i):
                    for line,g in zip(curves,groups):line.set_data(geom[i,g,0],geom[i,g,2])
                    sphere.center=(geom[i,br,0],geom[i,br,2])
                updaters.append(update_geom)
            else:
                edges=d['edges'];pts=geom[:,:,[*projection]]
                lc=LineCollection([],colors='#346f8e',linewidths=1.4);a.add_collection(lc)
                dots=a.scatter([],[],s=18,c='#de8641')
                lo=pts.min(axis=(0,1));hi=pts.max(axis=(0,1));pad=np.maximum((hi-lo)*.18,1e-5)
                a.set(xlim=(lo[0]-pad[0],hi[0]+pad[0]),ylim=(lo[1]-pad[1],hi[1]+pad[1]),
                      xlabel='xyz'[projection[0]]+'（mm）',ylabel='xyz'[projection[1]]+'（mm）',title='实际节点/单元边，变形 ×1')
                a.set_aspect('equal')
                def update_probe(i):
                    if len(edges):lc.set_segments(pts[i,edges])
                    dots.set_offsets(pts[i])
                updaters.append(update_probe)
        else:
            # For waves the undeformed coordinates are intentional; nanometre motion
            # is represented by a labelled scalar, not an invented geometric scale.
            a.set_title('顶面位移场，未变形坐标')
        if kind in ('impact','plan'):
            ax=b if kind=='impact' else a
            x=xyz[top,0]*1e3;y=xyz[top,1]*1e3
            xs=np.unique(x);ys=np.unique(y)
            if len(xs)*len(ys)==len(top):
                ix=np.searchsorted(xs,x);iy=np.searchsorted(ys,y)
                maps=np.zeros((len(tt),len(ys),len(xs)));maps[:,iy,ix]=sc[:,top]
                artist=ax.pcolormesh(xs,ys,maps[0],shading='nearest',cmap='RdBu_r',vmin=-bound,vmax=bound)
                updaters.append(lambda i:artist.set_array(maps[i].ravel()))
            else:
                artist=ax.scatter(x,y,c=sc[0,top],s=8,cmap='RdBu_r',vmin=-bound,vmax=bound)
                updaters.append(lambda i:artist.set_array(sc[i,top]))
            ax.set(xlabel='x（mm）',ylabel='y（mm）',title='%s 顶面场（%s）'%(cl,units));ax.set_aspect('equal')
            fig.colorbar(artist,ax=ax,pad=.03,fraction=.05)
            if kind=='impact':
                cx=xyz[int(d['ball_row']),0]*1e3;cy=xyz[int(d['ball_row']),1]*1e3
                ax.set(xlim=(cx-15,cx+15),ylim=(cy-15,cy+15))
        if kind in ('line','plan'):
            target=a if kind=='line' else b
            mid=(xyz[top,1].min()+xyz[top,1].max())/2
            y=np.unique(xyz[top,1]);y0=y[np.argmin(abs(y-mid))]
            lineids=top[abs(xyz[top,1]-y0)<1e-10];lineids=lineids[np.argsort(xyz[lineids,0])]
            line,=target.plot(xyz[lineids,0]*1e3,sc[0,lineids],color='#087c91',lw=1.5)
            target.set(ylim=(-bound*1.08,bound*1.08),xlabel='x（mm）',ylabel='%s（%s）'%(cl,units),title='中心线波形（选取保存节点）')
            updaters.append(lambda i:line.set_ydata(sc[i,lineids]))
            if kind=='line':
                artist=b.pcolormesh(xyz[lineids,0]*1e3,tt,sc[:,lineids],shading='nearest',cmap='RdBu_r',vmin=-bound,vmax=bound)
                b.set(xlabel='x（mm）',ylabel=tl,title='保存帧的时空图（实际保存时刻）')
                h=b.axhline(tt[0],color='#e88035');updaters.append(lambda i:h.set_ydata([tt[i],tt[i]]))
        if kind=='probe':
            line,=b.plot(np.arange(len(top)),sc[0,top],'o-',ms=3,color='#087c91')
            b.set(xlabel='显示节点序号',ylabel='%s（%s）'%(cl,units),ylim=(-bound*1.08,bound*1.08),title='位移/速度分量（非材料应变）')
            updaters.append(lambda i:line.set_ydata(sc[i,top]))
        c.plot(tt,sc[:,chosen],color='#087c91',lw=1.5)
        c.set(xlabel=tl,ylabel='%s（%s）'%(cl,units),title='显示节点中峰值响应点的时程',xlim=(tt[0],tt[-1]))
        cursors.append(c.axvline(tt[0],color='#e88035',lw=1))
        hk=next((k for k in ('hist_ALLDMD','hist_ALLKE','hist_ALLIE') if k in d and np.max(abs(d[k][:,1]))>0),None)
        if hk:
            hist=d[hk];e.plot(hist[:,0]*tf,hist[:,1]*1e3,color='#a95151',lw=1.5)
            e.set(xlabel=tl,ylabel=hk[5:]+'（mJ）',title='ODB 全局能量历史',xlim=(tt[0],tt[-1]))
        else:
            e.plot(tt,np.max(abs(sc[:,top]),axis=1),color='#a95151')
            e.set(xlabel=tl,ylabel='max |分量|（%s）'%units,title='已显示节点的最大响应',xlim=(tt[0],tt[-1]))
        cursors.append(e.axvline(tt[0],color='#e88035',lw=1))
    for ax in (a,b,c,e):
        ax.set_facecolor('white');ax.spines[['top','right']].set_visible(False)
    for ax in (c,e):ax.grid(alpha=.16)
    images=[]
    for i,time_us in enumerate(tt):
        for update in updaters:update(i)
        for cur in cursors:cur.set_xdata([time_us,time_us])
        stamp.set_text('t = %.3f %s    |    保存帧 %d / %d    |    %s'%(time_us,tu,i+1,len(tt),'未完成时段' if not meta['complete'] else '已完成算例'))
        fig.canvas.draw();images.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[:,:,:3].copy()))
    proof=gif(images,dest)
    poster=len(images)//2 if trace_only else int(np.argmax(np.max(abs(sc[:,top]),axis=1)))
    images[poster].save(dest.with_suffix('.png'))
    plt.close(fig)
    item=dict(meta,renderer_version=(3 if trace_only else 2),gif=str(dest.resolve()),poster=str(dest.with_suffix('.png').resolve()),**proof)
    if not trace_only:item.update(display_units=units,color_half_range=bound)
    receipt.write_text(json.dumps(item,indent=2,ensure_ascii=False),encoding='utf-8')
    return item


shard=int(sys.argv[2]) if len(sys.argv)>2 else None
suffix='' if shard is None else '_'+str(shard)
results=[];errors=[]
for path in sorted(DATA.glob('*.json')):
    meta=json.loads(path.read_text(encoding='utf-8'))
    if shard is not None and int(hashlib.sha1(meta['key'].encode()).hexdigest(),16)%4!=shard:continue
    try:
        item=render(meta);results.append(item);print('GIF',meta['key'],flush=True)
    except Exception as exc:
        errors.append(dict(data=str(path),error=str(exc),traceback=traceback.format_exc()));print('ERROR',path,exc,flush=True)
    (OUT/('manifest'+suffix+'.json')).write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
    (OUT/('render_errors'+suffix+'.json')).write_text(json.dumps(errors,indent=2,ensure_ascii=False),encoding='utf-8')
print('RENDER_FINISHED',len(results),'errors',len(errors),flush=True)
