"""Write the top-surface centre line from an Abaqus .odb into the in-house format.

`dispersion_check.wave_numbers` reads an npz holding `frames` (time x space),
`frame_t` and `x`, so this lets the Abaqus run be measured with the same wavenumber
extractor the in-house model was verified with. Using one estimator on both is the
whole point: a difference in the numbers is then a difference in the models and not
in the post-processing.

    abaqus python read_odb_surface.py job.odb out.npz --nx 500 --ny 4 --nz 4 --lx 0.5

The line is the width-centre row of top-surface nodes, which is what
solve_uvg_3d.py stores for `--frames line`. Node labels follow the generator's
numbering, 1 + i + (nx+1)*(j + (ny+1)*k); they are computed here and checked against
the odb instead of being assumed.
"""
import argparse

import numpy as np

from odbAccess import openOdb


def main():
    p = argparse.ArgumentParser()
    p.add_argument('odb')
    p.add_argument('out')
    p.add_argument('--nx', type=int, default=500)
    p.add_argument('--ny', type=int, default=4)
    p.add_argument('--nz', type=int, default=4)
    p.add_argument('--lx', type=float, default=0.5)
    p.add_argument('--step', default='WAVE')
    a = p.parse_args()

    def nid(i, j, k):
        return 1 + i + (a.nx + 1) * (j + (a.ny + 1) * k)

    labels = [nid(i, a.ny // 2, a.nz) for i in range(a.nx + 1)]
    want = dict((lab, n) for n, lab in enumerate(labels))

    odb = openOdb(a.odb, readOnly=True)
    try:
        step = odb.steps[a.step]
        times, rows = [], []
        for frame in step.frames:
            fo = frame.fieldOutputs['U']
            got = {}
            # bulkDataBlocks is the vectorised route; walking fieldOutputs.values
            # costs one API call per node per frame instead.
            for block in fo.bulkDataBlocks:
                comps = list(block.componentLabels)
                if 'U3' not in comps:
                    continue
                c = comps.index('U3')
                for n, lab in enumerate(list(block.nodeLabels)):
                    m = want.get(lab)
                    if m is not None:
                        got[m] = float(block.data[n][c])
            if not got:
                for v in fo.values:
                    m = want.get(v.nodeLabel)
                    if m is not None:
                        got[m] = float(v.data[2])
            missing = [n for n in range(len(labels)) if n not in got]
            if missing:
                raise SystemExit('frame %d: %d of %d line nodes missing, e.g. %s'
                                 % (frame.frameId, len(missing), len(labels), missing[:4]))
            times.append(float(frame.frameValue))
            rows.append([got[n] for n in range(len(labels))])
    finally:
        odb.close()

    frames = np.array(rows)
    frame_t = np.array(times)
    spacing = np.diff(frame_t)
    if np.ptp(spacing) > 1e-12:
        # Field frames are written at whatever increment the solver has reached, so
        # their spacing is not exactly uniform while the wavenumber extractor assumes
        # it is. Resample onto the mean spacing before handing the file over.
        tu = frame_t[0] + np.arange(frame_t.size) * spacing.mean()
        frames = np.vstack([np.interp(tu, frame_t, frames[:, j])
                            for j in range(frames.shape[1])]).T
        frame_t = tu
        print('resampled onto a uniform %.4e s grid (spacing spread was %.2e s)'
              % (spacing.mean(), np.ptp(spacing)))
    np.savez_compressed(a.out, frames=frames, frame_t=frame_t,
                        x=np.arange(a.nx + 1) * (a.lx / a.nx))
    print('%s: frames %s, dt %.4e s, %d x points to %.3f m'
          % (a.out, frames.shape, frame_t[1] - frame_t[0], frames.shape[1], a.lx))


if __name__ == '__main__':
    main()
