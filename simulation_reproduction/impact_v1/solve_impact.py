"""Clamped orthotropic Kirchhoff plate + unilateral Hertz proxy, SI units.

Rayleigh-Ritz spatial discretization, mass-normalized modes, velocity Verlet.
Only NumPy required. No synthetic wave packets and no voltage prediction.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import json
from pathlib import Path
import numpy as np
from numpy.polynomial import Legendre


def basis(x, order, length):
    """x is dimensionless [0,1]; physical derivatives. w=w,n=0 at edges."""
    x = np.asarray(x)
    g = x*x*(1-x)**2
    dg = 2*x-6*x*x+4*x**3
    ddg = 2-12*x+12*x*x
    rows = [[], [], []]
    for i in range(order):
        p = Legendre.basis(i)
        v, d, dd = p(2*x-1), 2*p.deriv()(2*x-1), 4*p.deriv(2)(2*x-1)
        rows[0].append(g*v)
        rows[1].append((dg*v+g*d)/length)
        rows[2].append((ddg*v+2*dg*d+g*dd)/length**2)
    return [np.array(r).T for r in rows]


def stiffness(config):
    """Uniform 50/50 Q0,Q90 mixture: explicit substitute, NOT real stacking."""
    m = config['substitute_material']
    e1, e2, nu, g = m['E1_Pa'], m['E2_Pa'], m['nu12'], m['G12_Pa']
    den = 1-nu*nu*e2/e1
    q11, q22, q12 = e1/den, e2/den, nu*e2/den
    h = config['thickness_m']
    scale = config.get('stiffness_scale', 1.)
    return np.array([(q11+q22)/2, (q11+q22)/2, q12, g])*h**3/12*scale


def build(config, order):
    if order < 2:
        raise ValueError('At least two basis functions per direction required')
    if not np.allclose(np.array(config['outer_size_m'])-2*config['clamp_width_m'],config['clear_span_m'],rtol=0,atol=1e-12):
        raise ValueError('Clear span must match outer dimensions and clamp width')
    a, b = config['clear_span_m']
    gx, wt = np.polynomial.legendre.leggauss(max(32, 2*order+6))
    xi, wt = (gx+1)/2, wt/2
    bx, by = basis(xi, order, a), basis(xi, order, b)
    xx = [[bx[i].T@(wt[:, None]*bx[j])*a for j in range(3)] for i in range(3)]
    yy = [[by[i].T@(wt[:, None]*by[j])*b for j in range(3)] for i in range(3)]
    d11, d22, d12, d66 = stiffness(config)
    mass = config['rho_kg_m3']*config['thickness_m']*np.kron(xx[0][0], yy[0][0])
    k = (d11*np.kron(xx[2][2], yy[0][0]) + d22*np.kron(xx[0][0], yy[2][2])
         + d12*(np.kron(xx[2][0], yy[0][2])+np.kron(xx[0][2], yy[2][0]))
         + 4*d66*np.kron(xx[1][1], yy[1][1]))
    lower = np.linalg.cholesky(mass)
    inv = np.linalg.solve(lower, np.eye(order*order))
    normal = inv@k@inv.T
    eig, vec = np.linalg.eigh((normal+normal.T)/2)
    if eig.min() <= 0:
        raise ValueError('Non-positive plate eigenvalue')
    modes = inv.T@vec
    residual = np.linalg.norm(k@modes-mass@modes*eig)/(np.linalg.norm(k)*np.linalg.norm(modes))
    def point(xy, deriv=(0, 0)):
        x, y = (np.array(xy)-config['clamp_width_m'])/np.array([a,b])
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError('Point outside clear span')
        return np.kron(basis([x], order, a)[deriv[0]][0],
                       basis([y], order, b)[deriv[1]][0])@modes
    force_shape = point(config['impact_xy_m'])
    gq, wq = np.polynomial.legendre.leggauss(6)
    strain = []
    for xy in config['sensor_xy_m']:
        curv = np.zeros(order*order)
        for u, wu in zip(gq,wq):
            for v, wv in zip(gq,wq):
                pos = np.array(xy)+config['patch_size_m']/2*np.array([u,v])
                curv += wu*wv/4*(point(pos,(2,0))+point(pos,(0,2)))
        # z and w positive downward: top face z=-h/2, epsilon=-z*curvature.
        strain.append(config['thickness_m']/2*curv)
    return eig, force_shape, np.array(strain), modes, point, float(residual)


def run(config, order=10, dt=2.5e-7, duration=.004, out=None):
    if dt<=0 or duration<=0 or config['ball']['height_m']<=0:
        raise ValueError('Positive dt, duration and release height required')
    if out and Path(out).exists():
        raise FileExistsError('Refusing to overwrite existing results: '+str(out))
    eig, shape, strain, modes, point, residual = build(config,order)
    r = config['ball']['diameter_m']/2
    m = config['ball']['rho_kg_m3']*4*np.pi*r**3/3
    effective = 1/((1-config['ball']['nu']**2)/config['ball']['E_Pa']
                   +(1-config['contact_proxy']['nu']**2)/config['contact_proxy']['E_Pa'])
    hertz = 4/3*effective*np.sqrt(r)*config.get('contact_scale',1.)
    g = 9.81
    v = np.sqrt(2*g*config['ball']['height_m'])
    initial = .5*m*v*v
    q, qv = np.zeros_like(eig), np.zeros_like(eig)
    z = 0.
    acc = np.zeros_like(eig)
    za = g
    n = int(np.ceil(duration/dt)); dt = duration/n
    if dt*np.sqrt(eig.max()) >= .8:
        raise ValueError('Time step too large for retained plate modes')
    stride = max(1,round(config['output_dt_s']/dt))
    columns = []; fields = []; field_t = []
    gridx = np.linspace(config['clamp_width_m'], config['outer_size_m'][0]-config['clamp_width_m'],41)
    gridy = np.linspace(config['clamp_width_m'], config['outer_size_m'][1]-config['clamp_width_m'],33)
    field_shape = np.array([point([x,y]) for y in gridy for x in gridx])
    peak_force = peak_delta = peak_w = peak_ratio = 0.
    max_drift = 0.; first_touch = None; first_end = None
    field_stride = max(1,round(5e-5/dt))
    for step in range(n+1):
        t = step*dt
        gap = max(0., z-shape@q)
        force = hertz*gap**1.5
        energy = .5*np.dot(qv,qv)+.5*np.dot(eig*q,q)+.5*m*v*v+2/5*hertz*gap**2.5-m*g*z
        max_drift = max(max_drift,abs(energy-initial)/initial)
        peak_force = max(peak_force,force); peak_delta=max(peak_delta,gap)
        peak_w=max(peak_w,abs(shape@q))
        if force>0 and first_touch is None: first_touch=t
        if force==0 and first_touch is not None and first_end is None: first_end=t
        tangent=1.5*hertz*np.sqrt(gap)
        peak_ratio=max(peak_ratio,dt*np.sqrt(eig.max()+tangent*(shape@shape+1/m)))
        if step%stride==0:
            columns.append([t,force,shape@q,z,gap,energy,*list(strain@q)])
        if step%field_stride==0:
            fields.append(field_shape@q); field_t.append(t)
        if step==n: break
        q += dt*qv+.5*dt*dt*acc
        z += dt*v+.5*dt*dt*za
        gap_new=max(0.,z-shape@q)
        fn=hertz*gap_new**1.5
        next_acc=shape*fn-eig*q
        next_za=g-fn/m
        qv += .5*dt*(acc+next_acc); v += .5*dt*(za+next_za)
        acc,za=next_acc,next_za
    data=np.array(columns)
    summary=dict(order=order,spatial_dofs=order*order,dt_s=dt,duration_s=duration,
                 ball_mass_kg=m,incident_energy_J=initial,D_Nm=stiffness(config).tolist(),
                 clear_span_mass_kg=float(np.prod(config['clear_span_m'])*config['rho_kg_m3']*config['thickness_m']),
                 first_frequencies_Hz=(np.sqrt(eig[:6])/(2*np.pi)).tolist(),
                 peak_contact_force_N=peak_force,peak_indentation_m=peak_delta,
                 peak_impact_point_displacement_m=peak_w,
                 first_contact_duration_s=None if first_end is None else first_end-first_touch,
                 energy_max_relative_error=max_drift,max_tangent_step_bound=peak_ratio,
                 eigen_relative_residual=residual,
                 patch_peak_strain_trace=np.max(abs(data[:,6:]),axis=0).tolist(),
                 status='UNVALIDATED_MECHANICAL_PROXY_NOT_PZT_VOLTAGE')
    if peak_ratio>=2: raise ValueError('Contact time step bound violated')
    if not np.isfinite(data).all(): raise ValueError('Non-finite simulation output')
    if out:
        out=Path(out); out.mkdir(parents=True,exist_ok=False)
        (out/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
        (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
        np.savetxt(out/'signals.csv',data,delimiter=',',header='time_s,contact_force_N,impact_w_m,ball_travel_m,indentation_m,energy_J,S1_mean_exx_plus_eyy,S2_mean_exx_plus_eyy,S3_mean_exx_plus_eyy,S4_mean_exx_plus_eyy',comments='')
        np.savez_compressed(out/'fields.npz',x=gridx,y=gridy,t=field_t,w=fields)
    return data, summary, dict(x=gridx,y=gridy,t=np.array(field_t),w=np.array(fields))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config',type=Path,default=Path(__file__).with_name('simulation_config.json'))
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--order',type=int,default=10)
    parser.add_argument('--dt',type=float,default=2.5e-7)
    args=parser.parse_args()
    _,s,_=run(json.loads(args.config.read_text(encoding='utf8')),args.order,args.dt,out=args.out)
    print(json.dumps(s,indent=2))
