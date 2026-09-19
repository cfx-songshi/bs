"""Locally refined 3D submodel of the impact point; SI units.

Why this file exists
--------------------
The uniform-mesh global model (solve_impact_3d.py) cannot resolve the contact
zone: the Hertz patch radius is sqrt(R*delta) ~ 0.22 mm while the finest uniform
element was 1.25 mm. A force applied to a single node of a coarse mesh makes the
local compliance an artefact of the element size, so refining a uniform mesh
towards the patch is the only way to see whether the local response is a
prediction or a regularisation. Two changes are needed, not one:

1. graded tensor-product mesh, finest at the impact corner and coarsening away,
   so the refinement is affordable;
2. the contact force is spread over the physical Hertz patch instead of one
   node, because a point load on a solid mesh has a mesh-dependent local
   deflection that never converges.

Contact is still the same single non-linear Hertz law as impact_v1 and
solve_impact_3d (same hertz coefficient, same ball data), only its spatial
distribution differs. That keeps the hybrid-spring formulation comparable while
removing the point-load artefact. See the limitations section of the README for
what this does and does not settle: the hybrid spring still supplies the local
indentation analytically, so once the mesh resolves the patch the two overlap.

Sign convention follows impact_v1: z and w positive downward, top surface at
z = -h/2.
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

from solve_impact_3d import (G, G2, CORNERS, material, implied_plate_d,
                             shape_derivatives, strain_matrix, hex8_stiffness,
                             sensor_layout, directional)


def graded_offsets(length, h0, growth, h_max):
    """Offsets from 0 to length with the first element about h0 and growth capped.

    growth = 1 is allowed and yields a uniform mesh, which is what the equivalence
    check against the uniform solver uses.
    """
    if h0 <= 0 or growth < 1 or h_max < h0:
        raise ValueError('Require 0 < h0 <= h_max and growth >= 1')
    sizes, h = [], h0
    while sum(sizes) < length:
        sizes.append(min(h, h_max))
        h *= growth
    sizes = np.array(sizes)
    sizes *= length / sizes.sum()
    return np.concatenate([[0.0], np.cumsum(sizes)])


def graded_axis(fine_coord, length, h0, growth, h_max, direction=-1):
    """Coordinates with the finest element at `fine_coord`, extending by `length`."""
    d = graded_offsets(length, h0, growth, h_max)
    axis = fine_coord + direction * d
    return np.sort(axis)


def _part(nat, slots):
    """B-contribution of one natural derivative: slots are (strain row, dof offset)."""
    b = np.zeros((6, 24))
    for row, off in slots:
        b[row, off::3] = nat
    return b


def element_parts(c):
    """Six constant 24x24 blocks such that, for a rectangular box,

        K = (dy*dz/(2*dx))*A[0] + (dx*dz/(2*dy))*A[1] + (dx*dy/(2*dz))*A[2]
            + (dz/2)*A[3] + (dy/2)*A[4] + (dx/2)*A[5]

    Exactly, with no additional approximation: for a box the natural Jacobian is
    constant, so every entry of B is (2/dx) times a xi-derivative, (2/dy) times an
    eta-derivative or (2/dz) times a zeta-derivative. The 1/2 factors come from the
    natural-domain volume J = (dx/2)(dy/2)(dz/2) = dx*dy*dz/8 together with the
    squares and cross products of the 2/dx factors.
    """
    a = [np.zeros((24, 24)) for _ in range(6)]
    for xi in G2:
        for eta in G2:
            for zeta in G2:
                dn_xi = 0.125 * CORNERS[:, 0] * (1 + CORNERS[:, 1] * eta) * (1 + CORNERS[:, 2] * zeta)
                dn_eta = 0.125 * CORNERS[:, 1] * (1 + CORNERS[:, 0] * xi) * (1 + CORNERS[:, 2] * zeta)
                dn_ze = 0.125 * CORNERS[:, 2] * (1 + CORNERS[:, 0] * xi) * (1 + CORNERS[:, 1] * eta)
                bx = _part(dn_xi, [(0, 0), (4, 2), (5, 1)])     # eps11, gamma13, gamma12
                by = _part(dn_eta, [(1, 1), (3, 2), (5, 0)])    # eps22, gamma23, gamma12
                bz = _part(dn_ze, [(2, 2), (3, 1), (4, 0)])     # eps33, gamma23, gamma13
                a[0] += bx.T @ c @ bx
                a[1] += by.T @ c @ by
                a[2] += bz.T @ c @ bz
                a[3] += bx.T @ c @ by + by.T @ c @ bx
                a[4] += bx.T @ c @ bz + bz.T @ c @ bx
                a[5] += by.T @ c @ bz + bz.T @ c @ by
    return a


def verify_parts(c, dx=0.5, dy=0.3, dz=0.2):
    """element_parts must reproduce the direct box stiffness exactly."""
    a = element_parts(c)
    fast = (dy * dz / (2 * dx) * a[0] + dx * dz / (2 * dy) * a[1] + dx * dy / (2 * dz) * a[2]
            + dz / 2 * a[3] + dy / 2 * a[4] + dx / 2 * a[5])
    direct = hex8_stiffness(dx, dy, dz, c)
    scale = np.abs(direct).max()
    return float(np.abs(fast - direct).max() / scale)


def mass_scaled_bound(kff, mf):
    """Gershgorin bound on the spectral radius of M^-1 K.

    lambda_max(M^-1 K) = lambda_max(M^-1/2 K M^-1/2), and for a symmetric matrix
    the row-sum bound is max_i sum_j |K_ij| / sqrt(m_i m_j).

    Dividing by m_i alone is only the same when every nodal mass is equal. On a
    graded mesh the masses near the contact are orders of magnitude smaller than
    far away, so the m_i-only form under-estimates the bound badly and the step it
    produces is unstable. That is the defect this function removes.
    """
    inv_sqrt = 1.0 / np.sqrt(mf)
    d = diags(inv_sqrt)
    scaled = d @ abs(kff) @ d
    return float(np.max(np.asarray(scaled.sum(axis=1)).ravel()))


def build_local(config, h0, z0, growth, h_max):
    c = material(config)
    lx, ly, h = config['quarter_x_m'], config['quarter_y_m'], config['thickness_m']
    xs = graded_axis(lx, lx, h0, growth, h_max, direction=-1)
    ys = graded_axis(ly, ly, h0, growth, h_max, direction=-1)
    zs = graded_axis(-h / 2., h, z0, growth, h_max, direction=+1)
    nx, ny, nz = len(xs) - 1, len(ys) - 1, len(zs) - 1
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

    dxe = np.diff(xs)[i.ravel()]
    dye = np.diff(ys)[j.ravel()]
    dze = np.diff(zs)[k.ravel()]
    a = element_parts(c)
    kk_all = ((dye * dze / (2 * dxe))[:, None, None] * a[0]
              + (dxe * dze / (2 * dye))[:, None, None] * a[1]
              + (dxe * dye / (2 * dze))[:, None, None] * a[2]
              + (dze / 2)[:, None, None] * a[3]
              + (dye / 2)[:, None, None] * a[4]
              + (dxe / 2)[:, None, None] * a[5])
    dof = (conn[:, :, None] * 3 + np.arange(3)).reshape(-1, 24)
    n_node = coords.shape[0]
    rows = np.repeat(dof, 24, axis=1).ravel().astype(np.int32)
    cols = np.tile(dof, (1, 24)).ravel().astype(np.int32)
    k_csr = coo_matrix((kk_all.reshape(-1), (rows, cols)), shape=(3 * n_node, 3 * n_node)).tocsr()
    nodal_mass = config['rho_kg_m3'] * dxe * dye * dze / 8
    mass = np.bincount(dof.ravel(),
                       weights=np.repeat(nodal_mass, 24), minlength=3 * n_node)
    if mass.min() <= 0:
        raise ValueError('Zero lumped mass at some dof')

    tol = 1e-9
    clamp = config['clamp_width_m']
    fixed_nodes = (coords[:, 0] <= clamp + tol) | (coords[:, 1] <= clamp + tol)
    free = np.ones(3 * n_node, bool)
    free[np.repeat(fixed_nodes, 3)] = False
    free[3 * np.nonzero(np.isclose(coords[:, 0], lx, atol=tol))[0]] = False
    free[3 * np.nonzero(np.isclose(coords[:, 1], ly, atol=tol))[0] + 1] = False
    idx_free = np.nonzero(free)[0]
    kff = k_csr[free][:, free].tocsr()
    mf = mass[free]
    bound = mass_scaled_bound(kff, mf)

    impact_node = int(grid[0, ny, nx])
    impact_dof = 3 * impact_node + 2
    impact_local = int(np.searchsorted(idx_free, impact_dof))
    if idx_free[impact_local] != impact_dof:
        raise ValueError('Impact dof is constrained')
    if abs(coords[impact_node, 0] - lx) > tol or abs(coords[impact_node, 1] - ly) > tol:
        raise ValueError('Impact node is not at the symmetry corner')

    # Only top-surface nodes with a FREE vertical dof can carry contact load or
    # represent a sensor; the clamped strip fixes all three dofs of its nodes.
    top_all = np.nonzero(np.isclose(coords[:, 2], -h / 2., atol=1e-12))[0]
    top_nodes = top_all[free[3 * top_all + 2]]
    dist = np.hypot(coords[top_nodes, 0] - lx, coords[top_nodes, 1] - ly)
    order = np.argsort(dist)
    top_nodes, dist = top_nodes[order], dist[order]
    top_zdof = 3 * top_nodes + 2
    top_zlocal = np.searchsorted(idx_free, top_zdof)
    if not np.array_equal(idx_free[top_zlocal], top_zdof):
        raise ValueError('A top-surface z dof is constrained')

    dx_min = float(dxe.min())
    return dict(c=c, xs=xs, ys=ys, zs=zs, conn=conn, coords=coords, grid=grid,
                kff=kff, mf=mf, bound=bound,
                idx_free=idx_free, n_dof=3 * n_node, n_node=n_node,
                nx=nx, ny=ny, nz=nz, n_elem=len(conn), dx_min=dx_min,
                impact_node=impact_node, impact_local=impact_local,
                top_nodes=top_nodes, dist=dist, top_zlocal=top_zlocal,
                top_zlocal_by_node=dict(zip(top_nodes.tolist(), top_zlocal.tolist())))


def hertz_weights(b, radius):
    """Nodal weights of the Hertz pressure profile p(r) ~ sqrt(1-(r/a)^2), r <= a.

    The weights are normalised to sum to one, so the resultant equals the scalar
    Hertz force. `dist` is sorted, so the active set is found by binary search.
    """
    if radius <= 0:
        return b['top_zlocal'][:1], np.array([1.0])
    n_sel = int(np.searchsorted(b['dist'], radius, side='right'))
    n_sel = max(n_sel, 1)
    r = b['dist'][:n_sel]
    w = np.sqrt(np.maximum(0.0, 1.0 - (r / radius) ** 2))
    w = w / w.sum()
    return b['top_zlocal'][:n_sel], w


def run(config, h0=0.08, z0=0.06, growth=1.15, h_max=0.004, duration=None, out=None,
        dt_fixed=None, safety=0.7):
    """dt_fixed pins the time step, which is how the equivalence check against
    solve_impact_3d is kept reproducible: the two solvers use different (both
    valid) step-bound formulas, so only a pinned step makes them comparable.
    `safety` is the fraction of the stability limit actually used."""
    if out and Path(out).exists():
        raise FileExistsError('Refusing to overwrite existing results: ' + str(out))
    duration = float(duration if duration is not None else config['duration_s'])
    start = time.time()
    b = build_local(config, h0, z0, growth, h_max)
    kff, mf, bound = b['kff'], b['mf'], b['bound']
    lx, ly = config['quarter_x_m'], config['quarter_y_m']

    dt_limit_base = 2. / np.sqrt(bound)
    # The contact stiffens the system, so the plate-only step limit is not enough:
    # an explicit run sized that way diverges as soon as the penetration exceeds
    # the value assumed when sizing. Size from a penetration bound that holds for
    # any solution: if all the incident kinetic energy were stored in the contact,
    # 0.5*m*v^2 = 0.4*hertz*delta^2.5, so delta <= delta_max with
    ball = config['ball']
    r_ball = ball['diameter_m'] / 2
    m_ball = ball['rho_kg_m3'] * 4 * np.pi * r_ball ** 3 / 3
    proxy = config['contact_proxy']
    effective = 1. / ((1 - ball['nu'] ** 2) / ball['E_Pa'] + (1 - proxy['nu'] ** 2) / proxy['E_Pa'])
    hertz = 4. / 3 * effective * np.sqrt(r_ball) * config.get('contact_scale', 1.)
    v_ball = np.sqrt(2 * G * ball['height_m'])
    initial = 0.5 * m_ball * v_ball ** 2
    delta_max = (initial / (0.4 * hertz)) ** 0.4
    # The contact term tangent*(sum w^2/m + 1/m_ball) peaks at an INTERIOR
    # penetration, not at delta_max: a small patch has a small effective mass but a
    # small tangent, a large patch the reverse. Sizing at delta_max alone
    # under-estimates it and the run then diverges, so scan the range and take the
    # maximum. Each evaluation is a binary search plus a short weighted sum.
    contact_lam = 0.0
    for g_probe in np.geomspace(delta_max * 1e-4, delta_max, 240):
        loc_g, w_g = hertz_weights(b, np.sqrt(r_ball * g_probe))
        contact_lam = max(contact_lam, 1.5 * hertz * np.sqrt(g_probe)
                          * (float(np.sum(w_g ** 2 / mf[loc_g])) + 1. / m_ball))
    dt_limit = 2. / np.sqrt(bound + contact_lam)
    if dt_fixed:
        steps = max(1, int(round(duration / float(dt_fixed))))
    else:
        steps = int(np.ceil(duration / (safety * dt_limit)))
    dt = duration / steps
    patched = bool(config.get('distribute_contact', True))

    n_free = kff.shape[0]
    u = np.zeros(n_free)
    v = np.zeros(n_free)
    acc = np.zeros(n_free)
    f_ext = np.zeros(n_free)
    z_ball, za = 0.0, G
    ku = np.zeros(n_free)
    loc, wts = hertz_weights(b, 0.0)

    stride = max(1, int(round(config['output_dt_s'] / dt)))
    # Radial surface profile: a fixed-width window over the top nodes nearest the
    # impact point, so the saved array has constant shape as the patch grows.
    n_profile = int(min(600, len(b['top_nodes'])))
    profile_dof = b['top_zlocal'][:n_profile]
    profile_dist = b['dist'][:n_profile]
    sig, profile_rows = [], []
    peak_force = peak_gap = peak_w = peak_bound = 0.0
    peak_patch = 0.0
    max_drift = 0.0
    first_touch = first_end = None
    patch_size = 0.0

    def contact_state():
        """Force, gap and displacement measures for the current state.

        The gap is taken at the impact corner and the force is then spread over
        the Hertz patch with fixed weights. This is the variant whose results are
        step-convergent (see the README); measuring the gap with the weighted patch
        average instead was tried and diverges, so it is NOT used. Note the
        consequence: the applied load pattern and the gap are then not conjugate,
        so the energy check is only approximate and step refinement, not the
        energy drift, is the verification criterion.
        """
        w_c = float(u[b['impact_local']])
        gap = max(0.0, z_ball - w_c)
        force = hertz * gap ** 1.5
        return force, gap, w_c

    for step in range(steps + 1):
        t = step * dt
        acc[:] = (f_ext - ku) / mf
        force, gap, w_corner = contact_state()
        energy = (0.5 * float(np.dot(mf * v, v)) + 0.5 * float(np.dot(u, ku))
                  + 0.5 * m_ball * v_ball ** 2 + 0.4 * hertz * gap ** 2.5 - m_ball * G * z_ball)
        max_drift = max(max_drift, abs(energy - initial) / initial)
        peak_force = max(peak_force, force)
        peak_gap = max(peak_gap, gap)
        peak_w = max(peak_w, abs(w_corner))
        tangent = 1.5 * hertz * np.sqrt(gap) if gap > 0 else 0.0
        if tangent > 0:
            radius_now = np.sqrt(r_ball * gap)
            loc_now, w_now = hertz_weights(b, radius_now)
            # The contact term is the rank-one matrix tangent * w w^T, so its
            # spectral radius in the M^-1 K sense is tangent * (sum w_i^2/m_i +
            # 1/m_ball). Using a single node mass instead would diverge as the
            # mesh is refined.
            contact_lam = tangent * (float(np.sum(w_now ** 2 / mf[loc_now])) + 1. / m_ball)
            peak_patch = max(peak_patch, radius_now)
        else:
            contact_lam = 0.0
        peak_bound = max(peak_bound, dt * np.sqrt(bound + contact_lam))
        if force > 0 and first_touch is None:
            first_touch = t
        if force == 0 and first_touch is not None and first_end is None:
            first_end = t

        if step % stride == 0:
            sig.append([t, force, w_corner, z_ball, gap, energy, max_drift, patch_size,
                        float(np.dot(wts, u[loc]))])
            profile_rows.append([t, *[float(x) for x in u[profile_dof]]])

        if step == steps:
            break
        u += dt * v + 0.5 * dt * dt * acc
        z_ball += dt * v_ball + 0.5 * dt * dt * za
        w_new = float(u[b['impact_local']])
        gap_new = max(0.0, z_ball - w_new)
        force_new = hertz * gap_new ** 1.5
        patch_size = np.sqrt(r_ball * gap_new) if gap_new > 0 else 0.0
        f_ext[:] = 0.0
        if force_new > 0:
            if patched:
                np.add.at(f_ext, loc, force_new * wts)   # same pattern as the gap
                loc, wts = hertz_weights(b, patch_size)  # pattern for the next step
            else:
                f_ext[b['impact_local']] = force_new
        ku = kff @ u
        acc_new = (f_ext - ku) / mf
        za_new = G - force_new / m_ball
        v += 0.5 * dt * (acc + acc_new)
        v_ball += 0.5 * dt * (za + za_new)
        acc, za = acc_new, za_new

    signals = np.array(sig)
    summary = dict(model='locally refined 3D H8 explicit FE submodel',
                   graded=dict(h0_m=h0, z0_m=z0, growth=growth, h_max_m=h_max),
                   nx=b['nx'], ny=b['ny'], nz=b['nz'], elements=int(b['n_elem']),
                   nodes=int(b['n_node']), free_dofs=int(n_free),
                   min_element_size_m=b['dx_min'],
                   distributed_contact=patched,
                   dt_s=dt, steps=steps, duration_s=duration,
                   dt_upper_bound_s=dt_limit, dt_upper_bound_plate_only_s=dt_limit_base,
                   penetration_bound_m=delta_max,
                   ball_mass_kg=m_ball, incident_energy_J=initial,
                   implied_D_Nm=implied_plate_d(b['c'], config['thickness_m']).tolist(),
                   peak_contact_force_N=peak_force, peak_indentation_m=peak_gap,
                   peak_impact_point_displacement_m=peak_w,
                   peak_patch_radius_m=peak_patch,
                   first_contact_duration_s=None if first_end is None else first_end - first_touch,
                   energy_max_relative_error=max_drift, max_tangent_step_bound=peak_bound,
                   seconds=time.time() - start,
                   status='UNVALIDATED_MECHANICAL_PROXY_NOT_PZT_VOLTAGE')
    if peak_bound >= 2:
        raise ValueError('Contact time step bound violated')
    if not np.isfinite(signals).all():
        raise ValueError('Non-finite simulation output')
    if out:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=False)
        (out / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf8')
        (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
        np.savetxt(out / 'signals.csv', signals, delimiter=',',
                   header='time_s,contact_force_N,corner_w_m,ball_travel_m,indentation_m,'
                          'energy_J,energy_drift,patch_radius_m,patch_mean_w_m', comments='')
        np.savez_compressed(out / 'contact_patch.npz',
                            profile_dist=profile_dist,
                            profile_time=signals[:, 0],
                            profile_uz=np.array([r[1:] for r in profile_rows]))
    return summary


def contact_lcp(gap, inv_m, inv_m_ball, dt, iters=400, tol=1e-12):
    """Position-level LCP for the unilateral rigid-sphere contact.

    Find impulses lam >= 0 satisfying, at every candidate node,

        gap_i + dt * ( lam_i/m_i + sum_j lam_j/m_ball )  >=  0 ,  complementary.

    The effective matrix is diagonal plus a rank-one ball term. The near-contact
    nodal masses are orders of magnitude smaller than the ball mass, so the matrix
    is strongly diagonally dominant and a vectorised sweep with the rank-one sum
    lagged converges in a few tens of iterations. The impulses are what the
    sphere and the plate exchange; the pressure distribution is an OUTPUT, not an
    input, which is the whole point of this formulation.
    """
    lam = np.zeros_like(gap)
    total = 0.0
    diag = dt * (inv_m + inv_m_ball)
    scale = float(np.max(np.abs(gap))) + 1e-30
    for _ in range(iters):
        w = gap + dt * (lam * inv_m + total * inv_m_ball)
        new = np.maximum(0.0, lam - w / diag)
        delta = float(np.max(np.abs(new - lam)))
        lam = new
        total = float(lam.sum())
        if delta <= tol * scale:
            break
    return lam


def geometric_offsets(b, radius):
    """Sphere surface drop c_i = R - sqrt(R^2 - r_i^2) for the surface nodes.

    Non-penetration reads gap_i = w_i - zeta + c_i >= 0, with zeta the downward
    travel of the sphere centre from first touch. Returns the candidate window:
    nodes with c_i below the cut-off, so the active set can be found by search.
    """
    r = b['dist']
    inside = r < radius
    c = np.full_like(r, np.inf)
    c[inside] = radius - np.sqrt(radius ** 2 - r[inside] ** 2)
    return c


def run_rigid(config, h0=0.08, z0=0.06, growth=1.15, h_max=0.004, duration=None,
              out=None, safety=0.5, iters=400):
    """Rigid sphere, unilateral non-penetration, central difference + impulse LCP.

    Unlike the prescribed-Hertz variant this system is conservative: the
    constraint does no work, so the energy check is a valid verification and step
    refinement is a second one. The price is that the local indentation is now a
    genuine finite element quantity, so the mesh near the contact must resolve it.
    """
    if out and Path(out).exists():
        raise FileExistsError('Refusing to overwrite existing results: ' + str(out))
    duration = float(duration if duration is not None else config['duration_s'])
    start = time.time()
    b = build_local(config, h0, z0, growth, h_max)
    kff, mf, bound = b['kff'], b['mf'], b['bound']
    ball = config['ball']
    r_ball = ball['diameter_m'] / 2
    m_ball = ball['rho_kg_m3'] * 4 * np.pi * r_ball ** 3 / 3
    inv_m_ball = 1. / m_ball

    dt_limit = 2. / np.sqrt(bound)          # the constraint adds no stiffness
    steps = max(1, int(np.ceil(duration / (safety * dt_limit))))
    dt = duration / steps

    # Candidate window: the geometric offset only reaches zeta for r <= sqrt(2 R zeta).
    c_all = geometric_offsets(b, r_ball)
    cand = np.nonzero(np.isfinite(c_all) & (c_all <= config.get('contact_window_m', 4e-4)))[0]
    if cand.size == 0:
        raise ValueError('No surface node inside the contact window')
    c_cand = c_all[cand]
    loc_cand = b['top_zlocal'][cand]
    inv_m = 1. / mf[loc_cand]

    v_ball = np.sqrt(2 * G * ball['height_m'])
    initial = 0.5 * m_ball * v_ball ** 2

    n_free = kff.shape[0]
    u = np.zeros(n_free)
    v = np.zeros(n_free)
    zeta, zdot = 0.0, v_ball
    contact_live = False
    stride = max(1, int(round(config['output_dt_s'] / dt)))
    sig, patch_rows = [], []
    peak_force = peak_pen = peak_w = max_drift = 0.0
    first_touch = first_end = None
    energies = []
    for step in range(steps + 1):
        t = step * dt
        ku = kff @ u
        acc = -ku / mf
        energy = (0.5 * float(np.dot(mf * v, v)) + 0.5 * float(np.dot(u, ku))
                  + 0.5 * m_ball * zdot ** 2 - m_ball * G * zeta)
        max_drift = max(max_drift, abs(energy - initial) / initial)
        forces = np.zeros(cand.size)
        if contact_live:
            gap = u[loc_cand] - zeta + c_cand
            forces = contact_lcp(gap, inv_m, inv_m_ball, dt, iters=iters) / dt
        total_force = float(forces.sum())
        peak_force = max(peak_force, total_force)
        peak_w = max(peak_w, abs(float(u[b['impact_local']])))
        if step % stride == 0:
            energies.append(energy)
            sig.append([t, total_force, float(u[b['impact_local']]), zeta,
                        float(np.max(-(u[loc_cand] - zeta + c_cand))), energy, max_drift])
            patch_rows.append(list(forces))
        if step == steps:
            break
        # central difference (leapfrog) on plate and sphere, no contact forces yet
        v += dt * acc
        zdot += dt * G
        u += dt * v
        zeta += dt * zdot
        gap = u[loc_cand] - zeta + c_cand
        pen = float(np.min(gap))
        peak_pen = max(peak_pen, -pen)
        contact_live = pen < 0
        if contact_live:
            lam = contact_lcp(gap, inv_m, inv_m_ball, dt, iters=iters)
            v[loc_cand] += lam / mf[loc_cand]
            zdot -= float(lam.sum()) * inv_m_ball
            if first_touch is None:
                first_touch = t
        elif first_touch is not None and first_end is None:
            first_end = t

    signals = np.array(sig)
    energies = np.array(energies)
    summary = dict(model='locally refined 3D H8, rigid sphere + unilateral impulse contact',
                   graded=dict(h0_m=h0, z0_m=z0, growth=growth, h_max_m=h_max),
                   nx=b['nx'], ny=b['ny'], nz=b['nz'], elements=int(b['n_elem']),
                   nodes=int(b['n_node']), free_dofs=int(n_free),
                   min_element_size_m=b['dx_min'], contact_candidates=int(cand.size),
                   dt_s=dt, steps=steps, duration_s=duration,
                   dt_upper_bound_s=dt_limit, ball_mass_kg=m_ball,
                   incident_energy_J=initial,
                   implied_D_Nm=implied_plate_d(b['c'], config['thickness_m']).tolist(),
                   peak_contact_force_N=peak_force,
                   peak_penetration_m=peak_pen,
                   peak_surface_deflection_m=peak_w,
                   first_contact_duration_s=None if first_end is None else first_end - first_touch,
                   energy_max_relative_error=max_drift,
                   seconds=time.time() - start,
                   status='UNVALIDATED_MECHANICAL_PROXY_NOT_PZT_VOLTAGE')
    if max_drift > 1e-3:
        raise ValueError('Energy drift too large for a conservative contact: %.3e' % max_drift)
    if not np.isfinite(signals).all():
        raise ValueError('Non-finite simulation output')
    if out:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=False)
        (out / 'config.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf8')
        (out / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
        np.savetxt(out / 'signals.csv', signals, delimiter=',',
                   header='time_s,contact_force_N,centre_deflection_m,zeta_m,max_penetration_m,'
                          'energy_J,energy_drift', comments='')
        np.savez_compressed(out / 'contact_patch.npz',
                            r_m=b['dist'][cand], c_m=c_cand,
                            time=signals[:, 0], force=signals[:, 1],
                            nodal_force=np.array(patch_rows))
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, default=Path(__file__).with_name('simulation_config_3d.json'))
    p.add_argument('--out', type=Path, default=None)
    p.add_argument('--h0', type=float, default=0.08, help='smallest in-plane element (m)')
    p.add_argument('--z0', type=float, default=0.06, help='smallest through-thickness element (m)')
    p.add_argument('--growth', type=float, default=1.15)
    p.add_argument('--hmax', type=float, default=0.004)
    p.add_argument('--duration', type=float, default=None)
    p.add_argument('--verify', action='store_true')
    p.add_argument('--rigid', action='store_true',
                   help='use the rigid-sphere unilateral contact instead of the Hertz proxy')
    p.add_argument('--safety', type=float, default=0.7)
    a = p.parse_args()
    cfg = json.loads(a.config.read_text(encoding='utf8'))
    if a.verify:
        print('element_parts vs direct box stiffness, max relative error = %.3e'
              % verify_parts(material(cfg)))
    if a.rigid:
        print(json.dumps(run_rigid(cfg, h0=a.h0, z0=a.z0, growth=a.growth, h_max=a.hmax,
                                   duration=a.duration, out=a.out, safety=a.safety), indent=2))
    else:
        print(json.dumps(run(cfg, h0=a.h0, z0=a.z0, growth=a.growth, h_max=a.hmax,
                             duration=a.duration, out=a.out, safety=a.safety), indent=2))
