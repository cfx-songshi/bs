"""Throwaway: read the interface stiffness out of the two-brick tension test.

The two bricks share no nodes, so the whole opening between them is carried by the
cohesive interaction. The top face is pulled by a known displacement, so the traction is
the reaction force on that face divided by its area, and the stiffness is that over the
opening the interface opened by.
"""
import sys

from odbAccess import openOdb

AREA = 1e-6

for path in sys.argv[1:]:
    odb = openOdb(path, readOnly=True)
    step = odb.steps[list(odb.steps.keys())[0]]

    force = None
    for _, region in step.historyRegions.items():
        if 'RF3' in region.historyOutputs:
            data = region.historyOutputs['RF3'].data
            force = sum(value for _, value in data[-4:]) / 4.0
    print('%s' % path)
    print('  reaction on the pulled face, mean of the last samples: %.6e N'
          % force if force is not None else '  no RF3 in the odb')

    for index, frame in enumerate(step.frames):
        for key in frame.fieldOutputs.keys():
            if not key.startswith('COPEN'):
                continue
            opening = max(value.data for value in frame.fieldOutputs[key].values)
            if opening <= 0.0:
                continue
            print('  frame %2d t=%.4g s: opening %.6e m, traction %.6e Pa, '
                  'K = %.4e Pa/m'
                  % (index, frame.frameValue, opening, force / AREA, force / AREA / opening))
    odb.close()
