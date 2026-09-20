"""Generate an Abaqus/Explicit input file for the guided-wave plate.

Status: RUN IN ABAQUS. The deck has been submitted to Abaqus 2026 and completed
(THE ANALYSIS HAS COMPLETED SUCCESSFULLY): a 12x12x4 syntax-check case and a
500x4x4 line-source case at dx = 1.0 mm. The first submission failed twice for
reasons verify_inp could not see -- a bare node id in the assembly-level *Cload and
a missing *Orientation -- so those two errors were found by running the deck, not by
reading it. Section 4 of README.md records both.

What it builds
--------------
The same physical case as the in-house 3D solver (solve_uvg_3d.py) and the 2D model
(guided_wave_v2/solve.py): a flat orthotropic plate, T300/F593, excited at 100 kHz by
a five-cycle Hann-windowed force acting normally on both faces at one location. The
point of keeping them aligned is that the in-house model already agrees with the
analytical Rayleigh-Lamb dispersion to about 0.1-0.4 percent on the A0 phase
velocity, so the same case in Abaqus has a known reference to be compared against.

Choices worth knowing about
---------------------------
* The element type matters more than expected, and measurement overturned the original
  choice. C3D8R was picked because full integration locks in bending, which is exactly
  the deformation A0 is made of. On the verified 500x4x4 mesh -- 12.7 elements per A0
  wavelength -- its hourglass energy reached 17-26% of ALLIE and the amplitude came out
  17% low, while C3D8 matched the in-house solver to within 3%. Use `--element C3D8`
  at that resolution, and read ALLAE against ALLIE before trusting any
  reduced-integration run.
* *Orientation is mandatory. The laminate is unidirectional with the fibres along
  the global x axis, but an anisotropic material still requires an explicit local
  system in Abaqus even when its axes coincide with the global ones; omitting it is
  a hard error (Anisotropic material properties without a local orientation
  system). This docstring used to claim the opposite, and the first submission
  failed because of it.
* Loads written in the assembly must name nodes as instance.node. A bare id is read
  as an assembly-level node and rejected with Unknown assembly id; the first
  submission failed that way too.
* No mass scaling. The in-house model runs at its own stable step too, so the two
  remain comparable; enabling scaling would change the wave speeds being compared.
* Amplitude given as a table sampled every 0.5 us over the 50 us burst. That
  resolves five cycles at 100 kHz with 100 samples per cycle.

Usage
-----
    python make_abaqus_inp.py --nx 40 --ny 40 --nz 4 --out abaqus/small.inp
    python make_abaqus_inp.py --nx 200 --ny 200 --nz 4 --out abaqus/plate.inp
    abaqus job=plate input=plate.inp cpus=8        # Abaqus 2026 lives in D:\\Abaqus
"""
import argparse
import json
import math
from pathlib import Path

MATERIAL = dict(E1=128.1e9, E2=8.2e9, E3=8.2e9, nu12=0.27, nu13=0.27, nu23=0.20,
                G12=4.7e9, G13=4.7e9, G23=3.44e9, rho=1570.0)
THICKNESS = 1.72e-3
FREQ_HZ = 100e3
CYCLES = 5
DURATION = 220e-6
HANN_T = CYCLES / FREQ_HZ


def hann_table(n=101):
    """Five-cycle Hann-windowed sine, peak normalised to 1, as (time, value) pairs."""
    fine = [HANN_T * i / 200000 for i in range(200001)]
    norm = max(abs(math.sin(2 * math.pi * FREQ_HZ * t) * math.sin(math.pi * t / HANN_T) ** 2)
               for t in fine)
    return [(HANN_T * i / (n - 1),
             math.sin(2 * math.pi * FREQ_HZ * (HANN_T * i / (n - 1)))
             * math.sin(math.pi * (HANN_T * i / (n - 1)) / HANN_T) ** 2 / norm)
            for i in range(n)]


def emit(path, nx, ny, nz, lx, ly, thickness=THICKNESS, x_src=0.1, mode='line',
         damage=None, field_interval=2e-6, history_interval=1e-6, duration=DURATION,
         element='C3D8R'):
    dx, dy, dz = lx / nx, ly / ny, thickness / nz
    nnode = (nx + 1) * (ny + 1) * (nz + 1)

    def nid(i, j, k):
        return 1 + i + (nx + 1) * (j + (ny + 1) * k)

    corners = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
               (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]

    # Delamination: mid-surface nodes inside the rectangle get a duplicate that only
    # the elements above the mid plane use, so the two halves share nothing over the
    # damaged area while the crack tips stay connected. Abaqus would normally do this
    # with two instances and a partial tie; writing the split into the mesh keeps the
    # model definition in one part and removes the tie-equation bookkeeping.
    dup = {}
    nzmid = nz // 2
    if damage is not None:
        x0, x1, y0, y1 = damage
        for i in range(nx + 1):
            if not (x0 < i * dx < x1):
                continue
            for j in range(ny + 1):
                if y0 < j * dy < y1:
                    # nnode is the highest id already used, and ids start at 1, so the
                    # first duplicate must be nnode + 1. Starting at nnode silently
                    # overwrote the last original node -- caught by verify_inp.
                    nnode += 1
                    dup[(i, j, nzmid)] = nnode

    src_i = min(max(int(round(x_src / dx)), 0), nx)
    src_j = ny // 2
    recv_nodes = [nid(min(max(int(round(v / dx)), 0), nx), ny // 2, nz)
                  for v in (0.18, 0.32)]

    out = ['*Heading',
           '** Guided-wave plate, T300/F593 unidirectional, 100 kHz five-cycle Hann burst.',
           '** Generated by make_abaqus_inp.py. The 500x4x4 line-source form of this',
           '** deck is run in Abaqus 2026 and compared against the in-house solver in',
           '** section 4b of README.md; the element type and the mesh are the two things',
           '** that decide whether that comparison holds.',
           '*Preprint, echo=NO, model=NO, history=NO, contact=NO',
           '**',
           '*Part, name=Part-1',
           '*Node']
    for k in range(nz + 1):
        z = k * dz
        for j in range(ny + 1):
            y = j * dy
            out.extend('%d, %.7e, %.7e, %.7e' % (nid(i, j, k), i * dx, y, z)
                       for i in range(nx + 1))
    out.extend('%d, %.7e, %.7e, %.7e' % (new, i * dx, j * dy, k * dz)
               for (i, j, k), new in dup.items())
    out.append('*Element, type=%s' % element)
    eid = 0
    for k in range(nz):
        for j in range(ny):
            for i in range(nx):
                eid += 1
                ns = []
                for di, dj, dk in corners:
                    ii, jj, kk = i + di, j + dj, k + dk
                    if kk == nzmid and k >= nzmid and (ii, jj, nzmid) in dup:
                        ns.append(dup[(ii, jj, nzmid)])
                    else:
                        ns.append(nid(ii, jj, kk))
                out.append('%d, %s' % (eid, ', '.join(str(v) for v in ns)))
    out.append('*Elset, elset=ALL, generate')
    out.append('1, %d, 1' % eid)
    out.extend(['**',
                '** Anisotropic properties REQUIRE an explicit local orientation in',
                '** Abaqus, even when the material axes coincide with the global ones.',
                '** Omitting it is a hard error, not a default: the first successful',
                '** submission attempt failed with Anisotropic material properties',
                '** without a local orientation system. Local 1 runs along the fibres',
                '** (global x), local 2 along y, local 3 through the thickness.',
                '*Orientation, name=Fibre',
                '1., 0., 0., 0., 1., 0.',
                '3, 0.',
                '*Solid Section, elset=ALL, material=CFRP, orientation=Fibre',
                ',',
                '*End Part',
                '**',
                '*Material, name=CFRP',
                '*Density',
                '%.3f,' % MATERIAL['rho'],
                '*Elastic, type=ENGINEERING CONSTANTS',
                '%.6e, %.6e, %.6e, %.6e, %.6e, %.6e, %.6e, %.6e,' %
                (MATERIAL['E1'], MATERIAL['E2'], MATERIAL['E3'], MATERIAL['nu12'],
                 MATERIAL['nu13'], MATERIAL['nu23'], MATERIAL['G12'], MATERIAL['G13']),
                '%.6e,' % MATERIAL['G23'],
                '**',
                '*Assembly, name=Assembly',
                '*Instance, name=PLATE-1, part=Part-1',
                '*End Instance',
                # Sets live in the assembly, not the part, once an instance exists.
                '*Nset, nset=RECV, instance=PLATE-1',
                ', '.join(str(v) for v in recv_nodes) + ',',
                '*End Assembly'])

    top_src = [nid(src_i, j, nz) for j in range(ny + 1)] if mode == 'line' \
        else [nid(src_i, src_j, nz)]
    bot_src = [nid(src_i, j, 0) for j in range(ny + 1)] if mode == 'line' \
        else [nid(src_i, src_j, 0)]

    out.extend(['**',
                '** Five-cycle Hann burst at 100 kHz, sampled every 0.5 us, peak 1.',
                '*Amplitude, name=HANN, time=TOTAL TIME'])
    table = hann_table(101)
    for s in range(0, len(table), 4):
        out.append(', '.join('%.7e, %.7e' % tv for tv in table[s:s + 4]))
    out.extend(['**',
                '*Step, name=WAVE, nlgeom=NO',
                '*Dynamic, Explicit',
                ', %.7e' % duration,
                '*Bulk Viscosity',
                '0.06, 1.2',
                '**',
                '** Loads are applied per node; the amplitude times the terminal value',
                '** gives 1 N per metre of width for the line source, matching the',
                '** in-house model. No boundary conditions: a free plate is admissible',
                '** in explicit dynamics and it is what the reference model solves.',
                '*Cload, amplitude=HANN'])
    amp = 1.0 * dy if mode == 'line' else 1.0
    # Loads live in the assembly, where every node reference must carry its instance
    # prefix. A bare id is read as an assembly-level node and rejected -- the first
    # submission of this deck failed with Unknown assembly id 679 for exactly that
    # reason, so the prefix is not cosmetic.
    out.extend('PLATE-1.%d, 3, %.7e' % (n, amp) for n in top_src)
    out.extend('PLATE-1.%d, 3, %.7e' % (n, amp) for n in bot_src)
    out.extend(['**',
                '*Output, field, number interval=%d' % max(1, int(round(duration / field_interval))),
                '*Node Output',
                'U, V',
                '*Output, history, time interval=%.7e' % history_interval,
                '** ALLAE against ALLIE is the hourglass check when reduced integration',
                '** is used; ETOTAL must stay flat once the burst has passed, the plate',
                '** being free and undamped.',
                '*Energy Output',
                'ALLAE, ALLIE, ALLKE, ETOTAL',
                '*Node Output, nset=RECV',
                'U3',
                '*End Step'])

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(out) + '\n', encoding='ascii')
    return dict(path=str(path), elements=eid, nodes=nnode, dx_m=dx, dy_m=dy, dz_m=dz,
                field_output_intervals=max(1, int(round(duration / field_interval))),
                amplitude_samples=len(table))


def verify_inp(path):
    """Static consistency check of a generated file, since Abaqus cannot be run here.

    Parses the *Node, *Element, *Nset and *Cload blocks and checks the things that a
    solver would reject: node references outside the defined range, duplicate ids,
    missing mandatory keywords, and load sets that name nodes that do not exist. This
    cannot prove Abaqus will accept the deck, but it does catch the class of error
    that a hand-built mesh generator is most likely to make.
    """
    text = Path(path).read_text(encoding='ascii').splitlines()
    nodes, elements, refs = set(), 0, []
    problems = []
    section = None
    for raw in text:
        line = raw.strip()
        if not line or line.startswith('**'):
            continue
        if line.startswith('*'):
            section = line.split(',')[0].lower()
            if section not in ('*node', '*element', '*nset', '*cload'):
                continue
            if section == '*node':
                nodes = set()
            continue
        parts = [p.strip() for p in line.split(',')]
        if section == '*node':
            try:
                nid = int(parts[0])
            except ValueError:
                problems.append('node line without id: %s' % line[:60])
                continue
            if nid in nodes:
                problems.append('duplicate node id %d' % nid)
            nodes.add(nid)
        elif section == '*element':
            elements += 1
            if len(parts) < 9:
                problems.append('element %s has %d fields, expected 9' % (parts[0], len(parts)))
            refs.extend(int(p) for p in parts[1:9] if p.lstrip('-').isdigit())
        elif section == '*nset':
            refs.extend(int(p) for p in parts if p.lstrip('-').isdigit())
        elif section == '*cload':
            # Loads sit in the assembly, where a node must be named instance.node. A
            # bare integer there is not a formatting nicety: Abaqus reads it as an
            # assembly-level node and rejects the deck with Unknown assembly id, which
            # is how the first real submission of this generator failed. The original
            # check missed it because it only asked whether the id existed in the part.
            ref = parts[0]
            if '.' not in ref:
                problems.append('*Cload node %r has no instance prefix; assembly-level '
                                'loads must be written instance.node' % ref)
                continue
            node = ref.split('.', 1)[1]
            if node.lstrip('-').isdigit():
                refs.append(int(node))

    if not nodes:
        problems.append('no *Node block found')
    if elements == 0:
        problems.append('no *Element block found')
    bad = sorted({r for r in refs if r not in nodes and r > 0})
    if bad:
        problems.append('%d node references are undefined, e.g. %s' % (len(bad), bad[:5]))

    required = ['*part', '*end part', '*assembly', '*end assembly', '*material',
                '*density', '*elastic', '*solid section', '*amplitude', '*step',
                '*dynamic', '*cload', '*output', '*end step']
    present = {l.strip().split(',')[0].lower() for l in text if l.strip().startswith('*')}
    missing = [k for k in required if k not in present]
    if missing:
        problems.append('missing keywords: %s' % ', '.join(missing))

    return dict(nodes=len(nodes), elements=elements, references=len(refs),
                undefined_references=len(bad), problems=problems)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--nx', type=int, default=40)
    p.add_argument('--ny', type=int, default=40)
    p.add_argument('--nz', type=int, default=4)
    p.add_argument('--lx', type=float, default=0.5)
    p.add_argument('--ly', type=float, default=None)
    p.add_argument('--x-src', type=float, default=0.1)
    p.add_argument('--mode', choices=['line', 'point'], default='line')
    p.add_argument('--element', choices=['C3D8R', 'C3D8'], default='C3D8R',
                   help='reduced (default) or full integration. Reduced integration is '
                        'the usual choice, but at 12.7 elements per A0 wavelength on '
                        'this plate its hourglass energy reached 17-26%% of ALLIE and '
                        'the amplitude came out 17%% low, while C3D8 matched the '
                        'in-house solver to within 3%%; see section 4b of README.md')
    p.add_argument('--damage', type=float, nargs=4, default=None,
                   metavar=('X0', 'X1', 'Y0', 'Y1'))
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--verify', action='store_true', default=True)
    a = p.parse_args()
    info = emit(a.out, a.nx, a.ny, a.nz, a.lx, a.ly if a.ly else a.lx,
                x_src=a.x_src, mode=a.mode, element=a.element,
                damage=tuple(a.damage) if a.damage else None)
    print(json.dumps(info, indent=2))
    if a.verify:
        check = verify_inp(a.out)
        print(json.dumps(check, indent=2))
        if check['problems']:
            raise SystemExit('input file failed its consistency check')


if __name__ == '__main__':
    main()
