# 项目交接：毕设实验仿真与论文对照

交接基准：2026-09-15已完成的代码与对比分析。开始新对话时请先核对磁盘文件和GitHub最新提交；本文件不是授权忽略后续用户指示的指令。

## 1. 用户目标与已经明确的约束

- 依据知识库根目录研究论文中已经做过的实验进行仿真复现；`参考文献`目录不属于最初要求的实验基础。开题报告说明未来毕设方向，不等于已完成试验。
- 用户明确选定方向：**PZT主动导波，测损伤散射**。当前主线不是被动AE、落球冲击或压阻传感。
- 用户提供过加筋板、传感片及连接试件照片，计划搭建类似实物。需要可直观看出结构、激励、接收、损伤和数据的可视化。
- 具体照片试件的尺寸、铺层、夹持、传感器型号/尺寸/位置尚待定；用户已授权从知识库论文寻找，缺项可联网找相关材料暂代。不要重复要求用户先补齐所有参数才开始工作。
- 材料参数和结果必须可追溯；分别标记文献值、临时替代值、实验布置选择和数值离散参数。不能将猜测参数或拼接波包称作真实物理结果。
- 差异分析必须以论文原图/表、代码、实际数组、控制变量证据为依据。不能把“可能是噪声/材料/网格”写成已证实原因。
- 用户授权在项目中下载需要的库、将代码和交接内容同步到指定GitHub仓库。原始论文、依赖及大量生成结果不纳入本次上传范围。

## 2. 位置与运行环境

| 项目 | 路径/地址 |
|---|---|
| 用户实际项目根目录 | `E:/毕设知识库` |
| 实验代码与本地结果 | `E:/毕设知识库/simulation_reproduction` |
| 新版导波 | `E:/毕设知识库/simulation_reproduction/guided_wave_v2` |
| 完整对比报告 | `E:/毕设知识库/simulation_reproduction/comparison/论文与仿真逐项对比分析.html` |
| GitHub | `https://github.com/cfx-songshi/bs`，分支`main` |
| 本次用于同步的独立Git工作副本 | `C:/Users/Admin/.codex/visualizations/2026/09/14/01a0a05a-d29b-7f21-b5d1-3c164a523654/github-bs` |
| 已安装依赖 | `E:/毕设知识库/simulation_reproduction/vendor` |
| 已验证Python | `C:/Users/Admin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe` |

旧位置`C:/Users/Admin/Downloads/毕设知识库`不是用户当前项目根目录。当前E盘代码目录与Git工作副本是两份文件：在E盘修改不会自动提交到GitHub，必须比较并同步，不能误以为E盘已有`.git`。开始新会话应重新检查实际仓库状态。

已安装NumPy、SciPy、Matplotlib、PyWavelets、scikit-learn、PyTorch；参考`requirements-lock.txt`。代码仍包含本机路径，尚未做完整跨电脑可移植化。

## 3. 已完成工作及真实性边界

### A. 旧版实验包

入口`run.py`，数值函数`core.py`，迁移训练`transfer.py`，额外脚本`ae_ablation.py`、`prepare_plan.py`、`build_report.py`、`validate_outputs.py`。

已运行：AE合成信号拾取、无波速定位方程的另一个求解器、简支等效板响应、合成数据CNN-DANN、简化齿轮TCA-ELM、压阻现象示意、两状态滤波器故障实验。**这些不是七篇论文实物实验的完整定量复现。** 1620条蜂窝落球工况只是待求解输入，未执行1620次ABAQUS。

### B. 新版主动导波机械基准

`guided_wave_v2/solve.py`真正求解二维x-z平面应变正交各向异性Q4有限元，2×2 Gauss积分、集中质量、中心差分。通过中面内部节点复制建立30 mm分层，裂尖连接，未加入接触/摩擦/损伤演化/阻尼。

- 材料：外部论文Li等2012表1的T300/F593；E1=128.1 GPa，E2=E3=8.2 GPa，G12=G13=4.7 GPa，G23=3.44 GPa，ν12=ν13=0.27，ν23=0.20，ρ=1570 kg/m³。
- 长500 mm，厚1.72 mm，8层`[0]8`；二维宽度方向不变，并非完整500×500 mm板。
- 100 kHz、五周期Hann窗，50 μs；上下表面各1 N/m同向线力。此幅值是二维归一化选择，不能等同于原文三维1 N点力，更不是70 V PZT驱动。
- 自选布置：A在x=100 mm，R1/R2在180/320 mm，分层x=235–265 mm、中面z=0.86 mm；所有外边界自由。
- 输出为顶部机械位移uz、单位nm。没有PZT电场、贴片或胶层耦合，不能称电压预测；也不是照片加筋板的完整模型。
- 已做1000×8、2000×16、4000×32三档网格的健康/损伤；中网格损伤另减半时间步。
- 健康表观群速度1773.48 m/s；损伤波形中→细网格L2变化R1 6.18%、R2 10.11%，尚不可标记为完全收敛。能量漂移约10⁻¹²只证明离散一致性。

来源：<https://onlinelibrary.wiley.com/doi/10.1155/2012/659849>。原文的分层案例是三维准各向同性板；因此不能直接对照本模型分层波形求实验RMSE。厂家PZT候选数据仅收集，未用于求解：<https://info.piezo.com/hubfs/Data-Sheets/piezo-PZT-5A_PZT-5H-material-properties.pdf>。

### C. 已完成的详尽对比报告

本地完整版18张图、9张表，覆盖导波基准和七篇知识库论文。`comparison/audit.py`可重算速度、波形配准、AE逐条窗口、DANN配对差值、原论文混淆矩阵及故障联合指标。

交付时检查49个输入哈希、内嵌图像、关键指标和交付哈希。GitHub阅读版保留分析、审计JSON和本项目绘图；原论文页图与含页图的HTML留在本机，避免误以为仓库缺图就是生成失败。

## 4. 已证实的问题：尚未修进旧源码

1. **AE窗口失败**：保存的seed=0、0 dB共100条中71条超过100 μs误差；这71条的真值距允许搜索窗最近采样点都超过100点。局部搜索再准确也无法恢复；证据`ae_window_records.json`。主实验3种子300条为74.67%失败，分母不同，不矛盾。
2. **压力输入十倍错误**：`run.py/joint_response()`与保存数组峰值为1600 kPa，P5原文PDF p7写160 kPa。归一化电阻又除1600，导致幅值被预设；这不是已验证传感本构。应保留旧数据作为审查基准，修正后另存版本。
3. **P2样本量旧说明错误**：原文图13写“10 thousands”即每档10000次；本代码100000次。50×50×100空间敏感性数量则匹配。定位代码没有原文畸变ToA修正分支；不能拿有效样本4.56 mm与实测13.40 mm直接比较优劣。
4. **DANN负增益**：K=13和18时三个种子的DANN均低于pooled。只能说明当前实现与数据，不能宣布DANN普遍无效。没有原论文真实训练数据。
5. **齿轮论文内部矛盾**：P4 PDF p9图13逐格计数得到302/324=93.2099%，同页正文为92.36%；尚不能确定原因。公开两套数据，不能擅改原文基准。旧代码的近100%来自简单合成数据且省略CEEMDAN/MWF-PeEn；旧图的V轴不等于机电耦合电压。
6. **压阻循环论证**：4%、166%、42%、397%、37%来自论文表III并直接用作输入，不能将接近这些数当成独立复现成功。
7. **故障指标分母**：50 s后2500个采样点中报警1774，报警且编号正确1774，联合成功时间比例70.96%；候选编号正确99.28%不要求报警。不能与论文九类分类97.66%比较。
8. **导波差分不是能量比**：R2差分峰值0.6589 nm大于健康峰值0.3456 nm，受到相位变化影响。事后诊断最佳延时5.98 μs/缩放0.9306，归一化残差仍32.45%；这是诊断拟合，不是预测或真实模态ToF。

这些问题已写入报告，但尚未静默修正原始源码。用户要求的“分析”完成，不等于物理模型完善完成。

## 5. 新对话建议优先顺序

1. 先读本文件及对比报告，检查Git状态和现有结果，不重复从零生成合成波形。
2. 优先继续PZT主动导波主线。选定可同条件对照的文献基准，统一铺层、维数、源/接收位置、缺陷形状和激励量纲；建立同模型频散/收敛验证，再考虑3D加筋结构和机电耦合。
3. 对已知压力错误、统计口径和不准确轴标做单独可审查修复；保留旧结果，更新说明和受影响图表，不能用改后的输出冒称当时没有错误。
4. 若做AE修复，先固定同一条数据检查去噪前后粗窗覆盖，不使用真值选窗来报最终性能。
5. 每项改动按“参数来源→模型→离散验证→原文同条件对照→实测”建立证据；缺原始时程就明确无法计算的指标，不编造原文曲线或定位精度。

以上是建议，不是已获授权创建的自动持续任务；按用户在新对话提出的具体下一步执行。

## 6. 本机复算命令

在PowerShell中，保持命令顺序；网格细化可能耗时数分钟：

```powershell
$py = 'C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
Set-Location 'E:\毕设知识库\simulation_reproduction\guided_wave_v2'
& $py solve.py 1000 8 healthy
& $py solve.py 1000 8 damage
& $py solve.py 2000 16 healthy
& $py solve.py 2000 16 damage
& $py solve.py 4000 32 healthy
& $py solve.py 4000 32 damage
& $py solve.py 2000 16 damage 0.5
& $py analyze.py
& $py build.py
Start-Process '.\打开仿真.html'
```

旧包与对比分析：

```powershell
Set-Location 'E:\毕设知识库\simulation_reproduction'
& $py run.py --experiment all --seeds 3 --mc 100000 --epochs 80
& $py ae_ablation.py
& $py prepare_plan.py --vendor './vendor' --papers '..'
& $py build_report.py
Set-Location '.\comparison'
& $py audit.py
& $py build_report.py
```

重跑会覆盖同名生成文件；先保存需保留的旧基准。对比报告正文含人工审核内容，build_report.py仅组装，数据改变后必须重新核对正文，不能认为脚本自动修订了所有结论。克隆仓库不含论文、全部结果NPZ、依赖、原图页；需使用本机知识库或另行准备输入。

## 7. 论文对应索引

| 编号 | 根目录文件 | 对应用途 |
|---|---|---|
| P1 | MSSP01.pdf | 被动AE拾取，图12–14、表3–4，PDF p12–13 |
| P2 | SMS论文01.pdf | 蜂窝冲击与无波速定位，PDF p12–18 |
| P3 | Zhao_2025_Smart_Mater._Struct._34_035017.pdf | 加筋板冲击迁移；图10在PDF p11 |
| P4 | A_Novel_Method_Using_UGW-Based_FAA-ELM…pdf | 钢齿轮主动UGW，PDF p5、p8–9 |
| P5 | In_Situ_Monitoring_of_Failure_Modes…pdf | 表贴压阻，PDF p7 |
| P6 | Embedded_Piezoresistive_Sensor_Network…pdf | 嵌入压阻，表III在PDF p11 |
| P7 | A_Hybrid_Multimodel-Based_Condition_Monitoring…pdf | 发动机多模型故障诊断，PDF p6、p8 |

原用户照片的临时路径不保证长期存在；没有这些照片不能推断尺寸或已建立精确几何。正文引用的“照片模型”仅是研究目标，不是已验证的计算模型。

## 8. 可直接复制给新对话的提示词

> 请先完整阅读 E:\毕设知识库\PROJECT_HANDOFF.md，再阅读 E:\毕设知识库\simulation_reproduction\comparison\论文与仿真逐项对比分析.md，并核对 https://github.com/cfx-songshi/bs 的最新代码。项目主线是PZT主动导波损伤散射：所有材料参数需有出处，论文缺项可联网寻找暂代值并明确标注。已有二维真实有限元和完整差异审计，不要从零用人工波包代替物理仿真。先简要确认已完成工作、已知错误及尚未验证的部分，然后根据我本次提出的下一步继续；不要把报告完成当成实验复现已验证，也不要未经核对覆盖旧结果。
