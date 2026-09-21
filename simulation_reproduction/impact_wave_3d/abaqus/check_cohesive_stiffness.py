"""Measure the stiffness Abaqus uses for contact-based cohesive behaviour.

    abaqus python check_cohesive_stiffness.py

Two 1 mm bricks are stacked and share no nodes at the interface, exactly as the plate
model's plies do not, so the opening between them is carried by the cohesive interaction
alone. The top face is pulled by a slowly prescribed displacement, twenty microseconds
against a 0.39 us axial period, so the response is quasi-static, and the interface normal
stiffness is the traction over the opening. The deck is written both with and without a
data line under *COHESIVE BEHAVIOR, which is the comparison that matters.

Run it with abaqus python rather than python: it launches the jobs and then reads their
odbs, and only abaqus python has odbAccess.

The lateral degrees of freedom are held on the faces either side of the interface and on
the pulled face. Without that the upper brick tilts, the interface opens as a wedge, and
the opening read is the wedge's maximum rather than the value the stiffness belongs to.

What this established
---------------------
The default is 2.37e13 Pa/m, which is the ply scale: E3 over the ply thickness is 3.28e13.
That killed the first explanation offered for the wave model's asymmetric drift, which was
that the default penalty stiffness is far too large.

What this does not establish
----------------------------
It does not measure the cohesive stiffness on its own. The apparent value does not scale
with the specified one, 3.28e13 specified giving 8.20e12 apparent, and a cohesive stiffness
in series with a contact penalty cannot reproduce both numbers at all, it would need a
negative stiffness. So the number here is the combined normal compliance of the contact
pair. Whatever makes the wave model unstable when the data line is omitted, it is not the
value of this stiffness: specifying the measured default itself is stable, and specifying
anything from 1e12 to 3.28e14 is stable too. The working rule that came out of it is to
always give *COHESIVE BEHAVIOR a data line, and the mechanism is still open.
"""
import os
import subprocess
from pathlib import Path

from odbAccess import openOdb

ABAQUS = r'D:\Abaqus\Commands\abaqus.bat'
PLY_THICKNESS = 0.25e-3
AREA = 1e-6

DECK = """*Heading
** %s
*Preprint, echo=NO, model=NO, history=NO, contact=NO
*Node
1, 0., 0., 0.
2, 1e-3, 0., 0.
3, 1e-3, 1e-3, 0.
4, 0., 1e-3, 0.
5, 0., 0., 1e-3
6, 1e-3, 0., 1e-3
7, 1e-3, 1e-3, 1e-3
8, 0., 1e-3, 1e-3
11, 0., 0., 1e-3
12, 1e-3, 0., 1e-3
13, 1e-3, 1e-3, 1e-3
14, 0., 1e-3, 1e-3
15, 0., 0., 2e-3
16, 1e-3, 0., 2e-3
17, 1e-3, 1e-3, 2e-3
18, 0., 1e-3, 2e-3
*Element, type=C3D8
1, 1, 2, 3, 4, 5, 6, 7, 8
2, 11, 12, 13, 14, 15, 16, 17, 18
*Elset, elset=LOWER
1,
*Elset, elset=UPPER
2,
*Nset, nset=BOTTOM
1, 2, 3, 4,
*Nset, nset=MIDLOWER
5, 6, 7, 8,
*Nset, nset=MIDUPPER
11, 12, 13, 14,
*Nset, nset=TOP
15, 16, 17, 18,
*Boundary
BOTTOM, ENCASTRE
TOP, 1, 2
MIDLOWER, 1, 2
MIDUPPER, 1, 2
*Surface, type=ELEMENT, name=LOWER_TOP
LOWER, S2
*Surface, type=ELEMENT, name=UPPER_BOTTOM
UPPER, S1
*Material, name=STEEL
*Density
7800.,
*Elastic
2.1e11, 0.3
*Solid Section, elset=LOWER, material=STEEL
,
*Solid Section, elset=UPPER, material=STEEL
,
*Amplitude, name=RAMP, time=STEP TIME
0., 0.
2e-5, 1.
*Surface Interaction, name=COH
*Cohesive Behavior
%s*Contact
*Contact Inclusions
LOWER_TOP, UPPER_BOTTOM
*Contact Property Assignment
 ,  , COH
*Step, name=PULL, nlgeom=NO
*Dynamic, Explicit
, 4e-5
*Bulk Viscosity
0.06, 1.2
*Boundary
BOTTOM, ENCASTRE
*Boundary, amplitude=RAMP, type=DISPLACEMENT
TOP, 3, 3, 4e-8
*Output, field, number interval=10
*Node Output
U, V
*Contact Output
CDISP, CSTRESS
*Output, history, time interval=2e-7
*Node Output, nset=TOP
RF3, U3
*Energy Output
ALLKE, ALLIE, ETOTAL
*End Step
"""

CASES = (('cohesive_k_default', None),
         ('cohesive_k_ply', '%.6g, %.6g, %.6g\n' % (8.2e9 / PLY_THICKNESS,
                                                    4.7e9 / PLY_THICKNESS,
                                                    3.44e9 / PLY_THICKNESS)))


def launch(work, name, stiffness):
    (work / ('%s.inp' % name)).write_text(
        DECK % (name, '' if stiffness is None else stiffness), encoding='ascii')
    done = subprocess.run([ABAQUS, 'job=%s' % name, 'input=%s.inp' % name,
                           'double=explicit', 'interactive'],
                          cwd=str(work), capture_output=True, text=True)
    if 'COMPLETED' not in done.stdout:
        print('%s did not complete' % name)
        return None
    return work / ('%s.odb' % name)


def report(path):
    odb = openOdb(str(path), readOnly=True)
    step = odb.steps[list(odb.steps.keys())[0]]
    force = None
    for _, region in step.historyRegions.items():
        if 'RF3' in region.historyOutputs:
            data = region.historyOutputs['RF3'].data
            force = sum(value for _, value in data[-4:]) / 4.0
    frame = step.frames[-1]
    keys = [name for name in frame.fieldOutputs.keys() if name.startswith('COPEN')]
    opening = max(value.data for value in frame.fieldOutputs[keys[0]].values) if keys else 0.0
    odb.close()
    if force is None or opening <= 0.0:
        print('%s: no reaction or no opening' % os.path.basename(str(path)))
        return
    print('%-24s traction %10.4e Pa, opening %10.4e m, apparent K %10.4e Pa/m'
          % (os.path.basename(str(path)), force / AREA, opening, force / AREA / opening))


def main():
    work = Path(os.path.abspath(__file__)).parent / 'runs'
    work.mkdir(exist_ok=True)
    print('two brick tension test, run from %s' % work)
    for name, stiffness in CASES:
        path = launch(work, name, stiffness)
        if path is not None:
            report(path)


if __name__ == '__main__':
    main()
