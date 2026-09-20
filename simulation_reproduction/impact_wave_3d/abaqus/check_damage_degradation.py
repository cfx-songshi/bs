"""Does the damage evolution actually degrade the stiffness on a solid element?

The preprocessor accepts `*Damage Evolution` next to the general stress-based criteria
for anisotropic materials, and those criteria do take solid elements. That is not enough
to conclude that a solid element can carry damage: the keyword's own documentation lists
where the evolution applies, and an elastic anisotropic material is not on the list (it
covers cohesive elements, plane-stress elements with the fibre-reinforced damage model,
and, in Explicit, elastic-plastic materials). An input file that is accepted but whose
evolution is ignored would leave the material elastic and report nothing but a failure
index, which is the kind of quiet failure this project's checks exist to catch.

Each case is a single element loaded by a prescribed displacement, and two loadings are
run side by side because the first version of this test confused them:

  * axial   - the x=0 face held in x, the x=1mm face pulled along x, lateral contraction
              left free. This is uniaxial stress along the fibre, so the reaction is
              E1 * A * strain and fibre tensile failure is what initiates.
  * shear   - the bottom face fully fixed, the top face pushed along x. This is shear in
              the x-z plane, governed by G13, and the first version of this test used it
              while comparing against a hand calculation based on E1. Its reaction came
              out about a fifth of that calculation, which is what sent us looking.

The discriminator is final/peak: if the evolution is honoured the reaction peaks near the
initiation strain and then falls, so the ratio drops well below one; if the criterion
only reports a failure index the material stays elastic and the reaction rises with the
displacement, so the final value is the peak.

The SC8R case with Hashin is the control: that combination is documented to work, so it
must soften. Without the control a flat result could mean the test is wrong rather than
the model, which is exactly what happened the first time.

Run:  python check_damage_degradation.py
"""
import re
import subprocess
import sys
from pathlib import Path

from capability_sweep import (ABAQUS, MAX_STRAIN_LIMITS, MAX_STRESS_LIMITS, block)

HERE = Path(__file__).resolve().parent
RUNS = HERE / 'runs' / 'degradation'

# Hand calculations the measured reactions are compared against. The element is
# 1 mm x 1 mm x 0.5 mm, the fibre runs along x, and the ramp ends at 3.0e-2 strain.
E1 = 1.281e11
G13 = 4.7e9
LENGTH_X = 1e-3
THICKNESS = 5e-4
STRAIN_END = 3.0e-2
DISPLACEMENT_END = STRAIN_END * LENGTH_X
AXIAL_PREDICTION = E1 * (1e-3 * THICKNESS) * STRAIN_END
SHEAR_PREDICTION = G13 * (1e-3 * 1e-3) * (DISPLACEMENT_END / THICKNESS)
STEP_END = 2e-4

NODES = """*Node
1, 0., 0., 0.
2, 1e-3, 0., 0.
3, 1e-3, 1e-3, 0.
4, 0., 1e-3, 0.
5, 0., 0., 5e-4
6, 1e-3, 0., 5e-4
7, 1e-3, 1e-3, 5e-4
8, 0., 1e-3, 5e-4
*Nset, nset=ZERO
1, 4, 5, 8
*Nset, nset=FAR
2, 3, 6, 7
*Nset, nset=TOP
5, 6, 7, 8
*Nset, nset=BOT
1, 2, 3, 4
"""

# Uniaxial stress along the fibre: only x is held on the near face, and the three rigid
# body modes left over are removed at two nodes. Clamping the whole near face instead
# would suppress the lateral contraction and add a Poisson stiffening on top of E1.
AXIAL_BC = """*Boundary, amplitude=RAMP
FAR, 1, 1, 3e-5
*Boundary
ZERO, 1, 1, 0.
1, 2, 2, 0.
1, 3, 3, 0.
2, 3, 3, 0.
"""

SHEAR_BC = """*Boundary, amplitude=RAMP
TOP, 1, 1, 3e-5
*Boundary
BOT, ENCASTRE
"""

STEP = """*Output, history
*Node Output, nset=FAR
RF1
*Node Output, nset=TOP
RF1
*Output, field, frequency=10
*Node Output
U
*Element Output
S, SDEG
*End Step
"""

AMPLITUDE = """*Amplitude, name=RAMP
0., 0., 2e-4, 1.
"""

HASHIN_UD = block('HASHIN', '1.5e9, 1.2e9, 5.0e7, 2.0e8, 7.0e7, 7.0e7',
                  '9.16e4, 7.99e4, 2.2e2, 1.1e3')

CASES = {
    # The loading the hand calculation describes, with and without damage.
    'axial_c3d8_elastic': ('C3D8', 'solid', 'axial', ''),
    'axial_c3d8_max_stress': ('C3D8', 'solid', 'axial',
                              block('MAX STRESS', MAX_STRESS_LIMITS)),
    'axial_c3d8_maxps': ('C3D8', 'solid', 'axial',
                         block('MAXPS', MAX_STRESS_LIMITS.split(',')[0])),
    'axial_c3d8_quads': ('C3D8', 'solid', 'axial',
                         block('QUADS', '1.5e9, 1.2e9, 5.0e7, 2.0e8, 7.0e7')),
    # Control: documented to degrade. Plane stress, so its axial stiffness carries the
    # 1/(1 - nu12*nu21) factor rather than being plain E1.
    'axial_sc8r_hashin': ('SC8R', 'shell', 'axial', HASHIN_UD),
    # The loading the first version of this file actually applied.
    'shear_c3d8_elastic': ('C3D8', 'solid', 'shear', ''),
    'shear_c3d8_max_stress': ('C3D8', 'solid', 'shear',
                              block('MAX STRESS', MAX_STRESS_LIMITS)),
}


def deck(element, kind, loading, damage):
    if kind == 'shell':
        geometry = ('*Shell Section, elset=ALL, material=CFRP, orientation=Fibre\n'
                    '5.0e-4, 5')
    else:
        geometry = ('*Section Controls, name=SC, max degradation=1.0\n'
                    '*Solid Section, elset=ALL, material=CFRP, orientation=Fibre, '
                    'controls=SC\n,')
    damage_block = f'{damage}\n' if damage.strip() else ''
    boundary = AXIAL_BC if loading == 'axial' else SHEAR_BC
    return f"""*Heading
** degradation check, generated by check_damage_degradation.py
*Preprint, echo=NO, model=NO, history=NO, contact=NO
{NODES}*Element, type={element}
1, 1, 2, 3, 4, 5, 6, 7, 8
*Elset, elset=ALL
1,
*Orientation, name=Fibre
1., 0., 0., 0., 1., 0.
3, 0.
{geometry}
*Material, name=CFRP
*Density
1570.,
*Elastic, type=ENGINEERING CONSTANTS
1.281e11, 8.2e9, 8.2e9, 0.27, 0.27, 0.20, 4.7e9, 4.7e9
3.44e9,
{damage_block}*Step, name=S1, nlgeom=NO
*Dynamic, Explicit
, 2e-4
{boundary}{STEP}*End Step
{AMPLITUDE}"""


def reaction_summary(odb, nodes):
    proc = subprocess.run([ABAQUS, 'python', str(HERE / 'read_odb_reaction.py'),
                           str(odb), 'RF1', ','.join(str(n) for n in nodes)],
                          cwd=str(RUNS), capture_output=True, text=True, errors='replace')
    match = re.search(r'(\d+) samples, last at t=([\d.eE+-]+) s, peak ([\d.eE+-]+) at '
                      r't=([\d.eE+-]+) s, final ([\d.eE+-]+)', proc.stdout)
    if not match:
        print(proc.stdout)
        return None
    return dict(samples=int(match.group(1)), last_t=float(match.group(2)),
                peak=float(match.group(3)), peak_t=float(match.group(4)),
                final=float(match.group(5)))


def main():
    RUNS.mkdir(parents=True, exist_ok=True)
    print('fibre along x, prescribed displacement ramped to %.4g m (%.4g strain) over '
          '%.4g s' % (DISPLACEMENT_END, STRAIN_END, STEP_END))
    print('hand calculation for the axial loading: E1*A*strain = %.4g N' % AXIAL_PREDICTION)
    print('hand calculation for the shear loading: G13*A*gamma  = %.4g N\n' % SHEAR_PREDICTION)

    header = ('%-24s %-6s %-6s %10s %11s %10s %11s %10s'
              % ('case', 'elem', 'load', 'last t [s]', 'peak RF1 [N]', 'peak t [s]',
                 'final RF1 [N]', 'final/peak'))
    print(header)
    verdicts = {}
    for name, (element, kind, loading, damage) in CASES.items():
        (RUNS / f'{name}.inp').write_text(deck(element, kind, loading, damage),
                                          encoding='ascii')
        subprocess.run([ABAQUS, f'job={name}', f'input={name}.inp', 'interactive'],
                       cwd=str(RUNS), capture_output=True, text=True, errors='replace')
        odb = RUNS / f'{name}.odb'
        if not odb.exists():
            print('%-24s %-6s %-6s  NO ODB' % (name, element, loading))
            verdicts[name] = 'no odb'
            continue
        loaded_face = (2, 3, 6, 7) if loading == 'axial' else (5, 6, 7, 8)
        info = reaction_summary(odb, nodes=loaded_face)
        if info is None:
            verdicts[name] = 'no rf1'
            continue
        ratio = info['final'] / info['peak'] if info['peak'] else float('nan')
        complete = info['last_t'] >= 0.999 * STEP_END
        prediction = AXIAL_PREDICTION if loading == 'axial' else SHEAR_PREDICTION
        implied = info['final'] / prediction
        verdicts[name] = ('ramp incomplete' if not complete
                          else 'elastic (no degradation)' if ratio > 0.98
                          else 'degrades')
        print('%-24s %-6s %-6s %10.3g %11.4g %10.3g %11.4g %10.3f'
              % (name, element, loading, info['last_t'], info['peak'], info['peak_t'],
                 info['final'], ratio))
        print('%-24s %-6s %-6s  final is %.3f of the %s hand calculation'
              % ('', '', '', implied, loading))
    print()
    for name, verdict in verdicts.items():
        print('%-24s %s' % (name, verdict))
    return 0


if __name__ == '__main__':
    sys.exit(main())
