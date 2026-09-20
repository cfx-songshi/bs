"""Which built-in damage models does Abaqus/Explicit accept on a 3D solid element?

The literature route for three-dimensional Hashin damage on solids is a user material
(VUMAT), and this machine has no Fortran toolchain, so before giving up the solid
elements it is worth knowing exactly what the built-in library will offer them. Hashin
is only one entry in it.

Two things this script established, both of which contradict a first guess:

  * Hashin is rejected on both C3D8 and C3D8R. It is a plane-stress criterion.
  * The general stress- and strain-based criteria for anisotropic materials are a
    separate family, and the manual states they "can be used with any elements in
    Abaqus that include mechanical behavior". They are written in the local material
    directions, with separate tension and compression limits for X, Y and Z plus three
    shear limits, so unlike a principal-value criterion they can tell fibre failure
    from matrix cracking. The criterion names contain a space.

Each variant is a single-element deck that differs only in the damage block. A variant
passes when the preprocessor and the analysis both complete; the failing line is printed
so a rejected criterion can be told apart from a mistake in the data (an earlier version
of this sweep also omitted *Orientation, and a second bug left a blank line inside the
material data, which Abaqus read as a zero-valued data row; both looked like
rejections).

Run:  python capability_sweep.py
"""
import re
import subprocess
from pathlib import Path

ABAQUS = r'D:\Abaqus\Commands\abaqus.bat'
HERE = Path(__file__).resolve().parent
RUNS = HERE / 'runs'

NODES = """*Node
1, 0., 0., 0.
2, 1e-3, 0., 0.
3, 1e-3, 1e-3, 0.
4, 0., 1e-3, 0.
5, 0., 0., 5e-4
6, 1e-3, 0., 5e-4
7, 1e-3, 1e-3, 5e-4
8, 0., 1e-3, 5e-4
"""

# Labelled substitutes, not measured values for the specimen: elastic constants from the
# T300/F593 set this project already uses, strengths from a T300 measurement of the same
# family, fracture energies from the low-velocity impact models that use this criterion
# set. Max stress takes local X, Y, Z tension and compression then the three shears;
# max strain takes the same limits expressed as strains; Tsai-Wu takes the twelve
# stress-space coefficients with the usual -1/2*sqrt(F11*F22) interaction assumption.
G_FIBRE_T = '9.16e4'
MAX_STRESS_LIMITS = '1.5e9, 1.2e9, 5.0e7, 2.0e8, 5.0e7, 2.0e8, 7.0e7, 7.0e7, 5.0e7'
MAX_STRAIN_LIMITS = ('1.171e-2, 9.368e-3, 6.098e-3, 2.439e-2, 6.098e-3, 2.439e-2, '
                     '1.489e-2, 1.489e-2, 1.453e-2')
TSAIWU_COEFFICIENTS = ('-1.667e-10, 1.5e-8, 1.5e-8, 5.556e-19, 1.0e-16, 1.0e-16, '
                       '-3.727e-18, -3.727e-18, -5.0e-17, 4.0e-16, 2.041e-16, 2.041e-16')


def wrap8(values, per_line=8):
    """Split a data line so that continuation works.

    Abaqus accepts at most eight fields per data line, so max stress with its nine
    limits has to be written as 8 + 1. Passing all nine on one line produced "THERE ARE
    TOO FEW LINES TO DEFINE THIS MATERIAL OPTION", which reads like the criterion being
    unsupported but is only the line length.
    """
    fields = [v.strip() for v in values.split(',')]
    lines = []
    while fields:
        chunk, fields = fields[:per_line], fields[per_line:]
        lines.append(', '.join(chunk) + (',' if fields else ''))
    return '\n'.join(lines)


def block(criterion, data, energy=G_FIBRE_T):
    return (f'*Damage Initiation, criterion={criterion}\n{wrap8(data)}\n'
            f'*Damage Evolution, type=ENERGY\n{wrap8(energy)}')


VARIANTS = {
    # Hashin, for the record: rejected on both solid forms.
    'c3d8_hashin': ('C3D8', block('HASHIN',
                                  '1.5e9, 1.2e9, 5.0e7, 2.0e8, 7.0e7, 7.0e7',
                                  '9.16e4, 7.99e4, 2.2e2, 1.1e3')),
    'c3d8r_hashin': ('C3D8R', block('HASHIN',
                                    '1.5e9, 1.2e9, 5.0e7, 2.0e8, 7.0e7, 7.0e7',
                                    '9.16e4, 7.99e4, 2.2e2, 1.1e3')),
    # A plain elastic solid, to prove the harness itself accepts a solid element.
    'c3d8_elastic': ('C3D8', ''),
    # The family that matters: written in the local material directions.
    'c3d8_max_stress': ('C3D8', block('MAX STRESS', MAX_STRESS_LIMITS)),
    'c3d8_max_strain': ('C3D8', block('MAX STRAIN', MAX_STRAIN_LIMITS)),
    'c3d8_tsaiwu': ('C3D8', block('TSAIWU', TSAIWU_COEFFICIENTS)),
    # Principal-value criteria: one scalar limit, no resolution into material
    # directions, so they cannot separate fibre failure from matrix cracking. Kept as
    # evidence that they do run on solids, not as the intended criterion.
    'c3d8_maxps': ('C3D8', block('MAXPS', MAX_STRESS_LIMITS.split(',')[0])),
    'c3d8_maxpe': ('C3D8', block('MAXPE', MAX_STRAIN_LIMITS.split(',')[0])),
    # Fabric criterion: five modes, but it assumes a balanced weave, which the first
    # stage of this chain (a unidirectional [0]8) is not.
    'c3d8_quads': ('C3D8', block('QUADS', '1.5e9, 1.2e9, 5.0e7, 2.0e8, 7.0e7')),
}


def deck(element, damage):
    # No blank line when there is no damage block: Abaqus reads it as a zero-valued data
    # row and reports an error against *ELASTIC, which is where it happened to be
    # looking, not where the problem was.
    damage_block = f'{damage}\n' if damage.strip() else ''
    return f"""*Heading
** capability sweep, generated by capability_sweep.py
*Preprint, echo=NO, model=NO, history=NO, contact=NO
{NODES}*Element, type={element}
1, 1, 2, 3, 4, 5, 6, 7, 8
*Elset, elset=ALL
1,
*Orientation, name=Fibre
1., 0., 0., 0., 1., 0.
3, 0.
*Section Controls, name=SC, element deletion=YES, max degradation=1.0
*Solid Section, elset=ALL, material=CFRP, orientation=Fibre, controls=SC
,
*Material, name=CFRP
*Density
1570.,
*Elastic, type=ENGINEERING CONSTANTS
1.281e11, 8.2e9, 8.2e9, 0.27, 0.27, 0.20, 4.7e9, 4.7e9
3.44e9,
{damage_block}*Step, name=S1, nlgeom=NO
*Dynamic, Explicit
, 1e-6
*Output, field
*Node Output
U
*End Step
"""


def run(name, element, damage):
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f'{name}.inp').write_text(deck(element, damage), encoding='ascii')
    proc = subprocess.run([ABAQUS, f'job={name}', f'input={name}.inp', 'interactive'],
                          cwd=str(RUNS), capture_output=True, text=True,
                          errors='replace')
    dat = RUNS / f'{name}.dat'
    errors = []
    if dat.exists():
        text = dat.read_text(encoding='latin-1', errors='replace')
        for match in re.finditer(r'\*\*\*ERROR:(.{0,160})', text):
            errors.append(' '.join(match.group(1).split()))
    completed = 'COMPLETED SUCCESSFULLY' in proc.stdout
    status = 'PASS' if completed and not errors else 'FAIL'
    print(f'{status}  {name:18s} element={element:6s}'
          + (f'  <- {errors[0]}' if errors else ''))
    return status == 'PASS', errors


if __name__ == '__main__':
    results = {}
    for name, (element, damage) in VARIANTS.items():
        ok, errs = run(name, element, damage)
        results[name] = (ok, errs[:2])
    print()
    print('accepted by this release on solid elements:',
          [k for k, (ok, _) in results.items() if ok] or 'none of the above')
    print('rejected:', [k for k, (ok, _) in results.items() if not ok])
