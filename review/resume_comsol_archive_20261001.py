"""Finish the active archive pipeline; bounded retries, no independent deletion."""
import datetime,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'review/comsol_archive_20261001'
def stamp(stage,**extra):
    (OUT/'continuation.json').write_text(json.dumps(dict(stage=stage,time=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),**extra),indent=2),encoding='utf-8')
def main():
    active=int(sys.argv[1])
    stamp('waiting_for_existing_pipeline',pid=active)
    while True:
        # Match both PID and the exact task filename; reused PIDs do not keep us waiting.
        query=f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={active}'; if ($p.Name -eq 'python.exe' -and $p.CommandLine -like '*archive_comsol_20261001.py*') {{ 'ACTIVE' }}"
        if 'ACTIVE' not in subprocess.check_output(['powershell','-NoProfile','-Command',query],text=True):break
        time.sleep(30)
    for attempt in range(1,4):
        receipt=OUT/'deletion_receipt.json'
        if receipt.exists() and json.loads(receipt.read_text())['status']=='complete':
            stamp('publishing_completed_receipts')
            paths=['review/comsol_archive_20261001','review/archive_comsol_20261001.py','review/resume_comsol_archive_20261001.py']
            subprocess.run(['git','add','--',*paths],cwd=ROOT,check=True)
            if subprocess.run(['git','diff','--cached','--quiet','--',*paths],cwd=ROOT).returncode:
                subprocess.run(['git','-c','user.name=cfx-songshi','-c','user.email=z58599517@gmail.com','commit','--only','-m','Record COMSOL archive completion and continuation safeguards','--',*paths],cwd=ROOT,check=True)
            subprocess.run(['git','-c','core.sshCommand=ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=6','push','origin','main'],cwd=ROOT,check=True)
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/main'],cwd=ROOT,text=True).split()[0]
            if head!=remote:raise RuntimeError('Completion publication mismatch')
            stamp('complete',commit=head);return
        status=json.loads((OUT/'status.json').read_text())
        if status['stage']=='failed' and any(word in status.get('error','') for word in ['Original changed','Source changed','mismatch','Unsafe','Solver process active','Link refused']):
            stamp('stopped_requires_inspection',reason=status.get('error'));return
        stamp('continuing_pipeline',attempt=attempt)
        with (OUT/f'continuation_attempt_{attempt}.log').open('w',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,'-u',str(ROOT/'review/archive_comsol_20261001.py')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:time.sleep(30)
    receipt=OUT/'deletion_receipt.json'
    stamp('complete' if receipt.exists() and json.loads(receipt.read_text())['status']=='complete' else 'retry_limit_reached_originals_not_assumed_deleted')
if __name__=='__main__':
    try:main()
    except Exception as e:stamp('stopped_requires_inspection',error=type(e).__name__+': '+str(e));raise
