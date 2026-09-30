"""Evict only committed LFS simulation payloads after independent remote hash checks."""
import concurrent.futures, datetime, hashlib, json, os, subprocess, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/cleanup_verified_20261001'
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while b:=f.read(8*1024**2): h.update(b)
    return h.hexdigest()
def save(name,data):
    p=OUT/name; t=p.with_suffix('.tmp')
    t.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); t.replace(p)
def main():
    OUT.mkdir(exist_ok=True)
    head=git('rev-parse','HEAD').decode().strip()
    remote=git('ls-remote','origin','refs/heads/main').decode().split()[0]
    if head!=remote: raise RuntimeError('Remote HEAD mismatch')
    items=json.loads((ROOT/'.git/cleanup_candidates_20261001.json').read_text())
    plan=[]
    for x in items:
        p=(ROOT/x['name']).resolve()
        if not p.is_relative_to(ROOT/'simulation_reproduction') and not p.is_relative_to(ROOT/'archives'): raise RuntimeError('Outside allowed roots')
        if p.is_symlink() or p.is_junction(): raise RuntimeError('Link target refused')
        pointer=git('show',head+':'+x['name'])
        expected=f"version https://git-lfs.github.com/spec/v1\noid sha256:{x['oid']}\nsize {x['size']}\n".encode()
        if pointer!=expected: raise RuntimeError('Committed pointer mismatch')
        s=p.stat()
        if s.st_size!=x['size'] or digest(p)!=x['oid']: raise RuntimeError('Modified local data: '+x['name'])
        plan.append(dict(path=x['name'],oid=x['oid'],bytes=x['size'],mtime_ns=s.st_mtime_ns))
    save('plan.json',dict(remote_commit=head,files=plan))
    auth_run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','git@github.com','git-lfs-authenticate cfx-songshi/bs.git download'],capture_output=True,text=True,timeout=30)
    if auth_run.returncode: raise RuntimeError('LFS authorization failed')
    auth=json.loads(auth_run.stdout)
    req=urllib.request.Request(auth['href'].rstrip('/')+'/objects/batch',data=json.dumps({'operation':'download','transfers':['basic'],'objects':[dict(oid=x['oid'],size=x['bytes']) for x in plan]}).encode(),headers={**auth.get('header',{}),'Content-Type':'application/vnd.git-lfs+json','Accept':'application/vnd.git-lfs+json'})
    with urllib.request.urlopen(req,timeout=60) as r: batch=json.load(r)
    actions={x['oid']:x for x in batch['objects']}
    def verify(x):
        o=actions[x['oid']]
        if o.get('error') or o.get('size')!=x['bytes']: raise RuntimeError('Remote missing object')
        a=o['actions']['download']; h=hashlib.sha256(); n=0
        request=urllib.request.Request(a['href'],headers=a.get('header',{}))
        with urllib.request.urlopen(request,timeout=120) as r:
            while b:=r.read(1024**2): h.update(b); n+=len(b)
        if n!=x['bytes'] or h.hexdigest()!=x['oid']: raise RuntimeError('Remote content mismatch')
        print('REMOTE_VERIFIED',x['path'],flush=True)
        return dict(path=x['path'],oid=x['oid'],bytes=n,verified=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: checked=list(pool.map(verify,plan))
    save('remote_verification.json',dict(remote_commit=head,checked_at=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),method='Independent full HTTP download and SHA-256, no local cache fallback',files=checked,all_verified=True))
    # Recheck all sources before the first mutation.
    for x in plan:
        p=ROOT/x['path']; s=p.stat()
        if s.st_size!=x['bytes'] or s.st_mtime_ns!=x['mtime_ns'] or digest(p)!=x['oid']: raise RuntimeError('Source changed; no eviction')
    evicted=[]; caches=[]
    for x in plan:
        p=ROOT/x['path']
        pointer=f"version https://git-lfs.github.com/spec/v1\noid sha256:{x['oid']}\nsize {x['bytes']}\n".encode()
        tmp=p.with_name(p.name+'.verified-eviction'); tmp.write_bytes(pointer); tmp.replace(p)
        evicted.append(x)
        # Only the exact corresponding cache payload, whose bytes were verified remotely.
        oid=x['oid']; cache=(ROOT/'.git/lfs/objects'/oid[:2]/oid[2:4]/oid).resolve()
        if not cache.is_relative_to((ROOT/'.git/lfs/objects').resolve()): raise RuntimeError('Unsafe cache path')
        if cache.exists() and not cache.is_symlink() and cache.stat().st_size==x['bytes'] and digest(cache)==oid:
            cache.unlink(); caches.append(dict(oid=oid,bytes=x['bytes']))
        save('receipt.json',dict(remote_commit=head,status='complete' if len(evicted)==len(plan) else 'in_progress',files=evicted,caches=caches,payload_bytes=sum(v['bytes'] for v in evicted),cache_bytes=sum(v['bytes'] for v in caches)))
    print('COMPLETE',len(evicted),'payload bytes',sum(v['bytes'] for v in evicted),'cache bytes',sum(v['bytes'] for v in caches),flush=True)
if __name__=='__main__': main()
