"""Generate Explicit restart steps without redefining cohesive contact or material.

Relaxation is a numerical preparation, not a measured inter-drop waiting time.
Alpha=20000/s is an engineering trial value; it is OFF during free impacts.
Keyword sources (Abaqus 2025 documentation; verified with local Abaqus 2026):
https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-damping.htm
https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-restart.htm
https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-field.htm
"""


def header(previous_step):
    # Explicit interval avoids the misleading "Restart frame is set 0" warning
    # emitted by the local 2026 solver when interval is omitted. All jobs save 1.
    return '*Heading\n** Repeat-drop state continuation\n*Restart, read, step=%d, interval=1, end step\n' % previous_step


def amplitude(name, points, smooth=False):
    return ('*Amplitude, name=%s, time=STEP TIME%s\n' %
            (name, ', definition=SMOOTH STEP' if smooth else '') +
            '\n'.join('%.12g, %.12g' % p for p in points) + '\n')


def output(frames, interval):
    return '''*Output, field, op=NEW, number interval=%d
*Node Output
U, V
*Element Output
S
*Contact Output
CSTRESS, CDISP, CSDMG
*Output, history, op=NEW, time interval=%.12g
*Node Output, nset=BALLREF
U3, V3
*Node Output, nset=TOPCENTRE
U3
*Energy Output
ALLKE, ALLIE, ALLSE, ALLAE, ALLDMD, ALLPD, ALLWK, ETOTAL, ALLVD, ALLFD, ALLCW, ALLPW
*Restart, write, number interval=1
*End Step
''' % (frames, interval)


def step(name, duration, damping_amplitude, bc, frames=10, interval=5e-7):
    return '''*Step, name=%s, nlgeom=NO
*Dynamic, Explicit
, %.12g
*Bulk Viscosity
0.06, 1.2
*Field, variable=1, amplitude=%s
PLATENODES, 1.
%s%s''' % (name, duration, damping_amplitude, bc, output(frames, interval))


def relaxation(previous_step, name, u_start, v_start, duration=500e-6, park=.003):
    # Match inherited velocity before catching: a zero-slope displacement ramp would
    # delete the rebound kinetic energy instantaneously at the step boundary.
    # Integrate a piecewise linear velocity profile to the requested parking height.
    travel_s = min(100e-6, duration)
    middle_v = 2*(park-u_start)/travel_s - .5*v_start
    if middle_v < -1e-6 or v_start < -1e-6:
        raise ValueError('recovery must move away from plate; increase parking height')
    text = header(previous_step)
    text += amplitude(name+'_DAMP', [(0., 1.), (duration, 1.)])
    text += amplitude(name+'_MOVE', [(0., v_start), (travel_s/2,middle_v), (travel_s,0.), (duration,0.)])
    bc = '*Boundary, op=NEW\nFRAME, ENCASTRE\n*Boundary, op=NEW, type=VELOCITY, amplitude=%s_MOVE\nBALLREF, 3, 3, 1.\n' % name
    return text + step(name, duration, name+'_DAMP', bc)


def preparation(previous_step, prefix, u_start, speed, clearance=100e-6,
                position_s=100e-6, launch_s=50e-6):
    # A linear velocity ramp has travel speed*T/2. The end has positive clearance,
    # so the next (unconstrained) step, not this launch actuator, generates contact.
    target = clearance + speed*launch_s/2
    text = header(previous_step)
    text += amplitude(prefix+'_ON', [(0., 1.), (1., 1.)])
    text += amplitude(prefix+'_OFF', [(0., 0.), (1., 0.)])
    text += amplitude(prefix+'_POS', [(0., u_start), (position_s, target)], True)
    text += amplitude(prefix+'_VEL', [(0., 0.), (launch_s, -speed)])
    bc = '*Boundary, op=NEW\nFRAME, ENCASTRE\n*Boundary, op=NEW, amplitude=%s_POS\nBALLREF, 3, 3, 1.\n' % prefix
    text += step(prefix+'_POSITION', position_s, prefix+'_ON', bc)
    bc = '*Boundary, op=NEW\nFRAME, ENCASTRE\n*Boundary, op=NEW, type=VELOCITY, amplitude=%s_VEL\nBALLREF, 3, 3, 1.\n' % prefix
    text += step(prefix+'_LAUNCH', launch_s, prefix+'_OFF', bc)
    return text


def impact(previous_step, name, duration=500e-6):
    text = header(previous_step) + amplitude(name+'_OFF', [(0., 0.), (duration, 0.)])
    # Removing the ball velocity boundary preserves its attained velocity.
    return text + step(name, duration, name+'_OFF', '*Boundary, op=NEW\nFRAME, ENCASTRE\n', frames=50)
