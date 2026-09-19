"""Plane-strain orthotropic Q4 transient FE; SI internally. No fitted waveforms."""
import sys, os, json, time
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
ROOT=Path(__file__).resolve().parent
# Dependencies come from the interpreter's site-packages on this machine (there is no
# vendor directory here; see PROJECT_HANDOFF.md). The old hardcoded E: vendor path was
# removed because it only existed on the previous computer.
os.environ['MPLCONFIGDIR']=str(ROOT/'mplcache')
import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.signal import hilbert

def elastic():
    # Li et al., 2012, Table 1, T300/F593; engineering shear convention.
    E1,E2,E3=128.1e9,8.2e9,8.2e9
    S=np.diag([1/E1,1/E2,1/E3,1/3.44e9,1/4.7e9,1/4.7e9])
    S[0,1]=S[1,0]=-.27/E1
    S[0,2]=S[2,0]=-.27/E1
    S[1,2]=S[2,1]=-.2/E2
    C=np.linalg.inv(S)
    return C[np.ix_([0,2,4],[0,2,4])]

def element(dx,dz):
    k=np.zeros((8,8)); C=elastic()
    for r in [-1/np.sqrt(3),1/np.sqrt(3)]:
        for s in [-1/np.sqrt(3),1/np.sqrt(3)]:
            nx=np.array([-(1-s),1-s,1+s,-(1+s)])/2/dx
            nz=np.array([-(1-r),-(1+r),1+r,1-r])/2/dz
            B=np.zeros((3,8)); B[0,0::2]=nx; B[1,1::2]=nz
            B[2,0::2]=nz; B[2,1::2]=nx
            k+=B.T@C@B*dx*dz/4
    return k

def run(nx,nz,damaged,dt_scale=1.,save=True):
    start=time.time(); L=.5; H=.00172; rho=1570.; dx=L/nx; dz=H/nz
    x=np.linspace(0,L,nx+1); z=np.linspace(0,H,nz+1)
    base=np.arange((nx+1)*(nz+1)).reshape(nz+1,nx+1)
    nn=base.size; dup={}
    # Crack tips remain connected, interior coincident nodes separated.
    if damaged:
        for i in range(nx+1):
            if .235+1e-10<x[i]<.265-1e-10:
                dup[int(base[nz//2,i])]=nn; nn+=1
    conn=[]
    for j in range(nz):
        for i in range(nx):
            nodes=[int(base[j,i]),int(base[j,i+1]),int(base[j+1,i+1]),int(base[j+1,i])]
            if damaged and j==nz//2:
                nodes=[dup.get(n,n) if q<2 else n for q,n in enumerate(nodes)]
            conn.append(nodes)
    conn=np.array(conn); dof=(conn[:,:,None]*2+np.arange(2)).reshape(-1,8)
    ke=element(dx,dz)
    K=coo_matrix((np.tile(ke.ravel(),len(conn)),(np.repeat(dof,8,axis=1).ravel(),np.tile(dof,(1,8)).ravel())),shape=(nn*2,nn*2)).tocsr()
    mass=np.bincount(dof.ravel(),weights=np.full(dof.size,rho*dx*dz/4),minlength=2*nn)
    assert mass.min()>0
    # Certified upper bound for spectral radius of M^-1 K by absolute row sums.
    bound=np.max(np.asarray(abs(K).sum(axis=1)).ravel()/mass)
    dt_limit=2/np.sqrt(bound); nt=int(np.ceil(220e-6/(.7*dt_limit*dt_scale)))
    dt=220e-6/nt; A=diags(1/mass)@K
    force=np.zeros(nn*2)
    # Unit-width strip: each surface receives line load 1 N/m (not 3D point force 1 N).
    for j in [0,nz]: force[2*base[j,int(round(.1/dx))]+1]=1.
    rec=[2*base[nz,int(round(v/dx))]+1 for v in [.18,.32]]
    surf=2*base[nz]+1
    sample=max(1,int(round(.1e-6/dt))); frame=max(1,int(round(2e-6/dt)))
    u=np.zeros(nn*2); old=u.copy(); ts=[]; signals=[]; frames=[]; ft=[]; energies=[]
    # Peak-normalize the analytic five-cycle Hann source to exactly 1 N/m.
    fine=np.linspace(0,50e-6,100001)
    norm=np.max(np.abs(np.sin(2*np.pi*1e5*fine)*np.sin(np.pi*fine/50e-6)**2))
    for n in range(nt+1):
        t=n*dt
        if n%sample==0: ts.append(t); signals.append(u[rec].copy())
        if n%frame==0:
            frames.append(u[surf][::max(1,nx//500)].copy()); ft.append(t)
        val=np.sin(2*np.pi*1e5*t)*np.sin(np.pi*t/50e-6)**2/norm if t<=50e-6 else 0.
        new=2*u-old+dt*dt*(force*val/mass-A@u)
        if n%frame==0 and t>55e-6:
            vh=(new-u)/dt
            # Exactly conserved central-difference energy after forcing ends.
            energies.append(.5*np.dot(mass*vh,vh)+.5*np.dot(new,K@u))
        old,u=u,new
    energies=np.array(energies)
    # Rigid translations and infinitesimal rotation are null modes.
    coords=np.array([[xx,zz] for zz in z for xx in x]+[[x[n%(nx+1)],z[n//(nx+1)]] for n in dup])
    rot=np.column_stack([-coords[:,1],coords[:,0]]).ravel()
    residual=float(np.linalg.norm(K@rot)/(np.linalg.norm(K.data)*np.linalg.norm(rot)))
    meta=dict(nx=nx,nz=nz,damaged=damaged,dt_s=dt,dt_upper_bound_s=dt_limit,steps=nt,nodes=nn,
              mass_kg_per_m=float(mass.sum()/2),energy_relative_drift=float(np.ptp(energies)/np.mean(energies)),
              rigid_rotation_relative_residual=residual,seconds=time.time()-start)
    result=dict(t=np.array(ts),signal=np.array(signals),frames=np.array(frames),frame_t=np.array(ft),x=x[::max(1,nx//500)])
    name=f'{nx}_{nz}_{"damage" if damaged else "healthy"}'+('_halfdt' if dt_scale<1 else '')
    if save: np.savez_compressed(ROOT/(name+'.npz'),**result)
    (ROOT/(name+'.json')).write_text(json.dumps(meta,indent=2),encoding='utf8')
    print(json.dumps(meta),flush=True)
    return result,meta

if __name__=='__main__':
    nx=int(sys.argv[1]) if len(sys.argv)>1 else 1000
    nz=int(sys.argv[2]) if len(sys.argv)>2 else 8
    damage=sys.argv[3]=='damage' if len(sys.argv)>3 else False
    run(nx,nz,damage,float(sys.argv[4]) if len(sys.argv)>4 else 1.)
