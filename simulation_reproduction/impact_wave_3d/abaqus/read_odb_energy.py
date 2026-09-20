"""Whole-model energies from an odb, for the energy balance check.

Every model this project builds is expected to show its bookkeeping: internal plus
kinetic plus damage energy should track the work done, and a drift means the time step or
the contact is misbehaving. This reads the whole-model energy history and reports the
quantities that matter, plus the initial kinetic energy, which doubles as a way to weigh
the model: give every node a known velocity and the initial kinetic energy is half the
mass times the velocity squared.

    abaqus python read_odb_energy.py <odb>
"""
import sys

from odbAccess import openOdb

WATCH = ('ALLKE', 'ALLIE', 'ALLSE', 'ALLAE', 'ALLDMD', 'ALLPD', 'ALLWK', 'ETOTAL')


def main():
    if len(sys.argv) < 2:
        raise SystemExit('usage: abaqus python read_odb_energy.py <odb>')
    odb = openOdb(sys.argv[1], readOnly=True)
    step = odb.steps[list(odb.steps.keys())[0]]
    print('odb %s, step %s, %d frames' % (sys.argv[1], step.name, len(step.frames)))

    series = {}
    for region_name, region in step.historyRegions.items():
        for name, output in region.historyOutputs.items():
            if name.upper() in WATCH:
                series.setdefault(name.upper(), output.data)
    if not series:
        print('  no whole-model energy history found')
        odb.close()
        return

    for name in WATCH:
        if name not in series:
            continue
        data = series[name]
        values = [value for _, value in data]
        first, last = values[0], values[-1]
        peak = max(values, key=abs)
        print('  %-7s first % .6e  last % .6e  peak % .6e at t=%.6g'
              % (name, first, last, peak, data[values.index(peak)][0]))

    if 'ALLIE' in series:
        internal = max(value for _, value in series['ALLIE'])
        if internal > 0:
            for name in ('ALLAE', 'ALLDMD', 'ALLPD'):
                if name in series:
                    peak = max(abs(value) for _, value in series[name])
                    print('  %s peak is %.4f%% of peak ALLIE' % (name, 100 * peak / internal))
    odb.close()


if __name__ == '__main__':
    main()
