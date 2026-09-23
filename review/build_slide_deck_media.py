"""The same eight stages, but each one led by its own simulation clip.

    python review\\build_slide_deck_media.py

Writes review/阶段仿真实现汇报_动画版.pptx. The figures-as-evidence deck
(build_slide_deck.py) stays untouched; this one exists because the runs have since been
exported as merged clips, and a stage that is about motion is better shown moving.

Three rules, all of them carried over from the audit rather than invented here:

  * A clip is chosen from case_manifest.json by (group, name), never by file name. The
    hash in a clip's file name changes whenever it is re-exported, so a hard-coded name
    would either break the build or, worse, silently point at a different run.
  * Where the clip already shows what a static figure showed, the figure is dropped
    instead of repeated smaller. What is left on the right is the evidence the clip does
    not carry — the convergence study, the calibration numbers, the layout.
  * Every clip keeps its caveat. Most of these are single-case or older-parameter runs,
    and several are historical comparisons that must not be read as the current result;
    the caveat goes in the notes so the slide itself can stay short.
"""
import json
import os
import sys
import zipfile

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches

import build_slide_deck as base
import build_stage_report as report

HERE = os.path.dirname(os.path.abspath(__file__))
CLIPS = os.path.join(HERE, 'simulation_gifs_20260923')
MANIFEST = os.path.join(CLIPS, 'case_manifest.json')
OUT = os.path.join(HERE, '阶段仿真实现汇报_动画版.pptx')

GAP = Inches(0.2)
CAPTION_H = Inches(0.32)
BAND_LEFT = Inches(0.6)
BAND_WIDTH = Inches(12.15)
BAND_BOTTOM = Inches(7.28)
TEXT_LEFT = Inches(0.85)
TEXT_WIDTH = Inches(12.1)
MARK = '　▶ 放映时播放'
NUMBERS = '一二三四五六七八'

with open(MANIFEST, encoding='utf-8') as handle:
    INDEX = {(row['group'], row['name']): row for row in json.load(handle)}


def clip(group, name, caption):
    """One animation, resolved through the manifest so the path cannot go stale."""
    row = INDEX.get((group, name))
    if row is None:
        raise SystemExit('case_manifest.json has no %s/%s' % (group, name))
    if not os.path.exists(row['gif']):
        raise SystemExit('clip listed but not on disk: %s' % row['gif'])
    return dict(gif=row['gif'], caption=caption + MARK, caveats=row.get('caveats') or [])


def place_centered(slide, path, left, top, box_w, box_h, caption):
    """Place a picture with its caption, centred in its cell.

    The clips are 1.63:1 while the cells are taller than that, so fitting to the top would
    leave every animation stranded above its caption.
    """
    if not os.path.exists(path):
        print('  missing %s' % os.path.basename(path))
        return
    width, height = base.fit(path, box_w, box_h - CAPTION_H)
    slide.shapes.add_picture(path, left + int((box_w - width) / 2),
                             top + int((box_h - CAPTION_H - height) / 2),
                             width=width, height=height)
    frame = base.textbox(slide, left, top + box_h - CAPTION_H + Emu(12000), box_w, Inches(0.3))
    base.paragraph(frame, caption, 10.5, color=base.MUTED, first=True, space_after=0,
                   align=PP_ALIGN.CENTER)


def strip_band(slide, anims, left, top, width, height):
    """Animations side by side across the full width."""
    cell_w = int((width - GAP * (len(anims) - 1)) / len(anims))
    for index, anim in enumerate(anims):
        place_centered(slide, anim['gif'], left + index * (cell_w + GAP), top, cell_w, height,
                       anim['caption'])


def figure_block(slide, keys, left, top, width, height):
    """The supporting charts, small, beside the animation.

    One column: the clips are four-panel composites, so they need most of the width, and a
    chart squeezed into half of what is left stops being readable on a projector. Vertical
    stacking keeps each chart as wide as the cell allows.
    """
    rows = len(keys)
    caption_h = Inches(0.34)
    cell_h = int((height - GAP * (rows - 1)) / rows)
    for index, key in enumerate(keys):
        cell_top = top + index * (cell_h + GAP)
        base.place(slide, os.path.join(base.HERE, report.FIGURES[key]),
                   left, cell_top, width, cell_h - caption_h,
                   caption=base.caption_for(key), caption_size=9.5,
                   caption_top=cell_top + cell_h - caption_h + Emu(12000))


def animation_band(slide, anims, figures, left, top, width, height):
    """The clip (or the pair) in the large cells, the charts in the cell beside them."""
    hero_w = int(width * (0.58 if len(anims) == 1 else 0.66))
    cell_w = int((hero_w - GAP * (len(anims) - 1)) / len(anims))
    for index, anim in enumerate(anims):
        place_centered(slide, anim['gif'], left + index * (cell_w + GAP), top, cell_w, height,
                       anim['caption'])
    if figures:
        figure_block(slide, figures, left + hero_w + GAP, top, width - hero_w - GAP, height)


def head(slide, spec):
    """Title and the short points, then the top of the figure band."""
    base.accent(slide, top=Inches(0.42), height=Inches(0.52))
    frame = base.textbox(slide, TEXT_LEFT, Inches(0.34), Inches(11.9), Inches(0.62))
    base.paragraph(frame, spec['number'] + '、' + spec['title'], 22, True, base.INK, first=True)
    size, text_h = base.point_layout(spec['points'])
    frame = base.textbox(slide, TEXT_LEFT, Inches(1.0), TEXT_WIDTH, text_h)
    for index, point in enumerate(spec['points']):
        base.paragraph(frame, '· ' + point, size, first=(index == 0), space_after=5)
    return Inches(1.0) + text_h + Inches(0.1)


def notes_for(spec):
    """The stage's own notes, plus what the clips cannot say for themselves."""
    lines = [spec['notes'], '']
    lines.append('本页动画（素材见 review/simulation_gifs_20260923，来源与限制见 case_manifest.json）：')
    for anim in spec['animations'] or spec['strip']:
        lines.append('· ' + anim['caption'].replace(MARK, ''))
        for caveat in anim['caveats']:
            lines.append('　　— ' + caveat)
    return '\n'.join(lines)


def animation_slide(prs, spec):
    slide = base.blank(prs)
    base.set_notes(slide, notes_for(spec))
    top = head(slide, spec)
    animation_band(slide, spec['animations'], spec['figures'], BAND_LEFT, top,
                   BAND_WIDTH, BAND_BOTTOM - top)
    return slide


def table_slide(prs, spec):
    """Stage five: the route table is the result, so the clips go in a strip above it."""
    slide = base.blank(prs)
    base.set_notes(slide, notes_for(spec))
    top = head(slide, spec)
    height = BAND_BOTTOM - top
    strip_h = Emu(int(height * 0.54))
    strip_band(slide, spec['strip'], BAND_LEFT, top, BAND_WIDTH, strip_h)

    table_top = top + strip_h + GAP
    spec_table = next(item['table'] for item in report.STAGES if item.get('table'))
    rows = len(spec_table['rows']) + 1
    shape = slide.shapes.add_table(rows, 3, Inches(0.6), table_top, BAND_WIDTH,
                                   BAND_BOTTOM - table_top)
    table = shape.table
    for index, heading in enumerate(spec_table['headers']):
        cell = table.cell(0, index)
        cell.text = heading
        base.style_run(cell.text_frame.paragraphs[0].runs[0], 10.5, True, base.WHITE)
        cell.fill.solid()
        cell.fill.fore_color.rgb = base.BRAND
    for row, values in enumerate(spec_table['rows'], start=1):
        for column, value in enumerate(values):
            cell = table.cell(row, column)
            cell.text = value
            cell.fill.solid()
            cell.fill.fore_color.rgb = base.WHITE if row % 2 else base.SOFT
            colour = base.INK
            if column == 1:
                colour = base.ACCENT if value == '通过' else base.WARN
            base.style_run(cell.text_frame.paragraphs[0].runs[0], 10,
                           bold=(column == 1), color=colour)
    table.columns[0].width = Inches(4.3)
    table.columns[1].width = Inches(1.3)
    table.columns[2].width = Inches(6.55)
    return slide


# ---------------------------------------------------------------- the stage pages

STAGE_PAGES = [
    dict(number='一', title='薄板落球模型：这个模型能算到哪一步',
         points=[
             '做了什么：薄板加有限阶模态的落球模型——500×400×2 mm 板、8 mm 钨钢球、160 mm 落高',
             '怎么判断：每方向基函数阶数 6 加到 46（组合 46² = 2116 个空间自由度），时间步再减半',
             '结果：整板量稳住了（阶数 38 到 46 位移只差 0.6%），撞击点没稳（接触力还差 5.7%）',
             '所以它后面只用来算整板响应；撞击点的局部量交给三维模型做同工况对照',
         ],
         animations=[clip('61_thin_plate', 'order46',
                          '薄板代理模型：顶面位移场 w（向下为正）、中心线波形与节点时程')],
         figures=['s1_plate_modal'],
         notes=base.SLIDES[0]['notes']),
    dict(number='二', title='三维落球模型：撞击点差多少，传感器方向有没有影响',
         points=[
             '做了什么：自写三维模型分两级——局部小模型让刚球撞出接触力，再把它加到整板模型读 16 个传感器',
             '同工况对比（0.5 ms、6.23 mJ）：薄板给峰值力 162.5 N、下沉 112 µm；三维给 32.4 N、311 µm',
             '差异来源：两模型对局部接触柔度与接触过程的表示不同；各项来源尚未完全分离，也没有实物验证',
             '结果：加密到 200×160×4 后位移 313.0 µm，在所测网格间变化很小；读数还跟取向有关，差 1.2–4.3 倍',
         ],
         animations=[clip('62_custom_3d', 'submodel',
                          '三维局部子模型：总接触力与最大节点接触力的时程（无损伤演化）')],
         figures=['s2_plate_vs_solid', 's2_farfield_convergence', 's2_sensor_direction'],
         notes=base.SLIDES[1]['notes']),
    dict(number='三', title='波的传播速度：先立一把尺子',
         points=[
             '做了什么：先写各向异性板的 Rayleigh–Lamb 解析解，再从有限元波场里按选频与主导 A0 成分拟合相位斜率',
             '为什么这么抠：直接拿时程峰值算速度会被多个模态和边界反射搅乱（旧的 1773 m/s 就是这么来的）',
             '跟谁比：同材料、同板厚 1.72 mm、同传播方向、同模态（A0）；解析解先过各向同性板极限校核',
             '结果：三个网格 1280.3 / 1278.1 / 1277.6 m/s，比解析 1286.4 低约 0.7%；S0 与群速度都没通过',
         ],
         animations=[clip('60_custom_wave', '4000_32_healthy',
                          '最细网格（4000×32）的波场：中心线波形、保存帧时空图与时程')],
         figures=['s3_dispersion_analytic', 's3_dispersion_check'],
         notes=base.SLIDES[2]['notes']),
    dict(number='四', title='从这里接 Abaqus：换个求解器重算，两边对得上吗',
         points=[
             '分界：前面三个阶段是项目自写代码算的；从这一页起交给 Abaqus/Explicit 的三维实体单元',
             '拿什么当尺子：100 kHz 处 A0 相速度解析值 1286.4 m/s，只由材料、板厚、频率、方向与模态决定',
             '结果：自研 1285.6 m/s 低约 0.06%、Abaqus C3D8 1288.5 m/s 高约 0.17%，偏差方向不同',
             '波形差随网格加密下降，但近端仍大于自研自身的网格变化，所以不能说全部来自离散',
             'C3D8R 配默认沙漏控制不可用；换 ENHANCED 能救回幅值，代价是时间步减半',
         ],
         animations=[clip('30_abaqus_validation', 'ugw_line',
                          'Abaqus 线源算例：中心线波形、波场时空图与 ODB 全局动能历史')],
         figures=['s4_abaqus_speed', 's4_cross_solver', 's4_reduced_integration'],
         notes=base.SLIDES[3]['notes']),
    dict(number='五', title='动手之前先试一遍：Abaqus 里哪些路走得通',
         points=[
             '做了什么：动手写方案之前，先用小算例把 Abaqus 能做什么、不能做什么试清楚',
             'Hashin 那条：Abaqus 原生 Hashin 只适用于平面应力类单元，本项目要用的 C3D8 被预处理器拒——'
             '这是该原生实现的适用范围，不是 Hashin 理论的限制',
             '连续壳 SC8R 配 Hashin 能跑通，但没有采用；实体层内判据只给失效指数、不退化刚度',
             '最终架构：C3D8 实体层 + 层间表面黏聚，刚度退化全部由界面承担',
             '编译环境本次能力测试未配置（ifort / ifx / cl 都不在；cl 是 C/C++ 编译器，不是 Fortran 编译器）',
         ],
         strip=[clip('40_material_probes', 'axial_sc8r_hashin',
                     '单单元轴向探针：SC8R + Hashin 能跑通，位移随时间线性增加'),
                clip('40_material_probes', 'surfcoh_stack',
                     '单单元叠层探针：表面黏聚界面的分离，节点位移分段抬升')],
         animations=None,
         figures=[],
         notes=base.SLIDES[4]['notes']),
    dict(number='六', title='冲击区局部加密与三档数值标定',
         points=[
             '做了什么：生成器一次生成整个试件——100×100×2 mm、8 层（当前各层材料轴同向）、刚球落下、层间接触型黏聚',
             '为什么加密：粗网格 1.25 mm 下分层半径只有 1.2 mm，正好一个单元，导波模型连"有损伤"都表示不出来',
             '结果：在已测试的离散工况里，加密后 0.100 J 已出现损伤、粗网格要 0.794 J 才观察到；随后选 0.300 J 作数值致损工况',
             '还没解决：接触区只跨 1.3–1.9 个单元边长，局部接触应力未证明收敛；加密是为让导波能表示损伤',
         ],
         animations=[clip('01_current_impact', 'imp_lo',
                          '0.100 J：中心截面（球为圆形显示）、U3 顶面场与分层耗能'),
                     clip('01_current_impact', 'imp_mid',
                          '0.300 J（选定的数值致损工况）：同一视角，位移与分层耗能都更大')],
         figures=['s6_graded_mesh', 's6_impact_energies'],
         notes=base.SLIDES[5]['notes']),
    dict(number='七', title='导波步：理想脱黏模型的导波响应能不能辨出来',
         points=[
             '做了什么：同一套网格上加导波步——9 个通道、顶面 3 mm 半径压力片、100 kHz、5 周期',
             '为什么这么布点：板只有 100 mm 见方、整板约 8 个波长，边界反射来得早，所以取"短直路径 + 可分离的直达波"',
             '损伤怎么放：分别建静止的无损基线与理想圆形脱黏（0.8 / 3.1 mm），不代表逐点传递的真实分层几何',
             '结果：数值镜像基线 0.0012–0.0049（模型自身的数值基线，不是实验电子噪声）；0.8 mm 档高 9–46 倍，3.1 mm 档波形与相位明显改变',
         ],
         animations=[clip('02_current_wave', 'wav_base',
                          '无损基线：波从激励点散开，中心线波形与全局动能历史'),
                     clip('02_current_wave', 'wav_d08_r31',
                          '3.1 mm 理想脱黏：波场在损伤处明显改变，透射波形被重塑')],
         figures=['s7_sensor_layout', 's7_wave_waveforms', 's7_wave_floor'],
         notes=base.SLIDES[6]['notes']),
    dict(number='八', title='稳定性排查：噪声比信号还大，先把它查清',
         points=[
             '问题：无损板上对称位置的两个接收点本该读一样，晚时刻实测却差 23–39%，比小损伤的信号还大',
             '排查：未见明显全局能量漂移、不是单精度、不是接触范围；特征是逐位可复现、随时间放大，判为数值不稳定',
             '三条机制解释全被数据否掉；唯一确定的是"给不给 *Cohesive Behavior 数据行"是分界，在已测试的若干取值上都干净',
             '代价：换了界面刚度，三档损伤耗能与等价面积分别下降约 73%、51%、50%，而峰值力、挠度只动 1–4%',
         ],
         animations=[clip('20_historical', 'wave_base',
                          '省略数据行（Abaqus 默认罚刚度）：90 µs 镜像不对称涨到 23.88%'),
                     clip('20_historical', 'kply_ply',
                          '显式给出数据行（铺层尺度 3.28e13）：同一量降到 0.02–0.12%')],
         figures=['s8_instability'],
         notes=base.SLIDES[7]['notes']),
]

SOURCES = base.SOURCES + [
    '本页动画：review/simulation_gifs_20260923（清单 case_manifest.json、浏览 index.html），'
    '由 review/build_slide_deck_media.py 按清单插入；每个动画由同一算例的分析步与场数据/响应曲线'
    '合并而成，段与段不表示连续载荷历史',
    '动画为原始数值场导出，段内最多 51 个已保存时间帧、每帧 150 ms 慢放；时间标记是物理时间；'
    '色标在同一段内固定、不同段可不同，跨图比较要看范围',
    '机械响应不等于 PZT 电压；ALLDMD 等价圆半径是跨界面完全断裂能量的等效换算，不是几何损伤边界',
    '正式累积序列当前只收录完成的第 1 次冲击；无帧、失败与正在运行且有锁的算例未导出，'
    '不能把这些也算成已完成动画',
]


def title_slide(prs):
    slide = base.blank(prs)
    from pptx.enum.shapes import MSO_SHAPE
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, base.SLIDE_W, Inches(2.9))
    band.fill.solid()
    band.fill.fore_color.rgb = base.SOFT
    band.line.fill.background()
    band.shadow.inherit = False
    base.accent(slide, top=Inches(0.95), height=Inches(1.0))
    frame = base.textbox(slide, Inches(0.95), Inches(0.9), Inches(11.4), Inches(1.2))
    base.paragraph(frame, '落球冲击 → 损伤 → 导波检测', 40, True, base.INK, first=True,
                   space_after=6)
    base.paragraph(frame, '仿真实现阶段汇报 · 动画版', 22, False, base.BRAND)
    count = sum(len(spec['animations'] or spec['strip']) for spec in STAGE_PAGES)
    frame = base.textbox(slide, Inches(0.95), Inches(2.5), Inches(11.4), Inches(0.5))
    base.paragraph(frame, '研究基础 4 页 · 八个阶段 · %d 段仿真动画 · 16 张静态配图' % count,
                   15, False, base.MUTED, first=True)
    frame = base.textbox(slide, Inches(0.95), Inches(3.5), Inches(11.4), Inches(3))
    base.paragraph(frame, '每一页先用几行说清这一阶段做了什么、结果是什么，'
                          '再把这段仿真自己的动画放上来。', 14, False, base.INK, first=True,
                   space_after=10)
    base.paragraph(frame, '静态图只留动画没有覆盖的那部分证据：收敛研究、标定数字、布局。'
                          '动画里出现的算例都标了它的设置；历史对照与只在单次算例上成立的部分，'
                          '限制写在每页备注里。', 13, False, base.MUTED)
    base.set_notes(slide, '这是动画版，用来放映；文字与证据版的 deck 是 阶段仿真实现汇报.pptx，'
                          '那一份保持不动。两份的八个阶段、结论与限制一致，'
                          '差别只在这里每页以该阶段的仿真动画为主，静态图退到旁边。'
                          '动画由 review/simulation_gifs_20260923 提供，'
                          '按 case_manifest.json 逐条取用；每个动画的来源、算例身份与限制都能追到那里。'
                          '需要提醒：这些动画里有历史参数对照算例，比如第八页的两段是稳定性排查里的'
                          '界面刚度单变量对照，不是当前采用的取值；'
                          '它们只用来演示"给不给数据行"的差别。')
    return slide


def caveats_slide(prs):
    slide = base.blank(prs)
    base.accent(slide, color=base.WARN)
    frame = base.textbox(slide, Inches(0.85), Inches(0.5), Inches(11.9), Inches(0.7))
    base.paragraph(frame, '附录一：用这些数字时，必须一起说清的三件事', 26, True, base.INK,
                   first=True)
    frame = base.textbox(slide, Inches(0.85), Inches(1.6), Inches(11.6), Inches(5.2))
    for index, (headline, detail) in enumerate(base.CAVEATS):
        base.paragraph(frame, '· ' + headline, 16, True, base.WARN, first=(index == 0),
                       space_after=4)
        base.paragraph(frame, '　 ' + detail, 13.5, False, base.INK, space_after=15)
    base.set_notes(slide, '这三条不是在否定前面的结果，而是说明引用时的边界：'
                          '分层范围不是一个确定值、撞击应力本身还没算准、'
                          '黏聚界面为什么在省略数据行时会不稳定，原因还没查清。'
                          '凡是引用分层面积、半径或撞击应力的地方，都要把这三条一起说。'
                          '动画不改变这三条：它把已有的数值场重放一遍，'
                          '既不能证明应力收敛，也不能替代实物验证。')
    return slide


def sources_slide(prs):
    slide = base.blank(prs)
    base.accent(slide, color=base.MUTED)
    frame = base.textbox(slide, Inches(0.85), Inches(0.5), Inches(11.9), Inches(0.7))
    base.paragraph(frame, '附录二：数字与动画从哪来、怎么复现', 26, True, base.INK, first=True)
    frame = base.textbox(slide, Inches(0.85), Inches(1.35), Inches(11.6), Inches(5.5))
    for index, line in enumerate(SOURCES):
        base.paragraph(frame, '· ' + line, 12.5, first=(index == 0), space_after=9)
    base.set_notes(slide, '画面里每一个数、每一段动画都能追到源头：'
                          '数据图由 build_stage_figures.py 生成，时程由 export_history.py 从 odb 导出，'
                          'Abaqus 视图由 export_abaqus_views.py 截取，动画由 build_animations.py 合成，'
                          '研究基础页的九张文献插图由 export_reference_figures.py 裁取。'
                          '本页动画来自 review/simulation_gifs_20260923，由 '
                          'review/build_slide_deck_media.py 按 case_manifest.json 插入，'
                          '同一段动画在 PPT 里是原始 GIF 文件、在 PowerPoint 放映时才播放。'
                          '换一台机器时，odb、原始论文与这些动画都不在版本库里，'
                          '需要重新提交算例、重新拿到论文才能重出。')
    return slide


def validate(prs):
    problems = []
    for index, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if shape.left is None or shape.width is None:
                continue
            right = shape.left + shape.width
            bottom = shape.top + shape.height
            if shape.left < 0 or shape.top < 0 or right > prs.slide_width \
                    or bottom > prs.slide_height:
                problems.append('slide %2d: %-22s right %.2f bottom %.2f'
                                % (index, shape.shape_type, right / 914400.0,
                                   bottom / 914400.0))
    return problems


def main():
    prs = Presentation()
    prs.slide_width = base.SLIDE_W
    prs.slide_height = base.SLIDE_H
    title_slide(prs)
    base.foundation_table_slide(prs)
    base.foundation_impact_slide(prs)
    base.foundation_wave_slide(prs)
    base.foundation_bridge_slide(prs)
    base.overview_slide(prs)

    for spec in STAGE_PAGES:
        if spec['animations']:
            animation_slide(prs, spec)
        else:
            table_slide(prs, spec)

    caveats_slide(prs)
    sources_slide(prs)

    prs.save(OUT)
    print('wrote %s (%.2f MB, %d slides)'
          % (OUT, os.path.getsize(OUT) / 1e6, len(prs.slides._sldIdLst)))

    problems = validate(prs)
    print('shapes outside the slide: %d' % len(problems))
    for line in problems:
        print('  ' + line)

    with zipfile.ZipFile(OUT) as archive:
        gifs = [name for name in archive.namelist() if name.endswith('.gif')]
        print('media parts that are GIFs: %d (%.1f MB)'
              % (len(gifs), sum(len(archive.read(name)) for name in gifs) / 1e6))
        for name in gifs:
            print('  %s  %.2f MB' % (name, len(archive.read(name)) / 1e6))
    return 0


if __name__ == '__main__':
    sys.exit(main())
