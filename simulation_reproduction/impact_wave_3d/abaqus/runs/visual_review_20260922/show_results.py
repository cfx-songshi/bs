from abaqus import *
from abaqusConstants import *
import visualization
import os, sys, json, traceback
ROOT = r'D:/bs_thesis/simulation_reproduction/impact_wave_3d/abaqus'
OUT = os.path.join(ROOT, 'runs/visual_review_20260922')
sys.path.insert(0, ROOT)
from read_odb_wave import sensor_series, compare
def main():
    names = ['wav_base', 'wav_d03_r08', 'wav_d08_r31']
    odbs = [session.openOdb(name=os.path.join(ROOT, 'runs/impact', n+'.odb'), readOnly=True) for n in names]
    steps = [o.steps['WAVE'] for o in odbs]
    info = json.load(open(os.path.join(ROOT, 'runs/impact/wav_base.sensors.json')))
    vp = session.viewports['Viewport: 1']
    vp.restore()
    width, height = session.drawingArea.width, session.drawingArea.height
    w, h = width/2.0, height/2.0
    vp.setValues(origin=(0,h), width=w, height=h)
    right = session.Viewport(name='Large disbond - U3', origin=(w,h), width=w, height=h)
    low1 = session.Viewport(name='R1 velocity comparison', origin=(0,0), width=w, height=h)
    low2 = session.Viewport(name='R2 velocity comparison', origin=(w,0), width=w, height=h)
    for v, o, s in [(vp,odbs[0],steps[0]), (right,odbs[2],steps[2])]:
        v.setValues(displayedObject=o)
        v.odbDisplay.setPrimaryVariable(variableLabel='U', outputPosition=NODAL, refinement=(COMPONENT,'U3'))
        v.odbDisplay.display.setValues(plotState=(CONTOURS_ON_UNDEF,))
        v.odbDisplay.commonOptions.setValues(visibleEdges=NONE)
        v.odbDisplay.setFrame(step=0, frame=min(range(len(s.frames)), key=lambda i:abs(s.frames[i].frameValue-50e-6)))
        v.odbDisplay.contourOptions.setValues(minAutoCompute=OFF,maxAutoCompute=OFF,minValue=-1e-7,maxValue=1e-7)
        v.view.setViewpoint(viewVector=(0,0,1), cameraUpVector=(0,1,0))
        v.view.fitView()
    results = {}
    colors = ['#000000','#0077DD','#DD2200']
    for receiver, v in [('R1',low1),('R2',low2)]:
        sensor = info['sensors'][receiver]
        series = [[(t,x) for t,x in sensor_series(s,(sensor['node'],sensor['element']))['V3'] if t<=90e-6] for s in steps]
        results[receiver] = {names[i]:compare(series[0],series[i]) for i in [1,2]}
        curves=[]
        for i, data in enumerate(series):
            xy=session.XYData(name=receiver+'_'+names[i],data=tuple((t*1e6,x) for t,x in data),xValuesLabel='Time (us)',yValuesLabel='V3 (m/s)')
            c=session.Curve(xyData=xy)
            c.lineStyle.setValues(color=colors[i])
            curves.append(c)
        plot=session.XYPlot(name=receiver+' - baseline and disbond')
        chart=plot.charts[list(plot.charts.keys())[0]]
        chart.setValues(curvesToPlot=tuple(curves))
        v.setValues(displayedObject=plot)
    json.dump(results,open(os.path.join(OUT,'verified_metrics.json'),'w'),indent=2)
    vp.makeCurrent()
    session.printToFile(fileName=os.path.join(OUT,'abaqus_comparison'),format=PNG,canvasObjects=(vp,right,low1,low2))
    open(os.path.join(OUT,'ready.txt'),'w').write('Read-only GUI ready; 50 us wave fields; 0-90 us V3 curves. Metric order: RMS difference, correlation, peak ratio.')
try:
    main()
except Exception:
    open(os.path.join(OUT,'error.txt'),'w').write(traceback.format_exc())
    raise
