"""Quarter-symmetric 3D hexahedral explicit FE for the P2 drop-ball route; SI units.

Spatial   trilinear (H8) hexahedra, 2x2x2 Gauss, B^T C B. The through-thickness
          degrees of freedom that the impact_v1 Kirchhoff/Rayleigh-Ritz model does
          not have are the whole point of this model.
Temporal  central difference with row-sum lumped mass. The step is sized from a
          Gershgorin bound on the spectral radius of M^-1 K, and the contact
          tangent stiffness is added to that bound inside the loop, exactly as
          impact_v1 tracks it.
Contact   unilateral Hertz, rigid sphere against the top surface, using the SAME
          law, the same ball data and the same contact_proxy as impact_v1, so any
          difference from the thin-plate result is attributable to the 3D
          kinematics rather than to a changed contact model.
Material  C_eff = mean of the 0-deg and 90-deg ply matrices (equal Q0/Q90
          mixture, the same homogenisation idea as impact_v1). The implied
          in-plane plane-stress D is written next to impact_v1's for
          traceability. The two are close but NOT identical, because impact_v1
          averaged the plane-stress reduced Q while this model averages the full
          3D C; the gap is reported, not hidden.
Output    mechanical displacement and strain only. NOT PZT voltage, NOT a damage
          prediction, NOT an experimentally validated specimen.

Sign convention follows impact_v1: z and w positive downward, so the top surface
is z = -h/2 and a positive u_z is a downward deflection.

Note on the surface strain: the strain is evaluated directly on the top face
(zeta = -1) of the top element layer, averaged over the four in-plane Gauss
points. Trilinear hexahedra under-predict bending strain at a free surface, so
the through-thickness refinement (nz = 2, 4, 8) is required evidence, not a
cosmetic option.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
import argparse
import json
import time
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.sparse.linalg import eigsh

G = 9.81
G2 = np.array([-1.0, 1.0]) / np.sqrt(3.0)
CORNERS = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
                    [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], float)


def ply_stiffness(e1, e2, e3, g12, g13, g23, nu12, nu13, nu23):
    """3D stiffness of a unidirectional ply, Voigt order [11,22,33,23,13,12]."""
    s = np.zeros((6, 6))
    s[0, 0], s[1, 1], s[2, 2] = 1 / e1, 1 / e2, 1 / e3
    s[0, 1] = s[1, 0] = -nu12 / e1
    s[0, 2] = s[2, 0] = -nu13 / e1
    s[1, 2] = s[2, 1] = -nu23 / e2
    s[3, 3], s[4, 4], s[5, 5] = 1 / g23, 1 / g13, 1 / g12
    return np.linalg.inv(s)


def material(config):
    """Equal 0-deg / 90-deg mixture in 3D Voigt form.

    A 90-deg ply about the plate normal maps 1<->2 and swaps the transverse shear
    terms 23<->13, so the index permutation is [1,0,2,4,3,5].
    """
    m = config['ply']
    c0 = ply_stiffness(m['E1_Pa'], m['E2_Pa'], m['E3_Pa'], m['G12_Pa'],
                       m['G13_Pa'], m['G23_Pa'], m['nu12'], m['nu13'], m['nu23'])
    perm = [1, 0, 2, 4, 3, 5]
    return 0.5 * (c0 + c0[np.ix_(perm, perm)])


def implied_plate_d(c, h):
    """Plane-stress condensed in-plane stiffness times h^3/12, order [D11,D22,D12,D66]."""
    idx = [0, 1, 5]
    q = c[np.ix_(idx, idx)].copy()
    c13 = c[idx, 2]
    q -= np.outer(c13, c13) / c[2, 2]
    return np.array([q[0, 0], q[1, 1], q[0, 1], q[2, 2]]) * h ** 3 / 12


def shape_derivatives(xi, eta, zeta, dx, dy, dz):
    """dN/d(x,y,z) of the eight H8 shape functions, shape (8,3)."""
    dn = 0.125 * np.column_stack([
        CORNERS[:, 0] * (1 + CORNERS[:, 1] * eta) * (1 + CORNERS[:, 2] * zeta),
        CORNERS[:, 1] * (1 + CORNERS[:, 0] * xi) * (1 + CORNERS[:, 2] * zeta),
        CORNERS[:, 2] * (1 + CORNERS[:, 0] * xi) * (1 + CORNERS[:, 1] * eta),
    ])
    return dn * np.array([2. / dx, 2. / dy, 2. / dz])


def strain_matrix(d):
    """B for one evaluation point; columns follow the 8-node, 3-dof node order."""
    b = np.zeros((6, 24))
    b[0, 0::3] = d[:, 0]
    b[1, 1::3] = d[:, 1]
    b[2, 2::3] = d[:, 2]
    b[3, 2::3] = d[:, 1]
    b[3, 1::3] = d[:, 2]
    b[4, 2::3] = d[:, 0]
    b[4, 0::3] = d[:, 2]
    b[5, 1::3] = d[:, 0]
    b[5, 0::3] = d[:, 1]
    return b


def face_strain_matrix(dx, dy, dz, zeta):
    """Mean B over the four in-plane Gauss points of one through-thickness face."""
    acc = None
    for xi in G2:
        for eta in G2:
            b = strain_matrix(shape_derivatives(xi, eta, zeta, dx, dy, dz))
            acc = b if acc is None else acc + b
    return acc / 4.


def hex8_stiffness(dx, dy, dz, c):
    k = np.zeros((24, 24))
    for xi in G2:
        for eta in G2:
            for zeta in G2:
                b = strain_matrix(shape_derivatives(xi, eta, zeta, dx, dy, dz))
                k += b.T @ c @ b * (dx / 2.) * (dy / 2.) * (dz / 2.)
    return k


def build_mesh(config, nx, ny, nz):
    lx, ly, h = config['quarter_x_m'], config['quarter_y_m'], config['thickness_m']
    xs = np.linspace(0., lx, nx + 1)
    ys = np.linspace(0., ly, ny + 1)
    zs = np.linspace(-h / 2., h / 2., nz + 1)        # index 0 is the top surface
    grid = np.arange((nz + 1) * (ny + 1) * (nx + 1)).reshape(nz + 1, ny + 1, nx + 1)
    i, j, k = np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing='ij')
    conn = np.stack([grid[k, j, i], grid[k, j, i + 1], grid[k, j + 1, i + 1], grid[k, j + 1, i],
                     grid[k + 1, j, i], grid[k + 1, j, i + 1], grid[k + 1, j + 1, i + 1],
                     grid[k + 1, j + 1, i]], axis=-1).reshape(-1, 8)
    ii, jj, kk = np.meshgrid(np.arange(nx + 1), np.arange(ny + 1), np.arange(nz + 1), indexing='ij')
    nid = (kk * (ny + 1) * (nx + 1) + jj * (nx + 1) + ii).ravel()
    coords = np.empty(((nx + 1) * (ny + 1) * (nz + 1), 3))
    coords[nid, 0] = xs[ii].ravel()
    coords[nid, 1] = ys[jj].ravel()
    coords[nid, 2] = zs[kk].ravel()
    return conn, coords, xs, ys, zs, grid


def sensor_layout(config):
    """P2 rule: an n x n grid over the monitoring region with edge = spacing / 2.

    The monitoring region is the clear span, because the clamped strip is
    immobile and cannot carry a working sensor. Numbering follows P2 figure 18
    (row-major starting from the largest y), which keeps the centre sub-region
    bounded by sensors 6, 7, 10 and 11 as in the paper.
    """
    n = config['sensors']['n_per_side']
    c = config['clamp_width_m']
    spanx = config['outer_size_m'][0] - 2 * c
    spany = config['outer_size_m'][1] - 2 * c
    sx, sy = spanx / n, spany / n
    xs = c + sx * (np.arange(n) + 0.5)
    ys = c + sy * (np.arange(n) + 0.5)
    out = [dict(id=row * n + col + 1, x_m=float(xs[col]), y_m=float(ys[n - 1 - row]),
                patch_size_m=config['patch_size_m'],
                axis_angle_deg=config['sensors']['axis_angle_deg'])
           for row in range(n) for col in range(n)]
    meta = dict(n_per_side=n, spacing_x_m=float(sx), spacing_y_m=float(sy),
                edge_x_m=float(sx / 2), edge_y_m=float(sy / 2),
                subregion_x_m=float(sx), subregion_y_m=float(sy),
                reference='clear span (outer size minus twice the clamp width)',
                rule='P2 SMS论文01 PDF p15: edge distance = half the monitoring region')
    return out, meta


def directional(exx, eyy, exy, theta_rad):
    ct, st = np.cos(theta_rad), np.sin(theta_rad)
    return exx * ct * ct + eyy * st * st + 2 * exy * st * ct


def build(config, nx, ny, nz):
    conn, coords, xs, ys, zs, grid = build_mesh(config, nx, ny, nz)
    lx, ly, h = config['quarter_x_m'], config['quarter_y_m'], config['thickness_m']
    dx, dy, dz = lx / nx, ly / ny, h / nz
    c = material(config)
    dof = (conn[:, :, None] * 3 + np.arange(3)).reshape(-1, 24)
    n_node = coords.shape[0]
    ke = hex8_stiffness(dx, dy, dz, c)
    k = coo_matrix((np.tile(ke.ravel(), len(conn)),
                    (np.repeat(dof, 24, axis=1).ravel(), np.tile(dof, (1, 24)).ravel())),
                   shape=(3 * n_node, 3 * n_node)).tocsr()
    mass = np.bincount(dof.ravel(),
                       weights=np.full(dof.size, config['rho_kg_m3'] * dx * dy * dz / 8),
                       minlength=3 * n_node)
    if mass.min() <= 0:
        raise ValueError('Zero lumped mass at some dof')

    tol = 1e-9
    clamp = config['clamp_width_m']
    fixed_nodes = (coords[:, 0] <= clamp + tol) | (coords[:, 1] <= clamp + tol)
    symx = np.isclose(coords[:, 0], lx, atol=tol)
    symy = np.isclose(coords[:, 1], ly, atol=tol)
    free = np.ones(3 * n_node, bool)
    free[np.repeat(fixed_nodes, 3)] = False
    free[3 * np.nonzero(symx)[0]] = False
    free[3 * np.nonzero(symy)[0] + 1] = False

    idx_free = np.nonzero(free)[0]
    kff = k[free][:, free].tocsr()
    mf = mass[free]
    rowsum = np.asarray(abs(kff).sum(axis=1)).ravel()

    impact_node = int(grid[0, ny, nx])                # top surface at the symmetry corner
    impact_dof = 3 * impact_node + 2
    impact_local = int(np.searchsorted(idx_free, impact_dof))
    if idx_free[impact_local] != impact_dof:
        raise ValueError('Impact dof is constrained by the symmetry or clamp conditions')

    # conn is ordered (i, j, k) because of the ij-meshgrid plus C-order reshape,
    # so the top element layer is k = 0, not the first nz-block of the array.
    top_elems = conn.reshape(nx, ny, nz, 8)[:, :, 0, :].reshape(-1, 8)
    top_nodes = top_elems[:, :4]
    top_dof = (top_elems[:, :, None] * 3 + np.arange(3)).reshape(-1, 24)

    return dict(coords=coords, xs=xs, ys=ys, zs=zs, grid=grid, c=c,
                kff=kff, mf=mf, rowsum=rowsum, bound=float(np.max(rowsum / mf)),
                idx_free=idx_free, n_dof=3 * n_node,
                dx=dx, dy=dy, dz=dz, n_node=n_node,
                impact_node=impact_node, impact_local=impact_local,
                top_nodes=top_nodes, top_dof=top_dof,
                b_top=face_strain_matrix(dx, dy, dz, -1.0),
                impact_col=np.array([int(grid[kk, ny, nx]) for kk in range(nz + 1)]),
                nx=nx, ny=ny, nz=nz)


def surface_nodal_strain(u_full, b):
    """Top-face strain averaged onto the top-surface nodes, shape (n_node, 6).

    Takes the FULL displacement vector: top_dof holds global dof numbers, while
    the integrated state vector only carries the free dofs.
    """
    eps = u_full[b['top_dof']] @ b['b_top'].T            # (n_elem, 6)
    nodal = np.zeros((b['n_node'], 6))
    counts = np.bincount(b['top_nodes'].ravel(), minlength=b['n_node']).astype(float)
    for c in range(6):
        nodal[:, c] = np.bincount(b['top_nodes'].ravel(), weights=eps[:, c].repeat(4),
                                  minlength=b['n_node'])
    seen = counts > 0
    nodal[seen] /= counts[seen, None]
    return nodal, seen


def run(config, nx, ny, nz, duration=None, out=None, modes=0):
    if out and Path(out).exists():
        raise FileExistsError('Refusing to overwrite existing results: ' + str(out))
    duration = float(duration if duration is not None else config['duration_s'])
    start = time.time()
    b = build(config, nx, ny, nz)
    kff, mf, bound = b['kff'], b['mf'], b['bound']
    lx, ly = config['quarter_x_m'], config['quarter_y_m']

    dt_limit = 2. / np.sqrt(bound)
    steps = int(np.ceil(duration / (0.7 * dt_limit)))
    dt = duration / steps

    ball = config['ball']
    r = ball['diameter_m'] / 2
    m_ball = ball['rho_kg_m3'] * 4 * np.pi * r ** 3 / 3
    proxy = config['contact_proxy']
    effective = 1. / ((1 - ball['nu'] ** 2) / ball['E_Pa'] + (1 - proxy['nu'] ** 2) / proxy['E_Pa'])
    hertz = 4. / 3 * effective * np.sqrt(r) * config.get('contact_scale', 1.)
    v_ball = np.sqrt(2 * G * ball['height_m'])
    initial = 0.5 * m_ball * v_ball ** 2

    sensors, grid_meta = sensor_layout(config)
    for s in sensors:
        s['theta_impact_deg'] = float(np.degrees(np.arctan2(ly - s['y_m'], lx - s['x_m'])))
    inside = [s for s in sensors if s['x_m'] <= lx + 1e-9 and s['y_m'] <= ly + 1e-9]

    n_free = kff.shape[0]
    u = np.zeros(n_free)
    v = np.zeros(n_free)
    acc = np.zeros(n_free)
    f_ext = np.zeros(n_free)
    z_ball, za = 0.0, G
    ku = np.zeros(n_free)

    stride = max(1, int(round(config['output_dt_s'] / dt)))
    sig, sensor_rows, profile_rows = [], [], []
    peak_force = peak_gap = peak_w = peak_bound = 0.0
    max_drift = 0.0
    first_touch = first_end = None

    for step in range(steps + 1):
        t = step * dt
        acc[:] = (f_ext - ku) / mf
        w_impact = float(u[b['impact_local']])
        gap = max(0.0, z_ball - w_impact)
        force = hertz * gap ** 1.5
        energy = (0.5 * float(np.dot(mf * v, v)) + 0.5 * float(np.dot(u, ku))
                  + 0.5 * m_ball * v_ball ** 2 + 0.4 * hertz * gap ** 2.5 - m_ball * G * z_ball)
        max_drift = max(max_drift, abs(energy - initial) / initial)
        peak_force = max(peak_force, force)
        peak_gap = max(peak_gap, gap)
        peak_w = max(peak_w, abs(w_impact))
        tangent = 1.5 * hertz * np.sqrt(gap) if gap > 0 else 0.0
        lam = max(bound, (b['rowsum'][b['impact_local']] + tangent) / mf[b['impact_local']],
                  tangent / m_ball)
        peak_bound = max(peak_bound, dt * np.sqrt(lam))
        if force > 0 and first_touch is None:
            first_touch = t
        if force == 0 and first_touch is not None and first_end is None:
            first_end = t

        if step % stride == 0:
            sig.append([t, force, w_impact, z_ball, gap, energy, max_drift])
            u_full = np.zeros(b['n_dof'])
            u_full[b['idx_free']] = u
            nodal, seen = surface_nodal_strain(u_full, b)
            for s in inside:
                x, y = s['x_m'], s['y_m']
                half = s['patch_size_m'] / 2
                sel = (seen & (abs(b['coords'][:, 0] - x) <= half + 1e-9)
                       & (abs(b['coords'][:, 1] - y) <= half + 1e-9))
                if not sel.any():
                    continue
                exx, eyy, exy = nodal[sel, 0].mean(), nodal[sel, 1].mean(), nodal[sel, 5].mean()
                sensor_rows.append([t, s['id'], x, y, exx, eyy, exy, exx + eyy,
                                    directional(exx, eyy, exy, np.radians(s['axis_angle_deg'])),
                                    directional(exx, eyy, exy, np.radians(s['theta_impact_deg']))])
            for kk, node in enumerate(b['impact_col']):
                profile_rows.append([t, b['zs'][kk], u_full[3 * node], u_full[3 * node + 1],
                                     u_full[3 * node + 2]])

        if step == steps:
            break
        u += dt * v + 0.5 * dt * dt * acc
        z_ball += dt * v_ball + 0.5 * dt * dt * za
        gap_new = max(0.0, z_ball - float(u[b['impact_local']]))
        force_new = hertz * gap_new ** 1.5
        f_ext[:] = 0.0
        f_ext[b['impact_local']] = force_new
        ku = kff @ u
        acc_new = (f_ext - ku) / mf
        za_new = G - force_new / m_ball
        v += 0.5 * dt * (acc + acc_new)
        v_ball += 0.5 * dt * (za + za_new)
        acc, za = acc_new, za_new

    signals = np.array(sig)
    summary = dict(model='quarter-symmetric 3D H8 explicit FE', nx=nx, ny=ny, nz=nz,
                   elements=int(nx * ny * nz), nodes=int(b['n_node']),
                   free_dofs=int(n_free), dt_s=dt, steps=steps, duration_s=duration,
                   dt_upper_bound_s=dt_limit, gershgorin_spectral_bound=bound,
                   ball_mass_kg=m_ball, incident_energy_J=initial,
                   quarter_size_m=[lx, ly], thickness_m=config['thickness_m'],
                   sensor_grid=grid_meta, sensors_total=len(sensors),
                   sensors_in_quarter=len(inside),
                   peak_contact_force_N=peak_force, peak_indentation_m=peak_gap,
                   peak_impact_point_displacement_m=peak_w,
                   first_contact_duration_s=None if first_end is None else first_end - first_touch,
                   energy_max_relative_error=max_drift, max_tangent_step_bound=peak_bound,
                   seconds=time.time() - start,
                   status='UNVALIDATED_MECHANICAL_PROXY_NOT_PZT_VOLTAGE')
    if modes:
        vals = eigsh(kff, k=modes, M=diags(mf), sigma=0.0, which='LM', return_eigenvectors=False)
        summary['lowest_frequencies_Hz'] = np.sort(np.sqrt(np.abs(vals)) / (2 * np.pi)).tolist()

    ref = config.get('impact_v1_reference')
    if ref:
        h = config['thickness_m']
        den = 1 - ref['nu12'] ** 2 * ref['E2_Pa'] / ref['E1_Pa']
        q11, q22 = ref['E1_Pa'] / den, ref['E2_Pa'] / den
        q12 = ref['nu12'] * ref['E2_Pa'] / den
        d_ref = np.array([(q11 + q22) / 2, (q11 + q22) / 2, q12, ref['G12_Pa']]) * h ** 3 / 12
        d_3d = implied_plate_d(b['c'], h)
        summary['implied_D_Nm'] = d_3d.tolist()
        summary['impact_v1_D_Nm'] = d_ref.tolist()
        summary['implied_D_relative_to_impact_v1'] = (np.abs(d_3d - d_ref) / np.abs(d_ref)).tolist()

    if peak_bound >= 2:
        raise ValueError('Contact time step bound violated')
    if not np.isfinite(signals).all():
        raise ValueError('Non-finite simulation output')

    if out:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=False)
        (out / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf8')
        (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
        (out / 'sensor_layout.json').write_text(
            json.dumps(dict(sensors=sensors, grid=grid_meta), ensure_ascii=False, indent=2), encoding='utf8')
        np.savetxt(out / 'signals.csv', signals, delimiter=',',
                   header='time_s,contact_force_N,impact_w_m,ball_travel_m,indentation_m,energy_J,energy_drift',
                   comments='')
        np.savetxt(out / 'sensors.csv', np.array(sensor_rows), delimiter=',',
                   header='time_s,sensor_id,x_m,y_m,exx,eyy,exy,exx_plus_eyy,eps_axis,eps_impact_dir',
                   comments='')
        np.savetxt(out / 'through_thickness.csv', np.array(profile_rows), delimiter=',',
                   header='time_s,z_m,ux,uy,uz', comments='')
    return summary


def run_prescribed(config, nx, ny, nz, t_hist, f_hist, duration=None, out=None):
    """Drive the global uniform model with a prescribed contact force history.

    Far-field strain obeys Saint-Venant: at the sensor distances the response is
    governed by the resultant force history, not by how the load is spread over
    the contact patch. So the contact force F(t) obtained from the locally refined
    rigid-sphere model (solve_impact_3d_local.run_rigid) is applied here as a point
    load at the impact node, and the sensor strain is read off the uniformly
    refined far field. This keeps the two-level model consistent without forcing
    the far-field mesh to resolve the ~0.2 mm contact patch.

    The prescribed force does work on the structure, so energy is not a conserved
    check here; the model is instead validated by the submodel's energy check and
    by the fact that the force magnitude (not its spatial distribution) determines
    the far field.
    """
    if out and Path(out).exists():
        raise FileExistsError('Refusing to overwrite existing results: ' + str(out))
    duration = float(duration if duration is not None else config['duration_s'])
    start = time.time()
    b = build(config, nx, ny, nz)
    kff, mf, bound = b['kff'], b['mf'], b['bound']
    lx, ly = config['quarter_x_m'], config['quarter_y_m']
    t_hist = np.asarray(t_hist, float)
    f_hist = np.asarray(f_hist, float)

    dt_limit = 2. / np.sqrt(bound)
    steps = int(np.ceil(duration / (0.7 * dt_limit)))
    dt = duration / steps

    sensors, grid_meta = sensor_layout(config)
    for s in sensors:
        s['theta_impact_deg'] = float(np.degrees(np.arctan2(ly - s['y_m'], lx - s['x_m'])))
    inside = [s for s in sensors if s['x_m'] <= lx + 1e-9 and s['y_m'] <= ly + 1e-9]

    n_free = kff.shape[0]
    u = np.zeros(n_free)
    v = np.zeros(n_free)
    acc = np.zeros(n_free)
    f_ext = np.zeros(n_free)
    ku = np.zeros(n_free)

    stride = max(1, int(round(config['output_dt_s'] / dt)))
    sensor_rows, profile_rows = [], []
    peak_force = peak_w = 0.0
    for step in range(steps + 1):
        t = step * dt
        acc[:] = (f_ext - ku) / mf
        force = float(np.interp(t, t_hist, f_hist))
        w_impact = float(u[b['impact_local']])
        peak_force = max(peak_force, force)
        peak_w = max(peak_w, abs(w_impact))
        if step % stride == 0:
            u_full = np.zeros(b['n_dof'])
            u_full[b['idx_free']] = u
            nodal, seen = surface_nodal_strain(u_full, b)
            for s in inside:
                x, y = s['x_m'], s['y_m']
                half = s['patch_size_m'] / 2
                sel = (seen & (abs(b['coords'][:, 0] - x) <= half + 1e-9)
                       & (abs(b['coords'][:, 1] - y) <= half + 1e-9))
                if not sel.any():
                    continue
                exx, eyy, exy = nodal[sel, 0].mean(), nodal[sel, 1].mean(), nodal[sel, 5].mean()
                sensor_rows.append([t, s['id'], x, y, exx, eyy, exy, exx + eyy,
                                    directional(exx, eyy, exy, np.radians(s['axis_angle_deg'])),
                                    directional(exx, eyy, exy, np.radians(s['theta_impact_deg']))])
            for kk, node in enumerate(b['impact_col']):
                profile_rows.append([t, b['zs'][kk], u_full[3 * node], u_full[3 * node + 1],
                                     u_full[3 * node + 2]])
        if step == steps:
            break
        u += dt * v + 0.5 * dt * dt * acc
        f_ext[:] = 0.0
        f_ext[b['impact_local']] = float(np.interp(t + dt, t_hist, f_hist))
        ku = kff @ u
        acc_new = (f_ext - ku) / mf
        v += 0.5 * dt * (acc + acc_new)
        acc = acc_new

    summary = dict(model='quarter-symmetric 3D H8, prescribed contact force (from local submodel)',
                   nx=nx, ny=ny, nz=nz, elements=int(nx * ny * nz), nodes=int(b['n_node']),
                   free_dofs=int(n_free), dt_s=dt, steps=steps, duration_s=duration,
                   dt_upper_bound_s=dt_limit,
                   quarter_size_m=[lx, ly], thickness_m=config['thickness_m'],
                   sensor_grid=grid_meta, sensors_total=len(sensors),
                   sensors_in_quarter=len(inside),
                   prescribed_peak_force_N=peak_force,
                   peak_impact_point_displacement_m=peak_w,
                   seconds=time.time() - start,
                   status='UNVALIDATED_MECHANICAL_PROXY_NOT_PZT_VOLTAGE')
    if out:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=False)
        (out / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf8')
        (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
        (out / 'sensor_layout.json').write_text(
            json.dumps(dict(sensors=sensors, grid=grid_meta), ensure_ascii=False, indent=2), encoding='utf8')
        np.savetxt(out / 'sensors.csv', np.array(sensor_rows), delimiter=',',
                   header='time_s,sensor_id,x_m,y_m,exx,eyy,exy,exx_plus_eyy,eps_axis,eps_impact_dir',
                   comments='')
        np.savetxt(out / 'through_thickness.csv', np.array(profile_rows), delimiter=',',
                   header='time_s,z_m,ux,uy,uz', comments='')
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, default=Path(__file__).with_name('simulation_config_3d.json'))
    p.add_argument('--out', type=Path, default=None)
    p.add_argument('--mesh', type=int, nargs=3, default=[40, 32, 4], metavar=('NX', 'NY', 'NZ'))
    p.add_argument('--duration', type=float, default=None)
    p.add_argument('--modes', type=int, default=0)
    a = p.parse_args()
    print(json.dumps(run(json.loads(a.config.read_text(encoding='utf8')),
                         a.mesh[0], a.mesh[1], a.mesh[2],
                         duration=a.duration, out=a.out, modes=a.modes), indent=2))
