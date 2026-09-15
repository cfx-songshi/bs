# bs

毕设论文实验的数值复现与主动导波参考仿真代码。

**新对话先读：[项目交接文档](PROJECT_HANDOFF.md)。** 包含项目目标、实际文件位置、已完成工作、已知错误、模型边界、复算命令和可复制提示词。

**分析报告：[论文与仿真逐项对比分析](simulation_reproduction/comparison/论文与仿真逐项对比分析.md)**。审计脚本与指标见 [对比分析说明](simulation_reproduction/comparison/README_对比报告.md)。本机完整HTML含原论文图页，仓库阅读版保留分析和本项目绘图。

## 目录

- `simulation_reproduction/`：AE 到达时间、定位、简化板动力响应、迁移学习及其他方法实验。
- `simulation_reproduction/guided_wave_v2/`：T300/F593 二维正交各向异性有限元导波模型，健康与中面分层对照。
- 原始论文、第三方依赖、缓存和大体积计算结果不纳入版本管理。

## 本机运行

现有项目位于 `E:\毕设知识库`，依赖已放在 `simulation_reproduction/vendor`。在 PowerShell 中执行：

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

若运行克隆后的目录，请把 `Set-Location` 改成克隆目录中的对应路径。Python 路径为现有电脑的运行环境路径，在其他电脑上需配置自己的 Python，并参考依赖清单安装所需库。程序包含对原 E 盘依赖目录的引用。

旧版完整运行命令和输入要求见 [复现说明](simulation_reproduction/README_复现说明.md)。`prepare_plan.py` 需要另外提供原始论文目录；仓库不分发论文文件。生成报告前应先完成相应求解。

## 模型与代码状态

本次导入保留本地源码版本，不是原论文作者提供的代码。旧版部分结果来自合成信号或参数化示意，不代表实物实验复现。旧循环压力模块存在待复核的压力输入值，不能直接用于实验结论。

新版导波输出是二维等效力激励下的机械位移，不是完整三维加筋板或 PZT 电压。详细参数、验证范围及复算顺序见 [参数来源与复现边界](simulation_reproduction/guided_wave_v2/参数来源与复现边界.md)。
