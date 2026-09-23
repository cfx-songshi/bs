"""Inventory and stage an explicit non-paper snapshot, including ignored results.

Large solver files are pending storage resolution; never claim full backup.
"""
import collections,json,os,re,subprocess,hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review'/'cloud_sync_20260924';OUT.mkdir(exist_ok=True)
SKIP_DIRS={'.git','.venv','venv','vendor','__pycache__','node_modules','.mplconfig','mplcache'}
PAPER_DIRS={'参考文献','source_text','inspection','explanation_sources','ref_figures'}
RAW={'.abq','.pac','.odb','.stt','.mdl','.res','.prt','.sel','.odb_f'}
records=[];included=[]
for base,dirs,files in os.walk(ROOT):
    dirs[:]=[d for d in dirs if d not in SKIP_DIRS]
    for name in files:
        p=Path(base)/name;rel=p.relative_to(ROOT).as_posix()
        if p.is_symlink():raise RuntimeError('Review symlink before staging: '+rel)
        size=p.stat().st_size;suf=p.suffix.lower();status='included';reason='project file or completed simulation result'
        if suf=='.pdf' or any(d in PAPER_DIRS for d in p.relative_to(ROOT).parts) or re.search(r'/P\d+-p\d+\.png$',rel):
            status='excluded_paper';reason='paper/reference source or extracted paper content'
        elif name.startswith(('~$','.env')) or suf in ('.env','.lck','.pid','.cid','.app_cache','.com') or re.match(r'abaqus\.rpy(?:\.\d+)?$',name):
            status='excluded_temporary';reason='environment, lock, cache or generated launcher'
        elif suf in RAW and size>=100*1024**2:
            status='pending_large_file';reason=('exceeds confirmed remote LFS 2 GiB per-file limit' if size>2147483648 else 'bulk solver archive pending storage plan: total about 94 GiB, local free about 9 GiB; cannot stage full LFS archive')
        elif size>100*1024**2 and suf not in ('.npz',):
            raise RuntimeError('Unreviewed large non-solver file: '+rel)
        record=dict(path=rel,bytes=size,status=status,reason=reason)
        if status=='included':
            # Scan small textual payloads; report only paths, never matching secrets.
            if suf in ('.py','.ps1','.json','.md','.txt','.html','.js','.yml','.yaml') and size<2*1024**2:
                s=p.read_text(encoding='utf-8',errors='replace')
                if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}',s):
                    raise RuntimeError('Possible credential requires review: '+rel)
            included.append(rel)
        records.append(record)
counts=collections.Counter(x['status'] for x in records)
sizes=collections.Counter()
for x in records:sizes[x['status']]+=x['bytes']
manifest=dict(scope='D:/bs_thesis; external D:/abaqus_runs not part of this requested folder',complete_backup=False,
    remote='git@github.com:cfx-songshi/bs.git',branch='main',
    remote_probe={'file':'acc_n02.abq','bytes':4402044928,'http_object_error':422,'message':'Size must be less than or equal to 2147483648'},
    counts=dict(counts),bytes_by_status=dict(sizes),files=records)
(OUT/'upload_inventory.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
lines=['# 非论文项目快照上传清单（2026-09-24）','',
'**这是部分备份，不是全量上传。第二轮已完成；上传仍有大文件问题，暂不关机。**','',
'GitHub LFS 对 acc_n02.abq（4,402,044,928 字节）的 batch 请求已明确返回 422：单文件必须 ≤2,147,483,648 字节。完整项目数据约 94 GiB，本地剩余约 9 GiB，不能一次性生成完整 LFS 对象副本。未购买额度或删除原始结果。','',
'本次包含代码、交接与指标、PPT/讲解稿、GIF/PNG、NPZ/CSV、输入 deck、诊断读数以及低于 100 MiB 的已保存求解器文件。≥100 MiB 的原始求解器文件等待确定容量与存储方案；并非这些文件全部超过远端单文件上限。具体范围以 JSON 逐文件清单为准。论文原文/提取素材、环境、缓存、锁与临时启动脚本排除。第三轮未启动。原始损伤场和 restart 主文件未全部上传，云端暂不能凭此快照完整续算。','',
'| 状态 | 文件数 | GiB |','|---|---:|---:|']
lines += [f'| {k} | {counts[k]} | {sizes[k]/1024**3:.3f} |' for k in counts]
lines += ['','## 待解决的大文件','', '| 路径 | GiB | 原因 |','|---|---:|---|']
lines += [f"| `{x['path']}` | {x['bytes']/1024**3:.3f} | {x['reason']} |" for x in records if x['status']=='pending_large_file']
(OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
included+=['review/cloud_sync_20260924/upload_inventory.json','review/cloud_sync_20260924/README.md']
# Explicit list overrides broad ignore rules without including paper content.
listing=ROOT/'.git'/'cloud_snapshot_paths.nul'
listing.write_bytes(b'\0'.join(p.encode('utf8') for p in sorted(set(included)))+b'\0')
print(json.dumps({'counts':dict(counts),'GiB':{k:round(v/1024**3,3) for k,v in sizes.items()}},ensure_ascii=False))
print('stage_list',listing)
