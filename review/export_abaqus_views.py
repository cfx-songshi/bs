"""Export Abaqus/CAE views of the ball-drop and guided-wave models, as PNG sequences.

    abaqus cae script=export_abaqus_views.py -- <odb> --outdir <dir> --view <kind>
           [--frames 24] [--until-us 120] [--size 1000,520]

Three kinds of view, because the report needs to show the model that was actually built
rather than only its numbers.

    model   isometric, feature edges only, no contour. The ply stack shows up as lines on
            the plate's cut edge, and the ball sits on the top face, so this is the "built
            in Abaqus" picture: geometry, layering and the rigid impactor in one frame.
    wave    top view, U3 contoured on the undeformed shape. This is the guided wave
            travelling from the actuator to the far edge, which is the thing the damage
            indicator is computed from.
    impact  isometric, U3 contoured on the undeformed shape. The ball arrives, the plate
            deflects, the ball leaves, the plate keeps ringing.

The contour is drawn on the undeformed shape on purpose: the wave stage's displacements are
1e-7 m on a 100 mm plate, so any deformation scale large enough to see would be a picture
of a geometry that does not exist, and the colour band already shows where the packet is.

Run this with abaqus cae, not python: only CAE has session and the display module. It writes
<outdir>/export_log.txt, because CAE does not return its output to the calling shell.
"""
import os
import sys

import numpy as np
from abaqus import *
from abaqusConstants import *

MAIN_VIEWPORT = 'Viewport: 1'


def parse_args(argv):
    """Our arguments, separated from the ones the CAE launcher adds.

    sys.argv also carries the launcher's own switches ('-cae', '-tmpdir', <path>, ...), so
    anything that is not an .odb and not one of our options is ignored.
    """
    args = [a for a in argv if a != '--']
    odb, outdir, kind = None, None, 'model'
    frames, until_us, size = 24, 120.0, (1000, 520)
    index = 0
    while index < len(args):
        token = args[index]
        if token == '--outdir':
            outdir, index = args[index + 1], index + 2
        elif token == '--view':
            kind, index = args[index + 1], index + 2
        elif token == '--frames':
            frames, index = int(args[index + 1]), index + 2
        elif token == '--until-us':
            until_us, index = float(args[index + 1]), index + 2
        elif token == '--size':
            size = tuple(int(v) for v in args[index + 1].split(','))
            index += 2
        elif token.lower().endswith('.odb'):
            odb, index = token, index + 1
        else:
            index += 1
    return odb, outdir, kind, frames, until_us, size


def u3_range(odb, frames=None):
    """Largest |U3| over the frames of interest, reduced per bulk data block.

    Reading values one at a time through the API would be frames x nodes of Python calls.
    Passing a frame list matters for the animations: the whole run's extreme is set by the
    late ringing, and using it would wash out the packet that the first hundred
    microseconds carry, which is the thing the animation is meant to show.
    """
    lo = hi = 0.0
    for frame in frames if frames is not None else odb.steps[list(odb.steps.keys())[0]].frames:
        field = frame.fieldOutputs['U']
        for block in field.bulkDataBlocks:
            components = list(block.componentLabels)
            if 'U3' not in components:
                continue
            column = np.asarray(block.data)[:, components.index('U3')]
            lo = min(lo, float(column.min()))
            hi = max(hi, float(column.max()))
    return lo, hi


def set_edge_display(viewport, want_edges):
    """Show or hide the mesh lines, returning what was accepted.

    FEATURE edges on a 90,000 element mesh draw a grid over the whole plate and swamp the
    contour, so the animations ask for no edges and fall back to free edges. Which symbol
    this release accepts is read from the return value rather than assumed.
    """
    for value in ((FEATURE,) if want_edges else (OFF, FREE)):
        try:
            viewport.odbDisplay.commonOptions.setValues(visibleEdges=value)
            return value
        except Exception:
            continue
    return None


def fix_limits(viewport, lo, hi):
    """Pin the contour legend so the same colour means the same displacement on every frame.

    minAutoCompute and maxAutoCompute are the switches that matter: setting minValue and
    maxValue alone is accepted, and reads back correctly, while the plot still rescales to
    each frame. animationAutoLimits holds a symbolic constant (ALL_FRAMES), not a switch --
    ON and OFF are both rejected -- so it is set first and dropped on the retry.
    """
    options = viewport.odbDisplay.contourOptions
    fixed = dict(minValue=lo, maxValue=hi, minAutoCompute=OFF, maxAutoCompute=OFF)
    for attempt in (dict(fixed, animationAutoLimits=ALL_FRAMES), fixed):
        try:
            options.setValues(**attempt)
            return dict((k, v) for k, v in attempt.items())
        except Exception:
            continue
    return None


def build_view(viewport, odb, kind):
    """Set the plot up for one of the three view kinds."""
    viewport.setValues(displayedObject=odb)
    if kind == 'model':
        viewport.odbDisplay.display.setValues(plotState=(UNDEFORMED,))
        edges = set_edge_display(viewport, True)
        viewport.view.setViewpoint(viewVector=(-1.2, -1.0, 0.8), cameraUpVector=(0.0, 0.0, 1.0))
        return 'visibleEdges %s' % edges
    viewport.odbDisplay.display.setValues(plotState=(CONTOURS_ON_UNDEF,))
    viewport.odbDisplay.setPrimaryVariable(variableLabel='U', outputPosition=NODAL,
                                           refinement=(COMPONENT, 'U3'))
    viewport.odbDisplay.contourOptions.setValues(numIntervals=14)
    edges = set_edge_display(viewport, False)
    if kind == 'wave':
        viewport.view.setViewpoint(viewVector=(0.0, 0.0, 1.0), cameraUpVector=(0.0, 1.0, 0.0))
    else:
        viewport.view.setViewpoint(viewVector=(-1.2, -1.0, 0.8), cameraUpVector=(0.0, 0.0, 1.0))
    return 'visibleEdges %s' % edges


def main():
    odb_path, outdir, kind, frames, until_us, size = parse_args(sys.argv[1:])
    if odb_path is None:
        raise SystemExit('usage: abaqus cae script=export_abaqus_views.py -- <odb> '
                         '--outdir <dir> --view model|wave|impact')
    if outdir is None:
        outdir = os.path.join(os.path.dirname(odb_path), 'views')
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    name = os.path.splitext(os.path.basename(odb_path))[0]
    log = []

    def emit(*parts):
        log.append(' '.join(str(part) for part in parts))
        with open(os.path.join(outdir, 'export_log.txt'), 'w') as handle:
            handle.write('\n'.join(log) + '\n')

    emit('odb', odb_path)
    emit('kind', kind, 'frames', frames, 'until_us', until_us, 'size', size)
    viewport = session.viewports[MAIN_VIEWPORT]
    session.pngOptions.setValues(imageSize=size)
    try:
        session.printOptions.setValues(vpBackground=ON, vpDecorations=ON)
    except Exception as error:
        emit('printOptions not applied: %s' % str(error)[:160])

    odb = session.openOdb(name=odb_path, readOnly=True)
    emit('view', build_view(viewport, odb, kind))
    viewport.view.fitView()
    step = odb.steps[list(odb.steps.keys())[0]]
    end_s = step.frames[-1].frameValue
    emit('step', step.name, 'frames available', len(step.frames), 'end_s', end_s)

    if kind == 'model':
        # Two stills rather than one, because neither alone shows the model: the isometric
        # view is what the built model looks like with the ball on it, and the front view
        # is the only one where the eight plies read as eight rows.
        for suffix, vector, up in (('model', (-1.2, -1.0, 0.8), (0.0, 0.0, 1.0)),
                                   ('model_front', (0.0, -1.0, 0.0), (0.0, 0.0, 1.0))):
            viewport.view.setViewpoint(viewVector=vector, cameraUpVector=up)
            viewport.view.fitView()
            target = os.path.join(outdir, '%s_%s' % (name, suffix))
            session.printToFile(fileName=target, format=PNG, canvasObjects=(viewport,))
            emit('wrote', target + '.png')
        emit('done')
        return

    available = [frame.frameValue for frame in step.frames]
    times = [min(until_us * 1e-6 * (index + 1) / frames, end_s) for index in range(frames)]
    indices = [min(range(len(available)), key=lambda i: abs(available[i] - target))
               for target in times]
    lo, hi = u3_range(odb, [step.frames[index] for index in sorted(set(indices))])
    # Symmetric about zero, from the exported frames only, so mid green is zero on every
    # frame and the legend does not move when the run is extended.
    bound = max(abs(lo), abs(hi))
    emit('u3_range_on_exported_frames_m', lo, hi, 'legend', -bound, bound)
    for number, index in enumerate(indices):
        viewport.odbDisplay.setFrame(step=0, frame=index)
        used = fix_limits(viewport, -bound, bound)
        target = os.path.join(outdir, '%s_%s_%02d' % (name, kind, number))
        session.printToFile(fileName=target, format=PNG, canvasObjects=(viewport,))
        emit('frame', number, 'requested_us', round(times[number] * 1e6, 2),
             'actual_us', round(available[index] * 1e6, 2),
             'limits', 'fixed' if used else 'AUTOMATIC (fixed limits rejected)')
    emit('done')


if __name__ == '__main__':
    main()
