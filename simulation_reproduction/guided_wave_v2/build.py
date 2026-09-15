from pathlib import Path
import json,re,base64,hashlib,html
P=Path(__file__).resolve().parent
fragment=P/'visual-template.html'
f=fragment.read_text(encoding='utf8')
data=(P/'visual-data.json').read_text(encoding='utf8')
f=re.sub(r' const data=.*?;\n',lambda m:' const data='+data+';\n',f,count=1)
fragment.write_text(f,encoding='utf8')
if (P.parent/'physical-experiment-model.html').exists():
    (P.parent/'physical-experiment-model.html').write_text(f,encoding='utf8')
assert len(f.encode())<1000000 and '__SIMULATION_DATA__' not in f
m=json.loads((P/'metrics.json').read_text())
result=f'''# 本次计算结果

全部数值由 solve.py 的有限元求解输出，不是实验测量值。

| 指标 | R1（180 mm） | R2（320 mm） |
|---|---:|---:|
| 健康主波包包络峰值时刻 / μs | {m['R1_healthy_packet_peak_us']:.2f} | {m['R2_healthy_packet_peak_us']:.2f} |
| 健康位移绝对峰值 / nm | {m['peak_healthy_nm_R1_R2'][0]:.4f} | {m['peak_healthy_nm_R1_R2'][1]:.4f} |
| 差分位移绝对峰值 / nm | {m['peak_difference_nm_R1_R2'][0]:.4f} | {m['peak_difference_nm_R1_R2'][1]:.4f} |
| 粗→中网格损伤波形 L2 变化 | {m['coarse_to_medium_relative_L2_R1_R2'][0]:.2%} | {m['coarse_to_medium_relative_L2_R1_R2'][1]:.2%} |
| 中→细网格损伤波形 L2 变化 | {m['medium_to_fine_relative_L2_R1_R2'][0]:.2%} | {m['medium_to_fine_relative_L2_R1_R2'][1]:.2%} |
| 中网格时间步减半 L2 变化 | {m['half_dt_relative_L2_R1_R2'][0]:.3%} | {m['half_dt_relative_L2_R1_R2'][1]:.3%} |

由两个健康接收点主波包包络峰间距计算的表观群速度为 {m['packet_group_speed_m_s']:.1f} m/s。该值是本模型数据处理结果，未拟合论文速度。

R1 在初始直达波之后出现较弱差分；R2 的透射波发生明显相位改变。差分峰值可以超过健康峰值，因为相减的两个波形可能反相，不能把这个幅值比解释为散射能量比或损伤百分比。

最细网格为 128000 个 Q4 单元，损伤状态 132272 个节点；步长约 9.248 ns，共 23789 步。所有工况总质量为 1.3502 kg/m（二维单位宽度），激励结束后离散能量相对漂移最大约 1.71×10⁻¹²。上述守恒检查通过，但中→细网格变化仍有 6%–10%，**当前仅作为初步物理参考，不标记为波形完全收敛或实验验证通过**。

完整时间窗为 0–220 μs，L2 网格比较使用 t<200 μs。存储输出间隔约 0.1 μs，随积分步长取整；时空图/交互图使用约 2 μs 波场帧及 1 mm 表面空间采样，原始计算网格更密。

![截面和接收信号](experiment-results.png)

![表面时空波场](wave-space-time.png)
'''
(P/'计算结果.md').write_text(result,encoding='utf8')
styles='''<style>:root{color-scheme:light;--foreground:#172b39;--background:#fff;--border:#adb8c0;--viz-series-1:#087f8c;--viz-series-2:#a83266;--viz-series-3:#c65f16}body{max-width:960px;margin:24px auto;padding:16px;font-family:Microsoft YaHei,sans-serif;color:var(--foreground);line-height:1.7}img{width:100%;height:auto}.viz-controls{display:flex;flex-wrap:wrap;gap:24px}label{display:grid;gap:4px}select,input{font:inherit}input{width:240px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}a{color:#076b90}.text-small{font-size:13px}</style>'''
images=''.join('<img alt="'+name+'" src="data:image/png;base64,'+base64.b64encode((P/name).read_bytes()).decode()+'">' for name in ['experiment-results.png','wave-space-time.png'])
page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>主动导波分层散射参考仿真</title>'+styles+'<body><h1>主动导波分层散射参考仿真</h1><p>文献材料参数 + 实际有限元求解。二维等效力基准，尚未建立 PZT 电压耦合。</p>'+f+images+'<h2>计算记录</h2><pre>'+html.escape(result.split('![截面')[0])+'</pre><p><a href="参数来源与复现边界.md">完整参数来源与复现边界</a> · <a href="receiver_signals.csv">接收信号 CSV</a> · <a href="solve.py">求解代码</a></p></body></html>'
(P/'打开仿真.html').write_text(page,encoding='utf8')
files=[q for q in P.iterdir() if q.is_file() and q.name!='manifest.json']
manifest={q.name:hashlib.sha256(q.read_bytes()).hexdigest() for q in files}
(P/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
print('Built',len(files),'files; inline bytes',len(f.encode()))
