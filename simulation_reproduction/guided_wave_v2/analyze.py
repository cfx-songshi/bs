from solve import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False
def get(nx,nz,kind): return np.load(ROOT/f'{nx}_{nz}_{kind}.npz')
def err(a,b,mask=None):
    interp=np.column_stack([np.interp(b['t'],a['t'],a['signal'][:,j]) for j in range(2)])
    if mask is None: mask=b['t']<200e-6
    return np.linalg.norm(interp[mask]-b['signal'][mask],axis=0)/np.linalg.norm(b['signal'][mask],axis=0)
co=get(1000,8,'damage'); mid=get(2000,16,'damage'); fine=get(4000,32,'damage'); h=get(4000,32,'healthy')
delta=fine['signal']-h['signal']; t=fine['t']*1e6
metrics={
    'coarse_to_medium_relative_L2_R1_R2':err(co,mid).tolist(),
    'medium_to_fine_relative_L2_R1_R2':err(mid,fine).tolist(),
    'half_dt_relative_L2_R1_R2':err(get(2000,16,'damage_halfdt'),mid).tolist(),
    'peak_healthy_nm_R1_R2':(np.max(abs(h['signal']),axis=0)*1e9).tolist(),
    'peak_difference_nm_R1_R2':(np.max(abs(delta),axis=0)*1e9).tolist(),
}
for j,win in enumerate([(45,100),(110,180)]):
    mask=(t>win[0])&(t<win[1]); env=abs(hilbert(h['signal'][:,j]))
    tt=t[mask][np.argmax(env[mask])]; metrics[f'R{j+1}_healthy_packet_peak_us']=float(tt)
metrics['packet_group_speed_m_s']=.14/((metrics['R2_healthy_packet_peak_us']-metrics['R1_healthy_packet_peak_us'])*1e-6)
mask=(t>=110)&(t<=190)
metrics['difference_over_healthy_L2_110_190us_R1_R2']=(np.linalg.norm(delta[mask],axis=0)/np.linalg.norm(h['signal'][mask],axis=0)).tolist()
(ROOT/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf8')
np.savetxt(ROOT/'receiver_signals.csv',np.column_stack([t,h['signal']*1e9,fine['signal']*1e9,delta*1e9]),delimiter=',',header='time_us,healthy_R1_nm,healthy_R2_nm,damage_R1_nm,damage_R2_nm,difference_R1_nm,difference_R2_nm',comments='')
fig,axes=plt.subplots(4,1,figsize=(11,10),layout='constrained')
ax=axes[0]
ax.fill_between([0,500],0,1.72,color='#dde9ed'); ax.hlines(np.linspace(0,1.72,9),0,500,color='#81919e',lw=.6)
ax.plot([235,265],[.86,.86],color='#cf4c35',lw=4,label='30 mm 分层：中面节点分离')
for p,label,c in [(100,'等效激励 A','#b87c13'),(180,'接收 R1','#157977'),(320,'接收 R2','#157977')]:
    ax.plot(p,1.72,'v',color=c); ax.text(p,2,label,ha='center',fontsize=10)
ax.set(xlim=(0,500),ylim=(-.2,2.8),xlabel='沿纤维方向 x / mm',ylabel='厚度 z / mm',title='文献参数参考算例 · 2D 平面应变 · [0]8 T300/F593（厚度显示放大）'); ax.legend(loc='lower right')
for j in range(2):
    ax=axes[j+1]; ax.plot(t,h['signal'][:,j]*1e9,label='健康',lw=1.2); ax.plot(t,fine['signal'][:,j]*1e9,label='分层',lw=1,alpha=.85)
    ax.set(xlabel='时间 / μs',ylabel='表面位移 uz / nm',title=f'R{j+1}：x = {[180,320][j]} mm'); ax.legend(); ax.grid(alpha=.2)
ax=axes[3]
for j in range(2): ax.plot(t,delta[:,j]*1e9,label=f'R{j+1} 损伤−健康',lw=1)
ax.set(xlabel='时间 / μs',ylabel='差分位移 / nm',title='散射差分由两次有限元求解相减得到；不含人为噪声或拟合波包'); ax.legend(); ax.grid(alpha=.2)
fig.savefig(ROOT/'experiment-results.png',dpi=160); plt.close(fig)
fig,ax=plt.subplots(figsize=(10,4),layout='constrained')
v=fine['frames']*1e9; vmax=np.max(abs(v))
im=ax.pcolormesh(fine['x']*1e3,fine['frame_t']*1e6,v,cmap='RdBu_r',vmin=-vmax,vmax=vmax,shading='auto')
ax.axvline(235,color='k',ls='--',lw=.8); ax.axvline(265,color='k',ls='--',lw=.8)
ax.set(xlabel='表面位置 x / mm',ylabel='时间 / μs',title='损伤状态表面波场：传播、端部反射及分层相互作用'); fig.colorbar(im,ax=ax,label='uz / nm')
fig.savefig(ROOT/'wave-space-time.png',dpi=160); plt.close(fig)
# Compact actual solved frames for an offline, interactive visualization.
data=dict(x=np.round(fine['x']*1e3,3).tolist(),t=np.round(fine['frame_t']*1e6,3).tolist(),
          healthy=np.round(h['frames']*1e9,6).tolist(),damage=np.round(fine['frames']*1e9,6).tolist(),
          metrics=metrics)
(ROOT/'visual-data.json').write_text(json.dumps(data,separators=(',',':')),encoding='utf8')
print(json.dumps(metrics,indent=2))
