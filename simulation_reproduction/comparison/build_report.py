from pathlib import Path
import re,html,base64,hashlib,json,shutil
P=Path(__file__).resolve().parent;B=Path('E:/毕设知识库/simulation_reproduction')
for src,dst in [('Zhao_2025_Smart_Mate_11.png','P3-p11.png'),('In_Situ_Monitoring_o_7.png','P5-p7.png'),('Embedded_Piezoresist_11.png','P6-p11.png'),('A_Hybrid_Multimodel-_8.png','P7-p8.png')]:
 shutil.copyfile(B/'inspection'/src,P/dst)
for name in ['localization_sensitivity.png','plate_convergence.png','gear.png','joint_net_tension.png','joint_shear_out.png','joint_bearing.png','faults.png']:
 shutil.copyfile(B/'results'/name,P/name)
def inline(t):
 t=html.escape(t)
 t=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'<a href="\2">\1</a>',t)
 t=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',t)
 return t
lines=(P/'论文与仿真逐项对比分析.md').read_text(encoding='utf8').splitlines();out=[];i=0
while i<len(lines):
 line=lines[i]
 if not line.strip():i+=1;continue
 if line.startswith('#'):
  n=len(line)-len(line.lstrip('#'));out.append(f'<h{n}>'+inline(line[n:].strip())+f'</h{n}>');i+=1
 elif line.startswith('|'):
  rows=[]
  while i<len(lines) and lines[i].startswith('|'):rows.append(lines[i]);i+=1
  out.append('<div class="table-wrap"><table>')
  for j,r in enumerate(rows):
   if j==1 and re.fullmatch(r'[| :\-]+',r):continue
   tag='th' if j==0 else 'td';out.append('<tr>'+''.join(f'<{tag}>'+inline(c.strip())+f'</{tag}>' for c in r.strip('|').split('|'))+'</tr>')
  out.append('</table></div>')
 elif line.startswith('!['):
  alt,name=re.fullmatch(r'!\[(.*?)\]\((.*?)\)',line).groups();img=P/name;assert img.exists(),name
  out.append('<figure><img loading="lazy" alt="'+html.escape(alt)+'" src="data:image/png;base64,'+base64.b64encode(img.read_bytes()).decode()+'"><figcaption>'+html.escape(alt)+'</figcaption></figure>');i+=1
 else:
  para=[line];i+=1
  while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','![')):para.append(lines[i]);i+=1
  out.append('<p>'+inline(' '.join(para))+'</p>')
css='''body{max-width:1100px;margin:32px auto;padding:0 22px;font:16px/1.85 "Microsoft YaHei",sans-serif;color:#243340;background:#fff}h1{font-size:28px}h2{margin-top:42px;border-bottom:2px solid #b5c8d1;padding-bottom:6px}h3{font-size:19px;margin-top:30px}a{color:#086c83}strong{color:#124b60}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.65}th,td{border:1px solid #c8d4d9;padding:9px;text-align:left;vertical-align:top}th{background:#edf4f6}.table-wrap{overflow:auto}figure{margin:24px 0}img{display:block;width:100%;height:auto;max-width:980px;margin:auto}figcaption{text-align:center;font-size:14px;color:#546673}@media print{body{max-width:none;font-size:11pt}h2{break-after:avoid}figure,table{break-inside:avoid}a{color:inherit}}'''
(P/'论文与仿真逐项对比分析.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>论文与仿真逐项对比分析</title><style>'+css+'</style><body>'+''.join(out)+'</body></html>',encoding='utf8')
inputs=list(B.glob('*.py'))+list((B/'guided_wave_v2').glob('*.py'))+list((B/'guided_wave_v2').glob('*.npz'))+list((B/'results').glob('*.json'))+[B/'results'/n for n in ['ae_dataset.npz','faults_traces.npz','joint_surrogates.npz']]+list(B.parent.glob('*.pdf'))
manifest={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs}
(P/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
outputs={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in P.iterdir() if f.is_file() and f.name!='analysis_manifest.json'}
(P/'analysis_manifest.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2),encoding='utf8')
print('Report generated:',len(lines),'lines;',len(outputs),'output files;',len(inputs),'input hashes.')
