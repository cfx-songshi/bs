"""Two-level 3D study for the P2 drop-ball route; writes the archived metrics.

Level 1  locally refined submodel, rigid sphere with a unilateral non-penetration
         constraint (solve_impact_3d_local.run_rigid). The contact force history and
         the contact patch are solved, not prescribed.
Level 2  uniform global model driven by that force history, which yields the sensor
         strain at the 16 PZT positions (solve_impact_3d.run_prescribed).

The split exists because the two requirements conflict on one mesh: the contact
patch is ~0.2 mm across and needs a graded local mesh, while the far-field sensor
response needs a uniform mesh over a 250 x 200 mm quarter. Far-field strain is
governed by the resultant force history rather than by how it is distributed over
the patch, which is what makes the two-level split legitimate here.

Outputs land in the target directory, which must not already exist. Only the JSON
metrics are version controlled; the CSV/NPZ bulk stays local (see the repository
.gitignore).

Usage:
    python run_study_3d.py --out study_3d
    python run_study_3d.py --out study_3d --convergence
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

import solve_impact_3d as G
import solve_impact_3d_local as L

HERE = Path(__file__).resolve().parent


def run_submodel(cfg, out, h0, z0, growth, h_max, duration, safety):
    t0 = time.time()
    s = L.run_rigid(cfg, h0=h0, z0=z0, growth=growth, h_max=h_max,
                    duration=duration, safety=safety, out=out)
    s['wall_seconds'] = time.time() - t0
    return s


def run_global(cfg, out, nx, ny, nz, t_hist, f_hist, duration):
    t0 = time.time()
    s = G.run_prescribed(cfg, nx, ny, nz, t_hist, f_hist, duration=duration, out=out)
    s['wall_seconds'] = time.time() - t0
    return s


def sensor_peaks(sensor_csv, cfg_impact):
    """Peak magnitude per sensor per readout, plus the angle of the principal strain.

    cfg_impact is the (x, y) of the impact point, i.e. the symmetry corner of the
    modelled quarter, so the impact direction is measured from each sensor towards
    it.
    """
    rows = np.loadtxt(sensor_csv, delimiter=',', skiprows=1)
    out = {}
    for sid in sorted(set(rows[:, 1].astype(int))):
        m = rows[rows[:, 1] == sid]
        i_imp = int(np.argmax(np.abs(m[:, 9])))
        exx, eyy, exy = float(m[i_imp, 4]), float(m[i_imp, 5]), float(m[i_imp, 6])
        emean = 0.5 * (exx + eyy)
        rad = float(np.hypot(0.5 * (exx - eyy), exy))
        out[str(sid)] = dict(
            x_m=float(m[0, 2]), y_m=float(m[0, 3]),
            distance_from_impact_m=float(np.hypot(cfg_impact[0] - m[0, 2],
                                                  cfg_impact[1] - m[0, 3])),
            exx=exx, eyy=eyy, exy=exy,
            peak_invariant=float(m[i_imp, 7]),
            peak_axis_projection=float(m[np.argmax(np.abs(m[:, 8])), 8]),
            peak_impact_direction_projection=float(m[i_imp, 9]),
            principal_e1=emean + rad, principal_e2=emean - rad,
            principal_angle_deg=float(np.degrees(0.5 * np.arctan2(2 * exy, exx - eyy))),
            impact_direction_deg=float(np.degrees(np.arctan2(
                cfg_impact[1] - m[0, 3], cfg_impact[0] - m[0, 2]))))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, default=HERE / 'simulation_config_3d.json')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--duration', type=float, default=5e-4,
                   help='analysis time; P2 PDF p18 uses 5e-4 s')
    p.add_argument('--h0', type=float, default=2.5e-4, help='finest in-plane element (m)')
    p.add_argument('--z0', type=float, default=1.25e-4, help='finest through-thickness element (m)')
    p.add_argument('--growth', type=float, default=1.15)
    p.add_argument('--hmax', type=float, default=4e-3)
    p.add_argument('--safety', type=float, default=0.5)
    p.add_argument('--mesh', type=int, nargs=3, default=[100, 80, 4], metavar=('NX', 'NY', 'NZ'))
    p.add_argument('--convergence', action='store_true',
                   help='also run the mesh and step refinement sweep')
    a = p.parse_args()
    if a.out.exists():
        raise FileExistsError('Refusing to overwrite existing results: %s' % a.out)
    cfg = json.loads(a.config.read_text(encoding='utf8'))
    started = time.strftime('%Y-%m-%d %H:%M:%S')
    a.out.mkdir(parents=True)

    print('[1/2] locally refined submodel (rigid sphere, unilateral contact)', flush=True)
    sub = run_submodel(cfg, a.out / 'submodel', a.h0, a.z0, a.growth, a.hmax,
                       a.duration, a.safety)
    print('      peak force %.2f N, drift %.2e, %.0f s'
          % (sub['peak_contact_force_N'], sub['energy_max_relative_error'],
             sub['wall_seconds']), flush=True)

    sig = np.loadtxt(a.out / 'submodel' / 'signals.csv', delimiter=',', skiprows=1)
    t_hist, f_hist = sig[:, 0], sig[:, 1]

    print('[2/2] global uniform model driven by that force history', flush=True)
    glo = run_global(cfg, a.out / 'global', a.mesh[0], a.mesh[1], a.mesh[2],
                     t_hist, f_hist, a.duration)
    print('      centre deflection %.1f um, %.0f s'
          % (glo['peak_impact_point_displacement_m'] * 1e6, glo['wall_seconds']), flush=True)

    sensors = sensor_peaks(a.out / 'global' / 'sensors.csv',
                           (cfg['quarter_x_m'], cfg['quarter_y_m']))

    metrics = dict(
        generated=started,
        reference_case=(
            'P2 SMS论文01 PDF p15-p18: 8 mm tungsten steel sphere, 160 mm drop, '
            'perimeter-clamped plate. Numerical reference, not a validated specimen.'),
        level1_submodel=sub,
        level2_global=glo,
        cross_check_deflection=dict(
            submodel_peak_m=sub['peak_surface_deflection_m'],
            global_peak_m=glo['peak_impact_point_displacement_m'],
            relative_difference=abs(sub['peak_surface_deflection_m']
                                    - glo['peak_impact_point_displacement_m'])
            / glo['peak_impact_point_displacement_m']),
        sensor_peaks=sensors,
        sensor_orientation_dependence=dict(
            note='peak of eps(theta) over theta for the sensor nearest the impact',
            **{k: dict(
                distance_from_impact_m=sensors[k]['distance_from_impact_m'],
                peak_impact_direction_projection=sensors[k]['peak_impact_direction_projection'],
                peak_axis_projection_at_0deg=sensors[k]['peak_axis_projection'],
                ratio_impact_over_axis=abs(sensors[k]['peak_impact_direction_projection'])
                / max(abs(sensors[k]['peak_axis_projection']), 1e-30),
                principal_angle_deg=sensors[k]['principal_angle_deg'])
               for k in sensors}),
        status='UNVALIDATED_MECHANICAL_PROXY_NOT_PZT_VOLTAGE')

    if a.convergence:
        print('[extra] mesh and time-step refinement sweep', flush=True)
        sweep = []
        for h0, z0 in [(5e-4, 2.5e-4), (2.5e-4, 1.25e-4), (1.25e-4, 6e-5)]:
            s = L.run_rigid(cfg, h0=h0, z0=z0, growth=a.growth, h_max=a.hmax,
                            duration=a.duration, safety=a.safety)
            sweep.append(dict(h0_m=h0, z0_m=z0, elements=s['elements'],
                              contact_candidates=s['contact_candidates'],
                              peak_force_N=s['peak_contact_force_N'],
                              peak_surface_deflection_m=s['peak_surface_deflection_m'],
                              peak_penetration_m=s['peak_penetration_m'],
                              energy_drift=s['energy_max_relative_error']))
            print('      h0=%.3f mm -> force %.2f N, drift %.2e'
                  % (h0 * 1e3, s['peak_contact_force_N'],
                     s['energy_max_relative_error']), flush=True)
        step_sweep = []
        for safety in [0.5, 0.25]:
            s = L.run_rigid(cfg, h0=1.25e-4, z0=6e-5, growth=a.growth, h_max=a.hmax,
                            duration=a.duration, safety=safety)
            step_sweep.append(dict(safety=safety, steps=s['steps'],
                                   peak_force_N=s['peak_contact_force_N'],
                                   peak_surface_deflection_m=s['peak_surface_deflection_m'],
                                   energy_drift=s['energy_max_relative_error']))
        metrics['convergence'] = dict(mesh_sweep=sweep, step_sweep=step_sweep)

    (a.out / 'study_metrics.json').write_text(
        json.dumps(metrics, indent=2), encoding='utf8')
    print('wrote %s' % (a.out / 'study_metrics.json'), flush=True)
    return metrics


if __name__ == '__main__':
    main()
