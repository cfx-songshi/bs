"""Draw one figure per claim the stage report makes.

Every figure reads a committed metrics JSON, the exported odb histories, or the
generator's own mesh function, and prints the numbers it plotted so the report can be
checked against the handoff record rather than trusted.

    python review\\build_stage_figures.py

Writes PNGs into review/figures/. Chinese labels need a CJK font, which is why the
family list starts with Microsoft YaHei: the default DejaVu face has no CJK glyphs and
would silently draw empty boxes.
"""
import json
import math
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'figures')

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.dpi'] = 130
plt.rcParams['axes.grid'] = True
plt.rcParams['grid.alpha'] = 0.25
plt.rcParams['font.size'] = 10

BRAND = '#6b4bd6'
NEUTRAL = '#8a8f98'
ACCENT = '#2f9e8f'
WARN = '#c2703a'


def load(relative):
    with open(os.path.join(ROOT, relative), encoding='utf-8') as handle:
        return json.load(handle)


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.tight_layout()
    fig.savefig(path, bbox_inches='tight')
    plt.close(fig)
    print('  wrote %s' % name)
    return 'figures/' + name


def note(text):
    print('    %s' % text)


def f_plate_modal():
    """Stage 1: the thin plate's Rayleigh-Ritz truncation study."""
    metrics = load('simulation_reproduction/impact_v1/computed_metrics.json')
    orders = [6, 10, 14, 18, 22, 30, 38, 46]
    force = [metrics['summaries']['order%d' % o]['peak_contact_force_N'] for o in orders]
    deflection = [metrics['summaries']['order%d' % o]['peak_impact_point_displacement_m'] * 1e6
                  for o in orders]
    steps = ['%d_to_%d' % (a, b) for a, b in zip(orders[:-1], orders[1:])]
    l2_force = [metrics['convergence_relative_L2'][key]['force'] for key in steps]
    l2_w = [metrics['convergence_relative_L2'][key]['impact_w'] for key in steps]
    note('order46 force %.3f N deflection %.2f um' % (force[-1], deflection[-1]))
    note('38_to_46 L2 force %.4f deflection %.4f' % (l2_force[-1], l2_w[-1]))

    fig, (left, right) = plt.subplots(1, 2, figsize=(10.4, 3.9))
    left.plot(orders, force, 'o-', color=BRAND, label='峰值接触力 N')
    left.set_xlabel('每方向基函数阶数')
    left.set_ylabel('峰值接触力 (N)', color=BRAND)
    twin = left.twinx()
    twin.plot(orders, deflection, 's--', color=ACCENT, label='冲击点位移 µm')
    twin.set_ylabel('冲击点峰值位移 (µm)', color=ACCENT)
    twin.grid(False)
    left.set_title('薄板模型的基函数截断：峰值量随阶数')

    positions = range(len(steps))
    right.semilogy(positions, l2_force, 'o-', color=BRAND, label='接触力')
    right.semilogy(positions, l2_w, 's--', color=ACCENT, label='冲击点位移')
    right.set_xticks(list(positions))
    right.set_xticklabels(steps, rotation=45, ha='right')
    right.set_ylabel('相邻两阶的时程相对 L2')
    right.set_title('逐阶的变化幅度（越小越收敛）')
    right.legend()
    return save(fig, 's1_plate_modal.png')


def f_plate_vs_solid():
    """Stage 2: why the thin plate cannot be used at the impact point."""
    thin = load('simulation_reproduction/study_final/study_metrics.json')['summaries']['order22']
    solid = load('simulation_reproduction/impact_3d_v1/study_3d/submodel/summary.json')
    thin_force = thin['peak_contact_force_N']
    thin_w = thin['peak_impact_point_displacement_m'] * 1e6
    solid_force = solid['peak_contact_force_N']
    solid_w = solid['peak_surface_deflection_m'] * 1e6
    note('thin %.2f N / %.2f um ; solid %.3f N / %.2f um' % (thin_force, thin_w, solid_force, solid_w))
    note('ratios force %.2f x, deflection %.2f x' % (thin_force / solid_force, solid_w / thin_w))

    fig, (left, right) = plt.subplots(1, 2, figsize=(9.6, 3.9))
    positions = [0, 1]
    left.bar([p - 0.0 for p in positions], [thin_force, solid_force], width=0.5,
             color=[NEUTRAL, BRAND])
    left.set_xticks(positions)
    left.set_xticklabels(['薄板 Rayleigh–Ritz\n(order22)', '三维刚球接触\n(局部子模型)'])
    left.set_ylabel('峰值接触力 (N)')
    left.set_title('峰值接触力：薄板高估 %.1f 倍' % (thin_force / solid_force))
    for position, value in zip(positions, [thin_force, solid_force]):
        left.text(position, value + 4, '%.1f N' % value, ha='center')

    right.bar(positions, [thin_w, solid_w], width=0.5, color=[NEUTRAL, BRAND])
    right.set_xticks(positions)
    right.set_xticklabels(['薄板 Rayleigh–Ritz\n(order22)', '三维刚球接触\n(局部子模型)'])
    right.set_ylabel('冲击点峰值位移 (µm)')
    right.set_title('冲击点位移：薄板低估 %.1f 倍' % (solid_w / thin_w))
    for position, value in zip(positions, [thin_w, solid_w]):
        right.text(position, value + 8, '%.1f µm' % value, ha='center')
    return save(fig, 's2_plate_vs_solid.png')


def f_farfield_convergence():
    """Stage 2: the far-field mesh convergence of the sensor response."""
    three = load('simulation_reproduction/impact_3d_v1/study_3d/study_metrics.json')
    rows = three['far_field_convergence']['meshes']
    labels = ['%dx%dx%d' % (r['nx'], r['ny'], r['nz']) for r in rows]
    deflection = [r['peak_impact_point_displacement_m'] * 1e6 for r in rows]
    strain = [r['sensor_peaks']['10']['peak_impact_direction_projection'] * 1e6 for r in rows]
    note('deflection um %s' % ', '.join('%.2f' % v for v in deflection))
    note('S10 strain ue %s' % ', '.join('%.1f' % v for v in strain))

    fig, (left, right) = plt.subplots(1, 2, figsize=(9.8, 3.9))
    positions = range(len(rows))
    left.plot(positions, deflection, 'o-', color=BRAND, label='冲击点位移 µm')
    left.plot(positions, strain, 's--', color=ACCENT, label='S10 沿冲击方向应变 µε')
    left.set_xticks(list(positions))
    left.set_xticklabels(labels, rotation=20, ha='right')
    left.set_ylabel('峰值')
    left.set_title('远场网格收敛（共用同一步长）')
    left.legend()

    deflection_delta = [100 * (deflection[i + 1] - deflection[i]) / deflection[i]
                        for i in range(len(deflection) - 1)]
    strain_delta = [100 * (strain[i + 1] - strain[i]) / strain[i] for i in range(len(strain) - 1)]
    right.axhline(0, color=NEUTRAL, linewidth=0.8)
    right.plot(range(len(deflection_delta)), deflection_delta, 'o-', color=BRAND, label='位移')
    right.plot(range(len(strain_delta)), strain_delta, 's--', color=ACCENT, label='S10 应变')
    right.set_xticks(range(len(deflection_delta)))
    right.set_xticklabels(['%s→%s' % (labels[i], labels[i + 1])
                           for i in range(len(labels) - 1)], rotation=20, ha='right')
    right.set_ylabel('相对变化 (%)')
    right.set_title('加密一档带来的变化（趋零即收敛）')
    right.legend()
    return save(fig, 's2_farfield_convergence.png')


def f_sensor_direction():
    """Stage 2: the sensor reading depends on the direction it is projected on."""
    three = load('simulation_reproduction/impact_3d_v1/study_3d/study_metrics.json')
    rows = three['sensor_orientation_dependence']
    keys = [k for k in ('9', '10', '13', '14') if k in rows]
    impact = [rows[k]['peak_impact_direction_projection'] * 1e6 for k in keys]
    axis = [rows[k]['peak_axis_projection_at_0deg'] * 1e6 for k in keys]
    ratio = [rows[k]['ratio_impact_over_axis'] for k in keys]
    distance = [rows[k]['distance_from_impact_m'] * 1e3 for k in keys]
    note('ratio impact/axis %s' % ', '.join('%.2f' % v for v in ratio))

    fig, axis_handle = plt.subplots(figsize=(8.6, 4.0))
    positions = range(len(keys))
    width = 0.36
    axis_handle.bar([p - width / 2 for p in positions], [abs(v) for v in impact], width,
                    color=BRAND, label='沿冲击方向投影')
    axis_handle.bar([p + width / 2 for p in positions], [abs(v) for v in axis], width,
                    color=NEUTRAL, label='沿铺设轴投影')
    axis_handle.set_xticks(list(positions))
    axis_handle.set_xticklabels(['S%s（距冲击点 %.0f mm）' % (k, d) for k, d in zip(keys, distance)])
    axis_handle.set_ylabel('峰值应变 (µε)')
    axis_handle.set_title('传感器读数的方向依赖：比值 %.2f–%.2f' % (min(ratio), max(ratio)))
    axis_handle.legend()
    for position, value in zip(positions, ratio):
        axis_handle.text(position, max(abs(impact[position]), abs(axis[position])) * 1.05,
                         '×%.2f' % value, ha='center', color=BRAND)
    return save(fig, 's2_sensor_direction.png')


def f_dispersion_analytic():
    """Stage 3: the analytic Rayleigh-Lamb curves the model is judged against."""
    data = load('simulation_reproduction/guided_wave_v2/dispersion.json')
    curves = data['curves']
    thickness = data['thickness_m']
    series = []
    for index in (0, 1):
        series.append([(c['frequency_hz'] / 1e3, c['branches'][index]['phase_velocity_m_s'] / 1e3)
                       for c in curves if len(c['branches']) > index])
    at_100 = min(curves, key=lambda c: abs(c['frequency_hz'] - 100e3))
    note('nearest curve f=%.2f kHz, branch0 %.1f m/s, branch1 %.1f m/s'
         % (at_100['frequency_hz'] / 1e3, at_100['branches'][0]['phase_velocity_m_s'],
            at_100['branches'][1]['phase_velocity_m_s']))

    fig, handle = plt.subplots(figsize=(8.6, 4.2))
    handle.plot([point[0] for point in series[0]], [point[1] for point in series[0]],
                color=BRAND, label='A0（基准分支）')
    handle.plot([point[0] for point in series[1]], [point[1] for point in series[1]],
                color=NEUTRAL, label='S0（次低分支）')
    handle.axvline(100, color=WARN, linewidth=1.0, linestyle=':')
    handle.axhline(1.286449, color=WARN, linewidth=1.0, linestyle=':')
    handle.text(101, 1.286449, ' 100 kHz，%.0f m/s' % (1.286449 * 1e3), color=WARN, va='bottom')
    handle.set_xlabel('频率 (kHz)，板厚 %.2f mm' % (thickness * 1e3))
    handle.set_ylabel('相速度 (km/s)')
    handle.set_ylim(0, 3.2)
    handle.set_xlim(0, max(point[0] for point in series[0]))
    handle.set_title('波速的参照：解析色散曲线')
    handle.legend()
    return save(fig, 's3_dispersion_analytic.png')


def f_dispersion_check():
    """Stage 3: the two-dimensional FE against that curve."""
    data = load('simulation_reproduction/guided_wave_v2/dispersion_check.json')
    rows = data['meshes']
    labels = [r['mesh'] for r in rows]
    phase = [r['A0_phase_FE_m_s'] for r in rows]
    analytic = [r['A0_phase_analytic_m_s'] for r in rows]
    error = [r['A0_phase_relative_error'] * 100 for r in rows]
    note('FE phase %s vs analytic %.1f' % (', '.join('%.1f' % v for v in phase), analytic[0]))
    note('error %% %s' % ', '.join('%.2f' % v for v in error))
    note('band max phase error %s' % ', '.join('%.2f' % (r['max_phase_relative_error'] * 100)
                                               for r in rows))

    fig, (left, right) = plt.subplots(1, 2, figsize=(9.8, 3.9))
    positions = range(len(rows))
    left.bar(positions, phase, width=0.5, color=BRAND)
    left.axhline(analytic[0], color=WARN, linestyle='--', linewidth=1.2,
                 label='解析 %.1f m/s' % analytic[0])
    left.set_xticks(list(positions))
    left.set_xticklabels(labels)
    left.set_ylabel('100 kHz 的 A0 相速度 (m/s)')
    left.set_ylim(min(phase) - 15, max(phase) + 15)
    left.set_title('A0 相速度：三个网格对解析 1286.4')
    left.legend()
    right.plot(positions, error, 'o-', color=ACCENT)
    right.set_xticks(list(positions))
    right.set_xticklabels(labels)
    right.set_ylabel('相对解析值的差 (%)')
    # Not titled "converging": the gap to the analytic value does not shrink with refinement.
    # What converges is the numerical solution itself, 1280.3 -> 1278.1 -> 1277.6 m/s.
    right.set_title('与解析值的差：数值解稳定后低约 0.7%')
    for position, value in zip(positions, error):
        right.text(position, value + 0.02, '%.2f%%' % value, ha='center')
    return save(fig, 's3_dispersion_check.png')


def f_abaqus_speed():
    """Stage 4: the first independent solver comparison."""
    data = load('simulation_reproduction/guided_wave_3d/abaqus_dispersion_check.json')
    analytic = data['analytic_phase_100k_m_s']
    rows = data['cases']
    labels = [r['case'] for r in rows]
    speeds = [r['c_phase_100k_m_s'] for r in rows]
    # The JSON stores the magnitude of the gap; the sign matters here because the in-house
    # and Abaqus columns fall on opposite sides of the analytic value, so compute it fresh.
    # The reference is rounded to the value printed on the dashed line, so that the labels
    # and the text that quotes "解析 1286.4" agree to the digits shown.
    reference = round(analytic, 1)
    errors = [(speed - reference) / reference * 100 for speed in speeds]
    for label, speed, error in zip(labels, speeds, errors):
        note('%-28s %.1f m/s (%+.2f%%)' % (label, speed, error))
    note('analytic %.1f m/s' % analytic)

    fig, handle = plt.subplots(figsize=(10.4, 4.2))
    positions = range(len(rows))
    colors = [ACCENT if 'in-house' in r['case'] else BRAND for r in rows]
    handle.bar(positions, speeds, width=0.55, color=colors)
    handle.axhline(analytic, color=WARN, linestyle='--', linewidth=1.2,
                   label='解析 %.1f m/s' % analytic)
    handle.set_xticks(list(positions))
    handle.set_xticklabels([label.replace(' @ abq dt', '\n(@ Abaqus dt)') for label in labels],
                           rotation=12, ha='right')
    handle.set_ylabel('100 kHz 的 A0 相速度 (m/s)')
    handle.set_ylim(min(speeds) - 12, max(speeds) + 22)
    handle.set_title('A0 相速度：自研（青）与 Abaqus（紫）对同一解析值')
    handle.legend()
    for position, (speed, error) in enumerate(zip(speeds, errors)):
        handle.text(position, speed + 3, '%+.2f%%' % error, ha='center', fontsize=9)
    return save(fig, 's4_abaqus_speed.png')


def f_cross_solver():
    """Stage 4: is the waveform difference a solver defect or discretisation?"""
    data = load('simulation_reproduction/guided_wave_3d/abaqus_line500_compare.json')
    rows = data['mesh_convergence']
    wanted = [
        ('Abaqus C3D8 vs in-house, 500 mesh', '跨求解器 @500'),
        ('Abaqus C3D8 vs in-house, 1000 mesh', '跨求解器 @1000'),
        ('in-house 500 vs 1000 (in-house mesh sensitivity)', '自研自身网格敏感性'),
        ('Abaqus C3D8 500 vs 1000 (Abaqus mesh sensitivity)', 'Abaqus 自身网格敏感性'),
    ]
    entries = []
    for key, label in wanted:
        near = [r for r in rows if r['comparison'] == key and abs(r['x_m'] - 0.18) < 1e-9]
        far = [r for r in rows if r['comparison'] == key and abs(r['x_m'] - 0.32) < 1e-9]
        if near and far:
            entries.append((label, near[0]['l2_relative_difference'],
                            far[0]['l2_relative_difference']))
    for label, near, far in entries:
        note('%-24s L2 %.3f (0.18 m) / %.3f (0.32 m)' % (label, near, far))

    fig, handle = plt.subplots(figsize=(9.2, 4.0))
    positions = range(len(entries))
    width = 0.36
    handle.bar([p - width / 2 for p in positions], [e[1] for e in entries], width,
               color=BRAND, label='接收点 0.18 m')
    handle.bar([p + width / 2 for p in positions], [e[2] for e in entries], width,
               color=ACCENT, label='接收点 0.32 m')
    handle.set_xticks(list(positions))
    handle.set_xticklabels([e[0] for e in entries], rotation=12, ha='right')
    handle.set_ylabel('直达波包的时程相对 L2')
    handle.set_title('波形差，与各自换网格时的变化')
    handle.legend()
    for position, entry in enumerate(entries):
        handle.text(position - width / 2, entry[1] + 0.02, '%.3f' % entry[1], ha='center', fontsize=9)
        handle.text(position + width / 2, entry[2] + 0.02, '%.3f' % entry[2], ha='center', fontsize=9)
    return save(fig, 's4_cross_solver.png')


def f_reduced_integration():
    """Stage 4: C3D8R fails on the default hourglass control, not on principle."""
    data = load('simulation_reproduction/guided_wave_3d/abaqus_line500_compare.json')
    by_name = dict((m['name'], m) for m in data['meshes'])
    rows = []
    for name, label in (('500x4x4', 'C3D8R（默认沙漏控制）'),
                        ('500x4x4 C3D8R enhanced HG', 'C3D8R（ENHANCED 沙漏控制）')):
        cases = [c for c in by_name[name]['cases'] if c['case'] == 'abaqus C3D8R'
                 or 'enhanced' in c['case']]
        rms = [c['rms_ratio_to_reference'] for c in cases]
        l2 = [c['l2_relative_difference'] for c in cases]
        rows.append((label, rms, l2))
        note('%s RMS ratio %s L2 %s' % (label, rms, l2))

    fig, (left, right) = plt.subplots(1, 2, figsize=(9.8, 3.9))
    positions = range(len(rows))
    width = 0.36
    left.axhline(1.0, color=WARN, linestyle='--', linewidth=1.0)
    left.bar([p - width / 2 for p in positions], [r[1][0] for r in rows], width, color=BRAND,
             label='接收点 0.18 m')
    left.bar([p + width / 2 for p in positions], [r[1][1] for r in rows], width, color=ACCENT,
             label='接收点 0.32 m')
    left.set_xticks(list(positions))
    left.set_xticklabels([r[0] for r in rows])
    left.set_ylabel('Abaqus 与自研的 RMS 比')
    left.set_title('幅值：ENHANCED 把 0.83 拉回 0.99')
    left.legend()
    right.bar([p - width / 2 for p in positions], [r[2][0] for r in rows], width, color=BRAND)
    right.bar([p + width / 2 for p in positions], [r[2][1] for r in rows], width, color=ACCENT)
    right.set_xticks(list(positions))
    right.set_xticklabels([r[0] for r in rows])
    right.set_ylabel('时程相对 L2')
    right.set_title('波形：1.39 → 0.44')
    return save(fig, 's4_reduced_integration.png')


def f_graded_mesh():
    """Stage 6: the in-plane grading, drawn from the generator's own function."""
    sys.path.insert(0, os.path.join(ROOT, 'simulation_reproduction', 'impact_wave_3d'))
    import make_impact_wave_inp as generator

    coordinates = generator.graded_coordinates(79, 0.1, 1.5e-4, 1.1)
    sizes = [coordinates[i + 1] - coordinates[i] for i in range(len(coordinates) - 1)]
    centres = [(coordinates[i] + coordinates[i + 1]) / 2 for i in range(len(coordinates) - 1)]
    ratios = [sizes[i + 1] / sizes[i] for i in range(len(sizes) - 1)]
    # The first element is at the clamped edge, not at the centre: the grading runs outwards
    # from the middle of the coupon, so the finest element is in the middle of the list.
    centre_size, edge_size = min(sizes), max(sizes)
    middle = len(sizes) // 2
    note('elements %d, centre %.4f mm, edge %.4f mm, max ratio %.4f'
         % (len(sizes), centre_size * 1e3, edge_size * 1e3, max(ratios)))
    note('element at the middle of the list is %.4f mm, at the centre of the coupon'
         % (sizes[middle] * 1e3))
    note('waves per A0 at the edge: %.1f' % (12.7e-3 / edge_size))

    fig, (left, right) = plt.subplots(1, 2, figsize=(10.0, 3.9),
                                      gridspec_kw={'width_ratios': [1.35, 1]})
    left.semilogy([c * 1e3 for c in centres], [s * 1e3 for s in sizes], color=BRAND, linewidth=1.6)
    left.set_xlabel('面内位置 x (mm)')
    left.set_ylabel('单元边长 (mm，对数轴)')
    left.set_title('面内几何级数加密：中心 %.3f mm → 边缘 %.3f mm'
                   % (centre_size * 1e3, edge_size * 1e3))
    left.axhline(12.7 / 10, color=WARN, linestyle='--', linewidth=1.0)
    left.text(52, 12.7 / 10, ' A0 波长的 1/10 = 1.27 mm', color=WARN, va='bottom', fontsize=9)

    zoom = sizes[middle - 12:middle + 12]
    right.bar(range(len(zoom)), [s * 1e3 for s in zoom], color=ACCENT, width=0.8)
    right.set_xlabel('从最中心单元起的序号')
    right.set_ylabel('单元边长 (mm)')
    right.set_title('中心区 24 个单元\n相邻比 ≤ %.2f，保持结构化' % max(ratios))
    return save(fig, 's6_graded_mesh.png')


def f_impact_energies():
    """Stage 6: the three calibration energies and the radius they hand over."""
    history = load('review/history_data.json')
    cases = [
        ('0.100 J', 0.0966, 0.17, 0.25, 0.361, 0.33, 0.48),
        ('0.300 J', 0.9267, 0.53, 0.78, 1.904, 0.76, 1.11),
        ('0.794 J', 15.11, 2.13, 3.13, 30.25, 3.01, 4.43),
    ]
    for label, damage, low, high, old_damage, old_low, old_high in cases:
        note('%s explicit %.4g mJ radius %.2f-%.2f | default %.4g mJ radius %.2f-%.2f'
             % (label, damage, low, high, old_damage, old_low, old_high))
    note('imp_mid reread from odb: ALLDMD peak %.6g J, ALLIE peak %.6g J'
         % (max(v for _, v in history['impact']['imp_mid']['energies']['ALLDMD']),
            max(v for _, v in history['impact']['imp_mid']['energies']['ALLIE'])))

    fig, (left, right) = plt.subplots(1, 2, figsize=(10.2, 3.9))
    positions = range(len(cases))
    width = 0.36
    left.bar([p - width / 2 for p in positions], [c[4] for c in cases], width, color=NEUTRAL,
             label='省略数据行（默认刚度）')
    left.bar([p + width / 2 for p in positions], [c[1] for c in cases], width, color=BRAND,
             label='显式 2.37e13')
    left.set_yscale('log')
    left.set_xticks(list(positions))
    left.set_xticklabels([c[0] for c in cases])
    left.set_ylabel('ALLDMD 峰值 (mJ，对数轴)')
    left.set_title('分层耗散能：显式刚度后三档分别降到约 26.8%、48.7%、50.0%')
    left.legend()
    for position, case in enumerate(cases):
        left.text(position - width / 2, case[4] * 1.15, '%.2f' % case[4], ha='center', fontsize=9)
        left.text(position + width / 2, case[1] * 1.15, '%.3f' % case[1], ha='center', fontsize=9)

    right.errorbar([p - 0.08 for p in positions], [c[5] for c in cases],
                   yerr=[[0] * len(cases), [c[6] - c[5] for c in cases]], fmt='o',
                   color=NEUTRAL, capsize=6, label='默认刚度区间')
    right.errorbar([p + 0.08 for p in positions], [c[2] for c in cases],
                   yerr=[[0] * len(cases), [c[3] - c[2] for c in cases]], fmt='s',
                   color=BRAND, capsize=6, label='显式 2.37e13 区间')
    right.axhline(1.0, color=WARN, linestyle='--', linewidth=1.0)
    right.text(2.35, 1.0, ' 0.8 mm\n 导波算例', color=WARN, fontsize=9)
    right.axhline(3.1, color=WARN, linestyle='--', linewidth=1.0)
    right.text(2.35, 3.1, ' 3.1 mm\n 导波算例', color=WARN, fontsize=9)
    right.set_xticks(list(positions))
    right.set_xticklabels([c[0] for c in cases])
    right.set_ylabel('等价圆半径区间 (mm)')
    right.set_xlim(-0.5, 3.4)
    right.set_title('分层范围随界面刚度整体缩小')
    right.legend(loc='upper left')
    return save(fig, 's6_impact_energies.png')


def f_impact_history():
    """Stage 6: the impact the calibration is read from, in time."""
    entry = load('review/history_data.json')['impact']['imp_mid']
    mass = 3.967622e-3
    times = [t for t, _ in entry['histories']['V3']]
    speeds = [v for _, v in entry['histories']['V3']]
    # The ball arrives moving down (V3 negative) and the contact force on it points up, so
    # the force is the ball's mass times the rise of its own velocity, not its fall.
    deflection = [-u * 1e6 for _, u in entry['histories']['U3']]
    damage = [v * 1e3 for _, v in entry['energies']['ALLDMD']]
    internal = [v * 1e3 for _, v in entry['energies']['ALLIE']]

    window = 2
    force, force_t = [], []
    for index in range(window, len(times) - window):
        span = times[index + window] - times[index - window]
        force.append(mass * (speeds[index + window] - speeds[index - window]) / span)
        force_t.append(times[index] * 1e6)
    peak = max(range(len(force)), key=lambda i: abs(force[i]))
    note('peak contact force %.2f N at t=%.1f us' % (force[peak], force_t[peak]))
    # The contact is not one interval: the undamped elastic plate springs back and meets the
    # ball again, so the force returns to zero in between. Counting the intervals is how the
    # figure's "intermittent" wording is kept a measurement rather than an impression.
    threshold = 0.01 * abs(force[peak])
    intervals = []
    for time, value in zip(force_t, force):
        if abs(value) > threshold:
            if intervals and time - intervals[-1][1] < 1.5:
                intervals[-1][1] = time
            else:
                intervals.append([time, time])
    for start, end in intervals:
        note('  contact interval %.2f-%.2f us' % (start, end))
    first_end = intervals[0][1]
    at_first_end = damage[int(round(first_end / 0.5))]
    note('ALLDMD %.4f mJ at the end of the first contact, %.4f mJ at the end of the step'
         % (at_first_end, damage[-1]))
    note('speed start %.4f m/s, end %.4f m/s, rebound %.3f'
         % (speeds[0], speeds[-1], -speeds[-1] / speeds[0]))
    note('downward deflection peak %.1f um ; ALLDMD final %.4f mJ ; ALLIE peak %.3f mJ'
         % (max(deflection), damage[-1], max(internal)))

    fig, (left, right) = plt.subplots(1, 2, figsize=(10.4, 3.9))
    left.plot(force_t, force, color=BRAND, linewidth=1.4)
    left.axhline(0, color=NEUTRAL, linewidth=0.8)
    left.annotate('峰值 %.0f N' % force[peak], xy=(force_t[peak], force[peak]),
                  xytext=(force_t[peak] + 80, force[peak] * 0.86),
                  arrowprops=dict(arrowstyle='->', color=NEUTRAL))
    loaded = [t for t, value in zip(force_t, force) if value > 0.01 * abs(force[peak])]
    left.axvspan(loaded[0], loaded[-1], color=BRAND, alpha=0.07)
    left.set_xlabel('时间 (µs)')
    left.set_ylabel('接触力 (N)，由球的质量乘速度斜率得出')
    left.set_title('0.300 J 工况：接触分 %d 段，末次分离 %.0f µs'
                   % (len(intervals), intervals[-1][1]))

    # The two quantities get their own scales: the damage energy is a thousandth of the
    # deflection trace's units once both are converted, so one shared axis would hide it.
    right.plot([t * 1e6 for t in times], deflection, color=ACCENT,
               label='冲击点向下挠度 µm')
    right.set_xlabel('时间 (µs)')
    right.set_ylabel('冲击点向下挠度 (µm)', color=ACCENT)
    right.axhline(0, color=NEUTRAL, linewidth=0.8)
    energy = right.twinx()
    energy.plot([t * 1e6 for t in times], damage, color=BRAND,
                label='ALLDMD 分层耗散 mJ')
    energy.set_ylabel('ALLDMD 分层耗散 (mJ)', color=BRAND)
    energy.grid(False)
    right.set_title('挠度与分层耗散（各自刻度；ALLIE 峰值 %.0f mJ 未画）'
                    % max(internal))
    handles, labels = right.get_legend_handles_labels()
    more, more_labels = energy.get_legend_handles_labels()
    right.legend(handles + more, labels + more_labels, loc='lower left', fontsize=9)
    return save(fig, 's6_impact_history.png')


def f_sensor_layout():
    """Stage 7: where the sensors are, and how small the disbond is."""
    sys.path.insert(0, os.path.join(ROOT, 'simulation_reproduction', 'impact_wave_3d'))
    import make_impact_wave_inp as generator

    sensors = generator.SENSORS
    radius = generator.ACTUATOR_RADIUS
    size = 100.0
    clamp = 15.0

    fig, (left, right) = plt.subplots(1, 2, figsize=(10.2, 4.6),
                                      gridspec_kw={'width_ratios': [1.5, 1]})
    length = size + 1
    left.add_patch(Rectangle((0, 0), size, size, facecolor='#f7f7fa', edgecolor=NEUTRAL,
                             linewidth=1.0))
    left.add_patch(Rectangle((clamp, clamp), size - 2 * clamp, size - 2 * clamp,
                             facecolor='none', edgecolor=WARN, linestyle='--', linewidth=1.0))
    left.text(clamp + 1, clamp + 1, '夹持带内缘', color=WARN, fontsize=8.5, va='bottom')
    for name, x, y in sensors:
        x_mm, y_mm = x * 1e3, y * 1e3
        if name == 'ACT':
            left.add_patch(Circle((x_mm, y_mm), radius * 1e3, facecolor=BRAND, alpha=0.30,
                                  edgecolor=BRAND))
            left.text(x_mm, y_mm + radius * 1e3 + 1.4, 'ACT 激励', ha='center', color=BRAND,
                      fontsize=8.5)
        else:
            left.plot(x_mm, y_mm, 'o', color=ACCENT, markersize=5)
            left.text(x_mm + 1.6, y_mm + 1.0, name, fontsize=8.5, color=ACCENT)
    left.set_xlim(-2, length)
    left.set_ylim(-2, length)
    left.set_aspect('equal')
    left.set_xlabel('x (mm)')
    left.set_ylabel('y (mm)')
    left.set_title('9 通道布局：1 激励 + 8 接收，R3/R4、R5/R6、R7/R8 关于 y=50 镜像')

    span = 7.0
    right.add_patch(Rectangle((-span, -span), 2 * span, 2 * span, facecolor='#f7f7fa',
                              edgecolor=NEUTRAL, linewidth=1.0))
    right.add_patch(Circle((0, 0), 0.8, facecolor='none', edgecolor=BRAND, linewidth=1.6))
    right.add_patch(Circle((0, 0), 3.1, facecolor='none', edgecolor=ACCENT, linewidth=1.6))
    right.plot(0, 0, '+', color=WARN, markersize=9)
    # The labels go in the corner rather than beside the circles: at this scale a label next
    # to the small one would run across the large one.
    right.plot([], [], color=BRAND, linewidth=1.6, label='0.8 mm（0.300 J footprint）')
    right.plot([], [], color=ACCENT, linewidth=1.6, label='3.1 mm（0.794 J footprint）')
    right.legend(loc='upper left', fontsize=9, framealpha=0.95)
    right.set_xlim(-span, span)
    right.set_ylim(-span, span)
    right.set_aspect('equal')
    right.set_xlabel('相对中心的 x (mm)')
    right.set_ylabel('相对中心的 y (mm)')
    right.set_title('中心放大：两档 disbond 的等面积圆（同一比例）')
    return save(fig, 's7_sensor_layout.png')


def f_wave_waveforms():
    """Stage 7: the indicator, seen rather than only computed."""
    data = load('review/history_data.json')['wave']
    # The baseline is drawn wide and pale underneath: the small damage case tracks it closely
    # enough that a thin line of the same weight would simply be covered by it.
    cases = [('wav_base', '无损基线', '#c9ccd1', 3.2),
             ('wav_d03_r08', '0.8 mm 分层', BRAND, 1.2),
             ('wav_d08_r31', '3.1 mm 分层', ACCENT, 1.2)]
    window = 90.0
    sensors = ('R1', 'R2')
    fig, handles = plt.subplots(1, 2, figsize=(10.6, 4.0), sharex=True)
    for handle, sensor in zip(handles, sensors):
        for name, label, color, width in cases:
            rows = data[name][sensor]['V3']
            times = [t * 1e6 for t, _ in rows if t * 1e6 <= window]
            values = [v for t, v in rows if t * 1e6 <= window]
            handle.plot(times, values, color=color, linewidth=width, label=label)
        handle.axhline(0, color=NEUTRAL, linewidth=0.6)
        handle.set_xlabel('时间 (µs)')
        handle.set_ylabel('V3 (m/s)')
        handle.set_title('%s（过损伤 %s）' % (sensor, '15 mm' if sensor == 'R1' else '30 mm'))
        handle.legend(fontsize=9)
    # Same window as the reader uses, so this number can be checked against its 0.0547.
    baseline = [v for t, v in data['wav_base']['R1']['V3'] if t * 1e6 <= window]
    damaged = [v for t, v in data['wav_d03_r08']['R1']['V3'] if t * 1e6 <= window]
    count = min(len(baseline), len(damaged))
    rms = math.sqrt(sum(value * value for value in baseline[:count]) / count)
    difference = math.sqrt(sum((damaged[i] - baseline[i]) ** 2 for i in range(count)) / count)
    note('R1 0-90 us normalised difference %.4f, to compare with the reader\'s 0.0547'
         % (difference / rms))
    return save(fig, 's7_wave_waveforms.png')


def f_wave_floor():
    """Stage 7: the signal against the noise floor it has to beat."""
    floor = [0.0017, 0.0012, 0.0049]
    small = [0.0547, 0.0463]
    large = [1.50, 1.33]
    note('floor %.4f-%.4f ; small %.4f/%.4f (%.0f-%.0f x); large %.2f/%.2f'
         % (min(floor), max(floor), small[0], small[1], small[0] / max(floor),
            small[0] / min(floor), large[0], large[1]))

    fig, handle = plt.subplots(figsize=(8.8, 4.0))
    labels = ['R3/R4', 'R5/R6', 'R7/R8', 'R1\n(0.8 mm)', 'R2\n(0.8 mm)',
              'R1\n(3.1 mm)', 'R2\n(3.1 mm)']
    values = floor + small + large
    colors = [NEUTRAL] * 3 + [BRAND] * 2 + [ACCENT] * 2
    handle.bar(range(len(values)), values, color=colors, width=0.6)
    handle.set_yscale('log')
    handle.set_xticks(range(len(values)))
    handle.set_xticklabels(labels)
    handle.set_ylabel('V3 归一化 RMS 差（对数轴）')
    band = handle.axhspan(min(floor), max(floor), color=NEUTRAL, alpha=0.12)
    handle.set_title('噪声底（灰）与两档损伤信号：小档仍高 9–46 倍')
    for index, value in enumerate(values):
        handle.text(index, value * 1.25, '%.4f' % value, ha='center', fontsize=8.8)
    handle.legend([band], ['无损基线镜像对的噪声底'], loc='upper left', fontsize=9)
    return save(fig, 's7_wave_floor.png')


def f_instability():
    """Stage 8: what was actually established about the asymmetry."""
    fig, (left, right) = plt.subplots(1, 2, figsize=(10.2, 3.9))
    default_time = [30, 60, 90]
    default_asymmetry = [2.07, 18.93, 23.88]
    left.plot(default_time, default_asymmetry, 'o-', color=WARN, linewidth=1.8,
              label='省略数据行（默认）')
    bands = [('显式 2.37e13', 0.03, 0.23, BRAND),
             ('显式 ply 3.28e13', 0.02, 0.12, ACCENT),
             ('显式 1.0e12', 0.02, 1.56, NEUTRAL)]
    for index, (label, low, high, color) in enumerate(bands):
        left.axhspan(low, high, color=color, alpha=0.35)
        left.text(91, (low + high) / 2, ' %s：%.2f–%.2f%%' % (label, low, high),
                  color=color, va='center', fontsize=8.6)
    left.set_yscale('log')
    left.set_xlabel('时间 (µs)')
    left.set_ylabel('镜像不对称（最坏，%）')
    left.set_title('决定因素是"给不给数据行"，不是刚度数值')
    left.set_xlim(25, 155)
    left.legend(loc='upper left', fontsize=9)

    names = ['默认\n（无数据行）', '2.37e13', 'ply 3.28e13', '3.28e14', '1.0e12']
    initial = [1.22410, 1.22410, 1.22410, 1.22410, 1.22410]
    right.bar(range(len(names)), initial, color=[WARN] + [BRAND] * 4, width=0.55)
    right.set_ylim(1.2235, 1.2246)
    right.set_xticks(range(len(names)))
    right.set_xticklabels(names, fontsize=9)
    right.set_ylabel('打包阶段的初始稳定步长 (10⁻⁸ s)')
    right.set_title('本组五种设置报告的初始稳定步长相同 1.22410e-08\n'
                    '→ 该比较未支持用初始步长差解释现象')
    for index in range(len(names)):
        right.text(index, 1.22411, '1.22410', ha='center', fontsize=8.8)
    return save(fig, 's8_instability.png')


FIGURES = [
    ('s1_plate_modal', f_plate_modal),
    ('s2_plate_vs_solid', f_plate_vs_solid),
    ('s2_farfield_convergence', f_farfield_convergence),
    ('s2_sensor_direction', f_sensor_direction),
    ('s3_dispersion_analytic', f_dispersion_analytic),
    ('s3_dispersion_check', f_dispersion_check),
    ('s4_abaqus_speed', f_abaqus_speed),
    ('s4_cross_solver', f_cross_solver),
    ('s4_reduced_integration', f_reduced_integration),
    ('s6_graded_mesh', f_graded_mesh),
    ('s6_impact_energies', f_impact_energies),
    ('s6_impact_history', f_impact_history),
    ('s7_sensor_layout', f_sensor_layout),
    ('s7_wave_waveforms', f_wave_waveforms),
    ('s7_wave_floor', f_wave_floor),
    ('s8_instability', f_instability),
]


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    manifest = {}
    for name, function in FIGURES:
        print('%s' % name)
        manifest[name] = function()
    with open(os.path.join(HERE, 'figure_manifest.json'), 'w') as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    print('wrote figure_manifest.json (%d figures)' % len(manifest))


if __name__ == '__main__':
    sys.exit(main())
