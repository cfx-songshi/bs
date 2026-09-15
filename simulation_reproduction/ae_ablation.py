"""Noise-type diagnostic. Does not retune thresholds using evaluation results."""
import sys
from pathlib import Path
vendor=sys.argv[1] if len(sys.argv)>1 else str(Path(__file__).resolve().parent/'vendor')
sys.argv=[sys.argv[0],'--vendor',vendor]
from run import np,OUT,save,pick_aic,wavelet_standard,plt,figsave
rng=np.random.default_rng(903);fs=1e6;t=np.arange(2048)/fs;rows=[]
for snr in [0,5,10]:
 for kind in ['white','white_friction','white_impulses','mixed']:
  errors=[]
  for event in range(100):
   onset=rng.uniform(250,450)*1e-6;u=np.maximum(t-onset,0)
   clean=(t>=onset)*(1-np.exp(-u/6e-6))*np.exp(-u/130e-6)*np.sin(2*np.pi*110e3*u)
   noise=rng.normal(size=len(t))
   if kind in ['white_friction','mixed']:noise+=.35*np.sin(2*np.pi*20e3*t+rng.uniform(0,6.28))
   if kind in ['white_impulses','mixed']:noise[rng.choice(len(t),6,False)]+=rng.normal(0,4,6)
   noise*=np.sqrt(np.mean(clean**2)/(10**(snr/10)*np.mean(noise**2)))
   x=clean+noise;errors.append([pick_aic(x,True)-onset*fs,pick_aic(wavelet_standard(x),True)-onset*fs])
  errors=np.array(errors)
  for i,method in enumerate(['step_AIC','sym8_step_AIC']):
   rows.append({'snr_db':snr,'noise':kind,'method':method,'n_events':100,
                'within20_percent':float(np.mean(abs(errors[:,i])<20)*100),'false_gt100_percent':float(np.mean(abs(errors[:,i])>100)*100)})
save('ae_noise_ablation',rows)
print(rows)
