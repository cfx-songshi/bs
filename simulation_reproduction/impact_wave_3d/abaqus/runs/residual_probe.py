"""Throwaway: how much is the plate still moving when the impact step ends?

Decides whether the wave step can follow the impact inside the same run or whether the
two stages have to be separate analyses. A plate that is still ringing at the end of the
impact contaminates the guided-wave reading, and the wave it scatters would have to be
separated from that ringing by filtering alone.
"""
import sys

from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
step = odb.steps[list(odb.steps.keys())[0]]
last = step.frames[-1]
print('last frame t=%.6g s' % last.frameValue)

for name, region in step.historyRegions.items():
    for output_name, output in region.historyOutputs.items():
        if output_name.upper() != 'U3':
            continue
        data = output.data
        print('U3 at %s: %d samples, last 20 (um):' % (name, len(data)))
        for time, value in data[-20:]:
            print('    t=%.7g s  % 9.4f' % (time, value * 1e6))

plate_nodes = int(sys.argv[2]) if len(sys.argv) > 2 else None
field = last.fieldOutputs['V']
heights = {}
for node in odb.rootAssembly.instances[field.values[0].instance.name].nodes:
    heights[int(node.label)] = node.coordinates[2]
plate, ball = [], []
for value in field.values:
    if int(value.nodeLabel) not in heights:
        continue
    speed = sum(component ** 2 for component in value.data) ** 0.5
    if plate_nodes is None or int(value.nodeLabel) <= plate_nodes:
        plate.append(speed)
    else:
        ball.append(speed)


def stats(name, values):
    if not values:
        return
    values = sorted(values)
    print('  %s: %d nodes, max |V| %.4g m/s, median %.4g, 99th %.4g'
          % (name, len(values), values[-1], values[len(values) // 2],
             values[int(0.99 * len(values))]))


print('velocity at the last frame:')
stats('plate', plate)
stats('ball', ball)
odb.close()
