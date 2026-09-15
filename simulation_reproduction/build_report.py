"""Build the Chinese report from actual result JSON; standard library only."""
import json,re,html,base64,hashlib,datetime
from pathlib import Path
root=Path(__file__).resolve().parent;out=root/'results'
def load(name):return json.loads((out/(name+'.json')).read_text(encoding='utf8'))
def table(headers,rows):
 return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
doc=(root/'报告正文.md').read_text(encoding='utf8')
ae=load('ae_summary');loc=load('localization_summary');transfer=load('transfer_summary');gear=load('gear_summary')
replacements={
'AE_TABLE':table(['SNR/dB','方法','误差<20 μs/%','误拾取>100 μs/%','全部样本 MAE/μs'],[[r['snr_db'],r['method'],f"{r['within20_percent']:.2f}",f"{r['false_gt100_percent']:.2f}",f"{r['mae_us_all']:.2f}"] for r in ae]),
'LOC_TABLE':table(['ToA 误差幅度/% L/v','有效数/100000','失败/%','有效样本均值/% L','全部样本误差<5%L/%'],[[f"{100*r['toa_error_halfwidth_fraction_of_L_over_v']:.2f}",r['valid_count'],f"{r['failure_percent']:.3f}",f"{r['mean_error_percent_L_valid']:.4f}",f"{r['success_within_5percent_L_all']:.3f}"] for r in loc]),
'PEAK_TABLE':table(['采样率/kHz','整数峰 MAE/μs','插值峰 MAE/μs','失败/1000'],[[r['fs_hz']/1000,f"{r['integer_peak_mae_us']:.4f}",f"{r['parabolic_mae_us']:.4f}",r['invalid']] for r in load('peak_interpolation')]),
'ANIS_TABLE':table(['方向系数 e','有效解平均误差/% L','失败/%'],[[r['anisotropy_e'],f"{r['mean_error_percent_L_valid']:.3f}",f"{r['failure_percent']:.2f}"] for r in load('localization_anisotropy')]),
'TRANSFER_TABLE':table(['目标训练样本数','方法','Accuracy 均值±标准差/%','Macro-F1'],[[8*r['k_per_class'],r['method'],f"{100*r['accuracy_mean']:.2f} ± {100*r['accuracy_std_across_seeds']:.2f}",f"{r['macro_f1_mean']:.4f}"] for r in transfer]),
'GEAR_TABLE':table(['转速/rpm','方法','留出测试数','Accuracy/%','Macro-F1'],[[r['rpm'],r['method'],r['target_test_n'],f"{r['accuracy']*100:.2f}",f"{r['macro_f1']:.4f}"] for r in gear])}
for key,value in replacements.items():doc=doc.replace('{{'+key+'}}',value)
assert '{{' not in doc
(root/'复现实验报告.md').write_text(doc,encoding='utf8')

def inline(s):
 s=html.escape(s)
 s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
 s=re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',s)
 s=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'<a href="\2">\1</a>',s)
 return s

lines=doc.splitlines();body=[];toc=[];i=0;heading=0
while i<len(lines):
 line=lines[i]
 if not line.strip():i+=1;continue
 if line.startswith('#'):
  level=len(line)-len(line.lstrip('#'));text=line[level:].strip();heading+=1
  body.append(f'<h{level} id="s{heading}">{inline(text)}</h{level}>')
  if level==2:toc.append(f'<a href="#s{heading}">{inline(text)}</a>')
 elif line.startswith('|'):
  rows=[]
  while i<len(lines) and lines[i].startswith('|'):
   cols=[c.strip() for c in lines[i].strip('|').split('|')]
   if not all(re.fullmatch(r':?-+:?',c) for c in cols):rows.append(cols)
   i+=1
  body.append('<div class="tablewrap"><table><thead><tr>'+''.join('<th>'+inline(c)+'</th>' for c in rows[0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in row)+'</tr>' for row in rows[1:])+'</tbody></table></div>');continue
 elif line.startswith('!['):
  match=re.fullmatch(r'!\[([^]]*)\]\(([^)]+)\)',line)
  file=root/match[2];assert file.is_file()
  b64=base64.b64encode(file.read_bytes()).decode()
  body.append(f'<figure><img alt="{html.escape(match[1])}" src="data:image/png;base64,{b64}"><figcaption>{inline(match[1])}</figcaption></figure>')
 elif line.startswith('- ') or re.match(r'^\d+\. ',line):
  body.append('<p class="item">'+inline(line)+'</p>')
 else:body.append('<p>'+inline(line)+'</p>')
 i+=1
css='''body{font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif;color:#203142;background:#f1f4f7;margin:0;line-height:1.85}main{max-width:1080px;margin:24px auto;background:white;padding:48px 60px;border-top:6px solid #157b80}h1{font-size:30px;line-height:1.4}h2{margin-top:54px;border-bottom:2px solid #b7d6d6;padding-bottom:10px;color:#145f64}h3{margin-top:32px}p{margin:14px 0}strong{color:#8c3527}code{font-family:Consolas,monospace;background:#f2f4f6;padding:2px 4px;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.6}th{background:#e7f2f2;text-align:left}td,th{padding:10px;border-bottom:1px solid #d5dfe6;vertical-align:top}tr:nth-child(even){background:#fafcfd}.tablewrap{overflow-x:auto;margin:24px 0}img{max-width:100%;height:auto}figure{margin:28px 0}figcaption{text-align:center;color:#617081;font-size:13px}nav{background:#edf5f5;padding:20px}nav a{display:block}a{color:#126d76;overflow-wrap:anywhere}.item{padding-left:18px}.badge{background:#fff1d9;border-left:4px solid #ba7b16;padding:16px} @media(max-width:750px){main{margin:0;padding:24px 18px}h1{font-size:24px}}@media print{body{background:white}main{padding:0;margin:0;border:0}h2{break-before:page}table,figure{break-inside:avoid}nav{display:none}}'''
page='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>论文实验仿真复现报告</title><style>'+css+'</style></head><body><main><div class="badge">已运行的数值复现与合成实验。明确区分论文原值、仿真假设、实际结果及未完成的高保真复现。</div><nav><b>目录</b>'+''.join(toc)+'</nav>'+''.join(body)+'</main></body></html>'
(root/'复现实验报告.html').write_text(page,encoding='utf8')
env=load('environment')
(root/'requirements-lock.txt').write_text('\n'.join(k+'=='+v for k,v in env['packages'].items())+'\n',encoding='utf8')
manifest=[]
for f in sorted(root.glob('*.py'))+sorted(out.glob('*.json'))+sorted(out.glob('*.npz'))+sorted(out.glob('*.pt'))+sorted(out.glob('*.png')):
 if f.name=='deliverable_manifest.json':continue
 manifest.append({'path':str(f.relative_to(root)),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
(out/'deliverable_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf8')
print('Built report:',len(doc),'characters;',len(manifest),'tracked files; HTML bytes',len(page.encode('utf8')))
