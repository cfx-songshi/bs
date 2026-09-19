"""Quantitative verification of the point source, which the line source cannot cover.

Why this is a separate question
-------------------------------
The analytical Rayleigh-Lamb reference assumes a plane-strain field, which is exactly
what a line source produces. A point source does not: it radiates a curved front in
two dimensions. So the earlier agreement (3D line source within 0.1-0.4 percent of the
analytics) says nothing directly about the point source.

What makes a verification possible is the in-plane anisotropy of the [0]8 laminate.
E1 is about 16 times E2, so the same plate carries A0 at very different speeds along
and across the fibres, and the wavefront is therefore an ellipse. That is a property
the plane-strain 2D model cannot represent at all, and it can be checked two ways:

* The phase slope along a line through the source recovers the wavenumber in that
  direction, so the wave speed along the fibres and across the fibres can each be
  compared with its own analytical branch.
* The measured ratio of the two speeds can be compared with the analytical ratio.

Both are done here. Two propagation directions were added to dispersion.py for this
purpose, with an isotropic self-test that forces the two to coincide.

Measurement windows are picked to stay ahead of reflections: A0 along the fibres runs
at about 1750 m/s, so in a 250 mm plate the front reaches the edge at roughly 72 us
and the reflection returns near 143 us, which caps the along-fibre window.

Usage
-----
    python check_point_source.py --npz out_point_200/wavefield.npz
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'guided_wave_v2'))
import dispersion as D                     # noqa: E402

MATS = {k: v for k, v in D.T300.items() if k != 'rho'}
H, RHO = D.THICKNESS, D.T300['rho']


def branch_table(direction, freqs, which='slowest'):
    """Analytical phase and group velocity of A0 (slowest) or S0 (fastest)."""
    m = D.plane_strain_stiffness(**MATS, direction=direction)
    cp, cg = [], []
    for f in freqs:
        br = D.branches_at(f, H, m, RHO)
        b = min(br, key=lambda b: b['phase_velocity_m_s']) if which == 'slowest' \
            else max(br, key=lambda b: b['phase_velocity_m_s'])
        cp.append(b['phase_velocity_m_s'])
        cg.append(b['group_velocity_m_s'] or np.nan)
    return np.array(cp), np.array(cg)


def phase_slope(frames_2d, times, coords, freqs, band, nfft=8192):
    """Wavenumber along one line, from the spatial phase slope at each frequency.

    frames_2d is (n_frames, n_coords) for the chosen line. The phase is unambiguous as
    sampled: the along-fibre A0 wavelength is about 12.9 mm against a 2.5 mm sample
    spacing, so the phase step stays well inside the unwrapping limit.
    """
    keep = np.ones(frames_2d.shape[0], bool)
    if band is not None:
        keep = (times >= band[0]) & (times <= band[1])
    data = frames_2d[keep]
    if data.shape[0] < 8:
        return None
    data = data * np.hanning(data.shape[0])[:, None]
    spec = np.fft.rfft(data, n=nfft, axis=0)
    fgrid = np.fft.rfftfreq(nfft, times[1] - times[0])
    out = []
    for f0 in freqs:
        i = int(np.argmin(np.abs(fgrid - f0)))
        phase = np.unwrap(np.angle(spec[i]))
        out.append(abs(float(np.polyfit(coords, phase, 1)[0])))
    return np.array(out)


def group_from_slope(freqs, k, half_hz=8e3):
    out = np.full(len(freqs), np.nan)
    for i, f0 in enumerate(freqs):
        m = np.abs(freqs - f0) <= half_hz
        if m.sum() >= 4:
            out[i] = 2 * np.pi / np.polyfit(freqs[m], k[m], 1)[0]
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--npz', type=Path, required=True)
    p.add_argument('--out', type=Path, default=HERE / 'point_source_check.json')
    p.add_argument('--fmin-khz', type=float, default=90.0)
    p.add_argument('--fmax-khz', type=float, default=110.0)
    p.add_argument('--x-window-mm', type=float, nargs=2, default=[25.0, 115.0])
    p.add_argument('--y-window-mm', type=float, nargs=2, default=[25.0, 115.0])
    p.add_argument('--x-time-us', type=float, nargs=2, default=[0.0, 120.0],
                   help='shortened to stay ahead of the along-fibre edge reflection')
    p.add_argument('--y-time-us', type=float, nargs=2, default=[0.0, 200.0])
    a = p.parse_args()

    d = np.load(a.npz)
    frames, ft, x, y = d['frames'], d['frame_t'], d['x'], d['y']
    stride = int(d['frame_stride_xy']) if 'frame_stride_xy' in d else 1
    xs, ys = x[::stride], y[::stride]
    src_i = int(np.argmin(np.abs(xs - xs.mean())))
    src_j = int(np.argmin(np.abs(ys - ys.mean())))
    print('表面场 %s，空间步长 %.3f mm，源在 (%.1f, %.1f) mm'
          % (frames.shape, (xs[1] - xs[0]) * 1e3, xs[src_i] * 1e3, ys[src_j] * 1e3))

    freqs = np.arange(a.fmin_khz, a.fmax_khz + 1e-9, 2.0) * 1e3
    report = dict(npz=str(a.npz), frame_shape=list(frames.shape),
                  spatial_step_m=float(xs[1] - xs[0]),
                  frequency_band_khz=[a.fmin_khz, a.fmax_khz], directions={})

    for label, line, coords, window, band in (
            ('along_fibre_x', frames[:, src_j, :], xs,
             np.array(a.x_window_mm) / 1e3, tuple(t * 1e-6 for t in a.x_time_us)),
            ('across_fibre_y', frames[:, :, src_i], ys,
             np.array(a.y_window_mm) / 1e3, tuple(t * 1e-6 for t in a.y_time_us))):
        m = (coords >= window[0]) & (coords <= window[1])
        k = phase_slope(line[:, m], ft, coords[m], freqs, band)
        if k is None:
            report['directions'][label] = dict(error='not enough samples')
            continue
        direction = 'x' if label.endswith('_x') else 'y'
        cp_fe = 2 * np.pi * freqs / k
        cp_an, cg_an = branch_table(direction, freqs, 'slowest')
        cg_fe = group_from_slope(freqs, k)
        i0 = int(np.argmin(np.abs(freqs - 100e3)))
        report['directions'][label] = dict(
            analytic_direction=direction,
            window_mm=list(window), time_window_us=list(band),
            A0_phase_FE_m_s=float(cp_fe[i0]), A0_phase_analytic_m_s=float(cp_an[i0]),
            A0_phase_relative_error=float(abs(cp_fe[i0] - cp_an[i0]) / cp_an[i0]),
            A0_group_FE_m_s=float(cg_fe[i0]), A0_group_analytic_m_s=float(cg_an[i0]),
            max_phase_error_in_band=float(np.max(np.abs(cp_fe - cp_an) / cp_an)),
            band=[dict(frequency_khz=float(f / 1e3), c_phase_FE_m_s=float(cf),
                       c_phase_analytic_m_s=float(ca))
                  for f, cf, ca in zip(freqs, cp_fe, cp_an)])

    dx = report['directions'].get('along_fibre_x', {})
    dy = report['directions'].get('across_fibre_y', {})
    if 'A0_phase_FE_m_s' in dx and 'A0_phase_FE_m_s' in dy:
        ratio_fe = dx['A0_phase_FE_m_s'] / dy['A0_phase_FE_m_s']
        ratio_an = dx['A0_phase_analytic_m_s'] / dy['A0_phase_analytic_m_s']
        report['anisotropy_ratio'] = dict(
            FE=float(ratio_fe), analytic=float(ratio_an),
            relative_error=float(abs(ratio_fe - ratio_an) / ratio_an),
            note='ratio of along-fibre to across-fibre A0 phase velocity at 100 kHz')

    print()
    print('%-16s %10s %10s %9s %10s' % ('direction', 'c_p FE', 'c_p 解析', 'vs解析', 'c_g FE'))
    for label, entry in report['directions'].items():
        if 'A0_phase_FE_m_s' not in entry:
            print('%-16s  %s' % (label, entry.get('error')))
            continue
        print('%-16s %10.1f %10.1f %8.2f%% %10.1f'
              % (label, entry['A0_phase_FE_m_s'], entry['A0_phase_analytic_m_s'],
                 100 * entry['A0_phase_relative_error'],
                 entry['A0_group_FE_m_s'] if np.isfinite(entry['A0_group_FE_m_s']) else float('nan')))
    if 'anisotropy_ratio' in report:
        r = report['anisotropy_ratio']
        print()
        print('各向异性比（沿纤维/垂直纤维，A0 相速度）：FE %.3f，解析 %.3f，差 %.2f%%'
              % (r['FE'], r['analytic'], 100 * r['relative_error']))
        print('若为各向同性板该比值应为 1.000；二维平面应变模型给不出这个量。')

    a.out.write_text(json.dumps(report, indent=2), encoding='utf8')
    print()
    print('wrote %s' % a.out)


if __name__ == '__main__':
    main()
