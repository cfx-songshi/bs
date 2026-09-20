# 对比分析

阅读 [论文与仿真逐项对比分析](论文与仿真逐项对比分析.md)。本目录包含审计脚本、审计JSON及本项目绘制的图表。

本机 HTML 版（`论文与仿真逐项对比分析.html`，18张图和9张表）由 `build_report.py` 生成，它还需要 4 张论文页图（`P3-p11.png` 等）。这些图只存在于旧电脑，本机缺 `inspection/` 目录，因此截至 2026-09-20 本机尚未生成该 HTML 及 `source_manifest.json`、`analysis_manifest.json`。GitHub 阅读版在相应位置标注本地附件名。

`audit_metrics.json` 和 `ae_window_records.json` 是结果快照，当前版本对应 2026-09-20 的本机重跑（`results/` 由 `run.py --experiment all` 重建）。审计读取本机既有 NPZ/JSON；仓库未包含全部求解输出，所以仅克隆仓库不能直接完成全部审计。其中 CNN 迁移支路受运行环境影响（torch 版本、CPU 指令路径），换环境重跑会得到不同数字，详见正文第 6 节「跨环境可复现性」。

在已有论文、`results/`、`inspection/`及`guided_wave_v2/`求解结果的本机目录中：

```powershell
Set-Location 'D:\bs_thesis\simulation_reproduction\comparison'
$py = 'C:\Users\29795\AppData\Local\Programs\Python\Python313\python.exe'
& $py audit.py
& $py build_report.py
```

脚本还依赖本地论文页图P*-p*.png。审计不会修改旧仿真代码。生成脚本会更新图与JSON，正文包含人工分析；若输入改变，必须人工/由后续助手重新核对正文数字与结论。

新对话请优先阅读仓库根目录 `PROJECT_HANDOFF.md`。
