"""Compare the Abaqus line-source runs against the in-house 3D solver.

Both models are the same physical case: a 500 x 20 x 1.72 mm T300/F593 strip, loaded
normally on both faces at x = 100 mm, free everywhere else, run for 220 us. The
Abaqus side comes from the odb through `abaqus/read_odb_receivers.py`.

Four things this comparison has to get right, each of which produced a wrong number on
the first attempt:

* Compare within the direct arrival only. The strip is short enough that the echo off
  the x = 0 free end reaches the near receiver at about 160 us with an amplitude
  comparable to the direct packet, so a whole-record L2 is mostly reflection
  interference. With the whole record, the Abaqus/in-house L2 came out 1.24, which
  says nothing about either solver.
* Match the time step. Abaqus runs at its own stable increment; the in-house solver is
  more conservative (a Gershgorin bound times a 0.7 factor), so at 500x4x4 it came out
  30% smaller. Numerical dispersion depends on dt, and that alone moved the in-house
  peak by 4.1% and its L2 against itself by 3.3%. Each mesh here is therefore
  referenced to the in-house run at that mesh's Abaqus step, with the in-house run at
  its own step kept as a sensitivity row.
* Normalise the energy residual by the energy scale. ETOTAL in a free-plate explicit
  run is a near-zero balance residual (~5e-14 J) against internal energies of order
  1e-10 J, so dividing its variation by its own mean gives a meaningless 88%; the
  meaningful figure is its variation relative to peak ALLIE.
* Report the windowed RMS next to the peak. Both histories are written every ~1 us,
  about ten samples per carrier cycle, so the largest sample sits up to 5% below the
  true peak depending on where the sampling lands; the RMS over the window is not
  sensitive to that, and the two disagree by more than 5% for the full-integration
  runs here.

The last block answers a separate question: whether the residual waveform difference
shrinks with mesh refinement, and whether it does so faster or slower than each
solver's own mesh sensitivity. That is the yardstick, because a bare L2 number has no
scale without knowing how much the same solver moves when the mesh changes.

Read `check_abaqus_dispersion.py` alongside this: the phase velocity, measured with
the estimator that verified the in-house solver, is the criterion the project trusts,
and it is where the agreement is strongest.
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / 'abaqus_line500_compare.json'

LENGTH = 0.5
RECV_X = (0.18, 0.32)
# Direct arrival only, in seconds: the packet leaves the source at x = 100 mm and
# lasts 50 us, and the first free-end echo arrives near 160 us at the near receiver
# and past the end of the record at the far one.
WINDOWS = ((30e-6, 120e-6), (110e-6, 220e-6))
DURATION = 220e-6

MESHES = [
    dict(name='500x4x4', nx=500, ny=4, nz=4,
         reference=HERE / 'out_line_abaqusdt' / 'wavefield.npz',
         own_dt=HERE / 'out_line_500x4x4' / 'wavefield.npz',
         abaqus={'abaqus C3D8R': HERE / 'abaqus_line500_c3d8r_history.json',
                 'abaqus C3D8': HERE / 'abaqus_line500_c3d8_history.json'}),
    dict(name='1000x4x8', nx=1000, ny=4, nz=8,
         reference=HERE / 'out_line_1000x4x8_abaqusdt' / 'wavefield.npz',
         own_dt=HERE / 'out_line_1000x4x8' / 'wavefield.npz',
         abaqus={'abaqus C3D8': HERE / 'abaqus_line1000_c3d8_history.json'}),
]


def node_label(nx, ny, nz, x):
    """The node id the generator gives the top-surface receiver at x, width centre.

    Reproducing the generator's numbering here is deliberate: if these ids are not in
    the odb, the two models are not the mesh they are claimed to be and the comparison
    should stop rather than produce numbers.
    """
    return 1 + int(round(x / (LENGTH / nx))) + (nx + 1) * (ny // 2 + (ny + 1) * nz)


def load_history(path):
    data = json.loads(Path(path).read_text(encoding='utf8'))
    traces, energy = {}, {}
    for info in data['steps']['WAVE'].values():
        if info['node_label'] is not None and 'U3' in info['series']:
            traces[info['node_label']] = np.array(info['series']['U3'], float)
        elif info['node_label'] is None:
            for key in ('ALLAE', 'ALLIE', 'ALLKE', 'ETOTAL'):
                if key in info['series']:
                    energy[key] = np.array(info['series'][key], float)
    return traces, energy


def best_lag(t, ref, sig, max_lag=3e-6):
    lags = np.linspace(-max_lag, max_lag, 2001)
    res = [np.linalg.norm(np.interp(t, t + L, ref) - sig) / np.linalg.norm(sig)
           for L in lags]
    i = int(np.argmin(res))
    return float(lags[i]), float(res[i])


def group_delay(t, u1, u2, window, lo=60e-6, hi=100e-6):
    """Delay that carries the direct packet of u1 onto that of u2.

    A restricted cross-correlation rather than a peak-to-peak difference: the envelope
    peak of a dispersive packet is not a wavefront marker. Still an estimate from two
    points, so read it as a consistency check, not as a validated group velocity.
    """
    m = (t >= window[0]) & (t <= window[1])
    best, bd = None, None
    for D in np.linspace(lo, hi, 4001):
        r = np.linalg.norm(np.interp(t[m], t + D, u1) - u2[m]) / np.linalg.norm(u2[m])
        if bd is None or r < bd:
            best, bd = D, r
    return float(best), float(bd)


def window_metrics(t, u, ur, lo, hi):
    m = (t >= lo) & (t <= hi)
    u, ur, tw = u[m], ur[m], t[m]
    lag, resid = best_lag(tw, ur, u)
    return dict(peak_m=float(np.abs(u).max()),
                peak_ratio_to_reference=float(np.abs(u).max() / np.abs(ur).max()),
                rms_m=float(np.sqrt(np.mean(u ** 2))),
                rms_ratio_to_reference=float(np.sqrt(np.mean(u ** 2) / np.mean(ur ** 2))),
                l2_relative_difference=float(np.linalg.norm(u - ur) / np.linalg.norm(ur)),
                best_lag_s=lag, aligned_residual=resid)


def mesh_cases(spec):
    """Reference, own-dt sensitivity and the Abaqus runs, all sampled on the reference
    time base."""
    labels = [node_label(spec['nx'], spec['ny'], spec['nz'], x) for x in RECV_X]
    ref = np.load(spec['reference'])
    t = ref['t']
    cases = {'in-house (Abaqus dt)': {lab: ref['signal'][:, n] for n, lab in enumerate(labels)}}
    own = np.load(spec['own_dt'])
    cases['in-house (own dt)'] = {lab: np.interp(t, own['t'], own['signal'][:, n])
                                  for n, lab in enumerate(labels)}
    energies = {}
    for name, path in spec['abaqus'].items():
        if not path.exists():
            print('missing %s, skipping %s' % (path.name, name))
            continue
        traces, energy = load_history(path)
        missing = [lab for lab in labels if lab not in traces]
        if missing:
            raise SystemExit('%s is missing receiver nodes %s; the deck and the in-house '
                             'run are then not the same mesh' % (name, missing))
        cases[name] = {lab: np.interp(t, traces[lab][:, 0], traces[lab][:, 1])
                       for lab in labels}
        energies[name] = energy
    return labels, t, cases, energies


def energy_metrics(energy):
    live = energy['ALLIE'][:, 1] > 0
    after = energy['ETOTAL'][:, 0] > 60e-6
    allie_peak = float(np.max(energy['ALLIE'][:, 1]))
    return dict(allae_max_j=float(np.max(energy['ALLAE'][:, 1])),
                allie_max_j=allie_peak,
                hourglass_ratio_peak=float(np.max(energy['ALLAE'][:, 1]) / allie_peak),
                hourglass_ratio_worst_sample=float(np.max(
                    energy['ALLAE'][live, 1] / energy['ALLIE'][live, 1])),
                etotal_variation_after_burst_j=float(np.ptp(energy['ETOTAL'][after, 1])),
                etotal_variation_over_peak_allie=float(
                    np.ptp(energy['ETOTAL'][after, 1]) / allie_peak))


def main():
    t_common = np.arange(0, DURATION + 1e-12, 1e-6)
    report = {'model': {'length_m': LENGTH, 'receivers_x_m': list(RECV_X),
                        'direct_arrival_windows_s': [list(w) for w in WINDOWS]},
              'meshes': [], 'energy': {}, 'mesh_convergence': []}

    common = {}
    for spec in MESHES:
        labels, t, cases, energies = mesh_cases(spec)
        entry = dict(name=spec['name'], nx=spec['nx'], ny=spec['ny'], nz=spec['nz'],
                     dx_m=LENGTH / spec['nx'], receiver_nodes=labels,
                     elements_per_A0_wavelength=12.7e-3 / (LENGTH / spec['nx']),
                     cases=[])
        print('=== %s (dx = %.3f mm, %.1f elements per A0 wavelength) ==='
              % (spec['name'], 1000 * LENGTH / spec['nx'],
                 12.7e-3 / (LENGTH / spec['nx'])))
        print('%-22s %-8s %9s %9s %9s %9s %8s %8s' %
              ('case', 'recv[m]', 'peak[nm]', 'rms[nm]', 'peak/ref', 'rms/ref', 'L2', 'lag[us]'))
        baseline = cases['in-house (Abaqus dt)']
        for name, series in cases.items():
            for n, lab in enumerate(labels):
                e = window_metrics(t, series[lab], baseline[lab], *WINDOWS[n])
                e.update(case=name, x_m=RECV_X[n], node=lab)
                entry['cases'].append(e)
                print('%-22s %-8.2f %9.4f %9.4f %9.3f %9.3f %8.4f %8.3f' %
                      (name, RECV_X[n], e['peak_m'] * 1e9, e['rms_m'] * 1e9,
                       e['peak_ratio_to_reference'], e['rms_ratio_to_reference'],
                       e['l2_relative_difference'], e['best_lag_s'] * 1e6))
        for name, energy in energies.items():
            em = energy_metrics(energy)
            report['energy']['%s %s' % (spec['name'], name)] = em
            print('%-22s ALLAE/ALLIE peak %.2f%% (worst sample %.2f%%), ETOTAL variation '
                  'after 60 us %.2e J = %.3f%% of peak ALLIE'
                  % (name, 100 * em['hourglass_ratio_peak'],
                     100 * em['hourglass_ratio_worst_sample'],
                     em['etotal_variation_after_burst_j'],
                     100 * em['etotal_variation_over_peak_allie']))
        meta = json.loads((spec['reference'].parent / 'summary.json').read_text(encoding='utf8'))
        entry['inhouse_reference'] = dict(dt_s=meta['dt_s'], steps=meta['steps'],
                                          energy_relative_drift=meta['energy_relative_drift'])
        # Two receivers cannot pin down a group velocity, and this estimator is here
        # only to show that it moves with the mesh far more than the models differ --
        # see check_abaqus_dispersion.py for the phase velocity, which is quotable.
        entry['direct_packet_group_delay'] = {}
        for name, series in cases.items():
            d, resid = group_delay(t, series[labels[0]], series[labels[1]], WINDOWS[1])
            entry['direct_packet_group_delay'][name] = dict(
                delay_s=d, speed_m_s=(RECV_X[1] - RECV_X[0]) / d, residual=resid)
            print('%-22s direct-packet delay %.3f us -> %.1f m/s (residual %.4f)'
                  % (name, d * 1e6, (RECV_X[1] - RECV_X[0]) / d, resid))
        report['meshes'].append(entry)
        # For the cross-mesh rows everything goes onto one 1 us grid, the spacing the
        # Abaqus history output uses; the meshes otherwise have slightly different
        # sample spacing and cannot be differenced directly.
        common[spec['name']] = {name: {lab: np.interp(t_common, t, series[lab])
                                       for lab in labels} for name, series in cases.items()}
        print()

    # Does the Abaqus-versus-in-house difference shrink with refinement, and does it
    # shrink faster than each solver's own mesh sensitivity? Comparing the gap against
    # those two self-differences is the only way to say whether L2 = 0.57 is a
    # disagreement or normal mesh-level movement.
    labels_by_mesh = {s['name']: [node_label(s['nx'], s['ny'], s['nz'], x) for x in RECV_X]
                      for s in MESHES}
    pairs = [
        ('in-house 500 vs 1000 (in-house mesh sensitivity)',
         ('500x4x4', 'in-house (Abaqus dt)'), ('1000x4x8', 'in-house (Abaqus dt)')),
        ('Abaqus C3D8 500 vs 1000 (Abaqus mesh sensitivity)',
         ('500x4x4', 'abaqus C3D8'), ('1000x4x8', 'abaqus C3D8')),
        ('Abaqus C3D8 vs in-house, 500 mesh',
         ('500x4x4', 'abaqus C3D8'), ('500x4x4', 'in-house (Abaqus dt)')),
        ('Abaqus C3D8 vs in-house, 1000 mesh',
         ('1000x4x8', 'abaqus C3D8'), ('1000x4x8', 'in-house (Abaqus dt)')),
    ]
    print('=== convergence, all traces on a common 1 us grid ===')
    print('%-52s %-8s %9s %9s %8s' % ('comparison', 'recv[m]', 'rms a/b', 'L2', 'lag[us]'))
    for label, (a_mesh, a_case), (b_mesh, b_case) in pairs:
        for n, x in enumerate(RECV_X):
            ua = common[a_mesh][a_case][labels_by_mesh[a_mesh][n]]
            ub = common[b_mesh][b_case][labels_by_mesh[b_mesh][n]]
            m = (t_common >= WINDOWS[n][0]) & (t_common <= WINDOWS[n][1])
            lag, _ = best_lag(t_common[m], ub[m], ua[m], max_lag=5e-6)
            row = dict(comparison=label, x_m=x, case_a=a_case, mesh_a=a_mesh,
                       case_b=b_case, mesh_b=b_mesh,
                       rms_ratio=float(np.sqrt(np.mean(ua[m] ** 2) / np.mean(ub[m] ** 2))),
                       l2_relative_difference=float(np.linalg.norm(ua[m] - ub[m]) / np.linalg.norm(ub[m])),
                       best_lag_s=lag)
            report['mesh_convergence'].append(row)
            print('%-52s %-8.2f %9.3f %9.4f %8.3f' %
                  (label, x, row['rms_ratio'], row['l2_relative_difference'], lag * 1e6))
        print()

    OUT.write_text(json.dumps(report, indent=2), encoding='utf8')
    print('wrote %s' % OUT.name)


if __name__ == '__main__':
    main()
