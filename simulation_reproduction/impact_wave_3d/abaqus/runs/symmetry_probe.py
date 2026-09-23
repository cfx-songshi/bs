"""Throwaway: is the solved field actually symmetric about y = 50 mm?

The sensor layout leans on that symmetry for a free check, so if a mirror pair disagrees
the reason has to be found rather than explained away. This compares every top face node
with its mirror image and reports the worst offenders, which separates "the mesh is not
symmetric" from "the solution is not symmetric" and from "the reader looked at the wrong
node".
"""
import sys

from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
step = odb.steps[list(odb.steps.keys())[0]]
print('step %s, %d frames' % (step.name, len(step.frames)))

instance = odb.rootAssembly.instances[list(odb.rootAssembly.instances.keys())[0]]
# Micrometre rounding for the lookup. Exact comparison fails here: the y coordinates are
# not exactly representable, so 0.1 - y does not reproduce the stored mirror coordinate
# even when the mesh is exactly symmetric.
lookup = {}
top = []
for node in instance.nodes:
    x, y, z = node.coordinates
    if abs(z - 2.0e-3) < 1e-9:
        lookup[(round(x * 1e6), round(y * 1e6))] = int(node.label)
        top.append((int(node.label), x, y))
mirrored = sum(1 for _, x, y in top
               if (round(x * 1e6), round((0.1 - y) * 1e6)) in lookup)
print('top face nodes: %d, of which %d have a mirror partner in the mesh'
      % (len(top), mirrored))

pairs = []
for label, x, y in top:
    partner = lookup.get((round(x * 1e6), round((0.1 - y) * 1e6)))
    if partner is not None:
        pairs.append((label, partner, x, y))

print('\nworst U3 mirror mismatch, frame by frame:')
for index in range(0, len(step.frames), max(1, len(step.frames) // 8)):
    frame = step.frames[index]
    values = {}
    for value in frame.fieldOutputs['U'].values:
        values[int(value.nodeLabel)] = float(value.data[2])
    worst = (0.0, None, None, 0.0, 0.0)
    largest = 0.0
    for label, partner, x, y in pairs:
        if label not in values or partner not in values:
            continue
        largest = max(largest, abs(values[label]), abs(values[partner]))
        difference = abs(values[label] - values[partner])
        if difference > worst[0]:
            worst = (difference, label, partner, x, y)
    if largest:
        print('  t=%.4g s: largest |U3| %.4e, worst mismatch %.4e (%.2f%%) at '
              '(%g, %g) mm' % (frame.frameValue, largest, worst[0],
                               100.0 * worst[0] / largest, worst[3] * 1e3, worst[4] * 1e3))
odb.close()

