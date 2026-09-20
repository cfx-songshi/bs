"""What stress state did a single-element test actually produce, and what moduli imply?

Written to explain a reaction force that came out about a fifth of the hand
calculation. The test prescribed the displacement of the top face along x with the
bottom face fully fixed, and the hand calculation then used the fibre tensile modulus.
Those two do not describe the same loading: displacing the top face of a cube along x
with the bottom held puts the element in shear in the x-z plane, which is governed by
G13, not by E1. Reading the stress components and the displacements back from the odb
settles which one it was, instead of assuming.

    abaqus python read_odb_field_summary.py <odb> [node-label,...]
"""
import sys

from odbAccess import openOdb

DEFAULT_NODES = (1, 2, 3, 4, 5, 6, 7, 8)


def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: abaqus python read_odb_field_summary.py <odb> [nodes]')
    odb_path = sys.argv[1]
    wanted = [int(v) for v in sys.argv[2].split(',')] if len(sys.argv) > 2 else list(DEFAULT_NODES)

    odb = openOdb(odb_path, readOnly=True)
    step = odb.steps[list(odb.steps.keys())[0]]
    frame = step.frames[-1]
    print('odb %s, step %s, last frame at t=%.6g s'
          % (odb_path, step.name, frame.frameValue))

    nodal = {}
    for block in frame.fieldOutputs['U'].bulkDataBlocks:
        for label, value in zip(block.nodeLabels, block.data):
            if int(label) in wanted:
                nodal[int(label)] = list(value)
    print('\ndisplacement of each node at the last frame (m):')
    for label in wanted:
        value = nodal.get(label)
        if value is not None:
            print('  node %-3d U = (% .6e, % .6e, % .6e)' % (label, value[0], value[1],
                                                             value[2]))

    stress = frame.fieldOutputs['S']
    print('\nstress at the element, averaged over its integration points (Pa):')
    for block in stress.bulkDataBlocks:
        labels = list(block.componentLabels)
        data = block.data
        for row_index, element in enumerate(block.elementLabels):
            points = [r for r in data]
            means = {}
            for column, name in enumerate(labels):
                means[name] = sum(float(r[column]) for r in points) / len(points)
            print('  element %s: %s' % (element,
                                        ', '.join('%s=% .4e' % (k, v)
                                                  for k, v in means.items())))
            print('    largest component by magnitude: %s'
                  % max(means, key=lambda k: abs(means[k])))

    # The two candidate readings of the same applied displacement, so the comparison is
    # explicit rather than left to the reader.
    ZERO_FACE = (1, 4, 5, 8)
    FAR_FACE = (2, 3, 6, 7)
    u1_zero = sum(nodal[label][0] for label in ZERO_FACE if label in nodal) / len(ZERO_FACE)
    u1_far = sum(nodal[label][0] for label in FAR_FACE if label in nodal) / len(FAR_FACE)
    print('\nmean U1 on the x=0 face %.6e, on the x=1mm face %.6e' % (u1_zero, u1_far))
    print('that is a displacement difference of %.6e m over the 1e-3 m length'
          % (u1_far - u1_zero))
    odb.close()


if __name__ == '__main__':
    main()
