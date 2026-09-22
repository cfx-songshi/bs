"""Assemble the stage review into one self contained HTML file.

    python review\\build_stage_report.py

The figures come from build_stage_figures.py, the numbers come from the committed metrics
JSONs and from review/history_data.json, and the written record they are checked against
is PROJECT_HANDOFF.md. Nothing here is a new measurement: this file reorganises what has
already been run, and every claim names the file or command it came from.
"""
import base64
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '阶段仿真实现汇报.html')

STAGES = [
    dict(
        id='stage1', number='一', date='2026-09-15',
        title='薄板落球模型：先证明"薄板在冲击点不可信"',
        what='按 P2 工况建立一个四边夹持薄板的落球模型：完整板面 Kirchhoff 薄板 '
             'Rayleigh–Ritz 离散 + 质量归一化模态 + 落球单边 Hertz 代理接触 + 速度 Verlet。'
             '试件 500×400×2 mm、8 mm 钨钢球、落高 160 mm（球质量 3.9676 g、能量 6.2276 mJ）。',
        why='这一行的最大风险不是算不出来，而是算出一个说不清来历的数并写进论文。'
            '所以在做三维之前，先把这个模型自身的可用范围量清楚：它在哪里可信、在哪里不可信。'
            '选解析可对照的薄板模型打底，也让后续三维模型有一个同构型的参照。',
        basis=[
            '模态截断研究：6/10/14/18/22/30/38/46 阶，逐阶比较全时程相对 L2。'
            '38→46 阶的接触力 L2 为 0.057、冲击点位移 0.006；46 阶步长减半后应变 L2 变化 0.012%。',
            '方形固支板特例的无量纲基频 35.98519，与经典值 35.99 相符。',
            '夹持宽度、50/50 等效刚度混合、接触参数都作为明确标注的假设写入 config，'
            '未知项保留在 specimen.json 里。',
        ],
        findings=[
            '等效模型一阶频率 122.52 Hz，46 阶中心最大挠度约 114.6 µm、峰值接触力 109.8 N（4 ms 时程）。',
            '局部接触与应变在模态截断下仍未完全收敛，因此不作"完全验证"的声明。',
        ],
        limits=[
            '输出是顶部名义 PZT 区域平均应变，没有 PZT、胶层、电路耦合或实际抗混叠滤波，'
            '绝不改标为电压。',
            '不是三维有限元，未使用人工波包；实测验证集为空。',
        ],
        meaning='它的价值不在结果本身，而在把"薄板模型能不能用于冲击点"这个问题先用数据答掉，'
                '从而给三维化提供理由；同时把夹持、铺层、接触这些假设逐项记录在案。',
        figures=[('s1_plate_modal', '图 1　薄板模型的模态截断研究',
                  '左：峰值接触力与冲击点位移随模态阶数的变化；右：相邻两阶之间的全时程相对 L2，'
                  '接触力的逐阶变化比位移大一个量级，说明接触量对截断更敏感。')],
    ),
    dict(
        id='stage2', number='二', date='2026-09-19',
        title='三维落球模型：量化薄板的误差，并确定传感器读什么方向',
        what='建立 impact_3d_v1，两级结构：局部细化子模型（刚球单边非穿透约束、每步解 LCP，'
             '接触力与压力分布由解得出，h0 = 0.25 mm、44,352 单元）+ 均匀全局模型'
             '（由子模型力时程驱动，读出 4×4 = 16 个传感器应变）。',
        why='用户要求"在仿真数值实验基础上建立有限元模型、拓展到三维"，并追加了'
            '"增加传感器数量、位置参考知识库论文、考虑三维下铺设方向的影响"。'
            '不先把薄板的误差量化，就无法说明"为什么必须上三维"。',
        basis=[
            '几何与布置依据 P2 论文 p16 图 18 的等间距布置，以及 p15 "边距 = 监控区域一半"的准则，'
            '套到净跨 460×360 mm：x = 77.5/192.5/307.5/422.5 mm、y = 65/155/245/335 mm。',
            '远场网格收敛：100×80×4 / 150×120×4 / 200×160×4 / 200×160×8，共用同一步长 7.3256e-08 s，'
            '因此只有网格在变。',
            '两级交叉验证：子模型挠度 311.0 µm 对全局收敛网格 312.5 µm，差 0.5%。',
        ],
        findings=[
            '薄板的峰值取在其 4 ms 时程上（order22，其接触在 190 µs 内结束），'
            '三维局部子模型的峰值取在 0.5 ms 时程上：薄板给 162.51 N / 112.22 µm，'
            '三维刚球给 32.40 N / 311.02 µm，即力高估 5.0 倍、位移低估 2.8 倍，'
            '方向自洽（三维局部柔度更大→球被接住更软）。',
            '远场收敛值：冲击点位移 300.2 / 308.5 / 312.5 / 313.0 µm，S10 沿冲击方向应变 '
            '195.8 / 204.6 / 206.9 / 206.9 µε，增量递减即收敛；200×160×4 已够，'
            '原先默认的 100×80×4 欠收敛（位移偏低 4.2%）。',
            '传感器方向依赖：距冲击点 73 mm 处沿冲击方向投影 206.9 µε、沿铺设轴 58.8 µε，'
            '比值 3.52；另三个传感器的比值为 1.23 / 3.00 / 4.28。',
        ],
        limits=[
            '局部模型的能量口径只是近似（力按赫兹分布摊到多节点、间隙取角点，二者非共轭）；'
            '改用共轭的贴片加权间隙更差（力 401 N、漂移 61 倍），已试过并回退，不要再试。',
            '小应变测点在欠收敛网格下符号不稳：S13 在 100×80×4 时 +13.8 µε，加密到 200×160×4 后翻为 −12.7 µε。',
            '无损伤、无阻尼、无胶层、无 PZT、无压电耦合。',
        ],
        meaning='这一轮给出了整条链的无损锚点（32 N / 313 µm），并把"传感器读哪个方向"这个实验设计问题'
                '提前用数字回答了 —— P2 取"沿冲击方向应变"因此有物理依据，不是随手选的。',
        figures=[
            ('s2_plate_vs_solid', '图 2　薄板与三维在冲击点的局部量相差数倍',
             '左：峰值接触力；右：冲击点峰值位移。两者方向相反，说明差异来自局部柔度而不是数值误差。'),
            ('s2_farfield_convergence', '图 3　远场网格收敛',
             '四档网格共用同一步长，因此只有网格在变。右图是加密一档带来的变化，趋零即收敛。'),
            ('s2_sensor_direction', '图 4　传感器读数的方向依赖',
             '同一点位，沿冲击方向投影与沿铺设轴投影的峰值应变，比值 1.23–4.28。'),
        ],
    ),
    dict(
        id='stage3', number='三', date='2026-09-19',
        title='导波频散基准：把"波传得对不对"立成判据',
        what='自写各向异性 Rayleigh–Lamb 行列式求解器（边界矩阵最小奇异值作判据），'
             '再按选频与时间窗，对目标频段的主导 A0 成分用空间相位斜率从 FE 波场里拟合 k(f)，两者对照。',
        why='此前自研导波模型的验证只覆盖离散自洽性（网格加密、半步长、能量漂移、刚体转动残差），'
            '从未验证"模型是否以正确速度传波"。报告里那个"表观群速度 1773.48 m/s"由包络峰值硬算，'
            '混杂模态与反射，不是频散意义上的模态速度。',
        basis=[
            '解析求解器先经各向同性严格极限自检才用于对照：S0 长波极限误差 3.8e-07、'
            '高阶分支高频趋近 Rayleigh 波速误差 3.4e-04、截止频率下侧分支数 = 2，均通过。',
            '材料与 FE 同源：E1 = 128.1 GPa、E2 = E3 = 8.2 GPa、G12 = G13 = 4.7 GPa、'
            'G23 = 3.44 GPa、ρ = 1570 kg/m³、板厚 1.72 mm。',
            '取 85–115 kHz 带内逐点比较，而不是只看一个频点。',
            '按频率分解本身不会自动隔离出单个模态，所以先选频、限定时间窗，'
            '再对该频段的主导 A0 成分取相位；解析值也只由材料、板厚、频率、'
            '传播方向与模态决定，比较时这几项都要固定（这里统一取 A0 与同一传播方向）。',
        ],
        findings=[
            'A0 相速度验证通过：100 kHz 处误差约 0.7%，全频段逐点 ±1.3% 以内；'
            '网格 1000×8 → 2000×16 → 4000×32 给 1280.3 / 1278.1 / 1277.6 m/s，误差 0.48% / 0.65% / 0.68%，收敛。',
            '途中修掉一个解析 bug：判别式为负时求解器返回"无解"，但那正对应沿厚度振荡同时指数变化的'
            '非均匀分波，是各向异性板的正常解；该早退曾把整个 A0 分支静默删除。',
        ],
        limits=[
            'S0 未验证：法向线力激励下面外位移分量极弱，S0 波数处无谱峰。',
            '群速度未达验证精度：解析 1745.5 m/s，包络峰值法 1778、相位斜率法 1817，两法彼此不一致，'
            '不应宣称通过。',
            'k(f) 存在 ±1% 振荡，最可能来自有限板长内波包与自由端反射的驻波干涉。',
        ],
        meaning='频散基准是后面一切损伤指标的前提：如果传播速度本身没校准，"波形变了"就无法归因于损伤。'
                '这一轮也留下了"短记录上群速度估计不可靠"这条经验。',
        figures=[
            ('s3_dispersion_analytic', '图 5　判据的基准：解析色散曲线',
             '各向异性 Rayleigh–Lamb 的两个低阶分支，虚线标出工作点 100 kHz、1286 m/s。'),
            ('s3_dispersion_check', '图 6　二维 FE 对解析基准',
             '左：100 kHz 的 A0 相速度（虚线为解析值）；右：相对误差随网格加密收敛。'),
        ],
    ),
    dict(
        id='stage4', number='四', date='2026-09-19 ~ 09-20',
        title='三维化与 Abaqus 独立验证：从自研求解器走到第三方求解器',
        what='在 guided_wave_3d 里用完整三维正交各向异性刚度重写显式求解器；'
             '生成 Abaqus/Explicit 输入并首次提交求解；再让自研与 Abaqus 在同一网格、'
             '同一时间步上逐点对照。线源（500×4×4、1000×4×8）与点源（400×400×4，64 万单元）都做了。',
        why='用户明确要求"后续所有工作都要拓展到三维，且需要 Abaqus 有限元模型，不只是自研求解器"。'
            '自研能跑只说明自洽；能被独立求解器复现，才是可以写进论文的证据。',
        basis=[
            '线源应退化为平面应变：3D 线源与 2D 同网格只差 0.11%，说明三维装配正确、'
            '完整三维刚度在单向铺层下与平面应变一致。',
            '对照前先对齐时间步：Abaqus 的稳定步长比自研保守估计大 30%，单这一项就让自研与自身'
            '差出峰值 4.7%；自研已接 --dt-scale，基准取与 Abaqus 差 0.016%。',
            '比较以直达波包的窗口 RMS 为准：两边历史输出都是 1 µs、约 10 点/周期，'
            '采样最大值可低估真峰达 5%。',
        ],
        findings=[
            'A0 相速度对照通过：解析 1286.4 m/s，自研 1285.6（比解析低约 0.06%）、'
            'Abaqus C3D8 1288.5（高约 0.17%），'
            '加密后 Abaqus C3D8 1285.3。这是本项目第一个真正独立的第三方求解器对照。'
            '注意两个求解器的偏差方向不同：自研偏低、Abaqus 偏高。',
            '那个"跨求解器 L2 ≈ 0.57"的波形形状差被定位到离散层面：加密到 1000×4×8 后跨求解器降到 '
            '0.451/0.365，而自研自身 500→1000 的网格敏感性是 0.322/0.862。'
            '远端测点的 0.365 小于自研自身的离散敏感性 0.862，但近端测点的 0.451 反而大于 0.322 —— '
            '所以只能说"网格加密降低了跨求解器波形差、离散误差是重要影响因素"，'
            '网格变化不是严格的误差上界，不能完全排除求解器差异，完整波形尚未逐点一致。',
            'C3D8R 的判断被自己的数据更正两次：默认沙漏控制不可用（ALLAE/ALLIE 峰值 17.3%，'
            '加密一倍反而 17.3%→31.2% 更差），但换成 ENHANCED 沙漏控制后响应救回来了'
            '（RMS 比 0.827→0.993），代价是稳定步长腰斩。准确说法是"配默认沙漏控制不可用"，'
            '不是"减缩积分不可用"；仍推荐 C3D8，理由从"救不了"改成成本。',
            '配套结论：ALLAE/ALLIE 不能跨沙漏控制类型比较 —— ENHANCED 的人工刚度更刚、其 ALLAE 定义随之改变，'
            '占比仍大而响应误差已从 17% 降到 1–3%。判单元应以响应量（RMS/L2/相速度）为准。',
            'Abaqus 首次提交暴露两个静态自检挡不住的真错误：assembly 层载荷必须写 PLATE-1.679；'
            '各向异性材料即使材料轴与全局轴重合也必须显式给 *Orientation。'
        ],
        limits=[
            '差异没有归零，仍不能宣称逐点波形一致。',
            '同一单元同一网格下，自研的波形随网格变化比 Abaqus 的大，这条已记录但未做归因。',
            '点源侧未做网格收敛；群速度两法互相矛盾，两个都不要引用。',
        ],
        meaning='把"自己能跑"升级为"独立求解器能复现"，并顺手积累了一套可复用的对照方法论：'
                '对齐时间步、以窗口 RMS 而非峰值比较、用各自的网格敏感性当尺子。',
        figures=[
            ('s4_abaqus_speed', '图 7　A0 相速度：自研与 Abaqus 对同一解析值',
             '青色为自研、紫色为 Abaqus，虚线为解析 1286.4 m/s；每根柱上标出相对误差。'),
            ('s4_cross_solver', '图 8　跨求解器差异与各自的网格敏感性',
             '跨求解器差异（前两组）必须与两个求解器各自的网格敏感性（后两组）相比才有意义：'
             '加密后在远端已低于自研自身的变化量，近端则不然，'
             '所以网格变化只能当作参照，不是严格误差上界。'),
            ('s4_reduced_integration', '图 9　C3D8R 的两种沙漏控制',
             '左：与自研的幅值比，虚线处才是 1.0；右：波形 L2。换 ENHANCED 后响应进入可用范围，'
             '但沙漏能占比仍大，所以判据以响应量为准。'),
        ],
    ),
    dict(
        id='stage5', number='五', date='2026-09-20',
        title='立项"落球 → 损伤 → 导波"，先做能力实测',
        what='把冲击线与导波线接成一条链，口径先定：铺层最终 0/90、先用已验证的 [0]₈ 打通；'
             '损伤先做层内 Hashin + 能量演化（实测后这一条只保留为诊断，见下）；'
             '导波先机械激励 + 应变读数，之后再接真压电。'
             '立项之前先做单元能力实测：几组测试 deck 与读数脚本都提交在 abaqus/ 下作为依据。',
        why='这一步要的产出是"哪些方案在本机做不到"，避免方案写到一半撞墙。'
            '同时也决定了整条链的本构架构：刚度退化由谁承担。',
        basis=[
            'C3D8 实体 + Hashin → 预处理器直接拒绝：Abaqus 原生的 Hashin 损伤模型只适用于'
            '平面应力类单元（壳、连续壳、膜），而本项目要用的是三维实体。'
            '这是该原生实现的适用范围，不是 Hashin 理论本身的限制；'
            '原生输入也不是无拉压区分的三个强度，它分别给纵向/横向的拉伸与压缩强度以及剪切强度。'
            '三维层内损伤需要另选兼容模型（例如 LaRC05，用前要核对它适用的求解器版本与损伤演化限制）'
            '或用户材料（VUMAT），并且做过验证才能用。',
            'SC8R 连续壳 + Hashin + 能量演化 → THE ANALYSIS HAS COMPLETED SUCCESSFULLY。'
            '注意这只说明它能跑通，并不说明最终采用了它。',
            '本次能力测试时本机没有配置编译环境（无 Intel oneAPI、无 Visual Studio，'
            'ifort / ifx / cl 均不在；其中 cl 是 C/C++ 编译器，不是 Fortran 编译器），'
            '"实体 + 自编三维 Hashin（VUMAT）"这条路暂不可走。'
            '这只是当时的软件环境快照，不是永久结论。',
            '三轮单单元能力测试证明：实体单元上的损伤判据只给失效指数、不退化刚度。',
        ],
        findings=[
            '架构结论：最终链路走 C3D8 实体层 + 层间表面黏聚（连续壳那条能跑通但没有采用）。'
            '层内判据只作诊断输出——实体单元上的判据给失效指数、不退化刚度；'
            '刚度退化全部由层间黏聚界面承担。'
            '黏聚单元那条路被否掉，因为它把稳定步长压到 3.8e-12 s。',
            '参数缺口显形：强度与断裂能在仓库里根本不存在（specimen.json 里是 null）。'
            '已找到可引用的替代表，并按项目惯例标注为替代值：强度 59.5 MPa、GnC = 490 J/m²、'
            'GsC = GtC = 1060 J/m²、B-K η = 2.284。',
        ],
        limits=[
            '实际实现的是层间分层；层内纤维与基体损伤没有退化刚度。'
            '因此不能说已模拟纤维断裂、基体开裂与分层的全部复合材料失效模式。',
            '曾经预判的连续壳代价没有发生：既然最终留在 C3D8 实体上，'
            '导波侧原先在 C3D8 上做的频散验证仍然适用，不必对 SC8R 重做。',
            '替代参数与实物之间不是同一批材料，不能与实测混淆。',
        ],
        meaning='这一轮决定的是整条链的架构，而且每个选择都有实测依据 —— 论文里可以直接写成方法选择理由，'
                '而不是"我选了 A"。',
        table=dict(
            title='损伤与界面路线的能力实测结果',
            detail='逐条列出本机实测的结论与依据，包括被拒绝的路线。'
                   '这些测试 deck 与读数脚本提交在 simulation_reproduction/impact_wave_3d/abaqus/ 下。',
            headers=('路线', '本机结论', '依据'),
            rows=(('C3D8 实体 + Hashin', '拒绝', 'Abaqus 原生 Hashin 只适用于平面应力类单元（壳、连续壳、膜），预处理器直接报错'),
                  ('SC8R 连续壳 + Hashin', '通过', 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY'),
                  ('C3D8 实体 + 自编三维 Hashin（VUMAT）', '不可行', '能力测试时未配置编译环境（无 Intel oneAPI / Visual Studio，ifort / ifx / cl 均不在）'),
                  ('C3D8 实体 + 层内判据', '仅诊断', '给失效指数但不退化刚度（三轮单单元测试）'),
                  ('黏聚单元 cohesive element', '不可用', '把稳定步长压到 3.8e-12 s'),
                  ('接触型黏聚（最终采用）', '通过', '无额外质量，刚度退化由界面承担')),
        ),
        figures=[],
    ),
    dict(
        id='stage6', number='六', date='2026-09-20',
        title='冲击步建成：加密网格、标定数值致损工况',
        what='写出一体化生成器 make_impact_wave_inp.py：100×100×2 mm 小试件、[0]₈ 八层、刚球解析面 + '
             '接触 + 初速，冲击步 500 µs。面内按几何级数从中心 0.15 mm 平滑长到边缘 1.269 mm；'
             '界面用接触型黏聚（无黏聚单元、无界面质量）。冲击步用命名面对而非 ALL EXTERIOR。',
        why='粗网格（1.25 mm 均匀）上，一次低能量冲击留下的分层半径只有约 1.2 mm，只对应 1 个单元 —— '
            '导波模型连"表示"这个损伤都做不到。所以加密不是为了把冲击应力算准，'
            '而是为了让导波模型能够表示损伤。',
        basis=[
            '加密做法：用平滑拉伸而不是"细 patch + 过渡环"，网格保持结构化，'
            '于是单元连接、铺层 elset、界面表面全都不用改，也没有悬挂节点；相邻单元尺寸比 ≤ 1.10。',
            '边缘 1.269 mm 仍满足 100 kHz 下每 A0 波长 10 个单元（波长约 12.7 mm）。',
            '三档标定以落球能量为自变量：0.100 / 0.300 / 0.794 J。',
            '界面参数取自文献替代表（见上一节），并按项目惯例标注出处。',
        ],
        findings=[
            '在已测试的离散工况中，加密把起始阈值降了约 8 倍：粗网格上 0.794 J 才刚起始，加密后 0.100 J 就起始。'
            '这是两个离散工况的对比，不是已经精确确定的物理阈值比。'
            '原因是粗网格把接触集中载荷摊在 1.25 mm 单元上、低估了局部界面剪应力；'
            '加密后剪应力峰值都落在 59.5 MPa 附近，与起始强度一致，说明判据标定自洽。',
            '选定 0.300 J（12.30 m/s）为数值致损工况：分层跨 5 个界面、直径约 1.5–2.2 mm，'
            '在中心 0.15–0.3 mm 网格上有 7–11 个单元，导波模型能表示，同时给后续多次落球留了累积空间。',
            '分层耗散在首个接触段内就已经完成：第一段接触结束（238 µs）时 ALLDMD 为 0.9267 mJ，'
            '与全步结束时的值相同；球在约 240–290 µs 的一次短暂分离后再次接触，没有新增分层。'
            '接触力本身是多峰形状（板弹回把球顶住），仅用"接触时长"描述这一段会丢掉这个结构。',
            '三个静默 bug 都在这一轮被抓出来：刚球分面连接关系偏移 1，把板的一个被夹持角节点拉进了刚体'
            '（Abaqus 只给一条打包警告）；*Initial Conditions, type=VELOCITY 写成四字段时'
            'Abaqus 把第三个字段当速度、忽略第四个，落高填多少球都以 3 m/s 飞出且一条警告都没有；'
            '通用接触把刚球自身分面纳入接触域，球面节点出现 580–862 MPa 虚假剪应力。',
        ],
        limits=[
            '接触半径 0.2–0.28 mm 除以 0.15 mm 网格约合 1.3–1.9 个单元边长、直径约 2.7–3.7 个：'
            '接触区只跨少量单元，局部冲击应力场没有证明收敛，不能说网格已经够细。'
            '加密是为了让导波能表示损伤，不是把冲击应力算准。',
            '在 0.794 J 下赫兹平均接触压力约 3.6 GPa，超过钢材屈服、远超层合板厚度方向强度，'
            '该能量下"弹性刚球 + 弹性板"的理想化已越出适用范围。',
        ],
        meaning='这一轮既给了"数值致损工况"一个可辩护的选取过程，也把"哪些量可信、哪些只是表示得出来"'
                '划清楚了。三个静默 bug 更是"必须真跑一次"的实证：静态自检全绿也挡不住。',
        figures=[
            ('s6_abaqus_model', '在 Abaqus 里搭出来的实体模型（0.300 J 冲击算例）',
             '左：等轴视图，刚球落在 100×100×2 mm 试件中央，板边能看到铺层分界；'
             '右：正视图。正视图里板只占几十个像素高 —— 这不是图没截好，'
             '而是 2 mm 板厚对 100 mm 边长就是这个比例，也正是"用导波测这种损伤"难的地方。'
             '铺层、界面、刚球与传感器都在同一个实例里，这是后面所有读数所依附的模型。'),
            ('s6_layers', '同一模型的铺层放大（正视图裁切）',
             '从 4000×1200 的正视图里裁出中心 30 mm，8 层铺层读成 8 条清晰的水平线，'
             '刚球压在顶面 —— 与生成器写的 8 层、每层 0.25 mm 一致。'),
            ('s6_impact_animation', '冲击过程的动态云图（U3，0–500 µs）',
             '逐帧从 odb 导出后合成，24 帧，色标固定在 ±1.6e-3 m 且关于零对称，所以颜色可比。'
             '球落下、板被压下、球弹起离开，板继续振荡 —— 冲击结束时板还带着约 0.13 J 的振荡能量，'
             '这正是导波步必须从静止板单独起算的原因。'),
            ('s6_graded_mesh', '面内几何级数加密',
             '左：单元边长沿板长（对数轴），虚线是 A0 波长的 1/10；右：中心区 24 个单元的放大，'
             '可见平滑过渡与相邻比上限。'),
            ('s6_impact_energies', '三档标定与交出去的 footprint',
             '左：分层耗散能（对数轴），省略数据行与显式刚度两种界面律并列；'
             '右：由 ALLDMD 与断裂能反推的等价圆半径区间，虚线标出两档导波算例所用半径。'),
            ('s6_impact_history', '0.300 J 工况的冲击时程',
             '左：接触力（由球的质量乘速度斜率得出），阴影为判为接触的时段。'
             '接触不是一段：球在约 240–290 µs 之间与板分开后又撞了一次，末次分离在 342 µs —— '
             '无阻尼理想化下板会弹回并把球再次接住。'
             '右：冲击点向下挠度与分层耗散（各自刻度；内能 ALLIE 峰值 254 mJ 与它们不同量级，未画）。'),
        ],
    ),
    dict(
        id='stage7', number='七', date='2026-09-21',
        title='导波步建成：传感器布局、两段式、双精度',
        what='同一加密网格上建导波步：9 通道（1 个激励 + 8 个接收），激励为顶面 3 mm 半径压力片、'
             '5 周期汉宁窗 100 kHz 猝发；接收读顶面节点 U3/V3 与顶层单元应变。'
             '损伤以"kissing bond"形式施加：把冲击算出的 footprint 作为界面上只留摩擦、可张开的裂面。',
        why='目标不是成像，而是回答"导波能不能测到落球造成的分层"。'
            '板只有 100 mm 见方，A0 在 100 kHz 的波长约 12.7 mm —— 整板约 8 个波长'
            '（扣掉夹持带后的 80 mm 自由跨度约 6.3 个），'
            '边界反射早到，所以取"短直路径 + 可分离直达波"，而不是成像阵列。',
        basis=[
            '布局依据四条：① 短直路径可分离直达波；② ACT–R2 构成穿透对且损伤落在直线上；'
            '③ R3/R4、R5/R6、R7/R8 是关于 y = 50 的镜像对（激励点也在该面上，网格与损伤均对称）；'
            '④ 全部处于 λ/10 网格区，并按实际边距说明与夹持带的关系 —— '
            '离夹持内缘最近的是 R2（x = 80 mm，距 x = 90 mm 的内缘 10 mm）。',
            '两段式的实测理由：0.300 J 冲击结束时板仍带约 0.13 J 机械能在振荡，低频部分可滤波，'
            '但分层区的高频拍打滤不掉。所以导波步不接在冲击步之后，而是从静止完好板出发、'
            '把 footprint 作为 disbond 施加。',
            '必须双精度：导波位移只有 1e-7 m 量级而板长 0.1 m，两者尺度相差很大，'
            '舍入误差值得单独检查 —— 单/双精度的对称性对照见下一条。',
        ],
        findings=[
            '镜像对自检（无损板必须读得一样）把精度问题量了出来：单精度 12%，double=explicit 后 0.0–0.9%。'
            '12% 与损伤信号同量级，即单精度跑出来的导波结果是在测舍入。',
            '损伤指标刻意报三个数：归一化 RMS 差、相关系数、峰值比。'
            '一个小分层只该表现成一个小变化，合成一个"好看"的单数字会掩盖这一点。',
            '换用显式界面刚度后数值镜像基线降到 0.0012–0.0049（0–90 µs 窗口，V3 归一化 RMS 差）；'
            '这是本模型的数值基线，不是实验电子噪声。'
            '因此小分层的 5.5% / 4.6% 比该基线高 9–46 倍、corr 0.999，指标可采信。',
            '大分层（3.1 mm）使穿透对的相关系数为负（−0.447 / −0.199）、峰值比 0.71–0.75，'
            '即透射波包的波形与相位明显改变，并损失约四分之一幅值；'
            '相关系数为负说明明显负相关，但不能据此说整个波包严格反相 180°。',
        ],
        limits=[
            '导波仍无 PZT、胶层、机电耦合，输出是机械位移不是电压。',
            '0.300 J 档在显式刚度下受损界面是 4 个，而对应导波算例仍按 5 个界面建，'
            '多出的那个界面只有 56 个节点到损伤（偏保守，未重跑）。',
            '频散自检用起点对起点，读数 1219–1448 m/s 对设计 1269 m/s；'
            '0.5 µs 的 history 采样是这套数的不确定度来源（25 mm 路径上即 2.6%）。',
        ],
        meaning='这是课题核心命题（导波能否测到落球损伤）的直接仿真回答。'
                '同时"镜像对免费自检""位移量级决定精度"这类做法本身可以写进方法学。',
        figures=[
            ('s7_abaqus_model', '导波算例的实体模型',
             '与冲击算例同一套网格、铺层与界面，去掉刚球：导波步从静止的完好板出发，'
             '分层以界面上的"可张开、只留摩擦"裂面施加。'),
            ('s7_wave_animation', '导波传播的动态云图（U3，0–130 µs）',
             '俯视，逐帧从 odb 导出后合成，色标固定在 ±3.4e-7 m 且关于零对称，'
             '所以每一帧的颜色都可比。波包从左上方的激励点散开、并在夹持边界反射；'
             '接收点读的就是这批直达波，损伤指标也只在这个窗口内取。'),
            ('s7_wave_frames', '导波云图的四个关键帧（静态）',
             '给纸面阅读与无法播放动画的场合：同一批帧里的四个时刻。'),
            ('s7_sensor_layout', '9 通道布局与两档 disbond 的真实尺寸',
             '左：板、夹持带内缘、激励片与 8 个接收点；右：中心放大到同一比例，'
             '画出 0.8 mm 与 3.1 mm 两个等面积圆 —— 损伤尺度相对板长有多小，一眼可见。'),
            ('s7_wave_waveforms', '接收点的 V3 波形：无损与两档分层',
             '穿透对 R1（过损伤 15 mm）与 R2（30 mm）在 0–90 µs 窗口内的时程，'
             '大分层档的波包形状被明显重塑。'),
            ('s7_wave_floor', '损伤信号与噪声底（对数轴）',
             '灰带是无损基线镜像对的噪声底，两组柱是两档分层的指标。'
             '小档高 9–46 倍，大档高两个量级以上。'),
        ],
    ),
    dict(
        id='stage8', number='八', date='2026-09-21',
        title='稳定性排查与交接链自洽：把不确定度也量化',
        what='无损基线出现"镜像对在晚时差 23–39%"的问题，比小分层的信号还大。'
             '排查后用"显式给出黏聚数据行"治好；随后发现界面刚度会改变冲击分层面积，'
             '于是重跑三档冲击标定、并按新的 footprint 区间重跑两档导波。',
        why='噪声底比信号还大，指标就不可用；而"给不给数据行"是一个必须能写进方法的选择。'
            '更关键的是：交给导波模型的裂面尺寸，与冲击算出来的裂面尺寸必须来自同一套界面律，'
            '否则交接链不自洽。',
        basis=[
            '排查顺序（每条都实测排除）：未见明显全局能量漂移（ETOTAL 相对 6e-6，'
            '但不能据此排除局部数值误差）；不是单精度（双精度下同样出现）；'
            '不是接触域（收到命名面对后此网格上解逐位不变）。特征是逐位可复现、随时间放大、'
            '空间上集中在夹持带内缘 —— 判为弱不稳定模态。',
            '单变量对照：只改 *Cohesive Behavior 数据行。省略时镜像不对称 30 µs 2.07% → 90 µs 23.88%；'
            '给出数据行后（1e12 至 3.28e14 任一取值）为 0.01–1.6%。',
            '两单元受拉探针：默认的表观法向刚度实测为 2.371e13 Pa/m，量级就是铺层尺度（E3/h = 3.28e13）。',
        ],
        findings=[
            '三条机制假设全部被自己的数据否掉：~~默认罚刚度过大~~（更硬 14 倍反而更干净）、'
            '~~静态顺应性控制失稳~~（同表观刚度、两种结果）、'
            '~~指定数据行后刚度进入稳定步长估计~~（本组五种设置报告的初始稳定步长逐位相同 1.22410e-08；'
            '但这只说明打包阶段的初始步长没有随该设置变化，'
            '该比较未支持用初始步长差解释现象，不足以据此下全局机制定论）。'
            '唯一确证的是：决定因素是"给不给数据行"，在已测试的若干取值上都干净。',
            '工程规则：*Cohesive Behavior 一律给数据行，取 2.37e13（复现默认的静态顺应性，'
            '把物理改动压到最小）。噪声底随之降 100–300 倍。',
            '代价被量化：换刚度后三档的损伤耗能与等价面积分别下降约 73%、51%、50%，'
            '而峰值力、挠度、反弹比只动 1–4% —— '
            '面积是近阈值量在极小区域上的积分，对界面刚度远比全局量敏感。'
            '原先选的 1.0 / 3.5 mm 因此落到新反推区间（0.53–0.78 / 2.13–3.13 mm）之外，'
            '按同一规则改取上界 0.8 / 3.1 mm 重跑。',
            '顺带更正两处旧记录：0.100 J 那行的 3.581 mJ 是笔误（复核 odb 应为 0.358 mJ）；'
            '0.300 J 的分离时刻原写"未变"，实为 334.5 → 342.0 µs。',
        ],
        limits=[
            '黏聚失稳的机制未查清，只能给工程规则。',
            'footprint 自带与界面刚度同量级的不确定度（面积约 2 倍），'
            '不能当确定值引用；这里给的是按断裂能换算的等价面积，'
            '不是真实分层几何面积，也不是统计置信区间。',
        ],
        meaning='这一轮的价值在诚实与可核：机制没查清就不写"已解释"；'
                'footprint 有约 2 倍面积的不确定度就明确标注。这些正是论文"不确定度分析"章节的现成材料。',
        figures=[
            ('s8_instability', '图 17　不稳定模态的单变量对照',
             '左：镜像不对称随时间增长，省略数据行时 90 µs 到 23.88%，给定数据行后落到 1.6% 以下；'
             '右：本组五种设置报告的初始稳定步长相同，该比较未支持用初始步长差解释现象。'),
        ],
    ),
]

FIGURES = {
    's1_plate_modal': 'figures/s1_plate_modal.png',
    's2_plate_vs_solid': 'figures/s2_plate_vs_solid.png',
    's2_farfield_convergence': 'figures/s2_farfield_convergence.png',
    's2_sensor_direction': 'figures/s2_sensor_direction.png',
    's3_dispersion_analytic': 'figures/s3_dispersion_analytic.png',
    's3_dispersion_check': 'figures/s3_dispersion_check.png',
    's4_abaqus_speed': 'figures/s4_abaqus_speed.png',
    's4_cross_solver': 'figures/s4_cross_solver.png',
    's4_reduced_integration': 'figures/s4_reduced_integration.png',
    's6_graded_mesh': 'figures/s6_graded_mesh.png',
    's6_abaqus_model': 'figures/s6_abaqus_model.png',
    's6_layers': 'figures/s6_layers.png',
    's6_impact_animation': 'figures/s6_impact_animation.gif',
    's6_impact_energies': 'figures/s6_impact_energies.png',
    's6_impact_history': 'figures/s6_impact_history.png',
    's7_sensor_layout': 'figures/s7_sensor_layout.png',
    's7_abaqus_model': 'figures/s7_abaqus_model.png',
    's7_wave_animation': 'figures/s7_wave_animation.gif',
    's7_wave_frames': 'figures/s7_wave_frames.png',
    's7_wave_waveforms': 'figures/s7_wave_waveforms.png',
    's7_wave_floor': 'figures/s7_wave_floor.png',
    's8_instability': 'figures/s8_instability.png',
}

# Captions written before the numbers were assigned by hand start with "图 N"; the builder
# strips that and writes its own, so the two can no longer disagree.
NUMBERED = re.compile(r'^图\s*\d+\s*[　\s]*')
CHIP = {'通过': 'ok', '拒绝': 'no', '不可行': 'no', '不可用': 'no', '仅诊断': 'note'}

CSS = """
:root { --ink:#1d2025; --muted:#6b7280; --line:#e3e6ea; --brand:#6b4bd6; --bg:#ffffff;
        --soft:#f6f7f9; }
* { box-sizing: border-box; }
body { margin:0; background:var(--soft); color:var(--ink);
       font-family:"Microsoft YaHei","PingFang SC","Segoe UI",sans-serif;
       font-size:15px; line-height:1.75; }
.wrap { display:flex; max-width:1400px; margin:0 auto; gap:28px; padding:24px; }
nav { position:sticky; top:24px; align-self:flex-start; width:264px; flex:none;
      background:var(--bg); border:1px solid var(--line); border-radius:10px; padding:18px 16px;
      max-height:calc(100vh - 48px); overflow:auto; font-size:13.5px; }
nav h2 { font-size:14px; margin:0 0 10px; color:var(--muted); font-weight:600; }
nav ol { margin:0 0 16px; padding-left:18px; }
nav li { margin:5px 0; }
nav a { color:var(--ink); text-decoration:none; }
nav a:hover { color:var(--brand); }
main { flex:1; min-width:0; }
header { background:var(--bg); border:1px solid var(--line); border-radius:10px;
         padding:26px 30px; margin-bottom:20px; }
h1 { font-size:24px; margin:0 0 8px; }
.sub { color:var(--muted); font-size:13.5px; }
section { background:var(--bg); border:1px solid var(--line); border-radius:10px;
          padding:24px 30px 8px; margin-bottom:20px; }
section h2 { font-size:19px; margin:0 0 4px; border-left:4px solid var(--brand);
             padding-left:12px; }
.meta { color:var(--muted); font-size:13px; margin:0 0 16px 16px; }
h3 { font-size:15px; margin:20px 0 6px; color:var(--brand); }
p, ul { margin:8px 0; }
ul { padding-left:22px; }
li { margin:6px 0; }
figure { margin:20px 0 26px; }
figure img { width:100%; border:1px solid var(--line); border-radius:8px; background:#fff; }
figcaption { font-size:13.5px; color:var(--muted); margin-top:8px; }
figcaption b { color:var(--ink); }
table { border-collapse:collapse; width:100%; font-size:13.5px; margin:12px 0; }
th, td { border:1px solid var(--line); padding:7px 10px; text-align:left; vertical-align:top; }
th { background:var(--soft); font-weight:600; }
caption { caption-side:top; text-align:left; font-size:14px; font-weight:600;
          padding:0 0 8px; color:var(--ink); }
.tnote { font-size:13px; color:var(--muted); margin:6px 0 18px; }
.chip { display:inline-block; padding:1px 10px; border-radius:999px; font-size:12.5px;
        border:1px solid var(--line); white-space:nowrap; }
.chip-ok { background:#e6f4ef; color:#1d6b58; border-color:#bfe0d5; }
.chip-no { background:#fbeade; color:#8c4a1c; border-color:#f0d3bb; }
.chip-note { background:var(--soft); color:var(--muted); }
.callout { background:var(--soft); border-left:3px solid var(--brand); border-radius:0 8px 8px 0;
           padding:10px 16px; margin:14px 0; font-size:14px; }
.limit { background:#fdf6ef; border-left:3px solid #c2703a; border-radius:0 8px 8px 0;
         padding:10px 16px; margin:14px 0; font-size:14px; }
code { background:var(--soft); padding:1px 5px; border-radius:4px;
       font-family:Consolas,monospace; font-size:13px; }
.idx { columns:2; column-gap:32px; }
"""


def embed(relative):
    with open(os.path.join(HERE, relative), 'rb') as handle:
        return base64.b64encode(handle.read()).decode('ascii')


def listing(items):
    return '<ul>' + ''.join('<li>%s</li>' % item for item in items) + '</ul>'


def figure_lookup():
    """Number the figures in document order, and list them the same way.

    The captions used to carry their own numbers in the text, so inserting or dropping one
    figure left every later number stale. They are assigned here instead, and any prefix
    already present in the stored caption is stripped.
    """
    numbers, order = {}, []
    for stage in STAGES:
        for entry in stage['figures']:
            numbers[entry[0]] = len(numbers) + 1
            order.append(entry)
    return numbers, order


def figure_html(entry, number):
    key, caption, detail = entry
    title = NUMBERED.sub('', caption)
    path = FIGURES[key]
    # The animations are GIFs, and a data URI that declares image/png for them is a lie the
    # browser is not obliged to see through.
    mime = 'image/gif' if path.endswith('.gif') else 'image/png'
    return ('<figure id="%s"><img alt="%s" src="data:%s;base64,%s">'
            '<figcaption><b>图 %d　%s</b>　%s</figcaption></figure>'
            % (key, title, mime, embed(path), number, title, detail))


def table_html(spec, number):
    """A capability matrix belongs in a table, not in a hand drawn figure.

    It was drawn in matplotlib first, and the axis-free patches, mixed coordinate systems
    and long reason strings came out misaligned and clipped. Text in a table is text.
    """
    head = ''.join('<th>%s</th>' % cell for cell in spec['headers'])
    rows = []
    for row in spec['rows']:
        cells = ''
        for index, cell in enumerate(row):
            if index == 1:
                cells += ('<td><span class="chip chip-%s">%s</span></td>'
                          % (CHIP.get(cell, 'note'), cell))
            else:
                cells += '<td>%s</td>' % cell
        rows.append('<tr>%s</tr>' % cells)
    return ('<table id="table%d"><caption>表 %d　%s</caption><thead><tr>%s</tr></thead>'
            '<tbody>%s</tbody></table><p class="tnote">%s</p>'
            % (number, number, spec['title'], head, ''.join(rows), spec['detail']))


def build():
    numbers, order = figure_lookup()
    total = len(order)
    tables = sum(1 for stage in STAGES if stage.get('table'))
    toc = ''.join('<li><a href="#%s">%s、%s</a></li>' % (s['id'], s['number'], s['title'])
                  for s in STAGES)
    figure_index = ''.join('<li><a href="#%s">图 %d　%s</a></li>'
                           % (entry[0], numbers[entry[0]], NUMBERED.sub('', entry[1]))
                           for entry in order)

    body = []
    table_number = 0
    for stage in STAGES:
        figures = ''.join(figure_html(entry, numbers[entry[0]]) for entry in stage['figures'])
        table = ''
        if stage.get('table'):
            table_number += 1
            table = table_html(stage['table'], table_number)
        body.append(
            '<section id="%s"><h2>%s、%s</h2><p class="meta">%s</p>'
            '<h3>做了什么</h3><p>%s</p>'
            '<h3>为什么这么做</h3><p>%s</p>'
            '<h3>依据是什么</h3>%s'
            '<h3>实测结果</h3>%s'
            '<div class="limit"><b>必须一并说明的保留：</b>%s</div>'
            '<h3>对课题的意义</h3><p>%s</p>'
            '%s%s</section>'
            % (stage['id'], stage['number'], stage['title'], stage['date'], stage['what'],
               stage['why'], listing(stage['basis']), listing(stage['findings']),
               listing(stage['limits']), stage['meaning'], table, figures))

    html = (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<title>阶段仿真实现汇报</title><style>%s</style></head><body><div class="wrap">'
        '<nav><h2>目录</h2><ol>%s</ol><h2>图表索引</h2><ol class="idx">%s</ol>'
        '<h2>数据出处</h2><p style="font-size:12.5px;color:#6b7280">'
        '所有数字取自仓库内已提交的指标 JSON、由 odb 导出的时程，以及 PROJECT_HANDOFF.md 的数值实测／算例记录（本项目仿真结果部分）。'
        '数据图由 review/build_stage_figures.py 生成，时程由 review/export_history.py 导出，'
        'Abaqus 模型与云图由 review/export_abaqus_views.py 从 odb 直接截取。'
        '文献实验图由 review/export_reference_figures.py 按各篇 PDF 的图注位置裁取，'
        '原始论文与 odb 一样不在仓库内。'
        '本文件不含新的测量；review/ 目录当前仍未纳入版本跟踪，'
        '不能说整份汇报已提交、可从远端完整恢复。</p></nav>'
        '<main><header><h1>阶段仿真实现汇报</h1>'
        '<p class="sub">落球冲击 → 损伤 → 导波检测：八个阶段，共 %d 张配图与 %d 张表，'
        '其中 Abaqus 侧的动画由 odb 逐帧导出后合成。'
        '每节按"做了什么 / 为什么这么做 / 依据是什么 / 实测结果 / 保留 / 对课题的意义"排列，'
        '可直接对照审阅。</p></header>%s'
        '<section><h2>附录：引用这些数字时必须一并说明的三条</h2>'
        '<div class="callout"><b>黏聚失稳的机制未查清</b>：三条机制假设都被实测否掉，'
        '但"一律给 *Cohesive Behavior 数据行"这条工程规则是可靠的。</div>'
        '<div class="callout"><b>footprint 自带与界面刚度同量级的不确定度</b>：'
        '换刚度后三档的损伤耗能与等价面积分别下降约 73%%、51%%、50%%，不能当确定值引用；'
        '这是按断裂能换算的等价面积，不是真实分层几何面积，也不是统计置信区间。</div>'
        '<div class="callout"><b>冲击应力场未收敛</b>：接触半径 0.2–0.28 mm 约合 1.3–1.9 个单元边长'
        '（直径 2.7–3.7 个），接触区只跨少量单元；'
        '加密是为了让导波能表示损伤，不是把冲击应力算准。</div>'
        '</section>'
        '</main></div></body></html>'
        % (CSS, toc, figure_index, total, tables, ''.join(body)))

    with open(OUT, 'w', encoding='utf-8') as handle:
        handle.write(html)
    print('wrote %s (%.1f MB, %d figures, %d table)'
          % (OUT, os.path.getsize(OUT) / 1e6, total, tables))


if __name__ == '__main__':
    build()
