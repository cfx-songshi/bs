# CalculiX 2.23：Abaqus 的开源语法兼容替代

## 为什么是它，而不是 Abaqus

用户要求在本机安装 Abaqus。Abaqus 是商业软件：安装介质必须从 Dassault Systèmes 授权账号下载，运行需要有效的 SIMULIA 许可证（FLEXlm）。这两样都只能由用户或其单位提供，无法代为取得，也不应去找非授权来源。

因此改装 CalculiX：开源（GPL）、免费、**输入文件语法基于 Abaqus 格式**（作者声明经 HKS 许可沿用），是工业界常见的第三方对照求解器。它给本项目补上"独立求解器交叉验证"这一环。

## 安装位置与可执行文件

- 目录：`D:\CalculiX\calculix_2.23_4win`（绿色包，无需安装程序）
- 来源：`https://www.dhondt.de/calculix_2.23_4win.zip`（58.8 MB）
- **可用可执行文件：`ccx_static.exe`**（静态链接）

⚠️ `ccx_dynamic.exe`、`ccx_i4.exe`、`ccx_dynamic_i8.exe` 在本机均以 `0xC0000135`（找不到 DLL）退出，**只有静态版能跑**。图形界面 `cgx_STATIC.exe` 未验证。

## 本机验证

**1. 单元素算例**（`selftest.inp`）：1 m 钢立方体、底面固定、`*FREQUENCY` 取 4 阶。前两阶均为 636.9 Hz —— 两个弯曲方向简并，符合对称性；三、四阶 862.9 / 1433.6 Hz。

**2. 悬臂梁网格收敛**（`beam_5.inp` / `beam_10.inp` / `beam_20.inp`，1×0.1×0.1 m 钢梁，C3D8I 单元）：

| 沿长度单元数 | 一阶弯曲频率 | vs Euler–Bernoulli 81.54 Hz |
|---|---|---|
| 5 | 82.62 Hz | +1.33% |
| 10 | 81.70 Hz | +0.20% |
| 20 | 81.38 Hz | **−0.20%** |

单调收敛到解析值，说明求解器数值正确，不只是"能启动"。

## 重要限制：没有显式动力学

CalculiX 的 `*DYNAMIC` 是**隐式**（HHT-α），**不提供** Abaqus/Explicit 那样的显式动力学求解器。

因此它**不能直接替代** Abaqus/Explicit 做主动导波的时域仿真：100 kHz 瞬态需要约 1e-7 s 的步长，隐式方法每步都要解大型线性系统，对 3D 网格的成本远高于显式。

它能做的：**模态分析**（`*FREQUENCY`）、静力、屈曲、稳态动力学（频响）、小模型的隐式动力学。

对本项目而言：可用它独立校核**低频模态**（板的固有频率），**不能**校核 100 kHz 的导波波速。所以 Abaqus 的缺口**仍然存在**。

## 与 Abaqus 输入的关系

语法相近（`*NODE` / `*ELEMENT` / `*MATERIAL` / `*STEP` 等），但：

- 单元名不同：CalculiX **没有** `C3D8R`；弯曲问题建议 `C3D8I`（非协调模式）或 `C3D20R`，用 `C3D8` 会剪切锁定
- 分析步不同：无 Explicit
- 幅值表、输出请求的写法也有差异

所以 `make_abaqus_inp.py` 生成的 `.inp` **不能**直接提交给 CalculiX，需要转换。转换工作尚未做。

## 复算

```powershell
$ccx = 'D:\CalculiX\calculix_2.23_4win\ccx_static.exe'
& $ccx -i selftest     # 单元素模态
& $ccx -i beam_20      # 悬臂梁；结果在 beam_20.dat 的 EIGENVALUE OUTPUT 段
```

`ccx` 的求解输出（`.frd` / `.sta` / `.cvg` / `.12d` / `.dat`）均为生成物，未纳入版本库。
