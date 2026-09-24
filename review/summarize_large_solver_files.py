"""Build a compact report and GIF package for the 107 pending solver files.

Uses traceable ODB exports and validated repeat-impact metrics; never deletes raw data.
"""
import collections,html,json,shutil,subprocess,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/large_file_summary_20260924'
OLD=ROOT/'review/simulation_gifs_20260923'
NEW=OUT/'new_animations'
for folder in ('gifs','posters','figures'): (OUT/folder).mkdir(exist_ok=True)
read=lambda p:json.loads(p.read_text(encoding='utf8'))
save=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
inventory=read(ROOT/'review/cloud_sync_20260924/upload_inventory.json')
pending=[x for x in inventory['files'] if x['status']=='pending_large_file']
groups=collections.defaultdict(list)
for item in pending:groups[str((ROOT/item['path']).with_suffix(''))].append(item)
cases=read(OLD/'case_manifest.json')+read(NEW/'case_manifest.json')
clips=read(OLD/'manifest.json')+read(NEW/'manifest.json')
repeat=read(ROOT/'simulation_reproduction/impact_wave_3d/repeat_impact_summary.json')
hits=[x for x in repeat['stages'] if x['kind']=='impact']
assert len(pending)==107 and len(groups)==35 and len(hits)==2
errors=read(NEW/'render_errors.json');assert not errors,errors

# Build one chronological overview of the actual two-hit sequence, keeping real sources.
seq=OUT/'repeat_sequence';seq.mkdir(exist_ok=True)
sequence=[]
for i,stage in enumerate(repeat['stages']):
    matched=[x for x in clips if str(Path(x['source']))==str(Path(stage['metrics']['odb'])) and x['step']==stage['metrics']['step']]
    assert len(matched)==1,(stage['job'],len(matched))
    sequence.append(dict(matched[0],simulation_identity='formal_repeat_030J_two_hits',
        simulation_name='repeat_030J_two_hits',sequence_order=i))
save(seq/'manifest.json',sequence)
subprocess.run([sys.executable,str(ROOT/'review/merge_gifs_by_simulation.py'),str(seq)],check=True)
overview=read(seq/'case_manifest.json')[0]
shutil.copyfile(overview['gif'],OUT/'gifs/repeat_030J_two_hits.gif')
shutil.copyfile(overview['poster'],OUT/'posters/repeat_030J_two_hits.png')

records=[]
for identity,files in groups.items():
    odb=Path(identity+'.odb');job=odb.stem
    selected=[x for x in cases if str(odb) in x['sources']]
    relevant=[x for x in clips if str(odb)==str(Path(x['source']))]
    relevant.sort(key=lambda x:x.get('sequence_order',0))
    sta=odb.with_suffix('.sta')
    success=sta.exists() and 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in sta.read_text(errors='replace')
    entry=dict(job=job,source_odb=str(odb),large_files=files,large_bytes=sum(x['bytes'] for x in files),
        completed=success,steps=[],gif=None,poster=None,category='缺少过程帧')
    for file in files:
        p=ROOT/file['path'];assert p.exists() and p.stat().st_size==file['bytes'],str(p)
    if selected:
        assert len(selected)==1
        chosen=selected[0];key=chosen['key']
        dest=OUT/'gifs'/(key+'.gif');poster=OUT/'posters'/(key+'.png')
        shutil.copyfile(chosen['gif'],dest);shutil.copyfile(chosen['poster'],poster)
        entry.update(gif=dest.relative_to(OUT).as_posix(),poster=poster.relative_to(OUT).as_posix(),
                     category=chosen['group'],caveats=chosen['caveats'])
        with Image.open(dest) as im:
            entry['gif_frames']=im.n_frames
            for n in range(im.n_frames):im.seek(n);im.load()
    else:
        assert job=='grade'
        entry['caveats']=['grade 的求解状态为成功，但 ODB 的 IMPACT 步不足两帧；不能从单帧构造真实过程。']
    for clip in relevant:
        z=np.load(clip['data']);top=z['top_rows'];u=z['values'][:,:,2][:,top]
        e=dict(step=clip['step'],frames=clip['frames'],source_frames=clip['source_frames'],
               time_start_us=float(z['times'][0]*1e6),time_end_us=float(z['times'][-1]*1e6),
               max_abs_top_U3_sampled_um=float(np.max(abs(u))*1e6) if clip['field']=='U' else None,
               field=clip['field'],source_data=clip['data'])
        for k in ('ALLDMD','ALLKE','ALLIE'):
            if 'hist_'+k in z:
                v=z['hist_'+k][:,1];e[k+'_last_mJ']=float(v[-1]*1000);e[k+'_delta_mJ']=float((v[-1]-v[0])*1000)
        entry['steps'].append(e)
    records.append(entry)
records.sort(key=lambda x:(x['category'],x['source_odb']))

plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
fig,axes=plt.subplots(1,3,figsize=(14,4.4),layout='constrained')
dmd=[x['metrics']['energy']['ALLDMD']['last_J']*1000 for x in hits]
axes[0].bar(['第1次','第2次'],dmd,color=['#527eab','#13958f'])
axes[0].set(ylabel='累计 ALLDMD（mJ）',ylim=(0,1.12),title='累计损伤耗能')
for i,v in enumerate(dmd):axes[0].text(i,v+.025,f'{v:.6f}',ha='center')
for i,x in enumerate(hits):
    lo,hi=x['metrics']['energy_equivalent_radius_mm']
    axes[1].plot([lo,hi],[i,i],lw=9,color=['#527eab','#13958f'][i],solid_capstyle='round')
    axes[1].text((lo+hi)/2,i+.14,f'{lo:.4f}–{hi:.4f} mm',ha='center')
axes[1].set(yticks=[0,1],yticklabels=['第1次','第2次'],ylim=(-.4,1.5),xlim=(0,.95),
            xlabel='能量等价圆半径（mm）',title='能量换算区间，不是几何边界')
for i,x in enumerate(hits):
    inter=x['metrics']['interfaces'];h=np.array([v['height_mm'] for v in inter]);d=[v['max_CSDMG'] for v in inter]
    axes[2].barh(h+(i-.5)*.08,d,height=.07,label=f'第{i+1}次')
axes[2].set(xlim=(0,1),xlabel='各界面 max CSDMG',ylabel='界面高度（mm）',title='界面损伤略有增加');axes[2].legend()
fig.savefig(OUT/'figures/two_hit_comparison.png',dpi=160);plt.close(fig)

total=sum(x['bytes'] for x in pending)/1024**3
growth=(dmd[1]/dmd[0]-1)*100
lines=['# 107 个大型仿真文件：结果总结与过程动画','',
f'本报告对应未上传清单中的 **107 个文件，合计 {total:.3f} GiB，归属于 35 个 Abaqus 作业**。同一作业的 ODB 与续算文件不重复算成独立试验。',
'', '文件构成为 30 个 ODB、35 个 ABQ、31 个 PAC、11 个 STT。ODB 提供可读回的场/历史结果；其余为求解器状态与打包辅助文件等，不逐个制作重复动画。报告以同名 ODB 的导出数据、已校验结果 JSON 和权威交接文档为依据，并未把内部状态文件当成独立物理结果重新求解。',
'', '**交付：34 个作业 GIF + 1 个两次冲击全过程汇总 GIF，共 35 个 GIF。** 原始文件保持不变；这些紧凑成果不能替代 ODB 和 restart 原始状态，也不能单凭 GIF 在云端续算。',
'', '## 1. 当前最重要的结论','',
f'两次同点约 0.300 J 落球均完成，第三次未运行。累计 ALLDMD 从 {dmd[0]:.6f} 增至 {dmd[1]:.6f} mJ，第二次新增 {dmd[1]-dmd[0]:.6f} mJ，相对增加 {growth:.2f}%。这是当前数值模型下的小幅累积，不能凭两次结果认定损伤饱和，也不能外推实际疲劳寿命。',
'', '[播放两次冲击全过程](gifs/repeat_030J_two_hits.gif)：第1次冲击 → 数值消振 → 球复位 → 入射速度准备 → 第2次冲击。段落保留各分析步的局部物理时间；各段以同样帧播放时长展示，不意味着真实等待时间相同。',
'', '![两次冲击对比](figures/two_hit_comparison.png)','',
'| 次数 | 累计 ALLDMD / mJ | 本次增量 / mJ | 能量等价半径 / mm | 峰值力 / N | 最大向下位移 / µm | 反弹比 |',
'|---|---:|---:|---|---:|---:|---:|']
for x in hits:
    m=x['metrics'];lo,hi=m['energy_equivalent_radius_mm']
    lines.append(f"| {x['hit']} | {m['energy']['ALLDMD']['last_J']*1e3:.6f} | {m['energy']['ALLDMD']['delta_J']*1e3:.6f} | {lo:.4f}–{hi:.4f} | {m['ball']['force_peak_N']:.3f} | {m['centre']['peak_downward_um']:.3f} | {m['ball']['rebound_ratio']:.5f} |")
lines += ['', '数据来源：`simulation_reproduction/impact_wave_3d/repeat_impact_summary.json`，由 Abaqus ODB 读数器完成全阶段连续性与能量检查；本报告复用已校验的数值，不把 GIF 抽帧峰值代替历史输出峰值。','',
'## 2. 分层 footprint 与中间阶段','',
'两次冲击后均有 4 个受损界面。下面面积是节点控制面积的阈值估计，各界面不可简单视为同一圆形损伤区。','',
'| 界面高度 / mm | 第1次 max D | 第2次 max D | 第1次 D>0.01 面积 / mm² | 第2次 D>0.01 面积 / mm² | 第2次最远受损半径 / mm |',
'|---|---:|---:|---:|---:|---:|']
for a,b in zip(hits[0]['metrics']['interfaces'],hits[1]['metrics']['interfaces']):
    lines.append(f"| {b['height_mm']:.3f} | {a['max_CSDMG']:.6f} | {b['max_CSDMG']:.6f} | {a['area_D_gt_0p01_mm2']:.6f} | {b['area_D_gt_0p01_mm2']:.6f} | {b['max_damage_radius_mm']:.6f} |")
lines += ['', '两次冲击的 D≥0.95 面积均为 0；存在局部部分损伤，并不等于出现完全断开的圆孔。第二次主要体现既有区域的损伤程度增加，1.000 mm 界面的阈值面积略有扩展。','',
'消振末段板机械能为 1.56146e-5 J、最大速度 0.0226034 m/s，通过所设静止判据。消振、复位和入射准备三个阶段 ALLDMD 增量均为 0；不能把球准备过程的动能增长误认为板损伤增长。','',
'## 3. 其他作业应如何解释','',
'- 当前单次标定 `imp_lo / imp_mid / imp_hi`：0.100 / 0.300 / 0.794 J，交接文档记录 ALLDMD 约 0.0966 / 0.9267 / 15.11 mJ；用于单次能量对照，不是三次累积。',
'- 当前导波 `wav_base / wav_d03_r08 / wav_d08_r31`：无损、0.8 mm、3.1 mm 预置脱黏对照；交接文档记录两档 R1/R2 为 0.0547/0.0463 与 1.50/1.33。这些导波不是第二轮冲击后新跑的结果。',
'- `grade_*`、`impact_*`、`wave_*`、`wav_d03 / wav_d08` 等为早期网格或参数对照；旧半径导波不能替代修正半径版本。',
'- `kdef / kply_* / ksoft`、`scope_*` 为界面刚度、接触范围和数值稳定性对照。默认刚度的失稳机制仍未查清；成功结束不等于物理或数值验收合格。',
'- `interrupted_20260923_133902/acc_n02_relax1` 是中断归档，仅作诊断；对应完整消振作业位于父目录，已另列动画。',
'- `grade` 虽有求解成功标记，但仅有不足两帧的场输出，无法制作真实过程 GIF。未伪造动画。','',
'## 4. 必须随结果保留的限制','',
'材料强度、断裂能采用有出处的替代值：朱国华等，复合材料学报 40(6), 3626–3639 (2023)，DOI 10.13801/j.cnki.fhclxb.20220720.002；并非本试件实测标定。接触型黏聚刚度显式取 2.37e13 Pa/m。',
'', '冲击应力场未收敛，界面刚度带来约两倍面积敏感性；未与实物实验验证。数值消振参数与静止判据为工程假设，阻尼敏感性尚未完成。小半径导波存在冲击 4 个受损界面与导波 5 个预置界面的映射差异。',
'', 'ALLDMD/Gc 得到跨界面汇总的完全断裂能量等价面积；部分损伤也贡献耗能。因此等价圆半径区间不是几何损伤半径的严格上下界，不能复制到每一个界面。',
'', 'GIF 仅展示已保存数值场，最多选取每步 51 帧、每帧 150 ms；导波场可能抽取显示节点。单段色标固定，跨图/跨段可能不同。位移场和能量不是 PZT 电压；多段拼接只用于展示，不会生成新的物理解。','',
'## 5. 35 个作业及 GIF 索引','',
'数值列来自各步已导出的 ODB 历史/场记录。U3 峰值仅指抽取帧与显示顶面节点中的最大绝对值，不是严格全场或冲击中心时程峰值。','',
'| 作业（目录用于区分重名） | 大文件数 | GiB | 状态 | 过程 GIF |',
'|---|---:|---:|---|---|']
for x in records:
    label=Path(x['source_odb']).parent.name+'/'+x['job'];link=f"[播放]({x['gif']})" if x['gif'] else '缺少过程帧'
    lines.append(f"| {label} | {len(x['large_files'])} | {x['large_bytes']/1024**3:.3f} | {'求解完成' if x['completed'] else '中断/未完成'} | {link} |")
lines += ['', '## 6. 按分析步的直接读数','',
'| 作业 / 分析步 | 物理时间范围 / µs | 显示帧 / 保存帧 | ALLDMD 末值 / mJ | 抽样顶面 max abs U3 / µm |',
'|---|---|---|---:|---:|']
for x in records:
    for s in x['steps']:
        d=s.get('ALLDMD_last_mJ');u=s['max_abs_top_U3_sampled_um']
        ds='未输出' if d is None else f'{d:.6g}';us='非U场' if u is None else f'{u:.6g}'
        lines.append(f"| {Path(x['source_odb']).parent.name}/{x['job']} / {s['step']} | {s['time_start_us']:.3f}–{s['time_end_us']:.3f} | {s['frames']}/{s['source_frames']} | {ds} | {us} |")
lines += ['', '## 7. 文件与追溯','',
'`large_file_manifest.json` 覆盖每一个待上传大文件及其所属作业、原始路径、大小、GIF 和读数来源；`repeat_impact_summary.json` 保存本轮正式读数副本。HTML 报告可直接播放动画，Markdown 便于其他 agent 引用。原始 87.35 GiB 文件仍保留本地，未删除或压缩替代。']
report='\n'.join(lines)+'\n'
(OUT/'SUMMARY.md').write_text(report,encoding='utf8')
save(OUT/'large_file_manifest.json',dict(large_file_count=len(pending),large_bytes=sum(x['bytes'] for x in pending),jobs=records,
    overview_gif='gifs/repeat_030J_two_hits.gif',source_inventory='review/cloud_sync_20260924/upload_inventory.json'))
save(OUT/'repeat_impact_summary.json',repeat)

# Small Markdown renderer for this generated report (no external web dependencies).
def inline(s):
    import re
    s=html.escape(s)
    s=re.sub(r'!\[([^]]*)\]\(([^)]+)\)',r'<img class="chart" alt="\1" src="\2">',s)
    s=re.sub(r'\[([^]]*)\]\(([^)]+)\)',r'<a href="\2">\1</a>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',s)
    s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
    return s
body=[];table=False
for line in lines:
    if line.startswith('|'):
        if not table:body.append('<div class="table"><table>');table=True
        if set(line.replace('|','').replace('-','').replace(':','').strip())==set():continue
        body.append('<tr>'+''.join('<td>'+inline(cell.strip())+'</td>' for cell in line.strip('|').split('|'))+'</tr>');continue
    if table:body.append('</table></div>');table=False
    if line.startswith('# '):body.append('<h1>'+inline(line[2:])+'</h1>')
    elif line.startswith('## '):body.append('<h2>'+inline(line[3:])+'</h2>')
    elif line:body.append('<p>'+inline(line)+'</p>')
if table:body.append('</table></div>')
cards=[]
for x in records:
    if not x['gif']:continue
    cards.append('<article><h3>'+html.escape(Path(x['source_odb']).parent.name+'/'+x['job'])+'</h3><img loading="lazy" src="'+x['poster']+'" data-gif="'+x['gif']+'" onclick="this.src=this.dataset.gif" alt="点击播放过程"><p>点击封面播放；<a href="'+x['gif']+'">打开 GIF</a></p><p>'+html.escape('；'.join(x['caveats']))+'</p></article>')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>大型仿真文件总结</title><style>body{font:16px/1.7 system-ui;max-width:1200px;margin:35px auto;padding:0 20px;background:#f4f7fa;color:#183347}h1,h2{color:#075d71}a{color:#007b8a}td{padding:8px;border-bottom:1px solid #cbd5df}table{border-collapse:collapse;width:100%;font-size:14px}.table{overflow:auto}tr:first-child{font-weight:bold;background:#dfeaf1}.chart{max-width:100%}code{overflow-wrap:anywhere}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:18px}article{background:white;padding:15px;border-radius:10px}article img{width:100%;cursor:pointer}article p{font-size:13px}@media print{section{display:none}body{background:white}}</style>'''+''.join(body)+'<h2>动画预览：点击封面播放</h2><section>'+''.join(cards)+'</section></html>'
(OUT/'REPORT.html').write_text(page,encoding='utf8')
print('REPORT_COMPLETE',len(records),'jobs',sum(bool(x['gif']) for x in records),'job GIFs + 1 sequence GIF',flush=True)
