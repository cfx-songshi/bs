import os,sys,json,hashlib
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1'
P=Path(__file__).resolve().parent; B=Path('E:/毕设知识库/simulation_reproduction')
sys.path[:0]=[str(B/'vendor'),str(B)]
os.environ['MPLCONFIGDIR']=str(P/'mplcache')
import numpy as np,pywt
from scipy.signal import hilbert
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from core import aic_curve,pick_aic
plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
def save(n,x): (P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
g=B/'guided_wave_v2'; out={}
rows=[]
for nx,nz in [(1000,8),(2000,16),(4000,32)]:
 h=np.load(g/f'{nx}_{nz}_healthy.npz');d=np.load(g/f'{nx}_{nz}_damage.npz'); t=h['t']*1e6
 peaks=[]
 for j,(lo,hi) in enumerate([(45,100),(110,180)]):
  mask=(t>lo)&(t<hi);env=abs(hilbert(h['signal'][:,j]));peaks.append(float(t[mask][env[mask].argmax()]))
 rows.append(dict(nx=nx,nz=nz,peak_us=peaks,cg_m_s=140000/(peaks[1]-peaks[0])))
out['mesh_speeds']=rows
h=np.load(g/'4000_32_healthy.npz');d=np.load(g/'4000_32_damage.npz');t=h['t']*1e6
mask=(t>=110)&(t<=190);yh=h['signal'][:,1];yd=d['signal'][:,1]
raw=np.linalg.norm(yd[mask]-yh[mask])/np.linalg.norm(yh[mask]);best=None
for lag in np.linspace(-10,10,2001):
 shifted=np.interp(t-lag,t,yh); a=max(0,float(shifted[mask]@yd[mask]/(shifted[mask]@shifted[mask])))
 error=np.linalg.norm(yd[mask]-a*shifted[mask])/np.linalg.norm(yd[mask])
 if best is None or error<best['residual_relative_to_damage']:best=dict(lag_us=float(lag),scale=a,residual_relative_to_damage=float(error))
out['R2_alignment_diagnostic']=dict(raw_difference_relative_to_healthy=float(raw),raw_difference_relative_to_damage=float(np.linalg.norm(yd[mask]-yh[mask])/np.linalg.norm(yd[mask])),**best)
fig,ax=plt.subplots(1,2,figsize=(11,4),layout='constrained')
ax[0].plot(t,yh*1e9,label='健康');ax[0].plot(t,yd*1e9,label='分层');ax[0].set(xlim=(110,190),xlabel='时间 / μs',ylabel='uz / nm',title='R2 原始波形：不对齐');ax[0].legend()
pred=best['scale']*np.interp(t-best['lag_us'],t,yh)
ax[1].plot(t,yd*1e9,label='分层');ax[1].plot(t,pred*1e9,'--',label='健康波形：拟合延时与缩放');ax[1].set(xlim=(110,190),xlabel='时间 / μs',ylabel='uz / nm',title='仅诊断相位/幅值差异，非校准结果');ax[1].legend()
fig.savefig(P/'guided-alignment.png',dpi=160);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4),layout='constrained');ax.plot([.5,.25,.125],[r['cg_m_s'] for r in rows],'o-',label='本模型：包络峰差分')
ax.axhline(1794,ls='--',color='orange',label='Li 2012 正文：3D SEM 1794 m/s');ax.invert_xaxis();ax.set(xlabel='x 向单元尺寸 / mm',ylabel='群速度 / (m/s)',title='仅健康单向板速度量级对照；两者提取方法不同');ax.legend();fig.savefig(P/'guided-speed.png',dpi=160);plt.close(fig)
# Inspect exactly the stored seed=0, SNR=0 dB AE records; do not change data.
a=np.load(B/'results/ae_dataset.npz'); records=[];zs=[]
for i,(x,onset) in enumerate(zip(a['waveforms'],a['onset_s'])):
 sigma=np.median(abs(x[:100]-np.median(x[:100])))/.6744897501960817
 cs=pywt.wavedec(x,'sym8',level=4,mode='symmetric')
 for k in range(1,len(cs)):
  j=5-k;lam=sigma*np.sqrt(2*np.log(len(x)))/np.log(j+1);cs[k]=pywt.threshold(cs[k],lam,mode='soft')
 z=pywt.waverec(cs,'sym8',mode='symmetric')[:len(x)];zs.append(z)
 idx=np.arange(100,len(z)-4,100);ac=aic_curve(z);j=np.argmax(np.diff(ac[idx])/np.diff(idx));approx=int((idx[j]+idx[j+1])/2)
 lo=max(0,approx-250);hi=min(len(z),approx+250);truth=float(onset*1e6);pick=pick_aic(z,True)
 records.append(dict(id=i,truth_sample=truth,coarse_center=approx,window_start=lo,window_end=hi,pick=pick,error_us=pick-truth,
  truth_in_window=bool(lo<=truth<hi),window_distance=float(max(lo-truth,truth-(hi-1),0))))
save('ae_window_records.json',records)
out['AE_window_audit']=dict(n=len(records),false_gt100=sum(abs(r['error_us'])>100 for r in records),truth_outside=sum(not r['truth_in_window'] for r in records),
 guaranteed_false_from_excluded_window=sum(r['window_distance']>100 for r in records),
 false_despite_truth_in_window=sum(abs(r['error_us'])>100 and r['truth_in_window'] for r in records))
fig,ax=plt.subplots(figsize=(10,4),layout='constrained')
for r in records:ax.plot([r['window_start'],r['window_end']],[r['id'],r['id']],color='#c4cad0',lw=2)
ax.scatter([r['truth_sample'] for r in records],[r['id'] for r in records],s=8,label='生成器真值');ax.scatter([r['pick'] for r in records],[r['id'] for r in records],s=8,label='实际拾取')
ax.set(xlabel='采样点（1 点 = 1 μs）',ylabel='保存的信号编号',title='AE 失败路径核查：灰线为粗定位后允许搜索的窗口');ax.legend();fig.savefig(P/'ae-window-audit.png',dpi=160);plt.close(fig)
# Paper Figure 10 exact integer counts, compared descriptively with generated results.
tr=json.loads((B/'results/transfer_summary.json').read_text()); paperN=np.array([22,59,70,74])/80*100;paperT=np.array([63,77,78,80])/80*100
ks=[2,8,13,18];trrows=[]
for i,k in enumerate(ks):
 vals={q['method']:q for q in tr if q['k_per_class']==k}
 trrows.append(dict(K=k,paper_no_transfer=float(paperN[i]),paper_transfer=float(paperT[i]),sim_target_only=vals['target_only']['accuracy_mean']*100,sim_DANN=vals['DANN']['accuracy_mean']*100,sim_pooled=vals['pooled']['accuracy_mean']*100,
 paper_gain_pp=float(paperT[i]-paperN[i]),sim_gain_pp=(vals['DANN']['accuracy_mean']-vals['target_only']['accuracy_mean'])*100))
out['transfer_comparison']=trrows
fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
for ax,key,pk,title in [(axes[0],'target_only',paperN,'无迁移/仅目标域'),(axes[1],'DANN',paperT,'迁移/DANN')]:
 vals=[next(q for q in tr if q['k_per_class']==k and q['method']==key) for k in ks]
 ax.plot(ks,pk,'s--',label='论文图10：80次测试');ax.errorbar(ks,[q['accuracy_mean']*100 for q in vals],yerr=[q['accuracy_std_across_seeds']*100 for q in vals],fmt='o-',capsize=4,label='合成数据：3种子均值±标准差')
 ax.set(xlabel='每类目标训练数 K',ylabel='准确率 / %',ylim=(0,105),title=title);ax.legend(fontsize=8)
fig.suptitle('不同数据集的结果对照，不构成算法优劣检验');fig.savefig(P/'transfer-comparison.png',dpi=160);plt.close(fig)
paper_cm=np.array([[[26,1,0],[2,24,1],[0,1,26]],[[26,1,0],[2,24,1],[1,1,25]],[[25,2,0],[1,26,0],[0,1,26]],[[25,0,2],[1,26,0],[2,2,23]]])
out['gear_paper_internal_audit']={'figure13_confusion_matrices_H_C_W':paper_cm.tolist(),'figure13_accuracies_percent':(np.trace(paper_cm,axis1=1,axis2=2)/paper_cm.sum((1,2))*100).tolist(),'text_accuracies_percent':[93.06,91.67,94.44,90.28],'figure13_pooled_accuracy_percent':float(sum(np.trace(c) for c in paper_cm)/paper_cm.sum()*100),'text_mean_accuracy_percent':92.36}
trials=json.loads((B/'results/transfer_trials.json').read_text());paired=[]
for k in ks:
 for seed in [0,1,2]:
  q={r['method']:r['accuracy'] for r in trials if r['k_per_class']==k and r['seed']==seed}
  paired.append({'K':k,'seed':seed,'DANN_minus_target_pp':100*(q['DANN']-q['target_only']),'DANN_minus_pooled_pp':100*(q['DANN']-q['pooled'])})
out['paired_transfer_deltas']=paired
f=np.load(B/'results/faults_traces.npz'); fm=f['time_s']>=50
alarm=f['alarm'][fm].astype(bool); correct=f['predicted_sensor'][fm]==0
out['faults_joint_metric_audit']={'sample_count_after_50s':int(fm.sum()),'alarm_count':int(alarm.sum()),'alarm_and_correct_count':int((alarm&correct).sum()),'alarm_and_correct_fraction':float(np.mean(alarm&correct)),'correct_given_alarm_fraction':float(np.mean(correct[alarm]))}
j=np.load(B/'results/joint_surrogates.npz')
out['pressure_input_audit']={'saved_peak_kPa':float(j['pressure_kPa'].max()),'paper_P5_p7_kPa':160,'ratio':float(j['pressure_kPa'].max()/160)}
save('audit_metrics.json',out)
print(json.dumps(out,ensure_ascii=False,indent=2))
