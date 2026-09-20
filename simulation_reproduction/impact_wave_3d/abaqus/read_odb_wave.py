"""Guided wave sensor readings, and the comparison that is the damage indicator.

Two things are reported per receiver. First the reading itself: the arrival time and peak
of the out-of-plane velocity, which is the direct A0 packet the actuator launches, and the
peak of the surface strain in the top ply, which is what a bonded patch would measure.

Second, when a second odb is given, the difference between the two, which is the damage
indicator. It is deliberately reported three ways, because no single number answers "did
the wave see the damage": the normalised RMS difference says how much of the waveform
changed at all, the correlation coefficient says whether the change is a shift or just a
scale, and the peak ratio says whether the transmitted packet lost amplitude. A small
delamination is expected to show as a small change, and reporting it as one large-sounding
number would be dishonest, so the parts are kept separate.

The sensor labels come from the sidecar make_impact_wave_inp.py writes next to the deck,
because a deck's node sets do not survive into the odb: Abaqus writes only the sets it
makes itself, so there is nothing in the odb to match a per-node history region against.

    abaqus python read_odb_wave.py <baseline odb> [<damaged odb>]
"""
import json
import math
import sys

from odbAccess import openOdb

SENSORS = ('ACT', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8')
COMPONENTS = ('U3', 'V3')
STRAINS = ('E11', 'E22', 'E12')
# y = 50 mm is a plane of symmetry of the mesh, the actuator sits on it and the disbond is
# a circle about the centre, so on an undamaged plate each of these pairs must read the
# same to within the solver's precision. This is the check that caught the wave stage
# being run in single precision: the reading agreed to 12 per cent there and to 0.0 in
# double precision, and 12 per cent is the size of the damage signal.
MIRROR_PAIRS = (('R3', 'R4'), ('R5', 'R6'), ('R7', 'R8'))
# A reflection in y leaves the out-of-plane motion and the direct strains alone but flips
# the in-plane y motion and therefore the shear strain E12. Comparing E12 for equality
# instead of for opposite sign makes a perfectly symmetric plate look 200 per cent wrong.
MIRROR_FLIPS = ('E12', 'E13', 'E23', 'U2', 'V2')


def sensor_series(step, sensor):
    """Node and element histories for one sensor, keyed by output name.

    Element regions are per integration point, named "Element PART-1-1.18567 Int Point 5",
    so the label has to be taken from the fragment after the dot rather than the whole
    fragment. Only the four upper points are averaged: the receiver is on the top face and
    a 0.25 mm ply across the 2 mm plate is a surface strain, which is what a bonded patch
    measures.
    """
    node_label, element_label = str(sensor[0]), str(sensor[1])
    node_series = {}
    element_series = {}
    for region_name, region in step.historyRegions.items():
        head = region_name.split()[0]
        parts = region_name.rsplit('.', 1)[-1].split()
        if not parts:
            continue
        if head == 'Node' and parts[0] == node_label:
            for name, output in region.historyOutputs.items():
                if name.upper() in COMPONENTS:
                    node_series.setdefault(name.upper(), output.data)
        elif head == 'Element' and parts[0] == element_label and len(parts) >= 4:
            point = int(parts[3])
            for name, output in region.historyOutputs.items():
                if name.upper() in STRAINS:
                    element_series.setdefault(point, {})[name.upper()] = output.data

    top = sorted(point for point in element_series if point >= 5)
    for component in STRAINS:
        series = [element_series[point][component] for point in top
                  if component in element_series[point]]
        if not series:
            continue
        node_series.setdefault(component, [(rows[0][0], sum(item[1] for item in rows)
                                            / len(rows))
                                           for rows in zip(*series)])
    return node_series


def find_nodes(odb_path):
    """Sensor name to (node label, element label), from the deck's sidecar."""
    path = odb_path[:-4] + '.sensors.json' if odb_path.endswith('.odb') else odb_path
    try:
        with open(path, 'r') as handle:
            sensors = json.load(handle)['sensors']
    except IOError:
        return {}
    return dict((name, (entry['node'], entry['element'])) for name, entry in sensors.items())


def peaks(data):
    times = [time for time, _ in data]
    values = [value for _, value in data]
    index = max(range(len(values)), key=lambda i: abs(values[i]))
    return times[index], values[index]


def compare(a, b):
    """Normalised RMS difference, correlation and peak ratio of two series."""
    count = min(len(a), len(b))
    x = [a[i][1] for i in range(count)]
    y = [b[i][1] for i in range(count)]
    rms = math.sqrt(sum(v * v for v in x) / count)
    if rms == 0.0:
        return None
    difference = math.sqrt(sum((x[i] - y[i]) ** 2 for i in range(count)) / count) / rms
    mx = sum(x) / count
    my = sum(y) / count
    sxy = sum((x[i] - mx) * (y[i] - my) for i in range(count))
    sxx = sum((v - mx) ** 2 for v in x)
    syy = sum((v - my) ** 2 for v in y)
    correlation = sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float('nan')
    peak_x = max(abs(v) for v in x) or 1.0
    peak_y = max(abs(v) for v in y)
    return difference, correlation, peak_y / peak_x


def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: abaqus python read_odb_wave.py <odb> [<odb damaged>]')
    odbs = [openOdb(path, readOnly=True) for path in sys.argv[1:]]
    steps = [odb.steps[list(odb.steps.keys())[0]] for odb in odbs]
    sensors = find_nodes(sys.argv[1])
    if not sensors:
        print('no sidecar beside %s: run make_impact_wave_inp.py to write it' % sys.argv[1])
        return
    print('sensor readings, %s' % ', '.join(sys.argv[1:]))

    for name in SENSORS:
        if name not in sensors:
            continue
        first = sensor_series(steps[0], sensors[name])
        print('\n%s (node %d, element %d)' % (name, sensors[name][0], sensors[name][1]))
        for component in ('V3', 'U3'):
            if component not in first:
                continue
            time, value = peaks(first[component])
            print('  %-4s peak % .4e at t=%.6g s' % (component, value, time))
        for component in STRAINS:
            if component not in first:
                continue
            time, value = peaks(first[component])
            print('  %-4s peak % .4e at t=%.6g s' % (component, value, time))

        if len(odbs) < 2:
            continue
        second = sensor_series(steps[1], sensors[name])
        print('  damaged against baseline:')
        for component in COMPONENTS + STRAINS:
            if component not in first or component not in second:
                continue
            result = compare(first[component], second[component])
            if result is None:
                continue
            difference, correlation, ratio = result
            print('    %-4s normalised RMS difference %.4f, correlation %.6f, '
                  'peak ratio %.4f' % (component, difference, correlation, ratio))

    print('\nmirror pairs about y = 50 mm, which an undamaged plate must read identically:')
    for left, right in MIRROR_PAIRS:
        if left not in sensors or right not in sensors:
            continue
        a = sensor_series(steps[0], sensors[left])
        b = sensor_series(steps[0], sensors[right])
        # Scale the mismatch by the pair's own signal level rather than by each component's
        # own amplitude. A component that happens to be near zero at that point, which the
        # shear and transverse strains often are, would otherwise show a meaningless
        # hundred per cent for a difference far below the wave.
        scale = 0.0
        for component in COMPONENTS + STRAINS:
            if component in a and component in b:
                count = min(len(a[component]), len(b[component]))
                scale = max(scale, max(abs(a[component][i][1]) for i in range(count)),
                            max(abs(b[component][i][1]) for i in range(count)))
        if scale == 0.0:
            continue
        worst = (0.0, None)
        for component in COMPONENTS + STRAINS:
            if component not in a or component not in b:
                continue
            count = min(len(a[component]), len(b[component]))
            sign = -1.0 if component in MIRROR_FLIPS else 1.0
            difference = max(abs(a[component][i][1] - sign * b[component][i][1])
                             for i in range(count))
            if difference > worst[0]:
                worst = (difference, component)
        print('  %s vs %s: worst %s, %.3f%% of the pair\'s signal level'
              % (left, right, worst[1], 100.0 * worst[0] / scale))

    for odb in odbs:
        odb.close()


if __name__ == '__main__':
    main()
