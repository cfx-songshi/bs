"""Render measured ODB frames as a looping GIF, with fixed scales and 1:1 geometry.

python render_impact_animation.py <export.npz> <output.gif>
"""
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle
from PIL import Image


def main():
    source,target=Path(sys.argv[1]),Path(sys.argv[2])
    d=np.load(source)
    plt.rcParams.update({'font.family':'Microsoft YaHei','font.size':10,'axes.unicode_minus':False})
    t=d['times']*1e6
    xyz=d['section_xyz']*1e3
    section=xyz[None,:,:]+d['section_u']*1e3
    top=d['top_xyz']*1e3
    top_u=d['top_u'][:,:,2]*1e3
    ball=(d['ball_xyz'][None,:]+d['ball_u'])*1e3
    plane=d['section_plane']
    groups=[np.where(plane==p)[0] for p in sorted(set(plane))]
    groups=[g[np.argsort(xyz[g,0])] for g in groups]
    assert len(groups)==16 and all(len(g)==107 for g in groups)
    xs=np.unique(top[:,0]); ys=np.unique(top[:,1])
    assert len(xs)*len(ys)==len(top)
    ix=np.searchsorted(xs,top[:,0]); iy=np.searchsorted(ys,top[:,1])
    maps=np.empty((len(t),len(ys),len(xs)))
    maps[:,iy,ix]=top_u
    limit=np.ceil(np.max(np.abs(top_u))*10)/10
    fig=plt.figure(figsize=(12,7.6),dpi=110,facecolor='#f4f7fb')
    gs=fig.add_gridspec(2,2,height_ratios=[2.6,1],width_ratios=[1.35,1],
                           left=.065,right=.95,bottom=.1,top=.83,hspace=.45,wspace=.27)
    ax=fig.add_subplot(gs[0,0]); plan=fig.add_subplot(gs[0,1]); trace=fig.add_subplot(gs[1,0]); dmg=fig.add_subplot(gs[1,1])
    fig.text(.065,.95,'第一次落球冲击 · 实际 ODB 帧回放',fontsize=21,weight='bold',color='#10263d')
    fig.text(.065,.905,'0.300 J  |  8 层板  |  acc_n01 / IMPACT  |  0–500 µs',fontsize=11,color='#465a70')
    title=fig.text(.065,.86,'',fontsize=12,color='#007b89',weight='bold')
    ax.set(xlim=(35,65),ylim=(-1.5,13),xlabel='x（mm）',ylabel='z（mm）',title='中心截面 y=50 mm · 真实位移 ×1')
    ax.set_aspect('equal'); ax.axhline(2,color='#9aa6b5',ls=':',lw=.8)
    polygons=[]
    for p in range(8):
        poly=Polygon(np.zeros((214,2)),facecolor=('#90b8cd' if p%2 else '#c1d5e0'),edgecolor='#355970',lw=.6)
        ax.add_patch(poly); polygons.append(poly)
    sphere=Circle((50,6),4,facecolor='#a5acb6',edgecolor='#354358',lw=1.8)
    ax.add_patch(sphere)
    plan.set(xlim=(35,65),ylim=(35,65),xlabel='x（mm）',ylabel='y（mm）',title='板顶面 U3 · 固定色标（mm）')
    plan.set_aspect('equal')
    mesh=plan.pcolormesh(xs,ys,maps[0],shading='nearest',cmap='RdBu_r',vmin=-limit,vmax=limit,rasterized=True)
    plan.plot(50,50,'+',color='#172b43',ms=7)
    fig.colorbar(mesh,ax=plan,pad=.035,fraction=.05)
    center=np.argmin((top[:,0]-50)**2+(top[:,1]-50)**2)
    trace.plot(t,top_u[:,center],color='#007b89',lw=1.7)
    trace.set(xlim=(0,500),xlabel='时间（µs）',ylabel='板中心 U3（mm）',title='向下位移为负')
    cursor1=trace.axvline(0,color='#f08036',lw=1.2)
    point1,=trace.plot([],[],'o',color='#f08036')
    history=d['damage_history']; dmg.plot(history[:,0]*1e6,history[:,1]*1e3,color='#a74548',lw=1.7)
    dmg.set(xlim=(0,500),ylim=(0,max(history[:,1])*1e3*1.12),xlabel='时间（µs）',ylabel='ALLDMD（mJ）',title='累计界面损伤耗散')
    cursor2=dmg.axvline(0,color='#f08036',lw=1.2)
    for panel in (ax,plan,trace,dmg):
        panel.set_facecolor('white')
        panel.spines[['top','right']].set_visible(False)
    for panel in (trace,dmg):panel.grid(alpha=.18)
    fig.text(.065,.032,'51 个保存帧慢放；截面几何与位移均不放大。右上为未变形坐标上的位移云图，颜色不代表损伤。',fontsize=9,color='#536579')
    images=[]
    for i,time_us in enumerate(t):
        for p,poly in enumerate(polygons):
            low=section[i,groups[2*p]][:,[0,2]]
            high=section[i,groups[2*p+1]][:,[0,2]]
            poly.set_xy(np.vstack([low,high[::-1]]))
        sphere.center=(ball[i,0],ball[i,2])
        mesh.set_array(maps[i].ravel())
        cursor1.set_xdata([time_us,time_us]);cursor2.set_xdata([time_us,time_us]);point1.set_data([time_us],[top_u[i,center]])
        title.set_text('t = %6.1f µs     球参考点 Δz = %+.3f mm     板中心 U3 = %+.3f mm'%(time_us,d['ball_u'][i,2]*1e3,top_u[i,center]))
        fig.canvas.draw()
        images.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())[:,:,:3].copy()))
    target.parent.mkdir(parents=True,exist_ok=True)
    # Shared palette, sampled across the whole motion, prevents frame-to-frame shimmer.
    strip=Image.new('RGB',(images[0].width,len(images[::5])*100))
    for j,img in enumerate(images[::5]):strip.paste(img.resize((img.width,100)),(0,j*100))
    palette=strip.quantize(colors=192)
    frames=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in images]
    frames[0].save(target,save_all=True,append_images=frames[1:],duration=150,loop=0,disposal=2,optimize=False)
    peak=int(np.argmin(top_u[:,center]));images[peak].save(target.with_suffix('.png'))
    with Image.open(target) as saved:
        assert saved.n_frames==len(t)
        print('GIF verified:',saved.n_frames,'frames;',saved.size,'; milliseconds/frame',saved.info['duration'])
    print('peak centre U3: %.6f mm at %.3f us; colour range +/- %.2f mm'%(top_u[peak,center],t[peak],limit))
    print(target.resolve())


if __name__=='__main__':main()
