"""Build the slide deck from the same stage data the HTML report uses.

    python review\\build_slide_deck.py

Writes review/阶段仿真实现汇报.pptx, 16:9, one slide per stage plus a cover, an overview
table and the caveats.

The animations are inserted as the GIF files themselves. python-pptx stores the original
image blob, so PowerPoint keeps all the frames and plays them in slideshow, which is the
only way an animated GIF survives the trip into a deck; rasterising it would leave a still.
The build checks afterwards that the media parts really are GIFs of the same size as the
sources, because a silent conversion to PNG would look fine in the file listing and only
show up as a dead picture during the talk.

Slide copy is written here rather than reused from the HTML: a slide has room for about
four short lines, and the report's paragraphs are the opposite of that.
"""
import os
import sys
import zipfile

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

import build_stage_report as report

HERE = os.path.dirname(os.path.abspath(__file__))
REF_FIGURES = os.path.join(HERE, 'ref_figures')
# Optional first argument: an alternative output path. Needed when the deck is open in a
# viewer, which locks the file against being overwritten.
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '阶段仿真实现汇报.pptx')

INK = RGBColor(0x1D, 0x20, 0x25)
MUTED = RGBColor(0x6B, 0x72, 0x80)
BRAND = RGBColor(0x6B, 0x4B, 0xD6)
ACCENT = RGBColor(0x2F, 0x9E, 0x8F)
WARN = RGBColor(0xC2, 0x70, 0x3A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SOFT = RGBColor(0xF6, 0xF7, 0xF9)

FONT = 'Microsoft YaHei'
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

OVERVIEW = [
    ('一', '薄板落球模型', '它只能算整板，算不准撞击点'),
    ('二', '三维落球模型', '撞击点差多少量清了：力 5 倍、下沉 2.8 倍'),
    ('三', '波的传播速度', '先立下"多快算对"的标准'),
    ('四', '接入 Abaqus', '换个求解器重算，两边对得上'),
    ('五', '路线能力测试', '先试出能用什么单元、损伤怎么退化'),
    ('六', '冲击步', '局部加密与三档数值标定'),
    ('七', '导波步', '理想脱黏模型的导波响应可辨'),
    ('八', '稳定性排查', '数值不稳定性与敏感性的排查'),
]

# The experiments the simulations are built on: four from the same group at Xiamen
# University's School of Aerospace Engineering. The fifth paper by that group (aero gas
# turbine condition monitoring) is simulation only and is left out of the table.
FOUNDATION = [
    ('冲击监测\nZhao 2025, SMS',
     '1000×1000×2 mm 编织碳纤维板（16 层），\n中心四条 T 形加强筋',
     '8 个 PZT 贴在表面（SMART layer 集成），\n水平间距 400 mm、垂直 200 mm；\n手持力锤随机能量敲击',
     '冲击划分到 8 个子区域并定位：\n按各方向间距归一化的误差\n水平 5.4%、垂直 10.8%（分母不同）；\n力估计误差迁移后 17.3–34.1%'),
    ('齿轮箱主动导波\nChai 2025, IEEE TIM',
     '模拟风机主轴齿轮箱低速端的\n直齿轮试验台，40 号钢、齿轮厚 40 mm',
     'PZT 集成在 0.1 mm 聚酰亚胺 SMART layer，\n间距 60 mm；350 kHz、70 V 激励，\n24 MHz 采样',
     '健康 / 齿面磨损 1.5 mm / 齿根裂纹 4 mm\n三状态的测试集平均准确率 92.36%；\n故障散射信号 ±300 mV，\n95% 扩展不确定度 36 mV'),
    ('螺栓接头贴装压阻\nLiu 2024, IEEE Sensors J',
     'T300 CFRP 135×36×3 mm、孔径 6 mm；\n三种铺层分别做出三种失效',
     'CB/CNT 压阻墨水喷涂在表面；\n拉伸试验机加载（1 与 5 mm/s），\n同步测电阻变化率',
     '三种失效模式的电阻变化形态不同，\n可以分辨（净截面拉断 >250%、\n剪切撕裂 >800%、挤压分三段）'),
    ('螺栓接头嵌入压阻\nLiu 2025, IEEE Sensors J',
     '相同标称尺寸的试件；压阻层仅 0.035 mm，\n嵌在第 10–11 层之间',
     'CNT/GNP 压阻网络；\n拉伸速率 5 mm/min，同步测电阻',
     '嵌入式随损伤阶段发展：净截面拉断 166%→475%、剪出 409%→680%（Fig. 23）。'
     '同阶段贴装/嵌入对照（Fig. 26）：Stage 2 约 4%/166%、剪出约 42%/397%'),
]

FOUNDATION_NOTE = ('同一课题组的航空燃气轮机状态监测（Chen 2024, IEEE Sensors J）'
                   '在 MATLAB/Simulink 里用发动机模型做的，没有物理实验，所以没有列进这张表。')

SLIDES = [
    dict(number='一', title='薄板落球模型：这个模型能算到哪一步',
         points=[
             '做了什么：用薄板理论和有限阶模态搭一个落球模型——500×400×2 mm 板，'
             '8 mm 钨钢球，从 160 mm 高度落下',
             '为什么先做它：它算得快，但只描述"整块板怎么振动"，'
             '所以要先弄清它在撞击点附近能不能用',
             '怎么判断：每方向基函数阶数从 6 加到 46（组合起来是 46² = 2116 个空间自由度，'
             '不是总共 46 个振型）、时间步再减半，看结果还变不变；'
             '另外用方板无量纲基频的经典解 35.99 校核',
             '结果：整板量稳住了——基函数阶数 38 到 46，撞击点位移只差 0.6%；'
             '但接触力还差 5.7%，撞击点附近没稳',
             '所以这个模型后面只用来算整板响应；'
             '撞击点的局部量到底差多少，下一页拿三维接触模型做同工况对照',
         ],
         notes='这一步只做一件事：把薄板模型自己的可靠范围量出来，而不是急着下结论。'
               '做法有两条——一是模型自身够不够稳（每方向基函数阶数 6→46、步长再减半，'
               '结果还变不变），'
               '二是外部对照（方板无量纲基频的经典解 35.99，本模型算 35.98519）。'
               '这里说的"阶数"是每个方向展开基函数的阶数，'
               '两个方向组合后对应的空间自由度是 46² = 2116，不是 46 个振型。'
               '实测：撞击点位移在 38 到 46 之间只差 0.6%，可以说稳住了；'
               '接触力还差 5.7%，说明撞击点附近的量没稳。'
               '所以"薄板能不能用于撞击点"这个问题，这一步只答了一半：'
               '它只能算整板，撞击点局部量的误差大小要到下一页与三维模型对比才知道。',
         figures=['s1_plate_modal'],
         extra=[]),
    dict(number='二', title='三维落球模型：撞击点差多少，传感器的方向有没有影响',
         points=[
             '做了什么：自写三维模型，分两级——先在一个局部加密的小模型里让刚球撞出接触力，'
             '再把这条力加到整板模型上，读出 16 个传感器的应变',
             '为什么：薄板算不出撞击点附近真实的软硬，必须让接触区按三维变形',
             '同工况对比：都是 0.5 ms、都是 6.23 mJ 入射能。薄板给峰值力 162.5 N、'
             '撞击点下沉 112 µm；三维刚球给 32.4 N、下沉 311 µm',
             '为什么差这么多：两个模型对局部接触柔度和接触过程的表示不同——'
             '薄板用有限阶模态描述面外位移，把撞击点附近的局部凹陷抹平了。'
             '软硬一旦不同，力与位移就同时变：球被顶得更狠（力大 5 倍）、'
             '板被压得更浅（下沉小 2.8 倍）。'
             '三维这一侧做过相应的网格检查，但差异的各项来源还没有完全分离，'
             '也没有实物验证，所以不能说已经把原因单独隔离出来',
             '结果：整板网格加密到 200×160×4 后，位移 313.0 µm、应变 206.9 µε '
             '在所测试的网格之间变化很小；'
             '传感器读数还跟取哪个方向有关，沿指定贴片轴取比沿另一轴大 1.2–4.3 倍',
         ],
         notes='薄板为什么把力算大、位移算小：薄板用有限阶模态描述面外位移，'
               '撞击点应该出现的局部凹陷被模态截断抹平了，'
               '于是撞击点附近显得比实际软硬不同。同样入射能量下，接触区越硬，'
               '接触力越大、板下沉越少，所以"力大 5 倍、位移小 2.8 倍"'
               '是同一个原因的两个表现。'
               '但要收住：集中力下局部应力或曲率的处理困难，'
               '不能直接推成"位移必然发散"；薄板与三维之间除空间表示外，'
               '接触处理等也不一样，现有对照只支持"局部响应差异很大"，'
               '没有单独隔离出全部差异的唯一原因。'
               '三维这一侧的可信度来自两点：局部子模型自己做过接触区网格加密'
               '（h0 = 0.25/0.125 mm 给力 32.40/31.98 N，无趋势），'
               '以及子模型与全局模型的交叉核对（挠度 311.0 对 312.5 µm，差 0.5%）；'
               '整板量在 200×160×4 加密后，在所测试的网格之间变化很小。'
               '传感器方向：距撞击点 73 mm 处，沿指定贴片轴投影 206.9 µε、'
               '沿另一轴 58.8 µε，比值 3.5；四个传感器比值 1.23 / 3.52 / 3.00 / 4.28。'
               '"沿哪条轴"按实际输出方向写，不把传感器朝向直接等同于纤维方向。',
         figures=['s2_plate_vs_solid', 's2_farfield_convergence'],
         extra=['s2_sensor_direction']),
    dict(number='三', title='波的传播速度：先立一把尺子',
         points=[
             '做了什么：先自己写一个"波在板里传多快"的解析计算（各向异性板的 '
             'Rayleigh–Lamb 方程），再从有限元波场里把同一个量抠出来对比',
             '为什么要这么抠：直接拿时程峰值算速度会被多个模态和边界反射搅乱'
             '（报告里旧的 1773 m/s 就是这么来的，不可信）。'
             '改法是：先按频率选段、限定时间窗，'
             '对目标频段的主导 A0 成分做时间傅里叶变换、取出它的相位，'
             '再沿空间拟合相位随距离的斜率，得到波数 k，相速度 = 2πf/k。'
             '按频率分解本身不等于自动隔离出单个模态，'
             '所以还要配合选频和"这一段里 A0 是主导成分"的判断',
             '跟谁比：跟项目自己写的解析解比，同一材料、同一板厚 1.72 mm、'
             '同一传播方向、同一模态（A0）；'
             '解析解先用各向同性板做过极限校核（S0 长波极限误差 3.8e-07）',
             '结果：100 kHz 处 A0 的相速度，三个网格给 1280.3 / 1278.1 / 1277.6 m/s，'
             '相邻两次只差 2.2 和 0.5 m/s（说明网格够了），比解析值 1286.4 低约 0.7%',
             '没做到的两条：S0 没测出来（这种激励下面外位移太弱，频谱上没有它的峰）；'
             '群速度两种算法互相矛盾（1778 和 1817，解析 1745），所以一概不用',
         ],
         notes='为什么不用"看时程峰值"这种简单办法：时程里同时有多个模态和边界反射，'
               '峰值法算出来的速度是它们的混合。'
               '改用先选频、再对目标频段的主导 A0 成分取相位、沿空间拟合相位斜率的做法；'
               '按频率分解本身不会自动隔离出单个模态，'
               '这里靠选频与"该段以 A0 为主"的判断来保证比的是同一个模态。'
               '跟谁比、标准是什么：跟项目自己写的各向异性板 Rayleigh–Lamb 解析解比，'
               '同材料、同板厚 1.72 mm、同传播方向、同模态（A0）；'
               '解析解先过各向同性板极限校核（S0 长波极限误差 3.8e-07）。'
               '合格的标准是：有限元结果随网格加密趋于稳定，且与解析值相差在百分之几以内。'
               '实测三个网格 1280.3 / 1278.1 / 1277.6 m/s，相邻差 2.2 和 0.5 m/s，'
               '说明数值解稳定在 1277.6 附近，比解析 1286.4 低约 0.7%。'
               '注意这里的 1286.4 是固定值：只由材料、板厚、频率、'
               '传播方向与模态决定，不随网格变。'
               '没做到的：S0 在法向激励下面外位移太弱、频谱没有峰；'
               '群速度两种算法给 1778 和 1817（解析 1745）互相矛盾，所以都不用。',
         figures=['s3_dispersion_analytic', 's3_dispersion_check'],
         extra=[]),
    dict(number='四', title='从这里开始接 Abaqus：换个求解器重算，两边对得上吗',
         points=[
             '先说明分界：前三页都是项目自写代码算的（薄板、三维落球、二维导波）；'
             '从这一页开始，算例交给 Abaqus/Explicit，用它的三维实体单元',
             '做了什么：把自写代码按完整三维刚度重写；再把同样的网格、同样的激励交给 Abaqus，'
             '两边逐点比波形',
             '两个算例：线源 500×4×4（退化成平面应变，有解析可比）和点源 400×400×4。'
             '后者的 64 万单元不是挑的，是 400×400×4 算出来的，'
             'dx = 1.25 mm 约为指定方向 A0 波长的十分之一'
             '（各向异性板不同方向波长不同，这个比例只对指定方向成立）',
             '拿什么当尺子：100 kHz 处 A0 相速度的解析值 1286.4 m/s。'
             '它是固定值——只由材料、板厚、频率、传播方向与模态决定，不随网格变，'
             '所以三个网格和两个求解器都用它比',
             '结果：自写 1285.6 m/s 比解析值低约 0.06%、Abaqus C3D8 1288.5 m/s 高约 0.17%。'
             '（C3D8 是 Abaqus 的三维实体单元：8 节点、完全积分；'
             'C3D8R 是它的减缩积分版本，算得快，但要额外做沙漏控制）',
             '波形形状的差异：跨求解器的形状差 L2 = 0.57，但这个数单看说明不了好坏，'
             '所以拿每个求解器自己换网格时的波形变化当尺子。加密一倍后跨求解器降到 '
             '0.451 / 0.365：远端测点的 0.365 小于自写代码自己换网格的 0.862，'
             '近端测点的 0.451 反而大于自写网格变化的 0.322。'
             '所以只能说离散误差是重要影响因素，不能说两条差异全都来自离散、'
             '也不能把网格变化当成严格的误差上界',
             'C3D8R 的结论：配默认沙漏控制不可用（沙漏能占 17%、波形幅值低 17%，'
             '加密一倍也没改善）；换 ENHANCED 沙漏控制能把幅值救回来'
             '（与自写的幅值比 0.83 → 0.99），代价是时间步减半、算量约两倍',
         ],
         notes='分界：前三页（薄板、三维落球、二维导波）都是项目自写代码算的；'
               '从这一页开始把算例交给 Abaqus/Explicit，用它的三维实体单元。'
               '64 万单元怎么来的：点源算例的网格是 400×400×4 = 640,000 个单元，'
               'dx = 1.25 mm 约为指定方向 A0 波长的十分之一；'
               '各向异性板不同方向的波长不同，这个"十分之一"只对所指定的传播方向成立。'
               '1286.4 是不是固定值：是。它是 100 kHz 下 A0 的相速度解析值，'
               '只由材料、板厚、频率、传播方向与模态决定，与网格无关，'
               '所以三个网格、两个求解器都拿它当同一把尺子。'
               'A0 相速度的误差方向要写清楚：自写 1285.6 m/s 比解析值低约 0.06%，'
               'Abaqus C3D8 1288.5 m/s 高约 0.16%，一个偏低一个偏高。'
               'C3D8 是什么：Abaqus 的三维实体单元代号，8 节点、完全积分；'
               'C3D8R 是同一单元的减缩积分版本，计算快但需要沙漏控制。'
               '波形差的完整结论：跨求解器直达波包的形状差 L2 = 0.57，'
               '但孤立的一个 L2 没有尺度，所以拿两个求解器各自的网格敏感性当标尺——'
               '加密一倍（500→1000）后跨求解器降到 0.451 / 0.365；'
               '远端测点的 0.365 小于自写代码自身换网格的 0.862，'
               '近端测点的 0.451 却大于自写网格变化的 0.322。'
               '所以可靠的结论是"网格加密降低了跨求解器波形差，'
               '说明离散误差是重要影响因素"；'
               '不能写成两条差异都小于网格变化，网格变化也不是严格的误差上界，'
               '因而不能完全排除求解器差异，完整波形尚未逐点一致。'
               'C3D8R：配默认沙漏控制时沙漏能占 17%、幅值低 17%，加密一倍仍是 17%，'
               '所以不可用；换 ENHANCED 沙漏控制后幅值比从 0.83 升到 0.99，'
               '但稳定步长减半、算量约两倍，而且沙漏能占比仍大——'
               '所以判单元要看响应量，不要只看沙漏能占比。',
         figures=['s4_abaqus_speed', 's4_cross_solver'],
         extra=['s4_reduced_integration']),
    dict(number='五', title='动手之前先试一遍：Abaqus 里哪些路走得通',
         points=[
             '做了什么：先把"落球 → 损伤 → 导波"这条链接起来；动手写方案之前，'
             '先用小算例把 Abaqus 能做什么、不能做什么试清楚',
             '为什么值得先试：与其方案写到一半发现算不了，不如先花小算例把可行路线试出来',
             '试出来的三条：实体单元 C3D8 配 Hashin 会被预处理器直接拒；'
             '连续壳 SC8R 配 Hashin + 能量演化能跑通（能跑通不等于采用，见下）；'
             '本次能力测试时本机没配编译环境（ifort / ifx / cl 都不在，'
             '其中 cl 是 C/C++ 编译器，不是 Fortran 编译器），'
             '所以"实体 + 自编三维 Hashin（VUMAT）"这条路暂时走不通',
             'Hashin 为什么挑单元：Abaqus 原生的 Hashin 损伤模型适用于平面应力类单元，'
             '而本项目要用的是三维实体 C3D8，所以被预处理器拒绝。'
             '这是 Abaqus 这个原生实现的适用范围，不是 Hashin 理论本身的限制；'
             '原生输入也不只三个强度——它区分纵向/横向的拉伸与压缩强度以及剪切强度。'
             '三维层内要做渐进损伤，需要另行选择兼容的损伤模型'
             '（例如 LaRC05，用之前要核对它适用的求解器版本与损伤演化限制）'
             '或用户材料（VUMAT），并且做过验证才能用',
             '结果：最终走 C3D8 实体层 + 层间黏聚，刚度退化由界面承担；'
             '层内判据只给失效指数、不退化刚度，所以目前算到的是层间分层，'
             '层内纤维与基体损伤没有退化刚度；'
             '强度和断裂能在仓库里原本没有（specimen.json 里是 null），'
             '改用可引用的文献替代表并标注清楚',
         ],
         notes='为什么要先试能力：这一步的产出是"哪些方案在本机做不到"。'
               '实体单元 C3D8 配 Hashin 会被预处理器直接拒；'
               '连续壳 SC8R 配 Hashin 加能量演化能跑通（但最终没有采用）；'
               '本次能力测试时本机没有配置编译环境（ifort、ifx、cl 实测都不在；'
               '注意 cl 是 C/C++ 编译器，不是 Fortran 编译器），'
               '所以文献里常见的"实体 + 自编三维 Hashin（VUMAT）"这条路暂时走不了。'
               '这里要说准：被拒的是 Abaqus 原生 Hashin 实现的适用范围——'
               '它只作用于平面应力类单元，而本项目用的是 C3D8 三维实体。'
               '不能把这句话推广成"Hashin 理论本身只能用于平面应力"；'
               '原生 Hashin 的输入也不只是无拉压区分的三个强度，'
               '它分别给纵向与横向的拉伸、压缩强度以及剪切强度。'
               '同样，三维层内损伤也不是"只能 LaRC05 或 VUMAT"：'
               '这里只说明本项目当时试过的两条路，别的兼容模型需要另做评估；'
               '若用 LaRC05，要注明它适用的 Abaqus 版本与损伤演化方面的限制。'
               '缺编译器写"能力测试时未配置"即可，这只是当时的软件环境快照，'
               '不是永久限制。'
               '结论落到架构上：最终链路走 C3D8 实体层 + 层间表面黏聚，'
               '连续壳那条虽然能跑通、但并没有采用。'
               '层内判据只作诊断输出——实体单元上的判据给失效指数、不退化刚度；'
               '刚度退化全部由层间黏聚界面承担。'
               '所以现在模拟到的是层间分层，层内的纤维与基体损伤没有退化刚度，'
               '不能说已经把三类失效都算进去了。'
               '强度和断裂能在仓库里原本是空的，改用可引用的文献替代表并标注为替代值。',
         table=True,
         figures=[],
         extra=[]),
    dict(number='六', title='冲击区局部加密与三档数值标定',
         points=[
             '做了什么：写一个生成器，一次生成整个试件——100×100×2 mm、8 层，'
             '刚球从上方落下，层与层之间用接触型黏聚'
             '（当前各层材料轴同向，未复现交叉或织物铺层）',
             '为什么要加密：粗网格（1.25 mm）下，一次冲击留下的分层半径只有 1.2 mm，'
             '正好只占一个单元——导波模型连"这里有个损伤"都表示不出来',
             '怎么加密：面内单元边长从中心的 0.15 mm 按等比数列长到边缘的 1.269 mm，'
             '相邻单元大小之比不超过 1.10；用平滑拉伸而不是"细网格块 + 过渡环"，'
             '网格仍是有结构的，单元连接、铺层、界面都不用改',
             '结果：在已测试的离散工况里，加密后 0.100 J 已出现损伤、'
             '粗网格要到 0.794 J 才观察到；这是两个离散工况的对比，'
             '不是已精确确定的物理阈值比。随后选 0.300 J 作为数值致损工况',
             '三个不报错的错，是靠真跑一遍才发现的：刚球分面编号从 0 起算，'
             '把一个被夹持的角节点拉进了刚体（只给一句打包警告）；'
             '初速度关键字写成四个字段时 Abaqus 把第三个字段当速度，'
             '落高填多少球都以 3 m/s 飞出；通用接触把刚球自身分面也算了进去，'
             '球面出现 580–862 MPa 的假剪应力',
             '还没解决：接触区只跨少量单元——半径 0.2–0.28 mm 约合 1.3–1.9 个单元边长、'
             '直径约 2.7–3.7 个，因此局部接触应力未证明收敛。'
             '加密的目的是让导波能表示损伤，不是把撞击应力算准',
         ],
         notes='为什么要加密：粗网格 1.25 mm 下，一次低能量冲击留下的分层半径只有约 1.2 mm，'
               '正好只占一个单元，导波模型连"这里有个损伤"都表示不出来。'
               '加密做法：面内间距从中心 0.15 mm 按等比数列（每次乘 1.1）长到边缘 1.269 mm，'
               '相邻单元大小之比不超过 1.10；用平滑拉伸而不是"细网格块 + 过渡环"，'
               '网格保持有结构，单元连接、铺层 elset、界面表面都不用改，也没有悬挂节点。'
               '效果：在已测试的离散工况中，加密后 0.100 J 已观察到损伤、'
               '粗网格则要到 0.794 J 才观察到；这是两个离散工况的对比，'
               '不是已经精确确定的物理阈值比。'
               '铺层要说明白：当前生成器对全部 PLIES 指定同一个 Fibre 方向，'
               '八层是材料轴同向的实体层，不能当成 [0/90] 交叉铺层或织物层合板。'
               '三个不报错的错：刚球分面编号从 0 起算、把一个被夹持的角节点拉进了刚体，'
               'Abaqus 只给一条打包警告；*Initial Conditions, type=VELOCITY 写成四个字段时，'
               'Abaqus 把第三个字段当作速度、忽略第四个，落高填多少球都以 3 m/s 飞出，'
               '数据文件里一条相关警告都没有；通用接触把刚球自身分面也纳入接触域，'
               '球面节点出现 580–862 MPa 的虚假剪应力。'
               '仍未解决：接触区只跨少量单元——半径 0.2–0.28 mm 约合 1.3–1.9 个单元边长、'
               '直径约 2.7–3.7 个，所以局部接触应力场没有证明收敛。',
         figures=['s6_abaqus_model', 's6_impact_animation'],
         extra=['s6_layers', 's6_graded_mesh', 's6_impact_energies', 's6_impact_history']),
    dict(number='七', title='导波步：理想脱黏模型的导波响应能不能辨出来',
         points=[
             '做了什么：在同一套网格上加导波步——9 个通道（1 个激励 + 8 个接收），'
             '激励是顶面 3 mm 半径的压力片，100 kHz、5 个周期的猝发',
             '为什么这么布点：板只有 100 mm 见方，A0 波长 12.7 mm，整板约 8 个波长'
             '（扣掉夹持带后的 80 mm 自由跨度约 6.3 个），边界反射来得早，'
             '所以取"短直路径 + 可分离的直达波"，不做成像阵列；'
             '接收点成对地关于中线对称，方便用"对称位置应该读得一样"自查'
             '（离夹持内缘最近的是 R2，x=80 mm，距 x=90 mm 的夹持内缘 10 mm）',
             '损伤怎么放进去：分别建立静止的无损基线和理想圆形脱黏模型，'
             '脱黏半径取 0.8 / 3.1 mm，界面保留压缩接触与摩擦；'
             '尺寸参考冲击耗能等价指标，不代表逐点传递的真实分层几何',
             '一个必须用双精度的发现：对称位置的两个接收点本该读一样，'
             '单精度下差 12%——和损伤信号一样大；换双精度后降到 0.0–0.9%。'
             '导波位移只有 1e-7 m 量级而板长 0.1 m，尺度差这么大，'
             '舍入误差值得单独检查',
             '结果（0–90 µs 窗内 V3 的归一化 RMS 差）：数值镜像基线 0.0012–0.0049，'
             '这是本模型的数值基线、不是实验电子噪声；半径 0.8 mm 的脱黏在穿透对上读 0.055，'
             '比基线高 9–46 倍；半径 3.1 mm 时透射波形与相位明显改变，相关系数 −0.447',
         ],
         notes='为什么这样布点：板只有 100 mm 见方，A0 波长 12.7 mm，整板约 8 个波长，'
               '扣掉夹持带后的 80 mm 自由跨度约 6.3 个波长，边界反射来得早，'
               '所以取"短直路径 + 可分离的直达波"而不是成像阵列。'
               '接收点成对地关于中线对称，可以用"对称位置应该读得一样"当免费自检；'
               '离夹持内缘最近的是 R2（x=80 mm），距 x=90 mm 的夹持内缘 10 mm。'
               '损伤怎么放进去：分别建立静止的无损基线与理想圆形脱黏模型，半径取 0.8 / 3.1 mm，'
               '界面保留压缩接触与摩擦。这两个半径参考的是冲击耗能的等价圆指标，'
               '并不是把冲击算出的分层逐点传递过来——没有传递 CSDMG、残余应力与变形；'
               '而且小档冲击有 4 个受损界面，导波模型设了 5 个界面。'
               '为什么必须双精度：单/双精度的对称性对照是实测的——单精度下对称点相差 12%'
               '（与损伤信号同量级），双精度降到 0.0–0.9%；'
               '导波位移 1e-7 m 与板长 0.1 m 的尺度差使舍入误差值得单独检查。'
               '结果：0–90 µs 窗内 V3 的归一化 RMS 差；数值镜像基线 0.0012–0.0049'
               '（这是本模型的数值基线，不是实验电子噪声）；半径 0.8 mm 的脱黏在穿透对上读 0.055，'
               '比基线高 9–46 倍；半径 3.1 mm 时波形与相位明显改变，相关系数 −0.447。',
         figures=['s7_wave_animation', 's7_abaqus_model'],
         extra=['s7_wave_frames', 's7_sensor_layout', 's7_wave_waveforms', 's7_wave_floor']),
    dict(number='八', title='稳定性排查：噪声比信号还大，先把它查清',
         points=[
             '问题：无损板上对称位置的两个接收点本该读一样，晚时刻实测却差 23–39%，'
             '比小损伤的信号还大',
             '排查：未见明显全局能量漂移（总能量相对漂移 6e-6，但不能据此排除局部数值误差）、'
             '不是单精度、不是接触范围。'
             '它的特征是每次算都逐位一样（不是随机噪声）、随时间越放越大，'
             '说明是数值上的不稳定',
             '试了三条解释，全部被数据否掉：默认罚刚度过大（改成更硬反而更好）、'
             '静态柔度决定（同样柔度两种结果）、'
             '稳定步长估计里含了接触刚度（本组五种设置报告的初始稳定步长逐位相同，'
             '但这只说明初始步长没随该设置变，不足以据此下全局结论）',
             '唯一确定的是：给不给 `*Cohesive Behavior` 数据行才是分界，'
             '在已测试的若干取值上都干净（1e12–3.28e14）。'
             '所以定成"一律给数据行、取 2.37e13"',
             '代价也量清了：换了界面刚度，三档的损伤耗能与等价面积分别下降约 73%、51%、50%，'
             '而峰值力、挠度只动 1–4%。原来的 1.0 / 3.5 mm 半径因此落到新范围之外，'
             '改成 0.8 / 3.1 mm 重跑',
         ],
         notes='问题：无损板上对称位置的两个接收点本该读一样，晚时刻实测却差 23–39%，'
               '比小损伤的信号还大，这样的指标不能用。'
               '排查顺序：未见明显全局能量漂移（总能量相对漂移 6e-6），'
               '但不能据此排除局部数值误差；不是单精度、不是接触范围；'
               '它的特征是每次算都逐位一样（不是随机噪声）、随时间越放越大，'
               '说明是数值上的不稳定，而不是物理效应。'
               '试过三条解释、全部被数据否掉：默认罚刚度过大（改成更硬反而更好）、'
               '静态柔度决定（同样柔度两种结果）、稳定步长估计里含了接触刚度'
               '（本组五种设置报告的初始稳定步长逐位相同，都是 1.22410e-08；'
               '但这只说明初始步长没有随该设置变化，'
               '该比较未支持用初始步长差解释现象，不足以据此下全局机制定论）。'
               '唯一确定的是：给不给 *Cohesive Behavior 数据行才是分界，'
               '在上述已测试的若干取值上都干净，所以定成"一律给数据行、取 2.37e13"。'
               '代价也量清了：换界面刚度后三档的损伤耗能与等价面积分别下降约 73%、51%、50%，'
               '而峰值力、挠度只动 1–4%；'
               '原来的 1.0 / 3.5 mm 半径落到新范围之外，改成 0.8 / 3.1 mm 重跑。'
               '机制本身仍未查清，报告里按工程规则写，没有当作已解释。',
         figures=['s8_instability'],
         extra=[]),
]

CAVEATS = [
    ('黏聚失稳的原因还没查清',
     '试过三条解释，全部被实测否掉（默认罚刚度过大、静态柔度、稳定步长估计）。'
     '能用的是一条工程规则：*Cohesive Behavior 一定要给数据行，取 2.37e13。'),
    ('分层范围本身带不确定度',
     '换了界面刚度，三档的损伤耗能与等价面积分别下降约 73%、51%、50%，'
     '而峰值力、挠度只动 1–4%。所以这个面积（还是按断裂能换算的等价面积）'
     '不能当确定值用，也不是统计置信区间。'),
    ('撞击应力还没算准',
     '接触半径 0.2–0.28 mm，除以 0.15 mm 网格约合 1.3–1.9 个单元边长、'
     '直径约 2.7–3.7 个，接触区只跨少量单元，局部应力未证明收敛。'
     '加密是为了让导波能表示损伤，不是把撞击应力算准。'),
]

SOURCES = [
    '数字来源（本项目仿真结果部分）：仓库里已提交的指标 JSON、从 odb 导出的时程、'
    '以及 PROJECT_HANDOFF.md 里的数值实测／算例记录',
    '研究基础页的数字与图为文献原文数据；文献实验图由 review/export_reference_figures.py '
    '按各篇 PDF 的图注位置裁取，原始论文不在仓库内',
    '数据图：review/build_stage_figures.py　　时程导出：review/export_history.py（用 abaqus python 运行）',
    'Abaqus 视图与云图：review/export_abaqus_views.py（用 abaqus cae script=... 运行）',
    '动图合成：review/build_animations.py　　本 PPT 与 HTML 报告：review/build_stage_report.py 与 build_slide_deck.py',
    '本汇报不含新的测量；本项目仿真结果部分的数字全部来自已经跑完并记录的算例，'
    '研究基础页的数字取自各篇论文原文；文献图与 odb 一样是外部资源，不在仓库内，需按上述脚本重新导出',
]

# Plain captions for the deck. Keys not listed fall back to the report's own caption.
SLIDE_CAPTIONS = {
    's1_plate_modal': '每方向基函数阶数加到 46，结果还变不变',
    's2_plate_vs_solid': '薄板和三维在撞击点差多少',
    's2_farfield_convergence': '整板网格加密：在所测试的网格间读数变化很小',
    's2_sensor_direction': '传感器朝哪个方向取，读数不一样',
    's3_dispersion_analytic': '波速的参照标准：解析色散曲线',
    's3_dispersion_check': '二维有限元算出来的波速，与解析解对比',
    's4_abaqus_speed': 'A0 相速度：自写代码与 Abaqus 对同一个解析值',
    's4_cross_solver': '两个求解器的波形差，和各自换网格时的变化',
    's4_reduced_integration': 'C3D8R 换沙漏控制前后的幅值与波形',
    's6_abaqus_model': '在 Abaqus 里搭出来的实体模型',
    's6_layers': '铺层放大：8 层读成 8 条线',
    's6_impact_animation': '撞击过程逐帧云图',
    's6_graded_mesh': '面内网格：中心 0.15 mm 到边缘 1.27 mm',
    's6_impact_energies': '三档标定与等价圆半径',
    's6_impact_history': '0.300 J 工况的冲击时程',
    's7_sensor_layout': '9 个通道的位置，与两档理想脱黏圆斑尺寸',
    's7_abaqus_model': '导波算例的实体模型',
    's7_wave_animation': '导波传播逐帧云图',
    's7_wave_frames': '导波云图的四个时刻',
    's7_wave_waveforms': '接收点的波形：无损与两档理想脱黏',
    's7_wave_floor': '损伤信号与数值镜像基线',
    's8_instability': '逐项试过：只有"给不给数据行"是分界',
}


def style_run(run, size, bold=False, color=INK, font=FONT):
    """Set a run's font, including the East Asian face.

    Setting run.font.name alone only writes the latin typeface, and PowerPoint then picks
    its own CJK font, which is how a deck ends up in a font mixture nobody chose.
    """
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font
    properties = run._r.get_or_add_rPr()
    for tag in ('a:latin', 'a:ea', 'a:cs'):
        element = properties.find(qn(tag))
        if element is None:
            element = properties.makeelement(qn(tag), {})
            properties.append(element)
        element.set('typeface', font)


def textbox(slide, left, top, width, height):
    box = slide.shapes.add_textbox(left, top, width, height)
    frame = box.text_frame
    frame.word_wrap = True
    return frame


def paragraph(frame, text, size, bold=False, color=INK, first=False, space_after=8,
              align=PP_ALIGN.LEFT):
    para = frame.paragraphs[0] if first else frame.add_paragraph()
    para.alignment = align
    para.space_after = Pt(space_after)
    run = para.add_run()
    run.text = text
    style_run(run, size, bold, color)
    return para


def accent(slide, top=Inches(0.55), height=Inches(0.62), color=BRAND):
    from pptx.enum.shapes import MSO_SHAPE
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), top, Inches(0.08), height)
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False
    return bar


def fit(path, box_w, box_h):
    """Image size in EMU that fits the box without distorting the aspect ratio."""
    with Image.open(path) as image:
        width, height = image.size
    scale = min(box_w / float(width), box_h / float(height))
    return int(width * scale), int(height * scale)


def place(slide, path, left, top, box_w, box_h, caption=None, caption_top=None,
          caption_size=10.5):
    if not os.path.exists(path):
        print('  missing %s' % os.path.basename(path))
        return
    width, height = fit(path, box_w, box_h)
    offset = left + int((box_w - width) / 2)
    slide.shapes.add_picture(path, offset, top, width=width, height=height)
    if caption:
        # In a grid the caption goes on a fixed baseline so that captions line up across a
        # row; under a single figure it simply follows the picture.
        anchor = caption_top if caption_top is not None else top + height + Emu(20000)
        frame = textbox(slide, left, anchor, box_w, Inches(0.3))
        paragraph(frame, caption, caption_size, color=MUTED, first=True, space_after=0,
                  align=PP_ALIGN.CENTER)


def grid_shape(count):
    """Columns and rows that give n figures the largest cells in a 4.6 inch tall band."""
    if count <= 1:
        return 1, 1
    if count == 2:
        return 2, 1
    if count == 3:
        return 3, 1
    if count == 4:
        return 2, 2
    return 3, (count + 2) // 3


def hero_band(slide, hero, others, left, top, width, height):
    """One figure large, the rest small, for the slides whose anchor is an animation.

    The viewport captures are close to square (1.28:1), so a large animation needs a tall
    region, and the only way to give it one on a slide that also carries five supporting
    charts is to let those get smaller. That is the trade this layout makes deliberately:
    the animation is the thing being shown, the charts are the evidence behind it.
    """
    gap = Inches(0.22)
    caption_height = Inches(0.34)
    hero_w = int(width * 0.47)
    place(slide, os.path.join(HERE, report.FIGURES[hero]), left, top,
          hero_w, height - caption_height, caption=caption_for(hero), caption_size=11.5,
          caption_top=top + height - caption_height + Emu(18000))

    right_left = left + hero_w + gap
    right_w = width - hero_w - gap
    columns = 2
    rows = (len(others) + columns - 1) // columns
    cell_w = int((right_w - gap * (columns - 1)) / columns)
    cell_h = int((height - gap * (rows - 1)) / rows)
    for index, key in enumerate(others):
        column, row = index % columns, index // columns
        cell_left = right_left + column * (cell_w + gap)
        cell_top = top + row * (cell_h + gap)
        # An odd count leaves the last row half empty, so the final figure spans both
        # columns and the grid reads as deliberate rather than as a gap.
        span = (columns - 1) if (index == len(others) - 1 and len(others) % 2) else 0
        place(slide, os.path.join(HERE, report.FIGURES[key]), cell_left, cell_top,
              cell_w + span * (cell_w + gap), cell_h - caption_height,
              caption=caption_for(key), caption_size=9.5,
              caption_top=cell_top + cell_h - caption_height + Emu(14000))


def figure_band(slide, keys, left, top, width, height):
    """Every figure of one stage, laid out in one band so a stage is a single slide."""
    columns, rows = grid_shape(len(keys))
    gap = Inches(0.22)
    caption_height = Inches(0.32)
    cell_w = int((width - gap * (columns - 1)) / columns)
    cell_h = int((height - gap * (rows - 1)) / rows)

    if rows == 1:
        # One row is usually width limited, so the cells end up taller than the pictures and
        # pinning the captions to the cell bottom would leave them stranded inches below.
        # The row is centred as a block instead, with the captions on one baseline.
        heights = []
        for key in keys:
            _, image_h = fit(os.path.join(HERE, report.FIGURES[key]), cell_w,
                             cell_h - caption_height)
            heights.append(image_h)
        block = max(heights) + caption_height
        block_top = top + int((height - block) / 2)
        for index, key in enumerate(keys):
            cell_left = left + index * (cell_w + gap)
            place(slide, os.path.join(HERE, report.FIGURES[key]), cell_left, block_top,
                  cell_w, cell_h - caption_height, caption=caption_for(key),
                  caption_top=block_top + max(heights) + Emu(18000))
        return

    for index, key in enumerate(keys):
        column, row = index % columns, index // columns
        cell_left = left + column * (cell_w + gap)
        cell_top = top + row * (cell_h + gap)
        place(slide, os.path.join(HERE, report.FIGURES[key]), cell_left, cell_top,
              cell_w, cell_h - caption_height, caption=caption_for(key),
              caption_top=cell_top + cell_h - caption_height + Emu(18000))


def blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def title_slide(prs):
    slide = blank(prs)
    from pptx.enum.shapes import MSO_SHAPE
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, Inches(2.9))
    band.fill.solid()
    band.fill.fore_color.rgb = SOFT
    band.line.fill.background()
    band.shadow.inherit = False
    accent(slide, top=Inches(0.95), height=Inches(1.0))
    frame = textbox(slide, Inches(0.95), Inches(0.9), Inches(11), Inches(1.2))
    paragraph(frame, '落球冲击 → 损伤 → 导波检测', 40, True, INK, first=True, space_after=6)
    paragraph(frame, '仿真实现阶段汇报', 22, False, BRAND)
    frame = textbox(slide, Inches(0.95), Inches(2.5), Inches(11), Inches(0.5))
    paragraph(frame, '研究基础 4 页（含 9 张文献实验图）· 八个阶段 · %d 张配图'
              % len(report.FIGURES), 15, False, MUTED, first=True)
    frame = textbox(slide, Inches(0.95), Inches(3.5), Inches(11.4), Inches(3))
    paragraph(frame, '每一页讲一个阶段：做了什么、为什么这么做、拿什么判断对不对、结果是什么，'
                     '以及哪些结论现在还不能用。', 14, False, INK, first=True, space_after=10)
    paragraph(frame, '本项目仿真结果部分的数字都来自已经跑完并记录下来的算例，'
                     '这份汇报里没有新做的仿真；研究基础页的数字取自各篇论文原文。'
                     '每页下方的备注里有更长的说明——方法为什么这么选、数字是怎么来的。',
              13, False, MUTED)
    set_notes(slide, '这份汇报把整个课题的仿真工作按时间顺序拆成八个阶段。'
                     '每一页的正文只说四件事：做了什么、为什么这么做、拿什么判断、结果是什么；'
                     '更长的解释（方法为什么这么选、某个数字怎么来的、哪条路试过但是走不通）'
                     '写在每页的备注里。'
                     '需要提醒的是：前三个阶段（当前第 7–9 页）用的是项目自己写的数值模型，'
                     '从第四阶段（当前第 10 页）开始才把算例交给 Abaqus，用它的三维实体单元；'
                     '真正完整的实体模型（8 层铺层、接触、层间界面）'
                     '是第六阶段（当前第 12 页）开始建的。')
    return slide


def overview_slide(prs):
    slide = blank(prs)
    accent(slide)
    frame = textbox(slide, Inches(0.85), Inches(0.5), Inches(11.5), Inches(0.7))
    paragraph(frame, '八个阶段一览', 28, True, INK, first=True)
    rows = len(OVERVIEW) + 1
    shape = slide.shapes.add_table(rows, 3, Inches(0.85), Inches(1.5), Inches(11.6),
                                   Inches(0.42 * rows))
    table = shape.table
    for index, heading in enumerate(('阶段', '内容', '这一阶段得到了什么')):
        cell = table.cell(0, index)
        cell.text = heading
        style_run(cell.text_frame.paragraphs[0].runs[0], 13, True, WHITE)
        cell.fill.solid()
        cell.fill.fore_color.rgb = BRAND
    for row, (number, name, result) in enumerate(OVERVIEW, start=1):
        for column, value in enumerate(('阶段' + number, name, result)):
            cell = table.cell(row, column)
            cell.text = value
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if row % 2 else SOFT
            style_run(cell.text_frame.paragraphs[0].runs[0], 12.5,
                      bold=(column == 0), color=INK if column != 2 else MUTED)
    table.columns[0].width = Inches(1.1)
    table.columns[1].width = Inches(3.6)
    table.columns[2].width = Inches(6.9)
    set_notes(slide, '八个阶段的分工：一到三阶段是用项目自己写的代码把基础问题弄清'
                     '（薄板够不够用、三维差多少、波传得多快）；'
                     '四到五阶段是接入 Abaqus 并先试通可行的技术路线；'
                     '六到八阶段才把完整的实体模型建起来，把冲击、损伤、导波连成一条链，'
                     '并把数值上的不稳定查清，同时给主要结果标出不确定度范围。')
    return slide


def block(slide, left, top, width, height, heading, lines, colour=BRAND, size=12.5):
    """A headed paragraph block, used on the foundation slides."""
    frame = textbox(slide, left, top, width, Inches(0.45))
    paragraph(frame, heading, 15, True, colour, first=True, space_after=0)
    frame = textbox(slide, left, top + Inches(0.44), width, height - Inches(0.44))
    for index, line in enumerate(lines):
        paragraph(frame, '· ' + line, size, first=(index == 0), space_after=8)


def foundation_table_slide(prs):
    """What the group has already measured, in one table."""
    slide = blank(prs)
    accent(slide)
    frame = textbox(slide, Inches(0.85), Inches(0.4), Inches(11.9), Inches(0.7))
    paragraph(frame, '研究基础：厦大团队已经做过的四个实验', 26, True, INK, first=True,
              space_after=2)
    paragraph(frame, '数字取自各文正文；未核实的参数一律不补写，具体缺项逐篇注明'
                     '（如力锤能量的焦耳数、PZT 个数、试件件数、螺栓预紧力矩）。',
              11.5, False, MUTED)

    rows = len(FOUNDATION) + 1
    width = Inches(12.15)
    shape = slide.shapes.add_table(rows, 4, Inches(0.6), Inches(1.5), width, Inches(3.4))
    table = shape.table
    for index, heading in enumerate(('实验', '试件', '传感与加载', '得到了什么')):
        cell = table.cell(0, index)
        cell.text = heading
        cell.fill.solid()
        cell.fill.fore_color.rgb = BRAND
        for paragraph_ in cell.text_frame.paragraphs:
            for run in paragraph_.runs:
                style_run(run, 12, True, WHITE)
            paragraph_.space_after = Pt(0)
    for row, values in enumerate(FOUNDATION, start=1):
        for column, value in enumerate(values):
            cell = table.cell(row, column)
            cell.text = value
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if row % 2 else SOFT
            for index, paragraph_ in enumerate(cell.text_frame.paragraphs):
                for run in paragraph_.runs:
                    style_run(run, 10, bold=(column == 0),
                              color=INK if column != 3 else MUTED)
                paragraph_.space_after = Pt(2 if index else 2)
    for column, inches in enumerate((2.1, 3.3, 3.5, 3.25)):
        table.columns[column].width = Inches(inches)

    frame = textbox(slide, Inches(0.6), Inches(5.35), Inches(12.15), Inches(1.7))
    paragraph(frame, '· 这四件事说明："测得到"已经有实验支撑——冲击能定位、能估力，'
                     '损伤能让导波散射、让电阻变化，不同失效模式还能分辨。',
              13, False, INK, first=True, space_after=10)
    paragraph(frame, '· ' + FOUNDATION_NOTE, 11.5, False, MUTED, space_after=10)
    paragraph(frame, '· 下一步要问的是：这些信号为什么长这样？损伤到底有多大？'
                     '——那是仿真要回答的，从下一页开始。', 13, False, BRAND)
    set_notes(slide, '四篇里的实验都是厦大航空航天学院卿新林课题组做的，'
                     '前三件（冲击监测、齿轮箱导波、螺栓接头压阻）是实体实验，'
                     '第四件是同一批人把压阻传感器从表面贴装改成嵌入层间，'
                     '灵敏度明显提高。'
                     '引用时要注意几处原文没写或前后不一致的地方：'
                     '冲击监测那篇没有给出力锤的冲击能量具体焦耳数（只给了力锤电压 500–7000 mV）；'
                     '齿轮箱那篇没写 PZT 个数与激励波形周期数；'
                     '螺栓接头那两篇没写试件件数与螺栓预紧力矩；'
                     '嵌入压阻那篇剪出的相对电阻在正文里出现 409%（Fig. 23 段）与 397%'
                     '（Fig. 26 对比段）两个数，引用时择一并注明图号。'
                     '这些在我方论文里引用时应标注"原文未说明"或注明图号。')
    return slide


def figure_grid(slide, entries, left, top, width, height, columns, caption_size=10):
    """A grid of reference figures with a caption each.

    entries are (file stem, caption) pairs; the caption carries the number the figure is
    there to support and the citation, so the slides do not repeat both in a text list.
    """
    rows = (len(entries) + columns - 1) // columns
    gap = Inches(0.2)
    # Two caption lines at 10 pt in a third of the slide width. Longer captions are worse
    # than shorter ones: they push the pictures smaller, which is the opposite of the point.
    caption_h = Inches(0.36)
    cell_w = int((width - gap * (columns - 1)) / columns)
    cell_h = int((height - gap * (rows - 1)) / rows)
    for index, (name, caption) in enumerate(entries):
        column, row = index % columns, index // columns
        cell_left = left + column * (cell_w + gap)
        cell_top = top + row * (cell_h + gap)
        place(slide, os.path.join(REF_FIGURES, name + '.png'), cell_left, cell_top,
              cell_w, cell_h - caption_h, caption=caption, caption_size=caption_size,
              caption_top=cell_top + cell_h - caption_h + Emu(12000))


def foundation_impact_slide(prs):
    """The impact monitoring experiment, the closest one to this project."""
    slide = blank(prs)
    accent(slide)
    frame = textbox(slide, Inches(0.85), Inches(0.34), Inches(11.9), Inches(0.7))
    paragraph(frame, '研究基础（一）：冲击监测实验', 25, True, INK, first=True, space_after=2)
    paragraph(frame, 'Zhao et al., Impact monitoring based on domain adversarial transfer '
                     'learning, Smart Mater. Struct. 34 (2025) 035017', 11.5, False, MUTED)

    points = [
        '试件：1000×1000×2 mm 的编织碳纤维板（16 层），中心四条 T 形加强筋；'
        '整板划成源域和目标域，每个域再分成 8 个 250×250 mm 子区域',
        '传感：8 个 PZT 贴在表面（源域、目标域各 4 个），水平间距 400 mm、垂直间距 200 mm；'
        '用 SMART layer 集成，最大 25 kHz 采样，每次冲击记 12 ms 内的 300 个点',
        '加载：手持力锤垂直敲击，能量随机，平板区和加强筋区都敲；敲击力另用 30 kHz 采集',
        '结果：按各方向传感器间距归一化的定位误差，水平 5.4%、垂直 10.8%；'
        '两者分母不同（400 mm 与 200 mm），按报告均值换算两个方向的平均绝对误差都约 21.6 mm，'
        '不能直接比较百分比来判定哪个方向的绝对精度更差。'
        '力估计平均误差由 22.0%–45.9% 降到迁移后 17.3%–34.1%',
        '作者写明的局限：只用了同一种冲击物；换冲击物材料、换结构之间的迁移还没验证',
    ]
    size, text_h = point_layout(points)
    frame = textbox(slide, Inches(0.85), Inches(1.06), Inches(12.1), text_h)
    for index, point in enumerate(points):
        paragraph(frame, '· ' + point, size, first=(index == 0), space_after=4)

    band_top = Inches(1.06) + text_h + Inches(0.12)
    figure_grid(slide, [
        ('imp_specimen_a', '试件实拍：1000×1000×2 mm 板 + 四条 T 形加强筋'
                           '（Zhao 2025, Fig. 8a）'),
        ('imp_specimen_b', '尺寸与布局：8 个 PZT，间距 400×200 mm'
                           '（Zhao 2025, Fig. 8b）'),
        ('imp_chain', '力锤与 PZT 采集系统：25 kHz 采样'
                      '（Zhao 2025, Fig. 9）'),
    ], Inches(0.6), band_top, Inches(12.15), Inches(7.28) - band_top, 3)
    set_notes(slide, '这篇与本研究最直接相关：它做的正是"冲击之后靠传感器把冲击找出来"。'
                     '有两点可以借鉴：一是传感器布局——报告给的定位误差是按各方向传感器间距'
                     '归一化后的百分比（水平 5.4%、垂直 10.8%），两者分母不同（400 mm 与 200 mm），'
                     '按报告均值换算两个方向的平均绝对误差都约 21.6 mm，'
                     '所以不能用这两个百分比直接断定哪个方向的绝对精度更差；'
                     '二是它用域对抗迁移学习，在有限目标域样本下改善预测。'
                     '迁移范围要收窄：该文验证的是同一试件不同区域之间的迁移，'
                     '跨材料、跨试件与不同冲击物的迁移仍待验证。'
                     '尺寸差距：它的试件是 1000 mm 见方，'
                     '比本研究目前算的试件（100 mm 见方、2 mm 厚）大一个量级。'
                     '该文的数据可用性声明称未产生或分析新数据，'
                     '这句话与正文实验叙述之间的关系需要作者澄清；'
                     '本文不据此推断实验数据的采集年代或是否复用。'
                     '它只监测"冲击事件"，没有对冲击造成的分层等损伤做验证；'
                     '损伤与信号变化的定量关系正是本研究要补的部分。')
    return slide


def foundation_wave_slide(prs):
    """The active guided wave work and the piezoresistive work, side by side."""
    slide = blank(prs)
    accent(slide, color=ACCENT)
    frame = textbox(slide, Inches(0.6), Inches(0.34), Inches(12.1), Inches(0.7))
    paragraph(frame, '研究基础（二）：主动导波与压阻传感实验', 25, True, INK, first=True)

    points = [
        '齿轮箱主动导波（Chai 2025）：PZT 发 350 kHz 导波、24 MHz 采样；'
        '健康 / 齿面磨损 / 齿根裂纹三状态，测试集平均分类准确率 92.36%',
        '螺栓接头压阻（Liu 2024、2025）：传感器贴在表面或嵌进层间，拉伸时测电阻变化；'
        '三种失效模式的电阻变化形态可分；'
        '在该接头与加载条件下，嵌入式的响应比贴装式更早、更明显',
        '与本研究的关系：齿轮箱那件给出信噪比与不确定度的实测做法；'
        '压阻那两件说明在该接头与加载条件下，嵌入式压阻传感器对早期内部损伤的响应'
        '比贴装式更明显——这提示要考虑传感机制和布置，'
        '但压阻是局部响应，不能直接替代本项目表面导波检测的验证',
    ]
    size, text_h = point_layout(points)
    frame = textbox(slide, Inches(0.6), Inches(1.02), Inches(12.1), text_h)
    for index, point in enumerate(points):
        paragraph(frame, '· ' + point, size, first=(index == 0), space_after=4)

    band_top = Inches(1.02) + text_h + Inches(0.1)
    figure_grid(slide, [
        ('gear_rig', '齿轮传动试验台：40 号钢、齿轮厚度 40 mm（原文 thickness，'
                     'Chai 2025, Fig. 3）'),
        ('gear_faults', '预置故障：齿根裂纹 4 mm、齿面磨损 1.5 mm（Chai 2025, Fig. 5）'),
        ('gear_signals', '故障散射 ±300 mV，95% 扩展不确定度 36 mV（Chai 2025, Fig. 9）'),
        ('bolt_layouts', '三种失效模式各配一套传感器布局（Liu 2024, Fig. 16）'),
        ('bolt_curve', '净截面拉断：电阻随加载变化，临近失效时陡升至 >250%'
                       '（Liu 2024, Fig. 17）'),
        ('bolt_damage', '拉伸后孔周损伤：净拉伸 / 剪切撕裂 / 挤压（Liu 2024, Fig. 20）'),
    ], Inches(0.6), band_top, Inches(12.15), Inches(7.28) - band_top, 3)
    set_notes(slide, '这两件实验与本研究的关系不同。'
                     '齿轮箱那件说明：在原文的试件与测试条件下，'
                     '主动导波的信噪比够用（故障散射 ±300 mV，'
                     '对 95% 扩展不确定度 36 mV）；'
                     '而且变工况下的漂移可以用统计检验说明未检出显著差异'
                     '（P=0.317 只表示该检验没有检出显著差异，'
                     '不是证明工况影响恒为零）——'
                     '这是本研究后面读数不确定度分析可以对照的做法。'
                     '要注意两点：一是"信噪比够用"是原文测试条件下的结论，'
                     '不能推广成所有真实结构的导波信噪比都够；'
                     '二是 92.36% 是测试集的平均分类准确率，'
                     '不要与 precision 之类的指标混用。'
                     '螺栓接头那两件说明：在该接头与加载条件下，'
                     '嵌入式压阻传感器对早期内部损伤的响应比贴装式更明显；'
                     '原文并没有说表面传感器完全测不到内部损伤。'
                     '这提示传感机制与布置需要考虑，'
                     '但压阻是局部的接触式响应，'
                     '不能直接当成"表面 PZT 导波测内部分层能力"的限制。'
                     '注意这两件实验的对象都不是冲击损伤，而是齿轮故障与连接失效。'
                     '本页六张图按原图裁剪，均标注了出处（连同研究基础（一）的 3 张，'
                     '研究基础部分共九张文献插图）；'
                     '另有 SMART layer 实物、传感器嵌入截面、嵌入式电阻曲线等图未放入，'
                     '需要时可以换上。')
    return slide


def foundation_bridge_slide(prs):
    """What the experiments settle, what they cannot, and what the simulation takes on."""
    slide = blank(prs)
    accent(slide, color=WARN)
    frame = textbox(slide, Inches(0.75), Inches(0.4), Inches(11.9), Inches(0.7))
    paragraph(frame, '从这些实验到本仿真：实验证明了什么，又留下了什么', 26, True, INK,
              first=True)
    block(slide, Inches(0.75), Inches(1.4), Inches(3.75), Inches(5.6),
          '① 文献在各自工况下证明了什么', [
              '在各自试件与工况下，冲击能被定位与定量：'
              '归一化水平误差 5.4%、力估计误差最小 17.3%',
              '预置的齿轮故障使导波散射达 ±300 mV，'
              '而 95% 扩展不确定度 36 mV（原文测试条件下）',
              '在该接头与加载条件下，三种失效模式靠电阻变化可分辨，'
              '嵌入式比贴装式更早、更明显',
              '也就是说，文献提供了特定试件和工况下的可测性证据；'
              '本模型的检测能力仍需独立验证',
          ], colour=ACCENT, size=12)
    block(slide, Inches(4.75), Inches(1.4), Inches(3.75), Inches(5.6),
          '② 这些文献尚未闭环到本课题的问题', [
              '原文未在本项目试件与参数下建立冲击载荷、逐界面损伤几何与'
              '主动导波响应之间的一一对应',
              '本项目中损伤尺寸没有独立测量，只能从耗能指标反推',
              '本项目里波速、模态与边界反射各占读数变化的多少，还没有分离',
              '传感布局（间距、数量、位置）的取舍，本项目还没有系统的参数研究',
          ], colour=WARN, size=12)
    block(slide, Inches(8.75), Inches(1.4), Inches(4.0), Inches(5.6),
          '③ 本仿真补什么', [
              '用仿真补场量分析与参数研究，并保留后续独立的实测验证',
              '八阶段已开展并形成阶段结果：薄板 → 三维落球 → 波速验证 → 接入 Abaqus → '
              '能力测试 → 冲击标定 → 导波 → 稳定性排查',
              '下一页起，按顺序讲这八阶段各做了什么、为什么这么做、结果是什么',
          ], colour=BRAND, size=12)
    set_notes(slide, '这一页是把文献基础和本仿真接起来的地方。'
                     '两者是互补的：实验与仿真共同支持机理分析与验证，'
                     '不宜说成"实验负责能不能测到、仿真负责为什么"。'
                     '左栏每一条都限定在原文自己的试件与工况下——'
                     '不同论文在各自条件下测得到，不能直接推出本项目的分层在实际条件下也测得到。'
                     '另外两篇参考文献不属于厦大，也不在实验基础里，但方法上有借鉴：'
                     '河北工业大学的声发射到达时间拾取（用小波去噪加 AIC 准则，'
                     '在 CFRP 板上用断铅做定位实验）；'
                     '中科院力学所的蜂窝夹芯板冲击定位（四传感器方阵，'
                     '不需要事先知道波速）。'
                     '两者针对的都是"低信噪比下怎么定到达时刻"和"波速不确定怎么办"，'
                     '与本研究后面用波包起始点定到达时刻的做法是同一类问题。')
    return slide


def set_notes(slide, text):
    """Put the long version on the notes page.

    A slide holds about nine lines, and the questions a reader asks of a number — where it
    came from, why this method, what the standard is — take more than that. The notes carry
    them so the slide itself can stay readable.
    """
    frame = slide.notes_slide.notes_text_frame
    frame.text = text
    for paragraph_ in frame.paragraphs:
        for run in paragraph_.runs:
            style_run(run, 12)


def point_layout(points):
    """Font size and band height for a list of points.

    Measured rather than fixed: a stage with four short points and one with seven long ones
    cannot share a band height, and the second case has to drop a point size so the text
    still stops above the figures instead of running over them.
    """
    limit, size = 64, 12.5
    lines = sum(max(1, int(len(point) / limit) + 1) for point in points)
    if lines > 9:
        limit, size = 72, 11.5
        lines = sum(max(1, int(len(point) / limit) + 1) for point in points)
    return size, Inches(min(2.55, 0.255 * lines + 0.12))


def stage_slide(prs, stage):
    """One slide per stage: title, a full width band of points, and every figure below.

    The points run across the whole width instead of down a column, which is what buys the
    room for a stage's entire figure set to sit on the one slide.
    """
    slide = blank(prs)
    set_notes(slide, stage['notes'])
    accent(slide, top=Inches(0.42), height=Inches(0.52))
    frame = textbox(slide, Inches(0.85), Inches(0.34), Inches(11.9), Inches(0.62))
    paragraph(frame, stage['number'] + '、' + stage['title'], 23, True, INK, first=True)

    size, text_h = point_layout(stage['points'])
    frame = textbox(slide, Inches(0.85), Inches(1.04), Inches(12.1), text_h)
    for index, point in enumerate(stage['points']):
        paragraph(frame, '· ' + point, size, first=(index == 0), space_after=5)

    band_top = Inches(1.04) + text_h + Inches(0.12)
    band_h = Inches(7.28) - band_top

    if stage.get('table'):
        spec = next(item['table'] for item in report.STAGES if item.get('table'))
        rows = len(spec['rows']) + 1
        height = min(band_h, Inches(0.58 * rows))
        shape = slide.shapes.add_table(rows, 3, Inches(1.35), band_top, Inches(10.6), height)
        table = shape.table
        for index, heading in enumerate(spec['headers']):
            cell = table.cell(0, index)
            cell.text = heading
            style_run(cell.text_frame.paragraphs[0].runs[0], 12, True, WHITE)
            cell.fill.solid()
            cell.fill.fore_color.rgb = BRAND
        for row, values in enumerate(spec['rows'], start=1):
            for column, value in enumerate(values):
                cell = table.cell(row, column)
                cell.text = value
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if row % 2 else SOFT
                color = INK
                if column == 1:
                    color = ACCENT if value in ('通过',) else WARN
                style_run(cell.text_frame.paragraphs[0].runs[0], 11,
                          bold=(column == 1), color=color)
        table.columns[0].width = Inches(3.9)
        table.columns[1].width = Inches(1.3)
        table.columns[2].width = Inches(5.4)
    else:
        keys = stage['figures'] + stage['extra']
        # A stage whose set contains an animation puts it in the large cell: it is the only
        # figure that needs the room, and the supporting charts stay readable small.
        hero = next((key for key in keys if report.FIGURES[key].endswith('.gif')), None)
        if hero:
            hero_band(slide, hero, [key for key in keys if key != hero],
                      Inches(0.6), band_top, Inches(12.15), band_h)
        else:
            figure_band(slide, keys, Inches(0.6), band_top, Inches(12.15), band_h)
    return slide


def _title(key):
    for stage in report.STAGES:
        for entry in stage['figures']:
            if entry[0] == key:
                return entry[1]
    return key


def caption_for(key):
    """The slide caption, in plain words.

    The report's own captions are written for a written document and carry phrases like
    "判据的基准" which read as jargon on a slide, so the deck keeps its own shorter wording.
    """
    title = SLIDE_CAPTIONS.get(key)
    if title is None:
        title = report.NUMBERED.sub('', _title(key))
        for separator in ('（', '：'):
            if separator in title:
                title = title.split(separator)[0]
        title = title[:34]
    if report.FIGURES[key].endswith('.gif'):
        title += '　▶ 放映时播放'
    return title


def validate(prs):
    """List shapes that fall outside the slide.

    This is the deck's version of the broken figure: nothing errors, the file opens, and the
    problem only shows up when the last line is already off the projected frame.
    """
    problems = []
    for index, slide in enumerate(prs.slides, start=1):
        for shape in slide.shapes:
            if shape.left is None or shape.width is None:
                continue
            right = shape.left + shape.width
            bottom = shape.top + shape.height
            if shape.left < 0 or shape.top < 0 or right > prs.slide_width \
                    or bottom > prs.slide_height:
                problems.append('slide %2d: %-22s left %.2f top %.2f right %.2f bottom %.2f'
                                % (index, shape.shape_type,
                                   shape.left / 914400.0, shape.top / 914400.0,
                                   right / 914400.0, bottom / 914400.0))
    return problems


def main():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    title_slide(prs)
    # The experiments the simulations build on come first, then the roadmap, then the stages.
    foundation_table_slide(prs)
    foundation_impact_slide(prs)
    foundation_wave_slide(prs)
    foundation_bridge_slide(prs)
    overview_slide(prs)

    for stage in SLIDES:
        stage_slide(prs, stage)

    slide = blank(prs)
    accent(slide, color=WARN)
    frame = textbox(slide, Inches(0.85), Inches(0.5), Inches(11.9), Inches(0.7))
    paragraph(frame, '附录一：用这些数字时，必须一起说清的三件事', 26, True, INK, first=True)
    frame = textbox(slide, Inches(0.85), Inches(1.6), Inches(11.6), Inches(5.2))
    for index, (headline, detail) in enumerate(CAVEATS):
        paragraph(frame, '· ' + headline, 16, True, WARN, first=(index == 0), space_after=4)
        paragraph(frame, '　 ' + detail, 13.5, False, INK, space_after=15)
    set_notes(slide, '这三条不是在否定前面的结果，而是说明引用时的边界：'
                     '分层范围不是一个确定值、撞击应力本身还没算准、'
                     '黏聚界面为什么在省略数据行时会不稳定，原因还没查清。'
                     '凡是引用分层面积、半径或撞击应力的地方，都要把这三条一起说。')

    slide = blank(prs)
    accent(slide, color=MUTED)
    frame = textbox(slide, Inches(0.85), Inches(0.5), Inches(11.9), Inches(0.7))
    paragraph(frame, '附录二：数字从哪来、怎么复现', 26, True, INK, first=True)
    frame = textbox(slide, Inches(0.85), Inches(1.7), Inches(11.6), Inches(4.6))
    for index, line in enumerate(SOURCES):
        paragraph(frame, '· ' + line, 14, first=(index == 0), space_after=12)
    set_notes(slide, '这份汇报里本项目仿真部分的每一张图、每一个数都能追到源头：'
                     '数据图由 build_stage_figures.py 生成，'
                     '时程由 export_history.py 从 odb 导出，'
                     'Abaqus 的模型视图和云图由 export_abaqus_views.py 直接截取，'
                     '动画由 build_animations.py 合成；'
                     '前面研究基础页的九张文献插图由 export_reference_figures.py '
                     '按图注位置从各篇 PDF 裁取。'
                     '换一台机器时，odb 与原始论文都不在版本库里，'
                     '需要重新提交算例、重新拿到论文才能重出这些图。'
                     '还有一点要说清：review/ 目录当前仍未纳入版本跟踪，'
                     '所以不能说整份汇报已经提交、可以从远端完整恢复。'
                     '当前记录的 origin/main 为 b072536，'
                     '这是本次未 fetch 时的本地远端跟踪引用快照，不一定是远端最新状态。')

    prs.save(OUT)
    print('wrote %s (%.2f MB, %d slides)'
          % (OUT, os.path.getsize(OUT) / 1e6, len(prs.slides._sldIdLst)))

    problems = validate(prs)
    print('shapes outside the slide: %d' % len(problems))
    for line in problems:
        print('  ' + line)

    with zipfile.ZipFile(OUT) as archive:
        gifs = [name for name in archive.namelist() if name.endswith('.gif')]
        print('media parts that are GIFs: %d' % len(gifs))
        for name in gifs:
            print('  %s  %.2f MB' % (name, len(archive.read(name)) / 1e6))


if __name__ == '__main__':
    sys.exit(main())
