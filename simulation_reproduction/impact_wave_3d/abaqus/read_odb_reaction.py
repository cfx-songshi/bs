"""Reaction-force history and the degradation variable, read back from an odb.

Written to settle a question the preprocessor cannot answer. `*Damage Evolution` is
accepted alongside the general stress-based criteria for anisotropic materials, but the
keyword's own documentation lists where the evolution applies, and an elastic anisotropic
material is not among them: the list covers cohesive elements, plane-stress elements with
the fibre-reinforced damage model, and, in Explicit, elastic-plastic materials.
Acceptance by the input file processor therefore does not prove the stiffness actually
degrades, and this script is how that gets checked rather than assumed.

A prescribed-displacement test decides it: if the evolution is honoured the reaction
peaks near the initiation strain and then falls, and if it is not the material stays
elastic and the reaction tracks the displacement.

Nodes are given by label rather than by set name because Abaqus/Explicit expands a
node-set history request into one region per node ("Node PART-1-1.5"), so there is no
region carrying the set's name to match against.

    abaqus python read_odb_reaction.py <odb> <RF1> <node-label,node-label,...>
"""
import sys

from odbAccess import openOdb

DEGRADATION_VARIABLES = ('SDEG', 'DAMAGET', 'DAMAGEFT', 'DAMAGEMT', 'DAMAGEFC', 'DAMAGEMC')


def node_label(region_name):
    return region_name.rsplit('.', 1)[-1]


def main():
    if len(sys.argv) < 4:
        raise SystemExit('usage: abaqus python read_odb_reaction.py <odb> <component> '
                         '<node-label,...>')
    odb_path, component = sys.argv[1], sys.argv[2]
    wanted = set(label.strip() for label in sys.argv[3].split(','))

    odb = openOdb(odb_path, readOnly=True)
    step = odb.steps[list(odb.steps.keys())[0]]
    print('odb %s, step %s, %d frames' % (odb_path, step.name, len(step.frames)))

    total = None
    times = None
    matched = 0
    for region_name, region in step.historyRegions.items():
        if node_label(region_name) not in wanted:
            continue
        for name, output in region.historyOutputs.items():
            if name.upper() != component.upper():
                continue
            matched += 1
            series = [value for _, value in output.data]
            if times is None:
                times = [time for time, _ in output.data]
            if total is None:
                total = list(series)
            else:
                # Sum by index: every region here samples the same increments.
                total = [a + b for a, b in zip(total, series)]
    if matched == 0:
        print('  no %s history on the requested nodes' % component)
    else:
        peak_index = max(range(len(total)), key=lambda i: abs(total[i]))
        # The time of the last sample is reported because a reaction that stops rising
        # can mean either "the material softened" or "the ramp never got there", and the
        # two are only distinguishable against the step's end time.
        print('  %s over %d node(s): %d samples, last at t=%.6g s, peak %.6g at t=%.6g s,'
              ' final %.6g' % (component, matched, len(total), times[-1], total[peak_index],
                               times[peak_index], total[-1]))
        if matched > 1:
            print('  final/peak %.4f'
                  % (total[-1] / total[peak_index] if total[peak_index] else float('nan')))

    last = step.frames[-1]
    for variable in DEGRADATION_VARIABLES:
        if variable not in last.fieldOutputs:
            continue
        field = last.fieldOutputs[variable]
        top = 0.0
        for block in field.bulkDataBlocks:
            values = getattr(block, 'data', None)
            if values is None or len(block.data.shape) != 2:
                continue
            for row in block.data:
                top = max(top, float(row[0]))
        print('  field %s at the last frame: max %.6g' % (variable, top))
    odb.close()


if __name__ == '__main__':
    main()
