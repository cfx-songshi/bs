import json,html,sys
from pathlib import Path
from collections import Counter
root=Path(sys.argv[1]).resolve()
cases=json.loads((root/'case_manifest.json').read_text(encoding='utf-8'))
cases.sort(key=lambda x:(x['group'],x['name']))
old=root/'index.html'
if old.exists() and not (root/'clips_gallery.html').exists():old.rename(root/'clips_gallery.html')
cards=[]
for x in cases:
    gif=Path(x['gif']).relative_to(root).as_posix();png=Path(x['poster']).relative_to(root).as_posix()
    search=html.escape(x['name']+' '+x['group'],quote=True)
    cards.append(f'<article data-search="{search}"><h3>{html.escape(x["name"])}</h3><p>{x["group"]} · {x["segments"]} 段 · {x["duration_s"]:.2f} 秒循环</p><a href="{gif}"><img loading="lazy" src="{png}" alt="封面"></a><p>{html.escape("；".join(x["caveats"]))}</p><a href="{gif}">打开汇总 GIF</a> · <a href="{png}">PNG 封面</a><details><summary>来源</summary>'+ '<br>'.join(html.escape(s) for s in x['sources'])+'</details></article>')
page='''<!doctype html><meta charset="utf-8"><title>每个仿真一个 GIF</title><style>body{font:16px system-ui;background:#f2f5f9;color:#183348;margin:30px}input{padding:12px;width:70%;font:inherit}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:20px}article{background:white;padding:16px;border-radius:12px;overflow-wrap:anywhere}article[hidden]{display:none}img{width:100%}p{font-size:14px}a{color:#007985}h3{margin:0}</style><h1>每个仿真一个 GIF</h1>'''+f'<p>{len(cases)} 个算例汇总 GIF。同一算例多视图/分析步按段播放；不同参数各自独立。<a href="README_PPT_HANDOFF.md">PPT 交接说明</a> · <a href="case_manifest.json">汇总清单</a> · <a href="clips_gallery.html">原分段素材</a></p><input id="q" placeholder="搜索：imp_mid、02_current_wave、order10 等"><main>'+''.join(cards)+'''</main><script>q.oninput=()=>document.querySelectorAll('article').forEach(e=>e.hidden=!e.dataset.search.toLowerCase().includes(q.value.toLowerCase()))</script>'''
old.write_text(page,encoding='utf-8')
readme=root/'README_PPT_HANDOFF.md';text=readme.read_text(encoding='utf-8')
if '## 分段素材的详细记录' in text:text=text.split('## 分段素材的详细记录',1)[1].lstrip()
head=['# 交付入口：每个仿真一个汇总 GIF','',f'**共 {len(cases)} 个算例汇总 GIF，位置：`{root / "00_by_simulation"}`。**','',
'优先使用本目录；`case_manifest.json` 给出每个汇总 GIF 对应的分段、来源、限制和封面。`index.html` 是汇总浏览目录。原分段文件仍保留，详见 `clips_gallery.html` 与 `manifest.json`。','',
'同一 ODB 的分析步、同一算例目录的场数据与响应曲线按段合并；段落标题标明来源与分析步。不同段可能从自身 t=0 开始，合并不是重新求解，也不表示连续载荷历史。不同能量、网格、预置损伤参数不合并。由同一 ODB 导出的旧波场展示只在来源匹配明确时并入该算例。','',
'给其他 agent 的指令可直接复制：','',
f'> 请先阅读 D:\\bs_thesis\\PROJECT_HANDOFF.md 和 {readme}，从 {root / "case_manifest.json"} 选择 GIF 与 PNG 制作汇报 PPT。优先当前冲击和修正半径导波，保留数值来源与未解决问题；不将历史对照、未完成片段或合成数据当作已验证主线结论。','',
'| 分类 | 汇总 GIF 数 |','|---|---:|']
head += [f'| {k} | {v} |' for k,v in sorted(Counter(x['group'] for x in cases).items())]
head += ['','---','','## 分段素材的详细记录','']
readme.write_text('\n'.join(head)+text,encoding='utf-8')
print('FINAL',len(cases),'cases')
