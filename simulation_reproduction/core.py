"""Numerical kernels. Python 3.10+, NumPy only; all units are SI unless stated.

This is an independent implementation, not code supplied by the paper authors.
"""
import numpy as np

# Symlet-8 reconstruction low-pass coefficients; numerical constants verified against
# https://github.com/PyWavelets/pywt/blob/main/pywt/_extensions/c/wavelets_coeffs.template.h
SYM8 = np.array([.0018899503327594609,-.0003029205147213668,-.014952258337048231,
 .0038087520138906151,.049137179673607506,-.027219029917056003,-.051945838107709037,
 .3644418948353314,.77718575170052351,.48135965125837221,-.061273359067658524,
 -.14329423835080971,.0076074873249176054,.031695087811492981,
 -.00054213233179114812,-.0033824159510061256])

def wavelet(x, levels=4, sigma=None, threshold=True):
    """Periodic orthogonal DWT, adjoint inverse; threshold only detail coefficients.
    MSSP Eq.(15): sigma*sqrt(2*ln(N))/ln(j+1), finest detail j=1.
    Periodic extension and pretrigger sigma estimate are implementation assumptions.
    """
    x=np.asarray(x,dtype=float); original=len(x)
    a=np.pad(x,(0,(-len(x)) % 2**levels),mode='wrap')
    h=SYM8; g=(-1.)**np.arange(len(h))*h[::-1]; ds=[]
    if sigma is None:
        pre=x[:min(100,len(x)//4)]
        sigma=np.median(np.abs(pre-np.median(pre)))/.6744897501960817
    for j in range(1,levels+1):
        n=len(a); idx=(2*np.arange(n//2)[:,None]+np.arange(16))%n
        block=a[idx]; low=block@h; detail=block@g
        if threshold:
            lam=sigma*np.sqrt(2*np.log(original))/np.log(j+1)
            detail=np.sign(detail)*np.maximum(abs(detail)-lam,0)
        ds.append(detail); a=low
    for d in ds[::-1]:
        n=2*len(a); rec=np.zeros(n)
        for k in range(16):
            np.add.at(rec,(2*np.arange(len(a))+k)%n,h[k]*a+g[k]*d)
        a=rec
    return a[:original]

def aic_curve(x):
    """MSSP Eq.(2), split k: left x[:k], right x[k:], weight N-k-1.
    Returned curve[k] scores a split BEFORE zero-based sample k.
    """
    x=np.asarray(x,float); n=len(x); k=np.arange(1,n)
    s=np.cumsum(x); s2=np.cumsum(x*x)
    v1=s2[:-1]/k-(s[:-1]/k)**2
    v2=(s2[-1]-s2[:-1])/(n-k)-((s[-1]-s[:-1])/(n-k))**2
    eps=max(np.var(x)*1e-12,1e-30)
    out=np.full(n,np.inf)
    out[k]=k*np.log(np.maximum(v1,eps))+(n-k-1)*np.log(np.maximum(v2,eps))
    out[:4]=np.inf; out[-4:]=np.inf
    return out

def pick_aic(x, improved=False, denoise=False, step=100):
    z=wavelet(x) if denoise else np.asarray(x)
    a=aic_curve(z)
    if not improved:return int(np.argmin(a))
    idx=np.arange(step,len(z)-4,step)
    # Center derivative between successive coarse split positions.
    slopes=np.diff(a[idx])/np.diff(idx)
    j=int(np.argmax(slopes)); approx=int((idx[j]+idx[j+1])//2)
    lo=max(0,approx-5*step//2); hi=min(len(z),approx+5*step//2)
    return lo+int(np.argmin(aic_curve(z[lo:hi])))

def first_peak(x, negative_threshold=None):
    """SMS section 2.1: AIC start, negative crossing end, 3-point parabola."""
    x=np.asarray(x); start=pick_aic(x)
    if negative_threshold is None:
        negative_threshold=-3*max(np.std(x[:10]),1e-12)
    below=np.flatnonzero(x[start:]<negative_threshold)
    end=start+int(below[0]) if len(below) else len(x)
    if end<=start+1:return float('nan')
    k=start+int(np.argmax(x[start:end]))
    if not 0<k<len(x)-1:return float(k)
    den=x[k-1]-2*x[k]+x[k+1]
    offset=.5*(x[k-1]-x[k+1])/den if den<0 else 0.
    return k+float(np.clip(offset,-.5,.5))

SQUARE=np.array([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])

def locate_free(times):
    """Algebraic solution of SMS Eq.(5), NOT the paper's five-intersection search.
    Square side = 1. Unknown origin time and speed; no true speed input.
    Returns xy, valid flag, matrix condition number, number of admissible roots.
    Rejects ambiguous, singular, noncausal, outside-square, or nonphysical solutions.
    Arbitrary translation/positive scaling of input arrival times is allowed.
    """
    times=np.atleast_2d(times).astype(float); n=len(times)
    span=np.ptp(times,axis=1); t=(times-times.min(axis=1)[:,None])/np.maximum(span[:,None],1e-20)
    mat=np.empty((n,3,3)); mat[:,:,:2]=-2*(SQUARE[1:]-SQUARE[0])[None]
    mat[:,:,2]=2*(t[:,1:]-t[:,0,None]); rhs=t[:,1:]**2-t[:,0,None]**2
    cond=np.linalg.cond(mat); good=(span>1e-15)&(cond<1e10)&np.isfinite(cond)
    sol=np.zeros((n,3)); sol[good]=np.linalg.solve(mat[good],rhs[good,:,None])[:,:,0]
    u=sol[:,:2]; t0=sol[:,2]
    aa=np.sum(u*u,axis=1); bb=2*(u@SQUARE[0])+(t[:,0]-t0)**2; cc=np.sum(SQUARE[0]**2)
    disc=bb*bb-4*aa*cc
    # Stable quadratic roots for q=v^2; avoid cancellation in the smaller root.
    q1=(bb+np.sqrt(np.maximum(disc,0)))/(2*np.maximum(aa,1e-30))
    q2=cc/np.maximum(aa*q1,1e-30)
    q=np.stack([q1,q2],axis=1); pos=q[:,:,None]*u[:,None,:]
    dist=np.linalg.norm(pos[:,:,None,:]-SQUARE[None,None,:,:],axis=-1)
    pred=t0[:,None,None]+dist/np.sqrt(np.maximum(q[:,:,None],1e-30))
    residual=np.max(abs(pred-t[:,None,:]),axis=2)
    valid=(good[:,None]&(disc[:,None]>=0)&(q>0)&(t0[:,None]<=t.min(axis=1)[:,None]+1e-8)
           &(np.max(abs(pos),axis=2)<=.5+1e-8)&(residual<1e-6))
    duplicate=np.linalg.norm(pos[:,0]-pos[:,1],axis=1)<1e-8
    valid[duplicate,1]=False
    count=valid.sum(axis=1); ok=count==1
    xy=np.full((n,2),np.nan); idx=valid.argmax(axis=1); xy[ok]=pos[np.flatnonzero(ok),idx[ok]]
    return xy,ok,cond,count

def metrics(y,p,nclass):
    cm=np.zeros((nclass,nclass),int);np.add.at(cm,(y,p),1)
    tp=np.diag(cm); f1=2*tp/np.maximum(cm.sum(0)+cm.sum(1),1)
    return {'accuracy':float(np.mean(y==p)),'macro_f1':float(f1.mean()),'confusion':cm.tolist()}

def standardize(train,*others):
    mu=train.mean(0);sd=train.std(0);sd=np.maximum(sd,1e-6)
    return [(x-mu)/sd for x in (train,)+others]

def pca_fit(x,k):
    mu=x.mean(0);_,_,v=np.linalg.svd(x-mu,full_matrices=False)
    return mu,v[:k].T

def tca_linear(xs,xt,k=12,mu=.1):
    """Primal linear-kernel TCA, constraint W^T X H X^T W=I.
    No labels needed. Target adaptation pool must NOT be the held-out test set.
    Generalized eigenproblem solved by symmetric whitening, not nonsymmetric eigh.
    """
    x=np.concatenate([xs,xt]);delta=xs.mean(0)-xt.mean(0)
    a=np.outer(delta,delta)+mu*np.eye(x.shape[1])
    xc=x-x.mean(0);b=xc.T@xc+1e-6*np.eye(x.shape[1])
    ev,u=np.linalg.eigh(b);w=(u*(1/np.sqrt(np.maximum(ev,1e-12))))@u.T
    vals,v=np.linalg.eigh(w@a@w)
    return w@v[:,:min(k,x.shape[1])]

def coral(xs,xt):
    def power(c,p):
        e,u=np.linalg.eigh(c+1e-3*np.eye(c.shape[0]));return (u*np.maximum(e,1e-8)**p)@u.T
    return (xs-xs.mean(0))@power(np.cov(xs,rowvar=False),-.5)@power(np.cov(xt,rowvar=False),.5)+xt.mean(0)

def elm_fit(x,y,nclass,seed=0,hidden=180,ridge=1.):
    rng=np.random.default_rng(seed);w=rng.normal(0,1/np.sqrt(x.shape[1]),(x.shape[1],hidden));b=rng.normal(0,.1,hidden)
    h=np.tanh(x@w+b);target=np.eye(nclass)[y]
    beta=np.linalg.solve(h.T@h+ridge*np.eye(hidden),h.T@target)
    return w,b,beta

def elm_predict(model,x):
    w,b,beta=model;return np.argmax(np.tanh(x@w+b)@beta,axis=1)
