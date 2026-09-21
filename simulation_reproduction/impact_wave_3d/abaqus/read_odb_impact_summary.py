"""The impact stage's acceptance check, read back from one odb.

Step 1 of the ball-drop route is the impact stage on its own, and it is accepted or
rejected on four questions. This prints the numbers behind all four so that the verdicts
are read from the run rather than from the deck's intent.

  1. Is the stable increment usable? Cohesive *elements* at the ply boundaries collapsed
     it to 3.8e-12 s, which is why the interface became a contact-based cohesive surface.
     The initial value and the mean over the step both come from the .sta.
  2. Does the energy balance? ALLDMD above zero means the interface is actually dissipating
     fracture energy; a large ETOTAL drift means the step or the contact is misbehaving.
  3. Did anything delaminate, and where? CSDMG is the interface damage variable for
     contact-based cohesive behaviour, the surface equivalent of a cohesive element's SDEG.
     It is reported per damaged node together with that node's height, since the interface
     a node belongs to is its height.
  4. How do the peak contact force and the impact-point deflection compare with the
     impact_3d_v1 anchor of 32 N / 313 um? The two models are different structures, so
     this is an order-of-magnitude check, not a validation. The force is not an output of
     the deck: it is the ball's mass times the slope of its own velocity history, which is
     the contact force and nothing else while the ball is a free rigid body.

The delaminated area is not an output either, and it is the number the wave stage's disbond
radius is read off. It comes from ALLDMD divided by the interface toughness, which spans
the mode I to the mixed mode value, so the honest answer is a bracket and not a radius. That
arithmetic used to be done by hand, which is how a factor of ten got into the record; it is
done here now. An equal area circle is an idealisation: the real footprint is not round.

    abaqus python read_odb_impact_summary.py <odb> --ball-mass <kg> [--gc 490,1060]
"""
import math
import re
import sys

from odbAccess import openOdb

WATCH = ('ALLKE', 'ALLIE', 'ALLSE', 'ALLAE', 'ALLDMD', 'ALLPD', 'ALLWK', 'ETOTAL')

# The solver's progress table, one row per printed increment: increment number, step time,
# total time, wall clock, stable increment, critical element, kinetic, total energy.
PROGRESS = re.compile(r'^\s*(\d+)\s+([\d.]+E[+-]\d+)\s+([\d.]+E[+-]\d+)\s+'
                      r'\d+:\d+:\d+\s+([\d.]+E[+-]\d+)\s+(\d+)\s+([\d.]+E[+-]\d+)\s+'
                      r'([\d.]+E[+-]\d+)\s*$', re.MULTILINE)


def option(name, default=None):
    if name in sys.argv:
        return sys.argv[sys.argv.index(name) + 1]
    return default


def contact_field(frame, prefix):
    for name in frame.fieldOutputs.keys():
        if name.startswith(prefix):
            return frame.fieldOutputs[name]
    return None


def status_report(sta_path):
    """Initial and mean stable increment, from the status file."""
    try:
        with open(sta_path, 'r', errors='replace') as handle:
            text = handle.read()
    except IOError:
        return None
    match = re.search(r'Initial time increment\s*=\s*([\d.E+-]+)', text)
    initial = float(match.group(1)) if match else None
    rows = PROGRESS.findall(text)
    if not rows:
        return dict(initial=initial, increments=None, end=None, mean=None)
    increments = int(rows[-1][0])
    end = float(rows[-1][1])
    return dict(initial=initial, increments=increments, end=end,
                mean=end / increments if increments else None)


def _number(value, fmt='%.4g'):
    return 'n/a' if value is None else fmt % value


def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: abaqus python read_odb_impact_summary.py <odb> '
                         '--ball-mass <kg>')
    odb_path = sys.argv[1]
    ball_mass = option('--ball-mass')
    ball_mass = float(ball_mass) if ball_mass else None
    # Interface toughness for the area conversion. The deck gives mode I 490 J/m2 and both
    # shear modes 1060 J/m2, so dividing the dissipated energy by each brackets the area.
    gc = sorted(float(value) for value in option('--gc', '490,1060').split(','))

    odb = openOdb(odb_path, readOnly=True)
    step = odb.steps[list(odb.steps.keys())[0]]
    if not step.frames:
        print('the step has no frames: the analysis did not run')
        odb.close()
        return
    last = step.frames[-1]
    print('odb %s, step %s, %d frames, ends at t=%.6g s'
          % (odb_path, step.name, len(step.frames), last.frameValue))

    print('\n1. stable increment')
    info = status_report(re.sub(r'\.odb$', '.sta', odb_path))
    if info is None:
        print('   no status file next to the odb')
    else:
        print('   initial %s s, %s increments, %s s per increment on average'
              % (_number(info['initial']), info['increments'], _number(info['mean'])))

    series = {}
    for _, region in step.historyRegions.items():
        for name, output in region.historyOutputs.items():
            if name.upper() in WATCH:
                series.setdefault(name.upper(), output.data)

    print('\n2. energy balance (J)')
    for name in WATCH:
        if name not in series:
            continue
        values = [value for _, value in series[name]]
        print('   %-7s first % .6e  last % .6e  peak % .6e'
              % (name, values[0], values[-1], max(values, key=abs)))
    if 'ETOTAL' in series:
        values = [value for _, value in series['ETOTAL']]
        print('   ETOTAL drift over the step: %+.3f%% of the initial value'
              % (100 * (values[-1] - values[0]) / values[0]))
    if 'ALLDMD' in series and 'ALLIE' in series:
        damage = max(abs(value) for _, value in series['ALLDMD'])
        internal = max(value for _, value in series['ALLIE'])
        print('   ALLDMD peak / ALLIE peak: %.4f'
              % (damage / internal if internal else float('nan')))
        if damage > 0.0:
            areas = [damage / value * 1e6 for value in gc]
            radii = [math.sqrt(area / math.pi) for area in areas]
            print('   ALLDMD -> area %.2f-%.2f mm2, equal area circle radius %.2f-%.2f mm '
                  '(Gc %g to %g J/m2)'
                  % (areas[0], areas[1], radii[0], radii[1], gc[0], gc[1]))

    print('\n3. interfaces, by node height')
    # CSDMG is written only for contact pairs that carry cohesive behaviour, so its
    # presence is also the evidence that the interface interaction is engaged at all
    # rather than silently overridden by the blanket friction assignment.
    damage_field = contact_field(last, 'CSDMG')
    pressure_field = contact_field(last, 'CPRESS')
    if damage_field is None:
        print('   no CSDMG in the odb: is the cohesive interaction assigned?')
    elif pressure_field is None:
        print('   no CPRESS in the odb, so the interface stress cannot be read')
    else:
        # The cohesive interface a node belongs to is its height, and so is the surface it
        # sits on, so one table separates the ply interfaces from the ball and from the
        # impact face. Heights with neither contact nor damage are left out, which drops
        # the ball's facets once it has separated.
        heights = {}
        instance = odb.rootAssembly.instances[damage_field.values[0].instance.name]
        for node in instance.nodes:
            heights[int(node.label)] = node.coordinates[2]
        rows = {}

        def row_for(label):
            z = heights.get(int(label))
            if z is None:
                return None
            return rows.setdefault(round(z * 1e3, 4),
                                   dict(damaged=0, damage=0.0, shear=0.0, shear_t=0.0,
                                        open=0.0, pressure=0.0))

        for value in damage_field.values:
            row = row_for(value.nodeLabel)
            if row is None:
                continue
            if value.data > 0.0:
                row['damaged'] += 1
            row['damage'] = max(row['damage'], value.data)

        # The peak is taken over every frame rather than at the last one. Once the ball has
        # separated the plate relaxes, and the last frame shows a small fraction of the
        # interface stress that decided whether anything delaminated.
        #
        # The columns are chosen to be the delamination drivers, not just the stresses that
        # happen to be largest. QUADS sums only the *tensile* normal traction and the two
        # shear tractions, so a large compressive CPRESS under the impact does not push the
        # interface towards damage at all; it is reported for context and the shear traction
        # magnitude from CSHEARMAG is the number to compare with the interface strength.
        # COPEN says whether the interface opens, which is what makes the normal branch
        # matter in the first place.
        for frame in step.frames:
            for prefix, key in (('CSHEARMAG', 'shear'), ('COPEN', 'open'),
                                ('CPRESS', 'pressure')):
                field = contact_field(frame, prefix)
                if field is None:
                    continue
                for value in field.values:
                    row = rows.get(round(heights.get(int(value.nodeLabel), -1.0) * 1e3, 4))
                    if row is None or value.data <= row[key]:
                        continue
                    row[key] = value.data
                    if prefix == 'CSHEARMAG':
                        row['shear_t'] = frame.frameValue

        print('   %-9s %8s %8s %11s %10s %11s %11s'
              % ('height mm', 'damaged', 'CSDMG', 'CSHEARMAG', 'COPEN', 'CPRESS',
                 'shear at t'))
        print('   %-9s %8s %8s %11s %10s %11s %11s'
              % ('', '', '', 'MPa', 'um', 'MPa', 's'))
        shown = 0
        for z in sorted(rows):
            row = rows[z]
            if not row['damaged'] and not row['shear'] and not row['pressure']:
                continue
            shown += 1
            print('   %-9.4f %8d %8.4f %11.3f %10.4g %11.3f %11.3g'
                  % (z, row['damaged'], row['damage'], row['shear'] * 1e-6,
                     row['open'] * 1e6, row['pressure'] * 1e-6, row['shear_t']))
        if not shown:
            print('   nothing is in contact and nothing is damaged')

    print('\n4. against the impact_3d_v1 anchor (32 N, 313 um)')
    gauge = []
    for region_name, region in step.historyRegions.items():
        for name, output in region.historyOutputs.items():
            upper = name.upper()
            if upper in ('V3', 'U3'):
                gauge.append((region_name.rsplit('.', 1)[-1], upper, output.data))
    for label, name, data in gauge:
        times = [time for time, _ in data]
        values = [value for _, value in data]
        if name == 'U3':
            peak = min(values)
            print('   node %s U3: final % .4e m, peak downward %.1f um'
                  % (label, values[-1], -peak * 1e6))
            continue
        print('   node %s V3: starts % .4f m/s, ends % .4f m/s, rebound ratio %.3f'
              % (label, values[0], values[-1], -values[-1] / values[0]))
        if ball_mass is None or len(times) < 3:
            continue
        # Window of two samples either side rather than one. The first increment carries
        # an impulse from resolving the initial overclosures of the ball's own facets,
        # which is not the impact force, and a one-sample difference picks it up as a peak
        # two orders of magnitude above the real one. The window is 4e-6 s wide, a few per
        # cent of the contact, so it smooths the impulse and the single-precision velocity
        # quantisation without flattening the contact itself.
        window = 2
        print('     first samples V3: %s'
              % ', '.join('%.4f' % value for value in values[:6]))
        print('     last samples V3: %s (flat means the ball has separated)'
              % ', '.join('%.4f' % value for value in values[-4:]))
        force = []
        for i in range(window, len(times) - window):
            span = times[i + window] - times[i - window]
            force.append((ball_mass * (values[i + window] - values[i - window]) / span,
                          times[i]))
        peak = max(force, key=lambda pair: abs(pair[0]))
        print('     ball %.4f g -> peak contact force %.2f N at t=%.4g s'
              % (ball_mass * 1e3, peak[0], peak[1]))
        # The window during which the ball is loaded, from the force it feels. The contact
        # is over when the force returns to zero, and the impact stage is only finished if
        # that happens inside the step.
        threshold = 0.01 * abs(peak[0])
        loaded = [time for value, time in force if abs(value) > threshold]
        print('     loaded from t=%.4g s to t=%.4g s, %.2f%% of the step'
              % (loaded[0], loaded[-1],
                 100 * (loaded[-1] - loaded[0]) / times[-1]))
    odb.close()


if __name__ == '__main__':
    main()
