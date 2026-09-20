"""Abaqus input for ball-drop impact damage followed by guided-wave interrogation.

This is the first stage of the chain the project is building: drop a ball on the plate,
let the impact leave damage, then interrogate that damage with guided waves. This file
covers the impact stage only; the wave step is added once the impact damages something.

What the model contains
-----------------------
* A rectangular coupon meshed with a structured grid. The in-plane element size is set
  by the guided-wave requirement of ten elements per A0 wavelength at 100 kHz, which is
  the same rule the validated wave models use, so the two stages can share one mesh.
* One solid element per ply through the thickness, so the ply boundaries, and therefore
  the cohesive interfaces, sit where the real ones do.
* The interface is contact-based cohesive behaviour, not cohesive elements. The nodes at
  each ply boundary are duplicated, so the two faces are separate and coincident, and a
  general-contact assignment gives that one pair the cohesive interaction. This is the
  only mechanism found that lets a solid-element model carry damage which changes its
  response: the general stress criteria flag failure on solids but never move the
  stiffness (see check_damage_degradation.py), and cohesive *elements* were ruled out by
  measurement because they take their mass from the constitutive thickness and collapse
  the stable increment (see check_surface_cohesive.py).
* A rigid ball, faceted, driven by an initial velocity, with a point mass on its
  reference node equal to the real ball so that the impact energy is the real energy.
* General contact, all exterior, with friction. General contact is used rather than a
  named pair because it is the documented route for surface-based cohesive behaviour in
  Explicit, and because every ply face at an interface is its own free surface once the
  nodes are duplicated, so all of them are exterior and all of them are contact faces.

Two things are deliberately crude at this stage and are reported rather than hidden
----------------------------------------------------------------------------------------
* The in-plane mesh cannot resolve the contact patch. At 1.25 mm elements and a contact
  radius of a few tenths of a millimetre, the contact pressure is lumped onto one or two
  elements, so the impact force and the damage extent are mesh dependent. The purpose of
  this stage is the chain, not the damage prediction; a local submodel or a graded mesh
  is the fix, and the project's impact route already works that way.
* The failure index of the general criterion is requested as a diagnostic only. It tells
  where the plies would fail first; it does not degrade anything.

Run:  python make_impact_wave_inp.py --out <path.inp>
"""
import argparse
from pathlib import Path

# T300/F593 elastic constants, the substitute set this project already uses, and
# strengths and fracture energies from the low-velocity impact literature. All are
# labelled substitutes, not measurements of the specimen.
ELASTIC = '1.281e11, 8.2e9, 8.2e9, 0.27, 0.27, 0.20, 4.7e9, 4.7e9\n3.44e9,'
# Nine limits need two data lines, eight fields per line; on one line Abaqus reports
# "THERE ARE TOO FEW LINES TO DEFINE THIS MATERIAL OPTION" and then "THE SHEAR STRENGTH
# IN 2-3 PLANE MUST BE GREATER THAN ZERO", neither of which points at the line length.
PLY_STRENGTHS = ('1.5e9, 1.2e9, 5.0e7, 2.0e8, 5.0e7, 2.0e8, 7.0e7, 7.0e7,\n'
                 '5.0e7')
G_PLY = '9.16e4'          # fibre tensile fracture energy, for the index's evolution
RHO_PLY = 1650.0
G_PLY_AXIAL = 100.0       # penalty for the index's stiffness, not used for damage

# Interface: cohesive traction-separation, quadratic stress initiation, B-K evolution.
IFACE_STRENGTH = '30e6, 30e6, 30e6'
IFACE_ENERGY = '1.0e3, 1.0e3, 1.0e3'
IFACE_POWER = 2.0

BALL_RADIUS = 4.0e-3
BALL_RHO = 14800.0
BALL_N_LAT = 90
BALL_N_LON = 120
FRICTION = 0.3


def sphere(centre, radius, n_lat, n_lon):
    """Lat-long facet mesh for a rigid ball, from the bottom pole up.

    Facets are about 0.14 mm across near the bottom pole, which is where contact
    happens, because the latitude steps are small there while the azimuthal spacing
    shrinks with the radius from the axis anyway.
    """
    import math
    cx, cy, cz = centre
    nodes = [(cx, cy, cz - radius)]          # bottom pole
    for lat in range(1, n_lat):
        theta = math.pi * lat / n_lat
        z = cz - radius * math.cos(theta)
        r = radius * math.sin(theta)
        for lon in range(n_lon):
            phi = 2.0 * math.pi * lon / n_lon
            nodes.append((cx + r * math.cos(phi), cy + r * math.sin(phi), z))
    nodes.append((cx, cy, cz + radius))      # top pole
    top = len(nodes)

    faces = []
    # fan at the bottom pole
    for lon in range(n_lon):
        a = 1 + lon
        b = 1 + (lon + 1) % n_lon
        faces.append((0, b, a))              # triangles, wound to face outwards
    # quad bands
    for lat in range(n_lat - 2):
        first = 1 + lat * n_lon
        second = first + n_lon
        for lon in range(n_lon):
            a = first + lon
            b = first + (lon + 1) % n_lon
            c = second + (lon + 1) % n_lon
            d = second + lon
            faces.append((a, b, c, d))
    # fan at the top pole
    last = 1 + (n_lat - 2) * n_lon
    for lon in range(n_lon):
        a = last + lon
        b = last + (lon + 1) % n_lon
        faces.append((top, a, b))
    return nodes, faces


def build(nx, ny, nz, lx, ly, thickness):
    """Nodes, elements and the sets the deck needs.

    Node planes: every ply boundary carries two coincident planes, the top of one ply and
    the bottom of the next, so there are two planes per ply. They are what makes the
    interface a pair of separate faces, which is what contact-based cohesive behaviour
    needs; the ply elements share nodes with their own plane only, so the stack is joined
    by the contact at the interface and by nothing else.
    """
    dz = thickness / nz
    n_planes = 2 * nz

    def nid(i, j, plane):
        return 1 + i + (nx + 1) * (j + (ny + 1) * plane)

    def zed(plane):
        # planes 0 and 1 are both at the bottom/top of ply 1, and so on
        return ((plane + 1) // 2) * dz

    nodes = []
    for plane in range(n_planes):
        z = zed(plane)
        for j in range(ny + 1):
            for i in range(nx + 1):
                nodes.append((i * lx / nx, j * ly / ny, z))

    ply_elements, ply_elset = [], []
    for ply in range(nz):
        bottom, top = 2 * ply, 2 * ply + 1
        for j in range(ny):
            for i in range(nx):
                ply_elements.append((nid(i, j, bottom), nid(i + 1, j, bottom),
                                     nid(i + 1, j + 1, bottom), nid(i, j + 1, bottom),
                                     nid(i, j, top), nid(i + 1, j, top),
                                     nid(i + 1, j + 1, top), nid(i, j + 1, top)))
                ply_elset.append(len(ply_elements))

    # No interface elements. The interface is a contact pair carrying cohesive behaviour,
    # which needs the two faces to be separate, and that is what the duplicated node
    # planes above provide. Cohesive elements were tried first and ruled out by
    # measurement: they take their mass from the constitutive thickness and they collapse
    # the stable increment (see check_surface_cohesive.py).
    return dict(nodes=nodes, ply_elements=ply_elements, nid=nid, dz=dz,
                n_planes=n_planes)


def emit(options):
    nx, ny, nz = options.nx, options.ny, options.nz
    lx, ly = options.lx, options.ly
    thickness = options.thickness
    mesh = build(nx, ny, nz, lx, ly, thickness)
    nodes = mesh['nodes']
    dt = mesh['dz']

    import math
    ball_mass = BALL_RHO * 4.0 / 3.0 * math.pi * BALL_RADIUS ** 3
    drop_height = options.drop_mm * 1e-3
    speed = math.sqrt(2.0 * 9.80665 * drop_height)
    energy = 0.5 * ball_mass * speed ** 2
    ball_nodes, ball_faces = sphere((lx / 2.0, ly / 2.0, thickness + BALL_RADIUS),
                                    BALL_RADIUS, BALL_N_LAT, BALL_N_LON)
    ball_node_offset = len(nodes)
    ref_node = ball_node_offset + len(ball_nodes) + 1

    out = ['*Heading',
           '** Ball-drop impact on a %g x %g x %g mm coupon, %d plies, contact-based'
           % (lx * 1e3, ly * 1e3, thickness * 1e3, nz),
           '** cohesive between them, generated by make_impact_wave_inp.py. Impact stage'
           ' only.',
           '** In-plane %g mm: set by ten elements per A0 wavelength at 100 kHz, which'
           % (lx / nx * 1e3),
           '** is the rule the validated wave models use, so one mesh serves both stages.',
           '*Preprint, echo=NO, model=NO, history=NO, contact=NO',
           '*Node']
    for index, (x, y, z) in enumerate(nodes, start=1):
        out.append('%d, %.10g, %.10g, %.10g' % (index, x, y, z))
    for index, (x, y, z) in enumerate(ball_nodes, start=ball_node_offset + 1):
        out.append('%d, %.10g, %.10g, %.10g' % (index, x, y, z))
    out.append('%d, %.10g, %.10g, %.10g' % (ref_node, lx / 2.0, ly / 2.0,
                                            thickness + BALL_RADIUS))

    out.append('** solid elements, one per ply')
    out.append('*Element, type=C3D8')
    for index, connectivity in enumerate(mesh['ply_elements'], start=1):
        out.append('%d, %s' % (index, ', '.join(str(n) for n in connectivity)))

    out.append('** rigid facets of the ball')
    out.append('*Element, type=R3D4')
    for index, connectivity in enumerate(ball_faces, start=1):
        if len(connectivity) == 3:
            continue
        out.append('%d, %s' % (len(mesh['ply_elements']) + index,
                               ', '.join(str(ball_node_offset + 1 + n)
                                         for n in connectivity)))
    out.append('*Element, type=R3D3')
    for index, connectivity in enumerate(ball_faces, start=1):
        if len(connectivity) != 3:
            continue
        out.append('%d, %s' % (len(mesh['ply_elements']) + index,
                               ', '.join(str(ball_node_offset + 1 + n)
                                         for n in connectivity)))

    # The ball's mass and inertia belong on its reference node, and *MASS takes an
    # element set, not a node set: asking for a node set gives "Unknown assembly set".
    # One-node MASS and ROTARYI elements carry the values.
    n_ply_elements = len(mesh['ply_elements'])
    n_ball = len(ball_faces)
    mass_element = n_ply_elements + n_ball + 1
    inertia_element = mass_element + 1
    out.append('*Element, type=MASS')
    out.append('%d, %d' % (mass_element, ref_node))
    out.append('*Element, type=ROTARYI')
    out.append('%d, %d' % (inertia_element, ref_node))
    out.append('*Elset, elset=BALLMASS')
    out.append('%d,' % mass_element)
    out.append('*Elset, elset=BALLINERTIA')
    out.append('%d,' % inertia_element)
    out.append('*Elset, elset=PLIES, generate')
    out.append('1, %d, 1' % n_ply_elements)
    # One elset per ply so that each interface can be named as a pair of faces. The
    # element numbering runs ply by ply, so a range is enough.
    per_ply = nx * ny
    for ply in range(nz):
        out.append('*Elset, elset=LAYER%d, generate' % (ply + 1))
        out.append('%d, %d, 1' % (ply * per_ply + 1, (ply + 1) * per_ply))
    for interface in range(nz - 1):
        out.append('*Surface, type=ELEMENT, name=IFACE%d_LOWER' % (interface + 1))
        out.append('LAYER%d, S2' % (interface + 1))
        out.append('*Surface, type=ELEMENT, name=IFACE%d_UPPER' % (interface + 1))
        out.append('LAYER%d, S1' % (interface + 2))
    out.append('*Elset, elset=BALL, generate')
    out.append('%d, %d, 1' % (n_ply_elements + 1, n_ply_elements + n_ball))
    # R3D3 and R3D4 are rigid facets: they only become a rigid body, with this reference
    # node as its single point of control, through *RIGID BODY.
    out.append('*Rigid Body, ref node=%d, elset=BALL' % ref_node)

    # The clamped frame: everything within a border of the coupon edge is held, which is
    # the same idealisation the earlier impact route used.
    border = max(1, int(round(0.01 / (lx / nx))))
    clamped = []
    for plane in range(mesh['n_planes']):
        for j in range(ny + 1):
            for i in range(nx + 1):
                if i < border or j < border or i > nx - border or j > ny - border:
                    clamped.append(mesh['nid'](i, j, plane))
    out.append('*Nset, nset=FRAME')
    out.append(_wrap(clamped))
    out.append('*Nset, nset=BALLREF')
    out.append('%d,' % ref_node)

    # Impact point: the node at the centre of the top face, for the deflection anchor.
    out.append('*Nset, nset=TOPCENTRE')
    out.append('%d,' % mesh['nid'](nx // 2, ny // 2, mesh['n_planes'] - 1))

    out.append('*Orientation, name=Fibre')
    out.append('1., 0., 0., 0., 1., 0.')
    out.append('3, 0.')
    out.append('*Section Controls, name=SC, max degradation=1.0')
    out.append('*Solid Section, elset=PLIES, material=PLY, orientation=Fibre, '
               'controls=SC')
    out.append(',')

    out.append('*Material, name=PLY')
    out.append('*Density')
    out.append('%.1f,' % RHO_PLY)
    out.append('*Elastic, type=ENGINEERING CONSTANTS')
    out.append(ELASTIC)
    out.append('** Diagnostic only: the failure index locates intralaminar failure but,')
    out.append('** as check_damage_degradation.py shows, it does not degrade a solid')
    out.append('** element. The stiffness reduction comes from the cohesive interfaces.')
    out.append('*Damage Initiation, criterion=MAX STRESS')
    out.append(PLY_STRENGTHS)
    out.append('*Damage Evolution, type=ENERGY')
    out.append(G_PLY)

    out.append('** Interface: contact-based cohesive behaviour. There is no cohesive')
    out.append('** element and therefore no cohesive material; the traction-separation')
    out.append('** law, its initiation criterion and its evolution all live on the')
    out.append('** surface interaction. Omitting the data line on *COHESIVE BEHAVIOR')
    out.append('** means the default penalty stiffness is used, so none has to be invented.')
    out.append('*Surface Interaction, name=DELAM')
    out.append('*Cohesive Behavior')
    out.append('*Damage Initiation, criterion=QUADS')
    out.append(IFACE_STRENGTH)
    out.append('*Damage Evolution, type=ENERGY, mixed mode behavior=BK, power=%g'
               % IFACE_POWER)
    out.append(IFACE_ENERGY)

    out.append('*Mass, elset=BALLMASS')
    out.append('%.6e,' % ball_mass)
    out.append('** Rotational inertia of a solid sphere, 2/5 m r^2. A central impact does')
    out.append('** not spin the ball; the value is here so the rigid body is well posed.')
    out.append('*Rotary Inertia, elset=BALLINERTIA')
    out.append('%.6e, %.6e, %.6e' % (2.0 / 5.0 * ball_mass * BALL_RADIUS ** 2,
                                      2.0 / 5.0 * ball_mass * BALL_RADIUS ** 2,
                                      2.0 / 5.0 * ball_mass * BALL_RADIUS ** 2))
    out.append('*Initial Conditions, type=VELOCITY')
    # Three fields, not four. Written as "node, dof, magnitude". Adding a second dof field
    # in the hope of a "first dof, last dof" range, which is how *BOUNDARY reads the same
    # shape of line, makes Abaqus read the magnitude from the third field and ignore the
    # fourth: the ball was given 3 m/s, the dof number, whatever drop height was asked for,
    # with no warning in the .dat. Both a deformable node and a rigid-body reference node
    # in one test deck came out at the dof value, 1 for dof 1 and 3 for dof 3. The energy
    # check in abaqus/read_odb_impact_summary.py is what caught it, and the field count is
    # now checked below so it cannot come back silently.
    out.append('%d, 3, %.6e' % (ref_node, -speed))

    out.append('*Surface Interaction, name=FRIC')
    out.append('*Friction')
    out.append('%g,' % FRICTION)
    out.append('*Contact, op=NEW')
    out.append('*Contact Inclusions, ALL EXTERIOR')
    out.append('** The blanket friction assignment comes first and the interface pairs')
    out.append('** after it, because a later assignment takes precedence over an earlier')
    out.append('** one for the same pair.')
    out.append('*Contact Property Assignment')
    out.append(' ,  , FRIC')
    for interface in range(nz - 1):
        out.append('IFACE%d_UPPER, IFACE%d_LOWER, DELAM'
                   % (interface + 1, interface + 1))

    out.append('*Step, name=IMPACT, nlgeom=NO')
    out.append('*Dynamic, Explicit')
    out.append(', %.6g' % (options.impact_us * 1e-6))
    out.append('*Bulk Viscosity')
    out.append('0.06, 1.2')
    out.append('*Boundary')
    out.append('FRAME, ENCASTRE')
    out.append('*Output, field, number interval=%d' % options.field_frames)
    out.append('*Node Output')
    out.append('U, V')
    out.append('*Element Output')
    out.append('S, SDEG')
    out.append('*Contact Output')
    out.append('** CSDMG is the interface damage variable for contact-based cohesive')
    out.append('** behaviour; it is to the surface what SDEG is to a cohesive element, and')
    out.append('** it is the variable the interface damage area is read from.')
    out.append('CSTRESS, CDISP, CSDMG')
    out.append('*Output, history, time interval=%.6g' % (options.history_interval))
    out.append('*Node Output, nset=BALLREF')
    out.append('V3')
    out.append('*Node Output, nset=TOPCENTRE')
    out.append('U3')
    out.append('*Energy Output')
    out.append('ALLKE, ALLIE, ALLSE, ALLAE, ALLDMD, ALLPD, ALLWK, ETOTAL')
    out.append('*End Step')

    return '\n'.join(out) + '\n', dict(mesh=mesh, ball_mass=ball_mass, speed=speed,
                                       energy=energy, ref_node=ref_node,
                                       n_nodes=len(nodes) + len(ball_nodes) + 1,
                                       n_ball_nodes=len(ball_nodes) + 1,
                                       n_ply=n_ply_elements, n_ball=n_ball, n_extra=2,
                                       n_interfaces=nz - 1, dz=dt)


def _wrap(ids, per_line=16):
    lines = []
    for start in range(0, len(ids), per_line):
        lines.append(', '.join(str(v) for v in ids[start:start + per_line]) + ',')
    return '\n'.join(lines)


def self_check(text, info):
    """Consistency check, parsed by keyword context.

    Line shape alone is not enough to tell a node from a data row: an *Elastic line has
    eight numbers like an element connectivity, and an *Initial Conditions line has a
    label and three numbers like a node. Tracking which keyword is open is the difference
    between a check that can be trusted and one that raises false alarms.
    """
    problems = []
    defined = set()
    elements = []
    rigid_nodes = set()
    keyword = None
    keyword_line = ''
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('**'):
            continue
        if line.startswith('*'):
            keyword_line = line.lower()
            keyword = line.split(',')[0].strip().lower()
            continue
        parts = [p.strip() for p in line.split(',')]
        if keyword == '*node':
            if len(parts) != 4 or not all(_is_number(p) for p in parts):
                problems.append('malformed node line: %s' % line[:60])
                continue
            label = int(parts[0])
            if label in defined:
                problems.append('node %d is defined twice' % label)
            defined.add(label)
        elif keyword == '*element':
            elements.append((keyword_line, line))
            if 'type=r3d' in keyword_line.replace(' ', ''):
                for value in parts[1:]:
                    if _is_number(value):
                        rigid_nodes.add(int(value))
        elif keyword == '*initial conditions':
            # Three fields, and the third one is the value. Extra fields are ignored
            # rather than rejected, so a four-field line runs happily with the wrong
            # velocity; see the note in emit().
            if len(parts) != 3:
                problems.append('*Initial Conditions line has %d fields, expected 3: %s'
                                % (len(parts), line[:60]))
            elif not _is_number(parts[1]) or not _is_number(parts[2]):
                problems.append('malformed *Initial Conditions line: %s' % line[:60])

    for keyword_line, line in elements:
        parts = [p.strip() for p in line.split(',')]
        if not parts or not _is_number(parts[0]):
            problems.append('malformed element line: %s' % line[:60])
            continue
        for value in parts[1:]:
            if not _is_number(value) or int(value) not in defined:
                problems.append('element %s refers to undefined node %s'
                                % (parts[0], value))
                break
            # A deformable node that turns up in a rigid facet is pulled into the rigid
            # body while any boundary condition on it stays: the packager only warns, so
            # the model runs with a corner of the plate clamped and rigid at once.
            if 'type=c3d' in keyword_line.replace(' ', '') and int(value) in rigid_nodes:
                problems.append('node %s is shared between a solid element and a rigid '
                                'facet' % value)
                break

    n_defined = len(defined)
    if n_defined != info['n_nodes']:
        problems.append('defined %d nodes, expected %d' % (n_defined, info['n_nodes']))
    n_elements = len(elements)
    expected = info['n_ply'] + info['n_ball'] + info['n_extra']
    if n_elements != expected:
        problems.append('defined %d elements, expected %d' % (n_elements, expected))
    return problems


def _is_number(text):
    try:
        float(text)
        return True
    except ValueError:
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--nx', type=int, default=80, help='in-plane elements along x')
    p.add_argument('--ny', type=int, default=80, help='in-plane elements along y')
    p.add_argument('--nz', type=int, default=8, help='elements through the thickness, '
                                                     'one per ply')
    p.add_argument('--lx', type=float, default=0.1, help='coupon length in m')
    p.add_argument('--ly', type=float, default=0.1, help='coupon width in m')
    p.add_argument('--thickness', type=float, default=2.0e-3, help='plate thickness in m')
    p.add_argument('--drop-mm', type=float, default=160.0, help='drop height in mm, only '
                                                                'used for the initial velocity')
    p.add_argument('--impact-us', type=float, default=300.0, help='impact step length in us')
    p.add_argument('--field-frames', type=int, default=50)
    p.add_argument('--history-interval', type=float, default=5e-7)
    p.add_argument('--out', type=Path, required=True)
    options = p.parse_args()

    text, info = emit(options)
    options.out.write_text(text, encoding='ascii')

    problems = self_check(text, info)
    print('coupon %.0f x %.0f x %.0f mm, in-plane %.3f mm, %d plies of %.3f mm'
          % (options.lx * 1e3, options.ly * 1e3, options.thickness * 1e3,
             options.lx / options.nx * 1e3, options.nz, info['dz'] * 1e3))
    print('nodes %d (incl. ball %d), solid %d, rigid facets %d, %d interfaces'
          % (info['n_nodes'], info['n_ball_nodes'], info['n_ply'], info['n_ball'],
             info['n_interfaces']))
    print('interfaces are contact pairs carrying cohesive behaviour, so there are no '
          'interface elements and no interface mass')
    print('ball %.4f g, drop %.1f mm -> v %.4f m/s, energy %.5f J'
          % (info['ball_mass'] * 1e3, options.drop_mm, info['speed'], info['energy']))
    print('plate mass %.4f g' % (options.lx * options.ly * options.thickness * RHO_PLY
                                 * 1e3))
    print('wrote %s (%.1f MB)' % (options.out, options.out.stat().st_size / 1e6))
    print('self check:', 'clean' if not problems else '; '.join(problems))
    return 0 if not problems else 1


if __name__ == '__main__':
    raise SystemExit(main())
