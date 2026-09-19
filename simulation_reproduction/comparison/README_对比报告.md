# 对比分析

阅读 [论文与仿真逐项对比分析](论文与仿真逐项对比分析.md)。本目录包含审计脚本、审计JSON及本项目绘制的图表。

本机完整版位于 `D:/毕设知识库/simulation_reproduction/comparison/论文与仿真逐项对比分析.html`，可离线阅读18张图和9张表。原论文页图及包含这些页图的HTML仅保存在本机，GitHub阅读版在相应位置标注本地附件名。

`audit_metrics.json` 和 `ae_window_records.json` 是完成审计时的结果快照，不代表重新运行后的最新结果。审计读取本机既有NPZ/JSON；仓库未包含全部求解输出，所以仅克隆仓库不能直接完成全部审计。

在已有论文、`results/`、`inspection/`及`guided_wave_v2/`求解结果的本机目录中：

```powershell
Set-Location 'D:\毕设知识库\simulation_reproduction\comparison'
$py = 'C:\Users\29795\AppData\Local\Programs\Python\Python313\python.exe'
& $py audit.py
& $py build_report.py
```

脚本还依赖本地论文页图P*-p*.png。审计不会修改旧仿真代码。生成脚本会更新图与JSON，正文包含人工分析；若输入改变，必须人工/由后续助手重新核对正文数字与结论。

新对话请优先阅读仓库根目录 `PROJECT_HANDOFF.md`。
