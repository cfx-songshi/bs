"""Lossless, content-addressed compressed archive of the 107 pending solver files.

Does not delete source files. Each file is independently hashed; shared chunks are
stored once. Manifest completion is atomic and reproducible restore is separate.
"""
import concurrent.futures,datetime,hashlib,json,lzma,os,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'archives/solver_archive_20260924'
CHUNKS=OUT/'chunks'
CHUNK_BYTES=16*1024**2

def compress(raw,oid):
    target=CHUNKS/(oid+'.xz')
    if target.exists():
        encoded=target.read_bytes()
        if hashlib.sha256(lzma.decompress(encoded)).hexdigest()!=oid:
            raise RuntimeError('Existing chunk failed integrity: '+oid)
    else:
        encoded=lzma.compress(raw,preset=3)
        tmp=target.with_suffix('.tmp');tmp.write_bytes(encoded);tmp.replace(target)
    return dict(raw_sha256=oid,raw_bytes=len(raw),path='chunks/'+target.name,
                compressed_bytes=len(encoded),compressed_sha256=hashlib.sha256(encoded).hexdigest())

def main():
    CHUNKS.mkdir(parents=True,exist_ok=True)
    source=json.loads((ROOT/'review/cloud_sync_20260924/upload_inventory.json').read_text(encoding='utf8'))
    pending=[x for x in source['files'] if x['status']=='pending_large_file']
    assert len(pending)==107
    known={};files=[];futures={}
    def collect(block=False):
        done=[o for o,f in futures.items() if f.done()]
        if block and not done:
            concurrent.futures.wait(futures.values(),return_when=concurrent.futures.FIRST_COMPLETED)
            done=[o for o,f in futures.items() if f.done()]
        for oid in done:known[oid]=futures.pop(oid).result()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for i,item in enumerate(pending,1):
            path=(ROOT/item['path']).resolve()
            if not path.is_relative_to(ROOT) or path.is_symlink():raise RuntimeError('Unsafe source path')
            before=path.stat()
            if before.st_size!=item['bytes']:raise RuntimeError('Source size changed: '+str(path))
            full=hashlib.sha256();parts=[]
            with path.open('rb') as f:
                while raw:=f.read(CHUNK_BYTES):
                    full.update(raw);oid=hashlib.sha256(raw).hexdigest();parts.append(oid)
                    if oid not in known and oid not in futures:
                        while len(futures)>=8:collect(True)
                        futures[oid]=pool.submit(compress,raw,oid)
                    collect()
            after=path.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise RuntimeError('Source changed during read')
            files.append(dict(path=item['path'],bytes=before.st_size,mtime_ns=before.st_mtime_ns,
                              sha256=full.hexdigest(),chunks=parts))
            print('ARCHIVED',i,'/107',path.name,'unique_chunks',len(known)+len(futures),flush=True)
        while futures:collect(True)
    manifest=dict(format='sha256-content-chunks-xz-v1',created=datetime.datetime.now().astimezone().isoformat(),
                  chunk_bytes=CHUNK_BYTES,source_root=str(ROOT),files=files,chunks=known,
                  raw_bytes=sum(x['bytes'] for x in files),stored_bytes=sum(x['compressed_bytes'] for x in known.values()))
    tmp=OUT/'manifest.tmp';tmp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(OUT/'manifest.json')
    print('DONE',len(files),'files',len(known),'unique chunks','compressed GiB',manifest['stored_bytes']/1024**3,flush=True)

if __name__=='__main__':main()
