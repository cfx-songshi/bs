# 论文实验仿真复现包

本包依据项目根目录的 7 篇研究论文和开题报告制作，排除了“参考文献”文件夹。

**先阅读 `复现实验报告.html` 或 `复现实验报告.md`。** 报告按“原文实验—实际实现—补充假设—运行结果—尚未复现内容”逐项说明。结果全部由代码运行产生；合成数据、等效模型和拟合示意不等于原文实物试验复现。

## 当前已执行

- 低信噪比 AE：1,500 条合成波形，4 种拾取方法；另做噪声类型诊断。
- 四传感器无预标定波速定位：7 档误差，每档 100,000 次；50×50×100 次位置敏感性实验；各向异性失配和首峰插值实验。
- 蜂窝夹层板的等效薄板动力响应：16 个观测点、4 档模态截断；不是显式蜂窝 ABAQUS 模型。
- 小样本 CNN-DANN：源域 200、目标域 16/64/104/144、独立测试 80；3 个随机种子，共训练 39 个模型。
- UGW 的 TCA-ELM 局部算法复现、两篇压阻传感论文的参数锚定示意、多传感器 Kalman 滤波器组故障注入。
- 数值检查及梯度反转检查。

## 一键运行（本机 PowerShell）

```powershell
Set-Location 'D:\毕设知识库\simulation_reproduction'
& 'C:\Users\29795\AppData\Local\Programs\Python\Python313\python.exe' run.py --experiment all --seeds 3 --mc 100000 --epochs 80
```

本机没有 `vendor` 目录，依赖已装在上面这个 Python 3.13.15 的 site-packages 中，因此需要传入一个不存在的 vendor 路径来使用它。不会写入原始论文。

若使用自己的 Python，建议新建虚拟环境，按 `requirements-lock.txt` 安装所需库：

```powershell
python run.py --vendor './no-vendor' --experiment all --seeds 3 --mc 100000 --epochs 80
```

单独运行：将 `--experiment` 改为 `checks`、`ae`、`localization`、`plate`、`gear`、`joints`、`faults` 或 `transfer`。

额外诊断和建模清单：

```powershell
& 'C:\Users\29795\AppData\Local\Programs\Python\Python313\python.exe' ae_ablation.py
& 'C:\Users\29795\AppData\Local\Programs\Python\Python313\python.exe' prepare_plan.py --vendor './no-vendor' --papers '..'
& 'C:\Users\29795\AppData\Local\Programs\Python\Python313\python.exe' build_report.py
```

`prepare_plan.py` 生成的 1,620 条 ABAQUS 工况是**待计算工况**，不是已经完成的有限元结果。没有把它们计入实际运行样本数。

## 文件索引

| 文件 | 用途 |
|---|---|
| `run.py` | 实验入口、波形生成、绘图、指标统计 |
| `core.py` | AIC、小波、无波速定位、TCA、ELM 数值实现 |
| `transfer.py` | PyTorch CNN、梯度反转、训练/测试划分 |
| `ae_ablation.py` | 固定算法的噪声类型诊断 |
| `prepare_plan.py` | 原论文哈希、FE 参数表、工况矩阵、数据接口 |
| `results/*summary.json` | 机器可读指标；不需要依赖本报告重新统计 |
| `results/*trials.json` | 逐样本/逐随机种子结果 |
| `results/*.npz` | 保存的波形、标签、位置及数据划分 |
| `results/*.pt` | 目标域 64 个样本、seed=0 的三个网络权重 |
| `results/abaqus_reference_spec.json` | 有限元原文参数和待核实项 |
| `results/hsp_1620_planned_cases.json` | 90 个位置 × 18 个工况，标记为 planned_not_solved |
| `results/source_inventory.json` | 8 份源文件及 SHA-256 |
| `source_text/` | 原文按 PDF 页码提取的文本，公式应结合原 PDF 核对 |

`.npz` 示例：

```python
import numpy as np
d = np.load('results/transfer_dataset_seed0.npz')
print(d['source'].shape)  # (200, 1, 4, 300)
print(d['test'].shape)    # (80, 1, 4, 300)
```

## 使用边界

这里的“复现”包含不同层次。到达时间算法与定位方程可直接审查；CNN 网络有明确补充设计；薄板是简化物理模型；压阻曲线是现象模型。尚未获得原作者波形、CFRP 完整材料/损伤参数、传感器传递函数及原始训练划分，不能宣称已复现原论文的实测准确率、材料破坏过程或仿真到实测迁移。

数值结果中存在失败和负迁移，均保留。重新运行会覆盖 `results` 中同名生成文件；请在需要保留多次实验时先复制整个结果目录。
