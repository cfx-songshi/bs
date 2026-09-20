"""Can a contact-based cohesive interface carry damage that changes the response?

The cohesive-element route was ruled out by measurement: with a physical constitutive
thickness the stable increment collapses to 3.8e-12 s, and with the default 1.0 m the
interface layers come out thousands of times heavier than the plate. Surface-based, or
contact-based, cohesive behaviour avoids both because it introduces no elements at all.

This is the check that it works before any of it is built into the coupon model. Two
solid layers, each one element thick, sheared by a prescribed displacement on the top
face, with the bottom face held:

  * stack     - the two layers share their interface nodes, so the stack is continuous
                and the reaction must rise monotonically. This is the control: any
                softening in the other case has to come from the cohesive law and not
                from the geometry.
  * interface - the interface nodes are duplicated, the two faces are coincident, and a
                contact pair with cohesive behaviour joins them. The reaction should
                reach the interface shear strength times the area and then fall away.

Hand calculations for a 1.25 x 1.25 mm footprint with two 0.25 mm layers:
  shear stress at initiation   = 30e6 Pa
  reaction at initiation       = stress * area                       = 46.9 N
  displacement at initiation   = stress * total thickness / G13      = 3.2e-6 m
  relative slip to full failure= 2 * GIIc / strength                 = 6.67e-5 m
so the prescribed 1e-4 m covers initiation and complete failure of the interface.

The 30 MPa and 1.0 kJ/m2 here are round numbers chosen so the hand calculation above is
exact; they are not the generator's values. What is being checked is the mechanism, that
contact-based cohesive behaviour degrades at all, so the magnitudes do not matter.
make_impact_wave_inp.py uses a published CFRP set and cites it there.

Run:  python check_surface_cohesive.py
"""
import re
import subprocess
import sys
from pathlib import Path

from capability_sweep import ABAQUS

HERE = Path(__file__).resolve().parent
RUNS = HERE / 'runs' / 'surface_cohesive'

SHEAR_STRENGTH = 30e6
GII_C = 1.0e3
G13 = 4.7e9
AREA = 1.25e-3 * 1.25e-3
LAYER = 0.25e-3
DISPLACEMENT_END = 1.0e-4
STEP_END = 2e-4

INITIATION_FORCE = SHEAR_STRENGTH * AREA
INITIATION_SLIP = SHEAR_STRENGTH * 2 * LAYER / G13
FAILURE_SLIP = 2 * GII_C / SHEAR_STRENGTH

NODES = """*Node
1, 0., 0., 0.
2, 1.25e-3, 0., 0.
3, 1.25e-3, 1.25e-3, 0.
4, 0., 1.25e-3, 0.
5, 0., 0., 2.5e-4
6, 1.25e-3, 0., 2.5e-4
7, 1.25e-3, 1.25e-3, 2.5e-4
8, 0., 1.25e-3, 2.5e-4
9, 0., 0., 2.5e-4
10, 1.25e-3, 0., 2.5e-4
11, 1.25e-3, 1.25e-3, 2.5e-4
12, 0., 1.25e-3, 2.5e-4
13, 0., 0., 5.0e-4
14, 1.25e-3, 0., 5.0e-4
15, 1.25e-3, 1.25e-3, 5.0e-4
16, 0., 1.25e-3, 5.0e-4
*Nset, nset=BASE
1, 2, 3, 4
*Nset, nset=DRIVEN
13, 14, 15, 16
*Elset, elset=LOWER
1,
*Elset, elset=UPPER
2,
"""

MATERIAL = """*Material, name=PLY
*Density
1650.,
*Elastic, type=ENGINEERING CONSTANTS
1.281e11, 8.2e9, 8.2e9, 0.27, 0.27, 0.20, 4.7e9, 4.7e9
3.44e9,
"""

INTERACTION = """** Surface-based cohesive behaviour. No data line on *COHESIVE BEHAVIOR means the
** default penalty stiffness is used, so no penalty value has to be invented; and with no
** elements there is no added mass and no stable increment penalty.
*Surface Interaction, name=DELAM
*Cohesive Behavior
*Damage Initiation, criterion=QUADS
30e6, 30e6, 30e6
*Damage Evolution, type=ENERGY, mixed mode behavior=BK, power=2.0
1.0e3, 1.0e3, 1.0e3
"""

STEP = """*Step, name=S1, nlgeom=NO
*Dynamic, Explicit
, 2e-4
*Boundary, amplitude=RAMP
DRIVEN, 1, 1, 1.0e-4
*Boundary
DRIVEN, 3, 3, 0.
BASE, ENCASTRE
*Output, history
*Node Output, nset=DRIVEN
RF1
*Output, field, frequency=10
*Node Output
U
*Element Output
S
*End Step
*Amplitude, name=RAMP
0., 0., 2e-4, 1.
"""

FRICTION = """*Surface Interaction, name=FRIC
*Friction
0.3,
"""


def deck(interface):
    if interface == 'stack':
        upper = '2, 5, 6, 7, 8, 13, 14, 15, 16'
        model_data = ''
    else:
        upper = '2, 9, 10, 11, 12, 13, 14, 15, 16'
        # General contact with the cohesive interaction assigned to the interface pair by
        # name. *CONTACT PAIR rejected both its TYPE and MECHANICAL CONSTRAINT parameters
        # on this release ("UNKNOWN PARAMETER TYPE"), and general contact is the
        # documented route for surface-based cohesive behaviour in Explicit anyway.
        # Assignments are applied in order with later ones taking precedence, so the
        # blanket friction comes first and the interface pair is overridden after.
        surfaces = ('** The two faces of the interface, named so that the cohesive\n'
                    '** interaction can be assigned to this pair alone.\n'
                    '*Surface, type=ELEMENT, name=LOWER_TOP\nLOWER, S2\n'
                    '*Surface, type=ELEMENT, name=UPPER_BOTTOM\nUPPER, S1\n')
        model_data = (surfaces + INTERACTION + FRICTION +
                      '*Contact, op=NEW\n'
                      '*Contact Inclusions, ALL EXTERIOR\n'
                      '*Contact Property Assignment\n'
                      ' ,  , FRIC\n'
                      'UPPER_BOTTOM, LOWER_TOP, DELAM\n')
    return f"""*Heading
** surface cohesive check, generated by check_surface_cohesive.py
*Preprint, echo=NO, model=NO, history=NO, contact=NO
{NODES}*Orientation, name=Fibre
1., 0., 0., 0., 1., 0.
3, 0.
*Element, type=C3D8
1, 1, 2, 3, 4, 5, 6, 7, 8
{upper}
*Solid Section, elset=LOWER, material=PLY, orientation=Fibre
,
*Solid Section, elset=UPPER, material=PLY, orientation=Fibre
,
{MATERIAL}{model_data}{STEP}"""


def reaction_summary(odb):
    proc = subprocess.run([ABAQUS, 'python', str(HERE / 'read_odb_reaction.py'),
                           str(odb), 'RF1', '13,14,15,16'],
                          cwd=str(RUNS), capture_output=True, text=True, errors='replace')
    match = re.search(r'(\d+) samples, last at t=([\d.eE+-]+) s, peak ([\d.eE+-]+) at '
                      r't=([\d.eE+-]+) s, final ([\d.eE+-]+)', proc.stdout)
    if not match:
        print(proc.stdout)
        return None
    return dict(last_t=float(match.group(2)), peak=float(match.group(3)),
                peak_t=float(match.group(4)), final=float(match.group(5)))


def main():
    RUNS.mkdir(parents=True, exist_ok=True)
    print('two 0.25 mm layers, 1.25 x 1.25 mm footprint, top face sheared by %.4g m\n'
          % DISPLACEMENT_END)
    print('hand calculation: initiation reaction %.4g N at %.4g m of slip, full failure '
          'at %.4g m\n' % (INITIATION_FORCE, INITIATION_SLIP, FAILURE_SLIP))

    print('%-12s %9s %11s %10s %11s %10s'
          % ('interface', 'last t [s]', 'peak RF1 [N]', 'peak t [s]', 'final RF1 [N]',
             'final/peak'))
    verdicts = {}
    for interface in ('stack', 'interface'):
        name = f'surfcoh_{interface}'
        (RUNS / f'{name}.inp').write_text(deck(interface), encoding='ascii')
        subprocess.run([ABAQUS, f'job={name}', f'input={name}.inp', 'interactive'],
                       cwd=str(RUNS), capture_output=True, text=True, errors='replace')
        odb = RUNS / f'{name}.odb'
        dat = RUNS / f'{name}.dat'
        if dat.exists():
            text = dat.read_text(encoding='latin-1', errors='replace')
            errors = [' '.join(m.group(1).split())
                      for m in re.finditer(r'\*\*\*ERROR:(.{0,140})', text)]
            if errors:
                print('%-12s  FAILED: %s' % (interface, errors[0]))
                verdicts[interface] = 'error'
                continue
        if not odb.exists():
            print('%-12s  NO ODB' % interface)
            verdicts[interface] = 'no odb'
            continue
        info = reaction_summary(odb)
        if info is None:
            verdicts[interface] = 'no rf1'
            continue
        ratio = info['final'] / info['peak'] if info['peak'] else float('nan')
        complete = info['last_t'] >= 0.999 * STEP_END
        verdicts[interface] = ('ramp incomplete' if not complete
                               else 'elastic (no degradation)' if ratio > 0.98
                               else 'degrades')
        print('%-12s %9.3g %11.4g %10.3g %11.4g %10.3f'
              % (interface, info['last_t'], info['peak'], info['peak_t'], info['final'],
                 ratio))
    print()
    for interface, verdict in verdicts.items():
        print('%-12s %s' % (interface, verdict))
    return 0


if __name__ == '__main__':
    sys.exit(main())
