"""Export the odb histories the stage report plots, as one JSON.

Run it with Abaqus python, not plain python: only its interpreter has odbAccess.

    abaqus python review\\export_history.py

Two things are exported.

The impact case's own histories: the ball reference node's V3 is the contact force
divided by the ball mass while the ball is a free rigid body, the top centre node's U3 is
the impact point deflection, and the energy histories are what says whether the step
behaved. The regions are matched by the output names rather than by node label, because
the sidecar for that run predates the labels being written into it.

The wavelength cases: the out of plane velocity at every sensor node, from the sidecar
that names them. These are what the damage indicator is computed from, so plotting them
is how the indicator can be checked by eye rather than only trusted.
"""
import json
import os
import sys

from odbAccess import openOdb

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(os.path.dirname(HERE), 'simulation_reproduction', 'impact_wave_3d',
                    'abaqus', 'runs', 'impact')
ENERGY = ('ALLDMD', 'ALLIE', 'ALLKE', 'ALLSE', 'ETOTAL')


def odb_path(name):
    return os.path.join(RUNS, '%s.odb' % name)


def impact(name):
    odb = openOdb(odb_path(name), readOnly=True)
    step = odb.steps[list(odb.steps.keys())[0]]
    out = dict(histories={}, energies={})
    for _, region in step.historyRegions.items():
        for output_name, output in region.historyOutputs.items():
            upper = output_name.upper()
            if upper in ('V3', 'U3') and upper not in out['histories']:
                out['histories'][upper] = [list(pair) for pair in output.data]
            if upper in ENERGY:
                out['energies'][upper] = [list(pair) for pair in output.data]
    out['frames'] = len(step.frames)
    out['end_s'] = step.frames[-1].frameValue if step.frames else None
    odb.close()
    return out


def wave(name):
    sidecar_path = os.path.join(RUNS, '%s.sensors.json' % name)
    with open(sidecar_path, 'r') as handle:
        sidecar = json.load(handle)
    sensors = dict((key, entry['node']) for key, entry in sidecar['sensors'].items())
    odb = openOdb(odb_path(name), readOnly=True)
    step = odb.steps[list(odb.steps.keys())[0]]
    by_label = dict((str(label), {}) for label in sensors.values())
    for region_name, region in step.historyRegions.items():
        if not region_name.startswith('Node'):
            continue
        label = region_name.rsplit('.', 1)[-1].split()[0]
        if label not in by_label:
            continue
        for output_name, output in region.historyOutputs.items():
            upper = output_name.upper()
            if upper in ('V3', 'U3'):
                by_label[label][upper] = [list(pair) for pair in output.data]
    odb.close()
    return dict((key, by_label[str(label)]) for key, label in sensors.items())


def main():
    data = dict(impact={}, wave={})
    for name in ('imp_mid',):
        print('reading %s' % name)
        data['impact'][name] = impact(name)
    for name in ('wav_base', 'wav_d03_r08', 'wav_d08_r31'):
        print('reading %s' % name)
        data['wave'][name] = wave(name)
    out = os.path.join(HERE, 'history_data.json')
    with open(out, 'w') as handle:
        json.dump(data, handle)
    print('wrote %s' % out)


if __name__ == '__main__':
    sys.exit(main())
