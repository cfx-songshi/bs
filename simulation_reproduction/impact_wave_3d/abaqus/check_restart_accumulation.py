"""Small solver check: partial cohesive damage survives restart and damping switches.

Run with abaqus python. This is a capability test, not coupon validation.
The 10/14 um imposed openings are chosen to exercise partial damage.
"""
import json
import subprocess
import sys
from pathlib import Path

from odbAccess import openOdb
from check_cohesive_stiffness import DECK, ABAQUS


def fields(frame, prefix):
    result = {}
    for name, field in frame.fieldOutputs.items():
        if name.startswith(prefix):
            for v in field.values:
                result[str(v.nodeLabel)] = max(result.get(str(v.nodeLabel), 0), float(v.data))
    return result


def main():
    work = Path(__file__).resolve().parent / 'runs' / 'restart_probe'
    work.mkdir(parents=True, exist_ok=True)
    base = DECK % ('restart partial damage test', '2.37e13, 2.37e13, 2.37e13\n')
    base = base.replace('*Contact\n', '*Damage Initiation, criterion=QUADS\n'
                        '59.5e6, 59.5e6, 59.5e6\n'
                        '*Damage Evolution, type=ENERGY, mixed mode behavior=BK, power=2.284\n'
                        '490., 1060., 1060.\n*Contact\n')
    base = base.replace('*Density', '*Damping, alpha=TABULAR, dependencies=1\n'
                        '0., 0., 0.\n20000., 0., 1.\n*Density')
    base = base.replace('*Boundary\nBOTTOM', '*Nset, nset=ALLN\n'
                        '1,2,3,4,5,6,7,8,11,12,13,14,15,16,17,18\n'
                        '*Initial Conditions, type=FIELD, variable=1\nALLN, 0.\n'
                        '*Boundary\nBOTTOM', 1)
    base = base.replace('4e-8', '1e-5').replace('CDISP, CSTRESS', 'CDISP, CSTRESS, CSDMG')
    base = base.replace('ALLKE, ALLIE, ETOTAL', 'ALLKE, ALLIE, ALLSE, ALLVD, ALLDMD, ALLWK, ETOTAL')
    base = base.replace('*End Step', '*Restart, write, number interval=1\n*End Step')
    tail = '''*Amplitude, name=ON, time=STEP TIME
0., 1., 1., 1.
*Amplitude, name=OFF, time=STEP TIME
0., 0., 1., 0.
*Amplitude, name=UNLOAD, time=STEP TIME
0., 1e-5, 2e-5, 0., 4e-5, 0.
*Amplitude, name=RELOAD, time=STEP TIME
0., 0., 2e-5, 1.4e-5, 4e-5, 1.4e-5
*Step, name=RELAX, nlgeom=NO
*Dynamic, Explicit
, 4e-5
*Field, variable=1, amplitude=ON
ALLN, 1.
*Boundary, amplitude=UNLOAD
TOP, 3, 3, 1.
*Restart, write, number interval=1
*End Step
*Step, name=RELOAD, nlgeom=NO
*Dynamic, Explicit
, 4e-5
*Field, variable=1, amplitude=OFF
ALLN, 1.
*Boundary, amplitude=RELOAD
TOP, 3, 3, 1.
*Restart, write, number interval=1
*End Step
'''
    for name, text, old in [('whole', base + tail, None), ('first', base, None),
                            ('continued', '*Heading\n*Restart, read, step=1, interval=1, end step\n' + tail, 'first')]:
        if (work / (name + '.odb')).exists():
            raise RuntimeError('refusing to overwrite probe: ' + name)
        (work / (name + '.inp')).write_text(text, encoding='ascii')
        cmd = [ABAQUS, 'job=' + name, 'input=' + name + '.inp', 'double=explicit', 'interactive']
        if old:
            cmd.append('oldjob=' + old)
        done = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True)
        (work / (name + '.launch.txt')).write_text(done.stdout + done.stderr)
        sta = work / (name + '.sta')
        if done.returncode or not sta.exists() or 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' not in sta.read_text():
            raise RuntimeError('probe failed: ' + name + '; inspect ' + str(work))
    whole = openOdb(str(work / 'whole.odb'), readOnly=True)
    first = openOdb(str(work / 'first.odb'), readOnly=True)
    continued = openOdb(str(work / 'continued.odb'), readOnly=True)
    initial = fields(first.steps['PULL'].frames[-1], 'CSDMG')
    inherited = fields(continued.steps['RELAX'].frames[0], 'CSDMG')
    final = fields(continued.steps['RELOAD'].frames[-1], 'CSDMG')
    expected = fields(whole.steps['RELOAD'].frames[-1], 'CSDMG')
    assert initial and 0.01 < max(initial.values()) < 0.99, initial
    assert initial.keys() == inherited.keys() == final.keys() == expected.keys()
    continuity = max(abs(initial[k] - inherited[k]) for k in initial)
    equivalence = max(abs(final[k] - expected[k]) for k in final)
    assert continuity < 1e-6 and equivalence < 1e-6
    assert max(final.values()) > max(initial.values()) + 0.01
    energies = {}
    for stepname in ('PULL', 'RELAX', 'RELOAD'):
        step = whole.steps[stepname]
        region = next(r for r in step.historyRegions.values() if 'ALLDMD' in r.historyOutputs)
        energies[stepname] = {k: [float(v.data[0][1]), float(v.data[-1][1])]
                              for k, v in region.historyOutputs.items()
                              if k in ('ALLDMD', 'ALLVD', 'ETOTAL')}
    # ALLVD includes bulk viscosity, so report rather than assume its OFF delta is zero.
    report = dict(passed=True, inherited_damage_max=max(initial.values()),
                  final_damage_max=max(final.values()), continuity_max_error=continuity,
                  restart_vs_whole_damage_max_error=equivalence, energy_J=energies)
    (work / 'verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    for odb in (whole, first, continued):
        odb.close()


if __name__ == '__main__':
    main()
