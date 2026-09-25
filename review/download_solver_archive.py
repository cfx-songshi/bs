"""Download committed archive directly from remote LFS and verify every payload.
Signed URLs and authorization remain in memory. No local LFS fallback is used.
"""
import concurrent.futures,hashlib,json,subprocess,urllib.request,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.git/solver_remote_verify'
PREFIX='archives/solver_archive_20260924/'

def main():
    commit=subprocess.check_output(['git','rev-parse','origin/main'],text=True).strip()
    raw=subprocess.check_output(['git','show',commit+':'+PREFIX+'manifest.json'])
    m=json.loads(raw);OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'manifest.json').write_bytes(raw)
    objects=list(m['chunks'].values())
    def fetch(pair):
        meta,action=pair
        path=OUT/meta['path'];path.parent.mkdir(parents=True,exist_ok=True)
        def valid(data):
            return len(data)==meta['compressed_bytes'] and hashlib.sha256(data).hexdigest()==meta['compressed_sha256']
        if path.exists() and valid(path.read_bytes()):return
        for attempt in range(3):
            try:
                req=urllib.request.Request(action['href'],headers=action.get('header',{}))
                with urllib.request.urlopen(req,timeout=120) as r:data=r.read()
                if not valid(data):raise ValueError('Payload integrity mismatch')
                tmp=path.with_suffix('.part');tmp.write_bytes(data);tmp.replace(path)
                return
            except Exception as exc:
                if attempt==2:raise RuntimeError('Remote download failed: '+type(exc).__name__) from None
                time.sleep(2)
    for start in range(0,len(objects),100):
        batch=objects[start:start+100]
        auth_run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15','git@github.com',
            'git-lfs-authenticate cfx-songshi/bs.git download'],capture_output=True,text=True,timeout=30)
        if auth_run.returncode:raise RuntimeError('SSH LFS authorization failed')
        auth=json.loads(auth_run.stdout)
        req=urllib.request.Request(auth['href'].rstrip('/')+'/objects/batch',
            data=json.dumps({'operation':'download','transfers':['basic'],'objects':[
                {'oid':x['compressed_sha256'],'size':x['compressed_bytes']} for x in batch]}).encode(),
            headers={**auth.get('header',{}),'Content-Type':'application/vnd.git-lfs+json','Accept':'application/vnd.git-lfs+json'})
        try:
            with urllib.request.urlopen(req,timeout=60) as r:result=json.load(r)
        except Exception as exc:raise RuntimeError('LFS batch failed: '+type(exc).__name__) from None
        by_oid={o['oid']:o for o in result['objects']}
        pairs=[]
        for meta in batch:
            obj=by_oid[meta['compressed_sha256']]
            if obj.get('error') or obj['size']!=meta['compressed_bytes']:raise RuntimeError('Remote object unavailable')
            pairs.append((meta,obj['actions']['download']))
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(fetch,pairs))
        print('REMOTE_DOWNLOADED',min(start+100,len(objects)),'/',len(objects),flush=True)
    (OUT/'download_receipt.json').write_text(json.dumps({'commit':commit,'objects':len(objects),
        'compressed_bytes':sum(x['compressed_bytes'] for x in objects),'all_payload_hashes_verified':True},indent=2))
    print('DOWNLOAD_OK',commit,flush=True)

if __name__=='__main__':main()
