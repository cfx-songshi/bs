"""Cross-check the 3D solver against the 2D model and the analytical dispersion.

The line source is the bridge. It is uniform across the plate width, so the
three-dimensional response must collapse onto the plane-strain one; if it does not,
the extra dimension or the 3D material law has introduced something the 2D model
does not have. Comparing all three at matched element sizes separates that question
from plain mesh resolution.

Every entry is processed with the same wavenumber extraction
(guided_wave_v2.dispersion_check.wave_numbers), so a difference in the numbers is a
difference in the models and not in the post-processing.

Only the antisymmetric A0 branch is compared: the normal line force excites it far
more strongly than S0, and under this excitation S0 has no spectral peak at all.

Usage
-----
    python check_3d_dispersion.py            # expects the out_* runs to exist
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


def analytic(h, m, rho):
    c = np.array([min(b['phase_velocity_m_s'] for b in D.branches_at(f, h, m, rho))
                  for f in FREQS])
    return c


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
    c_an = analytic(h, m, rho)
    i0 = int(np.argmin(np.abs(FREQS - F0)))

    cases = [
        ('3D line 500x4x4', HERE / 'out_line' / 'wavefield.npz'),
        ('3D line 1000x4x8', HERE / 'out_line_1000x4x8' / 'wavefield.npz'),
        ('2D 1000x8', HERE.parent / 'guided_wave_v2' / '1000_8_healthy.npz'),
        ('2D 4000x32', HERE.parent / 'guided_wave_v2' / '4000_32_healthy.npz'),
    ]

    rows = []
    print('A0 相速度，同一提取方法；解析参照 %.1f m/s @100 kHz' % c_an[i0])
    print()
    print('%-18s %10s %10s %9s %10s %9s' %
          ('case', 'c_p@100k', 'k@100k', 'vs解析', 'c_g@100k', 'vs解析'))
    print('-' * 72)
    for label, path in cases:
        if not path.exists():
            print('%-18s  缺少 %s' % (label, path.name))
            continue
        k = C.wave_numbers(str(path), FREQS)
        cp = 2 * np.pi * FREQS / k
        cg = group_from_slope(FREQS, k)
        cg_an = np.array([min(b['group_velocity_m_s'] for b in D.branches_at(f, h, m, rho)
                              if b['group_velocity_m_s']) for f in FREQS])
        rows.append(dict(case=label, path=path.name,
                         c_phase_100k_m_s=float(cp[i0]),
                         k_100k_rad_m=float(k[i0]),
                         phase_error_vs_analytic=float(abs(cp[i0] - c_an[i0]) / c_an[i0]),
                         c_group_100k_m_s=float(cg[i0]),
                         group_error_vs_analytic=float(abs(cg[i0] - cg_an[i0]) / cg_an[i0]),
                         max_phase_error_in_band=float(np.max(np.abs(cp - c_an) / c_an)),
                         band=[dict(frequency_khz=float(f / 1e3),
                                    c_phase_m_s=float(c), k_rad_m=float(kk))
                               for f, c, kk in zip(FREQS, cp, k)]))
        print('%-18s %10.1f %10.1f %8.2f%% %10.1f %8.2f%%' %
              (label, cp[i0], k[i0], 100 * rows[-1]['phase_error_vs_analytic'],
               cg[i0], 100 * rows[-1]['group_error_vs_analytic']))

    print()
    print('解析 c_p@100k = %.1f, c_g@100k = %.1f m/s'
          % (c_an[i0], min(b['group_velocity_m_s'] for b in D.branches_at(F0, h, m, rho)
                           if b['group_velocity_m_s'])))
    three = [r for r in rows if r['case'].startswith('3D')]
    two = [r for r in rows if r['case'].startswith('2D')]
    if three and two:
        print()
        print('3D 线源 vs 2D（同网格）：')
        for t in three:
            for s in two:
                print('  %s vs %s: c_p 差 %.2f%%'
                      % (t['case'], s['case'],
                         100 * abs(t['c_phase_100k_m_s'] - s['c_phase_100k_m_s'])
                         / s['c_phase_100k_m_s']))

    (HERE / 'dispersion_check_3d.json').write_text(
        json.dumps(dict(frequency_band_khz=[85, 115], analytic_100k_m_s=float(c_an[i0]),
                        cases=rows), indent=2), encoding='utf8')
    print()
    print('wrote dispersion_check_3d.json')


if __name__ == '__main__':
    main()
