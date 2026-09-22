"""One free brick: verify OFF / ON / OFF mass damping against exp(-alpha*t)."""
import json
import math
from pathlib import Path
import subprocess

from odbAccess import openOdb

ABAQUS = r'D:\Abaqus\Commands\abaqus.bat'


def main():
    work=Path(__file__).resolve().parent/'runs'/'damping_switch'
    work.mkdir(parents=True,exist_ok=True)
    name='switch'
    if (work/'switch.odb').exists():
        raise RuntimeError('refusing to overwrite existing probe')
    deck='''*Heading
** Free rigid translation: analytic damping check, not material calibration
*Node, nset=ALLN
1, 0, 0, 0
2, .001, 0, 0
3, .001, .001, 0
4, 0, .001, 0
5, 0, 0, .001
6, .001, 0, .001
7, .001, .001, .001
8, 0, .001, .001
*Element, type=C3D8, elset=BODY
1, 1,2,3,4,5,6,7,8
*Solid Section, elset=BODY, material=MAT
,
*Material, name=MAT
*Density
1650.
*Elastic
8.2e9, .3
*Damping, alpha=TABULAR, dependencies=1
0., 0., 0.
20000., 0., 1.
*Initial Conditions, type=FIELD, variable=1
ALLN, 0.
*Initial Conditions, type=VELOCITY
ALLN, 1, 1.
*Amplitude, name=ON
0.,1.,1.,1.
*Amplitude, name=OFF
0.,0.,1.,0.
'''
    for stage,amp,duration in [('OFF1','OFF',20e-6),('ON','ON',50e-6),('OFF2','OFF',20e-6)]:
        deck+='''*Step, name=%s, nlgeom=NO
*Dynamic, Explicit
, %.12g
*Field, variable=1, amplitude=%s
ALLN, 1.
*Output, field, number interval=10
*Node Output
V
*Output, history, time interval=1e-6
*Energy Output
ALLKE, ALLVD, ETOTAL
*End Step
'''%(stage,duration,amp)
    (work/'switch.inp').write_text(deck,encoding='ascii')
    done=subprocess.run([ABAQUS,'job=switch','input=switch.inp','double=explicit','interactive'],
                        cwd=work,capture_output=True,text=True)
    (work/'launch.txt').write_text(done.stdout+done.stderr)
    assert done.returncode==0 and 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in (work/'switch.sta').read_text()
    odb=openOdb(str(work/'switch.odb'),readOnly=True)
    measured={name:sum(float(v.data[0]) for v in step.frames[-1].fieldOutputs['V'].values)/8
              for name,step in odb.steps.items()}
    expected=dict(OFF1=1.,ON=math.exp(-1),OFF2=math.exp(-1))
    error=max(abs(measured[k]-expected[k]) for k in expected)
    assert error<.001,(measured,expected)
    off_tail=[float(f.fieldOutputs['V'].values[0].data[0]) for f in odb.steps['OFF2'].frames[1:]]
    assert max(off_tail)-min(off_tail)<1e-7
    result=dict(passed=True,measured_velocity=measured,expected_velocity=expected,max_error=error,
                off_tail_velocity_range=max(off_tail)-min(off_tail),
                limitation='OFF transition retains an integration transient (~0.26% on this coarse timestep); subsequent OFF velocity is constant')
    (work/'verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    odb.close()


if __name__=='__main__':
    main()
