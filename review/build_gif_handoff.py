"""Build portable gallery and PPT handoff from verified rendering receipts."""
import json,html,sys
from pathlib import Path
from collections import Counter
from PIL import Image,ImageDraw

root=Path(sys.argv[1]).resolve()
items=sorted([json.loads(p.read_text(encoding='utf-8')) for p in root.glob('*/*.json') if p.parent.name not in ('_data','00_by_simulation')],key=lambda x:(x.get('group',''),x.get('key','')))
items=[x for x in items if 'gif' in x]
for x in items:
    with Image.open(x['gif']) as im:
        assert im.n_frames==x['frames'],x['gif']
        for i in range(im.n_frames):im.seek(i);im.load()
    x['caption']=Path(x['source']).parent.name+' / '+Path(x['source']).stem+' / '+x.get('step','')+'；'+x['caveat']
    x['ppt_usage']='优先选用' if x['group'].startswith(('01_','02_')) else '仅按分类与限制使用'
(root/'manifest.json').write_text(json.dumps(items,indent=2,ensure_ascii=False),encoding='utf-8')
counts=Counter(x['group'] for x in items)
inventory=[]
for name in ('odb_inventory.json','saved_data_inventory.json'):
    for x in json.loads((root/name).read_text(encoding='utf-8')):
        if x['status'] not in ('processed','exported'):inventory.append(x)
        for o in x.get('outputs',[]):
            if o.get('status')=='no_animation':inventory.append(dict(source=x['source'],**o))
(root/'exclusions.json').write_text(json.dumps(inventory,indent=2,ensure_ascii=False),encoding='utf-8')
lines=['# 仿真 GIF 素材交接（2026-09-23）','',f'素材根目录：`{root}`',f'已验证 {len(items)} 个 GIF，每个有同名 PNG 封面与 JSON 来源说明。数量按“数据文件 / 分析步 / 展示内容”计，不等于独立物理算例数。','',
'## 给制作 PPT 的 agent','',
'先读仓库 PROJECT_HANDOFF.md 的当前结论，再读本文件和 manifest.json。用 index.html 浏览全部动画。当前冲击和修正半径导波优先使用 01_current_impact、02_current_wave。每页保留图注与限制，历史参数对照、流程验证、代理/合成数据不得混称当前有效结果。GIF 用于放映，PNG 用于静态导出或不播放动画的软件。不要使用 _data 中间文件直接充当插图。','',
'## 数据表达与限制','',
'- 原始数值场导出；每段最多选取 51 个已保存时间帧，GIF 每帧 150 ms，循环慢放。时间标记是物理时间，不是视频播放时间；未补造求解帧。高分辨率顶面可能抽取节点，详情见 JSON。',
'- 冲击截面变形比例为 1；导波显示未变形坐标上的位移场。色标在同一 GIF 内固定，不同 GIF 可不同，跨图对比应查看范围。未将机械响应冒充 PZT 电压。',
'- 只有时程的算例显示完整原始曲线与移动时间标记，不能据此重建缺失的全场。薄板 w 向下为正，Abaqus U3 取模型坐标方向。',
'- ALLDMD 是总损伤耗能。能量等价圆半径是跨界面完全断裂能量的等效换算；不是几何损伤边界，也不能直接解释为每个界面的真实半径。',
'- 当前单次标定采用替代材料参数；应力场尚未收敛，无实物验证。小半径导波仍有冲击 4 个受损界面与导波 5 个预置界面的映射差异。',
'- 正式累积序列当前只收录完成的第 1 次冲击。中断归档的松弛片段在 90_incomplete；正在运行且有锁的 ODB 未读取。无帧、失败和无物理时间轴数据见 exclusions.json，不能说这些也已生成完整动画。','',
'## 分类统计','', '| 目录 | GIF 数 |','|---|---:|']
lines += [f'| {k} | {v} |' for k,v in sorted(counts.items())]
lines += ['', '## 当前主线优先素材','', '| 算例 / 步 | GIF | 封面 |','|---|---|---|']
for x in items:
    if x['group'].startswith(('01_','02_')):
        lines.append(f"| {Path(x['source']).stem} / {x.get('step','')} | [{Path(x['gif']).name}]({Path(x['gif']).relative_to(root).as_posix()}) | [PNG]({Path(x['poster']).relative_to(root).as_posix()}) |")
lines += ['', '## 未生成项','']
for x in inventory:lines.append(f"- `{x['source']}` {x.get('step','')}：{x.get('reason',x['status'])}")
(root/'README_PPT_HANDOFF.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
cards=[]
for x in items:
    gif=Path(x['gif']).relative_to(root).as_posix();png=Path(x['poster']).relative_to(root).as_posix()
    title=Path(x['source']).parent.name+' / '+Path(x['source']).stem+' / '+x.get('step','')
    cards.append(f'<article data-search="{html.escape(x["group"]+" "+title,quote=True)}"><h3>{html.escape(title)}</h3><p>{x["group"]}</p><a href="{gif}"><img loading="lazy" src="{png}" alt="{html.escape(title,quote=True)}"></a><p>{html.escape(x["caveat"])}</p><a href="{gif}">打开 GIF</a> · <a href="{png}">PNG 封面</a><details><summary>来源</summary>{html.escape(x["source"])}</details></article>')
page='''<!doctype html><meta charset="utf-8"><title>仿真 GIF 素材目录</title><style>body{font:16px system-ui;background:#f2f5f9;color:#183348;margin:30px}input{padding:12px;width:70%;font:inherit}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:20px}article{background:white;padding:16px;border-radius:12px;overflow-wrap:anywhere}img{width:100%}p{font-size:14px}a{color:#007985}h3{margin:0}</style><h1>仿真 GIF 素材目录</h1>'''+f'<p>{len(items)} 个 GIF；点击封面打开动画。先读 <a href="README_PPT_HANDOFF.md">PPT 交接说明</a>，机器清单见 <a href="manifest.json">manifest.json</a>。</p><input id="q" placeholder="搜索算例名或分类，例如 imp_mid、02_current_wave"><main>'+''.join(cards)+'''</main><script>q.oninput=()=>document.querySelectorAll('article').forEach(e=>e.hidden=!e.dataset.search.toLowerCase().includes(q.value.toLowerCase()))</script>'''
(root/'index.html').write_text(page,encoding='utf-8')
for page,start in enumerate(range(0,len(items),24),1):
    subset=items[start:start+24];sheet=Image.new('RGB',(1160,((len(subset)+3)//4)*200),'#e8edf3');draw=ImageDraw.Draw(sheet)
    for j,x in enumerate(subset):
        with Image.open(x['poster']) as im:im.thumbnail((290,178));sheet.paste(im,(j%4*290,j//4*200))
        draw.text((j%4*290+4,j//4*200+178),x['key'][:41],fill='black')
    sheet.save(root/f'contact_sheet_{page:02d}.jpg')
print('VERIFIED',len(items),'GIFs; exclusions',len(inventory));print(dict(counts))
