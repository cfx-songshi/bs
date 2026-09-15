"""Trainable CNN + gradient reversal, synthetic impact-region transfer.
Kernel sizes and dense head sizes follow Zhao Table 1; unspecified details are
documented completion assumptions. NOT an exact architecture/data reproduction.
"""
import numpy as np
import torch
from torch import nn
from core import metrics
import matplotlib.pyplot as plt

class Reverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx,x,lam):ctx.lam=lam;return x.view_as(x)
    @staticmethod
    def backward(ctx,grad):return -ctx.lam*grad,None

class Network(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder=nn.Sequential(nn.Conv2d(1,8,5,padding=2),nn.ReLU(),nn.AvgPool2d((1,4)),
            nn.Conv2d(8,16,3,padding=1),nn.ReLU(),nn.AvgPool2d((1,3)),
            nn.Conv2d(16,32,5,padding=2),nn.ReLU(),nn.AdaptiveAvgPool2d((2,4)),nn.Flatten())
        self.task=nn.Sequential(nn.Linear(256,512),nn.ReLU(),nn.Linear(512,8))
        self.domain=nn.Sequential(nn.Linear(256,1024),nn.ReLU(),nn.Linear(1024,1024),nn.ReLU(),nn.Linear(1024,2))
    def forward(self,x,lam=0):
        f=self.encoder(x);return self.task(f),self.domain(Reverse.apply(f,lam))

def data(per_class,seed,domain):
    rng=np.random.default_rng(seed);fs=25000;t=np.arange(300)/fs
    sensors=np.array([[.3,.15],[.7,.15],[.3,.35],[.7,.35]])
    frequencies=np.array([1833,1083,583,333]) if domain==0 else np.array([1416,833,500,333])
    xs=[];ys=[];positions=[]
    for label in range(8):
        for i in range(per_class):
            # Independent event positions; no repeated waveform augmentations across splits.
            xy=np.array([label%4,label//4])*.25+rng.uniform(.015,.235,2)
            d=np.linalg.norm(sensors-xy,axis=1);angle=np.arctan2(sensors[:,1]-xy[1],sensors[:,0]-xy[0])
            speed=(800 if domain==0 else 700)*(1+.05*np.cos(2*angle))
            start=rng.uniform(.0001,.0003);energy=rng.uniform(.7,1.3);z=[]
            for j in range(4):
                u=np.maximum(t-start-d[j]/speed[j],0)
                gate=(t>=start+d[j]/speed[j])*(1-np.exp(-u/.00015))
                signal=np.zeros_like(t)
                for k,f in enumerate(frequencies):
                    signal+=gate*np.sin(2*np.pi*f*u)*np.exp(-u/(.0015+.0007*k))/(k+1)
                # Sensor response/range attenuation and reflected packet; assumed domain shift.
                signal*=energy*np.exp(-2*d[j])/(d[j]+.2)
                if domain:signal*=np.array([1.12,.85,1.05,.94])[j]
                signal+=rng.normal(0,.035,len(t));z.append(signal)
            xs.append(z);ys.append(label);positions.append(xy)
    return np.asarray(xs,dtype=np.float32)[:,None],np.asarray(ys),np.asarray(positions)

def fit(model,xs,ys,xt,yt,epochs,mode,seed):
    torch.manual_seed(seed);opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=1e-4)
    loss=nn.CrossEntropyLoss();history=[];model.train()
    for epoch in range(epochs):
        opt.zero_grad(set_to_none=True)
        if mode=='target_only':
            out,_=model(xt);task_loss=loss(out,yt);dom_loss=torch.tensor(0.)
        elif mode=='source_only':
            out,_=model(xs);task_loss=loss(out,ys);dom_loss=torch.tensor(0.)
        else:
            lam=(2/(1+np.exp(-10*epoch/epochs))-1)*.1 if mode=='DANN' else 0.
            out,dom=model(torch.cat([xs,xt]),lam)
            task_loss=.5*(loss(out[:len(xs)],ys)+loss(out[len(xs):],yt))
            domains=torch.cat([torch.zeros(len(xs),dtype=torch.long),torch.ones(len(xt),dtype=torch.long)])
            dom_loss=loss(dom,domains) if mode=='DANN' else torch.tensor(0.)
        total=task_loss+dom_loss;total.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5);opt.step()
        if epoch%10==0:history.append([epoch,float(task_loss.detach()),float(dom_loss.detach())])
    return history

def experiment(args,out,save,figsave):
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    # Exact GRL sign check; this does not assess model quality.
    x=torch.tensor([1.,2.],requires_grad=True);Reverse.apply(x,.3).sum().backward()
    assert torch.allclose(x.grad,torch.tensor([-.3,-.3]))
    results=[];histories={};counts=[2,8,13,18]
    for seed in range(args.seeds):
        sx,sy,sp=data(25,10000+seed,0);tx,ty,tp=data(18,20000+seed,1);ex,ey,ep=data(10,30000+seed,1)
        # Normalization exclusively fitted to source training data, frozen for all methods.
        mean=sx.mean();scale=sx.std();sx=(sx-mean)/scale;tx=(tx-mean)/scale;ex=(ex-mean)/scale
        np.savez_compressed(out/f'transfer_dataset_seed{seed}.npz',source=sx,source_y=sy,source_xy=sp,
                            target_pool=tx,target_y=ty,target_xy=tp,test=ex,test_y=ey,test_xy=ep,
                            normalization_source_mean=mean,normalization_source_std=scale,
                            source_event_ids=np.arange(200)+10000+seed*100000,
                            target_event_ids=np.arange(144)+20000+seed*100000,
                            test_event_ids=np.arange(80)+30000+seed*100000)
        sx=torch.from_numpy(sx);sy=torch.from_numpy(sy);test=torch.from_numpy(ex)
        torch.manual_seed(seed);source=Network();fit(source,sx,sy,None,None,args.epochs,'source_only',seed)
        source.eval()
        with torch.no_grad():pred=source(test)[0].argmax(1).numpy()
        results.append({'seed':seed,'k_per_class':0,'method':'source_only',**metrics(ey,pred,8)})
        for k in counts:
            idx=np.concatenate([np.arange(c*18,c*18+k) for c in range(8)])
            xx=torch.from_numpy(tx[idx]);yy=torch.from_numpy(ty[idx])
            for method in ['target_only','pooled','DANN']:
                torch.manual_seed(seed);model=Network()
                hist=fit(model,sx,sy,xx,yy,args.epochs,method,seed);model.eval()
                with torch.no_grad():pred=model(test)[0].argmax(1).numpy()
                result={'seed':seed,'k_per_class':k,'method':method,'target_train_n':8*k,'source_train_n':200,'test_n':80,**metrics(ey,pred,8)}
                results.append(result);histories[f'{seed}_{k}_{method}']=hist
                print('TRANSFER',seed,k,method,result['accuracy'],flush=True)
                if seed==0 and k==8:torch.save(model.state_dict(),out/f'cnn_{method}_seed0_k8.pt')
    save('transfer_trials',results);save('transfer_losses',histories)
    summary=[]
    for k in counts:
        for method in ['target_only','pooled','DANN']:
            runs=[r for r in results if r['k_per_class']==k and r['method']==method]
            summary.append({'k_per_class':k,'method':method,'seeds':len(runs),'accuracy_mean':float(np.mean([r['accuracy'] for r in runs])),
                            'accuracy_std_across_seeds':float(np.std([r['accuracy'] for r in runs],ddof=1)) if len(runs)>1 else 0.,
                            'macro_f1_mean':float(np.mean([r['macro_f1'] for r in runs]))})
    save('transfer_summary',summary)
    fig,ax=plt.subplots(1,2,figsize=(12,4))
    for method in ['target_only','pooled','DANN']:
        runs=[r for r in summary if r['method']==method]
        ax[0].errorbar([8*r['k_per_class'] for r in runs],[100*r['accuracy_mean'] for r in runs],yerr=[100*r['accuracy_std_across_seeds'] for r in runs],fmt='o-',capsize=3,label=method)
        ax[1].plot([8*r['k_per_class'] for r in runs],[r['macro_f1_mean'] for r in runs],'-o',label=method)
    ax[0].set(xlabel='Target labeled training events',ylabel='Synthetic test accuracy (%)',ylim=(0,105));ax[1].set(xlabel='Target labeled training events',ylabel='Macro-F1',ylim=(0,1.05));ax[0].legend()
    fig.suptitle('Synthetic-to-synthetic domain adaptation; target test never used for fitting');figsave('transfer')
    return {'seeds':args.seeds,'models_trained':args.seeds*13,'gradient_reversal_sign_check':'passed','status':'CNN-DANN on assumed synthetic signal domains; force branch not reproduced'}
