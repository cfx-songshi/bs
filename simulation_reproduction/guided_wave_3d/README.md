# 三维主动导波：自研显式求解器 + Abaqus 输入生成

本目录把主动导波模型从二维平面应变拓展到三维，并生成可与实物实验、商业软件对接的模型定义。

两部分交付，成熟度**不同**，请先看下表再使用：

| 交付物 | 状态 |
|---|---|
| [solve_uvg_3d.py](solve_uvg_3d.py) 三维显式有限元 | **已运行并通过解析验证**（见第 3 节） |
| [make_abaqus_inp.py](make_abaqus_inp.py) Abaqus 输入生成 | **已在 Abaqus 2026 上实跑，并在 500×4×4 与 1000×4×8 两个网格上做过定量对照**：A0 相速度 vs 解析 0.16% / 0.09%，RMS 差 2–5%；跨求解器的波形残差随加密从 L2 0.57 降到 0.45 / 0.37，已小于自研自身的网格敏感性。见第 4b 节与「波形差异随网格加密收敛」小节 |

## 1. 为什么必须做三维

[guided_wave_v2](../guided_wave_v2/参数来源与复现边界.md) 是平面应变：它假定场沿宽度方向不变。因此它**无法**表达

- 贴片类小源产生的圆形波前与波束扩散
- 侧边的反射与绕射
- 分层在宽度方向的散射

而这三件事恰恰是实验里看得到的。三维模型去掉该假设，并改用**完整三维正交各向异性刚度**而不是平面应变压缩块，使面外与剪切耦合得以存在。

## 2. 两种源模式，各有用途

| 模式 | 定义 | 用途 |
|---|---|---|
| `line` | 力沿整个宽度分布，x 方向单节点厚 | **验证模式**。它是二维线力的三维对应，响应必须退化为平面应变，因此可直接对着解析 Rayleigh–Lamb 频散检验 |
| `point` | 板中央单节点 | **应用模式**。小 PZT 贴片的最低成本近似，产生圆波前 |

这个设计是刻意的：先靠 `line` 证明三维实现本身没错，再用 `point` 做真实场景。

## 3. 验证：三维线源确实退化到平面应变

用**同一套**波数提取方法（`guided_wave_v2/dispersion_check.py`）处理全部算例，避免后处理差异混淆结论：

| 算例 | c_p @100 kHz | vs 解析 |
|---|---|---|
| **3D 线源 500×4×4** | 1285.2 m/s | **0.10%** |
| **3D 线源 1000×4×8** | 1281.7 m/s | **0.37%** |
| 2D 1000×8（同网格对照） | 1280.3 m/s | 0.48% |
| 2D 4000×32 | 1277.6 m/s | 0.68% |
| 解析 Rayleigh–Lamb | 1286.4 m/s | — |

**3D 与 2D 在相同网格下只差 0.11%**（3D 1000×4×8 vs 2D 1000×8）。这一条同时说明三件事：三维装配正确、完整三维正交各向异性刚度在单向铺层下与平面应变压缩一致、线源激励确实均匀无宽度效应。

数值健康度也好于二维模型：能量相对漂移 **1.5e-14**（二维为 4e-13）。

复算：

```powershell
& $py solve_uvg_3d.py --mode line --nx 500 --ny 4 --nz 4 --lx 0.5 --ly 0.02 --out out_line
& $py solve_uvg_3d.py --mode line --nx 1000 --ny 4 --nz 8 --lx 0.5 --ly 0.02 --out out_line_1000x4x8
& $py check_3d_dispersion.py
```

## 3b. 点源：两个方向均已验证

点源不能用线源那套理由验证：解析参考是平面应变模态，而点源辐射二维弯波前。可用判据是面内各向异性 —— E1 约为 E2 的 16 倍，所以 A0 沿纤维与垂直纤维的波速不同，波前应为椭圆，这是二维平面应变模型给不出的量。

为此给 `dispersion.py` 加了传播方向选择（沿材料 1 / 材料 2），并加自检：各向同性板下两方向必须给出相同结果（实测差异 **0.0**）。

| 方向 | FE c_p @100 kHz | 解析 | 差异 |
|---|---|---|---|
| 沿纤维 x | 1306.4（dx 1.25 / 0.893 mm 一致） | 1286.4 | **1.55%** |
| 垂直纤维 y | 798.0 → 776.4（网格加密后） | 751.7 | **6.17% → 3.29%** |

各向异性比（沿纤维/垂直纤维）：FE 1.637 → 1.683，解析 1.711，差 **4.35% → 1.69%**。

### 途中发现并修复了一个解析 bug（这一段比结果本身重要）

第一次做出来的是 y 方向偏差 10.9%，而且该方向的"解析 A0"在 85–115 kHz **恒为 896.1 m/s、完全不随频率变化**。A0 是色散模态，不可能如此，所以问题在解析侧。

追查发现 `boundary_matrix` 里有一句 `if disc < 0: return None`。判别式为负意味着 `p²` 是复数，对应**沿厚度振荡同时指数变化**的非均匀分波 —— 这是各向异性板的正常解，不是无解。该早退把所有这类解静默删掉了。

x 方向恰好判别式为正，所以从未暴露；y 方向判别式为负，整个 A0 分支被丢弃，只剩下 S0 和一个位于体波剪切速度的假根。

修复后 y 方向的 A0 恢复正确色散：

| f (kHz) | 修复前 c_ph | 修复后 c_ph | c_g/c_ph |
|---|---|---|---|
| 85 | 896.1（恒定） | 704.4 | 1.685 |
| 100 | 896.1 | **751.7** | 1.647 |
| 115 | 896.1 | 793.3 | 1.612 |

相速度随频率单调增（793/704 ≈ √(115/85)，符合弯曲波），且 751.7 **低于 Kirchhoff 上界 845 m/s**（Kirchhoff 忽略剪切柔度与转动惯量，故为上界），物理正确。修复未触动任何原有自检：S0 长波极限 3.57e-07、Rayleigh 3.48e-04、方向映射 0.0 全部保持。

### 残余差异的性质

两方向偏差**同号**（FE 都偏快），符合数值色散特征。y 方向波长更短（8.96 mm）、网格更粗，所以偏差更大且随加密下降（6.17% → 3.29%）。x 方向波长 12.86 mm，1.55% 在两种网格下不变，已收敛。各向异性比 1.69% 的残差是这一构型下点源与平面波解析之间可预期的差别（解析是平面波，点源是柱面波前）。

复算：

```powershell
& $py solve_uvg_3d.py --mode point --nx 200 --ny 200 --nz 4 --lx 0.25 --ly 0.25 --x-src 0.125 --frames 2d --out out_point_200
& $py solve_uvg_3d.py --mode point --nx 280 --ny 280 --nz 4 --lx 0.25 --ly 0.25 --x-src 0.125 --frames 2d --out out_point_280
& $py check_point_source.py --npz out_point_200/wavefield.npz
& $py check_point_source.py --npz out_point_280/wavefield.npz --out point_source_check_280.json
```

**注意**：`--frames 2d` 的 `--frame-stride` 默认为 1（不降采样）。若降采样到 2.5 mm，垂直纤维方向只剩 3.6 个采样点/波长，相位拟合会失效 —— 这一条已写在代码注释里。

## 4. Abaqus：已在 2026 上实跑通过

本机已安装 **Abaqus 2026**（`D:\Abaqus`；许可证由本机 `ABAQUSLM` 服务提供，不是远程 license server，因此不需要校园网或 VPN）。首次提交完成：

```
Output Field Frame Number   110, of    110, at step time 2.200E-04
  THE ANALYSIS HAS COMPLETED SUCCESSFULLY
Abaqus JOB ugw_small COMPLETED
```

1404 个时间增量、110 个输出帧、显式稳定步长 1.60e-07 s、墙钟 23 秒。

### 4b. 定量验证：500×4×4 线源（2026-09-20）

第一个有物理意义的算例：`--nx 500 --ny 4 --nz 4 --lx 0.5 --ly 0.02 --mode line`，dx = 1.0 mm，每 A0 波长 12.7 个单元。**8000 单元 / 12525 节点 / 37575 变量，与自研 `solve_uvg_3d.py` 的同一网格逐一相同**（节点号也对得上：两个接收点是 11203 与 11343）。

```
abaqus job=ugw_line input=ugw_line_500x4x4.inp cpus=8 interactive
```

2329 个增量、110 帧、稳定步长 9.554e-08 s、墙钟约 3 秒。第 4 节检查清单四项的结果：

| 清单项 | 结果 |
|---|---|
| 稳定步长（防质量缩放） | 9.554e-08 s，与稳定性估计一致（自研的 Gershgorin 界是 1.053e-07 s）。质量缩放会把步长抬高一到两个量级，未发生。注意前 47 个增量走的是约 4.29e-08 s，t = 2.018 µs 之后才恒定，而那 2 µs 内激励幅值不足峰值的 1.5% |
| 沙漏能 ALLAE/ALLIE | C3D8R **17.3%**（最差采样点 26.4%）；C3D8 按构造恒为 0 |
| 能量平衡 ETOTAL | 激励结束后变化 5.1e-14 J（C3D8R）/ 5.4e-14 J（C3D8），即峰值 ALLIE 的 **0.047% / 0.051%**。注意 ETOTAL 是接近零的平衡残差（~5e-14 J）而 ALLIE 是 ~1e-10 J，用它的自身均值做分母会得到 88% 这种无意义的数 |
| 与解析对表 | 见下表 |

A0 相速度用**验证自研模型时的同一套估计器**（场输出时空谱相位斜率，`dispersion_check.wave_numbers`）：

| 算例 | c_p@100 kHz | vs 解析 1286.4 | c_g@100 kHz | vs 解析 1745.5 |
|---|---|---|---|---|
| 自研 500×4×4（同步长） | 1285.6 | **0.07%** | 1738.6 | 0.40% |
| Abaqus C3D8 | 1288.5 | **0.16%** | 1924.7 | 10.3% |
| Abaqus C3D8R | 1273.6 | **1.00%** | 1698.1 | 2.7% |

**结论：A0 相速度这一项通过。** 群速度那一列不可用：同一方法给自研 0.40% 却给 C3D8 10.3%，而直达波包互相关给出的是 1811.6 / 1792.1 / 1772.2 m/s（三个都偏高 2–4%），两法彼此矛盾——这与第 3b 节及二维工作已记录的结论一致：短记录上的群速度估计不可靠，**不要引用这一列**。

时程对照（`compare_abaqus_line.py`）。只在直达波包窗口内统计：整段记录会被 x=0 自由端约 160 µs 到达、幅度与直达波相当的反射污染，整段 L2 会给出 1.24 这种与两个求解器都无关的数。基准是自研在 **Abaqus 步长**下的运行（`--dt-scale 1.2955`），因为数值色散依赖 dt，而 Abaqus 的稳定步长比自研的保守估计大 30%。

| 算例 | 接收点 | 峰值比 | RMS 比 | L2 | 最佳时移 |
|---|---|---|---|---|---|
| 自研（自身步长，作灵敏度） | 0.18 / 0.32 m | 0.953 / 0.952 | 0.967 / 0.968 | 0.037 | 0.02 µs |
| Abaqus C3D8 | 0.18 / 0.32 m | 0.850 / 0.965 | **1.006 / 0.974** | 0.57 / 0.77 | 0.56 / 1.24 µs |
| Abaqus C3D8R | 0.18 / 0.32 m | 0.798 / 0.864 | **0.827 / 0.826** | 0.68 / 1.39 | 1.22 / 2.75 µs |

峰值受采样相位影响：两边历史输出都是 1 µs、约 10 点/周期，采样最大值可低估真峰达 5%，所以**以 RMS 为准**，峰值只作参考。第一行同时给出时间步本身的影响：步长差 23% 就会让幅值差 3–5%。

两条可用性结论：

- **C3D8（全积分）：可用。** RMS 差 3% 以内、相速度差 0.16%、直达波包群延迟差 1.1%。
- **C3D8R（减缩积分，本目录原默认）配默认沙漏控制时，在本问题上不可用。** 沙漏能占 17–26%，RMS 低 **17%**、峰值低 15–20%。加密一倍救不回来（沙漏占比 17.26%→17.28%），**但改用 ENHANCED 沙漏控制能把响应救回来**（RMS 差 1–3%），代价是稳定步长腰斩。两条补救路线的实测见下面「减缩积分：加密与增强沙漏控制两条路都试过了」小节——注意那一节同时更正了本节的两句判断（"C3D8R 配默认沙漏控制即可" 和"减缩积分在这里根本不能用"都不准确）。

**当时未解决（如实记录；已由下一节的网格加密定位为离散层面）**：直达波包内两模型的波形仍有 L2 ≈ 0.57 的形状差，且随距离变大（0.18 m 处 0.57、0.32 m 处 0.77，而自研自身换步长的 L2 只有 0.037）。已用实测排除四个候选：

| 候选 | 实测 | 结论 |
|---|---|---|
| 单精度（Abaqus 显式默认单精度） | `double=explicit` 后峰值 0.3416→0.3416、L2 0.6832→0.6831 | 无影响，排除 |
| 时间步不同 | 已用 `--dt-scale` 对齐到 0.016% 以内 | 非主因 |
| 沙漏 | C3D8 沙漏恒为 0，仍然差 | 排除 |
| 体积粘性 | `*Bulk Viscosity` 改 0.0, 0.0 后 L2 0.5669→0.5722 | 无影响，排除 |

相速度与 RMS 都对上、而波形形状没对上，差异应在包络/相位随距离的演化上。下一节的加密实验表明它**随网格加密收敛**（属离散层面，不是求解器缺陷），但仍未归零，所以**不要宣称逐点波形一致**。

### 波形差异随网格加密收敛（2026-09-20 补做）

把同一算例加密到 **1000×4×8**（dx = 0.5 mm，25.4 单元/A0 波长，32000 单元 / 45045 节点），两侧都按各自网格的 Abaqus 步长对齐（Abaqus 4.77432e-08 s vs 自研 4.77431e-08 s）。Abaqus 侧 4630 增量、墙钟 36 秒。

| 量（0.18 m / 0.32 m） | 500×4×4 | 1000×4×8 |
|---|---|---|
| Abaqus C3D8 RMS 比 | 1.006 / 0.974 | 1.020 / 0.947 |
| Abaqus vs 自研 L2 | 0.564 / 0.771 | **0.451 / 0.365** |
| 最佳时移 | 0.555 / 1.239 µs | **0.240 / 0.300 µs** |
| 直达波包群延迟（自研 / Abaqus，差） | 1811.6 / 1792.1（1.1%） | 1787.8 / 1784.1（**0.2%**） |
| A0 相速度（自研 / Abaqus） | 1285.6 / 1288.5 | 1281.7 / 1285.3 |
| 沙漏 ALLAE/ALLIE、ETOTAL/峰值 ALLIE | 0、0.051% | 0、**0.012%** |

**判据**：一个 L2 数字本身没有尺度，所以拿两个求解器**各自的网格敏感性**做标尺（全部插到同一条 1 µs 网格上）：

| 对比 | 0.18 m | 0.32 m |
|---|---|---|
| 自研 500 vs 自研 1000（自研自身网格敏感性） | 0.322 | **0.862** |
| Abaqus C3D8 500 vs 1000（Abaqus 自身网格敏感性） | 0.145 | 0.334 |
| Abaqus vs 自研，500 网格 | 0.564 | 0.771 |
| Abaqus vs 自研，1000 网格 | **0.451** | **0.365** |

**结论：那个波形差属于离散层面、随加密收敛，不是求解器缺陷。** 加密后跨求解器差异在远端从 0.771 降到 0.365、时移从 1.239 降到 0.300 µs、群延迟差从 1.1% 降到 0.2%，且 1000 网格上的跨求解器差异（0.451 / 0.365）**已小于自研自身的网格敏感性**（远端 0.862）。A0 相速度在两个网格上 Abaqus 都在 0.2% 以内（细网格 0.09%）。

两条不要过度解读：①差异**没有归零**，所以仍不能宣称逐点波形一致，只能说它与离散误差同量级；②同一单元同一网格下，**自研的波形随网格变化（0.322 / 0.862）反而比 Abaqus 的大（0.145 / 0.334）**——这一条已如实记录，未做解释。

#### 减缩积分：加密与增强沙漏控制两条路都试过了（2026-09-20）

既然 4b 判定"减缩积分不可用"，剩下两条补救路线是加密网格和改沙漏控制。两条都做了。

**路线一：加密。** 把 C3D8R 也在 1000×4×8 上跑了一遍（4630 增量、稳定步长 4.77377e-08 s、墙钟 7 秒；与 C3D8 的 4.77432e-08 s 同步长，自研参考仍用同一个 4.77431e-08 s）。

| 量 | C3D8R @500 | C3D8R @1000 | C3D8 @1000（对照） |
|---|---|---|---|
| ALLAE/ALLIE 峰值 | 17.26% | **17.28%** | 0 |
| ALLAE/ALLIE 最差采样点 | 26.37% | **31.20%** | 0 |
| RMS 比 vs 自研 | 0.827 / 0.826 | 0.854 / 0.864 | 1.020 / 0.947 |
| 峰值比 vs 自研 | 0.798 / 0.864 | 0.824 / 0.888 | 0.895 / 0.904 |
| A0 相速度 vs 解析 | 1.00% | 0.81% | **0.09%** |
| 1000 网格上 vs C3D8 的 L2 | — | 0.319 / 0.372 | — |

**路线一的结论：加密救不回来。** dx 从 1.0 mm 减到 0.5 mm，沙漏占比 17.26% → 17.28%（毫厘不变，最差采样点反而从 26.4% 升到 31.2%），幅值仍低 9–15%，相速度仍偏 0.81%（C3D8 是 0.09%）。沙漏占比为何与单元尺寸几乎无关，只作为**观察**记录（单元类型与体积粘性都没动，唯一变的是 dx，占比却不降），**未做归因**。

**路线二：增强沙漏控制。** 生成器加了 `--hourglass {default,enhanced,stiffness,combined}` 与 `--hourglass-stiffness`，写出 `*Section Controls, hourglass=ENHANCED` 并由 `*Solid Section` 引用。⚠️ `*Section Controls` 是 **model 层**关键字，放进 `*Part` 里会被预处理器判为 misplaced（第一次就这么错了），必须放在 `*End Part` 之后。

```powershell
& $py make_abaqus_inp.py --nx 500 --ny 4 --nz 4 --lx 0.5 --ly 0.02 --mode line --hourglass enhanced --out "$r\ugw_line_c3d8r_ehg.inp"
& $py solve_uvg_3d.py --mode line --nx 500 --ny 4 --nz 4 --lx 0.5 --ly 0.02 --dt-scale 0.6507 --out out_line_ehgdt
```

⚠️ **增强控制会把稳定步长腰斩**：9.554e-08 s → **4.79792e-08 s**，增量 2329 → **4592**，即约两倍代价。所以它的自研参照必须另跑一个同步长的（`--dt-scale 0.6507`，dt = 4.79721e-08，与 Abaqus 差 0.015%），否则单元结论会和两倍时间步变化混在一起。

| 量 | C3D8R 默认控制 | C3D8R ENHANCED | C3D8 全积分（对照） |
|---|---|---|---|
| ALLAE/ALLIE 峰值 / 最差采样 | 17.26% / 26.37% | 15.11% / **35.16%** | 0 / 0 |
| RMS 比 vs 自研 | 0.827 / 0.826 | **0.993 / 0.972** | 1.006 / 0.974 |
| 峰值比 vs 自研 | 0.798 / 0.864 | 0.982 / 0.970 | 0.850 / 0.965 |
| L2 vs 自研 | 0.678 / 1.388 | **0.246 / 0.436** | 0.564 / 0.771 |
| 最佳时移 | 1.22 / 2.75 µs | **−0.18 / 0.48 µs** | 0.56 / 1.24 µs |
| 直达波包群延迟差 | 2.2% | **0.9%** | 1.1% |
| 稳定步长 | 9.554e-08 | 4.798e-08（**腰斩**） | 9.554e-08 |

**这不是时间步的功劳。** 同一个自研模型、同一网格，把 dt 减半只造成 L2 **0.023 / 0.021**、幅值 2%（0.983 / 1.008），量级远小于上表里 0.678→0.246 的变化。所以增强沙漏控制确实把**响应**救回来了。

**需要更正 4b 的两句判断**（本轮最重要的产出）：

1. **`ALLAE/ALLIE` 不能跨沙漏控制类型比较。** ENHANCED 用的是更刚的人工刚度，它的 ALLAE 定义随之改变：占比仍高达 15–35%（最差采样点反而更高），但响应误差从 17% 掉到 1–3%。也就是说 4b 里"ALLAE 占 17–26% 所以不可用"这个推理，**只在默认控制下成立**；判单元优劣应以响应量（RMS/L2/相速度）为准，ALLAE 只作同一控制类型内部的自查。
2. **"减缩积分在本问题上不可用"不成立。** 准确说法是：**减缩积分配默认沙漏控制**不可用；配 ENHANCED 可用，代价是稳定步长约两倍。本目录仍然推荐 `--element C3D8`，但理由从"减缩积分救不了"改成**成本**：C3D8 不需要腰斩的步长，且同样把 RMS 做到 3% 以内。

`--hourglass stiffness/combined`（含刚度比例因子）未试。

### 4c. 4b 的复算命令

仓库路径已是纯 ASCII，可直接在仓库内求解；一次求解会写十来个产物，仓库内 `abaqus/runs/` 已忽略，也可以放到仓库外（如 `D:\abaqus_runs\line500`）。

```powershell
$py = 'C:\Users\29795\AppData\Local\Programs\Python\Python313\python.exe'
Set-Location 'D:\bs_thesis\simulation_reproduction\guided_wave_3d'

# 生成 deck（C3D8）与自研参考（--dt-scale 把步长对齐到 Abaqus 的 9.554e-08 s）
& $py make_abaqus_inp.py --nx 500 --ny 4 --nz 4 --lx 0.5 --ly 0.02 --mode line --element C3D8 --out abaqus/ugw_line_500x4x4.inp
& $py solve_uvg_3d.py --mode line --nx 500 --ny 4 --nz 4 --lx 0.5 --ly 0.02 --dt-scale 1.2955 --out out_line_abaqusdt

# 求解（8 cpus，约 3 秒）
& 'D:\Abaqus\Commands\abaqus.bat' job=ugw_line input=ugw_line_500x4x4.inp cpus=8 interactive

# 从 odb 取数；odbAccess 属于 Abaqus 安装，这里必须用 Abaqus 自带的 python
& 'D:\Abaqus\Commands\abaqus.bat' python abaqus\read_odb_receivers.py ugw_line.odb abaqus_line500_c3d8_history.json
& 'D:\Abaqus\Commands\abaqus.bat' python abaqus\read_odb_surface.py ugw_line.odb abaqus_line500_c3d8_surface.npz --nx 500 --ny 4 --nz 4 --lx 0.5

# 对照
& $py compare_abaqus_line.py
& $py check_abaqus_dispersion.py
```

加密到 1000×4×8（deck 4.3 MB，按 `.gitignore` 的约定特大 deck 不入库，用生成器现做；运行目录例如 `D:\abaqus_runs\line1000`）：

```powershell
$r = 'D:\abaqus_runs\line1000'
& $py make_abaqus_inp.py --nx 1000 --ny 4 --nz 8 --lx 0.5 --ly 0.02 --mode line --element C3D8 --out "$r\ugw_line_1000x4x8.inp"
& $py make_abaqus_inp.py --nx 1000 --ny 4 --nz 8 --lx 0.5 --ly 0.02 --mode line --out "$r\ugw_line_1000x4x8_c3d8r.inp"   # 减缩积分那一版，不带 --element
& $py solve_uvg_3d.py --mode line --nx 1000 --ny 4 --nz 8 --lx 0.5 --ly 0.02 --dt-scale 1.2928 --out out_line_1000x4x8_abaqusdt
& $py solve_uvg_3d.py --mode line --nx 1000 --ny 4 --nz 8 --lx 0.5 --ly 0.02 --out out_line_1000x4x8

Set-Location $r
& 'D:\Abaqus\Commands\abaqus.bat' job=ugw_line1000 input=ugw_line_1000x4x8.inp cpus=8 interactive   # 4630 增量、约 36 秒
& 'D:\Abaqus\Commands\abaqus.bat' python 'D:\bs_thesis\simulation_reproduction\guided_wave_3d\abaqus\read_odb_receivers.py' ugw_line1000.odb 'D:\bs_thesis\simulation_reproduction\guided_wave_3d\abaqus_line1000_c3d8_history.json'
& 'D:\Abaqus\Commands\abaqus.bat' python 'D:\bs_thesis\simulation_reproduction\guided_wave_3d\abaqus\read_odb_surface.py' ugw_line1000.odb 'D:\bs_thesis\simulation_reproduction\guided_wave_3d\abaqus_line1000_c3d8_surface.npz' --nx 1000 --ny 4 --nz 8 --lx 0.5
```
两个 `solve_uvg_3d.py` 的 `--dt-scale` 是各自网格的 Abaqus 步长除以 0.7 倍 Gershgorin 界；换成别的网格时先跑一次自身步长（看 `summary.json` 的 `dt_upper_bound_s`）再算这个比值。

- 仓库里提交的 `abaqus/ugw_line_500x4x4.inp` 是 **C3D8** 版本。C3D8R 那一行去掉 `--element C3D8`、输出名改成 `..._c3d8r_...` 即可。
- `abaqus_line500_c3d8r_history.json` 来自**单精度**默认求解；`abaqus_line500_c3d8r_dp_surface.npz` 来自 `double=explicit` 的那次（两者结果一致到 4 位有效数字，那次跑的目的正是证明精度不是差异来源），所以 `check_abaqus_dispersion.py` 里那一行标的是 "C3D8R 500x4x4 dp"。
- 1000 网格两个单元都跑了：`abaqus_line1000_c3d8_history.json` 与 `abaqus_line1000_c3d8r_history.json`（后者用于确认「加密救不回减缩积分」）。
- 两个 `*_surface.npz` 是 `*.npz`，按 `.gitignore` 不入库；没有它们时 `check_abaqus_dispersion.py` 会直接报"缺少"。

在 CAE 里看结果（不产出数值，只开图形界面）：

```powershell
& 'D:\Abaqus\Commands\abaqus.bat' cae script=abaqus\view_odb.py -- `
    'D:\abaqus_runs\line500\ugw_line.odb' `
    'D:\abaqus_runs\line500\ugw_line_c3d8r_dp.odb' `
    --outdir 'D:\abaqus_runs\view' --times 40,60,80,100,130,200 --leave-at 100
```

- 会对每个 odb 建"未变形形状 + U3 云图 + 顶部视图"，按 `--times` 导出 PNG 到 `--outdir`，并把过程写进 `--outdir\view_log.txt`（CAE 不回传输出到调用它的终端，所以日志是唯一的自查途径）。
- **色标是固定的**（取该 odb 全时程的 |U3| 极值），否则每换一帧 Abaqus 会按该帧数据重算，同一个颜色在不同帧代表不同位移。生效的关键是 `minAutoCompute`/`maxAutoCompute`，只写 `minValue`/`maxValue` 会被静默覆盖——这一点是查属性表确认的，不是猜的。播放动画不重算是靠 `animationAutoLimits`，它**不是开关而是符号常量**（这版是 `ALL_FRAMES`），早期用 `ON`/`OFF` 去设全被拒；同样是从对象上读回来才确认的。
- 固定范围**按 odb 各自取**：C3D8R 的极值比 C3D8 宽（沙漏贡献进去了），所以两套 PNG 里同一个颜色并不代表同一位移。
- 会话结束后停在**命令里第一个 odb**（也就是被推荐的那个单元类型）的 `--leave-at` 帧上，不停在最后一段记录（那时自由端回波已经扫过接收点）。

### 两条必须知道的实际约束

**1. 路径必须是纯 ASCII（该约束现已满足）。** 该 deck 第一次提交时仓库路径还是 `D:\毕设知识库`，预处理成功，但显式求解器在 `Begin Abaqus/Explicit Analysis` 之后立刻崩溃：

```
UnicodeEncodeError: 'charmap' codec can't encode characters in position 15-19
```

位置 15-19 正是路径里的中文字符。**pre.exe 能处理中文路径，explicit.exe 不能** —— 所以"预处理通过"不能当作"路径没问题"。**仓库路径已因此改为纯 ASCII 的 `D:\bs_thesis`，现在可以直接在仓库内运行**（本条记录保留，因为把算例放进任何中文目录都会以同样方式失败）。改名前的成功运行是在 `D:\abaqus_runs\small` 下做的：

```powershell
$r = 'D:\abaqus_runs\small'; New-Item -ItemType Directory -Force -Path $r | Out-Null
Copy-Item 'D:\bs_thesis\simulation_reproduction\guided_wave_3d\abaqus\ugw_small.inp' $r
Set-Location $r
& 'D:\Abaqus\Commands\abaqus.bat' job=ugw_small input=ugw_small.inp cpus=2 interactive
```

**2. 首次提交暴露的两个真实错误（均已修）。** 静态自检当时是全绿的，却挡不住它们 —— 这正是"必须真跑一次"的理由。

| 错误 | 原因 | 修法 |
|---|---|---|
| `Unknown assembly id 679` | assembly 层的载荷用了裸节点号 | 改为 `PLATE-1.679`（instance 前缀） |
| `Anisotropic material properties without a local orientation system` | 各向异性材料**必须**显式给出局部坐标系，即使与全局轴重合 | 加 `*Orientation, name=Fibre`，由 `*Solid Section` 引用 |

第二条曾被本文档判断为"不需要"，是错的。第一条的检查规则已补进静态自检：它原先只验证节点存在，不检查 assembly 层的引用格式。

### 这个算例只用于语法检查

`ugw_small.inp` 是 12×12×4 = 576 单元、dx = 41.7 mm，而 100 kHz 的 A0 波长是 12.7 mm —— **每波长仅 0.3 个单元，物理结果无意义**。它的唯一作用是证明 deck 能被求解器接受。有物理意义的算例需要 dx ≤ 1.27 mm，即 `--nx 400`。

### 提交大算例前的检查清单

1. **稳定步长**：本例报 1.60e-07 s。未做质量缩放（刻意，见下），若 Abaqus 报出的步长远大于此，说明缩放被默认打开，波速会失真。
2. **沙漏能**：C3D8R 是减缩积分，须看 ALLAE（人工应变能）相对 ALLIE 是否可忽略。
3. **能量平衡**：激励结束后 ETOTAL 应保持常数（自由板、无阻尼）。这是与自研模型同一口径的检查。
4. **与解析对表**：A0 相速度应为 1286 m/s @100 kHz、群速度 1745 m/s；S0 约 9053 m/s。这是第 3 节已验证过的参照。

### 建模选择及理由

| 选择 | 理由 |
|---|---|
| 单元类型：见 4b | 原选 `C3D8R`，理由是"全积分 `C3D8` 在弯曲下剪切锁定，而 A0 正是弯曲变形"。实测**推翻了**这个选择：同一网格下 C3D8R 配默认沙漏控制的 RMS 比自研低 17%、沙漏能占 ALLIE 的 17–26%，而 C3D8 的 RMS 差 3% 以内、相速度差 0.16%。**加密一倍也救不回来**（17.26%→17.28%），**ENHANCED 沙漏控制能救回响应**（RMS 差 1–3%）但稳定步长腰斩、代价约两倍——见「减缩积分：加密与增强沙漏控制两条路都试过了」。故本问题取 `C3D8`，理由是**成本**（不需要腰斩的步长），不是"减缩积分救不了" |
| 必须写 `*Orientation` | 各向异性材料在 Abaqus 中**必须**显式给出局部坐标系，**即使材料轴与全局轴重合** —— 省略它是硬错误，不是"自动取默认"。首次实际提交即因此失败（`Anisotropic material properties without a local orientation system`）。这里定义局部 1 轴沿纤维（全局 x）、局部 2 轴沿 y、局部 3 轴沿厚度。若铺层旋转，改这里而不是改网格 |
| 不做质量缩放 | 自研模型也用自己的稳定步长，两者才可比；缩放会改变所要比较的波速 |
| 无边界条件 | 自由板在显式动力学中可解，且参考模型同样是自由边界 |
| 幅值表每 0.5 µs 一点 | 100 kHz 五周期，每周期 100 个采样点，足够复现 Hann 窗 |
| 分层写进网格而不是用 `*Tie` | 中面分层区内的节点复制一份，仅中面以上单元使用，两半在该区不共享节点、裂尖仍连接。写成单一 part 可省掉 tie 约束的簿记 |

### 用法

```powershell
# 小模型（几十秒级，先用它确认语法）
& $py make_abaqus_inp.py --nx 12 --ny 12 --nz 4 --lx 0.5 --ly 0.5 --out abaqus/ugw_small.inp

# 含分层
& $py make_abaqus_inp.py --nx 40 --ny 40 --nz 4 --damage 0.235 0.265 0.2 0.3 --out abaqus/ugw_small_damage.inp

# 实用规模的点源模型（生成约 20 MB，未入库）
& $py make_abaqus_inp.py --nx 200 --ny 200 --nz 4 --mode point --out abaqus/ugw_plate_point.inp

# 有 Abaqus 之后
abaqus job=ugw_small input=ugw_small.inp cpus=4
```

每次生成都会自动跑一致性自检，未通过则直接报错退出。

## 5. 网格与步长依据

100 kHz 下 A0 波长约 **12.7 mm**、S0 约 **90 mm**，因此**单元尺寸由 A0 决定**。默认保持每个 A0 波长至少 10 个单元，与二维验证所用的分辨率准则一致。

| 网格 | dx | 每 A0 波长单元数 | 用途 |
|---|---|---|---|
| 500×4×4 | 1.0 mm | 12.7 | 线源验证 |
| 1000×4×8 | 0.5 mm | 25.4 | 与 2D 同网格对照 |
| 200×200×4 | 2.5 mm | 5.1 | ⚠️ 仅用于连通性/成本试算，**不足以分辨 A0** |

需要提醒的是第三行：`200×200` 在 500 mm 板上给出 dx = 2.5 mm，只有 5 个单元/A0 波长，**不足以做定量结论**。若要全尺寸点源结果，应取 `--nx 400`（dx = 1.25 mm，10 单元/波长）。

线源验证之所以能用很小的 `ny`（4 层），是因为场沿宽度不变；点源则必须让宽度足够容纳波前扩散。

## 6. 限制与未完成

1. **Abaqus 侧的波形差已定位为离散层面、随加密收敛**（第 4b 节与「波形差异随网格加密收敛」小节）：同一网格、同一时间步下 A0 相速度差 0.16%（细网格 0.09%）、RMS 差 2–5%；500 网格上残留的 L2 ≈ 0.57 在 1000 网格上降到 0.451 / 0.365，且已小于自研自身的网格敏感性（0.862）。**但差异没有归零**：不要把静态自检通过读作"模型已可用"，也不要把相速度通过读作"逐点波形已复现"。
2. **分层区无接触、无黏聚、无摩擦**，与二维模型同一定义：开口界面，不闭合、不拍击。不能用于分层扩展或强度预测。
3. **无 PZT、无胶层、无机电耦合、无阻尼**。输出是**机械位移**，不是电压，绝不可标为电压。
4. **点源已验证**（见 3b）：沿纤维 1.55%，垂直纤维 3.29%（网格加密后），各向异性比 1.69%。
5. S0 在本模型的法向激励下依然不可见（与二维同样的问题），因此第 3 节的验证只覆盖 A0。
6. 未做 3D 侧的网格收敛扫描（2D 侧已有，见 [guided_wave_v2](../guided_wave_v2/参数来源与复现边界.md) 第 6 节）。
7. `dispersion.py` 的横向约束取的是平面应变（`ε_yy = 0`），自由板严格说应是平面应力（`σ_yy = 0`）。对 [0]8 实测影响很小，但换铺层（尤其大 ν 情形）须重估。**不要把这一条与 3b 记录的判别式 bug 混为一谈**：那个是代码缺陷、已修；这一条是仍存在的建模近似。

## 7. 文件

| 文件 | 用途 |
|---|---|
| `solve_uvg_3d.py` | 三维 H8 显式求解器；`--mode line/point/line_across`，可选分层，`--frames 2d` 存二维表面场，`--dt-scale` 放大稳定步长（用于与别的求解器对齐 dt） |
| `check_3d_dispersion.py` | 3D / 2D / 解析三方波速对比（线源），输出 `dispersion_check_3d.json` |
| `check_point_source.py` | 点源沿两个方向的波速与各向异性比，输出 `point_source_check*.json` |
| `check_abaqus_dispersion.py` | 用同一套波数提取器量 Abaqus 的 A0 相/群速度，输出 `abaqus_dispersion_check.json` |
| `compare_abaqus_line.py` | Abaqus 与自研的接收点时程对照（只在直达波包窗口内），输出 `abaqus_line500_compare.json` |
| `make_abaqus_inp.py` | Abaqus 输入生成 + 静态一致性自检；`--element C3D8R/C3D8`、`--hourglass default/enhanced/stiffness/combined`（含 `--hourglass-stiffness`） |
| `abaqus/read_odb_receivers.py` | 从 odb 取接收点 U3 时程与 ALLAE/ALLIE/ALLKE/ETOTAL；须用 `abaqus python` 运行 |
| `abaqus/read_odb_surface.py` | 从 odb 取上表面宽度中线 110 帧，写成与自研同格式的 npz；须用 `abaqus python` 运行 |
| `abaqus/view_odb.py` | 在 Abaqus/CAE 里显示结果：顶部视图 U3 云图、**固定色标**、每帧导出 PNG；须用 `abaqus cae script=...` 运行，且不会关闭会话 |
| `abaqus/ugw_small.inp` | 无分层小算例（12×12×4），用于确认语法 |
| `abaqus/ugw_small_damage.inp` | 含分层小算例（40×40×4） |
| `abaqus/ugw_line_500x4x4.inp` | 有物理意义的线源算例（500×4×4，dx = 1.0 mm），第 4b 节用的就是它 |

`out_*/` 为求解输出（`*.npz` 不入库），特大 `.inp` 亦不入库，详见 [.gitignore](.gitignore)。
