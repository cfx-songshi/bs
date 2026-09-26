"""Verify all restored bytes from the separately downloaded remote archive."""
import concurrent.futures,datetime,hashlib,json,lzma,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/'.git/solver_remote_verify'
RECEIPT=ROOT/'review/cloud_sync_20260924/solver_archive_remote_verification.json'

def main():
    downloaded=json.loads((ARCHIVE/'download_receipt.json').read_text())
    raw=(ARCHIVE/'manifest.json').read_bytes()
    committed=subprocess.check_output(['git','show',downloaded['commit']+':archives/solver_archive_20260924/manifest.json'])
    if raw!=committed:raise RuntimeError('Remote manifest mismatch')
    m=json.loads(raw)
    def check(entry):
        h=hashlib.sha256();size=0
        for oid in entry['chunks']:
            meta=m['chunks'][oid];p=(ARCHIVE/meta['path']).resolve()
            if not p.is_relative_to(ARCHIVE):raise RuntimeError('Unsafe chunk path')
            encoded=p.read_bytes()
            if len(encoded)!=meta['compressed_bytes'] or hashlib.sha256(encoded).hexdigest()!=meta['compressed_sha256']:
                raise RuntimeError('Compressed chunk mismatch')
            data=lzma.decompress(encoded)
            if len(data)!=meta['raw_bytes'] or hashlib.sha256(data).hexdigest()!=oid:raise RuntimeError('Raw chunk mismatch')
            h.update(data);size+=len(data)
        if size!=entry['bytes'] or h.hexdigest()!=entry['sha256']:raise RuntimeError('Original file mismatch')
        print('REMOTE_RESTORED_OK',entry['path'],flush=True)
        return {'path':entry['path'],'bytes':size,'sha256':h.hexdigest(),'verified':True}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:files=list(pool.map(check,m['files']))
    result={'commit':downloaded['commit'],'verified_at':datetime.datetime.now().astimezone().isoformat(),
        'method':'Fresh authenticated remote LFS downloads, compressed and raw chunk SHA256, full reconstructed file SHA256',
        'manifest_sha256':hashlib.sha256(raw).hexdigest(),'all_verified':True,'files':files,
        'original_bytes':sum(x['bytes'] for x in files),'compressed_bytes':m['stored_bytes'],'chunks':len(m['chunks'])}
    RECEIPT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('ALL_REMOTE_RESTORE_OK',len(files),flush=True)

if __name__=='__main__':main()
