"""Sequential, gated repeat-drop runner. Launch with ordinary Python, not CAE.

Every solver result is read by read_odb_impact_summary.py under Abaqus Python.
No failed/unfinished job is overwritten; rerun in the same directory resumes only
successfully completed jobs. All continuation files and diagnostics remain on disk.
"""
import argparse
import datetime
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import uuid

from repeat_impact import relaxation, preparation, impact

HERE = Path(__file__).resolve().parent
ABAQUS = r'D:\Abaqus\Commands\abaqus.bat'
READER = HERE / 'abaqus' / 'read_odb_impact_summary.py'
HANDOFF = HERE.parent.parent / 'PROJECT_HANDOFF.md'
MARK_START = '<!-- repeat-impact-20260922:start -->'
MARK_END = '<!-- repeat-impact-20260922:end -->'


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')


def continuity(previous, current):
    a, b = previous['damage_end'], current['damage_start']
    error = max([abs(a.get(k, 0.)-b.get(k, 0.)) for k in set(a)|set(b)] or [0.])
    energy_error = abs(previous['energy']['ALLDMD']['last_J']-current['energy']['ALLDMD']['first_J'])
    if error > 1e-6 or energy_error > 1e-9:
        raise RuntimeError('restart damage discontinuity: CSDMG=%g; ALLDMD=%g J' % (error, energy_error))
    balance_jump = current['energy']['ETOTAL']['first_J']-previous['energy']['ETOTAL']['last_J']
    if abs(balance_jump) > 3e-4:
        raise RuntimeError('step-boundary energy jump exceeds 0.1% incident: %g J' % balance_jump)
    current['continuity'] = dict(max_CSDMG_error=error, ALLDMD_error_J=energy_error,
                                 ETOTAL_boundary_jump_J=balance_jump)


def audit_messages(work, name):
    known = ('LINEAR GEOMETRIC KINEMATICS OPTION',
             'LOGARITHMIC INTERPOLATION OF RATE DEPENDENT COHESIVE DAMAGE',
             'OP=NEW ON *CONTACT IS IGNORED',
             'THE OPTION *BOUNDARY,TYPE=DISPLACEMENT HAS BEEN USED',
             'THE OPTION *FIELD IS USED BUT THE OPTION *INITIAL')
    reviewed, unknown = [], []
    for suffix in ('.dat','.msg','.sta'):
        file = work/(name+suffix)
        if not file.exists():
            continue
        text = file.read_text(errors='replace')
        for match in re.finditer(r'\*\*\*(WARNING|ERROR):\s*([^\r\n]+)', text, re.I):
            message = match.group(2).strip()
            if suffix=='.sta' and re.match(r'There are \d+ warning messages in the data', message):
                continue  # the actual .dat messages were individually audited above
            # A wrapped sentence containing "WARNINGS" is not a new warning marker.
            (reviewed if match.group(1).upper()=='WARNING' and
             any(k in message.upper() for k in known) else unknown).append(suffix+': '+message)
    dump(work/(name+'.message_audit.json'),dict(reviewed=reviewed,unresolved=unknown))
    if unknown:
        raise RuntimeError('unreviewed solver message: '+'; '.join(unknown))


class Study:
    def __init__(self, args):
        self.args = args
        self.work = args.work.resolve()
        self.work.mkdir(parents=True, exist_ok=True)
        self.records = []
        self.status = 'preparing'
        self.problem = ''
        self.meta = None
        self.started = time.time()

    def publish(self):
        study = dict(status=self.status, problem=self.problem,
                     updated=datetime.datetime.now().astimezone().isoformat(),
                     work=str(self.work), elapsed_this_controller_h=(time.time()-self.started)/3600,
                     assumptions=dict(energy_J=.29995, hits=self.args.hits, impact_us=500,
                                      alpha_per_s=20000, relaxation_chunk_us=500,
                                      residual_mechanical_limit_J=3e-5, max_speed_limit_m_s=.05,
                                      sources='repeat_impact.py module documentation'),
                     stages=self.records)
        dump(self.work/'study.json', study)
        rows = ['| 次数 | ALLDMD 累计 mJ | 本次冲击增量 mJ | 能量等价半径 mm | 受损界面数 | 峰值力 N | 最大向下位移 µm | 反弹比 |',
                '|---|---|---|---|---|---|---|---|']
        for record in self.records:
            if record['kind'] != 'impact':
                continue
            r = record['metrics']
            rows.append('| %d | %.6f | %.6f | %.4f–%.4f | %d | %.3f | %.3f | %.5f |' %
                (record['hit'], r['energy']['ALLDMD']['last_J']*1e3,
                 r['energy']['ALLDMD']['delta_J']*1e3, *r['energy_equivalent_radius_mm'],
                 sum(x['damaged_nodes']>0 for x in r['interfaces']), r['ball']['force_peak_N'],
                 r['centre']['peak_downward_um'], r['ball']['rebound_ratio']))
        detail = ['| 阶段 | ALLDMD 增量 mJ | 末段板机械能 J | 板最大速度 m/s | ETOTAL 漂移/单次入射能 |',
                  '|---|---|---|---|---|']
        footprint = ['| 次数 | 界面高度 mm | max CSDMG | 受损节点数 | D>0.01 面积 mm² | D≥0.95 面积 mm² | 最远受损半径 mm |',
                     '|---|---|---|---|---|---|---|']
        for record in self.records:
            r = record['metrics']
            detail.append('| %s | %.6f | %.6g | %.6g | %.6g |' % (r['step'],
                r['energy']['ALLDMD']['delta_J']*1e3, r['residual']['plate_mechanical_tail_max_J'],
                r['residual']['plate_max_speed_m_s'], r['etotal_delta_over_incident']))
            if record['kind'] == 'impact':
                for x in r['interfaces']:
                    footprint.append('| %d | %.3f | %.6f | %d | %.6f | %.6f | %.6f |' %
                        (record['hit'],x['height_mm'],x['max_CSDMG'],x['damaged_nodes'],
                         x['area_D_gt_0p01_mm2'],x['area_D_ge_0p95_mm2'],x['max_damage_radius_mm']))
        text = ('### 多次落球 restart 累积（2026-09-22，自动更新）\n\n'
                '状态：**%s**。更新时间：%s。工作目录：`%s`。\n\n' % (self.status, study['updated'], self.work) +
                ('停止原因：%s\n\n' % self.problem if self.problem else '') +
                '同点约 0.300 J × %d 次；每次 500 µs；每次间以数值质量比例阻尼 α=20000 s⁻¹ 衰减，'
                '自由冲击时关闭。α、500 µs 检查间隔、3e-5 J / 0.05 m/s 静止判据均为本轮工程假设，非实测参数；'
                '关键词出处见 `repeat_impact.py`。板状态不清零，黏聚接触不重建。\n\n' % self.args.hits +
                '\n'.join(rows) + '\n\n' + '\n'.join(detail) + '\n\n' + '\n'.join(footprint) + '\n\n' +
                '**未解决/引用边界**：冲击应力场未收敛；界面刚度导致约两倍面积敏感性；没有实物验证；'
                '数值衰减不代表真实等待时间，阻尼敏感性尚未完成；间隔期间增加的 ALLDMD 单列，不归为下一次冲击增量。'
                'ALLDMD/Gc 是多界面汇总的完全断裂能量等价面积，部分损伤也贡献耗散，半径区间不是实际几何半径的严格界限。'
                '逐界面面积是结构网格节点控制面积的阈值估计，阈值与网格均影响结果；不能把总等价圆复制到每个界面。'
                '本表响应为机械冲击响应，本轮未新跑导波。第 1 次球初始相切，后续自由释放留 0.1 mm 间隙（约 8 µs 飞行），'
                '入射能量相同但步内接触起点略有不同。\n')
        (self.work/'summary.md').write_text(text, encoding='utf-8')
        if self.args.production:
            (HERE/'repeat_impact_summary.md').write_text(text, encoding='utf-8')
            # Keep metrics, not binary solver artifacts, in the versionable result.
            compact = json.loads(json.dumps(study))
            for rec in compact['stages']:
                rec['metrics'].pop('damage_start', None)
                rec['metrics'].pop('damage_end', None)
            dump(HERE/'repeat_impact_summary.json', compact)
            handoff = HANDOFF.read_text(encoding='utf-8')
            block = MARK_START+'\n'+text+MARK_END
            if MARK_START in handoff:
                before, tail = handoff.split(MARK_START, 1)
                _, after = tail.split(MARK_END, 1)
                handoff = before+block+after
            else:
                pos = handoff.index('以下为原交接记录')
                handoff = handoff[:pos]+block+'\n\n'+handoff[pos:]
            HANDOFF.write_text(handoff, encoding='utf-8', newline='\n')

    def job(self, name, deck=None, old=None):
        self.status = 'running '+name
        self.publish()
        inp = self.work/(name+'.inp')
        if deck is not None:
            if inp.exists() and inp.read_text(encoding='ascii') != deck:
                raise RuntimeError('deck mismatch; refusing overwrite: '+str(inp))
            if not inp.exists():
                inp.write_text(deck, encoding='ascii')
        sta = self.work/(name+'.sta')
        if (self.work/(name+'.lck')).exists():
            raise RuntimeError('job still locked: '+name)
        if sta.exists() and 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in sta.read_text(errors='replace'):
            audit_messages(self.work,name)
            return
        if (self.work/(name+'.odb')).exists() or (self.work/(name+'.lck')).exists():
            raise RuntimeError('unfinished/existing job requires inspection: '+name)
        if shutil.disk_usage(self.work).free < 8*1024**3:
            raise RuntimeError('less than 8 GiB free: stop before new job')
        cmd = [ABAQUS, 'job='+name, 'input='+name+'.inp', 'double=explicit', 'interactive']
        if old:
            cmd.append('oldjob='+old)
        start = time.time()
        with (self.work/(name+'.launch.txt')).open('w') as out:
            done = subprocess.run(cmd, cwd=self.work, stdout=out, stderr=subprocess.STDOUT)
        dump(self.work/(name+'.timing.json'), dict(wall_s=time.time()-start, command=cmd, returncode=done.returncode))
        if done.returncode or not sta.exists() or 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' not in sta.read_text(errors='replace'):
            raise RuntimeError('solver failed: '+name+'; inspect launch/dat/msg/sta')
        if (self.work/(name+'.lck')).exists():
            raise RuntimeError('lock remains after solver exit: '+name)
        audit_messages(self.work,name)

    def read(self, name, step, duration, kind, hit, previous=None):
        dest = self.work/(name+'_'+step+'.json')
        fresh = self.work/(name+'_'+step+'.'+uuid.uuid4().hex+'.json')
        cmd = [ABAQUS, 'python', str(READER), str(self.work/(name+'.odb')),
               '--ball-mass','3.9676e-3','--step',step,'--expected-us',str(duration*1e6),
               '--ball-node',str(self.meta['ball_node']),'--top-node',str(self.meta['top_node']),
               '--json',str(fresh)]
        done = subprocess.run(cmd, cwd=self.work, capture_output=True, text=True, errors='replace')
        (self.work/(name+'_'+step+'.read.txt')).write_text(done.stdout+done.stderr, encoding='utf-8')
        # abaqus.bat can return 0 even when the Python script raises SystemExit.
        # A unique fresh result prevents a stale JSON from concealing that failure.
        if done.returncode or not fresh.exists():
            raise RuntimeError('reader failed: '+name+' '+step+'; '+(done.stdout+done.stderr)[-1800:])
        r = json.loads(fresh.read_text(encoding='utf-8'))
        fresh.replace(dest)
        if previous:
            continuity(previous, r)
        self.records.append(dict(job=name, kind=kind, hit=hit, metrics=r))
        self.publish()
        if abs(r['etotal_delta_over_incident']) > .01:
            raise RuntimeError('energy drift above 1% incident energy: '+name)
        if r['energy']['ALLDMD']['delta_J'] < -1e-9:
            raise RuntimeError('damage energy decreased: '+name)
        if any(r['damage_end'].get(k,0.) < v-1e-6 for k,v in r['damage_start'].items()):
            raise RuntimeError('a previously damaged interface healed: '+name)
        if r['energy']['ALLAE']['peak_abs_J'] > 3e-4:
            raise RuntimeError('unexpected artificial strain energy: '+name)
        return r

    def settled(self, r):
        q = r['residual']
        return q['plate_mechanical_tail_max_J'] < 3e-5 and q['plate_max_speed_m_s'] < .05

    def run(self):
        first = 'acc_n01' if self.args.production else 'coupon_first'
        if not (self.work/(first+'.inp')).exists():
            mesh = ['--nx','79','--ny','79','--nz','8','--centre-size','1.5e-4'] if self.args.production else ['--nx','19','--ny','19','--nz','2']
            cmd = [sys.executable,str(HERE/'make_impact_wave_inp.py'), *mesh,
                   '--contact-scope','interfaces','--cohesive-stiffness','2.37e13',
                   '--drop-mm','7709','--impact-us','500','--settle-alpha','20000',
                   '--out',str(self.work/(first+'.inp'))]
            done = subprocess.run(cmd,cwd=HERE,capture_output=True,text=True)
            (self.work/'generation.txt').write_text(done.stdout+done.stderr)
            if done.returncode or 'self check: clean' not in done.stdout:
                raise RuntimeError('generation/self-check failed')
        self.meta = json.loads((self.work/(first+'.sensors.json')).read_text())['impact']
        self.job(first)
        r = self.read(first,'IMPACT',500e-6,'impact',1)
        if abs(r['ball']['v3_first_m_s']+self.meta['speed']) > .001:
            raise RuntimeError('incorrect first incident velocity')
        if self.args.production:
            # Prior refined calibration: 0.9267 mJ. Damping is OFF, so it should reproduce.
            if abs(r['energy']['ALLDMD']['last_J']/.0009267-1) > .02:
                raise RuntimeError('first hit differs >2% from prior imp_mid damage; inspect before continuing')
        current = first
        for hit in range(2,self.args.hits+1):
            if r['ball']['v3_last_m_s'] <= 0 or r['ball']['force_tail_max_N'] > max(1.,abs(r['ball']['force_peak_N'])*.01):
                raise RuntimeError('ball not demonstrably separated at end of impact')
            if r['residual']['conservative_ball_gap_m'] <= 0:
                raise RuntimeError('no positive conservative separation gap')
            for chunk in range(1,5):
                name = 'acc_n%02d_relax%d' % (hit,chunk)
                park = max(.003,r['ball']['u3_last_m']+max(0.,r['ball']['v3_last_m_s'])*25e-6)
                self.job(name,relaxation(r['step_number'],name,r['ball']['u3_last_m'],r['ball']['v3_last_m_s'],park=park),current)
                previous = r
                r = self.read(name,name,500e-6,'relax',hit,previous)
                current = name
                if self.settled(r):
                    break
            else:
                raise RuntimeError('not settled after 4 x 500 us; no next hit submitted')
            name = 'acc_n%02d_prepare' % hit
            self.job(name,preparation(r['step_number'],name,r['ball']['u3_last_m'],self.meta['speed']),current)
            r = self.read(name,name+'_POSITION',100e-6,'position',hit,r)
            if r['energy']['ALLDMD']['delta_J'] > 1e-7:
                raise RuntimeError('positioning added damage; investigate possible unintended contact')
            r = self.read(name,name+'_LAUNCH',50e-6,'launch',hit,r)
            if r['energy']['ALLDMD']['delta_J'] > 1e-7:
                raise RuntimeError('launch added damage before free impact')
            if not self.settled(r) or r['residual']['conservative_ball_gap_m'] < 50e-6:
                raise RuntimeError('launch hit moving plate or lost free-flight clearance')
            if abs(r['ball']['v3_last_m_s']+self.meta['speed']) > .001:
                raise RuntimeError('launch speed differs from target')
            prep = name
            name = 'acc_n%02d' % hit
            self.job(name,impact(r['step_number'],name),prep)
            r = self.read(name,name,500e-6,'impact',hit,r)
            if abs(r['ball']['v3_first_m_s']+self.meta['speed']) > .001:
                raise RuntimeError('velocity not preserved after releasing ball')
            current = name
        self.status = 'completed'
        self.publish()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--hits',type=int,default=3)
    p.add_argument('--production',action='store_true')
    args = p.parse_args()
    if not 1<=args.hits<=3:
        p.error('--hits must be 1..3')
    study = Study(args)
    try:
        study.run()
    except Exception as exc:
        study.status='stopped: needs inspection'
        study.problem=str(exc)
        study.publish()
        traceback.print_exc()
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
