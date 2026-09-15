"""Reproducible experiments. See README_复现说明.md for fidelity and limitations."""
import os,sys,argparse,json,time,hashlib,platform
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument('--vendor',default=str(ROOT/'vendor'))
p.add_argument('--experiment',choices=['all','ae','localization','plate','gear','joints','faults','transfer','checks'],default='all')
p.add_argument('--seeds',type=int,default=3)
p.add_argument('--mc',type=int,default=100000)
p.add_argument('--epochs',type=int,default=100)
args=p.parse_args()
sys.path.insert(0,args.vendor)
os.environ['MPLCONFIGDIR']=str(ROOT/'results'/'.mplconfig')
os.environ['OMP_NUM_THREADS']='2';os.environ['MKL_NUM_THREADS']='2'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pywt
from scipy.signal import butter,sosfiltfilt,hilbert
from core import *
OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
plt.rcParams.update({'figure.dpi':130,'savefig.dpi':170,'axes.spines.top':False,'axes.spines.right':False,'font.size':10})

def save(name,obj):
    def conv(x):
        if isinstance(x,np.ndarray):return x.tolist()
        if isinstance(x,np.generic):return x.item()
        raise TypeError(type(x))
    (OUT/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=conv,allow_nan=False),encoding='utf8')

def figsave(name):
    plt.tight_layout();plt.savefig(OUT/(name+'.png'));plt.close()

def wavelet_standard(x,levels=4):
    sigma=np.median(abs(x[:100]-np.median(x[:100])))/.6744897501960817
    cs=pywt.wavedec(x,'sym8',level=levels,mode='symmetric')
    for i in range(1,len(cs)):
        j=levels-i+1;lam=sigma*np.sqrt(2*np.log(len(x)))/np.log(j+1)
        cs[i]=pywt.threshold(cs[i],lam,mode='soft')
    return pywt.waverec(cs,'sym8',mode='symmetric')[:len(x)]

def ae():
    points=np.array([[120,160],[100,400],[250,250],[300,100],[380,420]])/1000
    sensors=np.array([[20,20],[480,20],[480,480],[20,480]])/1000
    fs=1e6;n=2048;t=np.arange(n)/fs;snrs=[-10,-5,0,5,10]
    records=[];examples=None;signals=[];truths=[];meta=[]
    for seed in range(args.seeds):
        rng=np.random.default_rng(20260914+seed)
        for snr in snrs:
            for point_id,xy in enumerate(points):
                for event in range(5):
                    phase=rng.uniform(-.3,.3); source_time=rng.uniform(220,280)*1e-6
                    for channel,sensor in enumerate(sensors):
                        d=np.linalg.norm(xy-sensor);theta=np.arctan2(*(xy-sensor)[::-1])
                        speed=2600*(1+.12*np.cos(2*theta));onset=source_time+d/speed
                        u=t-onset;v=np.maximum(u,0)
                        clean=(u>=0)*(1-np.exp(-v/6e-6))*np.exp(-v/130e-6)*np.sin(2*np.pi*(110e3*v+25e6*v*v)+phase)
                        vr=np.maximum(u-190e-6,0)
                        clean+=.45*(u>=190e-6)*np.exp(-vr/240e-6)*np.sin(2*np.pi*65e3*vr)
                        clean*=np.exp(-1.6*d)/(np.sqrt(d+.03))
                        noise=rng.normal(size=n)
                        noise+=.35*np.sin(2*np.pi*20e3*t+rng.uniform(0,6.28))
                        spikes=rng.choice(n,6,replace=False);noise[spikes]+=rng.normal(0,4,6)
                        noise*=np.sqrt(np.mean(clean**2)/(10**(snr/10)*np.mean(noise**2)))
                        x=clean+noise;z=wavelet_standard(x)
                        sigma=np.std(x[:100]);over=np.flatnonzero(abs(x)>5*sigma)
                        picks={'threshold5sigma':int(over[0]) if len(over) else n,
                               'raw_AIC':pick_aic(x),'step_AIC':pick_aic(x,True),
                               'sym8_step_AIC':pick_aic(z,True)}
                        for method,pick in picks.items():
                            records.append({'seed':seed,'snr_db_record_power':snr,'point':point_id,'event':event,'channel':channel,
                                            'method':method,'error_us':float(pick-onset*fs)})
                        if seed==0 and snr==0:
                            signals.append(x);truths.append(onset);meta.append([point_id,event,channel])
                            if examples is None:examples=(x,z,clean,onset,picks)
    save('ae_trials',records)
    summary=[]
    for snr in snrs:
        for method in picks:
            vals=np.array([r['error_us'] for r in records if r['snr_db_record_power']==snr and r['method']==method])
            summary.append({'snr_db':snr,'method':method,'n':len(vals),'mae_us_all':float(abs(vals).mean()),
                            'median_abs_us':float(np.median(abs(vals))),'within20_percent':float(np.mean(abs(vals)<20)*100),
                            'false_gt100_percent':float(np.mean(abs(vals)>100)*100)})
    save('ae_summary',summary);np.savez_compressed(OUT/'ae_dataset.npz',waveforms=signals,onset_s=truths,event_metadata=meta,fs_hz=fs)
    fig,ax=plt.subplots(1,2,figsize=(12,4))
    for method in picks:
        s=[r for r in summary if r['method']==method]
        ax[0].plot(snrs,[r['within20_percent'] for r in s],'-o',label=method)
        ax[1].plot(snrs,[r['false_gt100_percent'] for r in s],'-o',label=method)
    ax[0].set(ylabel='|error| < 20 us (%)',xlabel='Record-power SNR (dB)',ylim=(0,105))
    ax[1].set(ylabel='|error| > 100 us (%)',xlabel='Record-power SNR (dB)',ylim=(-2,102));ax[0].legend(fontsize=8)
    figsave('ae_accuracy')
    x,z,clean,onset,picks=examples
    plt.figure(figsize=(10,4));plt.plot(t*1e6,x,color='#cccccc',label='Synthetic noisy AE');plt.plot(t*1e6,z,label='sym8 denoised');plt.plot(t*1e6,clean,alpha=.6,label='Synthetic clean signal')
    plt.axvline(onset*1e6,color='k',ls='--',label='Known simulated onset');plt.axvline(picks['sym8_step_AIC'],color='red',ls=':',label='Picked onset')
    plt.xlim(0,1100);plt.xlabel('Time (us)');plt.ylabel('Arbitrary sensor units');plt.legend(fontsize=8);figsave('ae_example')
    return {'waveforms':len(records)//4,'summary':'ae_summary.json'}

def localization():
    rng=np.random.default_rng(914);levels=[0,.001,.0025,.005,.01,.02,.05];summary=[]
    for level in levels:
        xy=rng.uniform(-.499,.499,(args.mc,2));d=np.linalg.norm(xy[:,None,:]-SQUARE,axis=2)
        times=d+rng.uniform(-level,level,d.shape)
        pred,ok,condition,roots=locate_free(times)
        err=np.linalg.norm(pred[ok]-xy[ok],axis=1)
        summary.append({'toa_error_halfwidth_fraction_of_L_over_v':level,'n_all':args.mc,'valid_count':int(ok.sum()),
                        'failure_percent':float(100*(1-ok.mean())),'ambiguous_count':int((roots>1).sum()),
                        'mean_error_percent_L_valid':float(err.mean()*100),'std_error_percent_L_valid':float(err.std()*100),
                        'p95_error_percent_L_valid':float(np.quantile(err,.95)*100),
                        'success_within_5percent_L_all':float(np.sum(err<.05)/args.mc*100)})
        print('Localization',level,summary[-1],flush=True)
    # Match original 50 x 50 x 100 first-quadrant sensitivity protocol; exact axes reported as singular.
    axis=np.linspace(0,.5,50);xx,yy=np.meshgrid(axis,axis);xy=np.c_[xx.ravel(),yy.ravel()];rep=np.repeat(xy,100,axis=0)
    d=np.linalg.norm(rep[:,None,:]-SQUARE,axis=2);pred,ok,condition,roots=locate_free(d+rng.uniform(-.01,.01,d.shape))
    err=np.linalg.norm(pred-rep,axis=1).reshape(2500,100);mask=ok.reshape(2500,100)
    means=np.nansum(err,axis=1)/np.maximum(mask.sum(1),1);fail=1-mask.mean(1)
    fig,ax=plt.subplots(1,2,figsize=(10,4))
    for a,field,title in zip(ax,[means*100,fail*100],['Mean error (% L), valid only','Rejected solutions (%)']):
        im=a.imshow(field.reshape(50,50),origin='lower',extent=[0,.5,0,.5],aspect='equal');a.set(title=title,xlabel='x/L',ylabel='y/L');fig.colorbar(im,ax=a)
    figsave('localization_heatmap')
    save('localization_summary',summary)
    fig,ax=plt.subplots(1,2,figsize=(11,4))
    ax[0].errorbar(np.array(levels)*100,[s['mean_error_percent_L_valid'] for s in summary],yerr=[s['std_error_percent_L_valid'] for s in summary],fmt='o-',capsize=3)
    ax[0].set(xlabel='ToA uniform error half-width (% L/v)',ylabel='Error (% L), valid only')
    ax[1].plot(np.array(levels)*100,[s['failure_percent'] for s in summary],'-o');ax[1].set(xlabel='ToA uniform error half-width (% L/v)',ylabel='Rejected solutions (%)')
    figsave('localization_sensitivity')
    anis=[]
    for e in [0,.02,.05,.1,.2]:
        xy=rng.uniform(-.48,.48,(10000,2));delta=xy[:,None,:]-SQUARE;angle=np.arctan2(delta[:,:,1],delta[:,:,0]);d=np.linalg.norm(delta,axis=2)
        pred,ok,_,_=locate_free(d/(1+e*np.cos(2*angle)))
        er=np.linalg.norm(pred[ok]-xy[ok],axis=1)
        anis.append({'anisotropy_e':e,'failure_percent':float((1-ok.mean())*100),'mean_error_percent_L_valid':float(er.mean()*100)})
    save('localization_anisotropy',anis)
    # First-peak interpolation: controlled waveform, randomized sub-sample phase.
    peak=[]
    for fs in [50000,100000,200000,500000,1000000]:
        errors=[];sample_errors=[];bad=0
        for i in range(1000):
            t=np.arange(int(.0005*fs))/fs;toa=rng.uniform(100e-6,180e-6);u=t-toa
            # First positive lobe at toa+25us; no precursory positive local maxima.
            signal=np.where(u>=0,np.sin(2*np.pi*10000*np.maximum(u,0))*np.exp(-np.maximum(u,0)/250e-6),0)
            signal+=rng.normal(0,.001,len(t));omega=2*np.pi*10000
            truth=toa+np.arctan(omega*250e-6)/omega
            pick=first_peak(signal,negative_threshold=-.01)
            if not np.isfinite(pick):bad+=1;continue
            errors.append(abs(pick/fs-truth)*1e6);sample_errors.append(abs(round(pick)/fs-truth)*1e6)
        peak.append({'fs_hz':fs,'n':1000,'invalid':bad,'parabolic_mae_us':float(np.mean(errors)),'integer_peak_mae_us':float(np.mean(sample_errors))})
    save('peak_interpolation',peak)
    return {'monte_carlo_per_level':args.mc,'heatmap_trials':250000}

def plate():
    """Physical forward model: equivalent isotropic simply supported Kirchhoff plate.
    It is NOT the paper's clamped explicit honeycomb/contact/plasticity FE model.
    """
    E=73e9;nu=.33;rho=2780.;skin=.0005;core=.014;L=.4
    D=2*E/(1-nu**2)*(skin**3/12+skin*((core+skin)/2)**2)
    core_fraction=.02 # Assumed equivalent density; not a measured calibration.
    mass_area=2*rho*skin+rho*core*core_fraction
    sensors=np.array([[x,y] for y in [.05,.15,.25,.35] for x in [.05,.15,.25,.35]])
    impact=np.array([.217,.183]);duration=5e-4;fs=200000;outs=np.arange(0,duration+1/fs/2,1/fs)
    mball=14800*4*np.pi*(.008/2)**3/3;v=np.sqrt(2*9.81*.36);contact=60e-6
    # Half-sine load matched to momentum impulse (restitution=0 assumed).
    amp=mball*v*np.pi/(2*contact);results={}
    for nmode in [6,10,16,24]:
        m,n=np.meshgrid(np.arange(1,nmode+1),np.arange(1,nmode+1));m=m.ravel();n=n.ravel()
        k2=(m*np.pi/L)**2+(n*np.pi/L)**2;omega=np.sqrt(D/mass_area)*k2;zeta=.015
        dt=min(1e-7,.15/omega.max());nt=int(np.ceil(duration/dt));dt=duration/nt;t=np.arange(nt+1)*dt
        force=np.where(t<contact,amp*np.sin(np.pi*t/contact),0)
        phi=np.sin(m*np.pi*impact[0]/L)*np.sin(n*np.pi*impact[1]/L)
        shapes=np.sin(sensors[:,0,None]*m*np.pi/L)*np.sin(sensors[:,1,None]*n*np.pi/L)
        # Newmark average acceleration: unconditional linear stability.
        q=np.zeros(len(m));qd=q.copy();qdd=q.copy();history=np.zeros((len(outs),16));oi=0
        c=2*zeta*omega;k=omega**2;eff=1+.5*dt*c+.25*dt*dt*k
        for it,tt in enumerate(t):
            if oi<len(outs) and tt+dt/2>=outs[oi]:
                history[oi]=shapes@q;oi+=1
            qp=q+dt*qd+.25*dt*dt*qdd;vp=qd+.5*dt*qdd
            load=phi*force[min(it+1,len(force)-1)]/(mass_area*L*L/4)
            anew=(load-c*vp-k*qp)/eff;q=qp+.25*dt*dt*anew;qd=vp+.5*dt*anew;qdd=anew
        results[nmode]=history
    ref=results[24];convergence=[]
    for count,h in results.items():
        convergence.append({'modes_per_axis':count,'relative_L2_all_sensors':float(np.linalg.norm(h-ref)/np.linalg.norm(ref))})
    save('plate_model',{'model':'equivalent simply-supported Kirchhoff plate; NOT ABAQUS reproduction','D_Nm':D,'areal_mass_kg_m2':mass_area,
                        'sphere_mass_kg':mball,'impact_velocity_m_s':v,'force_peak_N':amp,'contact_duration_s_assumed':contact,'convergence':convergence})
    np.savez_compressed(OUT/'plate_waveforms.npz',time_s=outs,displacement_m=ref,sensors_m=sensors,impact_m=impact)
    plt.figure(figsize=(10,4))
    for count,h in results.items():plt.plot(outs*1e6,h[:,5]*1e6,label=f'{count} x {count} modes')
    plt.xlabel('Time (us)');plt.ylabel('Sensor 6 displacement (um)');plt.legend();plt.title('Equivalent plate model: modal truncation sensitivity');figsave('plate_convergence')
    return {'model':'equivalent plate','sensors':16,'sample_count':len(outs)}

def joint_response():
    # Explicit constitutive surrogates; anchors are calibration inputs, not predictions.
    u=np.linspace(0,1,500);curves={};summ=[]
    for mode,anchor_s,anchor_e in [('net_tension',.04,1.66),('shear_out',.42,3.97),('bearing',None,.37)]:
        damage=np.clip((u-.25)/.6,0,1)**1.6
        load=10000*(1-np.exp(-4*u))*(1-.8*np.clip((u-.86)/.14,0,1))
        fig,ax=plt.subplots(1,2,figsize=(10,4));ax[0].plot(u,load);ax[0].set(xlabel='Normalized displacement (assumed)',ylabel='Load surrogate (N)')
        for layout,anchor in [('surface',anchor_s),('embedded',anchor_e)]:
            if anchor is None:
                resistance=.02*u-.1*damage;resistance[u>.6]=np.nan
            elif mode=='bearing':resistance=-anchor*damage+.015*u
            else:resistance=.01*u+anchor*damage+np.clip((u-.86)/.14,0,1)*(2.5 if mode=='net_tension' else 8)
            curves[mode+'_'+layout]=resistance
            ax[1].plot(u,resistance*100,label=layout)
        ax[1].set(xlabel='Normalized displacement (assumed)',ylabel='Resistance change (%)');ax[1].legend();fig.suptitle(mode+' - fitted mechanism illustration');figsave('joint_'+mode)
        summ.append({'failure_mode':mode,'stage2_surface_anchor_fraction':anchor_s,'stage2_embedded_anchor_fraction':anchor_e,'status':'calibration inputs from embedded paper Table III, not reproduced measurements'})
    # Pressure cycling: anchors from papers; rate/hysteresis assumed.
    t=np.linspace(0,350,3501);pressure=1600*(.5-.5*np.cos(2*np.pi*t/10));r_eq=-.3*pressure/1600;r=np.zeros_like(t)
    for i in range(1,len(t)):r[i]=r[i-1]+.1/.5*(r_eq[i]-r[i-1])
    np.savez_compressed(OUT/'joint_surrogates.npz',normalized_displacement=u,**curves,cycle_time_s=t,pressure_kPa=pressure,resistance_fraction=r)
    save('joint_anchors',summ)
    return {'papers':2,'status':'calibrated phenomenological surrogates only'}

def faults():
    """12-channel KF bank, one sensor left out in each subfilter. Toy health model."""
    rng=np.random.default_rng(34);dt=.04;t=np.arange(0,150,dt);h=np.c_[np.ones(12),np.linspace(-1,1,12)]
    true=np.c_[-.01*(t>=20),.003*np.sin(t/12)];noise=.05
    y=true@h.T+rng.normal(0,noise,(len(t),12));y[t>=45,0]+=.05
    # Bank estimates the two latent states from 11 channels, then scores retained residuals.
    bank=[]
    for omit in range(12):
        keep=np.arange(12)!=omit;H=h[keep];x=np.zeros(2);P=np.eye(2);score=[];est=[]
        for yi in y:
            P=P+np.eye(2)*1e-8;S=H@P@H.T+noise**2*np.eye(11);K=np.linalg.solve(S,(P@H.T).T).T
            innovation=yi[keep]-H@x;score.append(float(innovation@np.linalg.solve(S,innovation)))
            x=x+K@innovation;P=(np.eye(2)-K@H)@P;P=(P+P.T)/2;est.append(x.copy())
        bank.append(score)
    scores=np.array(bank).T
    # Calibration uses a distinct healthy noise realization, same frozen observation H.
    healthy=rng.normal(0,noise,(20000,12));stat=healthy**2/noise**2
    # Windowed rank statistic: persistent reduction when omitting the faulty sensor.
    win=int(5/dt);smooth=np.stack([np.convolve(scores[:,j],np.ones(win)/win,'full')[:len(t)] for j in range(12)],1)
    predicted=smooth.argmin(1);margin=np.median(smooth,axis=1)-smooth.min(1)
    healthy_scores=np.stack([(np.delete(stat,i,axis=1).sum(1)) for i in range(12)],1)
    smooth_h=np.stack([np.convolve(healthy_scores[:,j],np.ones(win)/win,'valid') for j in range(12)],1)
    threshold=float(np.quantile(np.median(smooth_h,axis=1)-smooth_h.min(1),.995))
    alarm=margin>threshold
    results={'model':'two-state synthetic health model, not JT9D/T-MATS','dt_s':dt,'noise_std':noise,'performance_change_s':20,
             'sensor_bias_s':45,'sensor_bias_fraction':.05,'window_s':5,'threshold_calibrated':threshold,
             'false_alarm_fraction_5to20s':float(alarm[(t>=5)&(t<20)].mean()),
             'detection_fraction_after50s':float(alarm[t>=50].mean()),'correct_isolation_fraction_after50s':float((predicted[t>=50]==0).mean()),
             'deviation':'rolling average score margin replaces original two WSSR/IWSSR thresholds; no LSTM or component-map reproduction'}
    save('faults_summary',results);np.savez_compressed(OUT/'faults_traces.npz',time_s=t,scores=scores,margin=margin,alarm=alarm,predicted_sensor=predicted)
    fig,ax=plt.subplots(2,1,figsize=(10,6),sharex=True);ax[0].plot(t,margin);ax[0].axhline(threshold,color='r',ls='--');ax[0].set(ylabel='Bank score margin')
    ax[1].plot(t,predicted+1,lw=.6);ax[1].set(xlabel='Time (s)',ylabel='Candidate sensor (1-based)')
    for a in ax:
        a.axvline(20,color='gray',ls=':');a.axvline(45,color='red',ls=':')
    figsave('faults');return results

def gear_features(x,fs):
    # NOT CEEMDAN/MWF-PeEn: explicit time windows and band statistics substitute.
    features=[]
    for segment in np.array_split(x,8):
        rms=np.sqrt(np.mean(segment**2));features.extend([rms,np.max(abs(segment)),np.std(segment),np.mean(segment)])
    spectrum=abs(np.fft.rfft(x));features.extend(np.array_split(spectrum,8)[i].sum() for i in range(8))
    return np.array(features)

def gear():
    fs=24e6;t=np.arange(6000)/fs;rng=np.random.default_rng(29);datasets={};waveforms={}
    for rpm in [0,150,200,250,300]:
        count=162 if rpm==0 else 27 # 486 source + 4*81=324 test, one interpretation of paper wording.
        xlist=[];ys=[];raw=[]
        for c in range(3):
            for i in range(count):
                shift=rng.normal(0,.05e-6)+rpm*.0006e-6
                def packet(at,width,amplitude):
                    u=t-at-shift;return amplitude*np.exp(-.5*(u/width)**2)*np.sin(2*np.pi*350e3*u)
                base=packet(72e-6,8e-6,1.2)+packet(148e-6,16e-6,.65)
                fault=packet(74e-6,6e-6,-.23) if c==2 else packet(152e-6,18e-6,-.25) if c==1 else 0
                x=(base+fault)*(1+rng.normal(0,.008))+.018*rng.normal(size=len(t))
                sos=butter(4,[330e3,370e3],fs=fs,btype='bandpass',output='sos');x=sosfiltfilt(sos,x)
                xlist.append(gear_features(x,fs));ys.append(c)
                if i==0:raw.append(x)
        datasets[rpm]=(np.array(xlist),np.array(ys));waveforms[str(rpm)]=np.array(raw)
    train,y=datasets[0];results=[]
    # Independent target adaptation signals use first 9/class, remaining 18/class held out.
    for rpm in [150,200,250,300]:
        target,yt=datasets[rpm];adapt=np.r_[0:9,27:36,54:63];test=np.setdiff1d(np.arange(81),adapt)
        xs,xa,xe=standardize(train,target[adapt],target[test]);W=tca_linear(xs,xa,k=12)
        aligned_s,aligned_e=standardize(xs@W,xe@W)
        for method,a,b in [('ELM',xs,xe),('linear_TCA_ELM',aligned_s,aligned_e)]:
            model=elm_fit(a,y,3,seed=29);pred=elm_predict(model,b)
            results.append({'rpm':rpm,'method':method,'source_train_n':486,'target_adapt_unlabeled_n':27,'target_test_n':54,**metrics(yt[test],pred,3)})
    save('gear_summary',results);np.savez_compressed(OUT/'gear_example_waveforms.npz',time_s=t,**waveforms)
    fig,ax=plt.subplots(1,2,figsize=(11,4))
    for c,label in enumerate(['healthy','wear','crack']):ax[0].plot(t*1e6,waveforms['0'][c],label=label)
    for method in ['ELM','linear_TCA_ELM']:
        s=[r for r in results if r['method']==method];ax[1].plot([r['rpm'] for r in s],[r['accuracy']*100 for r in s],'-o',label=method)
    ax[0].set(xlabel='Time (us)',ylabel='Synthetic UGW (V)');ax[0].legend();ax[1].set(xlabel='Speed (rpm)',ylabel='Held-out accuracy (%)',ylim=(0,105));ax[1].legend()
    figsave('gear');return {'status':'TCA + ELM partial reproduction; CEEMDAN/MWF-PeEn not reproduced'}

def checks():
    rng=np.random.default_rng(123);x=rng.normal(size=2048)
    assert np.max(abs(wavelet(x,threshold=False)-x))<1e-9
    assert np.max(abs(SYM8-np.array(pywt.Wavelet('sym8').rec_lo)))<1e-12
    xy=rng.uniform(.05,.45,(100,2));t=np.linalg.norm(xy[:,None,:]-SQUARE,axis=2)/1234+.012
    q,valid,_,_=locate_free(t);assert valid.all() and np.max(abs(q-xy))<1e-7
    qq,ok,_,_=locate_free(2.3*t+.123);assert ok.all() and np.max(abs(q-qq))<1e-7
    _,centerok,_,_=locate_free(np.ones((1,4)));assert not centerok[0]
    a=aic_curve(x);k=311;direct=k*np.log(np.var(x[:k]))+(len(x)-k-1)*np.log(np.var(x[k:]))
    assert abs(a[k]-direct)<1e-9
    xs=rng.normal(size=(40,6));xt=rng.normal(size=(30,6));w=tca_linear(xs,xt,k=4)
    xc=np.r_[xs,xt]-np.r_[xs,xt].mean(0);b=xc.T@xc+1e-6*np.eye(6)
    assert np.max(abs(w.T@b@w-np.eye(4)))<1e-8
    save('checks',{'wavelet_perfect_reconstruction':True,'sym8_constants_match_pywavelets':True,'noiseless_localization':True,
                   'toa_affine_invariance':True,'center_singularity_rejected':True,'prefix_aic_matches_direct_variance':True,'tca_constraint':True})
    return {'passed':7}

if __name__=='__main__':
    jobs={'checks':checks,'ae':ae,'localization':localization,'plate':plate,'gear':gear,'joints':joint_response,'faults':faults}
    if args.experiment in ['all','transfer']:
        from transfer import experiment as transfer_experiment
        jobs['transfer']=lambda:transfer_experiment(args,OUT,save,figsave)
    names=list(jobs) if args.experiment=='all' else [args.experiment]
    for name in names:
        print('START',name,flush=True);start=time.time();result=jobs[name]();print('DONE',name,round(time.time()-start,2),result,flush=True)
    import importlib.metadata
    versions={m:importlib.metadata.version(m) for m in ['numpy','scipy','matplotlib','PyWavelets','scikit-learn','torch']}
    save('environment',{'python':sys.version,'platform':platform.platform(),'packages':versions,'last_command':vars(args)})
