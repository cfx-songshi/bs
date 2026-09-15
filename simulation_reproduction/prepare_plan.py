"""Generate a paper-traceable simulation specification and 1,620 impact cases.
This DOES NOT invoke Abaqus or assert that these finite-element cases were solved.
"""
import argparse,json,hashlib,itertools,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--vendor');p.add_argument('--papers',required=True);a=p.parse_args()
if a.vendor:sys.path.insert(0,a.vendor)
import numpy as np
root=Path(__file__).resolve().parent;out=root/'results';out.mkdir(exist_ok=True)
def save(name,x):
    (out/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
inventory=[]
for file in Path(a.papers).glob('*.pdf'):
    inventory.append({'file':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                      'role':'proposal' if file.name.startswith('硕士') else 'primary_research'})
save('source_inventory.json',inventory)
spec={
 'status':'NOT_SOLVED_FE_SPECIFICATION',
 'source':'SMS论文01.pdf, PDF pages 15-18, Tables 2-4 and Figures 18-21',
 'units':'SI: m, kg, s, Pa, N',
 'geometry':{'panel_length':.4,'panel_width':.4,'skin_thickness_each':.0005,'core_height':.014,
             'hex_circumcircle_diameter':.008,'wall_thickness':.00004,'adhesive_film':.00015},
 'material_panel':{'rho':2780,'E':73e9,'nu':.33,'JC_A':325e6,'JC_B':684e6,'JC_C':.0083,'JC_n':.73,'JC_m_reported':0,'reference_strain_rate':1},
 'material_sphere_tungsten':{'rho':14800,'E':530e9,'nu':.24},
 'material_sensor_elastic_only':{'rho':7600,'E':10e9,'nu':.36},
 'elements':'S4R for skins and honeycomb; sphere element details not specified in extracted text',
 'mesh_skin_reference_m':.002,'mesh_convergence_m':[.006,.005,.004,.003,.002,.001],
 'boundary':'all DOFs of panel perimeter fixed; sphere allowed to move only normal to skin',
 'interfaces':'Tie skin to core, as in paper; no cohesive delamination in this baseline',
 'history_dt_s':5e-6,'duration_s':5e-4,
 'sensor_coordinates_from_lower_left_m':[[x,y] for y in [.05,.15,.25,.35] for x in [.05,.15,.25,.35]],
 'coordinate_note':'Original Fig.18 origin is sensor 1 and y points down. Here panel lower-left is origin, y points up; record mapping before comparing measured coordinates.',
 'must_resolve_before_FE':['Adhesive films add 0.3 mm to nominal 15 mm stack if modeled explicitly; original shell/Tie baseline omits separate glue geometry.',
    'Text calls material both 2024-T3 and pure aluminium; use Table 3 values and document this inconsistency.',
    'Do not blindly evaluate 1-(T*)^m with m=0: document disabled thermal-softening convention and solver implementation.',
    'Need shell offsets, core wall mesh, contact friction/penalty, hourglass control, sensor diameter/thickness/patch coupling.',
    'Explicit stable time increment is NOT the 5 us history output interval.',
    'Check kinetic/internal/hourglass energy balance, contact penetration, sensor strain waveform and time-step/mesh independence.',
    'PZT elastic strain output is not a measured voltage without a piezoelectric/charge-amplifier transfer function.']}
save('abaqus_reference_spec.json',spec)
rng=np.random.default_rng(20260914);locations=[]
for row in range(3):
 for col in range(3):
  for repeat in range(10):
   while True:
    xy=np.array([.05+.1*col,.05+.1*row])+rng.uniform(.002,.098,2)
    if all(np.linalg.norm(xy-np.array(q['xy_m']))>=.01 for q in locations):break
   locations.append({'location_id':len(locations),'region':row*3+col+1,'xy_m':xy.tolist()})
cases=[]
for point in locations:
 for material,diameter,height in itertools.product(['aluminium','tungsten_steel'],[.006,.008,.010],[.16,.25,.36]):
  density=2780 if material=='aluminium' else 14800
  mass=density*4*np.pi*(diameter/2)**3/3
  cases.append({'case_id':f'HSP_{len(cases):04d}',**point,'sphere_material':material,'diameter_m':diameter,
                'height_m':height,'initial_speed_m_s':float(np.sqrt(2*9.81*height)),
                'mass_kg':float(mass),'impact_energy_J':float(mass*9.81*height),
                'aluminium_sphere_density_is_assumed_from_panel_table':material=='aluminium','status':'planned_not_solved'})
assert len(cases)==1620
save('hsp_1620_planned_cases.json',cases)
save('data_schema.json',{
 'event_id':'unique original physical/simulated event; all its channels and augmentations stay in one split',
 'specimen_id':'physical coupon or FE geometry realization',
 'domain_id':'structure/material/layup/condition and simulation-vs-real provenance',
 'source_kind':'real_measurement | elastic_wave_surrogate | equivalent_plate | explicit_FE',
 'input':'waveform [event,channel,time], fs_hz, sensor_xyz_m, time_origin_s',
 'label':'task-specific: AE onset_s; impact_xy_m; impact_force_N; damage_type; damage_extent',
 'structure_attributes':'dimensions, layup, elastic tensor, density, boundaries, glue and sensor coupling',
 'nuisance_attributes':'temperature, noise PSD, channel gain, sensor debonding, dropouts',
 'quality':'saturation, missing channel, operator error, solver non-convergence',
 'split':'source_train, source_validation, target_adapt, target_test; split by specimen/event BEFORE augmentation',
 'K0':'held-out target structure: no target fitting, normalization, domain alignment, early stopping, or hyperparameter selection',
 'Kshot':'K labels per class; keep a separate unlabeled target adaptation pool if used; never silently reuse target_test'})
print('Wrote inventory, FE specification, 1620 planned cases and data schema.')
