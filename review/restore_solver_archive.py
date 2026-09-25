"""Verify or restore the lossless solver archive. Existing files are never overwritten.

python review/restore_solver_archive.py archives/solver_archive_20260924 --verify-only
python review/restore_solver_archive.py archives/solver_archive_20260924 --destination D:/restore
"""
import argparse,hashlib,json,lzma
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive',type=Path)
    p.add_argument('--destination',type=Path)
    p.add_argument('--verify-only',action='store_true')
    a=p.parse_args()
    if not a.verify_only and a.destination is None:p.error('Choose --verify-only or --destination')
    root=a.archive.resolve();m=json.loads((root/'manifest.json').read_text(encoding='utf8'))
    verified=set();total=0
    for entry in m['files']:
        dest=(a.destination.resolve()/entry['path']).resolve() if a.destination else None
        if dest is not None and not dest.is_relative_to(a.destination.resolve()):raise RuntimeError('Unsafe destination')
        if dest is not None and dest.exists():raise RuntimeError('Refusing overwrite: '+str(dest))
        writing=dest is not None and not a.verify_only
        if writing:dest.parent.mkdir(parents=True,exist_ok=True)
        tmp=dest.with_name(dest.name+'.restoring') if writing else None
        out=tmp.open('xb') if writing else None
        h=hashlib.sha256();length=0
        try:
            for oid in entry['chunks']:
                meta=m['chunks'][oid];path=(root/meta['path']).resolve()
                if not path.is_relative_to(root):raise RuntimeError('Unsafe archive path')
                encoded=path.read_bytes()
                if oid not in verified:
                    assert len(encoded)==meta['compressed_bytes']
                    assert hashlib.sha256(encoded).hexdigest()==meta['compressed_sha256']
                raw=lzma.decompress(encoded)
                assert len(raw)==meta['raw_bytes'] and hashlib.sha256(raw).hexdigest()==oid
                verified.add(oid);h.update(raw);length+=len(raw)
                if out:out.write(raw)
            assert length==entry['bytes'] and h.hexdigest()==entry['sha256'],entry['path']
        finally:
            if out:out.close()
        if writing:tmp.replace(dest)
        total+=length
        print('VERIFIED',entry['path'],flush=True)
    print('ALL_OK',len(m['files']),'files',total,'bytes',flush=True)

if __name__=='__main__':main()
