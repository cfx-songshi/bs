"""Check remote download availability for every unique LFS object at HEAD.

SSH authorization and signed URLs stay in memory and are never printed/saved.
This checks server availability, not a full re-download of all binary payloads.
"""
import datetime,json,subprocess,sys,urllib.request
from pathlib import Path

items=json.loads(subprocess.check_output(['git','lfs','ls-files','--json']))['files']
objects={x['oid']:{'oid':x['oid'],'size':x['size']} for x in items}
auth_run=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',
    'git@github.com','git-lfs-authenticate cfx-songshi/bs.git download'],capture_output=True,text=True,timeout=30)
if auth_run.returncode:raise RuntimeError('SSH LFS download authorization failed')
auth=json.loads(auth_run.stdout)
checks=[];values=list(objects.values())
for start in range(0,len(values),100):
    batch=values[start:start+100]
    req=urllib.request.Request(auth['href'].rstrip('/')+'/objects/batch',
        data=json.dumps({'operation':'download','transfers':['basic'],'objects':batch}).encode(),
        headers={**auth.get('header',{}),'Content-Type':'application/vnd.git-lfs+json','Accept':'application/vnd.git-lfs+json'})
    with urllib.request.urlopen(req,timeout=30) as response:data=json.load(response)
    received={o['oid']:o for o in data.get('objects',[])}
    for expected in batch:
        obj=received.get(expected['oid'],{})
        checks.append(dict(expected,available=bool(obj.get('actions',{}).get('download')) and not obj.get('error') and obj.get('size')==expected['size'],error=obj.get('error')))
result=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    checked_at=datetime.datetime.now().astimezone().isoformat(),
    method='Authenticated LFS download batch: object exists, size matches, download action returned; full payload not re-downloaded',
    files=len(items),unique_objects=len(checks),bytes=sum(o['size'] for o in values),
    all_available=all(x['available'] for x in checks),objects=checks)
Path(sys.argv[1]).write_text(json.dumps(result,indent=2),encoding='utf8')
print('REMOTE_LFS',sum(x['available'] for x in checks),'/',len(checks),'available')
raise SystemExit(0 if result['all_available'] else 1)
