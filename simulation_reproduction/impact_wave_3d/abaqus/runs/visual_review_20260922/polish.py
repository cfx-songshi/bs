from abaqus import *
from abaqusConstants import *
import visualization
import os, traceback
OUT=r'D:/bs_thesis/simulation_reproduction/impact_wave_3d/abaqus/runs/visual_review_20260922'
try:
    names=['Viewport: 1','Large disbond - U3','R1 velocity comparison','R2 velocity comparison']
    w=session.drawingArea.width*0.46
    h=session.drawingArea.height*0.43
    for i,name in enumerate(names):
        v=session.viewports[name]
        v.setValues(origin=((i%2)*w,(1-i//2)*h),width=w,height=h)
        if i<2:
            v.viewportAnnotationOptions.setValues(title=OFF,state=OFF,compass=OFF,triad=OFF,legendFont='-*-verdana-medium-r-normal-*-10-*-*-*-p-*-*-*')
            v.view.fitView()
    for name in session.xyPlots.keys():
        p=session.xyPlots[name]
        c=p.charts[list(p.charts.keys())[0]]
        c.axes1[0].axisData.setValues(useSystemTitle=False,title='Time (us)')
        c.axes2[0].axisData.setValues(useSystemTitle=False,title='V3 (m/s)')
    session.viewports['Viewport: 1'].makeCurrent()
    session.printToFile(fileName=os.path.join(OUT,'abaqus_comparison'),format=PNG,canvasObjects=tuple(session.viewports[n] for n in names))
except Exception:
    open(os.path.join(OUT,'polish_error.txt'),'w').write(traceback.format_exc())
