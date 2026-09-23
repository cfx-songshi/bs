"""Throwaway: where is the contact pressure, by height? Separates ball self-contact,
ball-plate contact and the ply interfaces."""
import sys

from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
step = odb.steps[list(odb.steps.keys())[0]]
frame = step.frames[-1]
key = [n for n in frame.fieldOutputs.keys() if n.startswith('CPRESS')][0]
field = frame.fieldOutputs[key]
instance = odb.rootAssembly.instances[field.values[0].instance.name]
heights = {}
for node in instance.nodes:
    heights[int(node.label)] = node.coordinates[2]

buckets = {}
for value in field.values:
    z = heights.get(int(value.nodeLabel))
    if z is None:
        continue
    entry = buckets.setdefault(round(z * 1e3, 4), [0, 0.0, 0])
    entry[0] += 1
    entry[2] += 1 if value.data > 0.0 else 0
    entry[1] = max(entry[1], value.data)

print('%-10s %8s %8s %14s' % ('height mm', 'nodes', 'contact', 'max CPRESS Pa'))
for z in sorted(buckets):
    nodes, peak, touching = buckets[z]
    print('%-10.4f %8d %8d %14.4g' % (z, nodes, touching, peak))
odb.close()
