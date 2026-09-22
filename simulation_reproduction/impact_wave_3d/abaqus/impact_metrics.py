"""Structured ODB readback shared by the impact reader and repeat-drop controller.

Energy-derived area is a summed-interface, full-fracture-equivalent proxy, not a
geometrical footprint. Nodal tributary areas below are separate thresholded estimates.
"""
import json
import math
from pathlib import Path

from odbAccess import openOdb


ENERGIES = ('ALLKE', 'ALLIE', 'ALLSE', 'ALLAE', 'ALLDMD', 'ALLPD', 'ALLWK',
            'ETOTAL', 'ALLVD', 'ALLFD', 'ALLCW', 'ALLPW')


def scalar_map(frame, prefix):
    result = {}
    for name, field in frame.fieldOutputs.items():
        if name.startswith(prefix):
            for value in field.values:
                key = (value.instance.name, value.nodeLabel)
                result[key] = max(result.get(key, 0.), float(value.data))
    return result


def node_history(step, label, name):
    found = []
    for region in step.historyRegions.values():
        if name not in region.historyOutputs:
            continue
        point = region.point
        try:
            matches = point.node.label == label
        except (AttributeError, TypeError):
            matches = region.name.endswith('.%d' % label)
        if matches:
            found.append(region.historyOutputs[name].data)
    if len(found) != 1:
        raise RuntimeError('expected one %s history for node %s, found %s' % (name, label, len(found)))
    return found[0]


def read(path, step_name, ball_mass, ball_label, top_label, expected_s=None,
         gc=(490., 1060.), nominal_energy=.3, centre=(.05, .05), thickness=.002):
    odb = openOdb(str(path), readOnly=True)
    try:
        if step_name is None:
            names = list(odb.steps.keys())
            if len(names) != 1:
                raise RuntimeError('multiple steps: explicitly select --step; available: ' + ', '.join(names))
            step_name = names[0]
        step = odb.steps[step_name]
        if not step.frames:
            raise RuntimeError('no frames in ' + step_name)
        first, last = step.frames[0], step.frames[-1]
        if expected_s is not None and abs(last.frameValue - expected_s) > max(1e-10, expected_s * 1e-5):
            raise RuntimeError('incomplete step: %g vs requested %g' % (last.frameValue, expected_s))
        series = {}
        for region in step.historyRegions.values():
            for name, output in region.historyOutputs.items():
                if name in ENERGIES:
                    if name in series:
                        raise RuntimeError('ambiguous energy history: ' + name)
                    series[name] = list(output.data)
        for required in ('ALLDMD', 'ALLKE', 'ALLSE', 'ETOTAL', 'ALLAE'):
            if required not in series:
                raise RuntimeError('missing mandatory energy: ' + required)
        for name, values in series.items():
            if not values or not all(math.isfinite(t) and math.isfinite(v) for t, v in values):
                raise RuntimeError('invalid energy history: ' + name)
            if abs(values[-1][0] - last.frameValue) > 1e-9:
                raise RuntimeError('energy history did not reach last frame: ' + name)
        energy = {k: dict(first_J=v[0][1], last_J=v[-1][1], delta_J=v[-1][1]-v[0][1],
                          peak_abs_J=max(abs(x[1]) for x in v)) for k, v in series.items()}
        damage0, damage1 = scalar_map(first, 'CSDMG'), scalar_map(last, 'CSDMG')
        if not damage1:
            raise RuntimeError('missing CSDMG: cohesive contact may be inactive')
        coords = {(inst.name, n.label): tuple(n.coordinates)
                  for inst in odb.rootAssembly.instances.values() for n in inst.nodes}
        # The ball's lowest node initially lies exactly on z=thickness. Selecting
        # the plate by z alone silently includes that rigid node in rest checks.
        plate_keys = {(inst.name, label) for inst in odb.rootAssembly.instances.values()
                      for element in inst.elements if element.type.startswith('C3D')
                      for label in element.connectivity}
        # Merge coincident sides of one interface; never count both surfaces twice.
        by_xyz = {}
        for key, value in damage1.items():
            xyz = tuple(round(x, 10) for x in coords[key])
            by_xyz[xyz] = max(by_xyz.get(xyz, 0.), value)
        plate_coords = [coords[k] for k in plate_keys]
        xs = sorted(set(round(x[0], 10) for x in plate_coords))
        ys = sorted(set(round(x[1], 10) for x in plate_coords))
        def weights(axis):
            return {x: ((axis[i+1] if i+1 < len(axis) else x) -
                        (axis[i-1] if i else x)) / 2 for i, x in enumerate(axis)}
        wx, wy = weights(xs), weights(ys)
        interfaces = {}
        for (x, y, z), value in by_xyz.items():
            if z <= 1e-8 or z >= thickness - 1e-8:
                continue
            r = interfaces.setdefault('%.6f' % (z*1e3), dict(height_mm=z*1e3,
                max_CSDMG=0., damaged_nodes=0, area_D_gt_0p01_mm2=0.,
                area_D_ge_0p95_mm2=0., damage_weighted_area_mm2=0., max_damage_radius_mm=0.))
            area = wx[x]*wy[y]*1e6
            r['max_CSDMG'] = max(r['max_CSDMG'], value)
            r['damage_weighted_area_mm2'] += area*value
            if value > .01:
                r['area_D_gt_0p01_mm2'] += area
                r['max_damage_radius_mm'] = max(r['max_damage_radius_mm'], math.hypot(x-centre[0], y-centre[1])*1e3)
            if value >= .95:
                r['area_D_ge_0p95_mm2'] += area
            if value > 1e-6:
                r['damaged_nodes'] += 1
        damage_J = energy['ALLDMD']['last_J']
        if damage_J < -1e-12:
            raise RuntimeError('negative damage dissipation')
        areas = [max(0., damage_J)/g*1e6 for g in sorted(gc, reverse=True)]
        vb = node_history(step, ball_label, 'V3')
        ub = node_history(step, ball_label, 'U3')
        ut = node_history(step, top_label, 'U3')
        forces = [(vb[i][0], ball_mass*(vb[i+2][1]-vb[i-2][1])/(vb[i+2][0]-vb[i-2][0]))
                  for i in range(2, len(vb)-2)]
        peak_force = max(forces, key=lambda v: abs(v[1])) if forces else (0., 0.)
        plate_speeds = []
        top_disps = []
        if 'V' not in last.fieldOutputs or 'U' not in last.fieldOutputs:
            raise RuntimeError('missing U/V fields')
        for value in last.fieldOutputs['V'].values:
            xyz = coords[(value.instance.name, value.nodeLabel)]
            if (value.instance.name, value.nodeLabel) in plate_keys:
                plate_speeds.append(math.sqrt(sum(float(x)**2 for x in value.data)))
        for value in last.fieldOutputs['U'].values:
            x,y,z = coords[(value.instance.name, value.nodeLabel)]
            if ((value.instance.name, value.nodeLabel) in plate_keys and
                    abs(z-thickness) < 1e-8 and math.hypot(x-centre[0], y-centre[1]) < .0045):
                top_disps.append(float(value.data[2]))
        if not plate_speeds or not top_disps:
            raise RuntimeError('plate node selection is empty')
        # Histories share requested sample times; fail on unexpected misalignment.
        ke, se = series['ALLKE'], series['ALLSE']
        if len(ke) != len(se) or len(ke) != len(vb) or any(abs(a[0]-b[0])>1e-10 for a,b in zip(ke,vb)):
            raise RuntimeError('energy and ball histories are not aligned')
        residual = [(a[0], max(0., a[1]-.5*ball_mass*v[1]**2)+s[1]) for a,s,v in zip(ke,se,vb)]
        tail = [e for t,e in residual if t >= last.frameValue-50e-6-1e-12]
        report = dict(odb=str(Path(path).resolve()), step=step_name, step_number=step.number,
            end_s=last.frameValue, frames=len(step.frames), energy=energy,
            energy_equivalent_area_mm2=areas,
            energy_equivalent_radius_mm=[math.sqrt(a/math.pi) for a in areas],
            energy_radius_caveat='summed-interface full-fracture-equivalent proxy, not per-interface geometric radius; partial damage contributes',
            interfaces=[interfaces[z] for z in sorted(interfaces)],
            damage_start={('%s:%s'%k):v for k,v in damage0.items() if v>1e-8},
            damage_end={('%s:%s'%k):v for k,v in damage1.items() if v>1e-8},
            ball=dict(node=ball_label, u3_last_m=ub[-1][1], v3_first_m_s=vb[0][1], v3_last_m_s=vb[-1][1],
                      rebound_ratio=-vb[-1][1]/vb[0][1] if vb[0][1] else None,
                      force_peak_N=peak_force[1], force_peak_time_s=peak_force[0],
                      force_tail_max_N=max([abs(f) for t,f in forces if t>last.frameValue-20e-6] or [0.])),
            centre=dict(node=top_label,u3_last_m=ut[-1][1],peak_downward_um=-min(v for _,v in ut)*1e6),
            residual=dict(plate_mechanical_tail_max_J=max(tail), plate_max_speed_m_s=max(plate_speeds),
                          local_top_max_u3_m=max(top_disps), conservative_ball_gap_m=ub[-1][1]-max(top_disps)),
            etotal_delta_over_incident=energy['ETOTAL']['delta_J']/nominal_energy)
        return report
    finally:
        odb.close()


def write_report(report, path):
    Path(path).write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False), encoding='utf-8')
