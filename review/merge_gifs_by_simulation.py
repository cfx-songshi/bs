"""Join views/steps belonging to the same saved simulation, with explicit segments."""
import json,hashlib,re,shutil,sys
from pathlib import Path
from collections import defaultdict
from PIL import Image,ImageDraw,ImageFont

root=Path(sys.argv[1]).resolve();out=root/'00_by_simulation';out.mkdir(exist_ok=True)
items=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
groups=defaultdict(list)
for x in items:
    p=Path(x['source'])
    if x.get('simulation_identity'):
        identity=x['simulation_identity'];name=x['simulation_name']
    elif p.suffix=='.odb':identity=str(p.with_suffix(''));name=p.stem
    elif p.name in ('fields.npz','signals.csv','sensors.csv','through_thickness.csv','contact_patch.npz'):
        identity=str(p.parent);name=p.parent.name
    else:
        identity=str(p.with_suffix(''));name=p.stem
        if 'gear_example_waveforms' in p.stem:identity+='_'+x['step'];name+='_'+x['step']
        match=re.fullmatch(r'abaqus_(line\d+)_(c3d8r?)_surface',p.stem)
        if match:
            folder,element=match.groups();job='ugw_'+folder
            if folder=='line500':job='ugw_line_'+element
            elif element=='c3d8r':job+='_'+element
            identity=str(Path('D:/abaqus_runs')/folder/job);name=job
    groups[identity].append((name,x))
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',21)
small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
result=[]
for identity,entries in groups.items():
    # ODB order was exported in step order; preserve physical ordering via source metadata inventory.
    entries.sort(key=lambda e:(e[1].get('sequence_order',0 if e[1].get('step')=='IMPACT' else 1 if e[1].get('step')=='WAVE' else 2),e[1]['source'],e[1].get('step','')))
    name=entries[0][0];key=re.sub('[^A-Za-z0-9_-]','_',name)+'__'+hashlib.sha1(identity.encode()).hexdigest()[:8]
    dest=out/(key+'.gif');poster=dest.with_suffix('.png');receipt=dest.with_suffix('.json')
    signature=[(x['key'],Path(x['gif']).stat().st_mtime,x.get('sequence_order')) for _,x in entries]
    if receipt.exists() and json.loads(receipt.read_text(encoding='utf-8')).get('merge_version')==2 and json.loads(receipt.read_text(encoding='utf-8')).get('signature')==[list(x) for x in signature]:
        result.append(json.loads(receipt.read_text(encoding='utf-8')));continue
    if len(entries)==1:
        shutil.copyfile(entries[0][1]['gif'],dest);shutil.copyfile(entries[0][1]['poster'],poster)
        total=entries[0][1]['gif_frames']
    else:
        frames=[]
        for n,(_,x) in enumerate(entries,1):
            with Image.open(x['gif']) as im:
                for i in range(im.n_frames):
                    im.seek(i);frame=im.convert('RGB');draw=ImageDraw.Draw(frame)
                    draw.rectangle((0,0,frame.width,85),fill='#f4f7fb')
                    draw.text((74,18),name+' / 同一算例汇总',font=font,fill='#16324c')
                    label=f"第 {n}/{len(entries)} 段：{Path(x['source']).name} / {x.get('step','')}"
                    draw.text((74,61),label[:95],font=small,fill='#465a70')
                    frames.append(frame)
        strip=Image.new('RGB',(1160,80*len(frames[::8])))
        for n,f in enumerate(frames[::8]):strip.paste(f.resize((1160,80)),(0,n*80))
        pal=strip.quantize(colors=192)
        quant=[f.quantize(palette=pal,dither=Image.Dither.NONE) for f in frames]
        quant[0].save(dest,save_all=True,append_images=quant[1:],duration=150,loop=0,disposal=2,optimize=False)
        # Prefer field-view poster over zero initial state.
        shutil.copyfile(entries[0][1]['poster'],poster);total=len(frames)
        del frames,quant
    with Image.open(dest) as check:
        assert check.n_frames==total,(str(dest),check.n_frames,total)
        for i in range(check.n_frames):check.seek(i);check.load()
    record=dict(merge_version=2,key=key,name=name,identity=identity,gif=str(dest),poster=str(poster),frames=total,
        segments=len(entries),duration_s=total*.15,signature=signature,
        group=entries[0][1]['group'],sources=sorted(set(x['source'] for _,x in entries)),
        caveats=sorted(set(x['caveat'] for _,x in entries)),parts=[x['key'] for _,x in entries])
    receipt.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8');result.append(record)
    print('CASE',name,len(entries),total,flush=True)
(root/'case_manifest.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print('MERGED',len(result),'cases',len(items),'source clips',flush=True)
