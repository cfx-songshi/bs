"""Evict verified uploaded solver payloads; preserve Git LFS pointers and reports."""
import datetime,hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def main():
    proof=json.loads((ROOT/'.git/cleanup_remote_availability.json').read_text())
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/main'],cwd=ROOT,text=True).split()[0]
    if not proof['all_available'] or proof['commit']!=head or remote!=head:raise RuntimeError('Remote verification does not match current commit')
    available={x['oid']:x['size'] for x in proof['objects'] if x['available']}
    targets=json.loads((ROOT/'.git/cleanup_lfs_targets.json').read_text())
    plan=[]
    for item in targets:
        p=(ROOT/item['name']).resolve()
        if not p.is_relative_to(ROOT) or '.git' in p.relative_to(ROOT).parts or p.is_symlink():raise RuntimeError('Unsafe payload path')
        if available.get(item['oid'])!=item['size']:raise RuntimeError('Payload not verified remotely')
        pointer=f"version https://git-lfs.github.com/spec/v1\noid sha256:{item['oid']}\nsize {item['size']}\n".encode()
        s=p.stat()
        if s.st_size==len(pointer) and p.read_bytes()==pointer:continue
        h=hashlib.sha256()
        with p.open('rb') as f:
            while chunk:=f.read(8*1024**2):h.update(chunk)
        if s.st_size!=item['size'] or h.hexdigest()!=item['oid'] or p.stat().st_mtime_ns!=s.st_mtime_ns:raise RuntimeError('Local payload differs; preserving all files')
        plan.append((p,pointer,s,item))
    result={'date':datetime.datetime.now().astimezone().isoformat(),'remote_commit':head,
        'method':'Remote LFS availability and local SHA256 verified; binary payload replaced by its LFS pointer, remote data retained',
        'files':[{'path':x[3]['name'],'bytes':x[3]['size'],'oid':x[3]['oid']} for x in plan],
        'payload_bytes':sum(x[3]['size'] for x in plan),'pointer_bytes':sum(len(x[1]) for x in plan)}
    receipt=ROOT/'review/cloud_sync_20260924/local_payload_eviction.json'
    receipt.write_text(json.dumps({**result,'status':'verified_plan'},ensure_ascii=False,indent=2),encoding='utf8')
    for p,pointer,s,item in plan:
        current=p.stat()
        if current.st_size!=s.st_size or current.st_mtime_ns!=s.st_mtime_ns:raise RuntimeError('File changed during cleanup')
        tmp=p.with_name(p.name+'.evicting');tmp.write_bytes(pointer);tmp.replace(p)
    receipt.write_text(json.dumps({**result,'status':'complete'},ensure_ascii=False,indent=2),encoding='utf8')
    print('EVICTED',len(plan),'files',result['payload_bytes'],'bytes',flush=True)

if __name__=='__main__':main()
