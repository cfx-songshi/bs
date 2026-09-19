# bs

毕设论文实验的数值复现与主动导波参考仿真代码。

**新对话先读：[项目交接文档](PROJECT_HANDOFF.md)。** 包含项目目标、实际文件位置、已完成工作、已知错误、模型边界、复算命令和可复制提示词。

**分析报告：[论文与仿真逐项对比分析](simulation_reproduction/comparison/论文与仿真逐项对比分析.md)**。审计脚本与指标见 [对比分析说明](simulation_reproduction/comparison/README_对比报告.md)。本机完整HTML含原论文图页，仓库阅读版保留分析和本项目绘图。

## 新增：实物碳板落球冲击机械基准

已按500×400×2 mm碳纤维板、PZT-5A名义测点和P2周边框架夹持路线建立独立的[impact_v1](simulation_reproduction/impact_v1/README.md)。包含实际运行的Rayleigh–Ritz薄板与落球接触求解、空间/时间验证、假设敏感性、[计算报告](simulation_reproduction/impact_v1/冲击仿真结果.html)及[缺失数据获取清单](simulation_reproduction/impact_v1/缺失数据与获取方法.md)。

这是未实物标定的机械代理模型，局部接触力与原始应变仍未充分空间收敛；不是PZT电压、损伤预测或3D有限元。旧版代码和审计结果保留。

## 新增：三维落球冲击模型

已建立 [impact_3d_v1](simulation_reproduction/impact_3d_v1/README.md)：八节点六面体显式有限元，四分之一对称几何，分两级 —— 局部细化子模型用刚球单边非穿透接触（每步解LCP，接触力与压力分布由解得出）给出力时程，均匀全局模型由该力时程驱动读出16个传感器（4×4，布置依据P2论文）的应变。

已验证：材料刚度与impact_v1一致到0.045%、一阶频率单调从上方收敛（+1.7%）、局部模型网格1.7%与时间步1%收敛、远场网格与时间步双重收敛（同网格换步长一致到0.01%）、能量漂移1e-5。**结论：impact_v1的薄板局部量不可信**（峰值接触力高估5.1倍、冲击点位移低估2.8倍）；**传感器方向依赖已量化**（同一贴片沿冲击方向与沿轴向差3.5倍）。仍是机械代理模型，不是PZT电压。

## 目录

- `simulation_reproduction/`：AE 到达时间、定位、简化板动力响应、迁移学习及其他方法实验。
- `simulation_reproduction/guided_wave_v2/`：T300/F593 二维正交各向异性有限元导波模型，健康与中面分层对照。
- `simulation_reproduction/impact_v1/`：500×400×2 mm 碳板落球冲击的 Rayleigh–Ritz 薄板与 Hertz 接触求解。
- `simulation_reproduction/impact_3d_v1/`：同工况的三维六面体有限元，局部细化子模型＋全局传感器响应。
- `simulation_reproduction/study_final/`：impact_v1 的空间/时间收敛与单因素研究结果。
- 原始论文、第三方依赖、缓存和大体积计算结果不纳入版本管理。

## 本机运行

本机项目位于 `D:\毕设知识库`，根目录自身就是git仓库（远端 `https://github.com/cfx-songshi/bs`，分支 `main`）。依赖已按 `requirements-lock.txt` 装进 Python 3.13.15 的 site-packages，本机没有 `simulation_reproduction/vendor` 目录。在 PowerShell 中执行：

```powershell
$py = 'C:\Users\29795\AppData\Local\Programs\Python\Python313\python.exe'
Set-Location 'D:\毕设知识库\simulation_reproduction\guided_wave_v2'
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

落球冲击（当前主线）：

```powershell
Set-Location 'D:\毕设知识库\simulation_reproduction\impact_v1'
& $py solve_impact.py --order 22 --out results/my_run
```

若在其他电脑运行，请自行安装 Python 并参考 `requirements-lock.txt` 安装所需库，同时把 `Set-Location` 改成实际路径。程序仍包含旧电脑的绝对路径引用（例如原来的 `vendor` 目录），尚未完成跨电脑可移植化。

旧版完整运行命令和输入要求见 [复现说明](simulation_reproduction/README_复现说明.md)。`prepare_plan.py` 需要另外提供原始论文目录；仓库不分发论文文件。生成报告前应先完成相应求解。

## 模型与代码状态

本次导入保留本地源码版本，不是原论文作者提供的代码。旧版部分结果来自合成信号或参数化示意，不代表实物实验复现。旧循环压力模块存在待复核的压力输入值，不能直接用于实验结论。

新版导波输出是二维等效力激励下的机械位移，不是完整三维加筋板或 PZT 电压。详细参数、验证范围及复算顺序见 [参数来源与复现边界](simulation_reproduction/guided_wave_v2/参数来源与复现边界.md)。
