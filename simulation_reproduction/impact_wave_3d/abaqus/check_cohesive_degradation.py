"""Can a solid-element model carry damage that actually changes its response?

The previous check answered the intralaminar question and the answer was no: MAX STRESS
on a solid lets the stress run to 2.6 times the fibre strength while the stiffness stays
exactly elastic. That matters because the guided wave in this project has to detect a
change, so damage that leaves the stiffness alone is useless here.

That leaves the interlaminar route, which is legitimate rather than a workaround: in
low-velocity impact of a thin laminate, delamination is the dominant damage mode. This
check puts a cohesive interface between two solid layers and shears the stack, which is
mode II loading of that interface.

  * interface=solid    - the middle element is ordinary C3D8 of the same material, so the
                         stack is elastic. The reaction must rise monotonically with the
                         displacement: this is the control that shows any softening comes
                         from the cohesive law and not from the geometry or the loading.
  * interface=cohesive - the middle element is COH3D8 with a traction-separation law. The
                         reaction should peak near the interface shear strength times the
                         area and then fall away as the interface fails.

Hand calculations, for the 1 mm x 1 mm footprint and a ramp to 1.2e-4 m:
  elastic stack reaction at the end   = G13 * A * u / h_total
  interface initiation reaction       = shear strength * A
  slip to full failure                = 2 * GIIc / shear strength

Run:  python check_cohesive_degradation.py
"""
import re
import subprocess
import sys
from pathlib import Path

from capability_sweep import ABAQUS

HERE = Path(__file__).resolve().parent
RUNS = HERE / 'runs' / 'cohesive'

G13 = 4.7e9
AREA = 1e-3 * 1e-3
DISPLACEMENT_END = 1.2e-4
STACK_THICKNESS = 1.01e-3
SHEAR_STRENGTH = 30e6
GII_C = 1.0e3
STEP_END = 2e-4

ELASTIC_PREDICTION = G13 * AREA * DISPLACEMENT_END / STACK_THICKNESS
INITIATION_PREDICTION = SHEAR_STRENGTH * AREA
FAILURE_SLIP = 2 * GII_C / SHEAR_STRENGTH

NODES = """*Node
1, 0., 0., 0.
2, 1e-3, 0., 0.
3, 1e-3, 1e-3, 0.
4, 0., 1e-3, 0.
5, 0., 0., 5.0e-4
6, 1e-3, 0., 5.0e-4
7, 1e-3, 1e-3, 5.0e-4
8, 0., 1e-3, 5.0e-4
9, 0., 0., 5.1e-4
10, 1e-3, 0., 5.1e-4
11, 1e-3, 1e-3, 5.1e-4
12, 0., 1e-3, 5.1e-4
13, 0., 0., 1.01e-3
14, 1e-3, 0., 1.01e-3
15, 1e-3, 1e-3, 1.01e-3
16, 0., 1e-3, 1.01e-3
*Nset, nset=BASE
1, 2, 3, 4
*Nset, nset=DRIVEN
13, 14, 15, 16
*Elset, elset=SOLID
1, 3
*Elset, elset=MIDDLE
2,
"""

STEP = """*Step, name=S1, nlgeom=NO
*Dynamic, Explicit
, 2e-4
*Boundary, amplitude=RAMP
DRIVEN, 1, 1, 1.2e-4
*Boundary
BASE, ENCASTRE
*Output, history
*Node Output, nset=DRIVEN
RF1
*Output, field, frequency=10
*Node Output
U
*Element Output
S, SDEG
*End Step
*Amplitude, name=RAMP
0., 0., 2e-4, 1.
"""

SOLID_MATERIAL = """*Material, name=CFRP
*Density
1570.,
*Elastic, type=ENGINEERING CONSTANTS
1.281e11, 8.2e9, 8.2e9, 0.27, 0.27, 0.20, 4.7e9, 4.7e9
3.44e9,
"""

# Interface properties are labelled substitutes, not measured values: a shear strength
# and a mode II fracture energy of the order used for a toughened epoxy interlayer in
# the low-velocity impact literature. The penalty stiffness is the usual kind of value
# for a traction-separation law and only has to be stiff compared with the plies.
#
# The Benzeggagh-Kenane exponent is a keyword parameter, not a data value: the data line
# carries the three fracture energies and the exponent goes in POWER=. Putting a fourth
# number on the data line is accepted without comment and fails with "THE POWER IS NOT
# SPECIFIED OR THE SPECIFIED VALUE IS EQUAL TO OR SMALLER THAN ZERO", which does not name
# the keyword it came from, and moving that fourth number to a second data line does not
# help either. MIXED MODE BEHAVIOR=BK additionally requires a mode mix ratio, and ENERGY
# is the default for element-based cohesive behaviour, so it can be left out.
COHESIVE_MATERIAL = """*Material, name=IFACE
*Density
1570.,
*Elastic, type=TRACTION
1e14, 1e14, 1e14
*Damage Initiation, criterion=QUADS
30e6, 30e6, 30e6
*Damage Evolution, type=ENERGY, mixed mode behavior=BK, power=2.0
1.0e3, 1.0e3, 1.0e3
"""


def deck(interface):
    if interface == 'cohesive':
        middle_element = '2, 5, 6, 7, 8, 9, 10, 11, 12'
        middle_type = 'COH3D8'
        # RESPONSE is required on this release and its value contains a space:
        # TRACTION_SEPARATION is rejected as an illegal value, and omitting the
        # parameter altogether gives "PARAMETER RESPONSE IS REQUIRED".
        sections = ('*Section Controls, name=SC, max degradation=1.0\n'
                    '*Cohesive Section, elset=MIDDLE, material=IFACE, '
                    'response=TRACTION SEPARATION, controls=SC\n'
                    '1.0,\n'
                    '*Solid Section, elset=SOLID, material=CFRP, orientation=Fibre\n'
                    ',')
        material = SOLID_MATERIAL + COHESIVE_MATERIAL
    else:
        middle_element = '2, 5, 6, 7, 8, 9, 10, 11, 12'
        middle_type = 'C3D8'
        sections = ('*Section Controls, name=SC, max degradation=1.0\n'
                    '*Solid Section, elset=MIDDLE, material=CFRP, orientation=Fibre, '
                    'controls=SC\n'
                    ',\n'
                    '*Solid Section, elset=SOLID, material=CFRP, orientation=Fibre, '
                    'controls=SC\n'
                    ',')
        material = SOLID_MATERIAL
    return f"""*Heading
** cohesive check, generated by check_cohesive_degradation.py
*Preprint, echo=NO, model=NO, history=NO, contact=NO
{NODES}** three elements stacked through the thickness: solid / interface / solid
*Element, type=C3D8
1, 1, 2, 3, 4, 5, 6, 7, 8
3, 9, 10, 11, 12, 13, 14, 15, 16
*Element, type={middle_type}
{middle_element}
*Orientation, name=Fibre
1., 0., 0., 0., 1., 0.
3, 0.
{sections}
{material}{STEP}"""


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
    print('a 0.5 mm solid layer, a 0.01 mm interface, another 0.5 mm solid layer,')
    print('sheared by a prescribed 1.2e-4 m on the top face\n')
    print('elastic stack reaction at the end would be %.4g N' % ELASTIC_PREDICTION)
    print('interface initiation reaction would be        %.4g N' % INITIATION_PREDICTION)
    print('slip needed for full interface failure        %.4g m\n' % FAILURE_SLIP)

    print('%-20s %9s %11s %10s %11s %10s'
          % ('interface', 'last t [s]', 'peak RF1 [N]', 'peak t [s]', 'final RF1 [N]',
             'final/peak'))
    verdicts = {}
    for interface in ('solid', 'cohesive'):
        name = f'cohesive_{interface}'
        (RUNS / f'{name}.inp').write_text(deck(interface), encoding='ascii')
        subprocess.run([ABAQUS, f'job={name}', f'input={name}.inp', 'interactive'],
                       cwd=str(RUNS), capture_output=True, text=True, errors='replace')
        odb = RUNS / f'{name}.odb'
        if not odb.exists():
            print('%-20s  NO ODB' % interface)
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
        print('%-20s %9.3g %11.4g %10.3g %11.4g %10.3f'
              % (interface, info['last_t'], info['peak'], info['peak_t'], info['final'],
                 ratio))
    print()
    for interface, verdict in verdicts.items():
        print('%-20s %s' % (interface, verdict))
    return 0


if __name__ == '__main__':
    sys.exit(main())
