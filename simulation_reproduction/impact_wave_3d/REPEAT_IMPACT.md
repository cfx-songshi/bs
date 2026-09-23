# 同点重复落球：状态续算与验收

本轮方案为约 0.300 J、同一点、3 次自由冲击，每次冲击步 500 µs。
第 1 次仍用 `make_impact_wave_inp.py` 生成；随后由 `repeat_impact.py` 生成
restart 输入。接触定义、网格和材料状态不重建，不通过预置 disbond 放大损伤。
结果只支持当前替代材料、夹持、网格和数值衰减下的机械响应，尚无实物验证。

从本目录运行：

```powershell
python run_repeat_impact.py --production --hits 3 --work abaqus/runs/impact/accum_030j_3
```

控制器将完整日志、ODB、restart 文件和逐步 JSON 留在工作目录；
`repeat_impact_summary.md/json` 与 `PROJECT_HANDOFF.md` 的标记区在每级读回后更新。
不覆盖失败的求解作业。再次执行同一命令只复用已成功完成的作业；
已有未完成 ODB 或锁文件时先停下供排查。无需同时打开多个终端。
长作业可用 `Start-Process -WindowStyle Hidden` 启动此控制器，并重定向 stdout/stderr。

## 网格、材料与衰减假设

生成参数固定为 `--nx 79 --ny 79 --nz 8 --centre-size 1.5e-4
--contact-scope interfaces --cohesive-stiffness 2.37e13 --drop-mm 7709
--impact-us 500 --settle-alpha 20000`，求解使用 `double=explicit`。
材料及界面替代参数出处沿用生成器和权威交接文档；本轮没有另改强度或断裂能。

`--settle-alpha` 预先定义场变量控制的质量比例阻尼；初始场变量为 0，
自由冲击时关闭。仅间隔阶段令 α=20000 s⁻¹。此值为数值准备的工程选择，
**不是实测阻尼，也不能把数值衰减时间当作真实落球间隔**。
依据：[Abaqus DAMPING](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-damping.htm)、
[FIELD](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-field.htm)、
[RESTART](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEKEYRefMap/simakey-r-restart.htm)。
本机 Abaqus 2026 已用小算例检验对应行为。

每次之间依次执行：

1. 确认球已反弹且末段接触力消失，再以连续速度曲线回收球，停在至少 3 mm 的高度。
2. 每 500 µs 检查一次。最近 50 µs 的板机械能（ALLKE 扣除球平移动能，再加 ALLSE）
   须低于 3e-5 J，末帧板最大速度须低于 0.05 m/s；这两项是本轮工程验收阈值。
   最多检查 4 段，仍未满足则停止，不进入下一次冲击。
3. 100 µs 平滑定位，50 µs 加速；末端球底与未变形板面间隙 0.1 mm，
   速度 −12.2963 m/s；随后解除球速度边界，自由撞击。
   定位/发射阶段另查损伤增量、板残余振动和间隙，不能靠执行成功判定无接触。

第 1 次球初始相切，后续多约 8 µs 自由飞行，所以接触时刻略不同，入射能量相同。
间隔过程的 ALLDMD 增量单独记录。损伤可以饱和，不预设它必须逐次增长。

按既有每 500 µs 约 4.6 h 估算，若每个间隔只需一段衰减：
第 1 次约 4.6 h；第 2、3 次各含间隔约 10.6 h；整轮约 **25.8 h**。
每额外一段 500 µs 衰减再加约 4.6 h。实际速度受机器负载影响。

## 逐级读数与停止条件

原读数命令仍可读单步 ODB。多步 ODB 必须加 `--step`，避免静默只读第一个步。
结构化读数示例（球/板节点号见初始 deck 的 `.sensors.json`）：

```powershell
cd abaqus
& D:\Abaqus\Commands\abaqus.bat python read_odb_impact_summary.py runs/impact/accum_030j_3/acc_n01.odb --ball-mass 3.9676e-3 --step IMPACT --expected-us 500 --ball-node 193867 --top-node 177460 --json runs/impact/accum_030j_3/manual_n01.json
```

上面的节点号使用前须对照生成的 sidecar；控制器总是从 sidecar 自动读取。
机器可读输出由 `impact_metrics.py` 实现，包含累计及步内增量 ALLDMD、能量等价圆半径、
逐界面损伤节点与面积、力/挠度/反弹、残余速度、能量平衡。
下一步启动前检查 CSDMG 与 ALLDMD 连续、损伤不回退，
ETOTAL 步内漂移 ≤单次入射能的 1%，步间跳变 ≤0.1%，
无异常 ALLAE、无未知求解器 warning/error、磁盘至少剩余 8 GiB。
这些是工程筛查阈值，不表示通过后已完成物理验证。

`abaqus.bat python` 在脚本 `SystemExit` 时可能返回 0，因此控制器还要求
每次读取生成一个全新唯一命名的 JSON，再替换上次结果，禁止用旧 JSON 冒充新读数。

## footprint 的口径与保留意见

`ALLDMD / [1060,490]` 及其等价圆半径是**所有界面的完全断裂能量等价指标**。
部分损伤也耗能，因此这不是几何裂面大小的严格上下界，不能复制到每个界面。
同时输出每个界面的 D>0.01 面积、D≥0.95 面积和最远受损节点半径。
面积按结构网格的节点控制面积近似，并合并两侧同坐标节点以免重复计数；
它仍依赖网格与阈值，不是已收敛的裂面测量。

持续保留的限制：接触应力场未收敛、界面刚度造成约两倍面积敏感性、
数值衰减系数敏感性未完成、无实验对照、层内实体损伤不退化刚度。
本轮不自动把能量等价圆交给导波，也未新跑导波，表中响应是冲击机械响应。

## 本轮启动前的实际检查

- 两实体块黏聚探针：CSDMG 0.879517 → 0.969510；restart 边界误差 0，
  最终与同 deck 连续计算的差值 0。显式指定 interval=1 的分支也为 0。
- 单自由砖块阻尼解析检查：关闭时速度 1；开启 50 µs 后 0.3678825，
  对比 exp(−1)=0.3678794；关闭后存在一个积分过渡（该粗时间步约 0.26%），
  随后各帧速度严格持平。不能把切换当成数学上零时间步的精确操作。
- 19×19×2 粗 coupon 验证回收/定位/再发射与多级续算，仅作流程验证。
- 默认冲击、导波生成内容分别与修改前版本逐字节一致。
- 已发现并修复：用高度筛选板节点误包含球底；回收开始瞬间抹去球反弹动能；
  多步读数默认只读第一步；能量半径上下界打印顺序反转。
- 本机省略 restart interval 会出现 `Restart frame is set 0 and restart analysis disabled`，
  虽探针证实状态已继承，仍改成显式 `interval=1, end step`，此警告消失。

可复算的求解器探针：`abaqus python check_restart_accumulation.py` 与
`abaqus python check_damping_switch.py`（在 `abaqus` 目录下执行，默认拒绝覆盖已有探针）。

## 第一次冲击动画

在本目录执行：

```powershell
& D:\Abaqus\Commands\abaqus.bat python abaqus/export_impact_animation.py abaqus/runs/impact/accum_030j_3/acc_n01.odb abaqus/runs/impact/accum_030j_3/animation/first_impact.npz
python render_impact_animation.py abaqus/runs/impact/accum_030j_3/animation/first_impact.npz abaqus/runs/impact/accum_030j_3/animation/first_impact.gif
```

51 个原始场输出帧，不插帧，150 ms/帧慢放。左侧是真实位移 ×1 的中心截面，球按刚体参考点位移绘制；右侧是未变形坐标上的顶面 U3，固定 ±0.8 mm 色标。下方为中心位移与 ALLDMD。球显示为圆，FE 几何仍是分片球面；不要用图片读数代替更密的历史输出。
