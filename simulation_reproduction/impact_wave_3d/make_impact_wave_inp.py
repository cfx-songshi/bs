"""Abaqus input for ball-drop impact damage followed by guided-wave interrogation.

This is the first stage of the chain the project is building: drop a ball on the plate,
let the impact leave damage, then interrogate that damage with guided waves. This file
covers the impact stage only; the wave step is added once the impact damages something.

What the model contains
-----------------------
* A rectangular coupon meshed with a structured grid. The in-plane spacing is stretched
  from a chosen size at the centre out to the far-field size, and that far-field size is
  set by the guided-wave requirement of ten elements per A0 wavelength at 100 kHz, which
  is the same rule the validated wave models use, so the two stages can share one mesh.
  The refinement is not decoration: at 1.25 mm the delaminated patch a low-energy impact
  leaves is about one element across, so the wave stage would be looking at a damage that
  its own mesh cannot represent.
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
* The refinement is finer in-plane only. Through the thickness there is still one element
  per ply, because the interfaces are the ply boundaries and splitting a ply would put an
  interface where the material does not have one. So the indentation itself is resolved by
  the in-plane grading alone. And how far the grading has to go is not settled by a
  convergence study here: the refinement is chosen from the contact radius, and the
  residual mesh dependence of the damage extent is reported rather than claimed away.
* The failure index of the general criterion is requested as a diagnostic only. It tells
  where the plies would fail first; it does not degrade anything.

Run:  python make_impact_wave_inp.py --out <path.inp>

The wave stage
--------------
The two stages are separate analyses on the same mesh, not two steps of one run, and the
reason is measured rather than assumed. At the end of the 0.3 J impact the plate is still
ringing with about 0.13 J of mechanical energy: the impact point is 274 um out of position
and still moving, and the plate's nodal velocities have a median of 0.93 m/s and a maximum
of 5.4 m/s (abaqus/runs/residual_probe.py). That is orders of magnitude above any guided
wave worth exciting. Its low-frequency part can be filtered out, but the high-frequency
flapping of the delaminated plies cannot, so a wave step bolted onto the impact step would
be measuring the ringing rather than the damage. Instead the impact model's job is to
produce the delamination footprint, and the wave model starts from the undamaged plate at
rest with that footprint applied as a disbond: the faces inside the patch keep friction and
lose the cohesive bond, so they can open and slide but still carry compression. That is the
kissing-bond idealisation the guided-wave literature uses, and it makes the repeated-drop
study a matter of growing the patch.

Sensors
-------
ACT (25, 50) mm is a 3 mm radius pressure patch on the top face: out of plane, five cycles
of a Hann windowed 100 kHz tone burst, so the excitation is mostly A0. The eight receivers
are read as out-of-plane displacement and velocity at the top face node and as strain in
the top ply element.

  R1 (65, 50)  15 mm past the damage on the direct path
  R2 (80, 50)  30 mm past the damage; with ACT this is the through-transmission pair
  R3 (50, 25)  broadside, 25 mm from the damage       R4 (50, 75)  mirror of R3
  R5 (75, 25)  forward scatter at 45 degrees          R6 (75, 75)  mirror of R5
  R7 (25, 25)  broadside at the actuator's station    R8 (25, 75)  mirror of R7

The layout follows from the plate rather than from an imaging requirement. A0 at 100 kHz
has a wavelength near 12.7 mm, which is what the far-field mesh is sized to, so the 80 mm
free region is only about six wavelengths across and the boundary reflections arrive early:
a short, separable direct path is worth more than a wide array here. R3/R4, R5/R6 and R7/R8
are mirror pairs about y = 50 mm, and the actuator sits on that plane, so on an undamaged
plate each pair must read identically. That is a free check on the whole wave setup, and
this project has caught real bugs with exactly this kind of check before.

Run the wave stage in double precision: `abaqus job=... double=explicit`. Single precision
is not good enough here and the mirror pairs are what shows it. The plate is 0.1 m across
and the wave moves it by 1e-7 m, so single precision keeps about five significant digits
on the thing being measured, and the mirror asymmetry came out at 12 per cent of the field.
In double precision the same check comes out at 0.00 to 0.88 per cent, the residue sitting
at the disbond edge where the crack faces open and stick and the response is genuinely not
symmetric. Twelve per cent of noise is the same size as the damage signal, so a single
precision wave run would have measured round-off. The impact stage has no such problem:
there the displacements are 1e-4 m and single precision is fine.
"""
import argparse
import json
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
# Substitute values from a published CFRP cohesive-property set, not measurements of this
# specimen: Zhu Guohua et al., "Multi-scale modeling and crashworthiness analysis of CFRP
# thin-walled structures", Acta Materiae Compositae Sinica 40(6) 3626-3639 (2023),
# DOI 10.13801/j.cnki.fhclxb.20220720.002, whose cohesive table gives an initiation stress
# of 59.5 MPa, G_nC = 490 J/m2, G_sC = G_tC = 1060 J/m2 and a B-K exponent of 2.284.
# The source gives one initiation stress, so the same value is used for all three
# directions rather than inventing a normal-shear split. The previous values here, 30 MPa
# and 1000 J/m2 in all three modes, were placeholders with no source at all.
IFACE_STRENGTH = '59.5e6, 59.5e6, 59.5e6'
IFACE_ENERGY = '490.0, 1060.0, 1060.0'
IFACE_POWER = 2.284

BALL_RADIUS = 4.0e-3
BALL_RHO = 14800.0
BALL_N_LAT = 90
BALL_N_LON = 120
FRICTION = 0.3

# Wave stage. See the module docstring for why this layout.
SENSORS = (('ACT', 25.0e-3, 50.0e-3),
           ('R1', 65.0e-3, 50.0e-3), ('R2', 80.0e-3, 50.0e-3),
           ('R3', 50.0e-3, 25.0e-3), ('R4', 50.0e-3, 75.0e-3),
           ('R5', 75.0e-3, 25.0e-3), ('R6', 75.0e-3, 75.0e-3),
           ('R7', 25.0e-3, 25.0e-3), ('R8', 25.0e-3, 75.0e-3))
ACTUATOR = 'ACT'
ACTUATOR_RADIUS = 3.0e-3
WAVE_FREQUENCY = 100.0e3
WAVE_CYCLES = 5
WAVE_FORCE = 10.0           # total peak force of the patch, N
SAMPLES_PER_CYCLE = 20      # the excitation is a table, so it has to be sampled
WAVE_SAMPLE = 1.0 / (SAMPLES_PER_CYCLE * WAVE_FREQUENCY)


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


def graded_coordinates(count, length, centre_size, ratio):
    """Node coordinates along one axis, finest at the centre, far-field size at the edge.

    A wave model wants one element size everywhere, ten per A0 wavelength. An impact wants
    small elements where the ball touches, and that contact radius is a fraction of a
    millimetre. The two are reconciled by stretching the spacing smoothly from
    `centre_size` at the middle out to length/count, which is the far-field size the wave
    requirement sets, rather than by refining a patch and ringing it with a transition:
    the grid stays structured, so the element connectivity, the ply elsets and the
    interface surfaces are all unchanged and no hanging nodes appear.

    Neighbouring elements differ by `ratio`, so the grading is gentle. Whatever it does
    scatter is also largely harmless here, because the damage indicator is the difference
    between two runs on this same mesh, and a difference cancels the mesh's own response.
    """
    far = length / float(count)
    if centre_size is None or centre_size >= far:
        return [index * far for index in range(count + 1)]

    half = 0.5 * length
    sizes = []
    size = centre_size
    used = 0.0
    while size < far - 1e-15 and used + size < half:
        sizes.append(size)
        used += size
        size *= ratio
    # The rest of the half-length is filled with whole far-field elements, stretched by
    # whatever fraction is needed to land exactly on the boundary. Letting the last element
    # absorb the leftover instead would leave a sliver, and the stable increment is set by
    # the smallest element in the model.
    remaining = half - used
    whole = max(1, int(round(remaining / far)))
    sizes.extend([remaining / whole] * whole)

    coordinates = [half]
    offset = 0.0
    for size in sizes:
        offset += size
        coordinates.append(half + offset)
        coordinates.insert(0, half - offset)
    return coordinates


def build(nx, ny, nz, lx, ly, thickness, centre_size=None, ratio=1.1):
    """Nodes, elements and the sets the deck needs.

    Node planes: every ply boundary carries two coincident planes, the top of one ply and
    the bottom of the next, so there are two planes per ply. They are what makes the
    interface a pair of separate faces, which is what contact-based cohesive behaviour
    needs; the ply elements share nodes with their own plane only, so the stack is joined
    by the contact at the interface and by nothing else.

    nx and ny are the far-field element counts, which fix the far-field size; the actual
    counts come back in the result, because the grading needs more elements than that to
    reach the centre size.
    """
    dz = thickness / nz
    n_planes = 2 * nz
    x = graded_coordinates(nx, lx, centre_size, ratio)
    y = graded_coordinates(ny, ly, centre_size, ratio)
    nx, ny = len(x) - 1, len(y) - 1

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
                nodes.append((x[i], y[j], z))

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
                n_planes=n_planes, nx=nx, ny=ny, x=x, y=y,
                centre_size=x[len(x) // 2] - x[len(x) // 2 - 1],
                far_size=x[-1] - x[-2])


def emit(options):
    nx, ny, nz = options.nx, options.ny, options.nz
    lx, ly = options.lx, options.ly
    thickness = options.thickness
    mesh = build(nx, ny, nz, lx, ly, thickness,
                 centre_size=options.centre_size, ratio=options.grade_ratio)
    nx, ny = mesh['nx'], mesh['ny']
    nodes = mesh['nodes']
    dt = mesh['dz']

    import math
    ball_mass = BALL_RHO * 4.0 / 3.0 * math.pi * BALL_RADIUS ** 3
    drop_height = options.drop_mm * 1e-3
    speed = math.sqrt(2.0 * 9.80665 * drop_height)
    energy = 0.5 * ball_mass * speed ** 2
    # The wave stage is a separate analysis on the same mesh with no ball at all, because
    # it starts from the undamaged plate at rest with the disbond patch applied. See the
    # module docstring for why the two stages are not two steps of one run.
    wave_only = bool(options.wave_only)
    if wave_only:
        ball_nodes, ball_faces = [], []
        ref_node = None
    else:
        ball_nodes, ball_faces = sphere((lx / 2.0, ly / 2.0, thickness + BALL_RADIUS),
                                        BALL_RADIUS, BALL_N_LAT, BALL_N_LON)
        ref_node = len(nodes) + len(ball_nodes) + 1
    ball_node_offset = len(nodes)
    disbond_radius = options.disbond_radius or 0.0
    inplane_inner = {}
    if disbond_radius > 0.0:
        for value in options.disbond_interfaces.split(','):
            if value.strip():
                inplane_inner[int(value)] = []

    out = ['*Heading',
           '** %s on a %g x %g x %g mm coupon, %d plies, contact-based cohesive between'
           % ('Guided wave stage' if wave_only else 'Ball-drop impact', lx * 1e3, ly * 1e3,
              thickness * 1e3, nz),
           '** them, generated by make_impact_wave_inp.py.',
           '** In-plane %g mm at the edges: set by ten elements per A0 wavelength at'
           % (mesh['far_size'] * 1e3),
           '** 100 kHz, the rule the validated wave models use, so one mesh serves both',
           '** stages. In-plane %g mm at the centre, where the ball contacts.'
           % (mesh['centre_size'] * 1e3),
           '*Preprint, echo=NO, model=NO, history=NO, contact=NO',
           '*Node']
    for index, (x, y, z) in enumerate(nodes, start=1):
        out.append('%d, %.10g, %.10g, %.10g' % (index, x, y, z))
    if not wave_only:
        for index, (x, y, z) in enumerate(ball_nodes, start=ball_node_offset + 1):
            out.append('%d, %.10g, %.10g, %.10g' % (index, x, y, z))
        out.append('%d, %.10g, %.10g, %.10g' % (ref_node, lx / 2.0, ly / 2.0,
                                                thickness + BALL_RADIUS))

    out.append('** solid elements, one per ply')
    out.append('*Element, type=C3D8')
    for index, connectivity in enumerate(mesh['ply_elements'], start=1):
        out.append('%d, %s' % (index, ', '.join(str(n) for n in connectivity)))

    n_ply_elements = len(mesh['ply_elements'])
    n_ball = len(ball_faces)
    mass_element = n_ply_elements + n_ball + 1
    inertia_element = mass_element + 1
    if not wave_only:
        out.append('** rigid facets of the ball')
        out.append('*Element, type=R3D4')
        for index, connectivity in enumerate(ball_faces, start=1):
            if len(connectivity) == 3:
                continue
            out.append('%d, %s' % (n_ply_elements + index,
                                   ', '.join(str(ball_node_offset + 1 + n)
                                             for n in connectivity)))
        out.append('*Element, type=R3D3')
        for index, connectivity in enumerate(ball_faces, start=1):
            if len(connectivity) != 3:
                continue
            out.append('%d, %s' % (n_ply_elements + index,
                                   ', '.join(str(ball_node_offset + 1 + n)
                                             for n in connectivity)))
        # The ball's mass and inertia belong on its reference node, and *MASS takes an
        # element set, not a node set: asking for a node set gives "Unknown assembly set".
        # One-node MASS and ROTARYI elements carry the values.
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
    # The plate's impact face, named so that the contact domain can be assembled from
    # surfaces rather than from everything exterior. See *Contact Inclusions below.
    out.append('*Surface, type=ELEMENT, name=TOP')
    out.append('LAYER%d, S2' % nz)

    # A disbonded interface is split into an inner patch and the bonded area around it,
    # because the two need different interactions. The patch is a circle about the damage
    # centre sized from the impact model's dissipated energy, which is an equivalent-area
    # idealisation: the footprint the impact leaves is not a circle, and the handoff note
    # says so. Each layer of an interface uses the same in-plane element ordering, so one
    # list of in-plane numbers serves both the lower and the upper face.
    for interface in inplane_inner:
        inner = []
        for j in range(ny):
            dy = 0.5 * (mesh['y'][j] + mesh['y'][j + 1]) - ly / 2.0
            for i in range(nx):
                dx = 0.5 * (mesh['x'][i] + mesh['x'][i + 1]) - lx / 2.0
                if dx * dx + dy * dy <= disbond_radius ** 2:
                    inner.append(j * nx + i + 1)
        inplane_inner[interface] = inner
    for interface in range(nz - 1):
        number = interface + 1
        if number not in inplane_inner:
            out.append('*Surface, type=ELEMENT, name=IFACE%d_LOWER' % number)
            out.append('LAYER%d, S2' % (interface + 1))
            out.append('*Surface, type=ELEMENT, name=IFACE%d_UPPER' % number)
            out.append('LAYER%d, S1' % (interface + 2))
            continue
        inner = inplane_inner[number]
        inside = set(inner)
        outer = [index for index in range(1, per_ply + 1) if index not in inside]
        for suffix, indices in (('IN', inner), ('OUT', outer)):
            out.append('*Elset, elset=IFACE%d_%s_LOWER' % (number, suffix))
            out.append(_wrap([index + interface * per_ply for index in indices]))
            out.append('*Elset, elset=IFACE%d_%s_UPPER' % (number, suffix))
            out.append(_wrap([index + (interface + 1) * per_ply for index in indices]))
            out.append('*Surface, type=ELEMENT, name=IFACE%d_%s_LOWER' % (number, suffix))
            out.append('IFACE%d_%s_LOWER, S2' % (number, suffix))
            out.append('*Surface, type=ELEMENT, name=IFACE%d_%s_UPPER' % (number, suffix))
            out.append('IFACE%d_%s_UPPER, S1' % (number, suffix))
    if not wave_only:
        out.append('*Elset, elset=BALL, generate')
        out.append('%d, %d, 1' % (n_ply_elements + 1, n_ply_elements + n_ball))
        out.append('*Surface, type=ELEMENT, name=BALLFACETS')
        out.append('BALL')
        # R3D3 and R3D4 are rigid facets: they only become a rigid body, with this
        # reference node as its single point of control, through *RIGID BODY.
        out.append('*Rigid Body, ref node=%d, elset=BALL' % ref_node)

    # Sensors. The reading is the top face node's out-of-plane motion plus the strain in
    # the top ply element under it, which is what a surface bonded patch measures. The
    # receiver elements are the top ply elements whose lower left corner is nearest the
    # requested position, which is deterministic and good to half an element.
    top_plane = mesh['n_planes'] - 1
    top_ply = nz - 1
    sensor_nodes, sensor_elements = {}, {}
    for name, sx, sy in SENSORS:
        i = nearest_index(mesh['x'], sx)
        j = nearest_index(mesh['y'], sy)
        sensor_nodes[name] = mesh['nid'](i, j, top_plane)
        sensor_elements[name] = (top_ply * per_ply + min(j, ny - 1) * nx
                                 + min(i, nx - 1) + 1)
        out.append('*Nset, nset=SENSOR_%s' % name)
        out.append('%d,' % sensor_nodes[name])
        out.append('*Elset, elset=SENSOR_%s' % name)
        out.append('%d,' % sensor_elements[name])

    # Actuator: the top faces of the elements inside ACTUATOR_RADIUS of ACT. A pressure on
    # them is the mechanical idealisation of a bonded patch, and spreading it over the
    # patch rather than loading one node keeps the excitation mesh independent.
    patch, patch_area = [], 0.0
    for j in range(ny):
        dy = 0.5 * (mesh['y'][j] + mesh['y'][j + 1]) - SENSORS[0][2]
        for i in range(nx):
            dx = 0.5 * (mesh['x'][i] + mesh['x'][i + 1]) - SENSORS[0][1]
            if dx * dx + dy * dy <= ACTUATOR_RADIUS ** 2:
                patch.append(top_ply * per_ply + j * nx + i + 1)
                patch_area += (mesh['x'][i + 1] - mesh['x'][i]) * (mesh['y'][j + 1]
                                                                   - mesh['y'][j])
    out.append('*Elset, elset=PATCH')
    out.append(_wrap(patch))
    out.append('*Surface, type=ELEMENT, name=PATCH')
    out.append('PATCH, S2')

    # The clamped frame: everything within a border of the coupon edge is held, which is
    # the same idealisation the earlier impact route used. The width is measured in
    # far-field elements, because the edge spacing is the far-field size and not lx/nx.
    border = max(1, int(round(0.01 / mesh['far_size'])))
    clamped = []
    for plane in range(mesh['n_planes']):
        for j in range(ny + 1):
            for i in range(nx + 1):
                if i < border or j < border or i > nx - border or j > ny - border:
                    clamped.append(mesh['nid'](i, j, plane))
    out.append('*Nset, nset=FRAME')
    out.append(_wrap(clamped))
    if not wave_only:
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

    if not wave_only:
        out.append('*Mass, elset=BALLMASS')
        out.append('%.6e,' % ball_mass)
        out.append('** Rotational inertia of a solid sphere, 2/5 m r^2. A central impact')
        out.append('** does not spin the ball; the value is here so the rigid body is well')
        out.append('** posed.')
        out.append('*Rotary Inertia, elset=BALLINERTIA')
        out.append('%.6e, %.6e, %.6e' % (2.0 / 5.0 * ball_mass * BALL_RADIUS ** 2,
                                          2.0 / 5.0 * ball_mass * BALL_RADIUS ** 2,
                                          2.0 / 5.0 * ball_mass * BALL_RADIUS ** 2))
        out.append('*Initial Conditions, type=VELOCITY')
        # Three fields, not four. Written as "node, dof, magnitude". Adding a second dof
        # field in the hope of a "first dof, last dof" range, which is how *BOUNDARY reads
        # the same shape of line, makes Abaqus read the magnitude from the third field and
        # ignore the fourth: the ball was given 3 m/s, the dof number, whatever drop height
        # was asked for, with no warning in the .dat. Both a deformable node and a
        # rigid-body reference node in one test deck came out at the dof value, 1 for dof 1
        # and 3 for dof 3. The energy check in abaqus/read_odb_impact_summary.py is what
        # caught it, and the field count is now checked below so it cannot come back
        # silently.
        out.append('%d, 3, %.6e' % (ref_node, -speed))

    out.append('*Surface Interaction, name=FRIC')
    out.append('*Friction')
    out.append('%g,' % FRICTION)
    out.append('*Contact, op=NEW')
    if options.contact_scope == 'all':
        out.append('*Contact Inclusions, ALL EXTERIOR')
    else:
        # Everything exterior is the wrong domain for this model. The ply interfaces are
        # duplicated node planes, so at the plate's perimeter every interface leaves two
        # coincident edge strips facing each other, and the general contact search sees them
        # as touching. The search is directional, so those contacts are the only mechanism
        # in an otherwise symmetric elastic model that can break its symmetry, and the
        # mirror pair check showed the field going asymmetric by up to 48 per cent near the
        # clamped edge as the wave decayed. Naming the pairs the contact is actually meant
        # to carry removes all of it: the interfaces, and for the impact the ball on the
        # top face. A side effect is that the ball stops contacting its own facets.
        out.append('*Contact Inclusions')
        for interface in range(nz - 1):
            number = interface + 1
            if number in inplane_inner:
                out.append('IFACE%d_IN_LOWER, IFACE%d_IN_UPPER' % (number, number))
                out.append('IFACE%d_OUT_LOWER, IFACE%d_OUT_UPPER' % (number, number))
            else:
                out.append('IFACE%d_LOWER, IFACE%d_UPPER' % (number, number))
        if not wave_only:
            out.append('TOP, BALLFACETS')
    out.append('** The blanket friction assignment comes first and the interface pairs')
    out.append('** after it, because a later assignment takes precedence over an earlier')
    out.append('** one for the same pair.')
    out.append('*Contact Property Assignment')
    out.append(' ,  , FRIC')
    for interface in range(nz - 1):
        number = interface + 1
        if number not in inplane_inner:
            out.append('IFACE%d_UPPER, IFACE%d_LOWER, DELAM' % (number, number))
            continue
        # Bonded area keeps the cohesive law; the patch keeps friction only, so it can
        # open and slide but still carries compression. That is the disbond.
        out.append('IFACE%d_IN_UPPER, IFACE%d_IN_LOWER, FRIC' % (number, number))
        out.append('IFACE%d_OUT_UPPER, IFACE%d_OUT_LOWER, DELAM' % (number, number))

    # The excitation: five Hann windowed cycles at WAVE_FREQUENCY. It starts and ends at
    # zero, so there is no step change at either end of the burst and the only thing
    # launched is the pulse. *AMPLITUDE is model data, so it has to come before the first
    # step, and the time base is STEP TIME so it replays from the start of the wave step.
    burst = WAVE_CYCLES * SAMPLES_PER_CYCLE
    out.append('*Amplitude, name=BURST, time=STEP TIME')
    for index in range(burst + 1):
        window = 0.5 * (1.0 - math.cos(2.0 * math.pi * index / burst))
        out.append('%.7g, %.7g' % (index * WAVE_SAMPLE,
                                   window * math.sin(2.0 * math.pi * index
                                                     / SAMPLES_PER_CYCLE)))

    if not wave_only:
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
        out.append('** behaviour; it is to the surface what SDEG is to a cohesive element,')
        out.append('** and it is the variable the interface damage area is read from.')
        out.append('CSTRESS, CDISP, CSDMG')
        out.append('*Output, history, time interval=%.6g' % (options.history_interval))
        out.append('*Node Output, nset=BALLREF')
        out.append('V3')
        out.append('*Node Output, nset=TOPCENTRE')
        out.append('U3')
        out.append('*Energy Output')
        out.append('ALLKE, ALLIE, ALLSE, ALLAE, ALLDMD, ALLPD, ALLWK, ETOTAL')
        out.append('*End Step')
        # A deck is one stage or the other and never both, which is deliberate rather than
        # an omission: the impact leaves the plate holding about 0.13 J of ringing, and its
        # high frequency part cannot be filtered out where the delaminated plies are
        # flapping, so a wave step appended to the impact step would measure the ringing
        # rather than the damage.
        return '\n'.join(out) + '\n', dict(
            mesh=mesh, ball_mass=ball_mass, speed=speed, energy=energy, ref_node=ref_node,
            n_nodes=len(nodes) + len(ball_nodes) + 1,
            n_ball_nodes=len(ball_nodes) + 1, n_ply=n_ply_elements, n_ball=n_ball,
            n_extra=2, n_interfaces=nz - 1, dz=dt, wave_only=False,
            patch=len(patch), patch_area=patch_area, disbond_radius=disbond_radius,
            disbonded=sorted(inplane_inner),
            disbond_elements=sum(len(v) for v in inplane_inner.values()),
            sensors=sensor_nodes, sensor_elements=sensor_elements)

    out.append('*Step, name=WAVE, nlgeom=NO')
    out.append('*Dynamic, Explicit')
    out.append(', %.6g' % (options.wave_us * 1e-6))
    out.append('*Bulk Viscosity')
    out.append('0.06, 1.2')
    out.append('*Boundary')
    out.append('FRAME, ENCASTRE')
    out.append('*Dsload, op=NEW, amplitude=BURST')
    out.append('PATCH, P, %.6e' % (WAVE_FORCE / patch_area))
    out.append('*Output, field, number interval=%d' % options.wave_frames)
    out.append('*Node Output')
    out.append('U, V')
    out.append('*Output, history, time interval=%.6g' % options.history_interval)
    for name, _, _ in SENSORS:
        out.append('*Node Output, nset=SENSOR_%s' % name)
        out.append('U3, V3')
        out.append('*Element Output, elset=SENSOR_%s' % name)
        out.append('E11, E22, E12')
    out.append('*Energy Output')
    out.append('ALLKE, ALLIE, ALLSE, ALLAE, ALLDMD, ALLPD, ALLWK, ETOTAL')
    out.append('*End Step')

    return '\n'.join(out) + '\n', dict(mesh=mesh, ball_mass=ball_mass, speed=speed,
                                       energy=energy, ref_node=ref_node,
                                       n_nodes=len(nodes) + len(ball_nodes)
                                       + (0 if wave_only else 1),
                                       n_ball_nodes=0 if wave_only else len(ball_nodes) + 1,
                                       n_ply=n_ply_elements, n_ball=n_ball,
                                       n_extra=0 if wave_only else 2,
                                       n_interfaces=nz - 1, dz=dt, wave_only=wave_only,
                                       patch=len(patch), patch_area=patch_area,
                                       disbond_radius=disbond_radius,
                                       disbonded=sorted(inplane_inner),
                                       disbond_elements=sum(len(v) for v in
                                                            inplane_inner.values()),
                                       sensors=sensor_nodes,
                                       sensor_elements=sensor_elements)


def _wrap(ids, per_line=16):
    lines = []
    for start in range(0, len(ids), per_line):
        lines.append(', '.join(str(v) for v in ids[start:start + per_line]) + ',')
    return '\n'.join(lines)


def nearest_index(coordinates, target):
    """Index of the coordinate closest to target. Used to snap sensors onto nodes."""
    return min(range(len(coordinates)), key=lambda index: abs(coordinates[index] - target))


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
    p.add_argument('--nx', type=int, default=80, help='far-field in-plane elements along x')
    p.add_argument('--ny', type=int, default=80, help='far-field in-plane elements along y')
    p.add_argument('--nz', type=int, default=8, help='elements through the thickness, '
                                                     'one per ply')
    p.add_argument('--lx', type=float, default=0.1, help='coupon length in m')
    p.add_argument('--ly', type=float, default=0.1, help='coupon width in m')
    p.add_argument('--thickness', type=float, default=2.0e-3, help='plate thickness in m')
    p.add_argument('--centre-size', type=float, default=None,
                   help='in-plane element size at the centre of the coupon, in m; omit '
                        'for the uniform far-field mesh')
    p.add_argument('--grade-ratio', type=float, default=1.1,
                   help='size ratio between neighbouring in-plane elements when grading')
    p.add_argument('--drop-mm', type=float, default=160.0, help='drop height in mm, only '
                                                                'used for the initial velocity')
    p.add_argument('--impact-us', type=float, default=300.0, help='impact step length in us')
    p.add_argument('--wave-us', type=float, default=250.0, help='wave step length in us')
    p.add_argument('--wave-only', action='store_true',
                   help='emit the guided wave stage only: no ball, no impact step, the '
                        'plate starts from rest')
    p.add_argument('--disbond-radius', type=float, default=None,
                   help='radius in m of the disbonded patch on each interface named by '
                        '--disbond-interfaces; omit for a fully bonded model')
    p.add_argument('--disbond-interfaces', default='',
                   help='comma separated interface numbers to disbond, counting from the '
                        'bottom of the plate')
    p.add_argument('--contact-scope', choices=('all', 'interfaces'), default='all',
                   help='"all" takes every exterior face into the general contact domain, '
                        'which brings in the coincident edge strips the duplicated ply '
                        'interfaces leave at the plate perimeter; "interfaces" names only '
                        'the pairs the contact is meant to carry')
    p.add_argument('--field-frames', type=int, default=50)
    p.add_argument('--wave-frames', type=int, default=25)
    p.add_argument('--history-interval', type=float, default=5e-7)
    p.add_argument('--out', type=Path, required=True)
    options = p.parse_args()

    text, info = emit(options)
    options.out.write_text(text, encoding='ascii')

    # A sidecar, because the deck's node sets do not survive into the odb: Abaqus writes
    # only the sets it makes itself, so the reader has no way to tell which per-node
    # history region is which sensor. This is the handoff.
    sidecar = options.out.with_suffix('.sensors.json')
    sidecar.write_text(json.dumps(dict(
        sensors=dict((name, dict(node=info['sensors'][name],
                                 element=info['sensor_elements'][name]))
                     for name, _, _ in SENSORS),
        sensor_positions=dict((name, [x, y]) for name, x, y in SENSORS),
        title='%s x %s mm coupon' % (options.lx * 1e3, options.ly * 1e3),
        mesh=dict(nx=info['mesh']['nx'], ny=info['mesh']['ny'], nz=options.nz,
                  centre=info['mesh']['centre_size'], far=info['mesh']['far_size']),
        wave=dict(frequency=WAVE_FREQUENCY, cycles=WAVE_CYCLES, force=WAVE_FORCE,
                  patch_area=info['patch_area'], step_us=options.wave_us),
        disbond=dict(radius=info['disbond_radius'], interfaces=info['disbonded'],
                     elements=info['disbond_elements']),
        impact=None if info['wave_only'] else dict(drop_mm=options.drop_mm,
                                                   speed=info['speed'],
                                                   energy=info['energy']),
    ), indent=2, sort_keys=True), encoding='ascii')
    print('wrote %s' % sidecar)

    problems = self_check(text, info)
    mesh = info['mesh']
    print('coupon %.0f x %.0f x %.0f mm, %d plies of %.3f mm'
          % (options.lx * 1e3, options.ly * 1e3, options.thickness * 1e3,
             options.nz, info['dz'] * 1e3))
    print('mesh %d x %d in-plane per ply, %.3f mm at the edge, %.3f mm at the centre'
          % (mesh['nx'], mesh['ny'], mesh['far_size'] * 1e3, mesh['centre_size'] * 1e3))
    print('nodes %d (incl. ball %d), solid %d, rigid facets %d, %d interfaces'
          % (info['n_nodes'], info['n_ball_nodes'], info['n_ply'], info['n_ball'],
             info['n_interfaces']))
    print('interfaces are contact pairs carrying cohesive behaviour, so there are no '
          'interface elements and no interface mass')
    if info['wave_only']:
        print('wave stage only: no ball, no impact step, plate starts at rest')
    else:
        print('ball %.4f g, drop %.1f mm -> v %.4f m/s, energy %.5f J'
              % (info['ball_mass'] * 1e3, options.drop_mm, info['speed'], info['energy']))
    if info['disbonded']:
        print('disbond radius %.3f mm on interface(s) %s: %d elements per interface, '
              '%d in total' % (info['disbond_radius'] * 1e3,
                               ', '.join(str(v) for v in info['disbonded']),
                               info['disbond_elements'] // len(info['disbonded']),
                               info['disbond_elements']))
    else:
        print('no disbond: every interface is fully bonded')
    print('actuator patch %d elements, %.2f mm2, %.4g kPa at %.0f kHz, %d cycles'
          % (info['patch'], info['patch_area'] * 1e6,
             WAVE_FORCE / info['patch_area'] / 1e3, WAVE_FREQUENCY / 1e3, WAVE_CYCLES))
    print('sensors:', ', '.join('%s node %d element %d'
                                % (name, info['sensors'][name],
                                   info['sensor_elements'][name])
                                for name, _, _ in SENSORS))
    print('plate mass %.4f g' % (options.lx * options.ly * options.thickness * RHO_PLY
                                 * 1e3))
    print('wrote %s (%.1f MB)' % (options.out, options.out.stat().st_size / 1e6))
    print('self check:', 'clean' if not problems else '; '.join(problems))
    return 0 if not problems else 1


if __name__ == '__main__':
    raise SystemExit(main())
