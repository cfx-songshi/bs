"""Generate a self-contained HTML report from solved arrays, NumPy only."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import numpy as np
from run_study import compare

ROOT=Path(__file__).resolve().parent
COLORS=['#147d92','#db6a32','#865db1','#5a963c']


def plot(series,title,xlabel,ylabel):
    w,h=900,310; left,right,top,bottom=85,25,45,55
    xmin=min(float(x.min()) for _,x,y in series); xmax=max(float(x.max()) for _,x,y in series)
    ymin=min(float(y.min()) for _,x,y in series); ymax=max(float(y.max()) for _,x,y in series)
    if ymax==ymin: ymax=ymin+1
    pad=(ymax-ymin)*.08; ymin-=pad; ymax+=pad
    sx=lambda x:left+(x-xmin)/(xmax-xmin)*(w-left-right)
    sy=lambda y:h-bottom-(y-ymin)/(ymax-ymin)*(h-top-bottom)
    out=[f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{html.escape(title)}"><rect width="900" height="310" fill="white"/><text x="85" y="25" font-size="18">{html.escape(title)}</text>']
    for i in range(6):
        x=xmin+(xmax-xmin)*i/5; y=ymin+(ymax-ymin)*i/5
        out += [f'<path d="M {sx(x):.2f} {top} V {h-bottom} M {left} {sy(y):.2f} H {w-right}" stroke="#e0e5e8" fill="none"/>',f'<text x="{sx(x):.2f}" y="{h-bottom+22}" text-anchor="middle">{x:.3g}</text>',f'<text x="{left-10}" y="{sy(y)+4:.2f}" text-anchor="end">{y:.3g}</text>']
    for j,(name,x,y) in enumerate(series):
        points=' '.join(f'{sx(a):.2f},{sy(b):.2f}' for a,b in zip(x,y))
        color=COLORS[j%len(COLORS)]
        out += [f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.4"/>',f'<text x="{480+j*105}" y="25" fill="{color}" font-size="13">{html.escape(name)}</text>']
    out += [f'<text x="480" y="302" text-anchor="middle">{xlabel}</text>',f'<text transform="translate(20 165) rotate(-90)" text-anchor="middle">{ylabel}</text></svg>']
    return ''.join(out)


def main():
    p=argparse.ArgumentParser(); p.add_argument('--study',type=Path,default=ROOT/'study_final'); args=p.parse_args()
    study=args.study
    summaries={q.parent.name:json.loads(q.read_text()) for q in study.glob('*/summary.json')}
    orders=sorted(int(k[5:]) for k in summaries if k.startswith('order'))
    fine=f'order{orders[-1]}'; previous=f'order{orders[-2]}'
    load=lambda name:np.loadtxt(study/name/'signals.csv',delimiter=',',skiprows=1)
    data=load(fine); off=load('offcentre')
    original=json.loads((study/'study_metrics.json').read_text())
    convergence={f'{a}_to_{b}':compare(load(f'order{a}'),load(f'order{b}')) for a,b in zip(orders[:-1],orders[1:])}
    compact={'summaries':summaries,'convergence_relative_L2':convergence,'checks':original['checks']}
    (ROOT/'computed_metrics.json').write_text(json.dumps(compact,indent=2),encoding='utf8')
    s=summaries[fine]; change=convergence[f'{orders[-2]}_to_{orders[-1]}']
    t=data[:,0]*1e3
    figures=[plot([(name,load(name)[:,0]*1e3,load(name)[:,1]) for name in [previous,fine] ],'空间加密：接触力','时间 / ms','接触力 / N'),
             plot([('中心位移',t,data[:,2]*1e3)],'冲击点挠度（向下为正）','时间 / ms','位移 / mm'),
             plot([(f'S{i+1}',off[:,0]*1e3,off[:,6+i]*1e6) for i in range(4)],'偏心冲击：贴片区域平均应变和（22阶，未收敛诊断）','时间 / ms','平均 εxx+εyy / με')]
    for i,f in enumerate(figures): (ROOT/f'figure{i+1}.svg').write_text(f,encoding='utf8')
    rows=''.join(f'<tr><td>{n}</td><td>{summaries[f"order{n}"]["first_frequencies_Hz"][0]:.5f}</td><td>{summaries[f"order{n}"]["peak_contact_force_N"]:.3f}</td><td>{summaries[f"order{n}"]["peak_impact_point_displacement_m"]*1e3:.4f}</td><td>{summaries[f"order{n}"]["energy_max_relative_error"]:.2e}</td></tr>' for n in orders)
    sensitivity=''.join(f'<tr><td>{html.escape(k)}</td><td>{v["first_frequencies_Hz"][0]:.2f}</td><td>{v["peak_contact_force_N"]:.2f}</td></tr>' for k,v in summaries.items() if k in ['order22','stiffness075','stiffness125','clamp10mm','clamp30mm','contact050','contact200'])
    fields=np.load(study/fine/'fields.npz')
    animation={'x':(fields['x']*1000).tolist(),'y':(fields['y']*1000).tolist(),'t':(fields['t']*1000).tolist(),'w':np.round(fields['w']*1000,6).tolist()}
    title='碳纤维板落球冲击：计算结果与缺失数据'
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif;background:#edf2f4;color:#183341;margin:0}}main{{max-width:1100px;margin:auto;padding:32px}}section{{background:white;padding:24px;margin:18px 0;border-radius:12px}}h1{{font-size:30px}}h2{{font-size:22px}}table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{border-bottom:1px solid #dce5e9;padding:9px;text-align:left}}svg{{width:100%;height:auto;font-family:system-ui}}.note{{border-left:5px solid #dc8035;background:#fff4e5;padding:16px}}canvas{{max-width:100%;height:auto}}a{{color:#006b80}}input{{width:65%}}</style>
<main><h1>{title}</h1><p>500×400×2 mm · 周边框架夹持 · PZT-5A名义测点 · 数值代理模型</p>
<p class="note"><b>已实际求解，未实物验证；局部冲击/原始应变尚未充分空间收敛。</b> 输出是板位移与基底应变，不是PZT电压，不预测损伤或无损阈值。</p>
<section><h2>模型与输入</h2><p>完整板面Kirchhoff薄板，Rayleigh–Ritz固支基函数，质量归一化模态；落球自由度与单边Hertz接触耦合，velocity-Verlet时间积分。未拼接人工波包。</p><p>外形和密度来自订单及商家；20 mm夹持宽度、50/50等效0/90刚度混合及Hertz压入关系均为临时假设。球质量 {s['ball_mass_kg']*1e3:.4f} g、入射能量 {s['incident_energy_J']*1e3:.4f} mJ（8 mm钨钢球，160 mm落高，按论文密度推算）。完整板名义质量0.66 kg，自由跨内质量0.54648 kg。</p><p>缺失数据如何获取：<a href="缺失数据与获取方法.md">逐项清单</a> · <a href="simulation_config.json">本次数值输入</a> · <a href="specimen.json">实物已知与未知</a></p></section>
<section><h2>板面位移动画（真实计算数组）</h2><p>俯视图，x沿500 mm长边、y沿400 mm短边；灰色为假设夹持区。方片为S1–S4，十字为冲击点。颜色是位移mm，采用全部帧统一色标，未按几何尺度放大变形。</p><canvas id="field" width="900" height="620"></canvas><p><button id="play">播放 / 暂停</button> <input id="time" type="range" min="0" max="{len(animation['t'])-1}" value="1"><span id="clock"></span></p></section>
<section><h2>已知数值检验与边界</h2><p>各向同性方形固支板特例无量纲基频参数 {original['checks']['isotropic_square_frequency_parameter']:.6f}，参考约35.99；基函数边缘位移和转角严格为零。此检验证明基本离散实现，不证明实物参数准确。</p><table><tr><th>每方向阶数</th><th>一阶频率 Hz</th><th>力峰值 N</th><th>冲击点峰值 mm</th><th>能量最大相对误差</th></tr>{rows}</table><p>最后两档{orders[-2]}→{orders[-1]}全时程相对L2：接触力 {100*change['force']:.2f}%，冲击点位移 {100*change['impact_w']:.2f}%，S1应变 {100*change['S1_strain']:.2f}%。空间误差不能归到材料参数，当前局部输出不应标为收敛。</p><p>22阶时间步减半：力 {100*original['checks']['halfdt_relative_L2']['force']:.4f}%，S1应变 {100*original['checks']['halfdt_relative_L2']['S1_strain']:.4f}%。时间步检查对应22阶，不外推成全部高阶工况的验证。</p></section>
<section>{figures[0]}{figures[1]}{figures[2]}<p>中心冲击与对称边界下四通道相同是模型对称性的结果；偏心工况用于观察通道差异，仍是22阶诊断结果。曲线是原始机械输出，未模拟真实模拟滤波，不可直接作为DAQ电压波形或ToA精度依据。</p></section>
<section><h2>单因素假设敏感性（同为22阶，非收敛预测）</h2><table><tr><th>工况</th><th>一阶 Hz</th><th>力峰值 N</th></tr>{sensitivity}</table><p>stiffness：整体弯曲刚度0.75/1.25倍；clamp：夹持宽度10/30 mm；contact：接触系数0.5/2倍。这些范围是诊断选择，不是实物误差区间。局部峰值受空间截断影响，不能用此表给缺失参数影响排序。</p></section>
<section><h2>最高阶时间步检查</h2><p>最高阶时间步减半的全时程L2：接触力 {100*original['checks']['finest_halfdt_relative_L2']['force']:.4f}%，S1应变 {100*original['checks']['finest_halfdt_relative_L2']['S1_strain']:.4f}%。它不能代替空间收敛。</p></section>
<section><h2>尚不能计算的量</h2><p>PZT电压、实际损伤面积、分层发生阈值、实验RMSE及定位精度。需先取得实物夹持/材料/接触/PZT/胶层/电路数据与独立实测记录。薄板模型也缺少横向剪切、旋转惯量、面内非线性及局部3D接触，后续应据目标频段决定升级。</p><p><a href="computed_metrics.json">全部指标JSON</a> · <a href="缺失数据与获取方法.md">缺失数据与获取方法</a></p></section></main>
<script>const fieldData={json.dumps(animation,separators=(',',':'))}; const c=document.getElementById('field'),ctx=c.getContext('2d'),slider=document.getElementById('time');
const peak=Math.max(...fieldData.w.map(a=>Math.max(...a.map(Math.abs))));
function draw(){{let i=+slider.value;ctx.clearRect(0,0,900,620);const px=x=>75+x*1.5,py=y=>600-y*1.35;ctx.fillStyle='#c8d1d7';ctx.fillRect(px(0),py(400),750,540);const nx=fieldData.x.length,ny=fieldData.y.length;
for(let iy=0;iy<ny-1;iy++)for(let ix=0;ix<nx-1;ix++){{let v=fieldData.w[i][iy*nx+ix]/peak,lo=Math.round(245-180*Math.abs(v));ctx.fillStyle=v>=0?`rgb(220,${{lo}},${{lo}})`:`rgb(${{lo}},${{lo}},220)`;ctx.fillRect(px(fieldData.x[ix]),py(fieldData.y[iy+1]),(fieldData.x[ix+1]-fieldData.x[ix])*1.5+1,(fieldData.y[iy+1]-fieldData.y[iy])*1.35+1);}}
ctx.font='16px sans-serif';ctx.fillStyle='#173849';ctx.fillText('y / mm ↑',5,40);ctx.fillText('x / mm →',730,618);ctx.fillText('0',60,618);ctx.fillText('500',810,618);ctx.fillText('400',30,65);
[[75,75],[425,75],[425,325],[75,325]].forEach((p,j)=>{{ctx.strokeStyle='#09282e';ctx.strokeRect(px(p[0]-7.5),py(p[1]+7.5),22.5,20.25);ctx.fillText('S'+(j+1),px(p[0])+15,py(p[1]));}});ctx.beginPath();ctx.moveTo(px(250)-8,py(200));ctx.lineTo(px(250)+8,py(200));ctx.moveTo(px(250),py(200)-8);ctx.lineTo(px(250),py(200)+8);ctx.stroke();ctx.fillText('统一色标：蓝 −'+peak.toFixed(4)+' / 红 +'+peak.toFixed(4)+' mm',220,28);document.getElementById('clock').textContent=fieldData.t[i].toFixed(2)+' ms';}}
slider.oninput=draw;let timer=null;document.getElementById('play').onclick=()=>{{if(timer){{clearInterval(timer);timer=null;}}else timer=setInterval(()=>{{slider.value=(+slider.value+1)%fieldData.t.length;draw();}},100);}};draw();</script></html>'''
    (ROOT/'冲击仿真结果.html').write_text(page,encoding='utf8')
    manifest={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest() for q in ROOT.rglob('*') if q.is_file() and '__pycache__' not in str(q) and q.name!='manifest.json'}
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print(json.dumps({'finest':fine,'last_relative_L2':change},indent=2))


if __name__=='__main__':main()
