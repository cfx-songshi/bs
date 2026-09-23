# 交付入口：每个仿真一个汇总 GIF

**共 130 个算例汇总 GIF，位置：`D:\bs_thesis\review\simulation_gifs_20260923\00_by_simulation`。**

优先使用本目录；`case_manifest.json` 给出每个汇总 GIF 对应的分段、来源、限制和封面。`index.html` 是汇总浏览目录。原分段文件仍保留，详见 `clips_gallery.html` 与 `manifest.json`。

同一 ODB 的分析步、同一算例目录的场数据与响应曲线按段合并；段落标题标明来源与分析步。不同段可能从自身 t=0 开始，合并不是重新求解，也不表示连续载荷历史。不同能量、网格、预置损伤参数不合并。由同一 ODB 导出的旧波场展示只在来源匹配明确时并入该算例。

给其他 agent 的指令可直接复制：

> 请先阅读 D:\bs_thesis\PROJECT_HANDOFF.md 和 D:\bs_thesis\review\simulation_gifs_20260923\README_PPT_HANDOFF.md，从 D:\bs_thesis\review\simulation_gifs_20260923\case_manifest.json 选择 GIF 与 PNG 制作汇报 PPT。优先当前冲击和修正半径导波，保留数值来源与未解决问题；不将历史对照、未完成片段或合成数据当作已验证主线结论。

| 分类 | 汇总 GIF 数 |
|---|---:|
| 01_current_impact | 4 |
| 02_current_wave | 3 |
| 20_historical | 26 |
| 30_abaqus_validation | 11 |
| 40_material_probes | 20 |
| 50_workflow_tests | 20 |
| 60_custom_wave | 12 |
| 61_thin_plate | 17 |
| 62_custom_3d | 6 |
| 70_surrogate | 9 |
| 90_incomplete | 2 |

---

## 分段素材的详细记录
# 仿真 GIF 素材交接（2026-09-23）

素材根目录：`D:\bs_thesis\review\simulation_gifs_20260923`
已验证 170 个 GIF，每个有同名 PNG 封面与 JSON 来源说明。数量按“数据文件 / 分析步 / 展示内容”计，不等于独立物理算例数。

## 给制作 PPT 的 agent

先读仓库 PROJECT_HANDOFF.md 的当前结论，再读本文件和 manifest.json。用 index.html 浏览全部动画。当前冲击和修正半径导波优先使用 01_current_impact、02_current_wave。每页保留图注与限制，历史参数对照、流程验证、代理/合成数据不得混称当前有效结果。GIF 用于放映，PNG 用于静态导出或不播放动画的软件。不要使用 _data 中间文件直接充当插图。

## 数据表达与限制

- 原始数值场导出；每段最多选取 51 个已保存时间帧，GIF 每帧 150 ms，循环慢放。时间标记是物理时间，不是视频播放时间；未补造求解帧。高分辨率顶面可能抽取节点，详情见 JSON。
- 冲击截面变形比例为 1；导波显示未变形坐标上的位移场。色标在同一 GIF 内固定，不同 GIF 可不同，跨图对比应查看范围。未将机械响应冒充 PZT 电压。
- 只有时程的算例显示完整原始曲线与移动时间标记，不能据此重建缺失的全场。薄板 w 向下为正，Abaqus U3 取模型坐标方向。
- ALLDMD 是总损伤耗能。能量等价圆半径是跨界面完全断裂能量的等效换算；不是几何损伤边界，也不能直接解释为每个界面的真实半径。
- 当前单次标定采用替代材料参数；应力场尚未收敛，无实物验证。小半径导波仍有冲击 4 个受损界面与导波 5 个预置界面的映射差异。
- 正式累积序列当前只收录完成的第 1 次冲击。中断归档的松弛片段在 90_incomplete；正在运行且有锁的 ODB 未读取。无帧、失败和无物理时间轴数据见 exclusions.json，不能说这些也已生成完整动画。

## 分类统计

| 目录 | GIF 数 |
|---|---:|
| 01_current_impact | 4 |
| 02_current_wave | 3 |
| 20_historical | 30 |
| 30_abaqus_validation | 14 |
| 40_material_probes | 20 |
| 50_workflow_tests | 30 |
| 60_custom_wave | 12 |
| 61_thin_plate | 34 |
| 62_custom_3d | 12 |
| 70_surrogate | 9 |
| 90_incomplete | 2 |

## 当前主线优先素材

| 算例 / 步 | GIF | 封面 |
|---|---|---|
| acc_n01 / IMPACT | [acc_n01__IMPACT__34fa7d29.gif](01_current_impact/acc_n01__IMPACT__34fa7d29.gif) | [PNG](01_current_impact/acc_n01__IMPACT__34fa7d29.png) |
| imp_hi / IMPACT | [imp_hi__IMPACT__41d87c74.gif](01_current_impact/imp_hi__IMPACT__41d87c74.gif) | [PNG](01_current_impact/imp_hi__IMPACT__41d87c74.png) |
| imp_lo / IMPACT | [imp_lo__IMPACT__f065c58c.gif](01_current_impact/imp_lo__IMPACT__f065c58c.gif) | [PNG](01_current_impact/imp_lo__IMPACT__f065c58c.png) |
| imp_mid / IMPACT | [imp_mid__IMPACT__e9f1fa9b.gif](01_current_impact/imp_mid__IMPACT__e9f1fa9b.gif) | [PNG](01_current_impact/imp_mid__IMPACT__e9f1fa9b.png) |
| wav_base / WAVE | [wav_base__WAVE__31bfb0d4.gif](02_current_wave/wav_base__WAVE__31bfb0d4.gif) | [PNG](02_current_wave/wav_base__WAVE__31bfb0d4.png) |
| wav_d03_r08 / WAVE | [wav_d03_r08__WAVE__610f16ee.gif](02_current_wave/wav_d03_r08__WAVE__610f16ee.gif) | [PNG](02_current_wave/wav_d03_r08__WAVE__610f16ee.png) |
| wav_d08_r31 / WAVE | [wav_d08_r31__WAVE__cf0049b0.gif](02_current_wave/wav_d08_r31__WAVE__cf0049b0.gif) | [PNG](02_current_wave/wav_d08_r31__WAVE__cf0049b0.png) |

## 未生成项

- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\c3d8_hashin.odb` S1：fewer than two field frames
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\c3d8_maxps_dir1.odb` S1：fewer than two field frames
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\c3d8_maxse.odb` S1：fewer than two field frames
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\c3d8_maxss.odb` S1：fewer than two field frames
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\c3d8r_hashin.odb` S1：fewer than two field frames
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\degradation\deg_c3d8_elastic.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\degradation\deg_c3d8_max_stress.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\degradation\deg_c3d8_maxps.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\degradation\deg_c3d8_quads.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\degradation\deg_sc8r_hashin.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\ic_probe.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\accum_030j_3\acc_n02_relax1.odb` ：lock exists: active or unverified job
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\grade.odb` IMPACT：fewer than two field frames
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\probe_a_thin_K1e16.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\probe_b_thick_K1e16.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\probe_c_thin_K1e13.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\probe_d_thick_K1e13.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\probe_dt.odb` S1：fewer than two field frames
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\probe_dt_thick.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\probe_dt_thin.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\probe_e_thick_K1e12.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\probe_f_thick_K1e10.odb` S1：no U or V nodal field
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\probe_mass.odb` S1：fewer than two field frames
- `D:\bs_thesis\simulation_reproduction\impact_wave_3d\abaqus\runs\impact\probe_mass2.odb` S1：fewer than two field frames
- `D:\bs_thesis\simulation_reproduction\results\transfer_dataset_seed0.npz` ：静态训练/迁移张量或无已定义物理时间轴，不补造过程动画
- `D:\bs_thesis\simulation_reproduction\results\transfer_dataset_seed1.npz` ：静态训练/迁移张量或无已定义物理时间轴，不补造过程动画
- `D:\bs_thesis\simulation_reproduction\results\transfer_dataset_seed2.npz` ：静态训练/迁移张量或无已定义物理时间轴，不补造过程动画
