"""Show the guided-wave odbs in Abaqus/CAE, contoured on U3, with PNG snapshots.

    abaqus cae script=view_odb.py -- <odb> [<odb> ...] --outdir <dir>
                              [--times 40,60,80] [--leave-at 100]

Each odb is displayed on the undeformed shape, a top view is fitted, and one PNG per
requested time is written to <dir>. The last odb named on the command line is *not*
what stays on screen: the first one does, because that is the one whose element type
the comparison says to trust (README 4b), shown inside the burst rather than at the end
of the record where the free-end echo has already crossed the receivers. The script
never closes the session, so the GUI remains for scrubbing and animation. It also
writes <dir>/view_log.txt, because Abaqus/CAE does not return its output to the calling
shell and every one of the choices below was settled from that log rather than from
guessing.

Why the plot is set up this way
-------------------------------
* Undeformed shape. The peak displacement is about 1 nm on a 500 mm plate; any
  deformation scale large enough to see would misrepresent the geometry, and the
  quantity of interest is where the packet is, which the colour band shows anyway.
* U3, not the displacement magnitude. U3 is what the in-house comparison reads
  (compare_abaqus_line.py), so what is on screen and what is in the numbers agree.
* Top view. The strip is 500 x 20 x 1.72 mm; an isometric view shows it almost
  edge-on and hides the travelling packet.
* A fixed colour scale, from the largest |U3| over the whole run, so frames can be
  compared. The switches are minAutoCompute and maxAutoCompute; setting minValue and
  maxValue without them is accepted and even reads back correctly, but the plot still
  rescales to each frame, which silently makes the same colour mean a different
  displacement on every frame. Read the accepted keywords from the log line rather
  than trusting this note on a different release.

Two limits worth knowing
------------------------
* The range is fixed per odb, from that odb's own extremes, not shared across odbs.
  C3D8R's extremes are wider than C3D8's because its hourglass content contributes to
  them, so the same colour in the two PNG sets is not the same displacement.
* animationAutoLimits holds a symbolic constant (ALL_FRAMES here), not a switch, and
  the script sets it explicitly. It was found by reading the attribute back after ON and
  OFF were both rejected, so if playback ever rescales the legend on another release,
  that read-back is the first thing to do.

A contour plot cannot show the difference between real deformation and hourglass
content -- that is what ALLAE/ALLIE in the odb history output is for (README 4b and the
C3D8R experiment). Use this viewer to see where the wave is, not to judge the element.
"""
import os
import sys

import numpy as np
from abaqus import *
from abaqusConstants import *

MAIN_VIEWPORT = 'Viewport: 1'
DEFAULT_TIMES_US = (40.0, 60.0, 80.0, 100.0, 130.0, 200.0)
DEFAULT_LEAVE_AT_US = 100.0


def parse_args(argv):
    """Split our arguments out of the ones the Abaqus launcher adds.

    When CAE runs a script, sys.argv carries the launcher's own switches too
    ('-cae', '-tmpdir', <path>, '-lmlog', 'ON'), so anything that is not an .odb and
    not one of our options is ignored rather than treated as an odb to open.
    """
    args = [a for a in argv if a != '--']
    odbs, outdir, times, leave_at = [], None, list(DEFAULT_TIMES_US), DEFAULT_LEAVE_AT_US
    i = 0
    while i < len(args):
        if args[i] == '--outdir':
            outdir = args[i + 1]
            i += 2
        elif args[i] == '--times':
            times = [float(t) for t in args[i + 1].split(',')]
            i += 2
        elif args[i] == '--leave-at':
            leave_at = float(args[i + 1])
            i += 2
        elif args[i].lower().endswith('.odb'):
            odbs.append(args[i])
            i += 1
        else:
            i += 1
    return odbs, outdir, times, leave_at


def u3_range(odb):
    """Largest |U3| over every frame, vectorised per bulk data block.

    Reading the values one at a time through the API would be 111 frames x 12525 nodes
    of Python-level calls; the block arrays are contiguous and can be reduced directly.
    """
    lo = hi = 0.0
    for frame in odb.steps[list(odb.steps.keys())[0]].frames:
        fo = frame.fieldOutputs['U']
        for block in fo.bulkDataBlocks:
            comps = list(block.componentLabels)
            if 'U3' not in comps:
                continue
            col = np.asarray(block.data)[:, comps.index('U3')]
            lo = min(lo, float(col.min()))
            hi = max(hi, float(col.max()))
    return lo, hi


def try_fixed_limits(vp, lo, hi):
    """Force the contour legend to a fixed range, so frames can be compared.

    The switches that matter on this release are minAutoCompute and maxAutoCompute.
    Setting minValue and maxValue without them is accepted and even stored -- reading
    them back returns the values -- but the plot still rescales to whatever frame is
    displayed, so the same colour means a different displacement on every frame.

    animationAutoLimits is not a switch: it holds a symbolic constant, ALL_FRAMES on
    this release, which is what keeps the legend from being recomputed during playback.
    Asking for ON or OFF is rejected outright, which is how the constant was found --
    the value was read back, not guessed. It is set explicitly here rather than relied
    on as a default, and the second attempt drops it so a release that renames the
    constant still gets the frame-by-frame legend fixed.
    """
    opts = vp.odbDisplay.contourOptions
    fixed = dict(minValue=lo, maxValue=hi, minAutoCompute=OFF, maxAutoCompute=OFF)
    attempts = [dict(fixed, animationAutoLimits=ALL_FRAMES), fixed]
    for kwargs in attempts:
        try:
            opts.setValues(**kwargs)
            return kwargs
        except Exception:
            continue
    return None


def contour_report(vp):
    """Everything needed to pin the legend API down on this release.

    Deliberately reads attributes one at a time: ContourOptions has no getValues() on
    this release, and an AttributeError here would abort the frame loop.
    """
    try:
        opts = vp.odbDisplay.contourOptions
        vals = {}
        for k in ('minValue', 'maxValue', 'minAutoCompute', 'maxAutoCompute',
                  'animationAutoLimits', 'numIntervals', 'intervalType', 'contourType'):
            try:
                vals[k] = getattr(opts, k)
            except Exception:
                pass
        return 'contourState %s' % vals
    except Exception as exc:
        return 'contour_report failed: %s' % str(exc)[:200]


def frame_for(step, target_s):
    times = [f.frameValue for f in step.frames]
    best = min(range(len(times)), key=lambda i: abs(times[i] - target_s))
    return best, times[best]


def setup_plot(vp, odb):
    """Contour U3 on the undeformed shape, top view, fitted."""
    vp.setValues(displayedObject=odb)
    vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_UNDEF,))
    vp.odbDisplay.setPrimaryVariable(variableLabel='U', outputPosition=NODAL,
                                     refinement=(COMPONENT, 'U3'))
    vp.odbDisplay.contourOptions.setValues(numIntervals=12)
    try:
        vp.view.setViewpoint(viewVector=(0.0, 0.0, 1.0), cameraUpVector=(0.0, 1.0, 0.0))
    except Exception as exc:
        return 'viewpoint failed: %s' % str(exc)[:120]
    vp.view.fitView()
    return None


def show_frame(vp, step, idx, lo, hi):
    """Move to a frame and re-apply the limits.

    The limits have to be set *after* the frame change: switching frames makes Abaqus
    recompute them from that frame's data, so limits applied once up front are silently
    replaced and the legend -- and with it the colours -- changes from frame to frame.
    That is exactly the kind of rescaling that makes a frame-by-frame amplitude
    comparison meaningless, so it is re-applied on every frame.
    """
    vp.odbDisplay.setFrame(step=0, frame=idx)
    return try_fixed_limits(vp, lo, hi)


def main():
    odbs, outdir, times, leave_at_us = parse_args(sys.argv[1:])
    if not odbs:
        raise SystemExit('usage: abaqus cae script=view_odb.py -- <odb> [...] '
                         '--outdir <dir> [--times 40,60,80] [--leave-at 100]')
    if outdir is None:
        outdir = os.path.join(os.path.dirname(odbs[0]), 'view')
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    log = []

    def emit(*parts):
        log.append(' '.join(str(p) for p in parts))
        with open(os.path.join(outdir, 'view_log.txt'), 'w') as fh:
            fh.write('\n'.join(log) + '\n')

    emit('outdir', outdir)
    emit('odbs', odbs)
    vp = session.viewports[MAIN_VIEWPORT]
    session.pngOptions.setValues(imageSize=(1800, 520))
    try:
        session.printOptions.setValues(vpBackground=ON, vpDecorations=ON)
    except Exception as exc:
        emit('printOptions not applied', type(exc).__name__, str(exc)[:160])

    first = None
    for path in odbs:
        name = os.path.splitext(os.path.basename(path))[0]
        emit('---', name)
        try:
            odb = session.openOdb(name=path, readOnly=True)
            note = setup_plot(vp, odb)
            if note:
                emit(note)

            step = odb.steps[list(odb.steps.keys())[0]]
            lo, hi = u3_range(odb)
            emit('step', step.name, 'frames', len(step.frames),
                 'step_time_end_s', step.frames[-1].frameValue)
            emit('u3_range_m', lo, hi)
            if first is None:
                first = (name, odb, step, lo, hi)

            for t_us in times:
                idx, t = frame_for(step, t_us * 1e-6)
                used = show_frame(vp, step, idx, lo, hi)
                target = os.path.join(outdir, '%s_t%03dus' % (name, int(round(t * 1e6))))
                session.printToFile(fileName=target, format=PNG, canvasObjects=(vp,))
                emit('frame', idx, 'requested_us', t_us, 'actual_us', round(t * 1e6, 3),
                     'limits', used if used else 'AUTOMATIC (fixed limits rejected)',
                     'png', target + '.png')
                if t_us == times[0]:
                    emit(contour_report(vp))
        except Exception as exc:
            emit('FAILED on', path, type(exc).__name__, str(exc)[:300])

    # Leave the first odb on screen: it is the one whose element type the comparison
    # says to trust (README 4b), shown inside the burst rather than at the end of the
    # record where the free-end echo has already crossed the receivers.
    if first is not None:
        name, odb, step, lo, hi = first
        setup_plot(vp, odb)
        idx, t = frame_for(step, leave_at_us * 1e-6)
        show_frame(vp, step, idx, lo, hi)
        emit('left displayed: %s at frame %d (%.1f us), fixed limits %.3e .. %.3e m'
             % (name, idx, t * 1e6, lo, hi))
    emit('receiver nodes on the 500x4x4 mesh: 11203 at x = 0.18 m, 11343 at x = 0.32 m')
    emit('done; the session stays open')


if __name__ == '__main__':
    main()
