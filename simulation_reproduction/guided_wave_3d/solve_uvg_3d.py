"""Three-dimensional explicit guided-wave FE for the orthotropic plate.

Why three dimensions
--------------------
The existing model in guided_wave_v2 is plane strain: it assumes the field does not
vary across the width, so it cannot represent a circular wavefront from a patch-like
source, spreading of the beam, reflection from the side edges, or the way a local
delamination scatters in the width direction. Those are exactly the effects an
experiment sees, so this solver drops the assumption.

What it computes
----------------
Eight-node hexahedra, full 2x2x2 Gauss integration, lumped mass, explicit central
difference -- the same scheme family as the 2D model and as impact_3d_v1. The
material is the full 3D orthotropic stiffness of T300/F593, not a reduced
plane-strain block, so the out-of-plane and shear couplings are present.

Two source modes are provided on purpose:
  line   a force distributed along the whole width, one node thick in x. This is the
         3D counterpart of the 2D line force, so its response must reproduce the
         plane-strain result and can therefore be checked against the analytical
         Rayleigh-Lamb dispersion. It is the verification mode.
  point  a single node in the middle of the plate, which is the closest cheap
         stand-in for a small PZT patch. This is the application mode.

A delamination is modelled the same way as in 2D: the nodes on the mid-surface
inside the damaged rectangle are duplicated, the upper half keeps the copy and the
lower half keeps the original, so the two halves share nothing over that area while
the crack tips stay connected. No contact, no cohesion, no friction.

Element size guidance
---------------------
At 100 kHz the A0 wavelength is about 12.7 mm and the S0 wavelength about 90 mm, so
the element size is governed by A0. The default keeps at least ten elements per A0
wavelength, matching the resolution criterion that the 2D verification used.

Cost
----
The line-source verification strip is tiny (the width only needs a few elements
because the field does not vary across it). A point-source run over a full plate is
large; the mesh is a parameter and the printed element/dof counts should be read
before starting one.

Usage
-----
    python solve_uvg_3d.py --mode line --nx 500 --ny 4 --nz 4 --out out_line
    python solve_uvg_3d.py --mode point --nx 200 --ny 200 --nz 4 --out out_point
"""
import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np
from scipy.sparse import coo_matrix, diags

HERE = Path(__file__).resolve().parent

# Li et al. 2012 table 1, T300/F593. Voigt order [11, 22, 33, 23, 13, 12].
MATERIAL = dict(E1=128.1e9, E2=8.2e9, E3=8.2e9, G12=4.7e9, G13=4.7e9, G23=3.44e9,
                nu12=0.27, nu13=0.27, nu23=0.20, rho=1570.0)
THICKNESS = 1.72e-3
FREQ_HZ = 100e3
CYCLES = 5
DURATION = 220e-6
HANN_T = CYCLES / FREQ_HZ


def stiffness3d(mat=MATERIAL):
    """Full 3D orthotropic stiffness (6x6), SI."""
    e1, e2, e3 = mat['E1'], mat['E2'], mat['E3']
    s = np.zeros((6, 6))
    s[0, 0], s[1, 1], s[2, 2] = 1 / e1, 1 / e2, 1 / e3
    s[3, 3], s[4, 4], s[5, 5] = 1 / mat['G23'], 1 / mat['G13'], 1 / mat['G12']
    s[0, 1] = s[1, 0] = -mat['nu12'] / e1
    s[0, 2] = s[2, 0] = -mat['nu13'] / e1
    s[1, 2] = s[2, 1] = -mat['nu23'] / e2
    return np.linalg.inv(s)


def h8_stiffness(dx, dy, dz, C):
    """24x24 stiffness of a rectangular H8 element with full 2x2x2 Gauss."""
    g = 1.0 / np.sqrt(3.0)
    sign = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
                     [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], float)
    jdet = dx * dy * dz / 8.0
    ke = np.zeros((24, 24))
    for xi in (-g, g):
        for eta in (-g, g):
            for zeta in (-g, g):
                dndx = np.zeros(8)
                dndy = np.zeros(8)
                dndz = np.zeros(8)
                for a in range(8):
                    sx, sy, sz = sign[a]
                    dndx[a] = sx * (1 + eta * sy) * (1 + zeta * sz) / (4 * dx)
                    dndy[a] = sy * (1 + xi * sx) * (1 + zeta * sz) / (4 * dy)
                    dndz[a] = sz * (1 + xi * sx) * (1 + eta * sy) / (4 * dz)
                B = np.zeros((6, 24))
                for a in range(8):
                    c = 3 * a
                    B[0, c] = dndx[a]
                    B[1, c + 1] = dndy[a]
                    B[2, c + 2] = dndz[a]
                    B[3, c + 1] = dndz[a]
                    B[3, c + 2] = dndy[a]
                    B[4, c] = dndz[a]
                    B[4, c + 2] = dndx[a]
                    B[5, c] = dndy[a]
                    B[5, c + 1] = dndx[a]
                ke += B.T @ C @ B * jdet
    return ke


def build(nx, ny, nz, lx, ly, thickness, C, rho, damage=None, batch=20000):
    """Assemble K and the lumped mass for a regular grid, with optional delamination.

    `damage` is (x0, x1, y0, y1) in metres. Mid-surface nodes strictly inside that
    rectangle get a duplicate: elements above the mid plane use the copy, elements
    below use the original, so the two halves share nothing over the damaged area
    while the crack-tip nodes remain shared. The remapping is done with boolean masks
    rather than a Python dictionary, which matters at point-source mesh sizes.
    """
    dx, dy, dz = lx / nx, ly / ny, thickness / nz
    nzmid = nz // 2

    def nid(i, j, k):
        return (i + (nx + 1) * (j + (ny + 1) * k)).astype(np.int64)

    ii, jj, kk = np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing='ij')
    ii, jj, kk = ii.ravel(), jj.ravel(), kk.ravel()
    nelem = ii.size

    corners = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                        [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]])
    conn = np.empty((nelem, 8), np.int64)
    for a, (di, dj, dk) in enumerate(corners):
        conn[:, a] = nid(ii + di, jj + dj, kk + dk)

    nnode = (nx + 1) * (ny + 1) * (nz + 1)
    if damage is not None:
        x0, x1, y0, y1 = damage
        xs = np.arange(nx + 1) * dx
        ys = np.arange(ny + 1) * dy
        inside_x = (xs > x0 + 1e-12) & (xs < x1 - 1e-12)
        inside_y = (ys > y0 + 1e-12) & (ys < y1 - 1e-12)
        dup_mask = np.zeros((nx + 1, ny + 1), bool)
        dup_mask[np.ix_(np.where(inside_x)[0], np.where(inside_y)[0])] = True
        # Duplicate numbering is assigned in index order so it is reproducible.
        dup_index = -np.ones((nx + 1, ny + 1), np.int64)
        di_idx, dj_idx = np.where(dup_mask)
        if di_idx.size:
            dup_index[di_idx, dj_idx] = nnode + np.arange(di_idx.size)
            nnode += di_idx.size

        upper = np.where(kk >= nzmid)[0]
        if upper.size and di_idx.size:
            base_i = ii[upper][:, None] + corners[:4, 0][None, :]
            base_j = jj[upper][:, None] + corners[:4, 1][None, :]
            split = dup_mask[base_i, base_j]
            original = nid(base_i, base_j, nzmid)
            conn[np.ix_(upper, np.arange(4))] = np.where(
                split, dup_index[base_i, base_j], original)

    ndof = 3 * nnode
    dof = (conn[:, :, None] * 3 + np.arange(3)).reshape(nelem, 24)
    ke = h8_stiffness(dx, dy, dz, C)

    rows, cols, vals = [], [], []
    for s in range(0, nelem, batch):
        e = min(nelem, s + batch)
        d = dof[s:e]
        rows.append(np.repeat(d, 24, axis=1).ravel())
        cols.append(np.tile(d, (1, 24)).ravel())
        vals.append(np.tile(ke.ravel(), d.shape[0]))
    K = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                   shape=(ndof, ndof)).tocsr()
    mass = np.bincount(dof.ravel(), weights=np.full(dof.size, rho * dx * dy * dz / 8.0),
                       minlength=ndof)
    return dict(K=K, mass=mass, nnode=nnode, nelem=nelem, ndof=ndof, dx=dx, dy=dy, dz=dz,
                conn=conn, nx=nx, ny=ny, nz=nz, lx=lx, ly=ly)


def source_dofs(mesh, mode, x_src, y_frac=0.5, dx_force=None):
    """Nodes and per-node force amplitude for the requested source mode."""
    nx, ny, nz = mesh['nx'], mesh['ny'], mesh['nz']
    i0 = int(round(x_src / mesh['dx']))
    i0 = min(max(i0, 0), nx)
    top, bot = nz, 0

    def nid(i, j, k):
        return i + (nx + 1) * (j + (ny + 1) * k)

    if mode == 'line':
        # Every node along y on both faces, so the load is uniform across the width.
        # Amplitude per node equals the line density times the node spacing, which
        # makes the total 1 N per metre of width -- the same excitation the 2D model
        # uses, which is what allows a direct comparison.
        amp = 1.0 * mesh['dy']
        js = np.arange(ny + 1)
        nodes = np.concatenate([nid(i0, js, top), nid(i0, js, bot)])
        vals = np.concatenate([np.full(ny + 1, amp), np.full(ny + 1, amp)])
    elif mode == 'point':
        j0 = int(round(y_frac * ny))
        nodes = np.array([nid(i0, j0, top), nid(i0, j0, bot)])
        vals = np.array([1.0, 1.0])
    else:
        raise ValueError('unknown source mode: %s' % mode)
    return nodes * 3 + 2, vals


def run(mesh, mode, x_src, duration=DURATION, out=None, dt_scale=1.0,
        receivers_x=(0.18, 0.32), frame_dt=2e-6, y_recv_frac=0.5):
    """Explicit central-difference solve; returns time history and surface frames."""
    K, mass = mesh['K'], mesh['mass']
    ndof = mesh['ndof']
    bound = float(np.max(np.asarray(abs(K).sum(axis=1)).ravel() / mass))
    dt_limit = 2.0 / np.sqrt(bound)
    nt = int(np.ceil(duration / (0.7 * dt_limit * dt_scale)))
    dt = duration / nt

    force = np.zeros(ndof)
    src, amp = source_dofs(mesh, mode, x_src)
    force[src] = amp

    nx, ny, nz = mesh['nx'], mesh['ny'], mesh['nz']
    top = nz

    def nid(i, j, k):
        return i + (nx + 1) * (j + (ny + 1) * k)

    rec_nodes = [nid(min(max(int(round(rx / mesh['dx'])), 0), nx), int(round(y_recv_frac * ny)), top)
                 for rx in receivers_x]
    rec_dofs = np.array(rec_nodes) * 3 + 2
    surf = (np.arange((nx + 1) * (ny + 1)) + (nx + 1) * (ny + 1) * top) * 3 + 2

    fine = np.linspace(0, HANN_T, 200001)
    norm = np.max(np.abs(np.sin(2 * np.pi * FREQ_HZ * fine) * np.sin(np.pi * fine / HANN_T) ** 2))

    sample = max(1, int(round(1e-6 / dt)))
    stride = max(1, int(round(frame_dt / dt)))
    u = np.zeros(ndof)
    old = u.copy()
    ts, signals, frames, ft, energies = [], [], [], [], []
    A = diags(1 / mass) @ K
    for n in range(nt + 1):
        t = n * dt
        val = (np.sin(2 * np.pi * FREQ_HZ * t) * np.sin(np.pi * t / HANN_T) ** 2 / norm
               if t <= HANN_T else 0.0)
        if n % sample == 0:
            ts.append(t)
            signals.append(u[rec_dofs].copy())
        if n % stride == 0:
            frames.append(u[surf].reshape(ny + 1, nx + 1)[int(round(ny / 2))].copy())
            ft.append(t)
        new = 2 * u - old + dt * dt * (force * val / mass - A @ u)
        if n % stride == 0 and t > 1.2 * HANN_T:
            vh = (new - u) / dt
            energies.append(0.5 * np.dot(mass * vh, vh) + 0.5 * np.dot(new, K @ u))
        old, u = u, new

    energies = np.array(energies)
    drift = float(np.ptp(energies) / np.mean(energies)) if energies.size else np.nan
    meta = dict(mode=mode, mesh='%dx%dx%d' % (nx, ny, nz),
                elements=int(mesh['nelem']), nodes=int(mesh['nnode']), dofs=int(ndof),
                dx_m=mesh['dx'], dy_m=mesh['dy'], dz_m=mesh['dz'],
                dt_s=dt, dt_upper_bound_s=dt_limit, steps=nt, duration_s=duration,
                elements_per_A0_wavelength=12.7e-3 / mesh['dx'],
                energy_relative_drift=drift)
    result = dict(t=np.array(ts), signal=np.array(signals), frames=np.array(frames),
                  frame_t=np.array(ft), x=np.arange(nx + 1) * mesh['dx'])
    if out:
        Path(out).mkdir(parents=True, exist_ok=True)
        np.savez_compressed(Path(out) / 'wavefield.npz', **result)
        (Path(out) / 'summary.json').write_text(json.dumps(meta, indent=2), encoding='utf8')
    return result, meta


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['line', 'point'], default='line')
    p.add_argument('--nx', type=int, default=500)
    p.add_argument('--ny', type=int, default=4)
    p.add_argument('--nz', type=int, default=4)
    p.add_argument('--lx', type=float, default=0.5)
    p.add_argument('--ly', type=float, default=None)
    p.add_argument('--x-src', type=float, default=0.1)
    p.add_argument('--duration', type=float, default=DURATION)
    p.add_argument('--damage', type=float, nargs=4, default=None,
                   metavar=('X0', 'X1', 'Y0', 'Y1'))
    p.add_argument('--out', type=Path, default=None)
    a = p.parse_args()

    ly = a.ly if a.ly is not None else a.lx
    C = stiffness3d()
    t0 = time.time()
    mesh = build(a.nx, a.ny, a.nz, a.lx, ly, THICKNESS, C, MATERIAL['rho'],
                 damage=tuple(a.damage) if a.damage else None)
    print('装配完成: %d 单元, %d 节点, %d DOF, %.1f s'
          % (mesh['nelem'], mesh['nnode'], mesh['ndof'], time.time() - t0), flush=True)
    result, meta = run(mesh, a.mode, a.x_src, duration=a.duration, out=a.out)
    print(json.dumps(meta, indent=2), flush=True)


if __name__ == '__main__':
    main()
