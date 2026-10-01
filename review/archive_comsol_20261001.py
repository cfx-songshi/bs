"""Archive three COMSOL projects; delete bulk originals ONLY after remote reconstruction.

Run from any directory. Restartable compression/download. Exact-file deletion only.
"""
import concurrent.futures, datetime, hashlib, json, lzma, os, shutil, subprocess, sys, urllib.request, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREFIX='archives/comsol_archive_20261001'
OUT=ROOT/PREFIX
VERIFY=ROOT/'.git/comsol_remote_verify_20261001'
REVIEW=ROOT/'review/comsol_archive_20261001'
PROJECTS=['comsol_diaz_2025','comsol_he2026','comsol_pfczm_01']
CHUNK=16*1024**2
def now(): return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def save(p,data):
    p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix('.tmp')
    t.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');t.replace(p)
def state(stage,**kw):
    save(REVIEW/'status.json',dict(stage=stage,time=now(),**kw)); print(stage,kw,flush=True)
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT).decode().strip()
def run(args): subprocess.run(args,cwd=ROOT,check=True)
def hashfile(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(CHUNK): h.update(b)
    return h.hexdigest()
def pointer(meta): return f"version https://git-lfs.github.com/spec/v1\noid sha256:{meta['compressed_sha256']}\nsize {meta['compressed_bytes']}\n".encode()
def cache(meta):
    oid=meta['compressed_sha256'];return ROOT/'.git/lfs/objects'/oid[:2]/oid[2:4]/oid
def safe(p,base):
    p=p.resolve();base=base.resolve()
    if not p.is_relative_to(base) or p==base: raise RuntimeError('Unsafe path '+str(p))
    for q in [p,*p.parents]:
        if q==base.parent: break
        if q.is_symlink() or q.is_junction(): raise RuntimeError('Link refused')
    return p
def compress(raw,oid):
    p=OUT/'chunks'/(oid+'.xz')
    if p.exists():
        encoded=p.read_bytes()
        if encoded.startswith(b'version https://git-lfs'): raise RuntimeError('Unexpected pointer before manifest complete')
        if hashlib.sha256(lzma.decompress(encoded)).hexdigest()!=oid: raise RuntimeError('Existing chunk corrupt')
    else:
        encoded=lzma.compress(raw,preset=1);tmp=p.with_suffix('.tmp');tmp.write_bytes(encoded);tmp.replace(p)
    return dict(raw_sha256=oid,raw_bytes=len(raw),path='chunks/'+p.name,compressed_bytes=len(encoded),compressed_sha256=hashlib.sha256(encoded).hexdigest())
def build():
    if (OUT/'manifest.json').exists(): return json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    (OUT/'chunks').mkdir(parents=True,exist_ok=True)
    files=[]
    for name in PROJECTS:
        base=ROOT/'simulation_reproduction'/name
        for p in sorted(base.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts: files.append(safe(p,base))
    state('compressing',files=len(files),bytes=sum(p.stat().st_size for p in files))
    known={};pending={};entries=[]
    def collect(block=False):
        if block: concurrent.futures.wait(pending.values(),return_when=concurrent.futures.FIRST_COMPLETED)
        for oid in [o for o,f in pending.items() if f.done()]: known[oid]=pending.pop(oid).result()
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for i,p in enumerate(files,1):
            s=p.stat();h=hashlib.sha256();parts=[]
            with p.open('rb') as f:
                while raw:=f.read(CHUNK):
                    h.update(raw);oid=hashlib.sha256(raw).hexdigest();parts.append(oid)
                    if oid not in known and oid not in pending:
                        while len(pending)>=32:collect(True)
                        pending[oid]=pool.submit(compress,raw,oid)
                    collect()
            after=p.stat()
            if (s.st_size,s.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('Source changed')
            rel=p.relative_to(ROOT).as_posix()
            bulk=p.relative_to(ROOT/'simulation_reproduction'/p.relative_to(ROOT/'simulation_reproduction').parts[0]).parts[0] in {'runs','recovery_snapshots'}
            entries.append(dict(path=rel,bytes=s.st_size,mtime_ns=s.st_mtime_ns,sha256=h.hexdigest(),chunks=parts,delete_after_verification=bulk))
            state('compressing',file=i,total_files=len(files),last=rel,read_bytes=sum(x['bytes'] for x in entries),unique_chunks=len(known)+len(pending))
        while pending: collect(True)
    m=dict(format='sha256-content-chunks-xz-v1',created=now(),chunk_bytes=CHUNK,source_root=str(ROOT),files=entries,chunks=known,raw_bytes=sum(x['bytes'] for x in entries),stored_bytes=sum(x['compressed_bytes'] for x in known.values()))
    save(OUT/'manifest.json',m);return m
def publish(m):
    state('preparing_lfs',chunks=len(m['chunks']),stored_bytes=m['stored_bytes'])
    (OUT/'.gitattributes').write_text('chunks/*.xz filter=lfs diff=lfs merge=lfs -text\n*.json -text\n',encoding='utf-8')
    for meta in m['chunks'].values():
        p=OUT/meta['path'];c=cache(meta);b=p.read_bytes()
        if b!=pointer(meta):
            if len(b)!=meta['compressed_bytes'] or hashlib.sha256(b).hexdigest()!=meta['compressed_sha256']:raise RuntimeError('Bad chunk')
            c.parent.mkdir(parents=True,exist_ok=True)
            if c.exists():
                if hashfile(c)!=meta['compressed_sha256']:raise RuntimeError('Bad cache')
                p.write_bytes(pointer(meta))
            else: p.replace(c);p.write_bytes(pointer(meta))
        elif not c.exists(): raise RuntimeError('Required local LFS object absent')
    paths=[PREFIX,'review/archive_comsol_20261001.py']
    run(['git','add','-f','--',*paths])
    changed=subprocess.run(['git','diff','--cached','--quiet','--',*paths],cwd=ROOT).returncode
    if changed: run(['git','-c','user.name=cfx-songshi','-c','user.email=z58599517@gmail.com','commit','--only','-m','Archive complete COMSOL project data for verified local cleanup','--',*paths])
    state('uploading',stored_bytes=m['stored_bytes'])
    run(['git','-c','lfs.concurrenttransfers=8','push','origin','main'])
    head=git('rev-parse','HEAD')
    if git('ls-remote','origin','refs/heads/main').split()[0]!=head:raise RuntimeError('Remote mismatch')
    return head
def download(m,commit):
    if shutil.disk_usage(ROOT).free < 1024**3:raise RuntimeError('Insufficient verification workspace; originals retained')
    VERIFY.mkdir(parents=True,exist_ok=True)
    raw=subprocess.check_output(['git','show',commit+':'+PREFIX+'/manifest.json'],cwd=ROOT)
    if json.loads(raw)!=m:raise RuntimeError('Committed manifest mismatch')
    (VERIFY/'manifest.json').write_bytes(raw)
    objects=list(m['chunks'].values())
    for start in range(0,len(objects),100):
        metas=objects[start:start+100]
        auth_run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','git@github.com','git-lfs-authenticate cfx-songshi/bs.git download'],capture_output=True,text=True,timeout=30)
        if auth_run.returncode:raise RuntimeError('Download authorization failed')
        auth=json.loads(auth_run.stdout)
        req=urllib.request.Request(auth['href'].rstrip('/')+'/objects/batch',data=json.dumps(dict(operation='download',transfers=['basic'],objects=[dict(oid=x['compressed_sha256'],size=x['compressed_bytes']) for x in metas])).encode(),headers={**auth.get('header',{}),'Content-Type':'application/vnd.git-lfs+json','Accept':'application/vnd.git-lfs+json'})
        with urllib.request.urlopen(req,timeout=90) as r:actions={o['oid']:o for o in json.load(r)['objects']}
        def fetch(meta):
            p=VERIFY/meta['path'];p.parent.mkdir(parents=True,exist_ok=True)
            if p.exists() and p.stat().st_size==meta['compressed_bytes'] and hashfile(p)==meta['compressed_sha256']:return
            o=actions[meta['compressed_sha256']]
            if o.get('error') or o['size']!=meta['compressed_bytes']:raise RuntimeError('Remote object missing')
            a=o['actions']['download']
            for attempt in range(3):
                try:
                    req=urllib.request.Request(a['href'],headers=a.get('header',{}))
                    with urllib.request.urlopen(req,timeout=120) as r:b=r.read()
                    if len(b)!=meta['compressed_bytes'] or hashlib.sha256(b).hexdigest()!=meta['compressed_sha256']:raise RuntimeError('Download hash mismatch')
                    p.write_bytes(b)
                    # This exact cache is redundant once its independent remote
                    # download is verified. Reclaim it to avoid two archive copies.
                    c=safe(cache(meta),ROOT/'.git/lfs/objects')
                    if c.exists() and c.stat().st_size==meta['compressed_bytes'] and hashfile(c)==meta['compressed_sha256']:c.unlink()
                    return
                except Exception:
                    if attempt==2:raise RuntimeError('Download failed after retries') from None
                    time.sleep(2)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(fetch,metas))
        state('downloading_for_verification',done=min(start+100,len(objects)),total=len(objects))
    def check(e):
        h=hashlib.sha256();n=0
        for oid in e['chunks']:
            meta=m['chunks'][oid];b=(VERIFY/meta['path']).read_bytes()
            if hashlib.sha256(b).hexdigest()!=meta['compressed_sha256']:raise RuntimeError('Chunk changed')
            data=lzma.decompress(b)
            if len(data)!=meta['raw_bytes'] or hashlib.sha256(data).hexdigest()!=oid:raise RuntimeError('Raw chunk mismatch')
            h.update(data);n+=len(data)
        if n!=e['bytes'] or h.hexdigest()!=e['sha256']:raise RuntimeError('Restored file mismatch')
        return dict(path=e['path'],bytes=n,sha256=h.hexdigest(),verified=True)
    state('verifying_remote_reconstruction')
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:files=list(pool.map(check,m['files']))
    save(REVIEW/'remote_verification.json',dict(commit=commit,time=now(),all_verified=True,manifest_sha256=hashlib.sha256(raw).hexdigest(),method='Fresh remote downloads; full reconstructed file SHA-256',files=files))
def cleanup(m,commit):
    state('auditing_originals_before_deletion')
    ps="@(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match 'comsol|matlab' }).Count"
    if int(subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True).strip()):raise RuntimeError('Solver process active; retaining originals')
    targets=[]
    for e in m['files']:
        if not e['delete_after_verification']:continue
        p=safe(ROOT/e['path'],ROOT/'simulation_reproduction')
        parts=p.relative_to(ROOT/'simulation_reproduction').parts
        if parts[0] not in PROJECTS or parts[1] not in {'runs','recovery_snapshots'}:raise RuntimeError('Deletion outside explicit scope')
        if not p.exists():raise RuntimeError('Missing original before cleanup')
        s=p.stat()
        if s.st_size!=e['bytes'] or s.st_mtime_ns!=e['mtime_ns'] or hashfile(p)!=e['sha256']:raise RuntimeError('Original changed; retaining data')
        targets.append(e)
    save(REVIEW/'deletion_plan.json',dict(archive_commit=commit,files=targets))
    deleted=[]
    for e in targets:
        p=safe(ROOT/e['path'],ROOT/'simulation_reproduction');s=p.stat()
        if s.st_size!=e['bytes'] or s.st_mtime_ns!=e['mtime_ns']:raise RuntimeError('Original changed during cleanup')
        p.unlink();deleted.append(e)
        save(REVIEW/'deletion_receipt.json',dict(archive_commit=commit,time=now(),files=deleted,deleted_bytes=sum(x['bytes'] for x in deleted),status='complete' if len(deleted)==len(targets) else 'in_progress'))
    # Remove only exact verified temporary/cache payloads from this archive.
    reclaimed=0
    for meta in m['chunks'].values():
        for p,base in [(VERIFY/meta['path'],VERIFY),(cache(meta),ROOT/'.git/lfs/objects')]:
            p=safe(p,base)
            if p.exists() and p.stat().st_size==meta['compressed_bytes'] and hashfile(p)==meta['compressed_sha256']:
                reclaimed+=p.stat().st_size;p.unlink()
    state('complete',archive_commit=commit,deleted_files=len(deleted),deleted_bytes=sum(x['bytes'] for x in deleted),temporary_cache_bytes=reclaimed)
    run(['git','add','--','review/comsol_archive_20261001'])
    run(['git','-c','user.name=cfx-songshi','-c','user.email=z58599517@gmail.com','commit','--only','-m','Record verified COMSOL archive and local data deletion','--','review/comsol_archive_20261001'])
    run(['git','push','origin','main'])
def main():
    REVIEW.mkdir(parents=True,exist_ok=True)
    m=build()
    receipt=REVIEW/'publication.json'
    if receipt.exists():
        commit=json.loads(receipt.read_text())['commit']
        run(['git','fetch','origin','main'])
        run(['git','merge-base','--is-ancestor',commit,'origin/main'])
        if json.loads(subprocess.check_output(['git','show',commit+':'+PREFIX+'/manifest.json'],cwd=ROOT))!=m:raise RuntimeError('Published manifest differs')
    else:
        commit=publish(m);save(receipt,dict(commit=commit,time=now()))
    download(m,commit);cleanup(m,commit)
if __name__=='__main__':
    try:main()
    except Exception as e:state('failed',error=type(e).__name__+': '+str(e));raise
