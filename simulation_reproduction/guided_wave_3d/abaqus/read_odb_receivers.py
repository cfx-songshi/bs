"""Pull the receiver histories and the energy summary out of an Abaqus .odb.

odbAccess ships with Abaqus, so this has to run under Abaqus's own interpreter
rather than the project Python:

    abaqus python read_odb_receivers.py job.odb out.json

One JSON file comes out, holding everything the comparison needs: the U3 history of
every node region that carries one (the RECV set has two nodes), plus the ALLAE /
ALLIE / ALLKE / ETOTAL series. The energies are not decoration -- ALLAE against
ALLIE is the hourglass check for the reduced-integration C3D8R elements this deck
uses, and ETOTAL has to stay flat after the burst because the plate is free and
undamped.
"""
import json
import sys

from odbAccess import openOdb


def node_label(region_name):
    """Recover the node label from a history region name such as 'Node ASSEMBLY.11203'.

    Returns None when the trailing token is not an integer, which is how Abaqus names
    the assembly-level energy region.
    """
    tail = region_name.rsplit('.', 1)[-1]
    try:
        return int(tail)
    except ValueError:
        return None


def main():
    if len(sys.argv) < 3:
        raise SystemExit('usage: abaqus python read_odb_receivers.py job.odb out.json')
    odb_path, out_path = sys.argv[1], sys.argv[2]
    odb = openOdb(odb_path, readOnly=True)
    try:
        steps = {}
        for step_name, step in odb.steps.items():
            regions = {}
            for region_name, region in step.historyRegions.items():
                series = {}
                for key, output in region.historyOutputs.items():
                    series[key] = [[float(t), float(v)] for t, v in output.data]
                if series:
                    regions[region_name] = {'node_label': node_label(region_name),
                                            'series': series}
            steps[step_name] = regions
        out = {'odb': odb_path, 'steps': steps,
               'instances': sorted(odb.rootAssembly.instances.keys())}
    finally:
        odb.close()
    with open(out_path, 'w') as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print('wrote %s: %d step(s)' % (out_path, len(steps)))


if __name__ == '__main__':
    main()
