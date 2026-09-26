"""Finish upload, independently verify remote restoration, then remove 107 originals.

Run from the repository root. Fails closed: no source removal before complete
remote verification and a second complete local source hash audit.
"""
import concurrent.futures,datetime,hashlib,json,os,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REVIEW=ROOT/'review/cloud_sync_20260924'
STATE=REVIEW/'solver_archive_completion.status.json'
PREFIX='archives/solver_archive_20260924'

def state(stage,**extra):
    data={'stage':stage,'time':datetime.datetime.now().astimezone().isoformat(),**extra}
    tmp=STATE.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(STATE)
    print(stage,flush=True)

def run(args,log):
    with (ROOT/'.git'/log).open('w',encoding='utf8') as out:
        r=subprocess.run(args,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
    if r.returncode:raise RuntimeError(f'{args[0]} failed; see .git/{log}')

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def main():
    os.chdir(ROOT)
    os.environ.update(HTTPS_PROXY='http://127.0.0.1:7890',HTTP_PROXY='http://127.0.0.1:7890',
        GIT_SSH_COMMAND='ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=6',GIT_LFS_FORCE_PROGRESS='1')
    resume_verified=sys.argv[1:]==['--resume-verified']
    upload_pid=int(sys.argv[1]) if len(sys.argv)>1 and not resume_verified else None
    if upload_pid:
        state('waiting_for_current_upload',pid=upload_pid)
        while True:
            query=f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={upload_pid}'; if ($p.Name -eq 'git-lfs.exe' -and $p.CommandLine -eq 'git-lfs push origin HEAD') {{ 'RUNNING' }}"
            if 'RUNNING' not in subprocess.check_output(['powershell','-NoProfile','-Command',query],text=True):break
            time.sleep(20)
    cfg=['git','-c','lfs.concurrenttransfers=16','-c','lfs.https://github.com/cfx-songshi/bs.git/info/lfs.locksverify=false']
    if resume_verified:
        run(['git','fetch','origin'],'solver_final_fetch.log')
        finish_cleanup(cfg)
        return
    state('ensuring_all_lfs_objects_uploaded')
    for attempt in range(3):
        try:
            run(cfg+['lfs','push','origin','HEAD'],'solver_final_lfs_push.log')
            break
        except RuntimeError:
            source=ROOT/'.git/solver_final_lfs_push.log'
            saved=ROOT/'.git'/('solver_lfs_failed_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'.log')
            saved.write_bytes(source.read_bytes())
            if attempt==2:raise
            state('retrying_interrupted_upload',attempt=attempt+2)
            time.sleep(30)
    state('pushing_archive_commit')
    run(cfg+['push','origin','main'],'solver_final_git_push.log')
    run(['git','fetch','origin'],'solver_final_fetch.log')
    if git('rev-parse','HEAD')!=git('rev-parse','origin/main'):raise RuntimeError('Remote branch mismatch')
    state('downloading_remote_archive')
    run([sys.executable,'-u','review/download_solver_archive.py'],'solver_remote_download.log')
    state('verifying_remote_reconstruction')
    run([sys.executable,'-u','review/verify_downloaded_solver_archive.py'],'solver_remote_restore.log')
    finish_cleanup(cfg)

def finish_cleanup(cfg):
    receipt=json.loads((REVIEW/'solver_archive_remote_verification.json').read_text(encoding='utf8'))
    manifest_raw=subprocess.check_output(['git','show',receipt['commit']+':'+PREFIX+'/manifest.json'])
    manifest=json.loads(manifest_raw)
    if json.loads((ROOT/PREFIX/'manifest.json').read_bytes())!=manifest:raise RuntimeError('Working manifest content changed')
    if not receipt['all_verified'] or receipt['manifest_sha256']!=hashlib.sha256(manifest_raw).hexdigest():raise RuntimeError('Verification receipt mismatch')
    if len(receipt['files'])!=107 or len(manifest['files'])!=107:raise RuntimeError('Unexpected source count')
    expected={e['path']:(e['bytes'],e['sha256']) for e in manifest['files']}
    actual={e['path']:(e['bytes'],e['sha256']) for e in receipt['files'] if e['verified']}
    if actual!=expected:raise RuntimeError('Verified file list mismatch')
    source_commit=receipt['commit']
    if subprocess.run(['git','merge-base','--is-ancestor',source_commit,'origin/main']).returncode:raise RuntimeError('Archive commit not on remote')
    state('auditing_originals_before_cleanup')
    solver_check="@(Get-CimInstance Win32_Process -Filter \"Name='explicit_dp.exe' OR Name='standard.exe'\").Count"
    if int(subprocess.check_output(['powershell','-NoProfile','-Command',solver_check],text=True).strip()):raise RuntimeError('A solver is running; cleanup deferred')
    targets=[]
    def audit(entry):
        p=(ROOT/entry['path']).resolve()
        allowed=(ROOT/'simulation_reproduction/impact_wave_3d/abaqus/runs/impact').resolve()
        if not p.is_relative_to(allowed) or p.is_symlink() or p.suffix not in {'.odb','.abq','.pac','.stt'}:raise RuntimeError('Unsafe source path')
        before=p.stat();h=hashlib.sha256()
        with p.open('rb') as f:
            while data:=f.read(8*1024**2):h.update(data)
        after=p.stat()
        if before.st_size!=entry['bytes'] or h.hexdigest()!=entry['sha256'] or before.st_mtime_ns!=after.st_mtime_ns:raise RuntimeError('Original changed; preserving sources')
        return {'path':entry['path'],'absolute_path':str(p),'bytes':entry['bytes'],'sha256':entry['sha256'],'mtime_ns':after.st_mtime_ns}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:targets=list(pool.map(audit,manifest['files']))
    plan={'archive_commit':source_commit,'remote_verified':True,'files':targets}
    planpath=REVIEW/'solver_original_cleanup_plan.json';planpath.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8')
    state('removing_verified_originals',count=len(targets))
    deleted=[]
    for entry in targets:
        p=Path(entry['absolute_path']);s=p.stat()
        if s.st_size!=entry['bytes'] or s.st_mtime_ns!=entry['mtime_ns']:raise RuntimeError('Source changed after audit; stopping cleanup')
        # Exact verified path only, no recursive deletion and no shell path interpolation.
        p.unlink();deleted.append(entry)
        result={'archive_commit':source_commit,'deleted_at':datetime.datetime.now().astimezone().isoformat(),
                'count':len(deleted),'bytes':sum(x['bytes'] for x in deleted),'files':deleted}
        (REVIEW/'solver_original_cleanup_receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    note=f'\n\n### 后续更新：{datetime.date.today()} 大文件归档上云并清理本地原件\n\n107 个大型原始求解文件共 {manifest["raw_bytes"]/1024**3:.3f} GiB，已无损分块去重压缩为 {manifest["stored_bytes"]/1024**3:.3f} GiB（{len(manifest["chunks"])} 块），上传至 `archives/solver_archive_20260924/`，归档提交 `{source_commit}`。从远端实际重新下载全部压缩块后，逐块及逐原文件 SHA-256 校验全部通过；随后再次比对本地 107 个原件哈希，才删除对应原件。完整记录见 `review/cloud_sync_20260924/solver_archive_remote_verification.json`、`solver_original_cleanup_receipt.json`。报告、35 个 GIF、代码、输入及其他小型输出保留。需查看原始 ODB 或续算时，先按归档 README 下载 LFS 对象并还原；紧凑报告不替代原始数据。原始文件虽已完整备份，模型未收敛/替代参数/缺少实验验证等科学局限不变。本次没有启动新仿真或执行关机。\n'
    with (ROOT/'PROJECT_HANDOFF.md').open('a',encoding='utf8') as f:f.write(note)
    state('cleanup_complete_publishing_receipts',count=len(deleted),bytes=result['bytes'],archive_commit=source_commit)
    paths=['PROJECT_HANDOFF.md','review/verify_downloaded_solver_archive.py','review/finish_solver_archive.py']
    paths += ['review/cloud_sync_20260924/'+x for x in ['solver_archive_remote_verification.json','solver_original_cleanup_plan.json','solver_original_cleanup_receipt.json']]
    run(['git','add','--',*paths],'solver_receipt_stage.log')
    run(['git','-c','user.name=cfx-songshi','-c','user.email=z58599517@gmail.com','commit','--only','-m','Record verified remote solver archive and remove backed-up local originals','--',*paths],'solver_receipt_commit.log')
    run(cfg+['push','origin','main'],'solver_receipt_push.log')
    remote=git('ls-remote','origin','refs/heads/main').split()[0]
    if remote!=git('rev-parse','HEAD'):raise RuntimeError('Final commit mismatch')
    state('complete',commit=remote,archive_commit=source_commit,deleted_files=len(deleted),deleted_bytes=result['bytes'])

if __name__=='__main__':
    try:main()
    except Exception as exc:
        state('failed',error=str(exc));raise
