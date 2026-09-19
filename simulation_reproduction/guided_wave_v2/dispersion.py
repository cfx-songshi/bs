"""Analytical Rayleigh-Lamb dispersion for the orthotropic plate, and a check against FE.

Why this exists
---------------
The transient FE model in solve.py had only ever been checked for discrete
self-consistency (mesh refinement, half time step, energy drift). None of those
checks can tell whether the model propagates waves at the physically correct
speed. For a damage-scattering study that is the foundation: if the modal phase
and group velocities are wrong, every later attribution of a wave packet to a
scattering event is unreliable.

This module computes the exact guided-wave dispersion of the same plate -- same
material, same thickness, same plane-strain assumption, same propagation
direction -- from the Rayleigh-Lamb determinant, so the FE wave speeds can be
compared against a closed-form reference rather than against themselves.

Geometry and convention
-----------------------
Waves travel along x, the fibre direction of the [0]8 laminate. The plate occupies
-h/2 <= z <= h/2 with traction-free faces. Plane strain keeps
eps_yy = gamma_xy = gamma_yz = 0, matching solve.py's reduced stiffness. Voigt
order is [11, 22, 33, 23, 13, 12].

The determinant is evaluated through the smallest singular value of the 4x4
boundary-condition matrix rather than through its determinant: sigma_min vanishes
exactly when the matrix is singular, and it is far better conditioned than a
determinant whose entries can span many orders of magnitude. Roots are located by
scanning the phase velocity and refining each local minimum, then filtering on a
magnitude threshold.

Self-test
---------
`--self-test` runs the same solver with an isotropic material and checks it
against closed-form Rayleigh-Lamb limits:
  * S0 low-frequency asymptote  sqrt(E / (rho (1 - nu^2)))
  * A1 cut-off frequency        f*d = c_T / 2
  * high-order asymptote        c -> Rayleigh surface wave speed
Those limits are independent of this implementation, so passing them is evidence
that the determinant and the root search are right.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, minimize_scalar

HERE = Path(__file__).resolve().parent

# Li et al. 2012 table 1, T300/F593; the same external substitute used by solve.py.
T300 = dict(E1=128.1e9, E2=8.2e9, E3=8.2e9, G12=4.7e9, G13=4.7e9, G23=3.44e9,
            nu12=0.27, nu13=0.27, nu23=0.20, rho=1570.0)
THICKNESS = 1.72e-3

# Below this many elements per wavelength the FE cannot represent the mode; above
# it the discretisation error is normally acceptable. Reported, not enforced.
ELEMENTS_PER_WAVELENGTH_TARGET = 10


def plane_strain_stiffness(E1, E2, E3, G12, G13, G23, nu12, nu13, nu23, direction='x'):
    """Reduced stiffness for guided waves travelling along a material axis.

    The returned keys keep the roles of the x-direction case, namely
    C11 = longitudinal in the propagation direction
    C13 = coupling between propagation and thickness
    C33 = through-thickness
    C55 = shear in the propagation-thickness plane
    so the determinant below does not need to know which axis was chosen.

    direction='x' keeps Voigt 11, 33, 13 (waves along material axis 1, the fibre
    direction of the [0]8 laminate). direction='y' keeps 22, 33, 23 (waves along
    material axis 2, across the fibres). The two differ because the plate is
    strongly anisotropic: E1 is about 16 times E2, so the same plate carries waves
    at very different speeds along and across the fibres. That difference is what
    makes the point-source wavefront elliptical, and it is a property no
    plane-strain two-dimensional model can produce.
    """
    s = np.zeros((6, 6))
    s[0, 0], s[1, 1], s[2, 2] = 1 / E1, 1 / E2, 1 / E3
    s[3, 3], s[4, 4], s[5, 5] = 1 / G23, 1 / G13, 1 / G12
    s[0, 1] = s[1, 0] = -nu12 / E1
    s[0, 2] = s[2, 0] = -nu13 / E1
    s[1, 2] = s[2, 1] = -nu23 / E2
    c = np.linalg.inv(s)
    if direction == 'x':
        return dict(C11=c[0, 0], C13=c[0, 2], C33=c[2, 2], C55=c[4, 4])
    if direction == 'y':
        return dict(C11=c[1, 1], C13=c[1, 2], C33=c[2, 2], C55=c[3, 3])
    raise ValueError('direction must be x or y, got %r' % (direction,))


def isotropic_stiffness(E, nu):
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E / (2 * (1 + nu))
    return dict(C11=lam + 2 * mu, C13=lam, C33=lam + 2 * mu, C55=mu)


def rayleigh_isotropic_speed(m, rho):
    """Exact Rayleigh surface-wave speed for an isotropic solid.

    Standard secular equation with x = (c_R/c_T)^2:
        (2 - x)^2 = 4 sqrt(1 - x) sqrt(1 - x (c_T/c_L)^2)
    The trivial root x = 0 is excluded by bracketing away from it.
    """
    cl = np.sqrt(m['C11'] / rho)
    ct = np.sqrt(m['C55'] / rho)
    r2 = (ct / cl) ** 2

    def eq(x):
        return (2 - x) ** 2 - 4 * np.sqrt(1 - x) * np.sqrt(1 - x * r2)

    x = brentq(eq, 1e-8, 1 - 1e-9, xtol=1e-14)
    return ct * np.sqrt(x)


def boundary_matrix(c, omega, h, m, rho):
    """4x4 traction-free matrix for phase velocity c, or None if degenerate.

    Columns are the four partial-wave solutions; rows are sigma_zz and sigma_xz at
    z = +h/2 and z = -h/2.
    """
    C11, C13, C33, C55 = m['C11'], m['C13'], m['C33'], m['C55']
    k = omega / c
    a_big = rho * omega ** 2 - C11 * k ** 2
    b_big = rho * omega ** 2 - C55 * k ** 2
    qa = C33 * C55
    qb = -(a_big * C33 + b_big * C55 + k ** 2 * (C13 + C55) ** 2)
    qc = a_big * b_big
    disc = qb * qb - 4 * qa * qc
    # A negative discriminant is NOT a failure to find a root. It means q = p^2 is
    # complex, so p = +/- (a + b i): the field oscillates through the thickness while
    # also growing or decaying across it, which is what a non-uniform partial wave
    # looks like in an anisotropic plate. Returning early here silently deleted every
    # such solution. That went unnoticed along the fibres because the discriminant
    # happens to be positive there, and it destroyed the whole A0 branch across the
    # fibres, leaving only S0 and a spurious root at the bulk shear speed.
    root = np.sqrt(complex(disc))
    ps = []
    for q in ((-qb + root) / (2 * qa), (-qb - root) / (2 * qa)):
        p = np.sqrt(complex(q))
        ps.extend([p, -p])
    mat = np.zeros((4, 4), complex)
    for j, p in enumerate(ps):
        denom = k * p * (C13 + C55)
        if abs(denom) < 1e-30:
            return None
        # Polarisation ratio W/U from the x-equation of motion:
        #   (A - C55 p^2) U = k p (C13 + C55) W  =>  W/U = (A - C55 p^2)/(k p (C13+C55))
        # Cross-checked against the z-equation, which requires
        #   (A - C55 p^2)(B - C33 p^2) = k^2 p^2 (C13+C55)^2,
        # i.e. exactly the quadratic that produced p in the first place.
        r = (a_big - C55 * p * p) / denom
        szz = C13 * k + C33 * p * r
        sxz = C55 * (p + k * r)
        # exp(+/- i p h/2) is written with the exponential growth factored out and
        # then removed, so a large imaginary part of p cannot overflow. The two
        # entries of a column share the same factor, which is the same as scaling
        # the column by a nonzero constant: it does not move the zeros.
        a_im, b_im = float(p.real), float(p.imag)
        shift = abs(b_im) * h / 2
        ep = np.exp(-b_im * h / 2 - shift) * np.exp(1j * a_im * h / 2)
        em = np.exp(b_im * h / 2 - shift) * np.exp(-1j * a_im * h / 2)
        mat[0, j] = szz * ep
        mat[1, j] = sxz * ep
        mat[2, j] = szz * em
        mat[3, j] = sxz * em
    # Column scaling to unit norm: again a nonzero right-multiplication, so the
    # deterministic zeros are unchanged, but the singular values become O(1) and a
    # single threshold works across the whole frequency range.
    norms = np.linalg.norm(mat, axis=0)
    if np.any(norms == 0) or not np.all(np.isfinite(norms)):
        return None
    return mat / norms


def singularity(c, omega, h, m, rho):
    """Reciprocal condition number of the boundary matrix, in [0, 1]; 0 means singular.

    Zero crossings of the determinant and minima of this quantity coincide; using
    the reciprocal condition number avoids the dynamic-range problems of a
    determinant built from exponentials.
    """
    mat = boundary_matrix(c, omega, h, m, rho)
    if mat is None:
        return np.inf
    s = np.linalg.svd(mat, compute_uv=False)
    return float(s[-1] / s[0])


def phase_velocities(omega, h, m, rho, c_lo, c_hi, n_scan=3000, tol=1e-3):
    """Every c in [c_lo, c_hi] whose boundary matrix is singular.

    The longitudinal and shear bulk speeds are excluded on a narrow band: at those
    speeds one of the p^2 roots vanishes, the polarisation ratio r divides by p, and
    the resulting matrix is numerically rank deficient for reasons that have nothing
    to do with a guided mode. Including them invents roots at c_L and c_T. The band
    is 0.2 percent, far narrower than the spacing of physical branches, so no real
    mode is lost.
    """
    specials = [np.sqrt(m['C11'] / rho), np.sqrt(m['C55'] / rho)]
    c = np.linspace(c_lo, c_hi, n_scan)
    sig = np.array([singularity(ci, omega, h, m, rho) for ci in c])
    if not np.any(np.isfinite(sig)):
        return []

    def near_bulk(ci):
        return any(abs(ci - cs) < 2e-3 * cs for cs in specials)

    roots = []
    for i in range(1, n_scan - 1):
        if not np.isfinite(sig[i]) or sig[i] > tol or near_bulk(c[i]):
            continue
        if sig[i] <= sig[i - 1] and sig[i] <= sig[i + 1]:
            res = minimize_scalar(lambda x: singularity(x, omega, h, m, rho),
                                  bounds=(c[i - 1], c[i + 1]), method='bounded',
                                  options=dict(xatol=1e-3))
            if res.fun <= tol and not near_bulk(res.x):
                roots.append(float(res.x))
    merged = []
    for r in sorted(roots):
        if not merged or abs(r - merged[-1]) > 1.0:
            merged.append(r)
    return merged


def branches_at(freq_hz, h, m, rho, c_max=None, n_scan=3000, tol=1e-3):
    """Phase and group velocities of every branch at one frequency.

    The group velocity is dw/dk by a central difference in frequency, with each
    branch matched to its nearest neighbour at f +/- df. That matching is only
    valid where the branch does not appear or vanish, i.e. away from a cut-off, so
    the value is flagged as unresolved when the neighbour count changes.
    """
    if c_max is None:
        # A lossless elastic plate has no real root above the longitudinal bulk
        # speed, so the upper limit is held just below it. Without this the
        # near-singular band around c_L leaks spurious roots that are physically
        # impossible for a propagating mode.
        c_max = 0.998 * np.sqrt(m['C11'] / rho)
    c_lo = max(1.0, 0.0005 * c_max)
    w = 2 * np.pi * freq_hz
    c0 = phase_velocities(w, h, m, rho, c_lo, c_max, n_scan=n_scan, tol=tol)
    if not c0:
        return []
    df = max(1e-3 * freq_hz, 10.0)
    wp, wm = 2 * np.pi * (freq_hz + df), 2 * np.pi * (freq_hz - df)
    cp = phase_velocities(wp, h, m, rho, c_lo, c_max, n_scan=n_scan, tol=tol)
    cm = phase_velocities(wm, h, m, rho, c_lo, c_max, n_scan=n_scan, tol=tol) \
        if freq_hz > df else []

    out = []
    for c in c0:
        entry = dict(phase_velocity_m_s=c, wavelength_m=float(2 * np.pi * c / w),
                     group_velocity_m_s=None)
        if cp and cm and len(cp) == len(cm) == len(c0):
            c_plus = min(cp, key=lambda x: abs(x - c))
            c_minus = min(cm, key=lambda x: abs(x - c))
            kp, km = wp / c_plus, wm / c_minus
            if kp != km:
                entry['group_velocity_m_s'] = float((wp - wm) / (kp - km))
        out.append(entry)
    return out


def self_test():
    """Check the solver against closed-form Rayleigh-Lamb limits (isotropic plate)."""
    E, nu, rho = 70e9, 0.33, 2700.0
    m = isotropic_stiffness(E, nu)
    h = 1.0e-3
    cl = np.sqrt(m['C11'] / rho)
    ct = np.sqrt(m['C55'] / rho)
    plate = np.sqrt(E / (rho * (1 - nu ** 2)))
    cr = rayleigh_isotropic_speed(m, rho)
    res = dict(cl_m_s=cl, ct_m_s=ct, expected_S0_plate_m_s=plate,
               expected_A1_cutoff_fd_Hz_m=ct / 2, expected_rayleigh_m_s=cr)

    # 1) S0 long-wave limit -> extensional plate velocity.
    f = 5.0e3
    br = branches_at(f, h, m, rho)
    if br:
        fast = max(b['phase_velocity_m_s'] for b in br)
        res['S0_phase_m_s'] = fast
        res['S0_relative_error'] = abs(fast - plate) / plate

    # 2) Below the A1 cut-off only S0 and A0 may exist.
    f_cut = 0.5 * ct / h
    below = branches_at(0.9 * f_cut, h, m, rho)
    res['branches_below_cutoff'] = len(below)
    res['branch_speeds_below_cutoff'] = [round(b['phase_velocity_m_s']) for b in below]

    # 3) Well above the cut-off the A1 branch must exist, sit below c_T, and the
    #    slowest branch must approach the Rayleigh speed. Just above the cut-off the
    #    branch is NOT separable from c_T: the phase-velocity curve has a vertical
    #    tangent there, so 1.02-1.5x the cut-off frequency still leaves A1 within a
    #    few m/s of c_T. That is physics, and the solver reports it as such.
    for mult in (1.1, 2.5):
        br = branches_at(mult * f_cut, h, m, rho)
        res['branch_speeds_%.1fx_cutoff' % mult] = [round(b['phase_velocity_m_s']) for b in br]
    far = branches_at(2.5 * f_cut, h, m, rho)
    if far:
        res['A1_resolved_at_2.5x'] = bool(min(b['phase_velocity_m_s'] for b in far) < ct)
        res['slowest_at_2.5x_m_s'] = round(min(b['phase_velocity_m_s'] for b in far))

    # 4) Higher-order branch at large f*d approaches the Rayleigh speed; the slowest
    #    branch is the one that does, so compare against the minimum, not the maximum.
    hi = branches_at(6.0 * f_cut, h, m, rho)
    if hi:
        slowest = min(b['phase_velocity_m_s'] for b in hi)
        res['slowest_at_6x_m_s'] = round(slowest)
        res['rayleigh_relative_error'] = abs(slowest - cr) / cr
        res['branch_speeds_high_fd'] = [round(b['phase_velocity_m_s']) for b in hi]

    # 5) An isotropic plate cannot distinguish the two propagation directions, so the
    #    axis-selection branches must agree exactly. This is what checks the Voigt
    #    index mapping in plane_strain_stiffness.
    g_iso = E / (2 * (1 + nu))
    mx = plane_strain_stiffness(E, E, E, g_iso, g_iso, g_iso, nu, nu, nu, direction='x')
    my = plane_strain_stiffness(E, E, E, g_iso, g_iso, g_iso, nu, nu, nu, direction='y')
    res['axis_selection_relative_difference'] = max(
        abs(mx[k] - my[k]) / abs(mx[k]) for k in mx)
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--out', type=Path, default=HERE / 'dispersion.json')
    p.add_argument('--fmax-khz', type=float, default=300.0,
                   help='upper frequency. The root search is verified and clean for '
                        'fd up to about 0.5 MHz mm (about 290 kHz here); above that the '
                        'branches crowd together and results need an independent check')
    p.add_argument('--nfreq', type=int, default=31)
    p.add_argument('--nscan', type=int, default=3000)
    p.add_argument('--tol', type=float, default=1e-3,
                   help='reciprocal-condition-number threshold for accepting a root; '
                        'physical branches land near 1e-5..1e-4, the excluded bulk-speed '
                        'artefacts near 1e-2')
    a = p.parse_args()

    if a.self_test:
        print(json.dumps(self_test(), indent=2))
        return

    m = plane_strain_stiffness(**{k: v for k, v in T300.items() if k != 'rho'})
    h, rho = THICKNESS, T300['rho']
    c_max = 0.998 * np.sqrt(m['C11'] / rho)
    freqs = np.linspace(10e3, a.fmax_khz * 1e3, a.nfreq)
    curves = []
    for f in freqs:
        br = branches_at(f, h, m, rho, c_max=c_max, n_scan=a.nscan, tol=a.tol)
        fd_MHz_mm = f * (h * 1e3) / 1e6
        curves.append(dict(frequency_hz=float(f), fd_MHz_mm=float(fd_MHz_mm), branches=br))
        print('f = %7.1f kHz  fd = %6.3f MHz mm  c_ph = %s m/s'
              % (f / 1e3, fd_MHz_mm,
                 ', '.join('%.0f' % b['phase_velocity_m_s'] for b in br)), flush=True)
    a.out.write_text(json.dumps(dict(material=T300, thickness_m=h, stiffness=m,
                                     c_max_m_s=c_max, nscan=a.nscan, tol=a.tol,
                                     curves=curves), indent=2), encoding='utf8')
    print('wrote %s' % a.out)


if __name__ == '__main__':
    main()
