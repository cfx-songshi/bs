"""Measure the Abaqus A0 speed with the same estimator the in-house model used.

`check_3d_dispersion.py` compares the in-house 3D solver against the 2D model and
against Rayleigh-Lamb theory, taking k(f) from the space-time phase slope of the
stored surface line. This script feeds the Abaqus run through that identical
extractor, so the three numbers are comparable: a difference is a difference in the
models, not in the post-processing.

The Abaqus side is the surface line written by
`abaqus/read_odb_surface.py` (needs Abaqus's own Python, hence the two-step flow):

    abaqus python abaqus/read_odb_surface.py job.odb surface.npz --nx 500 --ny 4 --nz 4 --lx 0.5
    python check_abaqus_dispersion.py

Only A0 is compared: a normal line force excites S0 far more weakly, and under this
excitation S0 has no spectral peak at all.
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'guided_wave_v2'))
import dispersion as D                     # noqa: E402
import dispersion_check as C               # noqa: E402

FREQS = np.arange(85e3, 116e3, 1e3)
F0 = 100e3


def group_from_slope(freqs, k, half_hz=6e3):
    out = np.full(len(freqs), np.nan)
    for i, f0 in enumerate(freqs):
        mask = np.abs(freqs - f0) <= half_hz
        if mask.sum() >= 4:
            out[i] = 2 * np.pi / np.polyfit(freqs[mask], k[mask], 1)[0]
    return out


def main():
    m = D.plane_strain_stiffness(**{k: v for k, v in D.T300.items() if k != 'rho'})
    h, rho = D.THICKNESS, D.T300['rho']
    c_an = np.array([min(b['phase_velocity_m_s'] for b in D.branches_at(f, h, m, rho))
                     for f in FREQS])
    cg_an = np.array([min(b['group_velocity_m_s'] for b in D.branches_at(f, h, m, rho)
                         if b['group_velocity_m_s']) for f in FREQS])
    i0 = int(np.argmin(np.abs(FREQS - F0)))

    cases = [
        ('in-house 500x4x4 @ abq dt', HERE / 'out_line_abaqusdt' / 'wavefield.npz'),
        ('in-house 1000x4x8 @ abq dt', HERE / 'out_line_1000x4x8_abaqusdt' / 'wavefield.npz'),
        ('abaqus C3D8R 500x4x4 dp', HERE / 'abaqus_line500_c3d8r_dp_surface.npz'),
        ('abaqus C3D8 500x4x4', HERE / 'abaqus_line500_c3d8_surface.npz'),
        ('abaqus C3D8 1000x4x8', HERE / 'abaqus_line1000_c3d8_surface.npz'),
    ]

    rows = []
    print('A0 相速度，同一提取方法（场输出时空谱相位斜率），解析 %.1f m/s @100 kHz'
          % c_an[i0])
    print()
    print('%-28s %10s %9s %10s %9s' % ('case', 'c_p@100k', 'vs解析', 'c_g@100k', 'vs解析'))
    print('-' * 72)
    for label, path in cases:
        if not path.exists():
            print('%-28s  缺少 %s' % (label, path.name))
            continue
        k = C.wave_numbers(str(path), FREQS)
        cp = 2 * np.pi * FREQS / k
        cg = group_from_slope(FREQS, k)
        rows.append(dict(case=label, path=path.name,
                         c_phase_100k_m_s=float(cp[i0]),
                         phase_error_vs_analytic=float(abs(cp[i0] - c_an[i0]) / c_an[i0]),
                         c_group_100k_m_s=float(cg[i0]),
                         group_error_vs_analytic=float(abs(cg[i0] - cg_an[i0]) / cg_an[i0]),
                         max_phase_error_in_band=float(np.max(np.abs(cp - c_an) / c_an))))
        print('%-28s %10.1f %8.2f%% %10.1f %8.2f%%'
              % (label, cp[i0], 100 * rows[-1]['phase_error_vs_analytic'],
                 cg[i0], 100 * rows[-1]['group_error_vs_analytic']))

    print()
    print('解析 c_p@100k = %.1f m/s, c_g@100k = %.1f m/s'
          % (c_an[i0], min(b['group_velocity_m_s'] for b in D.branches_at(F0, h, m, rho)
                           if b['group_velocity_m_s'])))

    (HERE / 'abaqus_dispersion_check.json').write_text(
        json.dumps(dict(frequency_band_khz=[85, 115],
                        analytic_phase_100k_m_s=float(c_an[i0]),
                        analytic_group_100k_m_s=float(min(
                            b['group_velocity_m_s'] for b in D.branches_at(F0, h, m, rho)
                            if b['group_velocity_m_s'])),
                        cases=rows), indent=2), encoding='utf8')
    print()
    print('wrote abaqus_dispersion_check.json')


if __name__ == '__main__':
    main()
