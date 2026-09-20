"""Compare the Abaqus line-source runs against the in-house 3D solver.

Both models are the same physical case: a 500 x 20 x 1.72 mm T300/F593 strip, loaded
normally on both faces at x = 100 mm, free everywhere else, run for 220 us. The
Abaqus side comes from the odb through `abaqus/read_odb_receivers.py`.

Three things this comparison has to get right, each of which produced a wrong number
on the first attempt:

* Compare within the direct arrival only. The strip is short enough that the echo off
  the x = 0 free end reaches the near receiver at about 160 us with an amplitude
  comparable to the direct packet, so a whole-record L2 is mostly reflection
  interference. With the whole record, the Abaqus/in-house L2 came out 1.24, which
  says nothing about either solver.
* Match the time step. Abaqus runs at its own stable increment, 9.554e-08 s; the
  in-house solver is more conservative (a Gershgorin bound times a 0.7 factor) and
  came out at 7.373e-08 s. Numerical dispersion depends on dt, and that alone moved
  the in-house peak by 4.1% and its L2 against itself by 3.3%. The reference used
  here is therefore the in-house run at Abaqus's step (`--dt-scale 1.2955`), with the
  in-house run at its own step kept as a sensitivity row.

* Normalise the energy residual by the energy scale. ETOTAL in a free-plate explicit
  run is a near-zero balance residual (~5e-14 J) against internal energies of order
  1e-10 J, so dividing its variation by its own mean gives a meaningless 88%; the
  meaningful figure is its variation relative to peak ALLIE.
* Report the windowed RMS next to the peak. Both histories are written every ~1 us,
  about ten samples per carrier cycle, so the largest sample sits up to 5% below the
  true peak depending on where the sampling lands; the RMS over the window is not
  sensitive to that, and the two disagree by more than 5% for the full-integration
  runs here.

Read `check_abaqus_dispersion.py` alongside this: the phase velocity, measured with
the estimator that verified the in-house solver, is the criterion the project trusts,
and it is where the agreement is strongest.
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REFERENCE = HERE / 'out_line_abaqusdt' / 'wavefield.npz'
OWN_DT = HERE / 'out_line_500x4x4' / 'wavefield.npz'
ABAQUS = {
    'abaqus C3D8R single': HERE / 'abaqus_line500_c3d8r_history.json',
    'abaqus C3D8': HERE / 'abaqus_line500_c3d8_history.json',
}
OUT = HERE / 'abaqus_line500_compare.json'

NX, NY, NZ = 500, 4, 4
RECV_X = (0.18, 0.32)
DX = 0.5 / NX
# Direct arrival only, in seconds: the packet leaves the source at x = 100 mm and
# lasts 50 us, and the first free-end echo arrives near 160 us at the near receiver
# and past the end of the record at the far one.
WINDOWS = ((30e-6, 120e-6), (110e-6, 220e-6))


def node_label(x):
    """The node id the generator gives the top-surface receiver at x, width centre.

    Reproducing the generator's numbering here is deliberate: if these ids are not in
    the odb, the two models are not the mesh they are claimed to be and the
    comparison should stop rather than produce numbers.
    """
    return 1 + int(round(x / DX)) + (NX + 1) * (NY // 2 + (NY + 1) * NZ)


def load_history(path):
    data = json.loads(Path(path).read_text(encoding='utf8'))
    regions = data['steps']['WAVE']
    traces, energy = {}, {}
    for info in regions.values():
        if info['node_label'] is not None and 'U3' in info['series']:
            traces[info['node_label']] = np.array(info['series']['U3'], float)
        elif info['node_label'] is None:
            for key in ('ALLAE', 'ALLIE', 'ALLKE', 'ETOTAL'):
                if key in info['series']:
                    energy[key] = np.array(info['series'][key], float)
    return traces, energy


def resample(series, t):
    """Sample an Abaqus (time, value) series, which is coarser, onto the in-house grid."""
    return np.interp(t, series[:, 0], series[:, 1])


def best_lag(t, ref, sig, max_lag=5e-6):
    lags = np.linspace(-max_lag, max_lag, 2001)
    res = [np.linalg.norm(np.interp(t, t + L, ref) - sig) / np.linalg.norm(sig)
           for L in lags]
    i = int(np.argmin(res))
    return float(lags[i]), float(res[i])


def group_delay(t, u1, u2, window, lo=60e-6, hi=100e-6):
    """Delay that carries the direct packet of u1 onto that of u2.

    A restricted cross-correlation rather than a peak-to-peak difference: the
    envelope peak of a dispersive packet is not a wavefront marker. Still an
    estimate from two points, so read it as a consistency check, not as a validated
    group velocity -- `check_abaqus_dispersion.py` shows the slope method and this one
    disagree by more than the models do.
    """
    m = (t >= window[0]) & (t <= window[1])
    best, bd = None, None
    for D in np.linspace(lo, hi, 4001):
        r = np.linalg.norm(np.interp(t[m], t + D, u1) - u2[m]) / np.linalg.norm(u2[m])
        if bd is None or r < bd:
            best, bd = D, r
    return float(best), float(bd)


def main():
    labels = [node_label(x) for x in RECV_X]

    ref_npz = np.load(REFERENCE)
    t = ref_npz['t']
    own_npz = np.load(OWN_DT)
    cases = {}
    cases['inhouse (Abaqus dt)'] = {lab: ref_npz['signal'][:, n]
                                    for n, lab in enumerate(labels)}
    cases['inhouse (own dt)'] = {lab: np.interp(t, own_npz['t'], own_npz['signal'][:, n])
                                 for n, lab in enumerate(labels)}

    energies = {}
    for name, path in ABAQUS.items():
        if not path.exists():
            print('missing %s, skipping %s' % (path.name, name))
            continue
        traces, energy = load_history(path)
        missing = [lab for lab in labels if lab not in traces]
        if missing:
            raise SystemExit('%s is missing receiver nodes %s; the deck and the '
                             'in-house run are then not the same mesh' % (name, missing))
        cases[name] = {lab: resample(traces[lab], t) for lab in labels}
        energies[name] = energy

    baseline = cases['inhouse (Abaqus dt)']

    report = {'model': {'nx': NX, 'ny': NY, 'nz': NZ, 'dx_m': DX,
                        'receivers_x_m': list(RECV_X), 'receiver_nodes': labels,
                        'direct_arrival_windows_s': [list(w) for w in WINDOWS]},
              'cases': [], 'energy': {}, 'sources': {'reference': str(REFERENCE)}}
    print('%-22s %-8s %9s %9s %9s %9s %8s %8s' %
          ('case', 'recv[m]', 'peak[nm]', 'rms[nm]', 'peak/ref', 'rms/ref',
           'L2', 'lag[us]'))
    for name, series in cases.items():
        for n, (x, lab) in enumerate(zip(RECV_X, labels)):
            m = (t >= WINDOWS[n][0]) & (t <= WINDOWS[n][1])
            u, ur, tw = series[lab][m], baseline[lab][m], t[m]
            lag, resid = best_lag(tw, ur, u, max_lag=3e-6)
            entry = dict(case=name, x_m=x, node=lab,
                         peak_m=float(np.abs(u).max()),
                         peak_time_s=float(tw[np.argmax(np.abs(u))]),
                         peak_ratio_to_reference=float(np.abs(u).max() / np.abs(ur).max()),
                         rms_m=float(np.sqrt(np.mean(u ** 2))),
                         rms_ratio_to_reference=float(np.sqrt(np.mean(u ** 2) / np.mean(ur ** 2))),
                         l2_relative_difference=float(np.linalg.norm(u - ur) / np.linalg.norm(ur)),
                         best_lag_s=lag, aligned_residual=resid)
            report['cases'].append(entry)
            print('%-22s %-8.2f %9.4f %9.4f %9.3f %9.3f %8.4f %8.3f' %
                  (name, x, entry['peak_m'] * 1e9, entry['rms_m'] * 1e9,
                   entry['peak_ratio_to_reference'], entry['rms_ratio_to_reference'],
                   entry['l2_relative_difference'], lag * 1e6))

    print()
    report['direct_packet_group_delay'] = {}
    for name, series in cases.items():
        d, resid = group_delay(t, series[labels[0]], series[labels[1]], WINDOWS[1])
        report['direct_packet_group_delay'][name] = dict(
            delay_s=d, speed_m_s=(RECV_X[1] - RECV_X[0]) / d, residual=resid)
        print('%-22s direct-packet delay %.3f us -> %.1f m/s (residual %.4f)'
              % (name, d * 1e6, (RECV_X[1] - RECV_X[0]) / d, resid))

    print()
    for name, energy in energies.items():
        live = energy['ALLIE'][:, 1] > 0
        after = energy['ETOTAL'][:, 0] > 60e-6
        allie_peak = float(np.max(energy['ALLIE'][:, 1]))
        entry = dict(
            allae_max_j=float(np.max(energy['ALLAE'][:, 1])),
            allie_max_j=allie_peak,
            hourglass_ratio_peak=float(np.max(energy['ALLAE'][:, 1]) / allie_peak),
            hourglass_ratio_worst_sample=float(np.max(
                energy['ALLAE'][live, 1] / energy['ALLIE'][live, 1])),
            etotal_variation_after_burst_j=float(np.ptp(energy['ETOTAL'][after, 1])),
            etotal_variation_over_peak_allie=float(
                np.ptp(energy['ETOTAL'][after, 1]) / allie_peak),
        )
        report['energy'][name] = entry
        print('%-22s ALLAE/ALLIE peak %.2f%% (worst sample %.2f%%), ETOTAL variation '
              'after 60 us %.2e J = %.3f%% of peak ALLIE'
              % (name, 100 * entry['hourglass_ratio_peak'],
                 100 * entry['hourglass_ratio_worst_sample'],
                 entry['etotal_variation_after_burst_j'],
                 100 * entry['etotal_variation_over_peak_allie']))

    meta = json.loads((REFERENCE.parent / 'summary.json').read_text(encoding='utf8'))
    report['inhouse_reference'] = dict(dt_s=meta['dt_s'], steps=meta['steps'],
                                       energy_relative_drift=meta['energy_relative_drift'],
                                       elements_per_A0_wavelength=meta['elements_per_A0_wavelength'])
    OUT.write_text(json.dumps(report, indent=2), encoding='utf8')
    print('\nwrote %s' % OUT.name)


if __name__ == '__main__':
    main()
