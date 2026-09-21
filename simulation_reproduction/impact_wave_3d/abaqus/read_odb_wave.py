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

--window-us A,B restricts every number below to that time window. It exists because the
wave model drifts asymmetric at late times, up to 23 to 39 per cent of the signal near the
inner edge of the clamp, which is larger than a small delamination's signature. The direct
packets arrive inside the first hundred microseconds, so windowing is the honest way to
read the indicator until that drift is fixed; it is also what the through transmission pair
is for, since a first arrival is the one thing a reflection cannot imitate.

    abaqus python read_odb_wave.py <baseline odb> [<damaged odb>] [--window-us A,B]
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
            return json.load(handle)
    except IOError:
        return {}


def read_window(argv):
    """--window-us A,B, as seconds, or None for the whole record."""
    if '--window-us' not in argv:
        return None
    text = argv[argv.index('--window-us') + 1]
    low, high = (float(value) * 1e-6 for value in text.split(','))
    return low, high


def apply_window(series, window):
    if window is None:
        return series
    return dict((name, [(time, value) for time, value in data
                        if window[0] <= time <= window[1]])
                for name, data in series.items())


def first_arrival(data, threshold=0.2):
    """The onset of the packet: the first time the signal reaches a fraction of its peak.

    The peak of the record is not an arrival time. At the receivers off the direct path the
    largest excursion comes from a boundary reflection arriving a hundred microseconds
    after the packet, and reading the peak as the arrival turned those into speeds of 118
    to 939 m/s against the 1269 m/s the mesh was sized on. The onset is what a time of
    flight is measured from, and it is the one feature a reflection cannot imitate.
    """
    values = [value for _, value in data]
    if not values:
        return None
    level = threshold * max(abs(value) for value in values)
    for time, value in data:
        if abs(value) >= level:
            return time
    return None


def travel(reader, name, series):
    """Distance and packet arrival time from the actuator, for the dispersion check."""
    if name == 'ACT' or 'ACT' not in reader.get('sensor_positions', {}):
        return None
    positions = reader['sensor_positions']
    ax, ay = positions['ACT']
    x, y = positions[name]
    distance = math.hypot(x - ax, y - ay)
    if 'V3' not in series:
        return None
    onset = first_arrival(series['V3'])
    if onset is None:
        return None
    return distance, onset, peaks(series['V3'])[0]


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
    paths = [path for path in sys.argv[1:] if path.endswith('.odb')]
    if not paths:
        raise SystemExit('usage: abaqus python read_odb_wave.py <odb> [<odb damaged>] '
                         '[--window-us A,B]')
    odbs = [openOdb(path, readOnly=True) for path in paths]
    steps = [odb.steps[list(odb.steps.keys())[0]] for odb in odbs]
    reader = find_nodes(paths[0])
    sensors = dict((name, (entry['node'], entry['element']))
                   for name, entry in reader.get('sensors', {}).items())
    if not sensors:
        print('no sidecar beside %s: run make_impact_wave_inp.py to write it' % paths[0])
        return
    print('sensor readings, %s' % ', '.join(paths))
    window = read_window(sys.argv)
    if window:
        print('  restricted to %.4g to %.4g us' % (window[0] * 1e6, window[1] * 1e6))

    # The actuator's own onset is the launch time, not its peak. The burst is five cycles,
    # fifty microseconds, which is not short against the twenty to forty microseconds a
    # receiver takes to be reached, so the burst's peak is half a burst late as a marker
    # and every speed comes out too high. Both ends are then the same threshold crossing,
    # which is what a time of flight should compare. The peak to peak time is still
    # printed beside it, and it is the one to distrust.
    fired = None
    fired_peak = None
    if 'ACT' in sensors:
        series = apply_window(sensor_series(steps[0], sensors['ACT']), window)
        if 'V3' in series:
            fired = first_arrival(series['V3'])
            fired_peak = peaks(series['V3'])[0]

    for name in SENSORS:
        if name not in sensors:
            continue
        first = apply_window(sensor_series(steps[0], sensors[name]), window)
        print('\n%s (node %d, element %d)' % (name, sensors[name][0], sensors[name][1]))
        for component in COMPONENTS + STRAINS:
            if component not in first:
                continue
            time, value = peaks(first[component])
            print('  %-4s peak % .4e at t=%.6g s' % (component, value, time))
        # The dispersion check this run can make for itself: A0 launched at the actuator,
        # its packet arriving at a receiver a known distance away, and the resulting speed.
        # It is the number to compare against the analytic Rayleigh-Lamb curve. Both the
        # onset and the peak are reported: where they disagree by a lot the peak is a
        # boundary reflection and only the onset is the packet.
        if fired is not None and name != 'ACT':
            info = travel(reader, name, first)
            if info is not None:
                distance, onset, peak_time = info
                if onset > fired:
                    line = ('  direct path %.1f mm, onset to onset %.4g s, %.0f m/s'
                            % (distance * 1e3, onset - fired, distance / (onset - fired)))
                    if fired_peak is not None and peak_time > fired_peak:
                        line += ('; peak to peak %.4g s, %.0f m/s'
                                 % (peak_time - fired_peak,
                                    distance / (peak_time - fired_peak)))
                    print(line)

        if len(odbs) < 2:
            continue
        second = apply_window(sensor_series(steps[1], sensors[name]), window)
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
        a = apply_window(sensor_series(steps[0], sensors[left]), window)
        b = apply_window(sensor_series(steps[0], sensors[right]), window)
        # Only the displacement and velocity channels. They are what the through
        # transmission indicator reads, and they are not near zero at a broadside point.
        # A strain component there can be, and a normalised difference against a signal
        # that is nearly zero says nothing except that the divisor was small; the shear
        # components also flip sign under the reflection, which is handled below but makes
        # them a poor choice to judge the whole check by.
        worst = (0.0, None)
        for component in COMPONENTS:
            if component not in a or component not in b:
                continue
            sign = -1.0 if component in MIRROR_FLIPS else 1.0
            flipped = [(time, sign * value) for time, value in b[component]]
            result = compare(a[component], flipped)
            if result and result[0] > worst[0]:
                worst = (result[0], component)
        print('  %s vs %s: normalised RMS difference %.4f (%s), where zero is what a '
              'symmetric plate must give' % (left, right, worst[0], worst[1]))

    for odb in odbs:
        odb.close()


if __name__ == '__main__':
    main()
